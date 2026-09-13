"""
Drawing primitives for PromptPlot v3.0

High-level shape commands (circle, hatch, spiral, etc.) that expand into
precise GCode sequences. LLMs output primitives for geometric shapes;
deterministic code here expands them into exact G1 segments.
"""

import inspect
import json
import math
from typing import List, Dict, Any, Callable, Tuple, Optional, get_type_hints

from .models import (
    GCodeCommand,
    GCodeProgram,
    PrimitiveCommand,
    FreeformCommand,
    DrawProgram,
)
from .config import PenConfig


# ---------------------------------------------------------------------------
# Geometry helpers (private)
# ---------------------------------------------------------------------------

def _rotate_point(x: float, y: float, cx: float, cy: float, angle_deg: float) -> Tuple[float, float]:
    """Rotate (x, y) around (cx, cy) by angle_deg degrees."""
    rad = math.radians(angle_deg)
    cos_a, sin_a = math.cos(rad), math.sin(rad)
    dx, dy = x - cx, y - cy
    return cx + dx * cos_a - dy * sin_a, cy + dx * sin_a + dy * cos_a


def _clip_line_to_rect(
    x0: float, y0: float, x1: float, y1: float,
    rx: float, ry: float, rw: float, rh: float,
) -> Optional[Tuple[float, float, float, float]]:
    """Cohen-Sutherland line clipping to axis-aligned rect [rx, rx+rw] x [ry, ry+rh].
    Returns clipped (x0, y0, x1, y1) or None if fully outside."""
    INSIDE, LEFT, RIGHT, BOTTOM, TOP = 0, 1, 2, 4, 8
    xmin, xmax = rx, rx + rw
    ymin, ymax = ry, ry + rh

    def _code(x: float, y: float) -> int:
        c = INSIDE
        if x < xmin: c |= LEFT
        elif x > xmax: c |= RIGHT
        if y < ymin: c |= BOTTOM
        elif y > ymax: c |= TOP
        return c

    c0, c1 = _code(x0, y0), _code(x1, y1)
    for _ in range(20):
        if not (c0 | c1):
            return (x0, y0, x1, y1)
        if c0 & c1:
            return None
        c_out = c0 or c1
        dx, dy = x1 - x0, y1 - y0
        if c_out & TOP:
            x = x0 + dx * (ymax - y0) / dy if dy else x0
            y = ymax
        elif c_out & BOTTOM:
            x = x0 + dx * (ymin - y0) / dy if dy else x0
            y = ymin
        elif c_out & RIGHT:
            y = y0 + dy * (xmax - x0) / dx if dx else y0
            x = xmax
        elif c_out & LEFT:
            y = y0 + dy * (xmin - x0) / dx if dx else y0
            x = xmin
        else:
            break
        if c_out == c0:
            x0, y0 = x, y
            c0 = _code(x0, y0)
        else:
            x1, y1 = x, y
            c1 = _code(x1, y1)
    return None


def _scanline_intersections(y: float, edges: List[Tuple[Tuple[float, float], Tuple[float, float]]]) -> List[float]:
    """Find x-intersections of a horizontal scanline at y with polygon edges."""
    xs = []
    for (x0, y0), (x1, y1) in edges:
        if y0 == y1:
            continue
        if min(y0, y1) <= y < max(y0, y1):
            t = (y - y0) / (y1 - y0)
            xs.append(x0 + t * (x1 - x0))
    xs.sort()
    return xs


def _make_stroke(points: List[Tuple[float, float]], feed: int, s_value: int) -> List[GCodeCommand]:
    """Create a complete stroke: M5 → G0 to start → M3 → G1 segments → M5."""
    if not points:
        return []
    cmds = [
        GCodeCommand(command="M5"),
        GCodeCommand(command="G0", x=round(points[0][0], 3), y=round(points[0][1], 3)),
        GCodeCommand(command="M3", s=s_value),
    ]
    for x, y in points[1:]:
        cmds.append(GCodeCommand(command="G1", x=round(x, 3), y=round(y, 3), f=feed))
    cmds.append(GCodeCommand(command="M5"))
    return cmds


def _make_marks(
    centers: List[Tuple[float, float]],
    length: float,
    angle_deg: float,
    feed: int,
    s_value: int,
    jitter: float = 0.0,
) -> List[GCodeCommand]:
    """Expand a list of mark centers into short directional strokes."""
    cmds: List[GCodeCommand] = []
    half = length / 2
    for idx, (cx, cy) in enumerate(centers):
        angle = math.radians(angle_deg + math.sin(idx * 1.618) * jitter)
        dx = half * math.cos(angle)
        dy = half * math.sin(angle)
        cmds.extend(_make_stroke([(cx - dx, cy - dy), (cx + dx, cy + dy)], feed, s_value))
    return cmds


# ---------------------------------------------------------------------------
# Primitive expanders
# ---------------------------------------------------------------------------

