"""
GCode quality scoring for PromptPlot v3.0

Measures canvas utilization, stroke efficiency, travel ratio, and assigns
a letter grade. Also extracts style profiles from existing GCode programs.
"""

import math
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict, Any

from .models import GCodeCommand, GCodeProgram, ChunkMetrics, Region
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
    composition_score: float = 0.0
    structure_score: float = 0.0
    texture_score: float = 0.0
    efficiency_score: float = 0.0
    central_clustering_penalty: float = 0.0
    repetition_penalty: float = 0.0
    failure_reasons: List[str] = field(default_factory=list)
    dominant_issue: str = "detail"
    creative_mode: str = "figurative"
    figurative_score: float = 0.0
    abstract_score: float = 0.0
    readability_score: float = 0.0
    focal_balance_score: float = 0.0

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
            "composition_score": round(self.composition_score, 3),
            "structure_score": round(self.structure_score, 3),
            "texture_score": round(self.texture_score, 3),
            "efficiency_score": round(self.efficiency_score, 3),
            "central_clustering_penalty": round(self.central_clustering_penalty, 3),
            "repetition_penalty": round(self.repetition_penalty, 3),
            "failure_reasons": list(self.failure_reasons),
            "dominant_issue": self.dominant_issue,
            "creative_mode": self.creative_mode,
            "figurative_score": round(self.figurative_score, 3),
            "abstract_score": round(self.abstract_score, 3),
            "readability_score": round(self.readability_score, 3),
            "focal_balance_score": round(self.focal_balance_score, 3),
        }


def score_gcode(program: GCodeProgram, paper: PaperConfig, creative_mode: str = "figurative") -> QualityReport:
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
    draw_segments: List[Tuple[float, float, float, float]] = []
    draw_angles: List[float] = []
    stroke_lengths: List[float] = []
    current_stroke_length = 0.0
    primitive_mix = program.metadata.get("primitive_mix", {}) if program.metadata else {}

    for cmd in program.commands:
        if cmd.command == "M3":
            pen_down = True
            stroke_count += 1
            current_stroke_length = 0.0
        elif cmd.command == "M5":
            if pen_down:
                pen_lift_count += 1
                if current_stroke_length > 0:
                    stroke_lengths.append(current_stroke_length)
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
                draw_segments.append((x, y, nx, ny))
                current_stroke_length += d
                if d > 0.01:
                    draw_angles.append(math.atan2(ny - y, nx - x))
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

    composition_score, central_penalty = _composition_score(
        draw_x_coords, draw_y_coords, paper, utilization,
    )
    structure_score = _structure_score(stroke_count, stroke_lengths, utilization)
    texture_score, repetition_penalty = _texture_score(draw_angles, primitive_mix)
    efficiency_score = _efficiency_score(ratio, longest_travel, travel_dist, draw_dist)
    readability_score = _readability_score(stroke_lengths, utilization, composition_score)
    focal_balance_score = _focal_balance_score(composition_score, texture_score, central_penalty)
    figurative_score = _figurative_score(structure_score, readability_score, composition_score, texture_score)
    abstract_score = _abstract_score(focal_balance_score, texture_score, composition_score, repetition_penalty)
    failure_reasons, dominant_issue = _failure_reasons(
        utilization, composition_score, structure_score, texture_score, efficiency_score,
        central_penalty, repetition_penalty, stroke_count, len(draw_segments), creative_mode,
    )

    # Grade
    grade = _compute_grade(
        utilization, ratio, stroke_count, len(program.commands),
        composition_score, structure_score, texture_score, efficiency_score,
        central_penalty, repetition_penalty, creative_mode, figurative_score, abstract_score,
    )

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
        composition_score=composition_score,
        structure_score=structure_score,
        texture_score=texture_score,
        efficiency_score=efficiency_score,
        central_clustering_penalty=central_penalty,
        repetition_penalty=repetition_penalty,
        failure_reasons=failure_reasons,
        dominant_issue=dominant_issue,
        creative_mode=creative_mode,
        figurative_score=figurative_score,
        abstract_score=abstract_score,
        readability_score=readability_score,
        focal_balance_score=focal_balance_score,
    )


