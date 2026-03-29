"""
Post-processing pipeline for PromptPlot v3.0

Merged from:
- PromptPlot utils/gcode_optimizer.py: stroke extraction, reordering, pen safety
- drawStream gcode_architect.py: G4 dwell injection after pen commands
- drawStream gcode_crafter.py: brush reload sequences every N strokes

Pipeline order (critical — dwells MUST be last):
  1. ensure_pen_safety()      — fix pen state violations
  2. optimize_gcode_program() — reorder strokes to minimize travel
  3. insert_paint_dips()      — ink reload sequences (brush mode)
  4. insert_pen_dwells()      — G4 after every M3/M5
"""

import math
import logging
from typing import List, Tuple, Union

from .models import GCodeCommand, GCodeProgram
from .config import PenConfig, BrushConfig, PaperConfig, PromptPlotConfig
from .engine import PenState

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 0. Bounds Validation
# ---------------------------------------------------------------------------

def validate_bounds(
    program: GCodeProgram,
    paper: PaperConfig,
    mode: str = "clamp",
) -> Tuple[GCodeProgram, List[str]]:
    """Validate and optionally fix out-of-bounds coordinates.

    Args:
        program: The GCode program to validate.
        paper: Paper configuration with dimensions and margins.
        mode: "clamp" (fix coordinates), "reject" (remove commands), or "warn" (keep, log).

    Returns:
        Tuple of (possibly modified program, list of violation messages).
    """
    x0, y0, x1, y1 = paper.get_drawable_area()
    violations: List[str] = []
    new_commands: List[GCodeCommand] = []

    for i, cmd in enumerate(program.commands):
        out_of_bounds = False
        clamped_x = cmd.x
        clamped_y = cmd.y

        if cmd.x is not None:
            if cmd.x < 0 or cmd.x > paper.width:
                out_of_bounds = True
                violations.append(
                    f"Cmd {i} ({cmd.command}): X={cmd.x:.1f} outside [0, {paper.width:.1f}]"
                )
                clamped_x = max(0, min(cmd.x, paper.width))

        if cmd.y is not None:
            if cmd.y < 0 or cmd.y > paper.height:
                out_of_bounds = True
                violations.append(
                    f"Cmd {i} ({cmd.command}): Y={cmd.y:.1f} outside [0, {paper.height:.1f}]"
                )
                clamped_y = max(0, min(cmd.y, paper.height))

        if out_of_bounds:
            if mode == "clamp":
                new_commands.append(cmd.model_copy(update={"x": clamped_x, "y": clamped_y}))
            elif mode == "reject":
                _log.warning("Rejecting command %d: %s (out of bounds)", i, cmd.to_gcode())
                continue
            else:  # warn
                new_commands.append(cmd)
        else:
            new_commands.append(cmd)

    # Ensure we don't end up with empty program after rejection
    if not new_commands:
        new_commands = [GCodeCommand(command="M5"), GCodeCommand(command="G0", x=0, y=0)]

    metadata = {**(program.metadata or {})}
    if violations:
        metadata["bounds_violations"] = len(violations)
        metadata["bounds_mode"] = mode

    return GCodeProgram(commands=new_commands, metadata=metadata), violations