def expand_circle(
    cx: float, cy: float, radius: float,
    segments: int = 24, feed: int = 2000, s_value: int = 1000,
) -> List[GCodeCommand]:
    """Draw a circle — use for geometric compositions, radial patterns, circular grids, concentric ring fields, and as a building block for rosettes and mandalas. Nest many circles at varying radii for concentric patterns. Tile circles in grids for generative dot-matrix effects.

    Args:
        cx: Center X coordinate
        cy: Center Y coordinate
        radius: Circle radius in mm
        segments: Number of line segments (more = smoother, use 36+ for large circles)
    """
    points = []
    for i in range(segments + 1):
        angle = 2 * math.pi * i / segments
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return _make_stroke(points, feed, s_value)


def expand_ellipse(
    cx: float, cy: float, rx: float, ry: float,
    segments: int = 24, feed: int = 2000, s_value: int = 1000,
) -> List[GCodeCommand]:
    """Draw an ellipse — use for oval motifs, perspective distortion effects, and stretched circular grids. Vary rx and ry across a grid to create fields of ellipses that warp and flow across the canvas.

    Args:
        cx: Center X coordinate
        cy: Center Y coordinate
        rx: Horizontal radius in mm
        ry: Vertical radius in mm
        segments: Number of line segments (more = smoother, use 36+ for large ellipses)
    """
    points = []
    for i in range(segments + 1):
        angle = 2 * math.pi * i / segments
        points.append((cx + rx * math.cos(angle), cy + ry * math.sin(angle)))
    return _make_stroke(points, feed, s_value)


def expand_polygon(
    points: List[List[float]],
    feed: int = 2000, s_value: int = 1000,
) -> List[GCodeCommand]:
    """Draw a closed polygon outline — use for triangles, hexagons, diamonds, and any geometric tile shape. Repeat polygons in grids or radial arrays for tessellations. Combine with hatch or crosshatch inside each polygon for filled pattern fields.

    Args:
        points: List of [x, y] vertex coordinates (minimum 3)
    """
    if len(points) < 3:
        return []
    pts = [(p[0], p[1]) for p in points]
    # Close the polygon
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    return _make_stroke(pts, feed, s_value)


def expand_hatch(
    x: float, y: float, width: float, height: float,
    angle: float = 0, spacing: float = 3,
    feed: int = 2000, s_value: int = 1000,
) -> List[GCodeCommand]:
    """Fill a rectangle with parallel hatching lines — THE KEY PRIMITIVE for generative plotter art. Tile many small hatch rectangles across the canvas and VARY THE ANGLE per cell to create wave patterns, moiré interference, flow fields, and op-art effects. This is how pen plotters create the richest visual complexity. Also use for shading: tight spacing (2mm) = dark, wide spacing (8mm) = light.

    Args:
        x: Left edge X coordinate
        y: Bottom edge Y coordinate
        width: Rectangle width in mm
        height: Rectangle height in mm
        angle: Line angle in degrees — VARY THIS across a grid for pattern effects (0=horizontal, 45=diagonal, 90=vertical, any value works)
        spacing: Distance between lines in mm (2-3 = dense/dark, 5-8 = light/airy)
    """
    cmds: List[GCodeCommand] = []
    cx, cy = x + width / 2, y + height / 2
    # Diagonal of the rect — ensures full coverage when rotated
    diag = math.sqrt(width ** 2 + height ** 2)
    half = diag / 2

    n_lines = int(diag / spacing) + 1
    start_offset = -half

    for i in range(n_lines):
        offset = start_offset + i * spacing
        # Horizontal line at offset, then rotate
        lx0, ly0 = cx - half, cy + offset
        lx1, ly1 = cx + half, cy + offset
        # Rotate around rect center
        lx0, ly0 = _rotate_point(lx0, ly0, cx, cy, angle)
        lx1, ly1 = _rotate_point(lx1, ly1, cx, cy, angle)
        # Clip to rect
        clipped = _clip_line_to_rect(lx0, ly0, lx1, ly1, x, y, width, height)
        if clipped:
            cx0, cy0, cx1, cy1 = clipped
            cmds.extend(_make_stroke([(cx0, cy0), (cx1, cy1)], feed, s_value))

    return cmds


def expand_crosshatch(
    x: float, y: float, width: float, height: float,
    spacing: float = 3,
    feed: int = 2000, s_value: int = 1000,
) -> List[GCodeCommand]:
    """Fill a rectangle with crosshatching (+45 and -45 degree lines) — creates the densest, darkest tonal value. Use for emphasis cells in pattern grids, solid-fill regions in geometric compositions, and anywhere maximum visual weight is needed. In a hatch-grid composition, crosshatch cells stand out against single-hatch neighbors.

    Args:
        x: Left edge X coordinate
        y: Bottom edge Y coordinate
        width: Rectangle width in mm
        height: Rectangle height in mm
        spacing: Distance between lines in mm (2-3 = very dense, 5-8 = medium density)
    """
    cmds = expand_hatch(x, y, width, height, angle=45, spacing=spacing, feed=feed, s_value=s_value)
    cmds.extend(expand_hatch(x, y, width, height, angle=-45, spacing=spacing, feed=feed, s_value=s_value))
    return cmds