def score_chunk(commands: List[GCodeCommand], region: Region) -> ChunkMetrics:
    """Lightweight per-region scoring."""
    x, y = 0.0, 0.0
    pen_down = False
    seg_count = 0
    primitive_like = 0
    angles: List[float] = []
    draw_xs: List[float] = []
    draw_ys: List[float] = []

    for cmd in commands:
        if cmd.command == "M3":
            pen_down = True
        elif cmd.command == "M5":
            pen_down = False
        elif cmd.command in ("G0", "G1"):
            nx = cmd.x if cmd.x is not None else x
            ny = cmd.y if cmd.y is not None else y
            if pen_down and cmd.command == "G1":
                d = math.sqrt((nx - x) ** 2 + (ny - y) ** 2)
                seg_count += 1
                draw_xs.append(nx)
                draw_ys.append(ny)
                if d > 0.01:
                    angles.append(math.atan2(ny - y, nx - x))
                if d < 12.0:
                    primitive_like += 1
            x, y = nx, ny

    x0, y0, x1, y1 = region.bounds
    rw = max(x1 - x0, 1.0)
    rh = max(y1 - y0, 1.0)
    if draw_xs and draw_ys:
        dw = max(draw_xs) - min(draw_xs)
        dh = max(draw_ys) - min(draw_ys)
        coverage = min((dw * dh) / (rw * rh), 1.0)
    else:
        coverage = 0.0

    if angles:
        sin_sum = sum(math.sin(a) for a in angles)
        cos_sum = sum(math.cos(a) for a in angles)
        angle_var = 1.0 - math.sqrt(sin_sum ** 2 + cos_sum ** 2) / len(angles)
    else:
        angle_var = 0.0

    primitive_ratio = (primitive_like / seg_count) if seg_count else 0.0

    return ChunkMetrics(
        coverage=coverage,
        segment_count=seg_count,
        angle_variance=angle_var,
        primitive_ratio=primitive_ratio,
        command_count=len(commands),
    )


def _compute_grade(
    utilization: float,
    ratio: float,
    strokes: int,
    commands: int,
    composition_score: float,
    structure_score: float,
    texture_score: float,
    efficiency_score: float,
    central_penalty: float,
    repetition_penalty: float,
    creative_mode: str,
    figurative_score: float,
    abstract_score: float,
) -> str:
    if commands < 3 or strokes == 0:
        return "F"
    score = 0.0
    # Utilization: 0-40 points
    score += min(utilization / 0.6, 1.0) * 25
    # Draw/travel ratio: 0-30 points (ratio of 3+ is excellent)
    score += min(ratio / 3.0, 1.0) * 15
    # Command richness: 0-30 points (30+ commands is good)
    score += min(commands / 30.0, 1.0) * 15
    score += composition_score * 20
    score += structure_score * 12
    score += texture_score * 7
    score += efficiency_score * 6
    if creative_mode == "abstract":
        score += abstract_score * 10
    elif creative_mode == "hybrid":
        score += (figurative_score + abstract_score) * 5
    else:
        score += figurative_score * 10
    score -= central_penalty * 8
    score -= repetition_penalty * 8

    if score >= 80:
        return "A"
    elif score >= 60:
        return "B"
    elif score >= 40:
        return "C"
    elif score >= 20:
        return "D"
    return "F"


def _composition_score(
    draw_x_coords: List[float],
    draw_y_coords: List[float],
    paper: PaperConfig,
    utilization: float,
) -> Tuple[float, float]:
    if not draw_x_coords or not draw_y_coords:
        return 0.0, 1.0
    x0, y0, x1, y1 = paper.get_drawable_area()
    cx = (x0 + x1) / 2
    cy = (y0 + y1) / 2
    w = max(x1 - x0, 1.0)
    h = max(y1 - y0, 1.0)
    center_radius_x = w * 0.2
    center_radius_y = h * 0.2
    center_hits = 0
    quadrants = set()
    for x, y in zip(draw_x_coords, draw_y_coords):
        if abs(x - cx) <= center_radius_x and abs(y - cy) <= center_radius_y:
            center_hits += 1
        quadrants.add((0 if x < cx else 1, 0 if y < cy else 1))
    center_share = center_hits / len(draw_x_coords)
    quadrant_score = len(quadrants) / 4.0
    composition = min(1.0, utilization * 0.5 + quadrant_score * 0.5)
    central_penalty = max(0.0, center_share - 0.35) / 0.65
    return composition, min(1.0, central_penalty)


