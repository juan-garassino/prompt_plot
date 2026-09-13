"""Shared 2D design kit — style-neutral line primitives for every piece.

Fills (serpentine/spiral/arc), orbits, marks, swatch bars, spaced-caps
single-stroke type, run clipping/fitting utilities, and re-exports of the
low-level generators helpers so pieces have ONE import site. Style (palette,
furniture system) is chosen at the LAMINA level — see ``promptplot/lamina``.
"""

from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple

from ..models import GCodeCommand
from .generators import (  # noqa: F401  (re-exported for pieces)
    _attention_matrix,
    _catmull_subdivide,
    _chain_segments,
    _dot,
    _limit_overdraw,
    _marching_squares,
    _poly,
    _stroke_text,
    _text_width,
)

Bounds = Tuple[float, float, float, float]

BAUHAUS_PALETTE = ["dodgerblue", "deeppink", "black"]
BLUE, PINK, BLACK = 0, 1, 2



def _pen(idx: int, colors: int) -> Optional[int]:
    return idx % colors if colors > 1 else None




# ---------------------------------------------------------------------------
# fills
# ---------------------------------------------------------------------------


def fill_rect(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    spacing: float = 0.55,
    pen: Optional[int] = None,
    f: int = 2200,
) -> List[GCodeCommand]:
    """Solid rectangle as one serpentine polyline."""
    pts = []
    y = y0
    flip = False
    while y <= y1 + 1e-9:
        row = [(x0, y), (x1, y)]
        pts.extend(reversed(row) if flip else row)
        flip = not flip
        y += spacing
    return _poly(pts, color=pen, f=f)




def fill_disc(
    cx: float, cy: float, r: float, spacing: float = 0.5, pen: Optional[int] = None, f: int = 2200
) -> List[GCodeCommand]:
    """Solid disc as one Archimedean spiral."""
    turns = max(2, int(r / spacing))
    n = turns * 30
    pts = []
    for k in range(n + 1):
        t = k / n
        rr = r * t
        a = 2 * math.pi * turns * t
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return _poly(pts, color=pen, f=f)




def fill_quarter(
    cx: float,
    cy: float,
    r: float,
    a_start: float,
    spacing: float = 0.55,
    pen: Optional[int] = None,
    f: int = 2200,
) -> List[GCodeCommand]:
    """Solid quarter-disc as concentric arcs."""
    out: List[GCodeCommand] = []
    rr = r
    while rr > 0.3:
        arc = []
        a = a_start
        while a <= a_start + math.pi / 2 + 1e-6:
            arc.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
            a += 0.08
        out += _poly(arc, color=pen, f=f)
        rr -= spacing
    return out




def fill_ring(
    cx: float,
    cy: float,
    r0: float,
    r1: float,
    spacing: float = 0.55,
    pen: Optional[int] = None,
    f: int = 2200,
) -> List[GCodeCommand]:
    out: List[GCodeCommand] = []
    rr = r0
    while rr <= r1 + 1e-9:
        ring = [
            (cx + rr * math.cos(2 * math.pi * k / 72), cy + rr * math.sin(2 * math.pi * k / 72))
            for k in range(73)
        ]
        out += _poly(ring, color=pen, f=f)
        rr += spacing
    return out




# ---------------------------------------------------------------------------
# geometry: runs, clipping (crop-at-frame + knockouts), cover-fit
# ---------------------------------------------------------------------------


def _runs_from_cmds(cmds: Sequence[GCodeCommand]) -> List[List[Tuple[float, float]]]:
    """Extract pen-down polylines from a command list."""
    runs: List[List[Tuple[float, float]]] = []
    cur: List[Tuple[float, float]] = []
    for c in cmds:
        if c.command == "G0":
            if len(cur) >= 2:
                runs.append(cur)
            cur = [(c.x, c.y)] if c.x is not None else []
        elif c.command == "G1" and c.x is not None:
            cur.append((c.x, c.y))
    if len(cur) >= 2:
        runs.append(cur)
    return runs




def _cut(inside, outside, keep, iters=14):
    """Bisect the crossing point between an inside and an outside point."""
    a, b = inside, outside
    for _ in range(iters):
        m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        if keep(m):
            a = m
        else:
            b = m
    return a




def _clip_runs(runs, keep) -> List[List[Tuple[float, float]]]:
    """Clip polylines to a boolean keep-region, cutting segments at the edge."""
    out: List[List[Tuple[float, float]]] = []
    for pts in runs:
        cur: List[Tuple[float, float]] = []
        for i, p in enumerate(pts):
            if i == 0:
                if keep(p):
                    cur.append(p)
                continue
            a = pts[i - 1]
            ka, kb = keep(a), keep(p)
            if ka and kb:
                if not cur:
                    cur = [a]
                cur.append(p)
            elif ka and not kb:
                if not cur:
                    cur = [a]
                cur.append(_cut(a, p, keep))
                if len(cur) >= 2:
                    out.append(cur)
                cur = []
            elif kb and not ka:
                cur = [_cut(p, a, keep), p]
        if len(cur) >= 2:
            out.append(cur)
    return out