def expand_filled_polygon(
    points: List[List[float]],
    spacing: float = 3, angle: float = 0,
    feed: int = 2000, s_value: int = 1000,
) -> List[GCodeCommand]:
    """Draw a hatched polygon — outline plus scan-line fill. Use for filled geometric tiles in tessellations, shaped fill regions, and irregular hatched zones. Vary spacing and angle per polygon in a grid for complex generative patterns. Multiple filled polygons with different angles create layered interference effects.

    Args:
        points: List of [x, y] vertex coordinates (minimum 3)
        spacing: Distance between fill lines in mm (2-3 = dense, 5-8 = sparse)
        angle: Fill line angle in degrees (vary per tile for pattern effects)
    """
    if len(points) < 3:
        return []
    # Outline
    cmds = expand_polygon(points, feed=feed, s_value=s_value)

    # Build edges
    pts = [(p[0], p[1]) for p in points]
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    edges = [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]

    # Bounding box
    all_x = [p[0] for p in pts]
    all_y = [p[1] for p in pts]
    min_y, max_y = min(all_y), max(all_y)
    center_x = (min(all_x) + max(all_x)) / 2
    center_y = (min_y + max_y) / 2

    # If angle != 0, rotate edges, fill, then rotate back
    if angle != 0:
        rotated_edges = []
        for (x0, y0), (x1, y1) in edges:
            rx0, ry0 = _rotate_point(x0, y0, center_x, center_y, -angle)
            rx1, ry1 = _rotate_point(x1, y1, center_x, center_y, -angle)
            rotated_edges.append(((rx0, ry0), (rx1, ry1)))
        edges = rotated_edges
        all_y_r = [p[0][1] for p in edges] + [p[1][1] for p in edges]
        min_y, max_y = min(all_y_r), max(all_y_r)

    y = min_y + spacing
    while y < max_y:
        xs = _scanline_intersections(y, edges)
        for i in range(0, len(xs) - 1, 2):
            x0, x1 = xs[i], xs[i + 1]
            if angle != 0:
                rx0, ry0 = _rotate_point(x0, y, center_x, center_y, angle)
                rx1, ry1 = _rotate_point(x1, y, center_x, center_y, angle)
                cmds.extend(_make_stroke([(rx0, ry0), (rx1, ry1)], feed, s_value))
            else:
                cmds.extend(_make_stroke([(x0, y), (x1, y)], feed, s_value))
        y += spacing

    return cmds


def expand_stipple(
    x: float, y: float, width: float, height: float,
    density: float = 0.5, dot_size: float = 0.5,
    feed: int = 2000, s_value: int = 1000,
) -> List[GCodeCommand]:
    """Fill a rectangle with stipple dots — use for pointillist texture, dot-matrix patterns, and tonal gradients without visible line direction. Tile stipple cells across the canvas and vary density per cell to create halftone-style gradients and photographic effects. Contrast stippled regions against hatched regions for visual variety.

    Args:
        x: Left edge X coordinate
        y: Bottom edge Y coordinate
        width: Rectangle width in mm
        height: Rectangle height in mm
        density: Dot density from 0.0 (sparse, barely visible) to 1.0 (dense, near-solid)
        dot_size: Size of each dot stroke in mm (0.3 = fine, 1.0 = bold)
    """
    cmds: List[GCodeCommand] = []
    # density 0..1 maps to spacing: 1.0 → tight (2mm), 0.1 → sparse (20mm)
    spacing = max(2.0, 20.0 * (1.0 - min(density, 1.0)))
    nx = max(1, int(width / spacing))
    ny = max(1, int(height / spacing))

    for ix in range(nx + 1):
        for iy in range(ny + 1):
            px = x + ix * (width / max(nx, 1))
            py = y + iy * (height / max(ny, 1))
            # Each dot is a tiny stroke
            cmds.extend(_make_stroke(
                [(px, py), (px + dot_size, py)],
                feed, s_value,
            ))

    return cmds


def expand_spiral(
    cx: float, cy: float,
    r_start: float = 0, r_end: float = 50,
    turns: float = 5, segments: int = 100,
    feed: int = 2000, s_value: int = 1000,
) -> List[GCodeCommand]:
    """Draw an Archimedean spiral — use for radial energy, organic flow within geometric compositions, vortex effects, and decorative rosettes. Tile spirals in grids with varying turns or radii for generative spiral fields. Combine with circles and hatched regions for layered complexity.

    Args:
        cx: Center X coordinate
        cy: Center Y coordinate
        r_start: Starting radius in mm (0 = start from center)
        r_end: Ending radius in mm
        turns: Number of full rotations (more = tighter winding)
        segments: Number of line segments (more = smoother, use 100+ for large spirals)
    """
    points = []
    total_angle = turns * 2 * math.pi
    for i in range(segments + 1):
        t = i / segments
        angle = t * total_angle
        r = r_start + (r_end - r_start) * t
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return _make_stroke(points, feed, s_value)


