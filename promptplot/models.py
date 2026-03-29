"""
Shared Pydantic models for PromptPlot v3.0

Core data models used throughout the system: GCodeCommand, GCodeProgram, WorkflowResult.
Merged from PromptPlot core/models.py + drawStream config_handler.py GCodeCommand parsing.
"""

import re
import math
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum


class GCodeCommand(BaseModel):
    """Single G-code command with coordinates, feed rate, and optional comment."""

    command: str
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None
    f: Optional[int] = None
    s: Optional[int] = None
    p: Optional[int] = None
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
            "G0", "G1", "G2", "G3", "G4", "G17", "G18", "G19", "G20", "G21",
            "G28", "G90", "G91", "G92", "M2", "M3", "M5", "M17", "M18", "M30",
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
        if ";" in raw:
            parts = raw.split(";", 1)
            raw = parts[0].strip()
            comment = parts[1].strip()

        tokens = raw.split()
        if not tokens:
            return cls(command="G0", comment=comment)

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

        return cls(command=command_type, comment=comment, **params)

    def to_gcode(self) -> str:
        """Convert to G-code string format."""
        if self.command == "COMPLETE":
            return "COMPLETE"
        parts = [self.command]
        for attr, value in self.model_dump().items():
            if value is not None and attr not in (
                "command", "comment",
            ):
                if isinstance(value, float):
                    parts.append(f"{attr.upper()}{value:.3f}")
                else:
                    parts.append(f"{attr.upper()}{value}")
        result = " ".join(parts)
        if self.comment:
            result += f" ; {self.comment}"
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
# Composition Planning (Feature 5)
# ---------------------------------------------------------------------------

class CompositionSubject(BaseModel):
    """A single subject/element in a composition plan."""
    name: str
    description: str = ""
    x: float       # center X position
    y: float       # center Y position
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
                violations.append(f"Subject '{s.name}' X range [{x_min:.1f}, {x_max:.1f}] outside [0, {paper_w:.1f}]")
            if y_min < 0 or y_max > paper_h:
                violations.append(f"Subject '{s.name}' Y range [{y_min:.1f}, {y_max:.1f}] outside [0, {paper_h:.1f}]")
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