def validate_single_command(
    cmd: GCodeCommand,
    paper: PaperConfig,
    pen_is_down: Union[bool, "PenState"],
) -> tuple[GCodeCommand, list[str], list[GCodeCommand]]:
    """Validate and fix a single command for live streaming.

    Returns:
        (fixed_cmd, warnings, prefix_commands)
        prefix_commands: any pen safety commands to insert BEFORE this command
            (e.g., M5 before a G0 travel, M3 before a G1 draw)
    """
    # Normalize PenState to bool for internal logic
    if isinstance(pen_is_down, PenState):
        pen_is_down = pen_is_down.is_down

    warnings: list[str] = []
    prefix: list[GCodeCommand] = []

    # Clamp coordinates to paper bounds
    x0, y0, x1, y1 = paper.get_drawable_area()
    fixed_x = cmd.x
    fixed_y = cmd.y
    if cmd.x is not None and (cmd.x < 0 or cmd.x > paper.width):
        fixed_x = max(0, min(cmd.x, paper.width))
        warnings.append(f"X={cmd.x:.1f} clamped to {fixed_x:.1f}")
    if cmd.y is not None and (cmd.y < 0 or cmd.y > paper.height):
        fixed_y = max(0, min(cmd.y, paper.height))
        warnings.append(f"Y={cmd.y:.1f} clamped to {fixed_y:.1f}")

    if fixed_x != cmd.x or fixed_y != cmd.y:
        cmd = cmd.model_copy(update={"x": fixed_x, "y": fixed_y})

    # Pen safety: ensure pen is up before travel, down before draw
    if cmd.command == "G0" and pen_is_down:
        prefix.append(GCodeCommand(command="M5"))
        warnings.append("Inserted M5 before travel move")
    elif cmd.command == "G1" and not pen_is_down:
        s_val = 1000  # default; caller can override
        prefix.append(GCodeCommand(command="M3", s=s_val))
        warnings.append("Inserted M3 before draw move")

    return cmd, warnings, prefix


# ---------------------------------------------------------------------------
# 0.5 Arc Approximation (G2/G3 → G1 segments)
# ---------------------------------------------------------------------------

def approximate_arcs(program: GCodeProgram, segments_per_arc: int = 12) -> GCodeProgram:
    """Convert G2/G3 arc commands to short G1 line segments.

    If the LLM generates arc commands despite instructions, this converts
    them to linear approximations that all plotters can execute.
    """
    has_arcs = any(cmd.command in ("G2", "G3") for cmd in program.commands)
    if not has_arcs:
        return program

    new_commands: List[GCodeCommand] = []
    cx, cy = 0.0, 0.0  # current position

    for cmd in program.commands:
        if cmd.command not in ("G2", "G3"):
            # Track position
            if cmd.command in ("G0", "G1") and cmd.x is not None:
                cx = cmd.x
            if cmd.command in ("G0", "G1") and cmd.y is not None:
                cy = cmd.y
            new_commands.append(cmd)
            continue

        # Arc approximation
        ex = cmd.x if cmd.x is not None else cx
        ey = cmd.y if cmd.y is not None else cy
        feed = cmd.f or 2000

        # Simple linear interpolation for arc (chord approximation)
        # Without I/J center offsets we just interpolate from current to end
        for i in range(1, segments_per_arc + 1):
            t = i / segments_per_arc
            ix = cx + (ex - cx) * t
            iy = cy + (ey - cy) * t
            new_commands.append(GCodeCommand(
                command="G1", x=round(ix, 3), y=round(iy, 3), f=feed
            ))

        cx, cy = ex, ey

    return GCodeProgram(
        commands=new_commands,
        metadata={**(program.metadata or {}), "arcs_approximated": True},
    )


# ---------------------------------------------------------------------------
# 1. Pen Safety
# ---------------------------------------------------------------------------

def ensure_pen_safety(commands: List[GCodeCommand],
                      pen_config: PenConfig = None) -> List[GCodeCommand]:
    """Enforce pen safety invariants on LLM-generated GCode.

    Uses pen_config.pen_down_s_value (default 1000) instead of hardcoded S100.
    """
    s_value = pen_config.pen_down_s_value if pen_config else 1000
    result: List[GCodeCommand] = []
    pen_state = PenState()

    if not commands or commands[0].command != "M5":
        result.append(GCodeCommand(command="M5"))

    for cmd in commands:
        if cmd.command == "M3":
            pen_state.set_down()
            result.append(cmd)
        elif cmd.command == "M5":
            pen_state.set_up()
            result.append(cmd)
        elif cmd.command == "G0":
            if pen_state.is_down:
                result.append(GCodeCommand(command="M5"))
                pen_state.set_up()
            result.append(cmd)
        elif cmd.command == "G1":
            if pen_state.is_up:
                result.append(GCodeCommand(command="M3", s=s_value))
                pen_state.set_down()
            result.append(cmd)
        else:
            result.append(cmd)

    if pen_state.is_down:
        result.append(GCodeCommand(command="M5"))

    last_g0 = None
    for cmd in reversed(result):
        if cmd.command == "G0":
            last_g0 = cmd
            break
    if last_g0 is None or (last_g0.x != 0.0 or last_g0.y != 0.0):
        result.append(GCodeCommand(command="G0", x=0.0, y=0.0))

    return result