def expand_flow_field(
    x: float, y: float, width: float, height: float,
    cols: int = 12, rows: int = 12,
    base_angle: float = 0, angle_variation: float = 90,
    stroke_length: float = 10, spacing_noise: float = 0,
    feed: int = 2000, s_value: int = 1000,
) -> List[GCodeCommand]:
    """Generate a flow field of short oriented strokes — THE ORGANIC PLOTTER PATTERN. Places a grid of individual dashes across the area, each oriented by a smoothly varying angle field. Creates the flowing, wind-like patterns seen in generative plotter art. The angle at each position blends base_angle with a sinusoidal variation that creates natural-looking curves and swirls. Emit multiple flow_field primitives with different base_angle values to layer color passes.

    Args:
        x: Left edge X coordinate
        y: Bottom edge Y coordinate
        width: Field width in mm
        height: Field height in mm
        cols: Number of stroke columns across the field
        rows: Number of stroke rows down the field
        base_angle: Base direction of flow in degrees (0=right, 90=up)
        angle_variation: How much the angle varies across the field in degrees (higher = more swirl)
        stroke_length: Length of each individual dash in mm
        spacing_noise: Random offset for stroke positions (0=grid, higher=organic scatter)
    """
    cmds: List[GCodeCommand] = []
    cell_w = width / max(cols, 1)
    cell_h = height / max(rows, 1)

    for row in range(rows):
        for col in range(cols):
            # Center of this cell
            cx = x + (col + 0.5) * cell_w
            cy = y + (row + 0.5) * cell_h

            # Add positional noise for organic feel
            if spacing_noise > 0:
                # Deterministic pseudo-noise from position
                noise_x = math.sin(col * 12.9898 + row * 78.233) * spacing_noise
                noise_y = math.cos(col * 78.233 + row * 12.9898) * spacing_noise
                cx += noise_x
                cy += noise_y

            # Compute angle from smooth field: base + sinusoidal variation
            # Two overlapping sine waves create natural flow patterns
            t_x = col / max(cols - 1, 1)
            t_y = row / max(rows - 1, 1)
            field_angle = (
                base_angle
                + angle_variation * math.sin(t_x * math.pi * 2)
                + angle_variation * 0.5 * math.sin(t_y * math.pi * 3 + t_x * math.pi)
            )

            # Compute stroke endpoints
            rad = math.radians(field_angle)
            half = stroke_length / 2
            dx = half * math.cos(rad)
            dy = half * math.sin(rad)
            cmds.extend(_make_stroke(
                [(cx - dx, cy - dy), (cx + dx, cy + dy)],
                feed, s_value,
            ))

    return cmds


def expand_contour_path(
    points: List[List[float]],
    feed: int = 2000,
    s_value: int = 1000,
    closed: bool = False,
) -> List[GCodeCommand]:
    """Expand a freeform contour path into a single expressive stroke."""
    if len(points) < 2:
        return []
    stroke_points = [(float(p[0]), float(p[1])) for p in points]
    if closed and stroke_points[0] != stroke_points[-1]:
        stroke_points.append(stroke_points[0])
    return _make_stroke(stroke_points, feed, s_value)


def expand_texture_strokes(
    centers: List[List[float]],
    stroke_length: float = 8,
    angle: float = 30,
    jitter: float = 20,
    feed: int = 2000,
    s_value: int = 1000,
) -> List[GCodeCommand]:
    """Expand texture marks into many short varied strokes."""
    if not centers:
        return []
    points = [(float(p[0]), float(p[1])) for p in centers]
    return _make_marks(points, stroke_length, angle, feed, s_value, jitter=jitter)


def expand_accent_marks(
    centers: List[List[float]],
    stroke_length: float = 4,
    angle: float = 90,
    jitter: float = 35,
    feed: int = 2000,
    s_value: int = 1000,
) -> List[GCodeCommand]:
    """Expand accent marks into short directional dashes."""
    if not centers:
        return []
    points = [(float(p[0]), float(p[1])) for p in centers]
    return _make_marks(points, stroke_length, angle, feed, s_value, jitter=jitter)


def expand_hatch_region_freeform(
    x: float,
    y: float,
    width: float,
    height: float,
    angle: float = 30,
    spacing: float = 4,
    feed: int = 2000,
    s_value: int = 1000,
) -> List[GCodeCommand]:
    """Freeform hatch region compiled through the geometric hatch expander."""
    return expand_hatch(x, y, width, height, angle=angle, spacing=spacing, feed=feed, s_value=s_value)


def expand_negative_space_region(
    x: float,
    y: float,
    width: float,
    height: float,
    feed: int = 2000,
    s_value: int = 1000,
) -> List[GCodeCommand]:
    """Negative space regions are planning hints and compile to no drawing."""
    return []