def _rect_keep(region: Bounds, inset: float = 0.0):
    rx0, ry0, rx1, ry1 = region
    return lambda p: rx0 + inset <= p[0] <= rx1 - inset and ry0 + inset <= p[1] <= ry1 - inset




def _fit_runs_cover(runs, target: Bounds) -> List[List[Tuple[float, float]]]:
    """Uniform-scale + recenter runs so their bbox COVERS the target rect
    (overshoots on one axis — made for cropping at the frame)."""
    xs = [p[0] for r in runs for p in r]
    ys = [p[1] for r in runs for p in r]
    if not xs:
        return runs
    bx0, bx1, by0, by1 = min(xs), max(xs), min(ys), max(ys)
    tx0, ty0, tx1, ty1 = target
    s = max((tx1 - tx0) / max(1e-9, bx1 - bx0), (ty1 - ty0) / max(1e-9, by1 - by0))
    bcx, bcy = (bx0 + bx1) / 2, (by0 + by1) / 2
    tcx, tcy = (tx0 + tx1) / 2, (ty0 + ty1) / 2
    return [[(tcx + (px - bcx) * s, tcy + (py - bcy) * s) for px, py in r] for r in runs]




def _emit_runs(runs, pen: Optional[int], f: int = 2200) -> List[GCodeCommand]:
    out: List[GCodeCommand] = []
    for r in runs:
        out += _poly(r, color=pen, f=f)
    return out





# ---------------------------------------------------------------------------
# furniture
# ---------------------------------------------------------------------------


def circle(
    cx: float, cy: float, r: float, pen: Optional[int] = None, f: int = 2200, n: int = 96
) -> List[GCodeCommand]:
    ring = [
        (cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n))
        for k in range(n + 1)
    ]
    return _poly(ring, color=pen, f=f)




def dotted_circle(
    cx: float,
    cy: float,
    r: float,
    pen: Optional[int] = None,
    bounds: Optional[Bounds] = None,
    f: int = 2200,
) -> List[GCodeCommand]:
    out: List[GCodeCommand] = []
    seg: List[Tuple[float, float]] = []
    for k in range(241):
        a = 2 * math.pi * k / 240
        px, py = cx + r * math.cos(a), cy + r * math.sin(a)
        ok = (k % 6) < 2
        if ok and bounds is not None:
            ok = bounds[0] + 0.5 < px < bounds[2] - 0.5 and bounds[1] + 0.5 < py < bounds[3] - 0.5
        if ok:
            seg.append((px, py))
        else:
            if len(seg) >= 2:
                out += _poly(seg, color=pen, f=f)
            seg = []
    if len(seg) >= 2:
        out += _poly(seg, color=pen, f=f)
    return out




def plus_mark(
    x: float, y: float, s: float = 1.0, pen: Optional[int] = None, f: int = 2200
) -> List[GCodeCommand]:
    return _poly([(x - s, y), (x + s, y)], color=pen, f=f) + _poly(
        [(x, y - s), (x, y + s)], color=pen, f=f
    )




def crosshair_rules(
    bounds: Bounds,
    xs: Sequence[float] = (),
    ys: Sequence[float] = (),
    pen: Optional[int] = None,
    f: int = 2200,
) -> List[GCodeCommand]:
    x0, y0, x1, y1 = bounds
    out: List[GCodeCommand] = []
    for x in xs:
        out += _poly([(x, y0 + 0.5), (x, y1 - 0.5)], color=pen, f=f)
    for y in ys:
        out += _poly([(x0 + 0.5, y), (x1 - 0.5, y)], color=pen, f=f)
    return out




def swatch_bar(
    x: float,
    y_top: float,
    pens: Sequence[Optional[int]],
    size: float = 2.2,
    spacing: float = 0.5,
    f: int = 2200,
) -> List[GCodeCommand]:
    out: List[GCodeCommand] = []
    y = y_top
    for pen in pens:
        out += fill_rect(x, y - size, x + size * 0.82, y, spacing=spacing, pen=pen, f=f)
        y -= size + 0.7
    return out




# ---------------------------------------------------------------------------
# type
# ---------------------------------------------------------------------------


def _spaced(text: str) -> str:
    return " ".join(text)




def type_block(
    lines: Sequence[str],
    x: float,
    y_top: float,
    height: float = 2.6,
    pen: Optional[int] = None,
    underline: bool = True,
    f: int = 2200,
) -> List[GCodeCommand]:
    out: List[GCodeCommand] = []
    y = y_top
    for ln in lines:
        out += _stroke_text(_spaced(ln), x, y, height, color=pen, f=f)
        y -= height * 2.0
    if underline:
        out += _poly(
            [(x, y + height * 2.0 - 2.0), (x + 6.0, y + height * 2.0 - 2.0)], color=pen, f=f
        )
    return out




def scale_footer(
    bounds: Bounds,
    text: str = "M 1:80",
    pen: Optional[int] = None,
    height: float = 2.6,
    f: int = 2200,
) -> List[GCodeCommand]:
    x0, y0, x1, _y1 = bounds
    tw = _text_width(_spaced(text), height)
    return _stroke_text(_spaced(text), x1 - tw - 3.0, y0 + 3.0, height, color=pen, f=f)