def _structure_score(strokes: int, stroke_lengths: List[float], utilization: float) -> float:
    if strokes == 0:
        return 0.0
    avg_stroke = sum(stroke_lengths) / len(stroke_lengths) if stroke_lengths else 0.0
    stroke_factor = min(strokes / 8.0, 1.0)
    length_factor = min(avg_stroke / 25.0, 1.0)
    return min(1.0, stroke_factor * 0.5 + length_factor * 0.3 + min(utilization / 0.5, 1.0) * 0.2)


def _texture_score(draw_angles: List[float], primitive_mix: Dict[str, Any]) -> Tuple[float, float]:
    if not draw_angles:
        return 0.0, 1.0
    sin_sum = sum(math.sin(a) for a in draw_angles)
    cos_sum = sum(math.cos(a) for a in draw_angles)
    spread = 1.0 - math.sqrt(sin_sum ** 2 + cos_sum ** 2) / len(draw_angles)
    primitive_ratio = primitive_mix.get("primitive_ratio", 0.0)
    freeform_ratio = primitive_mix.get("freeform_ratio", 0.0)
    balance_bonus = 1.0 - abs(primitive_ratio - freeform_ratio)
    texture = min(1.0, spread * 0.75 + max(balance_bonus, 0.0) * 0.25)
    repetition_penalty = max(0.0, 0.35 - spread) / 0.35
    return texture, min(1.0, repetition_penalty)


def _efficiency_score(ratio: float, longest_travel: float, travel_dist: float, draw_dist: float) -> float:
    ratio_score = min(ratio / 3.0, 1.0) if ratio >= 0 else 0.0
    longest_penalty = 0.0 if draw_dist <= 0 else min(longest_travel / max(draw_dist, 1.0), 1.0)
    travel_penalty = 0.0 if (draw_dist + travel_dist) <= 0 else travel_dist / (draw_dist + travel_dist)
    return max(0.0, min(1.0, ratio_score * 0.6 + (1.0 - longest_penalty) * 0.2 + (1.0 - travel_penalty) * 0.2))


def _failure_reasons(
    utilization: float,
    composition_score: float,
    structure_score: float,
    texture_score: float,
    efficiency_score: float,
    central_penalty: float,
    repetition_penalty: float,
    strokes: int,
    draw_segments: int,
    creative_mode: str,
) -> Tuple[List[str], str]:
    reasons: List[str] = []
    if utilization < 0.2:
        reasons.append("underuses_canvas")
    if composition_score < 0.45:
        reasons.append("weak_composition")
    if central_penalty > 0.35:
        reasons.append("central_clustering")
    if structure_score < 0.4 or strokes < 3:
        reasons.append("weak_silhouette")
    if texture_score < 0.35 or repetition_penalty > 0.35:
        reasons.append("repetitive_texture")
    if efficiency_score < 0.35:
        reasons.append("wasteful_travel")
    if draw_segments < 10:
        reasons.append("insufficient_detail")
    if creative_mode in ("figurative", "hybrid") and structure_score < 0.5:
        reasons.append("low_readability")
    if creative_mode in ("abstract", "hybrid") and composition_score < 0.5:
        reasons.append("weak_focal_balance")

    severity = {
        "composition": composition_score - central_penalty,
        "structure": structure_score,
        "texture": texture_score - repetition_penalty,
        "efficiency": efficiency_score,
    }
    dominant = min(severity, key=severity.get)
    return reasons, dominant


def _readability_score(stroke_lengths: List[float], utilization: float, composition_score: float) -> float:
    if not stroke_lengths:
        return 0.0
    avg = sum(stroke_lengths) / len(stroke_lengths)
    return min(1.0, min(avg / 18.0, 1.0) * 0.5 + min(utilization / 0.45, 1.0) * 0.2 + composition_score * 0.3)


def _focal_balance_score(composition_score: float, texture_score: float, central_penalty: float) -> float:
    return max(0.0, min(1.0, composition_score * 0.5 + texture_score * 0.35 + (1.0 - central_penalty) * 0.15))


def _figurative_score(structure_score: float, readability_score: float, composition_score: float, texture_score: float) -> float:
    return min(1.0, structure_score * 0.35 + readability_score * 0.35 + composition_score * 0.2 + texture_score * 0.1)


def _abstract_score(focal_balance_score: float, texture_score: float, composition_score: float, repetition_penalty: float) -> float:
    return max(0.0, min(1.0, focal_balance_score * 0.4 + texture_score * 0.3 + composition_score * 0.2 + (1.0 - repetition_penalty) * 0.1))


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