def expand_contour_bundle(
    paths: List[List[List[float]]],
    feed: int = 2000,
    s_value: int = 1000,
) -> List[GCodeCommand]:
    cmds: List[GCodeCommand] = []
    for path in paths:
        cmds.extend(expand_contour_path(path, feed=feed, s_value=s_value))
    return cmds


def expand_gesture_path(
    points: List[List[float]],
    feed: int = 2000,
    s_value: int = 1000,
) -> List[GCodeCommand]:
    return expand_contour_path(points, feed=feed, s_value=s_value, closed=False)


def expand_shading_region(
    x: float,
    y: float,
    width: float,
    height: float,
    angle: float = 20,
    spacing: float = 5,
    feed: int = 2000,
    s_value: int = 1000,
) -> List[GCodeCommand]:
    return expand_hatch(x, y, width, height, angle=angle, spacing=spacing, feed=feed, s_value=s_value)


def expand_texture_cluster(
    centers: List[List[float]],
    stroke_length: float = 6,
    angle: float = 40,
    jitter: float = 30,
    feed: int = 2000,
    s_value: int = 1000,
) -> List[GCodeCommand]:
    return expand_texture_strokes(centers, stroke_length=stroke_length, angle=angle, jitter=jitter, feed=feed, s_value=s_value)


def expand_detail_pass_region(
    x: float,
    y: float,
    width: float,
    height: float,
    cols: int = 6,
    rows: int = 6,
    base_angle: float = 20,
    angle_variation: float = 40,
    stroke_length: float = 7,
    feed: int = 2000,
    s_value: int = 1000,
) -> List[GCodeCommand]:
    return expand_flow_field(
        x, y, width, height, cols=cols, rows=rows, base_angle=base_angle,
        angle_variation=angle_variation, stroke_length=stroke_length, feed=feed, s_value=s_value,
    )


def expand_reserve_region(**kwargs) -> List[GCodeCommand]:
    return []


def expand_field_stack(
    x: float,
    y: float,
    width: float,
    height: float,
    layers: int = 2,
    base_angle: float = 0,
    spacing: float = 6,
    feed: int = 2000,
    s_value: int = 1000,
) -> List[GCodeCommand]:
    cmds: List[GCodeCommand] = []
    for idx in range(max(1, layers)):
        cmds.extend(expand_hatch(
            x, y, width, height,
            angle=base_angle + idx * 22.5,
            spacing=max(2.0, spacing - idx),
            feed=feed,
            s_value=s_value,
        ))
    return cmds


def expand_moire_grid(
    x: float,
    y: float,
    width: float,
    height: float,
    angle_a: float = 15,
    angle_b: float = 28,
    spacing: float = 5,
    feed: int = 2000,
    s_value: int = 1000,
) -> List[GCodeCommand]:
    cmds = expand_hatch(x, y, width, height, angle=angle_a, spacing=spacing, feed=feed, s_value=s_value)
    cmds.extend(expand_hatch(x, y, width, height, angle=angle_b, spacing=spacing, feed=feed, s_value=s_value))
    return cmds


def expand_radial_field(
    cx: float,
    cy: float,
    radius: float,
    spokes: int = 24,
    stroke_length: float = 16,
    feed: int = 2000,
    s_value: int = 1000,
) -> List[GCodeCommand]:
    centers: List[Tuple[float, float]] = []
    for idx in range(spokes):
        angle = 2 * math.pi * idx / max(spokes, 1)
        centers.append((cx + math.cos(angle) * radius * 0.6, cy + math.sin(angle) * radius * 0.6))
    cmds: List[GCodeCommand] = []
    for idx, (px, py) in enumerate(centers):
        cmds.extend(_make_marks([(px, py)], stroke_length, idx * (360 / max(spokes, 1)), feed, s_value))
    return cmds


def expand_ring_field(
    cx: float,
    cy: float,
    r_start: float = 10,
    r_end: float = 70,
    rings: int = 5,
    feed: int = 2000,
    s_value: int = 1000,
) -> List[GCodeCommand]:
    cmds: List[GCodeCommand] = []
    for idx in range(rings):
        r = r_start + (r_end - r_start) * idx / max(rings - 1, 1)
        cmds.extend(expand_circle(cx, cy, r, segments=36, feed=feed, s_value=s_value))
    return cmds


def expand_tiling_field(
    x: float,
    y: float,
    width: float,
    height: float,
    cols: int = 4,
    rows: int = 4,
    sides: int = 4,
    spacing: float = 4,
    feed: int = 2000,
    s_value: int = 1000,
) -> List[GCodeCommand]:
    cmds: List[GCodeCommand] = []
    cell_w = width / max(cols, 1)
    cell_h = height / max(rows, 1)
    radius = min(cell_w, cell_h) * 0.35
    for row in range(rows):
        for col in range(cols):
            cx = x + (col + 0.5) * cell_w
            cy = y + (row + 0.5) * cell_h
            pts = []
            for idx in range(max(3, sides)):
                angle = 2 * math.pi * idx / max(3, sides)
                pts.append([cx + radius * math.cos(angle), cy + radius * math.sin(angle)])
            cmds.extend(expand_filled_polygon(pts, spacing=spacing, angle=(row + col) * 12, feed=feed, s_value=s_value))
    return cmds