# ---------------------------------------------------------------------------
# 2. Stroke Optimization (nearest-neighbor reorder)
# ---------------------------------------------------------------------------

def extract_strokes(commands: List[GCodeCommand]) -> List[List[GCodeCommand]]:
    """Extract individual strokes (M3 ... G1s ... M5) from a command list."""
    strokes: List[List[GCodeCommand]] = []
    current: List[GCodeCommand] = []
    pen_state = PenState()

    for cmd in commands:
        if cmd.command == "M3":
            pen_state.set_down()
            current = [cmd]
        elif cmd.command == "M5":
            if current:
                current.append(cmd)
                strokes.append(current)
                current = []
            pen_state.set_up()
        elif pen_state.is_down and cmd.command == "G1":
            current.append(cmd)

    if current:
        current.append(GCodeCommand(command="M5"))
        strokes.append(current)

    return strokes


def _stroke_start(stroke: List[GCodeCommand]) -> Tuple[float, float]:
    for cmd in stroke:
        if cmd.command == "G1" and cmd.x is not None and cmd.y is not None:
            return (cmd.x, cmd.y)
    return (0.0, 0.0)


def _stroke_end(stroke: List[GCodeCommand]) -> Tuple[float, float]:
    for cmd in reversed(stroke):
        if cmd.command == "G1" and cmd.x is not None and cmd.y is not None:
            return (cmd.x, cmd.y)
    return (0.0, 0.0)


def _distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)


def optimize_stroke_order(
    strokes: List[List[GCodeCommand]],
) -> List[List[GCodeCommand]]:
    """Reorder strokes using nearest-neighbor heuristic."""
    if len(strokes) <= 1:
        return strokes
    remaining = list(range(len(strokes)))
    ordered: List[List[GCodeCommand]] = []
    pos = (0.0, 0.0)
    while remaining:
        best_idx = min(remaining, key=lambda i: _distance(pos, _stroke_start(strokes[i])))
        remaining.remove(best_idx)
        ordered.append(strokes[best_idx])
        pos = _stroke_end(strokes[best_idx])
    return ordered


def rebuild_program(strokes: List[List[GCodeCommand]]) -> List[GCodeCommand]:
    """Rebuild a full command list from ordered strokes with G0 repositioning."""
    commands: List[GCodeCommand] = [GCodeCommand(command="M5")]
    pos = (0.0, 0.0)
    for stroke in strokes:
        start = _stroke_start(stroke)
        if _distance(pos, start) > 0.01:
            commands.append(GCodeCommand(command="G0", x=start[0], y=start[1]))
        commands.extend(stroke)
        pos = _stroke_end(stroke)
    if not commands or commands[-1].command != "M5":
        commands.append(GCodeCommand(command="M5"))
    commands.append(GCodeCommand(command="G0", x=0.0, y=0.0))
    return commands


def optimize_gcode_program(program: GCodeProgram) -> GCodeProgram:
    """Optimize stroke order to minimize travel distance."""
    strokes = extract_strokes(program.commands)
    if len(strokes) <= 1:
        return program
    ordered = optimize_stroke_order(strokes)
    optimized = rebuild_program(ordered)
    return GCodeProgram(
        commands=optimized,
        metadata={
            **(program.metadata or {}),
            "optimized": True,
            "original_stroke_count": len(strokes),
            "optimization_method": "nearest_neighbor",
        },
    )


# ---------------------------------------------------------------------------
# 3. Brush / Paint Dip Insertion
# ---------------------------------------------------------------------------

