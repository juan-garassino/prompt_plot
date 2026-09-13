"""
Shared Pydantic models for PromptPlot v3.0

Core data models used throughout the system: GCodeCommand, GCodeProgram, WorkflowResult.
Merged from PromptPlot core/models.py + drawStream config_handler.py GCodeCommand parsing.
"""

import re
import math
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Optional, Dict, Any, Tuple, Union
from enum import Enum


class GCodeCommand(BaseModel):
    """Single G-code command with coordinates, feed rate, and optional comment."""

    command: str
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None
    f: Optional[int] = None
    s: Optional[int] = None
    p: Optional[float] = None
    color: Optional[int] = None  # pen/color layer index (metadata; not a machine token)
    comment: Optional[str] = None

    @field_validator("command")
    @classmethod
    def validate_command(cls, v):
        if not isinstance(v, str):
            raise ValueError(f"Command must be a string, got {type(v)}")
        v = v.upper().strip()
        if v == "COMPLETE":
            return v
        base_command = v.split()[0] if " " in v else v
        if not base_command.startswith(("G", "M")):
            raise ValueError(f"Command must start with G or M, got {v}")
        valid_commands = [
            "G0",
            "G1",
            "G2",
            "G3",
            "G4",
            "G17",
            "G18",
            "G19",
            "G20",
            "G21",
            "G28",
            "G90",
            "G91",
            "G92",
            "M2",
            "M3",
            "M5",
            "M17",
            "M18",
            "M30",
            "COMPLETE",
        ]
        if base_command not in valid_commands:
            raise ValueError(f"Command must be one of {valid_commands}, got {base_command}")
        return v

    @classmethod
    def from_string(cls, raw: str) -> "GCodeCommand":
        """Parse a raw G-code line like 'G1 X50 Y30 F2000 ; move' into a GCodeCommand."""
        raw = raw.strip()
        if not raw or raw.startswith(";"):
            return cls(command="G0", comment=raw.lstrip("; ") if raw else "")

        comment = None
        color = None
        if ";" in raw:
            parts = raw.split(";", 1)
            raw = parts[0].strip()
            comment = parts[1].strip()
            # Recover a color= tag written by to_gcode()
            if comment and "color=" in comment:
                toks = comment.split()
                kept = []
                for tok in toks:
                    if tok.startswith("color="):
                        try:
                            color = int(tok.split("=", 1)[1])
                            continue
                        except ValueError:
                            pass
                    kept.append(tok)
                comment = " ".join(kept) or None

        tokens = raw.split()
        if not tokens:
            return cls(command="G0", comment=comment, color=color)

        command_type = tokens[0].upper()
        params: Dict[str, Any] = {}
        for token in tokens[1:]:
            if len(token) >= 2 and token[0].upper() in "XYZFSP":
                key = token[0].lower()
                try:
                    value = float(token[1:])
                    if key in ("f", "s", "p"):
                        params[key] = int(value)
                    else:
                        params[key] = value
                except ValueError:
                    continue

        return cls(command=command_type, comment=comment, color=color, **params)

    def to_gcode(self) -> str:
        """Convert to G-code string format."""
        if self.command == "COMPLETE":
            return "COMPLETE"
        parts = [self.command]
        for attr, value in self.model_dump().items():
            if value is not None and attr not in (
                "command",
                "comment",
                "color",
            ):
                if attr == "p":
                    parts.append(f"P{value:g}" if isinstance(value, float) else f"P{value}")
                elif isinstance(value, float):
                    parts.append(f"{attr.upper()}{value:.3f}")
                else:
                    parts.append(f"{attr.upper()}{value}")
        result = " ".join(parts)
        # color is metadata, not a machine token — surface it as a comment so it
        # survives a save→reload round-trip without confusing the firmware.
        comment = self.comment
        if self.color is not None:
            tag = f"color={self.color}"
            comment = f"{comment} {tag}" if comment else tag
        if comment:
            result += f" ; {comment}"
        return result

    def is_movement_command(self) -> bool:
        return self.command in ("G0", "G1", "G2", "G3")

    def is_pen_command(self) -> bool:
        return self.command in ("M3", "M5")

    def is_pen_down(self) -> bool:
        return self.command == "M3"

    def is_pen_up(self) -> bool:
        return self.command == "M5"

    def is_dwell(self) -> bool:
        return self.command == "G4"