def expand_gradient_hatch_region(
    x: float,
    y: float,
    width: float,
    height: float,
    angle: float = 20,
    spacing_start: float = 8,
    spacing_end: float = 3,
    steps: int = 4,
    feed: int = 2000,
    s_value: int = 1000,
) -> List[GCodeCommand]:
    cmds: List[GCodeCommand] = []
    step_w = width / max(steps, 1)
    for idx in range(steps):
        spacing = spacing_start + (spacing_end - spacing_start) * idx / max(steps - 1, 1)
        cmds.extend(expand_hatch(x + idx * step_w, y, step_w, height, angle=angle, spacing=spacing, feed=feed, s_value=s_value))
    return cmds


def expand_noise_warped_flow(
    x: float,
    y: float,
    width: float,
    height: float,
    cols: int = 12,
    rows: int = 12,
    base_angle: float = 0,
    angle_variation: float = 120,
    stroke_length: float = 10,
    spacing_noise: float = 4,
    feed: int = 2000,
    s_value: int = 1000,
) -> List[GCodeCommand]:
    return expand_flow_field(
        x, y, width, height, cols=cols, rows=rows, base_angle=base_angle,
        angle_variation=angle_variation, stroke_length=stroke_length,
        spacing_noise=spacing_noise, feed=feed, s_value=s_value,
    )


def expand_mask_region(**kwargs) -> List[GCodeCommand]:
    return []


def expand_border_system(
    x: float,
    y: float,
    width: float,
    height: float,
    inset: float = 4,
    layers: int = 2,
    feed: int = 2000,
    s_value: int = 1000,
) -> List[GCodeCommand]:
    cmds: List[GCodeCommand] = []
    for idx in range(max(1, layers)):
        ix = x + idx * inset
        iy = y + idx * inset
        iw = max(1.0, width - 2 * idx * inset)
        ih = max(1.0, height - 2 * idx * inset)
        pts = [[ix, iy], [ix + iw, iy], [ix + iw, iy + ih], [ix, iy + ih]]
        cmds.extend(expand_polygon(pts, feed=feed, s_value=s_value))
    return cmds


# ---------------------------------------------------------------------------
# Registry + dispatcher
# ---------------------------------------------------------------------------

PRIMITIVE_REGISTRY: Dict[str, Callable[..., List[GCodeCommand]]] = {
    "circle": expand_circle,
    "ellipse": expand_ellipse,
    "polygon": expand_polygon,
    "hatch": expand_hatch,
    "crosshatch": expand_crosshatch,
    "filled_polygon": expand_filled_polygon,
    "stipple": expand_stipple,
    "spiral": expand_spiral,
    "flow_field": expand_flow_field,
}

VALID_PRIMITIVE_TYPES = set(PRIMITIVE_REGISTRY.keys())
FREEFORM_REGISTRY: Dict[str, Callable[..., List[GCodeCommand]]] = {
    "contour_path": expand_contour_path,
    "silhouette_outline": expand_contour_path,
    "texture_strokes": expand_texture_strokes,
    "accent_marks": expand_accent_marks,
    "hatch_region": expand_hatch_region_freeform,
    "negative_space_region": expand_negative_space_region,
    "contour_bundle": expand_contour_bundle,
    "gesture_path": expand_gesture_path,
    "shading_region": expand_shading_region,
    "texture_cluster": expand_texture_cluster,
    "detail_pass_region": expand_detail_pass_region,
    "reserve_region": expand_reserve_region,
    "field_stack": expand_field_stack,
    "moire_grid": expand_moire_grid,
    "radial_field": expand_radial_field,
    "ring_field": expand_ring_field,
    "tiling_field": expand_tiling_field,
    "gradient_hatch_region": expand_gradient_hatch_region,
    "noise_warped_flow": expand_noise_warped_flow,
    "mask_region": expand_mask_region,
    "border_system": expand_border_system,
}


def expand_primitive(
    ptype: str, params: Dict[str, Any], pen_config: PenConfig,
) -> List[GCodeCommand]:
    """Expand a single primitive into GCode commands using pen config defaults."""
    if ptype not in PRIMITIVE_REGISTRY:
        raise ValueError(f"Unknown primitive type: {ptype!r}. Valid types: {sorted(VALID_PRIMITIVE_TYPES)}")
    fn = PRIMITIVE_REGISTRY[ptype]
    # Inject pen config defaults if not specified
    params = dict(params)  # copy
    params.setdefault("feed", pen_config.feed_rate)
    params.setdefault("s_value", pen_config.pen_down_s_value)
    return fn(**params)


