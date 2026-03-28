"""
GCode quality scoring for PromptPlot v3.0

Measures canvas utilization, stroke efficiency, travel ratio, and assigns
a letter grade. Also extracts style profiles from existing GCode programs.
"""

import math
from dataclasses import dataclass, field
from typing import Optional, List, Tuple

from .models import GCodeCommand, GCodeProgram
from .config import PaperConfig


def _distance(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


@dataclass
class QualityReport:
    """Quality metrics for a GCode program."""
    canvas_utilization: float = 0.0
    stroke_count: int = 0
    draw_travel_ratio: float = 0.0
    longest_travel: float = 0.0
    total_draw_distance: float = 0.0
    total_travel_distance: float = 0.0
    pen_lift_count: int = 0
    estimated_time_seconds: float = 0.0
    command_count: int = 0
    grade: str = "F"

    def to_dict(self) -> dict:
        return {
            "canvas_utilization": round(self.canvas_utilization, 3),
            "stroke_count": self.stroke_count,
            "draw_travel_ratio": round(self.draw_travel_ratio, 3),
            "longest_travel": round(self.longest_travel, 2),
            "total_draw_distance": round(self.total_draw_distance, 2),
            "total_travel_distance": round(self.total_travel_distance, 2),
            "pen_lift_count": self.pen_lift_count,
            "estimated_time_seconds": round(self.estimated_time_seconds, 2),
            "command_count": self.command_count,
            "grade": self.grade,
        }


def score_gcode(program: GCodeProgram, paper: PaperConfig) -> QualityReport:
    """Score a GCode program for quality metrics."""
    x, y = 0.0, 0.0
    pen_down = False
    draw_dist = 0.0
    travel_dist = 0.0
    longest_travel = 0.0
    pen_lift_count = 0
    stroke_count = 0
    feed_rate = 2000.0  # default F value for time estimate

    draw_x_coords: List[float] = []
    draw_y_coords: List[float] = []

    for cmd in program.commands:
        if cmd.command == "M3":
            pen_down = True
            stroke_count += 1
        elif cmd.command == "M5":
            if pen_down:
                pen_lift_count += 1
            pen_down = False
        elif cmd.command in ("G0", "G1"):
            nx = cmd.x if cmd.x is not None else x
            ny = cmd.y if cmd.y is not None else y
            d = _distance(x, y, nx, ny)

            if cmd.f is not None:
                feed_rate = float(cmd.f)

            if pen_down and cmd.command == "G1":
                draw_dist += d
                draw_x_coords.append(nx)
                draw_y_coords.append(ny)
            else:
                travel_dist += d
                if d > longest_travel:
                    longest_travel = d

            x, y = nx, ny

    # Canvas utilization
    x0, y0, x1, y1 = paper.get_drawable_area()
    drawable_area = (x1 - x0) * (y1 - y0)
    utilization = 0.0
    if draw_x_coords and draw_y_coords and drawable_area > 0:
        drawing_w = max(draw_x_coords) - min(draw_x_coords)
        drawing_h = max(draw_y_coords) - min(draw_y_coords)
        drawing_area = drawing_w * drawing_h
        utilization = min(drawing_area / drawable_area, 1.0)

    # Draw/travel ratio
    ratio = draw_dist / travel_dist if travel_dist > 0 else (float("inf") if draw_dist > 0 else 0.0)

    # Time estimate (mm/min to seconds)
    total_dist = draw_dist + travel_dist
    time_est = (total_dist / feed_rate) * 60 if feed_rate > 0 else 0.0

    # Grade
    grade = _compute_grade(utilization, ratio, stroke_count, len(program.commands))

    return QualityReport(
        canvas_utilization=utilization,
        stroke_count=stroke_count,
        draw_travel_ratio=ratio,
        longest_travel=longest_travel,
        total_draw_distance=draw_dist,
        total_travel_distance=travel_dist,
        pen_lift_count=pen_lift_count,
        estimated_time_seconds=time_est,
        command_count=len(program.commands),
        grade=grade,
    )


def _compute_grade(utilization: float, ratio: float, strokes: int, commands: int) -> str:
    if commands < 3 or strokes == 0:
        return "F"
    score = 0.0
    # Utilization: 0-40 points
    score += min(utilization / 0.6, 1.0) * 40
    # Draw/travel ratio: 0-30 points (ratio of 3+ is excellent)
    score += min(ratio / 3.0, 1.0) * 30
    # Command richness: 0-30 points (30+ commands is good)
    score += min(commands / 30.0, 1.0) * 30

    if score >= 80:
        return "A"
    elif score >= 60:
        return "B"
    elif score >= 40:
        return "C"
    elif score >= 20:
        return "D"
    return "F"


# ---------------------------------------------------------------------------
# Style profile extraction (Phase 3)
# ---------------------------------------------------------------------------

@dataclass
class StyleProfile:
    """Extracted style characteristics from a GCode program."""
    avg_stroke_length: float = 0.0
    stroke_density: float = 0.0
    canvas_utilization: float = 0.0
    direction_variance: float = 0.0
    avg_gap_between_strokes: float = 0.0

    def to_prompt_hints(self) -> str:
        """Convert to natural language prompt constraints."""
        hints = []
        if self.avg_stroke_length > 0:
            hints.append(f"Use strokes averaging {self.avg_stroke_length:.1f}mm in length.")
        if self.canvas_utilization > 0:
            pct = int(self.canvas_utilization * 100)
            hints.append(f"Fill approximately {pct}% of the canvas.")
        if self.direction_variance > 1.5:
            hints.append("Vary stroke direction widely for texture.")
        elif self.direction_variance < 0.5:
            hints.append("Keep strokes mostly parallel for clean lines.")
        if self.avg_gap_between_strokes > 0:
            hints.append(f"Space strokes approximately {self.avg_gap_between_strokes:.1f}mm apart.")
        return " ".join(hints)


def extract_style_profile(program: GCodeProgram, paper: Optional[PaperConfig] = None) -> StyleProfile:
    """Extract style characteristics from a GCode program."""
    x, y = 0.0, 0.0
    pen_down = False
    stroke_lengths: List[float] = []
    current_stroke_len = 0.0
    stroke_gaps: List[float] = []
    angles: List[float] = []
    draw_x: List[float] = []
    draw_y: List[float] = []

    for cmd in program.commands:
        if cmd.command == "M3":
            pen_down = True
            current_stroke_len = 0.0
        elif cmd.command == "M5":
            if pen_down and current_stroke_len > 0:
                stroke_lengths.append(current_stroke_len)
            pen_down = False
        elif cmd.command in ("G0", "G1"):
            nx = cmd.x if cmd.x is not None else x
            ny = cmd.y if cmd.y is not None else y
            d = _distance(x, y, nx, ny)

            if pen_down and cmd.command == "G1":
                current_stroke_len += d
                draw_x.append(nx)
                draw_y.append(ny)
                if d > 0.01:
                    angle = math.atan2(ny - y, nx - x)
                    angles.append(angle)
            elif cmd.command == "G0" and not pen_down and d > 0.01:
                stroke_gaps.append(d)

            x, y = nx, ny

    # Compute stats
    avg_stroke = sum(stroke_lengths) / len(stroke_lengths) if stroke_lengths else 0.0
    avg_gap = sum(stroke_gaps) / len(stroke_gaps) if stroke_gaps else 0.0

    # Direction variance (circular variance)
    dir_var = 0.0
    if angles:
        sin_sum = sum(math.sin(a) for a in angles)
        cos_sum = sum(math.cos(a) for a in angles)
        r = math.sqrt(sin_sum ** 2 + cos_sum ** 2) / len(angles)
        dir_var = 1.0 - r  # 0 = all same direction, 1 = uniform spread

    # Canvas utilization
    util = 0.0
    if draw_x and draw_y and paper:
        x0, y0, x1, y1 = paper.get_drawable_area()
        drawable_area = (x1 - x0) * (y1 - y0)
        if drawable_area > 0:
            dw = max(draw_x) - min(draw_x)
            dh = max(draw_y) - min(draw_y)
            util = min((dw * dh) / drawable_area, 1.0)

    # Stroke density (strokes per mm² of used area)
    density = 0.0
    if draw_x and draw_y:
        used_area = (max(draw_x) - min(draw_x)) * (max(draw_y) - min(draw_y))
        if used_area > 0:
            density = len(stroke_lengths) / used_area

    return StyleProfile(
        avg_stroke_length=avg_stroke,
        stroke_density=density,
        canvas_utilization=util,
        direction_variance=dir_var,
        avg_gap_between_strokes=avg_gap,
    )