def insert_paint_dips(
    program: GCodeProgram, brush_config: BrushConfig
) -> GCodeProgram:
    """Insert ink reload sequences every N strokes.

    Sequence: M5 -> G0 to station -> G0 Z(dip_height) -> G4 hold -> G0 Z5 -> G4 drip -> resume
    """
    if not brush_config.enabled or brush_config.strokes_before_reload <= 0:
        return program

    commands: List[GCodeCommand] = []
    stroke_count = 0
    cx, cy = brush_config.charge_position
    dip_ms = int(brush_config.dip_duration * 1000)
    drip_ms = int(brush_config.drip_duration * 1000)

    for cmd in program.commands:
        if cmd.command == "M3":
            stroke_count += 1
            if stroke_count % brush_config.strokes_before_reload == 0:
                # Insert reload before this pen-down
                commands.append(GCodeCommand(command="M5"))
                commands.append(GCodeCommand(command="G0", x=cx, y=cy))
                commands.append(GCodeCommand(
                    command="G0", z=brush_config.dip_height,
                    comment="dip into ink",
                ))
                commands.append(GCodeCommand(command="G4", p=dip_ms, comment="hold in ink"))
                commands.append(GCodeCommand(command="G0", z=5.0, comment="lift"))
                commands.append(GCodeCommand(command="G4", p=drip_ms, comment="drip"))
        commands.append(cmd)

    return GCodeProgram(
        commands=commands,
        metadata={**(program.metadata or {}), "brush_reloads": stroke_count // brush_config.strokes_before_reload},
    )


# ---------------------------------------------------------------------------
# 4. Pen Dwell Injection (G4 after M3/M5)
# ---------------------------------------------------------------------------

def insert_pen_dwells(
    program: GCodeProgram, pen_config: PenConfig
) -> GCodeProgram:
    """Insert G4 dwell commands after every M3 and M5.

    Skips insertion when the corresponding delay is 0.
    """
    down_ms = int(pen_config.pen_down_delay * 1000)
    up_ms = int(pen_config.pen_up_delay * 1000)

    if down_ms == 0 and up_ms == 0:
        return program

    commands: List[GCodeCommand] = []
    for cmd in program.commands:
        commands.append(cmd)
        if cmd.command == "M3" and down_ms > 0:
            commands.append(GCodeCommand(command="G4", p=down_ms, comment="pen down dwell"))
        elif cmd.command == "M5" and up_ms > 0:
            commands.append(GCodeCommand(command="G4", p=up_ms, comment="pen up dwell"))

    return GCodeProgram(
        commands=commands,
        metadata={**(program.metadata or {}), "dwells_inserted": True},
    )


# ---------------------------------------------------------------------------
# Full Pipeline
# ---------------------------------------------------------------------------

def run_pipeline(program: GCodeProgram, config: PromptPlotConfig) -> GCodeProgram:
    """Run the full post-processing pipeline in the correct order.

    Order:
    0. Bounds validation (clamp/reject/warn out-of-bounds coordinates)
    1. Pen safety (fix state violations, use configurable S-value)
    2. Stroke optimization (nearest-neighbor reorder)
    3. Paint dips (brush mode only)
    4. Pen dwells (G4 after M3/M5 — MUST be last)
    """
    # 0. Arc approximation (convert G2/G3 to G1 segments)
    program = approximate_arcs(program)

    # 0.5 Bounds validation
    if config.bounds.enforce:
        program, violations = validate_bounds(program, config.paper, config.bounds.mode)
        if violations:
            _log.info("Bounds validation (%s mode): %d violations", config.bounds.mode, len(violations))

    # 1. Pen safety
    safe_commands = ensure_pen_safety(program.commands, config.pen)
    program = GCodeProgram(commands=safe_commands, metadata=program.metadata)

    # 2. Optimize stroke order
    program = optimize_gcode_program(program)

    # 3. Brush reload sequences
    if config.brush.enabled:
        program = insert_paint_dips(program, config.brush)

    # 4. Pen dwells (last!)
    program = insert_pen_dwells(program, config.pen)

    return program