def expand_freeform(
    ftype: str, params: Dict[str, Any], pen_config: PenConfig,
) -> List[GCodeCommand]:
    """Expand a single freeform command into GCode commands."""
    if ftype not in FREEFORM_REGISTRY:
        raise ValueError(f"Unknown freeform type: {ftype!r}. Valid types: {sorted(FREEFORM_REGISTRY)}")
    fn = FREEFORM_REGISTRY[ftype]
    params = dict(params)
    params.setdefault("feed", pen_config.feed_rate)
    params.setdefault("s_value", pen_config.pen_down_s_value)
    return fn(**params)


def _apply_color(commands: List[GCodeCommand], color) -> None:
    """Tag expanded drawing commands with a pen color index (in place)."""
    if color is None:
        return
    for c in commands:
        if c.command in ("M3", "G1"):
            c.color = color


def expand_primitives(program: DrawProgram, pen_config: PenConfig) -> GCodeProgram:
    """Expand all structured drawing commands in a DrawProgram."""
    expanded: List[GCodeCommand] = []
    primitive_count = 0
    freeform_count = 0
    for cmd in program.commands:
        if isinstance(cmd, PrimitiveCommand):
            primitive_count += 1
            out = expand_primitive(cmd.type, cmd.params, pen_config)
            _apply_color(out, cmd.color)
            expanded.extend(out)
        elif isinstance(cmd, FreeformCommand):
            freeform_count += 1
            out = expand_freeform(cmd.type, cmd.params, pen_config)
            _apply_color(out, cmd.color)
            expanded.extend(out)
        else:
            expanded.append(cmd)

    if not expanded:
        expanded = [GCodeCommand(command="M5"), GCodeCommand(command="G0", x=0, y=0)]

    structured_total = primitive_count + freeform_count
    return GCodeProgram(
        commands=expanded,
        metadata={
            **(program.metadata or {}),
            "primitives_expanded": True,
            "primitive_mix": {
                "primitive_count": primitive_count,
                "freeform_count": freeform_count,
                "primitive_ratio": primitive_count / structured_total if structured_total else 0.0,
                "freeform_ratio": freeform_count / structured_total if structured_total else 0.0,
            },
        },
    )


# ---------------------------------------------------------------------------
# Schema generation — auto-document primitives from function signatures
# ---------------------------------------------------------------------------

# Internal params injected from PenConfig, hidden from LLM
_HIDDEN_PARAMS = {"feed", "s_value"}


def _python_type_to_json(t: Any) -> str:
    """Map Python type hints to JSON schema type strings."""
    if t is float:
        return "number"
    if t is int:
        return "integer"
    if t is str:
        return "string"
    if t is bool:
        return "boolean"
    # Check for generic types like List[...]
    origin = getattr(t, "__origin__", None)
    if origin is list:
        return "array"
    return "string"


def _parse_google_docstring(docstring: str) -> Dict[str, str]:
    """Extract param descriptions from Google-style docstring Args: section."""
    result: Dict[str, str] = {}
    lines = docstring.split("\n")
    in_args = False
    for line in lines:
        stripped = line.strip()
        if stripped == "Args:":
            in_args = True
            continue
        if in_args:
            if stripped == "" or (not stripped.startswith(" ") and not ":" in stripped):
                break
            if ":" in stripped:
                param_name, _, desc = stripped.partition(":")
                param_name = param_name.strip()
                desc = desc.strip()
                if param_name:
                    result[param_name] = desc
    return result


def get_primitive_schema(name: str, func: Callable) -> Dict[str, Any]:
    """Generate a JSON-schema-like dict for one primitive from its signature."""
    sig = inspect.signature(func)
    hints = get_type_hints(func)
    doc_params = _parse_google_docstring(func.__doc__ or "")

    properties: Dict[str, Any] = {}
    required: List[str] = []
    for pname, param in sig.parameters.items():
        if pname in _HIDDEN_PARAMS:
            continue
        prop: Dict[str, Any] = {"type": _python_type_to_json(hints.get(pname))}
        if pname in doc_params:
            prop["description"] = doc_params[pname]
        if param.default is inspect.Parameter.empty:
            required.append(pname)
        else:
            prop["default"] = param.default
        properties[pname] = prop

    return {
        "type": name,
        "description": (func.__doc__ or "").split("\n")[0].strip(),
        "params": {"properties": properties, "required": required},
    }


def get_all_primitive_schemas() -> Dict[str, Dict]:
    """Generate schemas for all registered primitives."""
    return {name: get_primitive_schema(name, fn) for name, fn in PRIMITIVE_REGISTRY.items()}


