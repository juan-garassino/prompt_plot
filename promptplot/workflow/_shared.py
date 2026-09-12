"""Shared workflow helpers, console/logger singletons, and diagnostics.

Split out of the former monolithic workflow.py during the v3.1 reorg.
"""

import json
import time
from pathlib import Path
from typing import Optional, Any

from pydantic import ValidationError as PydanticValidationError
from rich.console import Console

from ..models import GCodeCommand, GCodeProgram, DrawProgram
from ..config import PromptPlotConfig
from ..llm import LLMProvider
from ..scoring import score_gcode, QualityReport
from ..logger import WorkflowLogger

console = Console()
logger = WorkflowLogger(console)
_GRADE_ORDER = {"A": 5, "B": 4, "C": 3, "D": 2, "F": 1}


# ===== sliced body (helpers _clean_llm_output.._select_candidate_report, diagnose_failure) =====
def _clean_llm_output(output: str) -> str:
    output = output.strip()
    if "```json" in output:
        start = output.find("```json") + 7
        end = output.rfind("```")
        output = output[start:end].strip()
    elif "```" in output:
        start = output.find("```") + 3
        end = output.rfind("```")
        output = output[start:end].strip()
    return output


def _extract_json(output: str) -> str:
    start = output.find("{")
    end = output.rfind("}") + 1
    if start < 0 or end <= start:
        raise ValueError("No valid JSON object found in output")
    return output[start:end]


def _has_structured_commands(data: dict) -> bool:
    """Check if a commands list contains structured commands."""
    if "commands" not in data:
        return False
    return any(
        isinstance(c, dict) and c.get("command") in {"PRIMITIVE", "FREEFORM"}
        for c in data["commands"]
    )


def _validate_output(output: str):
    """Returns GCodeProgram, DrawProgram, or GCodeCommand on success, Exception on failure."""
    cleaned = _clean_llm_output(output)
    json_str = _extract_json(cleaned)
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        return ValueError(f"Invalid JSON: {e}")

    if "commands" in data:
        # If any command is structured, parse as DrawProgram
        if _has_structured_commands(data):
            try:
                return DrawProgram(**data)
            except PydanticValidationError as e:
                return ValueError(f"DrawProgram validation failed: {e}")
        try:
            return GCodeProgram(**data)
        except PydanticValidationError as e:
            return ValueError(f"Program validation failed: {e}")
    else:
        try:
            return GCodeCommand(**data)
        except PydanticValidationError as e:
            return ValueError(f"Command validation failed: {e}")


def _check_bounds(program: GCodeProgram, config: PromptPlotConfig) -> Optional[str]:
    """Check if any commands exceed paper bounds. Returns error message or None."""
    if not config.bounds.enforce:
        return None
    x0, y0, x1, y1 = config.paper.get_drawable_area()
    violations = []
    for i, cmd in enumerate(program.commands):
        if cmd.x is not None and (cmd.x < 0 or cmd.x > config.paper.x_extent):
            violations.append(f"Command {i}: X={cmd.x} outside [0, {config.paper.x_extent}]")
        if cmd.y is not None and (cmd.y < 0 or cmd.y > config.paper.y_extent):
            violations.append(f"Command {i}: Y={cmd.y} outside [0, {config.paper.y_extent}]")
    if violations:
        return (
            f"Out-of-bounds coordinates detected. Valid X: [0, {config.paper.x_extent}], "
            f"Valid Y: [0, {config.paper.y_extent}]. Drawable area: X[{x0}-{x1}], Y[{y0}-{y1}]. "
            f"Violations: {'; '.join(violations[:5])}"
        )
    return None


def _supports_multimodal(llm: Any) -> bool:
    """True for real provider implementations, false for loose test doubles."""
    return isinstance(llm, LLMProvider)


def _analysis_output_dir(config: PromptPlotConfig, prompt: str, iteration: int) -> Path:
    import re

    slug = re.sub(r"[^a-z0-9]+", "_", prompt.lower())[:30].strip("_") or "drawing"
    base = (
        Path(config.workflow.output_directory)
        / "analysis"
        / f"{slug}_{int(time.time())}"
        / f"iter_{iteration}"
    )
    base.mkdir(parents=True, exist_ok=True)
    return base


def _select_candidate_report(report: QualityReport, creative_mode: str) -> tuple:
    if creative_mode == "abstract":
        return (
            _GRADE_ORDER.get(report.grade, 0),
            report.abstract_score,
            report.focal_balance_score,
            report.texture_score,
            -report.repetition_penalty,
        )
    if creative_mode == "hybrid":
        return (
            _GRADE_ORDER.get(report.grade, 0),
            (report.abstract_score + report.figurative_score) / 2,
            report.readability_score,
            report.focal_balance_score,
            -report.repetition_penalty,
        )
    return (
        _GRADE_ORDER.get(report.grade, 0),
        report.figurative_score,
        report.readability_score,
        report.structure_score,
        -report.repetition_penalty,
    )


def diagnose_failure(
    program: Optional[GCodeProgram], config: PromptPlotConfig, error: Optional[str] = None
) -> str:
    """Generate a targeted diagnosis message for failed GCode generation."""
    hints = []

    if error:
        hints.append(f"Previous error: {error}")

    if program is not None:
        n = len(program.commands)
        if n < 100:
            hints.append(
                f"Generate at least 200 GCode commands for detailed scenes. Your previous attempt had only {n}. Use many short G1 segments (3-8mm each) to create smooth, detailed shapes."
            )

        drawing = [c for c in program.commands if c.command == "G1"]
        if not drawing:
            hints.append("Your output must contain G1 drawing commands, not just travel moves.")

        # Check bounds
        x0, y0, x1, y1 = config.paper.get_drawable_area()
        oob = []
        for cmd in program.commands:
            if cmd.x is not None and (cmd.x < 0 or cmd.x > config.paper.x_extent):
                oob.append(f"X={cmd.x:.1f}")
            if cmd.y is not None and (cmd.y < 0 or cmd.y > config.paper.y_extent):
                oob.append(f"Y={cmd.y:.1f}")
        if oob:
            hints.append(
                f"Keep all coordinates within X:{x0:.1f}-{x1:.1f}, Y:{y0:.1f}-{y1:.1f}. "
                f"Out-of-range values: {', '.join(oob[:5])}"
            )

        # Check pen lifts
        has_m5 = any(c.command == "M5" for c in program.commands)
        has_m3 = any(c.command == "M3" for c in program.commands)
        if not has_m5 or not has_m3:
            s_val = config.pen.pen_down_s_value
            hints.append(
                f"Add M5 (pen up) before G0 travel moves and M3 S{s_val} "
                f"(pen down) before G1 draw moves."
            )

        # Check utilization
        try:
            report = score_gcode(program, config.paper)
            if report.canvas_utilization < 0.2:
                pct = int(report.canvas_utilization * 100)
                hints.append(
                    f"Use more of the canvas. Your drawing only covers {pct}% — aim for 60-80%."
                )
        except Exception:
            pass

    if not hints:
        hints.append("Review the error and try again with valid GCode.")

    return "\n".join(f"- {h}" for h in hints)