class GCodeProgram(BaseModel):
    """Complete G-code program as a list of commands with metadata."""

    commands: List[GCodeCommand]
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

    @field_validator("commands")
    @classmethod
    def validate_commands_not_empty(cls, v):
        if not v:
            raise ValueError("G-code program must contain at least one command")
        return v

    def to_gcode(self) -> str:
        if not self.commands:
            return ""
        return "\n".join(cmd.to_gcode() for cmd in self.commands)

    def get_movement_commands(self) -> List[GCodeCommand]:
        return [cmd for cmd in self.commands if cmd.is_movement_command()]

    def get_pen_commands(self) -> List[GCodeCommand]:
        return [cmd for cmd in self.commands if cmd.is_pen_command()]

    def get_drawing_commands(self) -> List[GCodeCommand]:
        drawing = []
        pen_down = False
        for cmd in self.commands:
            if cmd.is_pen_down():
                pen_down = True
            elif cmd.is_pen_up():
                pen_down = False
            elif cmd.command == "G1" and pen_down:
                drawing.append(cmd)
        return drawing

    def get_bounds(self) -> Optional[Dict[str, float]]:
        movement = self.get_movement_commands()
        if not movement:
            return None
        x_coords = [c.x for c in movement if c.x is not None]
        y_coords = [c.y for c in movement if c.y is not None]
        if not x_coords and not y_coords:
            return None
        bounds = {}
        if x_coords:
            bounds.update({"min_x": min(x_coords), "max_x": max(x_coords)})
        if y_coords:
            bounds.update({"min_y": min(y_coords), "max_y": max(y_coords)})
        return bounds

    def count_by_command_type(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for cmd in self.commands:
            counts[cmd.command] = counts.get(cmd.command, 0) + 1
        return counts


# ---------------------------------------------------------------------------
# Drawing Primitives — high-level shape commands for LLM output
# ---------------------------------------------------------------------------

VALID_PRIMITIVE_TYPES = {
    "circle",
    "ellipse",
    "polygon",
    "hatch",
    "crosshatch",
    "filled_polygon",
    "stipple",
    "spiral",
    "flow_field",
}
VALID_FREEFORM_TYPES = {
    "contour_path",
    "silhouette_outline",
    "texture_strokes",
    "accent_marks",
    "hatch_region",
    "negative_space_region",
    "contour_bundle",
    "gesture_path",
    "shading_region",
    "texture_cluster",
    "detail_pass_region",
    "reserve_region",
    "field_stack",
    "moire_grid",
    "radial_field",
    "ring_field",
    "tiling_field",
    "gradient_hatch_region",
    "noise_warped_flow",
    "mask_region",
    "border_system",
}


class PrimitiveCommand(BaseModel):
    """A high-level drawing primitive (circle, hatch, etc.) that expands to GCode."""

    command: str = "PRIMITIVE"
    type: str
    color: Optional[int] = None  # pen/color layer index applied to all expanded strokes
    params: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("command")
    @classmethod
    def validate_command(cls, v):
        if v != "PRIMITIVE":
            raise ValueError(f"PrimitiveCommand.command must be 'PRIMITIVE', got {v!r}")
        return v

    @field_validator("type")
    @classmethod
    def validate_type(cls, v):
        if v not in VALID_PRIMITIVE_TYPES:
            raise ValueError(
                f"Unknown primitive type {v!r}. Valid: {sorted(VALID_PRIMITIVE_TYPES)}"
            )
        return v


class FreeformCommand(BaseModel):
    """A high-level freeform drawing command expanded into expressive GCode."""

    command: str = "FREEFORM"
    type: str
    color: Optional[int] = None  # pen/color layer index applied to all expanded strokes
    params: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("command")
    @classmethod
    def validate_command(cls, v):
        if v != "FREEFORM":
            raise ValueError(f"FreeformCommand.command must be 'FREEFORM', got {v!r}")
        return v

    @field_validator("type")
    @classmethod
    def validate_type(cls, v):
        if v not in VALID_FREEFORM_TYPES:
            raise ValueError(f"Unknown freeform type {v!r}. Valid: {sorted(VALID_FREEFORM_TYPES)}")
        return v


DrawCommand = Union[GCodeCommand, PrimitiveCommand, FreeformCommand]


def _parse_draw_command(data: dict) -> DrawCommand:
    """Route a command dict to GCodeCommand or PrimitiveCommand."""
    if data.get("command") == "PRIMITIVE":
        return PrimitiveCommand(**data)
    if data.get("command") == "FREEFORM":
        return FreeformCommand(**data)
    return GCodeCommand(**data)


class DrawProgram(BaseModel):
    """Program mixing raw GCode and primitives. Expands to GCodeProgram before execution."""

    commands: List[DrawCommand]
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def parse_mixed_commands(cls, values):
        if isinstance(values, dict) and "commands" in values:
            raw_cmds = values["commands"]
            parsed = []
            for item in raw_cmds:
                if isinstance(item, dict):
                    parsed.append(_parse_draw_command(item))
                else:
                    parsed.append(item)
            values["commands"] = parsed
        return values

    @field_validator("commands")
    @classmethod
    def validate_commands_not_empty(cls, v):
        if not v:
            raise ValueError("DrawProgram must contain at least one command")
        return v

    def has_primitives(self) -> bool:
        return any(isinstance(c, PrimitiveCommand) for c in self.commands)

    def has_freeform(self) -> bool:
        return any(isinstance(c, FreeformCommand) for c in self.commands)


# ---------------------------------------------------------------------------
# Composition Planning (Feature 5)
# ---------------------------------------------------------------------------


class CompositionSubject(BaseModel):
    """A single subject/element in a composition plan."""

    name: str
    description: str = ""
    x: float  # center X position
    y: float  # center Y position
    width: float
    height: float
    density: str = "medium"  # sparse/medium/dense
    priority: int = 1

    @field_validator("density")
    @classmethod
    def validate_density(cls, v):
        if v not in ("sparse", "medium", "dense"):
            raise ValueError(f"density must be sparse/medium/dense, got {v}")
        return v


class CompositionPlan(BaseModel):
    """LLM-generated composition plan for structured drawing."""

    subjects: List[CompositionSubject]
    style: str = "artistic"
    estimated_commands: int = 50
    notes: Optional[str] = None

    @field_validator("subjects")
    @classmethod
    def validate_subjects_not_empty(cls, v):
        if not v:
            raise ValueError("CompositionPlan must have at least one subject")
        return v

    def validate_bounds(self, paper_w: float, paper_h: float) -> List[str]:
        """Check subjects fit within paper bounds. Returns list of violations."""
        violations = []
        for s in self.subjects:
            x_min = s.x - s.width / 2
            x_max = s.x + s.width / 2
            y_min = s.y - s.height / 2
            y_max = s.y + s.height / 2
            if x_min < 0 or x_max > paper_w:
                violations.append(
                    f"Subject '{s.name}' X range [{x_min:.1f}, {x_max:.1f}] outside [0, {paper_w:.1f}]"
                )
            if y_min < 0 or y_max > paper_h:
                violations.append(
                    f"Subject '{s.name}' Y range [{y_min:.1f}, {y_max:.1f}] outside [0, {paper_h:.1f}]"
                )
        return violations

    def to_prompt_guidance(self) -> str:
        """Convert plan to structured text for injection into GCode prompt."""
        lines = ["COMPOSITION PLAN (follow these positions and sizes):"]
        for i, s in enumerate(self.subjects, 1):
            lines.append(
                f"  {i}. {s.name}: center ({s.x:.1f}, {s.y:.1f}), "
                f"size {s.width:.1f}x{s.height:.1f}mm, "
                f"density={s.density}, priority={s.priority}"
            )
            if s.description:
                lines.append(f"     {s.description}")
        if self.notes:
            lines.append(f"  Notes: {self.notes}")
        return "\n".join(lines)


class FigurativeRegion(BaseModel):
    """A compositional region for figurative drawings."""

    name: str
    role: str = "subject"  # subject/support/detail/void/background
    x: float
    y: float
    width: float
    height: float
    line_mode: str = "contour"  # silhouette/contour/shading/texture/accent
    density: str = "medium"

    @field_validator("role")
    @classmethod
    def validate_role(cls, v):
        if v not in ("subject", "support", "detail", "void", "background"):
            raise ValueError(f"Invalid figurative region role: {v}")
        return v

    @field_validator("line_mode")
    @classmethod
    def validate_line_mode(cls, v):
        if v not in ("silhouette", "contour", "shading", "texture", "accent"):
            raise ValueError(f"Invalid figurative line mode: {v}")
        return v

    @field_validator("density")
    @classmethod
    def validate_density(cls, v):
        if v not in ("sparse", "medium", "dense"):
            raise ValueError(f"density must be sparse/medium/dense, got {v}")
        return v


class FigurativeCompositionPlan(BaseModel):
    """Region-aware plan for figurative prompts."""

    subjects: List[CompositionSubject]
    regions: List[FigurativeRegion]
    style: str = "artistic"
    estimated_commands: int = 120
    notes: Optional[str] = None

    @field_validator("subjects")
    @classmethod
    def validate_subjects_not_empty(cls, v):
        if not v:
            raise ValueError("FigurativeCompositionPlan must have at least one subject")
        return v

    @field_validator("regions")
    @classmethod
    def validate_regions_not_empty(cls, v):
        if not v:
            raise ValueError("FigurativeCompositionPlan must have at least one region")
        if not any(r.role == "void" for r in v):
            raise ValueError("FigurativeCompositionPlan must contain a void region")
        return v

    def to_prompt_guidance(self) -> str:
        lines = ["FIGURATIVE PLAN:"]
        for i, s in enumerate(self.subjects, 1):
            lines.append(
                f"  Subject {i}: {s.name} at ({s.x:.1f}, {s.y:.1f}) size {s.width:.1f}x{s.height:.1f} density={s.density}"
            )
        for i, r in enumerate(self.regions, 1):
            lines.append(
                f"  Region {i}: {r.name} role={r.role} line_mode={r.line_mode} "
                f"box=({r.x:.1f},{r.y:.1f},{r.width:.1f},{r.height:.1f}) density={r.density}"
            )
        if self.notes:
            lines.append(f"  Notes: {self.notes}")
        return "\n".join(lines)


class AbstractRegion(BaseModel):
    """A compositional region for abstract drawings."""

    name: str
    role: str  # focal/support/void/border/connector/texture_field
    x: float
    y: float
    width: float
    height: float
    field_family: str
    density: str = "medium"
    rhythm: str = "wave"
    layer: int = 1

    @field_validator("role")
    @classmethod
    def validate_role(cls, v):
        if v not in ("focal", "support", "void", "border", "connector", "texture_field"):
            raise ValueError(f"Invalid abstract region role: {v}")
        return v

    @field_validator("density")
    @classmethod
    def validate_density(cls, v):
        if v not in ("sparse", "medium", "dense", "saturated"):
            raise ValueError(f"Invalid abstract density: {v}")
        return v

    @field_validator("rhythm")
    @classmethod
    def validate_rhythm(cls, v):
        if v not in ("parallel", "diverging", "radial", "wave", "interference", "turbulent"):
            raise ValueError(f"Invalid abstract rhythm: {v}")
        return v


class AbstractCompositionPlan(BaseModel):
    """Region plan for abstract prompts."""

    regions: List[AbstractRegion]
    style: str = "artistic"
    estimated_commands: int = 160
    notes: Optional[str] = None

    @field_validator("regions")
    @classmethod
    def validate_regions(cls, v):
        if not v:
            raise ValueError("AbstractCompositionPlan must have at least one region")
        if not any(r.role == "focal" for r in v):
            raise ValueError("AbstractCompositionPlan must contain a focal region")
        if not any(r.role == "void" for r in v):
            raise ValueError("AbstractCompositionPlan must contain a void region")
        return v

    def to_prompt_guidance(self) -> str:
        lines = ["ABSTRACT PLAN:"]
        for i, r in enumerate(self.regions, 1):
            lines.append(
                f"  Region {i}: {r.name} role={r.role} family={r.field_family} rhythm={r.rhythm} "
                f"box=({r.x:.1f},{r.y:.1f},{r.width:.1f},{r.height:.1f}) density={r.density} layer={r.layer}"
            )
        if self.notes:
            lines.append(f"  Notes: {self.notes}")
        return "\n".join(lines)


class Region(BaseModel):
    """A rectangular work region for supervisor-worker orchestration."""

    bounds: Tuple[float, float, float, float]  # (x0, y0, x1, y1)
    role: str = "support"
    target_density: str = "medium"
    target_command_count: int = 1500
    name: Optional[str] = None

    @field_validator("bounds")
    @classmethod
    def validate_bounds(cls, v):
        if len(v) != 4:
            raise ValueError("bounds must be a 4-tuple (x0, y0, x1, y1)")
        x0, y0, x1, y1 = v
        if x1 <= x0 or y1 <= y0:
            raise ValueError(f"bounds must be ordered (x0<x1, y0<y1), got {v}")
        return tuple(float(c) for c in v)

    @field_validator("target_density")
    @classmethod
    def validate_density(cls, v):
        if v not in ("sparse", "medium", "dense", "saturated"):
            raise ValueError(f"target_density must be sparse/medium/dense/saturated, got {v}")
        return v

    @property
    def width(self) -> float:
        return self.bounds[2] - self.bounds[0]

    @property
    def height(self) -> float:
        return self.bounds[3] - self.bounds[1]

    @property
    def x(self) -> float:
        return self.bounds[0]

    @property
    def y(self) -> float:
        return self.bounds[1]


class ChunkMetrics(BaseModel):
    """Per-region scoring metrics from score_chunk()."""

    coverage: float = 0.0
    segment_count: int = 0
    angle_variance: float = 0.0
    primitive_ratio: float = 0.0
    command_count: int = 0


class WorkflowResult(BaseModel):
    """Standardized workflow execution result."""

    success: bool
    prompt: str
    commands_count: int
    gcode: str
    program: Optional[GCodeProgram] = None
    step_count: Optional[int] = None
    timestamp: str
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result = self.model_dump()
        if self.program:
            result["program"] = self.program.model_dump()
        return result