def format_schemas_for_prompt() -> str:
    """Format all primitive schemas as a concise prompt block for the LLM."""
    schemas = get_all_primitive_schemas()
    lines = [
        "DRAWING PRIMITIVES (use for precise geometry — they expand into exact GCode automatically):",
        "Instead of computing circle/spiral/hatching coordinates yourself, emit PRIMITIVE commands.",
        "",
    ]
    for name, schema in schemas.items():
        props = schema["params"]["properties"]
        req = set(schema["params"]["required"])

        req_parts = []
        opt_parts = []
        example_params: Dict[str, Any] = {}
        for pname, pinfo in props.items():
            ptype = pinfo["type"]
            if pname in req:
                req_parts.append(f"{pname} ({ptype})")
                # Generate sensible example values
                example_params[pname] = _example_value(pname, ptype)
            else:
                default = pinfo.get("default")
                opt_parts.append(f"{pname} ({ptype}, default={default})")

        lines.append(f"PRIMITIVE: {name} — {schema['description']}")
        if req_parts:
            lines.append(f"  Required: {', '.join(req_parts)}")
        if opt_parts:
            lines.append(f"  Optional: {', '.join(opt_parts)}")
        example = {"command": "PRIMITIVE", "type": name, "params": example_params}
        lines.append(f"  Example: {json.dumps(example)}")
        lines.append("")

    lines.append("GENERATIVE PATTERN TECHNIQUES (how to create rich plotter art):")
    lines.append("")
    lines.append("  FLOW FIELDS — Organic, wind-like patterns (use flow_field primitive):")
    lines.append("    Place a flow_field primitive covering the canvas. Each stroke follows a smooth")
    lines.append("    angle field, creating flowing curves from many short dashes. Layer multiple")
    lines.append("    flow_field primitives with different base_angle values for multi-color passes.")
    lines.append("    - Gentle flow: angle_variation=45, stroke_length=12")
    lines.append("    - Turbulent swirl: angle_variation=180, stroke_length=8")
    lines.append("    - Dense field: cols=20, rows=20. Sparse field: cols=8, rows=8")
    lines.append("    - Add spacing_noise=2-5 for organic scatter (breaks the grid feel)")
    lines.append("")
    lines.append("  HATCH GRIDS — Structured geometric patterns (use hatch primitive):")
    lines.append("    Tile the canvas with a grid of small hatch rectangles and VARY THE ANGLE")
    lines.append("    per cell to create moiré interference, wave patterns, and op-art effects.")
    lines.append("    - Wave pattern: angle changes sinusoidally across rows or columns")
    lines.append("    - Radial pattern: angle points toward/away from a center point")
    lines.append("    - Interference: two overlapping wave functions create moiré beats")
    lines.append("    Use 50-200+ hatch primitives to fill the canvas. MORE cells = richer pattern.")
    lines.append("")
    lines.append("  TONAL VALUE SCALE (controlling density):")
    lines.append("    Lightest: empty cell (skip it) → stipple density=0.2 → hatch spacing=8")
    lines.append("    Mid-tone: hatch spacing=4 → hatch spacing=3")
    lines.append("    Darkest: crosshatch spacing=3 → crosshatch spacing=2")
    lines.append("    Vary spacing across the grid to create gradients and focal points.")
    lines.append("")
    lines.append("  LAYERING — Combine primitive types for complexity:")
    lines.append("    - Flow fields for organic movement + hatch grids for structured contrast")
    lines.append("    - Multiple hatch grids at different spacings overlaid for moiré")
    lines.append("    - Stipple fields contrasted against hatched regions")
    lines.append("    - Spirals as focal points within a field of hatched cells or flow strokes")
    lines.append("")
    lines.append("  TESSELLATIONS — Tile polygons edge-to-edge:")
    lines.append("    Grid of filled_polygon hexagons, triangles, or diamonds, each with")
    lines.append("    different hatch angle or spacing inside, creates quilt-like patterns.")
    lines.append("")
    lines.append("IMPORTANT — ALWAYS PREFER PRIMITIVES over raw G0/G1:")
    lines.append("  - For ANY pattern, field, grid, or repeating motif → use PRIMITIVE commands.")
    lines.append("  - For flow/swirl/organic patterns → use flow_field (NOT manual G1 strokes).")
    lines.append("  - For hatching/shading/texture → use hatch or crosshatch (NOT manual parallel G1 lines).")
    lines.append("  - For circles/arcs → use circle or ellipse (NOT manual G1 approximations).")
    lines.append("  - Use raw G0/G1 ONLY for unique one-off lines that no primitive covers.")
    lines.append("  - A good generative drawing is 80-100% PRIMITIVE commands, not raw GCode.")
    lines.append("  Each primitive auto-generates its own pen up/down — do NOT wrap them in M3/M5.")
    return "\n".join(lines)


def _example_value(pname: str, ptype: str) -> Any:
    """Generate a sensible example value for a parameter."""
    examples: Dict[str, Any] = {
        "cx": 100, "cy": 150, "x": 50, "y": 50,
        "radius": 40, "rx": 40, "ry": 25,
        "width": 80, "height": 60,
        "angle": 45, "spacing": 3,
        "density": 0.5, "dot_size": 0.5,
        "r_start": 0, "r_end": 40, "turns": 5,
        "points": [[50, 50], [100, 80], [75, 120]],
        "cols": 12, "rows": 12,
        "base_angle": 30, "angle_variation": 90,
        "stroke_length": 10, "spacing_noise": 2,
    }
    if pname in examples:
        return examples[pname]
    if ptype == "number":
        return 0.0
    if ptype == "integer":
        return 0
    if ptype == "array":
        return []
    return ""
