"""Seeded generative art generators.

Each generator has the signature ``gen(rng, bounds, colors=1, **params)`` and
returns a flat ``List[GCodeCommand]`` (strokes tagged with a color index). They
draw ALL randomness from ``rng`` (a :class:`SeededRNG`) so output is fully
reproducible from the seed. Results flow through the normal
merge_chunks → postprocess → preview/stream pipeline.

``bounds`` is the drawable rectangle ``(x0, y0, x1, y1)`` in millimetres.
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

from ..models import GCodeCommand
from .rng import SeededRNG

Bounds = Tuple[float, float, float, float]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _r(v: float) -> float:
    return round(v, 2)


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else (hi if v > hi else v)


def _color_for(
    colors: int, idx: Optional[int] = None, rng: Optional[SeededRNG] = None
) -> Optional[int]:
    if colors <= 1:
        return None
    if idx is not None:
        return idx % colors
    return rng.randint(0, colors - 1) if rng is not None else 0


def _poly(points, color=None, f: int = 1500, s: int = 1000) -> List[GCodeCommand]:
    """Build one stroke (G0 → M3 → G1… → M5) from a list of (x, y) points."""
    pts = [p for p in points if p is not None]
    if len(pts) < 2:
        return []
    cmds = [
        GCodeCommand(command="G0", x=_r(pts[0][0]), y=_r(pts[0][1])),
        GCodeCommand(command="M3", s=s, color=color),
    ]
    for x, y in pts[1:]:
        cmds.append(GCodeCommand(command="G1", x=_r(x), y=_r(y), f=f, color=color))
    cmds.append(GCodeCommand(command="M5"))
    return cmds


def _dot(x: float, y: float, r: float = 0.5, color=None, f: int = 1200) -> List[GCodeCommand]:
    """A tiny plotted dot (short back-and-forth so the pen leaves a mark)."""
    return [
        GCodeCommand(command="G0", x=_r(x - r), y=_r(y)),
        GCodeCommand(command="M3", s=1000, color=color),
        GCodeCommand(command="G1", x=_r(x + r), y=_r(y), f=f, color=color),
        GCodeCommand(command="M5"),
    ]


# ---------------------------------------------------------------------------
# 1. tiled directional field  (the dense h/v/diagonal/zigzag/maze tile photo)
# ---------------------------------------------------------------------------


def tiled_field(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 1,
    cell: float = 12.0,
    line_spacing: float = 2.2,
    blank_weight: float = 0.1,
    feed: int = 1500,
) -> List[GCodeCommand]:
    """Grid of cells, each seed-filled with h/v/diagonal/zigzag/cross/maze lines.

    Reproduces the dense directional-tile aesthetic. Each cell picks a fill
    pattern at random; with ``colors`` > 1 each cell also gets a pen color.
    """
    x0, y0, x1, y1 = bounds
    patterns = ["h", "v", "diag_up", "diag_down", "zigzag", "cross", "maze", "blank"]
    weights = [1.0, 1.0, 0.8, 0.8, 1.1, 0.7, 0.9, blank_weight]
    inset = max(0.6, line_spacing * 0.4)
    out: List[GCodeCommand] = []

    ny = int((y1 - y0) // cell)
    nx = int((x1 - x0) // cell)
    for iy in range(ny):
        for ix in range(nx):
            cx0 = x0 + ix * cell + inset
            cy0 = y0 + iy * cell + inset
            cx1 = cx0 + cell - 2 * inset
            cy1 = cy0 + cell - 2 * inset
            pat = rng.choices(patterns, weights=weights, k=1)[0]
            col = _color_for(colors, rng=rng)
            out += _tile(rng, pat, cx0, cy0, cx1, cy1, line_spacing, col, feed)
    return out


def _tile(rng, pat, x0, y0, x1, y1, spacing, color, feed) -> List[GCodeCommand]:
    cmds: List[GCodeCommand] = []
    if pat == "blank":
        return cmds
    if pat in ("h", "cross"):
        y = y0
        while y <= y1 + 1e-6:
            cmds += _poly([(x0, y), (x1, y)], color=color, f=feed)
            y += spacing
    if pat in ("v", "cross"):
        x = x0
        while x <= x1 + 1e-6:
            cmds += _poly([(x, y0), (x, y1)], color=color, f=feed)
            x += spacing
    if pat in ("diag_up", "diag_down"):
        up = pat == "diag_up"
        # sweep diagonal lines across the cell
        d = x0 - (y1 - y0)
        while d <= x1 + (y1 - y0):
            if up:
                p0 = (_clamp(d, x0, x1), y0)
                p1 = (_clamp(d + (y1 - y0), x0, x1), y1)
            else:
                p0 = (_clamp(d, x0, x1), y1)
                p1 = (_clamp(d + (y1 - y0), x0, x1), y0)
            cmds += _poly([p0, p1], color=color, f=feed)
            d += spacing * 1.4
    if pat == "zigzag":
        y = y0
        pts = []
        toggle = True
        while y <= y1 + 1e-6:
            pts.append((x1 if toggle else x0, y))
            toggle = not toggle
            y += spacing
        cmds += _poly(pts, color=color, f=feed)
    if pat == "maze":
        # a short right-angle random walk inside the cell
        gx = max(2, int((x1 - x0) / spacing))
        gy = max(2, int((y1 - y0) / spacing))
        cxs = [x0 + i * (x1 - x0) / gx for i in range(gx + 1)]
        cys = [y0 + j * (y1 - y0) / gy for j in range(gy + 1)]
        i, j = rng.randint(0, gx), rng.randint(0, gy)
        pts = [(cxs[i], cys[j])]
        for _ in range(gx + gy + 4):
            if rng.random() < 0.5:
                i = _clamp(i + rng.choice([-1, 1]), 0, gx)
            else:
                j = _clamp(j + rng.choice([-1, 1]), 0, gy)
            pts.append((cxs[int(i)], cys[int(j)]))
        cmds += _poly(pts, color=color, f=feed)
    return cmds


# ---------------------------------------------------------------------------
# 2. ripple / ridgeline displacement field  (concentric ripples → noise peaks)
# ---------------------------------------------------------------------------


def ripple_field(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 1,
    line_count: int = 70,
    wavelength: float = 16.0,
    decay: float = 0.9,
    base_amp: float = 9.0,
    noise_amp: float = 12.0,
    noise_scale: float = 0.05,
    step: float = 1.8,
    feed: int = 1400,
) -> List[GCodeCommand]:
    """Stack of scanlines each displaced by concentric ripples + radial noise.

    Center rows form clean concentric rings; toward the top/bottom edges the
    displacement dissolves into noisy peaks. Evokes the ripple/ridgeline piece.
    """
    x0, y0, x1, y1 = bounds
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    half_w = (x1 - x0) / 2.0
    diag = math.hypot(x1 - x0, y1 - y0) / 2.0
    margin = base_amp + noise_amp + 2.0
    inner_y0, inner_y1 = y0 + margin, y1 - margin
    out: List[GCodeCommand] = []

    for li in range(line_count):
        baseline = inner_y0 + (inner_y1 - inner_y0) * li / max(1, line_count - 1)
        pts = []
        x = x0
        while x <= x1 + 1e-6:
            r = math.hypot(x - cx, baseline - cy)
            ripple = (
                base_amp * math.cos(r / wavelength * 2 * math.pi) * math.exp(-decay * (r / diag))
            )
            radial = min(1.0, r / diag)  # edges noisier than center
            noise = (
                noise_amp
                * (rng.fbm(x * noise_scale, baseline * noise_scale, octaves=4) - 0.5)
                * radial
            )
            yv = _clamp(baseline + ripple + noise, y0, y1)
            pts.append((x, yv))
            x += step
        col = _color_for(colors, idx=li)
        out += _poly(pts, color=col, f=feed)
    return out


# ---------------------------------------------------------------------------
# 3. flow field  (particles traced through a noise-driven vector field)
# ---------------------------------------------------------------------------


def flow_field(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 1,
    particles: int = 140,
    steps: int = 90,
    step_len: float = 1.5,
    noise_scale: float = 0.02,
    turns: float = 2.0,
    min_sep: float = 3.0,
    feed: int = 1400,
) -> List[GCodeCommand]:
    """Evenly-spaced streamlines along a noise angle-field — flowing, non-overlapping.

    Uses the Jobard–Lefebvre method: a streamline stops as soon as it comes within
    ``min_sep`` mm of any existing line, and new seed points are rejected if too
    close. Guarantees lines never overlap — set ``min_sep`` to ~4–6× the pen width.
    ``particles`` is an upper bound; the field fills until packed or exhausted.
    """
    x0, y0, x1, y1 = bounds
    cell = max(min_sep, 0.5)
    grid: dict = {}  # (i, j) -> list of (x, y) sample points from placed lines

    def _key(x, y):
        return (int((x - x0) / cell), int((y - y0) / cell))

    def _too_close(x, y):
        gi, gj = _key(x, y)
        m2 = min_sep * min_sep
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                for px, py in grid.get((gi + di, gj + dj), ()):
                    if (px - x) ** 2 + (py - y) ** 2 < m2:
                        return True
        return False

    def _register(pts):
        for x, y in pts:
            grid.setdefault(_key(x, y), []).append((x, y))

    def _angle(x, y):
        return rng.fbm(x * noise_scale, y * noise_scale, octaves=3) * math.pi * 2 * turns

    def _trace(sx, sy, direction):
        pts = []
        x, y = sx, sy
        for _ in range(steps):
            pts.append((x, y))
            a = _angle(x, y)
            x += math.cos(a) * step_len * direction
            y += math.sin(a) * step_len * direction
            if not (x0 <= x <= x1 and y0 <= y <= y1):
                break
            if _too_close(x, y):
                break
        return pts

    out: List[GCodeCommand] = []
    placed = 0
    attempts = 0
    max_attempts = max(particles * 60, 4000)
    while placed < particles and attempts < max_attempts:
        attempts += 1
        sx = rng.uniform(x0, x1)
        sy = rng.uniform(y0, y1)
        if _too_close(sx, sy):
            continue
        fwd = _trace(sx, sy, +1)
        bwd = _trace(sx, sy, -1)
        pts = list(reversed(bwd[1:])) + fwd  # join, drop duplicated seed
        if len(pts) < 3:
            continue
        _register(pts)
        col = _color_for(colors, idx=placed)  # round-robin → balanced color counts
        out += _poly(pts, color=col, f=feed)
        placed += 1
    return out


# ---------------------------------------------------------------------------
# 4. maze  (recursive-backtracker corridors)
# ---------------------------------------------------------------------------


def maze(
    rng: SeededRNG, bounds: Bounds, colors: int = 1, cell: float = 10.0, feed: int = 1500
) -> List[GCodeCommand]:
    """A perfect maze (recursive backtracker) drawn as connected corridors."""
    x0, y0, x1, y1 = bounds
    cols = max(2, int((x1 - x0) // cell))
    rows = max(2, int((y1 - y0) // cell))
    ox = x0 + ((x1 - x0) - cols * cell) / 2 + cell / 2
    oy = y0 + ((y1 - y0) - rows * cell) / 2 + cell / 2

    def center(i, j):
        return (ox + i * cell, oy + j * cell)

    visited = [[False] * rows for _ in range(cols)]
    edges: List[Tuple[Tuple[int, int], Tuple[int, int]]] = []
    stack = [(0, 0)]
    visited[0][0] = True
    while stack:
        i, j = stack[-1]
        nbrs = []
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ni, nj = i + di, j + dj
            if 0 <= ni < cols and 0 <= nj < rows and not visited[ni][nj]:
                nbrs.append((ni, nj))
        if not nbrs:
            stack.pop()
            continue
        ni, nj = rng.choice(nbrs)
        visited[ni][nj] = True
        edges.append(((i, j), (ni, nj)))
        stack.append((ni, nj))

    out: List[GCodeCommand] = []
    for a, b in edges:
        col = _color_for(colors, rng=rng)
        out += _poly([center(*a), center(*b)], color=col, f=feed)
    return out


# ---------------------------------------------------------------------------
# 5. truchet tiles
# ---------------------------------------------------------------------------


def truchet(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 1,
    cell: float = 14.0,
    arc_segments: int = 10,
    feed: int = 1500,
) -> List[GCodeCommand]:
    """Grid of Truchet tiles — two quarter-arcs per cell in a random orientation."""
    x0, y0, x1, y1 = bounds
    cols = max(1, int((x1 - x0) // cell))
    rows = max(1, int((y1 - y0) // cell))
    out: List[GCodeCommand] = []

    def arc(cx, cy, r, a0, a1, color):
        pts = []
        for k in range(arc_segments + 1):
            a = a0 + (a1 - a0) * k / arc_segments
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        return _poly(pts, color=color, f=feed)

    R = cell / 2.0
    for iy in range(rows):
        for ix in range(cols):
            bx = x0 + ix * cell
            by = y0 + iy * cell
            col = _color_for(colors, rng=rng)
            if rng.random() < 0.5:
                # arcs at bottom-left and top-right corners
                out += arc(bx, by, R, 0, math.pi / 2, col)
                out += arc(bx + cell, by + cell, R, math.pi, 1.5 * math.pi, col)
            else:
                # arcs at bottom-right and top-left corners
                out += arc(bx + cell, by, R, math.pi / 2, math.pi, col)
                out += arc(bx, by + cell, R, 1.5 * math.pi, 2 * math.pi, col)
    return out


# ---------------------------------------------------------------------------
# 6. wave bands
# ---------------------------------------------------------------------------


def wave_bands(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 1,
    bands: int = 24,
    samples: int = 180,
    amp: float = 6.0,
    feed: int = 1400,
) -> List[GCodeCommand]:
    """Horizontal bands, each a summed-sine wave with random frequency/phase."""
    x0, y0, x1, y1 = bounds
    out: List[GCodeCommand] = []
    for b in range(bands):
        baseline = y0 + (y1 - y0) * (b + 0.5) / bands
        f1 = rng.uniform(0.6, 2.4)
        f2 = rng.uniform(1.5, 5.0)
        ph = rng.uniform(0, 2 * math.pi)
        a = amp * rng.uniform(0.5, 1.0)
        pts = []
        for k in range(samples + 1):
            t = k / samples
            x = x0 + (x1 - x0) * t
            phase = t * 2 * math.pi
            yv = baseline + a * (0.7 * math.sin(f1 * phase + ph) + 0.3 * math.sin(f2 * phase))
            pts.append((x, _clamp(yv, y0, y1)))
        out += _poly(pts, color=_color_for(colors, idx=b), f=feed)
    return out


# ---------------------------------------------------------------------------
# 7. stipple  (jittered dot field)
# ---------------------------------------------------------------------------


def stipple(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 1,
    count: int = 1100,
    dot: float = 0.6,
    feed: int = 1200,
) -> List[GCodeCommand]:
    """A field of jittered dots (density texture)."""
    x0, y0, x1, y1 = bounds
    out: List[GCodeCommand] = []
    cols = max(1, int(math.sqrt(count * (x1 - x0) / max(1e-6, y1 - y0))))
    rows = max(1, count // cols)
    for j in range(rows):
        for i in range(cols):
            cx = x0 + (i + 0.5) * (x1 - x0) / cols + rng.gauss(0, (x1 - x0) / cols * 0.3)
            cy = y0 + (j + 0.5) * (y1 - y0) / rows + rng.gauss(0, (y1 - y0) / rows * 0.3)
            cx = _clamp(cx, x0 + dot, x1 - dot)  # keep the whole dot on paper
            cy = _clamp(cy, y0, y1)
            out += _dot(cx, cy, r=dot, color=_color_for(colors, rng=rng), f=feed)
    return out


# ---------------------------------------------------------------------------
# 8. waves with circles  (concentric rings perturbed by growing radial waves)
# ---------------------------------------------------------------------------


def waves_with_circles(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 1,
    rings: int = 26,
    samples: int = 240,
    wobble: float = 0.18,
    lobes: int = 7,
    feed: int = 1400,
) -> List[GCodeCommand]:
    """Concentric rings whose radius is perturbed by a radial wave growing outward."""
    x0, y0, x1, y1 = bounds
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    r_max = min(x1 - x0, y1 - y0) / 2.0 - 2.0
    out: List[GCodeCommand] = []
    lobe_phase = rng.uniform(0, 2 * math.pi)
    for ri in range(1, rings + 1):
        base_r = r_max * ri / rings
        amp = wobble * base_r  # perturbation grows outward
        k = lobes + rng.randint(-1, 1)
        ph = lobe_phase + rng.uniform(-0.3, 0.3)
        pts = []
        for si in range(samples + 1):
            a = 2 * math.pi * si / samples
            r = base_r + amp * math.sin(k * a + ph)
            x = _clamp(cx + r * math.cos(a), x0, x1)
            y = _clamp(cy + r * math.sin(a), y0, y1)
            pts.append((x, y))
        out += _poly(pts, color=_color_for(colors, idx=ri - 1), f=feed)
    return out


# ---------------------------------------------------------------------------
# 9. crosshatch weave  (dense ±angle diagonal plaid, random colors per line)
# ---------------------------------------------------------------------------


def _clip_to_rect(cx, cy, dx, dy, x0, y0, x1, y1):
    """Clip the infinite line through (cx,cy) with direction (dx,dy) to the rect.
    Returns (ax, ay, bx, by) or None (Liang–Barsky on a long segment)."""
    L = math.hypot(x1 - x0, y1 - y0) * 1.5
    ax, ay, bx, by = cx - dx * L, cy - dy * L, cx + dx * L, cy + dy * L
    p = [-(bx - ax), (bx - ax), -(by - ay), (by - ay)]
    q = [ax - x0, x1 - ax, ay - y0, y1 - ay]
    u0, u1 = 0.0, 1.0
    for pi, qi in zip(p, q):
        if pi == 0:
            if qi < 0:
                return None
        else:
            t = qi / pi
            if pi < 0:
                u0 = max(u0, t)
            else:
                u1 = min(u1, t)
    if u0 > u1:
        return None
    return (ax + u0 * (bx - ax), ay + u0 * (by - ay), ax + u1 * (bx - ax), ay + u1 * (by - ay))


def crosshatch_weave(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 1,
    spacing: float = 4.0,
    angle: float = 45.0,
    wobble: float = 0.4,
    black_bias: float = 0.35,
    double_frac: float = 0.0,
    double_gap: float = 1.2,
    feed: int = 1500,
) -> List[GCodeCommand]:
    """Dense woven plaid: two families of parallel lines at ±angle, each a random
    color (black-dominant). Reproduces the diagonal cross-hatch weave look.

    ``spacing`` = perpendicular gap between parallel lines (mm). ``wobble`` adds a
    slight hand-drawn waver. With ``colors`` > 1, index 0 is treated as black and
    picked with probability ``black_bias`` so black dominates like the reference.
    ``double_frac`` (0..1) is the fraction of lines drawn as a close parallel pair
    (offset by ``double_gap`` mm) for a more dynamic, hand-woven rhythm.
    """
    x0, y0, x1, y1 = bounds
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    reach = math.hypot(x1 - x0, y1 - y0) / 2.0 + spacing

    def _pick_color():
        if colors <= 1:
            return None
        if colors >= 2 and rng.random() < black_bias:
            return 0
        return rng.randint(1, colors - 1) if colors > 1 else 0

    def _offset(pts, px, py, d):
        return [(_clamp(x + px * d, x0, x1), _clamp(y + py * d, y0, y1)) for x, y in pts]

    out: List[GCodeCommand] = []
    for sign in (+1.0, -1.0):
        rad = math.radians(angle) * sign
        dx, dy = math.cos(rad), math.sin(rad)
        px, py = -dy, dx  # perpendicular sweep direction
        n = int(reach / spacing)
        for i in range(-n, n + 1):
            t = i * spacing
            seg = _clip_to_rect(cx + px * t, cy + py * t, dx, dy, x0, y0, x1, y1)
            if seg is None:
                continue
            ax, ay, bx, by = seg
            length = math.hypot(bx - ax, by - ay)
            if length < spacing * 0.5:
                continue
            if wobble > 0:
                steps = max(2, int(length / 8))
                pts = []
                for k in range(steps + 1):
                    u = k / steps
                    wx = ax + (bx - ax) * u
                    wy = ay + (by - ay) * u
                    if 0 < k < steps:
                        w = (rng.random() - 0.5) * 2 * wobble
                        wx += px * w
                        wy += py * w
                    pts.append((_clamp(wx, x0, x1), _clamp(wy, y0, y1)))
            else:
                pts = [(ax, ay), (bx, by)]
            color = _pick_color()
            # decide double AFTER color so color stream stays stable per line
            if double_frac > 0 and rng.random() < double_frac:
                out += _poly(_offset(pts, px, py, +double_gap / 2), color=color, f=feed)
                out += _poly(_offset(pts, px, py, -double_gap / 2), color=color, f=feed)
            else:
                out += _poly(pts, color=color, f=feed)
    return out


# ---------------------------------------------------------------------------
# 10. turning weave  (diagonal 'L' paths: enter an edge, turn inside, exit an edge)
# ---------------------------------------------------------------------------


def turning_weave(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 1,
    spacing: float = 6.0,
    turn_prob: float = 0.3,
    min_run: int = 2,
    density: float = 0.85,
    black_bias: float = 0.35,
    long_frac: float = 0.18,
    long_turn_prob: float = 0.06,
    double_frac: float = 0.2,
    double_gap: float = 0.5,
    feed: int = 1500,
) -> List[GCodeCommand]:
    """Grid-aligned woven field of turning diagonal ('L') paths.

    Every stroke starts at a boundary node of a regular ``spacing`` grid, hops
    along an exact ±45° diagonal from node to node, turns 90° at grid nodes with
    probability ``turn_prob`` (after at least ``min_run`` hops), and exits on
    another edge. All corners land on the lattice, so it reads as a woven grid
    rather than a random scatter.

    Aesthetic controls: ``long_frac`` of paths sweep with the lower
    ``long_turn_prob`` (long runs for length contrast); ``double_frac`` of paths
    are drawn as a tight parallel pair (``double_gap`` mm) for a bolder weight.
    ``black_bias`` biases toward pen 0 for a dominant color. ``density`` = fraction
    of boundary starts used.
    """
    x0, y0, x1, y1 = bounds
    g = spacing
    nx = max(2, int((x1 - x0) / g))
    ny = max(2, int((y1 - y0) / g))

    def node(i, j):
        return (x0 + i * g, y0 + j * g)

    def inb(i, j):
        return 0 <= i <= nx and 0 <= j <= ny

    def _pick_color():
        if colors <= 1:
            return None
        if colors >= 2 and rng.random() < black_bias:
            return 0
        return rng.randint(1, colors - 1)

    def _emit(pts, di, dj, color, thick):
        if thick:
            # perpendicular to the LAST segment direction (grid-preserving offset)
            px, py = -dj, di
            n = math.hypot(px, py) or 1.0
            ox, oy = px / n * double_gap / 2, py / n * double_gap / 2
            out.extend(_poly([(x + ox, y + oy) for x, y in pts], color=color, f=feed))
            out.extend(_poly([(x - ox, y - oy) for x, y in pts], color=color, f=feed))
        else:
            out.extend(_poly(pts, color=color, f=feed))

    # Boundary start nodes, each with its inward axis component.
    starts = []
    for i in range(nx + 1):
        starts.append((i, 0, (0, +1)))  # bottom → up
        starts.append((i, ny, (0, -1)))  # top → down
    for j in range(ny + 1):
        starts.append((0, j, (+1, 0)))  # left → right
        starts.append((nx, j, (-1, 0)))  # right → left

    out: List[GCodeCommand] = []
    for si, sj, (ax, ay) in starts:
        if rng.random() > density:
            continue
        # a minority of paths sweep with a lower turn probability (length contrast)
        tp = long_turn_prob if rng.random() < long_frac else turn_prob
        # initial diagonal carrying the inward component
        if ax != 0:
            di, dj = ax, rng.choice([-1, 1])
        else:
            di, dj = rng.choice([-1, 1]), ay
        i, j = si, sj
        pts = [node(i, j)]
        for _ in range(2 * (nx + ny)):
            run = 0
            while inb(i + di, j + dj):
                i += di
                j += dj
                run += 1
                if run >= min_run and rng.random() < tp:
                    break
            pts.append(node(i, j))
            # turn onto the perpendicular diagonal if there's room
            ndi, ndj = (-dj, di) if rng.random() < 0.5 else (dj, -di)
            if inb(i + ndi, j + ndj):
                di, dj = ndi, ndj
            else:
                break
        if len(pts) >= 2:
            _emit(pts, di, dj, _pick_color(), double_frac > 0 and rng.random() < double_frac)
    return out


# ---------------------------------------------------------------------------
# 11. wave gradient  (rows of waves: calm at top, growing spiky peaks at bottom)
# ---------------------------------------------------------------------------


def wave_gradient(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 1,
    rows: int = 60,
    amp_min: float = 0.6,
    amp_max: float = 16.0,
    gamma: float = 2.3,
    ridged: float = 0.65,
    base_freq: float = 0.09,
    freq_growth: float = 1.9,
    octaves: int = 4,
    step: float = 1.2,
    feed: int = 1400,
) -> List[GCodeCommand]:
    """Rows of horizontal wavy lines whose amplitude grows top→bottom.

    Top rows are near-flat; toward the bottom the waves build into tall, spiky
    peaks (seismograph-like). Peaks point upward; amplitude follows ``frac**gamma``
    so the growth accelerates. ``ridged`` (0..1) sharpens smooth waves into cusped
    peaks; ``freq_growth`` makes lower rows busier.
    """
    x0, y0, x1, y1 = bounds
    row_gap = (y1 - y0) / max(1, rows - 1)
    out: List[GCodeCommand] = []

    for r in range(rows):
        frac = r / max(1, rows - 1)  # 0 = top row, 1 = bottom row
        baseline = y1 - (y1 - y0) * frac  # top (y1) down to bottom (y0)
        amp = amp_min + (amp_max - amp_min) * (frac**gamma)
        freq = base_freq * (1.0 + (freq_growth - 1.0) * frac)
        row_seed = r * 3.17 + 0.5
        pts = []
        x = x0
        while x <= x1 + 1e-6:
            # smooth sine ridge + fractal noise, sharpened toward cusped peaks
            s = math.sin(x * freq * 2 * math.pi)
            n = 0.0
            a, f = 1.0, 1.0
            norm = 0.0
            for _ in range(max(1, octaves)):
                n += a * (rng.noise2d(x * base_freq * f, row_seed * f) - 0.5) * 2
                norm += a
                a *= 0.55
                f *= 2.0
            n = n / norm if norm else 0.0
            mixed = 0.55 * s + 0.45 * n
            peak = abs(mixed) ** (1.0 - 0.6 * ridged)  # >0, cusped when ridged high
            yv = _clamp(baseline + amp * peak, y0, y1)
            pts.append((x, yv))
            x += step
        out += _poly(pts, color=_color_for(colors, idx=r), f=feed)
    return out


# ---------------------------------------------------------------------------
# 12. interference field  (circular ripples from drop sources, interfering)
# ---------------------------------------------------------------------------


def interference_field(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 1,
    line_count: int = 90,
    sources: int = 3,
    wavelength: float = 13.0,
    amp: float = 6.0,
    decay: float = 0.6,
    step: float = 1.1,
    source_inset: float = 0.15,
    feed: int = 1400,
) -> List[GCodeCommand]:
    """A field of horizontal scanlines displaced by interfering circular ripples.

    ``sources`` seeded 'drops' each emit a radial sine ``sin(2π·r/wavelength − φ)``
    that decays with distance; the lines bulge into concentric circles around each
    drop and beat against each other where ripples overlap (interference fringes) —
    like a ripple tank / raindrops on water. Fully reproducible from the seed.
    """
    x0, y0, x1, y1 = bounds
    w, h = x1 - x0, y1 - y0
    diag = math.hypot(w, h)

    drops = []
    for _ in range(max(1, sources)):
        sx = x0 + rng.uniform(source_inset, 1.0 - source_inset) * w
        sy = y0 + rng.uniform(source_inset, 1.0 - source_inset) * h
        phase = rng.uniform(0.0, 2 * math.pi)
        a = amp * rng.uniform(0.7, 1.2)
        drops.append((sx, sy, phase, a))

    headroom = amp * math.sqrt(max(1, sources)) + 2.0
    inner0, inner1 = y0 + headroom, y1 - headroom
    out: List[GCodeCommand] = []
    for li in range(line_count):
        baseline = inner0 + (inner1 - inner0) * li / max(1, line_count - 1)
        pts = []
        x = x0
        while x <= x1 + 1e-6:
            disp = 0.0
            for sx, sy, phase, a in drops:
                r = math.hypot(x - sx, baseline - sy)
                disp += (
                    a * math.sin(2 * math.pi * r / wavelength - phase) * math.exp(-decay * r / diag)
                )
            yv = _clamp(baseline + disp, y0, y1)
            pts.append((x, yv))
            x += step
        out += _poly(pts, color=_color_for(colors, idx=li), f=feed)
    return out


# ---------------------------------------------------------------------------
# 13. frequency lens  (rows of sine; inside a circle the frequency drops)
# ---------------------------------------------------------------------------


def frequency_lens(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 1,
    rows: int = 74,
    base_freq: float = 0.14,
    amp: float = 4.0,
    depth: float = 0.72,
    radius_frac: float = 0.28,
    feather: float = 0.6,
    lenses: int = 1,
    step: float = 1.0,
    feed: int = 1400,
) -> List[GCodeCommand]:
    """Rows of horizontal sine waves with circular 'lenses' of lower frequency.

    Everywhere the wavelength is normal, but inside each seeded circle the local
    frequency drops (``depth``: 0=no effect, →1=much slower), so the waves stretch
    out — a smooth bubble where the sine slows down. Frequency is integrated into a
    running phase so the wave stays continuous across the circle edge (no breaks).
    ``feather`` softens the circle boundary; ``lenses`` places more than one.
    """
    x0, y0, x1, y1 = bounds
    w, h = x1 - x0, y1 - y0
    R = radius_frac * min(w, h)
    Ro = R * (1.0 + max(0.0, feather))

    centers = []
    for _ in range(max(1, lenses)):
        cx = x0 + rng.uniform(0.3, 0.7) * w
        cy = y0 + rng.uniform(0.3, 0.7) * h
        centers.append((cx, cy))

    def _mask(x, y):
        """1 inside a lens, smoothly → 0 outside; max over all lenses."""
        m = 0.0
        for cx, cy in centers:
            d = math.hypot(x - cx, y - cy)
            if d <= R:
                mi = 1.0
            elif d >= Ro:
                mi = 0.0
            else:
                t = (d - R) / (Ro - R)
                mi = 1.0 - (t * t * (3.0 - 2.0 * t))  # smoothstep
            if mi > m:
                m = mi
        return m

    margin = amp + 2.0
    inner0, inner1 = y0 + margin, y1 - margin
    out: List[GCodeCommand] = []
    for r in range(rows):
        baseline = inner1 - (inner1 - inner0) * r / max(1, rows - 1)
        phase = 0.0
        prev_x = x0
        pts = []
        x = x0
        while x <= x1 + 1e-6:
            f_local = base_freq * (1.0 - depth * _mask(x, baseline))
            phase += 2 * math.pi * f_local * (x - prev_x)
            yv = _clamp(baseline + amp * math.sin(phase), y0, y1)
            pts.append((x, yv))
            prev_x = x
            x += step
        out += _poly(pts, color=_color_for(colors, idx=r), f=feed)
    return out


# ---------------------------------------------------------------------------
# 14. hitomezashi  (Japanese stitch: offset dashes -> emergent staircase weave)
# ---------------------------------------------------------------------------


def hitomezashi(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 1,
    spacing: float = 5.0,
    on_prob: float = 0.5,
    feed: int = 1600,
) -> List[GCodeCommand]:
    """Hitomezashi stitch pattern — the purest 'Ls on a grid'.

    Each grid row and column gets a seeded binary offset; dashes alternate
    on/off along it. The overlaps produce emergent staircase mazes and woven
    rectangles. With 2 pens, horizontal vs vertical stitches split by color;
    with 4, rows and columns alternate within their own pair.
    """
    x0, y0, x1, y1 = bounds
    g = spacing
    nx = max(2, int((x1 - x0) / g))
    ny = max(2, int((y1 - y0) / g))
    row_off = [1 if rng.random() < on_prob else 0 for _ in range(ny + 1)]
    col_off = [1 if rng.random() < on_prob else 0 for _ in range(nx + 1)]

    def h_color(j):
        if colors <= 1:
            return None
        if colors >= 4:
            return j % 2
        return 0

    def v_color(i):
        if colors <= 1:
            return None
        if colors >= 4:
            return 2 + i % 2
        return 1 % colors

    out: List[GCodeCommand] = []
    for j in range(ny + 1):
        y = y0 + j * g
        for i in range(nx):
            if (i + row_off[j]) % 2 == 0:
                out += _poly([(x0 + i * g, y), (x0 + (i + 1) * g, y)], color=h_color(j), f=feed)
    for i in range(nx + 1):
        x = x0 + i * g
        for j in range(ny):
            if (j + col_off[i]) % 2 == 0:
                out += _poly([(x, y0 + j * g), (x, y0 + (j + 1) * g)], color=v_color(i), f=feed)
    return out


def _limit_overdraw(pts, cell: float = 0.8, max_hits: int = 6):
    """Split a polyline into runs, dropping points where a small ink-density
    cell has already been drawn over ``max_hits`` times — protects the paper
    at convergence points of attractors/harmonographs."""
    hits = {}
    runs = []
    cur = []
    for pt in pts:
        k = (int(pt[0] / cell), int(pt[1] / cell))
        h = hits.get(k, 0)
        if h >= max_hits:
            if len(cur) >= 2:
                runs.append(cur)
            cur = []
            continue
        hits[k] = h + 1
        cur.append(pt)
    if len(cur) >= 2:
        runs.append(cur)
    return runs


# ---------------------------------------------------------------------------
# 15. harmonograph  (one continuous decaying pendulum curve)
# ---------------------------------------------------------------------------


def harmonograph(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 1,
    periods: float = 70.0,
    damping: float = 0.0045,
    detune: float = 0.012,
    max_points: int = 9000,
    min_seg: float = 0.6,
    overdraw: int = 6,
    feed: int = 1800,
) -> List[GCodeCommand]:
    """A damped double-pendulum (harmonograph) curve — one continuous stroke.

    x/y are sums of two decaying sinusoids with near-integer frequency ratios
    (seeded ``detune`` off perfect harmony gives the slow precession). With
    ``colors`` > 1 the timeline splits into successive pen layers, so the curve
    fades from one pen to the next as it decays inward.
    """
    x0, y0, x1, y1 = bounds
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0

    ratios = [1, 2, 3, 2, 3, 4]
    f1 = 1.0
    f2 = rng.choice(ratios) + rng.uniform(-detune, detune)
    f3 = rng.choice(ratios) + rng.uniform(-detune, detune)
    f4 = rng.choice(ratios) + rng.uniform(-detune, detune)
    p1, p2, p3, p4 = (rng.uniform(0, 2 * math.pi) for _ in range(4))
    a_mix = rng.uniform(0.35, 0.65)

    T = periods * 2 * math.pi
    raw = []
    n_steps = max_points * 3
    for k in range(n_steps + 1):
        t = T * k / n_steps
        d = math.exp(-damping * t)
        xv = d * (a_mix * math.sin(f1 * t + p1) + (1 - a_mix) * math.sin(f2 * t + p2))
        yv = d * (a_mix * math.sin(f3 * t + p3) + (1 - a_mix) * math.sin(f4 * t + p4))
        raw.append((xv, yv))

    # fit to bounds with a small inset
    xs = [p[0] for p in raw]
    ys = [p[1] for p in raw]
    sx = (x1 - x0) * 0.48 / max(1e-9, max(abs(min(xs)), abs(max(xs))))
    sy = (y1 - y0) * 0.48 / max(1e-9, max(abs(min(ys)), abs(max(ys))))
    s = min(sx, sy)

    pts = []
    lx = ly = None
    for xv, yv in raw:
        px = _clamp(cx + xv * s, x0, x1)
        py = _clamp(cy + yv * s, y0, y1)
        if lx is None or math.hypot(px - lx, py - ly) >= min_seg:
            pts.append((px, py))
            lx, ly = px, py
        if len(pts) >= max_points:
            break

    runs = _limit_overdraw(pts, max_hits=overdraw) if overdraw > 0 else [pts]
    total = sum(len(r) for r in runs) or 1
    out: List[GCodeCommand] = []
    acc = 0
    for r in runs:
        color = min(colors - 1, int(acc / total * colors)) if colors > 1 else None
        acc += len(r)
        out += _poly(r, color=color, f=feed)
    return out


# ---------------------------------------------------------------------------
# 16. vortex field  (scanlines swirled around whirlpool centers)
# ---------------------------------------------------------------------------


def vortex_field(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 1,
    line_count: int = 84,
    vortices: int = 2,
    swirl: float = 150.0,
    radius_frac: float = 0.42,
    step: float = 1.2,
    feed: int = 1400,
) -> List[GCodeCommand]:
    """Horizontal scanlines swirled around seeded vortex centers.

    Each point rotates about every vortex by an angle that decays with distance
    (Gaussian falloff), so straight lines wind into whirlpools — the rotational
    cousin of ``interference_field``. ``swirl`` is the max rotation in degrees.
    """
    x0, y0, x1, y1 = bounds
    w, h = x1 - x0, y1 - y0
    R = radius_frac * min(w, h)

    vs = []
    for _ in range(max(1, vortices)):
        vx = x0 + rng.uniform(0.22, 0.78) * w
        vy = y0 + rng.uniform(0.22, 0.78) * h
        sign = rng.choice([-1.0, 1.0])
        strength = math.radians(swirl) * rng.uniform(0.7, 1.15) * sign
        vs.append((vx, vy, strength))

    def warp(px, py):
        for vx, vy, strength in vs:
            dx, dy = px - vx, py - vy
            r2 = (dx * dx + dy * dy) / (R * R)
            theta = strength * math.exp(-r2)
            c, sn = math.cos(theta), math.sin(theta)
            px = vx + dx * c - dy * sn
            py = vy + dx * sn + dy * c
        return px, py

    out: List[GCodeCommand] = []
    for li in range(line_count):
        baseline = y0 + (y1 - y0) * li / max(1, line_count - 1)
        pts = []
        x = x0
        while x <= x1 + 1e-6:
            px, py = warp(x, baseline)
            pts.append((_clamp(px, x0, x1), _clamp(py, y0, y1)))
            x += step
        out += _poly(pts, color=_color_for(colors, idx=li), f=feed)
    return out


# ---------------------------------------------------------------------------
# 17. moiré layers  (same grid drawn per pen at tiny rotations -> physical moiré)
# ---------------------------------------------------------------------------


def moire_layers(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 2,
    pitch: float = 2.8,
    rotate_step: float = 2.2,
    base_angle: float = -1.0,
    feed: int = 1600,
) -> List[GCodeCommand]:
    """Parallel-line layers at tiny relative rotations — moiré appears on paper.

    Every pen draws the SAME line grid rotated by ``rotate_step`` degrees from the
    previous one, centered on the sheet. Plotted in different pens, the physical
    overlap creates moiré interference fringes. ``base_angle`` < 0 → seeded.
    """
    x0, y0, x1, y1 = bounds
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    reach = math.hypot(x1 - x0, y1 - y0) / 2.0 + pitch
    layers = max(2, colors)
    a0 = rng.uniform(0.0, 180.0) if base_angle < 0 else base_angle

    out: List[GCodeCommand] = []
    for L in range(layers):
        ang = math.radians(a0 + (L - (layers - 1) / 2.0) * rotate_step)
        dx, dy = math.cos(ang), math.sin(ang)
        px, py = -dy, dx
        color = L % max(1, colors) if colors > 1 else None
        n = int(reach / pitch)
        for i in range(-n, n + 1):
            t = i * pitch
            seg = _clip_to_rect(cx + px * t, cy + py * t, dx, dy, x0, y0, x1, y1)
            if seg is None:
                continue
            ax, ay, bx, by = seg
            if math.hypot(bx - ax, by - ay) < pitch:
                continue
            # serpentine: alternate direction so travel moves are short
            if i % 2 == 0:
                out += _poly([(ax, ay), (bx, by)], color=color, f=feed)
            else:
                out += _poly([(bx, by), (ax, ay)], color=color, f=feed)
    return out


# ---------------------------------------------------------------------------
# 18. strange attractor  (controlled chaos — ported from formCollapse systems)
# ---------------------------------------------------------------------------

_ATTRACTOR_SYSTEMS = {
    # name: (deriv(x, y, z) -> (dx, dy, dz), dt, initial, transient_steps)
    "lorenz": (
        lambda x, y, z: (10.0 * (y - x), x * (28.0 - z) - y, x * y - (8.0 / 3.0) * z),
        0.004,
        (0.1, 0.0, 0.0),
        500,
    ),
    "rossler": (
        lambda x, y, z: (-y - z, x + 0.2 * y, 0.2 + z * (x - 5.7)),
        0.02,
        (0.1, 0.0, 0.0),
        500,
    ),
    "halvorsen": (
        lambda x, y, z: (
            -1.89 * x - 4 * y - 4 * z - y * y,
            -1.89 * y - 4 * z - 4 * x - z * z,
            -1.89 * z - 4 * x - 4 * y - x * x,
        ),
        0.006,
        (-1.48, -1.51, 2.04),
        800,
    ),
    "aizawa": (
        lambda x, y, z: (
            (z - 0.7) * x - 3.5 * y,
            3.5 * x + (z - 0.7) * y,
            0.6 + 0.95 * z - z * z * z / 3 - (x * x + y * y) * (1 + 0.25 * z) + 0.1 * z * x * x * x,
        ),
        0.01,
        (0.1, 0.0, 0.0),
        800,
    ),
}


def strange_attractor(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 1,
    system: str = "lorenz",
    steps: int = 26000,
    min_seg: float = 0.5,
    max_points: int = 9000,
    overdraw: int = 6,
    feed: int = 1800,
) -> List[GCodeCommand]:
    """A strange attractor traced as one continuous line (controlled chaos).

    Systems ported from the formCollapse catalog: ``lorenz``, ``rossler``,
    ``halvorsen``, ``aizawa``. RK4-integrated; the seed jitters the initial
    condition and picks the 3D→2D projection angle, so every seed is a different
    view of the same chaos. With ``colors`` > 1 the timeline splits into pens.
    """
    if system not in _ATTRACTOR_SYSTEMS:
        raise ValueError(f"Unknown system {system!r}. Valid: {sorted(_ATTRACTOR_SYSTEMS)}")
    deriv, dt, init, transient = _ATTRACTOR_SYSTEMS[system]
    x0, y0, x1, y1 = bounds
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0

    # seeded initial-condition jitter + seeded projection angles
    x, y, z = (v + rng.uniform(-0.05, 0.05) for v in init)
    ax_r = rng.uniform(0, 2 * math.pi)  # rotation about x-axis
    az_r = rng.uniform(0, 2 * math.pi)  # rotation about z-axis
    ca, sa = math.cos(ax_r), math.sin(ax_r)
    cb, sb = math.cos(az_r), math.sin(az_r)

    def rk4(x, y, z):
        k1 = deriv(x, y, z)
        k2 = deriv(x + dt / 2 * k1[0], y + dt / 2 * k1[1], z + dt / 2 * k1[2])
        k3 = deriv(x + dt / 2 * k2[0], y + dt / 2 * k2[1], z + dt / 2 * k2[2])
        k4 = deriv(x + dt * k3[0], y + dt * k3[1], z + dt * k3[2])
        return (
            x + dt / 6 * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0]),
            y + dt / 6 * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1]),
            z + dt / 6 * (k1[2] + 2 * k2[2] + 2 * k3[2] + k4[2]),
        )

    raw = []
    for k in range(steps):
        x, y, z = rk4(x, y, z)
        if not (math.isfinite(x) and math.isfinite(y) and math.isfinite(z)):
            break
        if k < transient:
            continue
        # rotate about z then x, project to (x, y)
        rx = x * cb - y * sb
        ry = x * sb + y * cb
        py = ry * ca - z * sa
        raw.append((rx, py))
    if len(raw) < 2:
        return []

    xs = [p[0] for p in raw]
    ys = [p[1] for p in raw]
    mx, my = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    sx = (x1 - x0) * 0.48 / max(1e-9, (max(xs) - min(xs)) / 2)
    sy = (y1 - y0) * 0.48 / max(1e-9, (max(ys) - min(ys)) / 2)
    s = min(sx, sy)

    pts = []
    lx = ly = None
    for rx, ryv in raw:
        px = _clamp(cx + (rx - mx) * s, x0, x1)
        pyv = _clamp(cy + (ryv - my) * s, y0, y1)
        if lx is None or math.hypot(px - lx, pyv - ly) >= min_seg:
            pts.append((px, pyv))
            lx, ly = px, pyv
        if len(pts) >= max_points:
            break

    runs = _limit_overdraw(pts, max_hits=overdraw) if overdraw > 0 else [pts]
    total = sum(len(r) for r in runs) or 1
    out: List[GCodeCommand] = []
    acc = 0
    for r in runs:
        color = min(colors - 1, int(acc / total * colors)) if colors > 1 else None
        acc += len(r)
        out += _poly(r, color=color, f=feed)
    return out


# ---------------------------------------------------------------------------
# 19. domain warp  (scanlines through warped noise -> liquid marble)
# ---------------------------------------------------------------------------


def domain_warp(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 1,
    line_count: int = 90,
    warp_amp: float = 16.0,
    noise_scale: float = 0.014,
    inner_warp: float = 2.2,
    octaves: int = 4,
    step: float = 1.2,
    feed: int = 1400,
) -> List[GCodeCommand]:
    """Scanlines displaced by domain-warped noise — marbled, liquid flow.

    The displacement field is fbm noise sampled at coordinates that are
    themselves warped by more fbm (``inner_warp``), giving the folded, fluid
    look of marbling — the turbulent sibling of ``vortex_field``.
    """
    x0, y0, x1, y1 = bounds
    headroom = warp_amp + 2.0
    inner0, inner1 = y0 + headroom, y1 - headroom
    out: List[GCodeCommand] = []
    for li in range(line_count):
        baseline = inner0 + (inner1 - inner0) * li / max(1, line_count - 1)
        pts = []
        x = x0
        while x <= x1 + 1e-6:
            qx = rng.fbm(x * noise_scale, baseline * noise_scale, octaves=octaves)
            qy = rng.fbm(x * noise_scale + 41.3, baseline * noise_scale + 7.9, octaves=octaves)
            n = rng.fbm(
                x * noise_scale + inner_warp * (qx - 0.5),
                baseline * noise_scale + inner_warp * (qy - 0.5),
                octaves=octaves,
            )
            yv = _clamp(baseline + warp_amp * (n - 0.5) * 2.0, y0, y1)
            pts.append((x, yv))
            x += step
        out += _poly(pts, color=_color_for(colors, idx=li), f=feed)
    return out


# ---------------------------------------------------------------------------
# 20. contour field  (topographic isolines of a seeded scalar field)
# ---------------------------------------------------------------------------


def _marching_squares(F, xs, ys, iso):
    """Extract iso-contour segments from grid F[j][i] (j indexes ys)."""
    segs = []
    for j in range(len(ys) - 1):
        for i in range(len(xs) - 1):
            v0, v1 = F[j][i], F[j][i + 1]
            v2, v3 = F[j + 1][i + 1], F[j + 1][i]
            case = (v0 > iso) | ((v1 > iso) << 1) | ((v2 > iso) << 2) | ((v3 > iso) << 3)
            if case == 0 or case == 15:
                continue
            xa, xb = xs[i], xs[i + 1]
            ya, yb = ys[j], ys[j + 1]

            def _lerp(pa, pb, va, vb):
                t = (iso - va) / (vb - va) if vb != va else 0.5
                return (pa[0] + t * (pb[0] - pa[0]), pa[1] + t * (pb[1] - pa[1]))

            eb = _lerp((xa, ya), (xb, ya), v0, v1)
            er = _lerp((xb, ya), (xb, yb), v1, v2)
            et = _lerp((xb, yb), (xa, yb), v2, v3)
            el = _lerp((xa, yb), (xa, ya), v3, v0)
            table = {
                1: [(el, eb)],
                2: [(eb, er)],
                3: [(el, er)],
                4: [(er, et)],
                5: [(el, et), (eb, er)],
                6: [(eb, et)],
                7: [(el, et)],
                8: [(et, el)],
                9: [(eb, et)],
                10: [(eb, el), (er, et)],
                11: [(er, et)],
                12: [(er, el)],
                13: [(eb, er)],
                14: [(eb, el)],
            }
            segs.extend(table[case])
    return segs


def _chain_segments(segs, tol: float = 1e-3):
    """Join marching-squares segments into polylines by matching endpoints."""

    def key(p):
        return (round(p[0] / tol), round(p[1] / tol))

    adj = {}
    for idx, (a, b) in enumerate(segs):
        adj.setdefault(key(a), []).append((idx, 0))
        adj.setdefault(key(b), []).append((idx, 1))
    used = [False] * len(segs)
    chains = []
    for start in range(len(segs)):
        if used[start]:
            continue
        used[start] = True
        a, b = segs[start]
        chain = [a, b]
        # extend forward from b, then backward from a
        for endpoint, append in ((b, True), (a, False)):
            cur = endpoint
            while True:
                found = None
                for idx, end in adj.get(key(cur), []):
                    if not used[idx]:
                        found = (idx, end)
                        break
                if found is None:
                    break
                idx, end = found
                used[idx] = True
                nxt = segs[idx][1 - end]
                if append:
                    chain.append(nxt)
                else:
                    chain.insert(0, nxt)
                cur = nxt
        chains.append(chain)
    return chains


def contour_field(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 1,
    levels: int = 16,
    cell: float = 2.2,
    field: str = "noise",
    blobs: int = 5,
    noise_scale: float = 0.016,
    octaves: int = 4,
    min_pts: int = 4,
    feed: int = 1400,
) -> List[GCodeCommand]:
    """Topographic contour map: isolines of a seeded scalar field.

    ``field``: ``noise`` (fbm terrain), ``blobs`` (gaussian hills → nested rings),
    or ``ridge`` (ridged noise → sharp valley lines). Isolines are extracted with
    marching squares and chained into smooth closed/open polylines — the calm,
    map-like register. Colors cycle per elevation level.
    """
    x0, y0, x1, y1 = bounds
    xs = [x0 + i * cell for i in range(int((x1 - x0) / cell) + 1)]
    ys = [y0 + j * cell for j in range(int((y1 - y0) / cell) + 1)]

    centers = []
    if field == "blobs":
        for _ in range(max(1, blobs)):
            centers.append(
                (
                    x0 + rng.uniform(0.15, 0.85) * (x1 - x0),
                    y0 + rng.uniform(0.15, 0.85) * (y1 - y0),
                    rng.uniform(0.15, 0.45) * min(x1 - x0, y1 - y0),
                    rng.uniform(0.6, 1.0),
                )
            )

    def sample(x, y):
        if field == "blobs":
            v = 0.0
            for cxb, cyb, rb, ab in centers:
                d2 = ((x - cxb) ** 2 + (y - cyb) ** 2) / (rb * rb)
                v += ab * math.exp(-d2)
            return v
        n = rng.fbm(x * noise_scale, y * noise_scale, octaves=octaves)
        if field == "ridge":
            return 1.0 - abs(2.0 * n - 1.0)
        return n

    F = [[sample(x, y) for x in xs] for y in ys]
    flat = [v for row in F for v in row]
    lo, hi = min(flat), max(flat)
    if hi - lo < 1e-9:
        return []

    out: List[GCodeCommand] = []
    for lv in range(levels):
        iso = lo + (hi - lo) * (lv + 1) / (levels + 1)
        segs = _marching_squares(F, xs, ys, iso)
        for chain in _chain_segments(segs):
            if len(chain) >= min_pts:
                pts = [(_clamp(px, x0, x1), _clamp(py, y0, y1)) for px, py in chain]
                out += _poly(pts, color=_color_for(colors, idx=lv), f=feed)
    return out


# ---------------------------------------------------------------------------
# 21. superformula bloom  (nested rotating superformula shells -> mandala)
# ---------------------------------------------------------------------------


def superformula_bloom(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 1,
    shells: int = 42,
    points: int = 240,
    rotate_per_shell: float = 2.0,
    scale_min: float = 0.06,
    feed: int = 1500,
) -> List[GCodeCommand]:
    """Nested, slowly rotating superformula outlines — a botanical mandala.

    The seed picks the superformula parameters (m petals, n1..n3 curvature), so
    each seed is a different 'species'. Shells grow from the centre outward with
    a cumulative twist. With multiple pens, shells split into contiguous bands.
    """
    x0, y0, x1, y1 = bounds
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    r_max = min(x1 - x0, y1 - y0) / 2.0 - 2.0

    m = rng.randint(3, 12)
    n1 = rng.uniform(0.4, 6.0)
    n2 = rng.uniform(0.5, 6.0)
    n3 = rng.uniform(0.5, 6.0)

    base = []
    biggest = 1e-9
    for k in range(points + 1):
        th = 2 * math.pi * k / points
        t1 = abs(math.cos(m * th / 4.0)) ** n2
        t2 = abs(math.sin(m * th / 4.0)) ** n3
        denom = (t1 + t2) ** (1.0 / n1) if (t1 + t2) > 1e-12 else 1e-12
        r = 1.0 / denom
        r = min(r, 1e6)
        base.append((th, r))
        biggest = max(biggest, r)

    out: List[GCodeCommand] = []
    for sh in range(shells):
        frac = sh / max(1, shells - 1)
        scale = (scale_min + (1.0 - scale_min) * frac) * r_max
        rot = math.radians(rotate_per_shell) * sh
        pts = []
        for th, r in base:
            rr = (r / biggest) * scale
            px = _clamp(cx + rr * math.cos(th + rot), x0, x1)
            py = _clamp(cy + rr * math.sin(th + rot), y0, y1)
            pts.append((px, py))
        color = (sh * colors) // shells if colors > 1 else None
        out += _poly(pts, color=color, f=feed)
    return out


# ---------------------------------------------------------------------------
# 22. lissajous carpet  (the classic frequency table as a grid of curve cells)
# ---------------------------------------------------------------------------


def lissajous_carpet(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 1,
    cell: float = 26.0,
    points: int = 220,
    inset_frac: float = 0.12,
    feed: int = 1500,
) -> List[GCodeCommand]:
    """A grid of Lissajous cells — frequency a grows along x, b along y.

    The classic physics 'Lissajous table': cell (col, row) draws
    ``x=sin(a·t+φ), y=sin(b·t)`` with a=col+1, b=row+1 and a seeded shared phase
    drift, so the whole carpet is one coherent family. Colors follow diagonals.
    """
    x0, y0, x1, y1 = bounds
    cols = max(1, int((x1 - x0) / cell))
    rows = max(1, int((y1 - y0) / cell))
    ox = x0 + ((x1 - x0) - cols * cell) / 2.0
    oy = y0 + ((y1 - y0) - rows * cell) / 2.0
    phi0 = rng.uniform(0, 2 * math.pi)
    drift = rng.uniform(0.0, math.pi / 2)
    half = cell * (0.5 - inset_frac)

    out: List[GCodeCommand] = []
    for rj in range(rows):
        for ci in range(cols):
            a = ci + 1
            b = rj + 1
            phi = phi0 + drift * (ci + rj) / max(1, cols + rows - 2)
            ccx = ox + (ci + 0.5) * cell
            ccy = oy + (rj + 0.5) * cell
            pts = []
            for k in range(points + 1):
                t = 2 * math.pi * k / points
                pts.append(
                    (
                        _clamp(ccx + half * math.sin(a * t + phi), x0, x1),
                        _clamp(ccy + half * math.sin(b * t), y0, y1),
                    )
                )
            out += _poly(pts, color=_color_for(colors, idx=ci + rj), f=feed)
    return out


# ---------------------------------------------------------------------------
# 23. scribble halftone  (image tones -> thousands of short seeded dashes)
# ---------------------------------------------------------------------------


def scribble_halftone(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 1,
    image: str = "",
    cell: float = 2.4,
    max_per_cell: int = 3,
    dash_len: float = 3.2,
    gamma: float = 1.4,
    threshold: float = 0.08,
    max_strokes: int = 14000,
    invert: bool = False,
    feed: int = 1800,
) -> List[GCodeCommand]:
    """Render an image as a field of short scribbled dashes (hatching portrait).

    Darkness drives density: dark areas get up to ``max_per_cell`` crossing
    dashes per ``cell`` mm; light areas stay blank. Dash positions/angles are
    seeded, so the same seed + image reproduces exactly. Without ``image`` a
    procedural fbm tone field is used (standalone demo mode). With multiple
    pens, tonal bands map to pens (darkest band → pen 0).
    Requires Pillow for image input (``pip install -e ".[vision]"``).
    """
    x0, y0, x1, y1 = bounds
    bw, bh = x1 - x0, y1 - y0

    if image:
        try:
            from PIL import Image
        except ImportError:
            raise RuntimeError("Pillow required for image input: pip install -e '.[vision]'")
        img = Image.open(image).convert("L")
        # fit image into bounds preserving aspect, centered
        iw, ih = img.size
        s = min(bw / iw, bh / ih)
        gw = max(2, int(iw * s / cell))
        gh = max(2, int(ih * s / cell))
        small = img.resize((gw, gh))
        px = small.load()
        off_x = x0 + (bw - gw * cell) / 2.0
        off_y = y0 + (bh - gh * cell) / 2.0

        def tone(i, j):
            # image y grows downward; flip so the drawing isn't mirrored
            v = px[i, gh - 1 - j] / 255.0
            return v if invert else 1.0 - v

    else:
        gw = max(2, int(bw / cell))
        gh = max(2, int(bh / cell))
        off_x, off_y = x0, y0

        def tone(i, j):
            return rng.fbm(i * 0.06, j * 0.06, octaves=4)

    # first pass: total demand so we can thin uniformly to max_strokes
    demand = []
    total = 0
    for j in range(gh):
        for i in range(gw):
            d = tone(i, j)
            d = max(0.0, min(1.0, d)) ** gamma
            if d < threshold:
                continue
            n = max(1, round(d * max_per_cell))
            demand.append((i, j, d, n))
            total += n
    keep = min(1.0, max_strokes / total) if total else 0.0

    out: List[GCodeCommand] = []
    placed = 0
    for i, j, d, n in demand:
        cx = off_x + (i + 0.5) * cell
        cy = off_y + (j + 0.5) * cell
        for _ in range(n):
            if keep < 1.0 and rng.random() > keep:
                continue
            ang = rng.uniform(0, math.pi)
            L = dash_len * rng.uniform(0.6, 1.0) * (0.6 + 0.4 * d)
            jx = cx + rng.uniform(-cell, cell) * 0.45
            jy = cy + rng.uniform(-cell, cell) * 0.45
            dx = math.cos(ang) * L / 2
            dy = math.sin(ang) * L / 2
            p0 = (_clamp(jx - dx, x0, x1), _clamp(jy - dy, y0, y1))
            p1 = (_clamp(jx + dx, x0, x1), _clamp(jy + dy, y0, y1))
            color = min(colors - 1, int((1.0 - d) * colors)) if colors > 1 else None
            out += _poly([p0, p1], color=color, f=feed)
            placed += 1
    return out


# ---------------------------------------------------------------------------
# 24. comic panels  (seeded comic-page layout, each panel a different generator)
# ---------------------------------------------------------------------------

# Default panel pool: vortex + topographies (override with the `subs` param).
_PANEL_SUBS = [
    "vortex_field",
    "contour_field",
]


def _panel_fill(name: str, rng: SeededRNG, b: Bounds, colors: int) -> List[GCodeCommand]:
    """Run a sub-generator with panel-scaled parameters."""
    x0, y0, x1, y1 = b
    w, h = x1 - x0, y1 - y0
    m = min(w, h)
    if name == "vortex_field":
        return vortex_field(
            rng, b, colors, line_count=max(10, int(h / 2.0)), vortices=1, swirl=150, step=1.0
        )
    if name == "contour_field":
        return contour_field(
            rng,
            b,
            colors,
            levels=max(8, int(m / 7)),
            cell=max(1.8, m / 45),
            field=rng.choice(["noise", "blobs"]),
        )
    if name == "domain_warp":
        return domain_warp(
            rng, b, colors, line_count=max(8, int(h / 2.2)), warp_amp=min(8.0, h * 0.15), step=1.0
        )
    if name == "wave_gradient":
        return wave_gradient(
            rng, b, colors, rows=max(8, int(h / 2.5)), amp_max=min(8.0, h * 0.2), step=1.0
        )
    if name == "interference_field":
        return interference_field(
            rng,
            b,
            colors,
            line_count=max(8, int(h / 2.2)),
            sources=2,
            wavelength=8,
            amp=min(4.0, h * 0.08),
            step=1.0,
        )
    if name == "tiled_field":
        return tiled_field(rng, b, colors, cell=max(6.0, m / 5), line_spacing=1.8)
    if name == "truchet":
        return truchet(rng, b, colors, cell=max(7.0, m / 5))
    if name == "hitomezashi":
        return hitomezashi(rng, b, colors, spacing=max(3.5, m / 10))
    if name == "waves_with_circles":
        return waves_with_circles(rng, b, colors, rings=max(6, int(m / 6)), samples=120)
    if name == "superformula_bloom":
        return superformula_bloom(rng, b, colors, shells=max(8, int(m / 4)), points=140)
    return []


def comic_panels(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 1,
    rows: int = 0,
    gutter: float = 4.0,
    inset: float = 2.5,
    border: bool = True,
    subs: str = "",
    feed: int = 1500,
) -> List[GCodeCommand]:
    """A comic-book page: seeded panel layout, each panel a different generator.

    Max 3 panels (templates: full-width + two, two + full-width, three stacked,
    or three across), seeded sizes with ``gutter`` mm between, each framed and
    filled by a panel-scaled sub-generator with its own derived seed. Default
    pool is vortex + topographic contours; ``subs`` overrides it
    (comma-separated generator names).
    """
    x0, y0, x1, y1 = bounds
    W, H = x1 - x0, y1 - y0
    pool = [s.strip() for s in subs.split(",") if s.strip()] or list(_PANEL_SUBS)

    # 3-panel-max layouts: panels per row, top row first.
    templates = [[1, 2], [2, 1], [1, 1, 1], [3]]
    if rows > 0:
        matching = [t for t in templates if len(t) == rows]
        layout = rng.choice(matching) if matching else templates[0]
    else:
        layout = rng.choice(templates)
    n_rows = len(layout)
    weights = [rng.uniform(0.75, 1.4) for _ in range(n_rows)]
    tw = sum(weights)
    row_h = [(H - (n_rows - 1) * gutter) * wgt / tw for wgt in weights]

    out: List[GCodeCommand] = []
    bag: List[str] = []
    cy = y1  # comics read top-down: first row at the top
    for rj in range(n_rows):
        h = row_h[rj]
        cy -= h
        n_cols = layout[rj]
        cweights = [rng.uniform(0.75, 1.4) for _ in range(n_cols)]
        ctw = sum(cweights)
        col_w = [(W - (n_cols - 1) * gutter) * wgt / ctw for wgt in cweights]
        cx = x0
        for ci in range(n_cols):
            w = col_w[ci]
            px0, py0, px1, py1 = cx, cy, cx + w, cy + h
            if border:
                out += _poly(
                    [(px0, py0), (px1, py0), (px1, py1), (px0, py1), (px0, py0)],
                    color=0 if colors > 1 else None,
                    f=feed,
                )
            if not bag:
                bag = list(pool)
                rng.shuffle(bag)
            name = bag.pop()
            sub_rng = SeededRNG(rng.randint(0, 2**31 - 1))
            fill_bounds = (px0 + inset, py0 + inset, px1 - inset, py1 - inset)
            if fill_bounds[2] - fill_bounds[0] > 8 and fill_bounds[3] - fill_bounds[1] > 8:
                out += _panel_fill(name, sub_rng, fill_bounds, colors)
            cx += w + gutter
        cy -= gutter
    return out


# ---------------------------------------------------------------------------
# image-tone helper (shared by the picture-based generators)
# ---------------------------------------------------------------------------


def _image_tone_grid(rng: SeededRNG, bounds: Bounds, image: str, cell: float, invert: bool):
    """Return (gw, gh, off_x, off_y, tone(i, j)) — image fitted to bounds, or a
    procedural fbm field when no image is given (standalone demo mode)."""
    x0, y0, x1, y1 = bounds
    bw, bh = x1 - x0, y1 - y0
    if image:
        try:
            from PIL import Image
        except ImportError:
            raise RuntimeError("Pillow required for image input: pip install -e '.[vision]'")
        img = Image.open(image).convert("L")
        iw, ih = img.size
        s = min(bw / iw, bh / ih)
        gw = max(2, int(iw * s / cell))
        gh = max(2, int(ih * s / cell))
        small = img.resize((gw, gh))
        px = small.load()
        off_x = x0 + (bw - gw * cell) / 2.0
        off_y = y0 + (bh - gh * cell) / 2.0

        def tone(i, j):
            v = px[i, gh - 1 - j] / 255.0  # flip: image y grows downward
            return v if invert else 1.0 - v

        return gw, gh, off_x, off_y, tone

    gw = max(2, int(bw / cell))
    gh = max(2, int(bh / cell))

    def tone(i, j):
        return rng.fbm(i * 0.06, j * 0.06, octaves=4)

    return gw, gh, x0, y0, tone


# ---------------------------------------------------------------------------
# 25. line halftone  (image as vertical line-screen: dark=solid, light=gap)
# ---------------------------------------------------------------------------


def line_halftone(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 1,
    image: str = "",
    pitch: float = 1.6,
    seg: float = 1.8,
    gamma: float = 1.3,
    threshold: float = 0.08,
    direction: str = "v",
    invert: bool = False,
    feed: int = 1800,
) -> List[GCodeCommand]:
    """Image rendered as a vertical (or horizontal) line screen.

    Parallel lines at ``pitch`` mm; along each line, dark tones draw solid runs,
    midtones break into dashes (duty cycle ∝ darkness), highlights stay blank —
    the classic line-screen photo look (forest-print style). Without ``image``
    a procedural field is used. Tonal bands map to pens (darkest → pen 0).
    """
    x0, y0, x1, y1 = bounds
    gw, gh, off_x, off_y, tone = _image_tone_grid(rng, bounds, image, pitch, invert)

    vertical = direction != "h"
    out: List[GCodeCommand] = []
    n_lines = gw if vertical else gh
    n_steps = gh if vertical else gw
    for li in range(n_lines):
        run_start = None
        run_d = 0.0

        def flush(end_pos):
            nonlocal run_start, run_d
            if run_start is None:
                return
            a, b = run_start, end_pos
            if b - a > 0.3:
                d = run_d
                color = min(colors - 1, int((1.0 - d) * colors)) if colors > 1 else None
                if vertical:
                    xpos = off_x + (li + 0.5) * pitch
                    out.extend(_poly([(xpos, a), (xpos, b)], color=color, f=feed))
                else:
                    ypos = off_y + (li + 0.5) * pitch
                    out.extend(_poly([(a, ypos), (b, ypos)], color=color, f=feed))
            run_start = None
            run_d = 0.0

        for si in range(n_steps):
            i, j = (li, si) if vertical else (si, li)
            d = max(0.0, min(1.0, tone(i, j))) ** gamma
            pos0 = (off_y if vertical else off_x) + si * seg * (1.0 if seg else 1.0)
            pos0 = (off_y + si * seg) if vertical else (off_x + si * seg)
            hi_lim = y1 if vertical else x1
            if pos0 > hi_lim:
                break
            if d < threshold:
                flush(pos0)
                continue
            duty = min(1.0, d * 1.25)
            if run_start is None:
                run_start = pos0 + seg * (1.0 - duty) / 2.0
                run_d = d
            run_d = max(run_d, d)
            seg_end = min(pos0 + seg * (0.5 + duty / 2.0), hi_lim)
            if duty < 0.92:
                flush(seg_end)
        flush(hi_lim)
    return out


# ---------------------------------------------------------------------------
# 26. scribble portrait  (continuous looping scribble, density from the image)
# ---------------------------------------------------------------------------


def scribble_portrait(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 1,
    image: str = "",
    cell: float = 2.8,
    passes: float = 2.0,
    radius: int = 4,
    gamma: float = 1.5,
    threshold: float = 0.12,
    smooth: int = 2,
    max_points: int = 9000,
    invert: bool = False,
    feed: int = 1800,
) -> List[GCodeCommand]:
    """Continuous looping scribble whose density follows image darkness.

    A wandering path hops between nearby dark cells (each cell has an ink budget
    ∝ darkness), then gets corner-cut smoothing — the hand-scribbled portrait
    look. With multiple pens, tonal bands are scribbled dark-first (pen 0 =
    darkest). Without ``image`` a procedural field is used.
    """
    x0, y0, x1, y1 = bounds
    gw, gh, off_x, off_y, tone = _image_tone_grid(rng, bounds, image, cell, invert)

    caps = {}
    band_of = {}
    n_bands = max(1, colors)
    for j in range(gh):
        for i in range(gw):
            d = max(0.0, min(1.0, tone(i, j))) ** gamma
            if d < threshold:
                continue
            caps[(i, j)] = max(1, round(d * passes))
            band_of[(i, j)] = min(n_bands - 1, int((1.0 - d) * n_bands))

    def chaikin(pts):
        for _ in range(max(0, smooth)):
            if len(pts) < 3:
                return pts
            nxt = [pts[0]]
            for a, b in zip(pts, pts[1:]):
                nxt.append((a[0] * 0.75 + b[0] * 0.25, a[1] * 0.75 + b[1] * 0.25))
                nxt.append((a[0] * 0.25 + b[0] * 0.75, a[1] * 0.25 + b[1] * 0.75))
            nxt.append(pts[-1])
            pts = nxt
        return pts

    def mm(c):
        i, j = c
        jx = rng.uniform(-0.35, 0.35) * cell
        jy = rng.uniform(-0.35, 0.35) * cell
        return (
            _clamp(off_x + (i + 0.5) * cell + jx, x0, x1),
            _clamp(off_y + (j + 0.5) * cell + jy, y0, y1),
        )

    out: List[GCodeCommand] = []
    total_pts = 0
    for band in range(n_bands):
        cells = [c for c, b in band_of.items() if b == band and caps.get(c, 0) > 0]
        while cells and total_pts < max_points:
            cells = [c for c in cells if caps.get(c, 0) > 0]
            if not cells:
                break
            cur = rng.choice(cells)
            caps[cur] -= 1
            path = [cur]
            for _ in range(320):
                ci, cj = cur
                cand = []
                wts = []
                for dj in range(-radius, radius + 1):
                    for di in range(-radius, radius + 1):
                        c = (ci + di, cj + dj)
                        cap = caps.get(c, 0)
                        if cap > 0 and c != cur:
                            cand.append(c)
                            wts.append(cap / (1.0 + abs(di) + abs(dj)))
                if not cand:
                    break
                cur = rng.choices(cand, weights=wts, k=1)[0]
                caps[cur] -= 1
                path.append(cur)
            if len(path) >= 3:
                pts = chaikin([mm(c) for c in path])
                total_pts += len(pts)
                out += _poly(pts, color=band if colors > 1 else None, f=feed)
    return out


# ---------------------------------------------------------------------------
# 27. sparkle grid  (mid-century atomic stars with long spurs, nested pens)
# ---------------------------------------------------------------------------


def sparkle_grid(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 1,
    cell: float = 32.0,
    fill: float = 0.8,
    shells: int = 4,
    spur_frac: float = 1.7,
    points: int = 72,
    feed: int = 1500,
) -> List[GCodeCommand]:
    """Four-pointed 'atomic sparkle' stars on a jittered grid with long spurs.

    Each star is a stack of nested astroid outlines (x=a·cos³t, y=b·sin³t) with
    seeded size/elongation, plus long horizontal/vertical spur lines reaching
    toward neighbours. With multiple pens, outer shells take pen 0 and inner
    shells the later pens (navy→red→yellow in the reference).
    """
    x0, y0, x1, y1 = bounds
    cols = max(1, int((x1 - x0) / cell))
    rws = max(1, int((y1 - y0) / cell))
    ox = x0 + ((x1 - x0) - cols * cell) / 2.0
    oy = y0 + ((y1 - y0) - rws * cell) / 2.0

    out: List[GCodeCommand] = []
    for rj in range(rws):
        for ci in range(cols):
            if rng.random() > fill:
                continue
            cx = ox + (ci + 0.5) * cell + rng.uniform(-0.15, 0.15) * cell
            cy = oy + (rj + 0.5) * cell + rng.uniform(-0.15, 0.15) * cell
            a = cell * rng.uniform(0.32, 0.62)
            b = a * rng.uniform(0.8, 1.25)
            n_sh = rng.randint(2, max(2, shells))
            for sh in range(n_sh):
                s = 1.0 - sh * (0.72 / n_sh)
                pts = []
                for k in range(points + 1):
                    t = 2 * math.pi * k / points
                    pts.append(
                        (
                            _clamp(cx + a * s * math.cos(t) ** 3, x0, x1),
                            _clamp(cy + b * s * math.sin(t) ** 3, y0, y1),
                        )
                    )
                color = (sh * colors) // n_sh if colors > 1 else None
                out += _poly(pts, color=color, f=feed)
            # long axis spurs (pen 0), sometimes reaching the neighbour cell
            for dx, dy, arm in ((1, 0, a), (-1, 0, a), (0, 1, b), (0, -1, b)):
                if rng.random() < 0.75:
                    L = arm * spur_frac * rng.uniform(0.5, 1.5)
                    p0 = (_clamp(cx + dx * arm * 0.9, x0, x1), _clamp(cy + dy * arm * 0.9, y0, y1))
                    p1 = (
                        _clamp(cx + dx * (arm * 0.9 + L), x0, x1),
                        _clamp(cy + dy * (arm * 0.9 + L), y0, y1),
                    )
                    out += _poly([p0, p1], color=0 if colors > 1 else None, f=feed)
    return out
