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


def _limit_overdraw(pts, cell: float = 1.4, max_hits: int = 4):
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
    overdraw: int = 4,
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
    # --- ported from the formCollapse catalog (docs/attractors.md params). ---
    # burke_shaw / finance / three_scroll / qi use the corrected classical
    # dynamics (the catalog variants diverge numerically); anishchenko, arnold,
    # chen_celikovsky, rayleigh_benard, tsucs1, liu_chen and the discrete maps
    # are omitted — degenerate or divergent in every probed form.
    "rabinovich_fabrikant": (
        lambda x, y, z: (
            y * (z - 1 + x * x) + 0.10 * x,
            x * (3 * z + 1 - x * x) + 0.10 * y,
            -2 * z * (0.14 + x * y),
        ),
        0.01,
        (-1.0, 0.0, 0.5),
        1000,
    ),
    "chen": (
        lambda x, y, z: (35 * (y - x), (28 - 35) * x - x * z + 28 * y, x * y - 3 * z),
        0.002,
        (-0.1, 0.5, -0.6),
        1000,
    ),
    "newton_leipnik": (
        lambda x, y, z: (
            -0.4 * x + y + 10 * y * z,
            -x - 0.4 * y + 5 * x * z,
            0.175 * z - 5 * x * y,
        ),
        0.01,
        (0.349, 0.0, -0.16),
        1000,
    ),
    "burke_shaw": (
        lambda x, y, z: (-10 * (x + y), -y - 10 * x * z, 10 * x * y + 4.272),
        0.003,
        (1.0, 0.0, 0.0),
        800,
    ),
    "finance": (
        lambda x, y, z: (z + (y - 0.001) * x, 1 - 0.2 * y - x * x, -x - 1.1 * z),
        0.01,
        (1.0, 2.0, -0.5),
        800,
    ),
    "three_scroll": (
        lambda x, y, z: (
            40 * (y - x) + 0.16 * x * z,
            55 * x - x * z + 20 * y,
            1.833 * z + x * y - 0.65 * x * x,
        ),
        0.0008,
        (0.1, 1.0, 0.1),
        1200,
    ),
    "qi": (
        lambda x, y, z: (38 * (y - x) + y * z, 80 * x + y - x * z, x * y - 2.666 * z),
        0.001,
        (3.0, 2.0, 20.0),
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
    overdraw: int = 4,
    feed: int = 1800,
) -> List[GCodeCommand]:
    """A strange attractor traced as one continuous line (controlled chaos).

    Systems ported from the formCollapse catalog: ``lorenz``, ``rossler``,
    ``halvorsen``, ``aizawa``, ``rabinovich_fabrikant``, ``chen``,
    ``newton_leipnik``, ``burke_shaw``, ``finance``, ``three_scroll``, ``qi``.
    RK4-integrated; the seed jitters the initial
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
    threshold: float = 0.12,
    max_strokes: int = 14000,
    invert: bool = False,
    shape_aware: bool = True,
    cross_threshold: float = 0.66,
    channels: str = "mono",
    _channel: str = "",
    _pen: int = -1,
    feed: int = 1800,
) -> List[GCodeCommand]:
    """Render an image as a field of short hatching dashes (hatching portrait).

    Darkness drives density; with ``shape_aware`` (default) each dash's
    DIRECTION follows the image: along the local contour tangent where the
    structure tensor is coherent (edges, brows, lids), blending into a seeded
    smooth noise field in flat tone — the drawing behaves like a field shaped
    by the picture. Dash length grows with coherence (long strokes along
    edges, short ticks in flat shade). Cells darker than ``cross_threshold``
    get a second family of dashes rotated 60–90° (cross-hatched shadows).
    Without ``image`` a procedural fbm field is used. Tonal bands map to pens
    (darkest band → pen 0). Requires Pillow for image input.
    """
    if channels == "cmyk" and image and not _channel:
        outc: List[GCodeCommand] = []
        for pen_i, ch in enumerate("cmyk"):
            outc += scribble_halftone(
                rng,
                bounds,
                colors=1,
                image=image,
                cell=cell,
                max_per_cell=max_per_cell,
                dash_len=dash_len,
                gamma=gamma,
                threshold=threshold,
                max_strokes=max_strokes // 4,
                invert=invert,
                shape_aware=shape_aware,
                cross_threshold=cross_threshold,
                channels="mono",
                _channel=ch,
                _pen=pen_i,
                feed=feed,
            )
        return outc

    x0, y0, x1, y1 = bounds
    gw, gh, off_x, off_y, tone = _image_tone_grid(
        rng, bounds, image, cell, invert, channel=_channel
    )
    if shape_aware:
        tangent, coherence = _image_orientation_grid(gw, gh, tone)

    # first pass: demand so we can thin uniformly to max_strokes
    demand = []
    total = 0
    for j in range(gh):
        for i in range(gw):
            d = max(0.0, min(1.0, tone(i, j))) ** gamma
            if d < threshold:
                continue
            n = max(1, round(d * max_per_cell))
            n_cross = round(d * max_per_cell * 0.7) if d > cross_threshold else 0
            demand.append((i, j, d, n, n_cross))
            total += n + n_cross
    keep = min(1.0, max_strokes / total) if total else 0.0

    def _angle(i, j):
        if not shape_aware:
            return rng.uniform(0, math.pi)
        th_t = tangent(i, j)
        c = coherence(i, j) ** 0.7
        th_n = rng.fbm(i * 0.05, j * 0.05, octaves=3) * math.pi
        # blend orientations on the doubled-angle circle (they are mod pi)
        vx = c * math.cos(2 * th_t) + (1 - c) * math.cos(2 * th_n)
        vy = c * math.sin(2 * th_t) + (1 - c) * math.sin(2 * th_n)
        return 0.5 * math.atan2(vy, vx) + rng.uniform(-0.14, 0.14)

    out: List[GCodeCommand] = []
    for i, j, d, n, n_cross in demand:
        cx = off_x + (i + 0.5) * cell
        cy = off_y + (j + 0.5) * cell
        c = coherence(i, j) if shape_aware else 0.5
        for pass_kind in range(2):
            count = n if pass_kind == 0 else n_cross
            for _ in range(count):
                if keep < 1.0 and rng.random() > keep:
                    continue
                ang = _angle(i, j)
                if pass_kind == 1:  # cross-hatch family in dark cells
                    ang += math.radians(rng.uniform(60.0, 90.0))
                L = dash_len * (0.55 + 0.75 * c) * rng.uniform(0.65, 1.0) * (0.6 + 0.4 * d)
                jx = cx + rng.uniform(-cell, cell) * 0.45
                jy = cy + rng.uniform(-cell, cell) * 0.45
                dx = math.cos(ang) * L / 2
                dy = math.sin(ang) * L / 2
                p0 = (_clamp(jx - dx, x0, x1), _clamp(jy - dy, y0, y1))
                p1 = (_clamp(jx + dx, x0, x1), _clamp(jy + dy, y0, y1))
                if _pen >= 0:
                    color = _pen
                else:
                    color = min(colors - 1, int((1.0 - d) * colors)) if colors > 1 else None
                out += _poly([p0, p1], color=color, f=feed)
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


def _image_tone_grid(
    rng: SeededRNG,
    bounds: Bounds,
    image: str,
    cell: float,
    invert: bool,
    auto_levels: bool = True,
    channel: str = "",
):
    """Return (gw, gh, off_x, off_y, tone(i, j)) — image fitted to bounds, or a
    procedural fbm field when no image is given (standalone demo mode).

    ``auto_levels`` stretches tones to the 5th–95th percentile of the sampled
    grid, so washed-out photos still produce blank highlights and solid darks.
    """
    x0, y0, x1, y1 = bounds
    bw, bh = x1 - x0, y1 - y0
    if image:
        try:
            from PIL import Image
        except ImportError:
            raise RuntimeError("Pillow required for image input: pip install -e '.[vision]'")
        img = Image.open(image).convert("RGB")
        iw, ih = img.size
        # auto-rotate: align the image's long side with the paper's long side
        if (iw >= ih) != (bw >= bh):
            img = img.transpose(Image.ROTATE_90)
            iw, ih = ih, iw
        # cover-fit: fill the WHOLE drawable area (max scale), center-cropping
        # the overflow so the drawing uses every mm inside the margins
        sc = max(bw / iw, bh / ih)
        crop_w = min(iw, bw / sc)
        crop_h = min(ih, bh / sc)
        left = (iw - crop_w) / 2.0
        top = (ih - crop_h) / 2.0
        img = img.crop((int(left), int(top), int(left + crop_w), int(top + crop_h)))
        gw = max(2, int(bw / cell))
        gh = max(2, int(bh / cell))
        small = img.resize((gw, gh))
        px = small.load()
        off_x = x0
        off_y = y0

        def _val(i, j):
            r8, g8, b8 = px[i, gh - 1 - j]  # flip: image y grows downward
            rv, gv, bv = r8 / 255.0, g8 / 255.0, b8 / 255.0
            if channel:
                kv = 1.0 - max(rv, gv, bv)
                if channel == "k":
                    return kv
                if channel == "c":
                    return max(0.0, (1.0 - rv) - kv)
                if channel == "m":
                    return max(0.0, (1.0 - gv) - kv)
                return max(0.0, (1.0 - bv) - kv)  # 'y'
            lum = 0.299 * rv + 0.587 * gv + 0.114 * bv
            return lum if invert else 1.0 - lum

        T = [[_val(i, j) for i in range(gw)] for j in range(gh)]
    else:
        gw = max(2, int(bw / cell))
        gh = max(2, int(bh / cell))
        off_x, off_y = x0, y0
        T = [[rng.fbm(i * 0.06, j * 0.06, octaves=4) for i in range(gw)] for j in range(gh)]

    if auto_levels:
        flat = sorted(v for row in T for v in row)
        p5 = flat[int(0.05 * (len(flat) - 1))]
        p95 = flat[int(0.95 * (len(flat) - 1))]
        if p95 - p5 >= 0.05:  # skip near-empty channels (don't amplify noise)
            span = p95 - p5
            T = [[min(1.0, max(0.0, (v - p5) / span)) for v in row] for row in T]

    def tone(i, j):
        return T[j][i]

    return gw, gh, off_x, off_y, tone


def _image_orientation_grid(gw: int, gh: int, tone):
    """Per-cell contour direction + coherence from the tone grid.

    Sobel gradients, then a 3×3-smoothed structure tensor:
    ``theta = 0.5*atan2(2*Jxy, Jxx - Jyy)`` is the dominant gradient direction;
    the contour tangent is theta + 90°. Coherence in [0,1] says how organized
    the local structure is (1 = strong edge, 0 = flat tone).
    Returns (tangent(i, j) -> radians, coherence(i, j) -> 0..1).
    """

    def t(i, j):
        return tone(min(gw - 1, max(0, i)), min(gh - 1, max(0, j)))

    gx = [[0.0] * gw for _ in range(gh)]
    gy = [[0.0] * gw for _ in range(gh)]
    for j in range(gh):
        for i in range(gw):
            gx[j][i] = (
                t(i + 1, j - 1)
                + 2 * t(i + 1, j)
                + t(i + 1, j + 1)
                - t(i - 1, j - 1)
                - 2 * t(i - 1, j)
                - t(i - 1, j + 1)
            ) / 8.0
            gy[j][i] = (
                t(i - 1, j + 1)
                + 2 * t(i, j + 1)
                + t(i + 1, j + 1)
                - t(i - 1, j - 1)
                - 2 * t(i, j - 1)
                - t(i + 1, j - 1)
            ) / 8.0

    def tensors(i, j):
        jxx = jyy = jxy = 0.0
        for dj in (-1, 0, 1):
            for di in (-1, 0, 1):
                ii = min(gw - 1, max(0, i + di))
                jj = min(gh - 1, max(0, j + dj))
                a, b = gx[jj][ii], gy[jj][ii]
                jxx += a * a
                jyy += b * b
                jxy += a * b
        return jxx, jyy, jxy

    def tangent(i, j):
        jxx, jyy, jxy = tensors(i, j)
        theta = 0.5 * math.atan2(2 * jxy, jxx - jyy)  # gradient direction
        return theta + math.pi / 2  # contour tangent

    def coherence(i, j):
        jxx, jyy, jxy = tensors(i, j)
        tr = jxx + jyy
        if tr < 1e-9:
            return 0.0
        return min(1.0, math.sqrt((jxx - jyy) ** 2 + 4 * jxy * jxy) / tr)

    return tangent, coherence


# ---------------------------------------------------------------------------
# 25. line halftone  (image as vertical line-screen: dark=solid, light=gap)
# ---------------------------------------------------------------------------


def line_halftone(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 1,
    image: str = "",
    pitch: float = 1.6,
    gamma: float = 1.3,
    threshold: float = 0.10,
    direction: str = "v",
    invert: bool = False,
    width_gap: float = 0.45,
    width2_threshold: float = 0.62,
    width3_threshold: float = 0.88,
    channels: str = "mono",
    _channel: str = "",
    _pen: int = -1,
    feed: int = 1800,
) -> List[GCodeCommand]:
    """Image rendered as a vertical (or horizontal) line screen.

    Parallel lines at ``pitch`` mm sampled on a square pitch grid: dark tones
    draw solid runs, midtones break into dashes (duty ∝ darkness), highlights
    stay blank. Dark runs get pen-width play: ≥``width2_threshold`` draws a
    doubled parallel pass (±``width_gap``/2), ≥``width3_threshold`` a tripled
    one — thick where the image is dark, hairline where light. Tonal bands map
    to pens (darkest → pen 0). Without ``image`` a procedural field is used.
    """
    if channels == "cmyk" and image and not _channel:
        outc: List[GCodeCommand] = []
        for pen_i, ch in enumerate("cmyk"):
            outc += line_halftone(
                rng,
                bounds,
                colors=1,
                image=image,
                pitch=pitch,
                gamma=gamma,
                threshold=threshold,
                direction=direction,
                invert=invert,
                width_gap=width_gap,
                width2_threshold=width2_threshold,
                width3_threshold=width3_threshold,
                channels="mono",
                _channel=ch,
                _pen=pen_i,
                feed=feed,
            )
        return outc

    x0, y0, x1, y1 = bounds
    gw, gh, off_x, off_y, tone = _image_tone_grid(
        rng, bounds, image, pitch, invert, channel=_channel
    )

    vertical = direction != "h"
    n_lines = gw if vertical else gh
    n_steps = gh if vertical else gw
    region_end = (off_y + gh * pitch) if vertical else (off_x + gw * pitch)

    out: List[GCodeCommand] = []
    for li in range(n_lines):
        line_pos = (off_x + (li + 0.5) * pitch) if vertical else (off_y + (li + 0.5) * pitch)
        run: list = []  # [start, end, max_d] of the open run

        def emit():
            if not run:
                return
            a, b, d = run[0], run[1], run[2]
            run.clear()
            if b - a < 0.3:
                return
            if _pen >= 0:
                color = _pen
            else:
                color = min(colors - 1, int((1.0 - d) * colors)) if colors > 1 else None
            if d >= width3_threshold:
                offs = (-width_gap, 0.0, width_gap)
            elif d >= width2_threshold:
                offs = (-width_gap / 2, width_gap / 2)
            else:
                offs = (0.0,)
            for o in offs:
                if vertical:
                    xp = _clamp(line_pos + o, x0, x1)
                    out.extend(_poly([(xp, a), (xp, b)], color=color, f=feed))
                else:
                    yp = _clamp(line_pos + o, y0, y1)
                    out.extend(_poly([(a, yp), (b, yp)], color=color, f=feed))

        for sj in range(n_steps):
            i, j = (li, sj) if vertical else (sj, li)
            d = max(0.0, min(1.0, tone(i, j))) ** gamma
            cell_a = (off_y if vertical else off_x) + sj * pitch
            if d < threshold:
                emit()
                continue
            duty = min(1.0, d * 1.25)
            a = cell_a + pitch * (1.0 - duty) / 2.0
            b = min(cell_a + pitch * (0.5 + duty / 2.0), region_end)
            if run:
                run[1] = b
                run[2] = max(run[2], d)
            else:
                run[:] = [a, b, d]
            if duty < 0.92:
                emit()
        emit()
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
    passes: float = 3.0,
    radius: int = 2,
    gamma: float = 2.0,
    threshold: float = 0.30,
    contrast: float = 1.0,
    smooth: int = 2,
    max_points: int = 9000,
    invert: bool = False,
    channels: str = "mono",
    _channel: str = "",
    _pen: int = -1,
    feed: int = 1800,
) -> List[GCodeCommand]:
    """Continuous looping scribble whose density follows image darkness.

    Highlights stay BLANK paper: cells below ``threshold`` get no ink at all;
    capacity rises steeply with darkness (``d**1.8 * passes``), and the walk is
    short-ranged (``radius`` cells) with cap²-weighted steps so the path hugs
    dark regions instead of wandering — the hand-scribbled portrait look. With
    multiple pens, tonal bands are scribbled dark-first (pen 0 = darkest).
    ``contrast`` multiplies the auto-leveled tone before gamma.
    """
    if channels == "cmyk" and image and not _channel:
        outc: List[GCodeCommand] = []
        for pen_i, ch in enumerate("cmyk"):
            outc += scribble_portrait(
                rng,
                bounds,
                colors=1,
                image=image,
                cell=cell,
                passes=passes,
                radius=radius,
                gamma=gamma,
                threshold=threshold,
                contrast=contrast,
                smooth=smooth,
                max_points=max_points // 4,
                invert=invert,
                channels="mono",
                _channel=ch,
                _pen=pen_i,
                feed=feed,
            )
        return outc

    x0, y0, x1, y1 = bounds
    gw, gh, off_x, off_y, tone = _image_tone_grid(
        rng, bounds, image, cell, invert, channel=_channel
    )

    caps = {}
    band_of = {}
    n_bands = max(1, colors)
    for j in range(gh):
        for i in range(gw):
            d = min(1.0, max(0.0, tone(i, j)) * contrast) ** gamma
            if d < threshold:
                continue
            cap = round(d**1.8 * passes)
            if cap < 1:
                continue
            caps[(i, j)] = cap
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
                            wts.append(cap * cap / (1.0 + abs(di) + abs(dj)))
                if not cand:
                    break
                cur = rng.choices(cand, weights=wts, k=1)[0]
                caps[cur] -= 1
                path.append(cur)
            if len(path) >= 3:
                pts = chaikin([mm(c) for c in path])
                total_pts += len(pts)
                color = _pen if _pen >= 0 else (band if colors > 1 else None)
                out += _poly(pts, color=color, f=feed)
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
    jitter: float = 0.0,
    tip_relief: float = 0.03,
    shell_gap: float = 0.26,
    slim: float = 3.6,
    stretch: float = 1.45,
    feed: int = 1500,
) -> List[GCodeCommand]:
    """Four-pointed 'atomic sparkle' stars on a STRICT grid with guarded spurs.

    Stars sit exactly on the lattice (``jitter`` defaults to 0) with sizes
    quantized to {0.35, 0.5, 0.62}·cell, so spur arms from different stars run
    along shared grid lines like the reference. An interval registry per grid
    row/column prevents any two ink segments from overlapping on the same line
    (paper protection): spurs claim only free sub-intervals (1mm safety margin,
    skipped when under 3mm). Inner shells skip the last ``tip_relief`` of the
    approach to each tip so the 4 tips don't pool ink. Outer shells pen 0,
    inner shells later pens. Shells hug the outline (``shell_gap`` apart) and
    arms are slimmed by the ``slim`` exponent for an elegant profile.
    """

    def _sp(v):
        return math.copysign(abs(v) ** slim, v)

    x0, y0, x1, y1 = bounds
    cols = max(1, int((x1 - x0) / cell))
    rws = max(1, int((y1 - y0) / cell))
    ox = x0 + ((x1 - x0) - cols * cell) / 2.0
    oy = y0 + ((y1 - y0) - rws * cell) / 2.0

    # interval registries: ink already placed along each grid row / column
    row_iv: dict = {}
    col_iv: dict = {}

    def _key(v):
        return round(v, 2)

    def _claim(registry, key, lo, hi, margin=1.0, min_len=3.0):
        """Clip [lo,hi] against existing intervals; register and return the
        free sub-interval starting at lo, or None."""
        if hi - lo < min_len:
            return None
        ivs = registry.setdefault(key, [])
        end = hi
        for a, b in ivs:
            if a - margin < lo < b + margin:  # start sits inside existing ink
                return None
            if lo < a:
                end = min(end, a - margin)
        if end - lo < min_len:
            return None
        ivs.append((lo, end))
        return lo, end

    def _register(registry, key, lo, hi):
        registry.setdefault(key, []).append((lo, hi))

    out: List[GCodeCommand] = []
    for rj in range(rws):
        for ci in range(cols):
            if rng.random() > fill:
                continue
            cx = ox + (ci + 0.5) * cell + rng.uniform(-jitter, jitter) * cell
            cy = oy + (rj + 0.5) * cell + rng.uniform(-jitter, jitter) * cell
            a = cell * rng.choice([0.3, 0.42, 0.52])
            b = a * stretch  # elongated, elegant profile
            # reserve the star body extents on its own axes
            _register(row_iv, _key(cy), cx - a, cx + a)
            _register(col_iv, _key(cx), cy - b, cy + b)

            n_sh = rng.randint(2, max(2, shells))
            for sh in range(n_sh):
                sc = 1.0 - sh * shell_gap
                relief = 0.0 if sh == 0 else tip_relief * 2 * math.pi
                if relief <= 0:
                    pts = []
                    for k in range(points + 1):
                        t = 2 * math.pi * k / points
                        pts.append(
                            (
                                _clamp(cx + a * sc * _sp(math.cos(t)), x0, x1),
                                _clamp(cy + b * sc * _sp(math.sin(t)), y0, y1),
                            )
                        )
                    arcs = [pts]
                else:
                    # 4 arcs between tips (tips at t = 0, pi/2, pi, 3pi/2)
                    arcs = []
                    seg_pts = max(8, points // 4)
                    for q in range(4):
                        t0 = q * math.pi / 2 + relief
                        t1 = (q + 1) * math.pi / 2 - relief
                        arc = []
                        for k in range(seg_pts + 1):
                            t = t0 + (t1 - t0) * k / seg_pts
                            arc.append(
                                (
                                    _clamp(cx + a * sc * _sp(math.cos(t)), x0, x1),
                                    _clamp(cy + b * sc * _sp(math.sin(t)), y0, y1),
                                )
                            )
                        arcs.append(arc)
                color = (sh * colors) // n_sh if colors > 1 else None
                for arc in arcs:
                    out += _poly(arc, color=color, f=feed)

            # guarded axis spurs (pen 0) along the shared grid lines
            for dx, dy, arm in ((1, 0, a), (-1, 0, a), (0, 1, b), (0, -1, b)):
                if rng.random() >= 0.75:
                    continue
                L = arm * spur_frac * rng.uniform(0.5, 1.5)
                start = arm * 1.02
                if dx != 0:
                    lo = cx + dx * start if dx > 0 else cx + dx * (start + L)
                    hi = cx + dx * (start + L) if dx > 0 else cx + dx * start
                    got = _claim(row_iv, _key(cy), min(lo, hi), max(lo, hi))
                    if got:
                        p0 = (_clamp(got[0], x0, x1), cy)
                        p1 = (_clamp(got[1], x0, x1), cy)
                        out += _poly([p0, p1], color=0 if colors > 1 else None, f=feed)
                else:
                    lo = cy + dy * start if dy > 0 else cy + dy * (start + L)
                    hi = cy + dy * (start + L) if dy > 0 else cy + dy * start
                    got = _claim(col_iv, _key(cx), min(lo, hi), max(lo, hi))
                    if got:
                        p0 = (cx, _clamp(got[0], y0, y1))
                        p1 = (cx, _clamp(got[1], y0, y1))
                        out += _poly([p0, p1], color=0 if colors > 1 else None, f=feed)
    return out


# ---------------------------------------------------------------------------
# 28. iso city  (axonometric voxel city, gridded faces, hidden lines removed)
# ---------------------------------------------------------------------------


def _convex_hull(points):
    """Monotone-chain convex hull (small point sets)."""
    pts = sorted(set(points))
    if len(pts) <= 2:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower = []
    for pt in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], pt) <= 0:
            lower.pop()
        lower.append(pt)
    upper = []
    for pt in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], pt) <= 0:
            upper.pop()
        upper.append(pt)
    return lower[:-1] + upper[:-1]


def iso_city(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 1,
    cols: int = 12,
    rows: int = 12,
    block: int = 2,
    max_h: int = 12,
    base_max: int = 4,
    tower_prob: float = 0.16,
    ground_frac: float = 0.24,
    noise_scale: float = 0.3,
    terraces: int = 5,
    projection: str = "2pt",
    persp: float = 0.55,
    zoom: float = 1.8,
    height: float = 1.0,
    lod: float = 3.2,
    detail: float = 0.22,
    mask_res: float = 0.4,
    sample_step: float = 0.25,
    min_run: float = 0.7,
    feed: int = 1500,
) -> List[GCodeCommand]:
    """Voxel city with gridded faces, hidden lines removed, in real perspective.

    A seeded heightmap of block towers; every visible face (top + camera-facing
    sides) is drawn as its unit voxel grid. ``projection``: ``2pt`` (default —
    two vanishing points, verticals near-vertical), ``1pt`` (single central
    vanishing point), or ``iso`` (classic 30° axonometric). ``persp`` (0..1)
    controls how aggressive the perspective is. Visibility: front-to-back
    occupancy-mask claiming — nearer columns draw, then claim their silhouettes
    (dilated, which also dedups shared edges); farther lines clip against the
    mask. Height bands map to pens when multiple colors are used.

    ``zoom`` > 1 crops INTO the city (seeded focus point): buildings run off
    every margin so the frame sits inside the scene — immersive, no visible
    object boundary. Columns claim their full projected silhouette (convex
    hull), so blocks are opaque with no see-through inner edges.
    """
    x0, y0, x1, y1 = bounds

    # -- heightmap (fixed loop order for determinism) --
    n = [
        [rng.fbm(i * noise_scale + 7.31, j * noise_scale + 3.17, octaves=3) for j in range(rows)]
        for i in range(cols)
    ]
    lo = min(min(r) for r in n)
    hi = max(max(r) for r in n)
    span = (hi - lo) or 1.0
    H = [[0] * rows for _ in range(cols)]
    for j in range(rows):
        for i in range(cols):
            n01 = (n[i][j] - lo) / span
            if n01 < ground_frac:
                h = 0  # void: streets / plazas
            else:
                # terraced plateaus: large connected masses of equal height
                lvl = 1 + int((n01 - ground_frac) / (1.0 - ground_frac) * (terraces - 1))
                h = max(1, round((lvl / terraces) ** 1.3 * max_h * 0.6))
            if h and rng.random() < tower_prob:
                h = min(max_h, h + rng.randint(max_h // 3, max_h - 1))
            H[i][j] = h
    hmax = max(1, max(max(r) for r in H))

    # -- projector: world (a, c, z) in voxel units -> unfitted screen coords --
    SX, SY, SZ = cols * block, rows * block, float(hmax)
    if projection == "iso":
        KX, KY, KZ = 0.8660254, 0.5, 1.0

        def raw(a, c, z):
            return ((a - c) * KX, (a + c) * KY + z * KZ)

        cam = None
    else:
        az = math.pi / 4 if projection == "2pt" else 0.0
        T = (SX / 2.0, SY / 2.0, SZ * 0.3)
        dist = max(SX, SY) * (2.8 - 1.9 * max(0.0, min(1.0, persp)))
        cam = (
            T[0] + dist * math.sin(az),
            T[1] - dist * math.cos(az),
            SZ * 0.6 + max(SX, SY) * 0.55,
        )
        fx, fy, fz = T[0] - cam[0], T[1] - cam[1], T[2] - cam[2]
        fl = math.sqrt(fx * fx + fy * fy + fz * fz)
        fx, fy, fz = fx / fl, fy / fl, fz / fl
        rx_, ry_, rz_ = fy, -fx, 0.0  # f x up(0,0,1)
        rl = math.hypot(rx_, ry_) or 1.0
        rx_, ry_ = rx_ / rl, ry_ / rl
        ux_ = ry_ * fz - rz_ * fy
        uy_ = rz_ * fx - rx_ * fz
        uz_ = rx_ * fy - ry_ * fx

        def raw(a, c, z):
            dx, dy, dz = a - cam[0], c - cam[1], z - cam[2]
            depth = dx * fx + dy * fy + dz * fz
            return ((dx * rx_ + dy * ry_) / depth, (dx * ux_ + dy * uy_ + dz * uz_) / depth)

    # -- fit raw projection into bounds (uniform scale, centered) --
    samples = []
    for i in range(cols + 1):
        for j in range(rows + 1):
            samples.append(raw(i * block, j * block, 0.0))
    for i in range(cols):
        for j in range(rows):
            a0, c0, h = i * block, j * block, H[i][j]
            if h:
                for da, dc in ((0, 0), (block, 0), (block, block), (0, block)):
                    samples.append(raw(a0 + da, c0 + dc, float(h)))
    sxs = [pt[0] for pt in samples]
    sys_ = [pt[1] for pt in samples]
    sw = (max(sxs) - min(sxs)) or 1.0
    sh = (max(sys_) - min(sys_)) or 1.0
    if zoom > 1.0:
        # COVER-fit: scale so the scene overflows the frame, then pick a seeded
        # focus whose window stays inside the scene on left/right/bottom
        # (the top is allowed to breathe — sky above the towers).
        sc = max((x1 - x0) / sw, (y1 - y0) / sh) * zoom
        half_wx = (x1 - x0) / (2.0 * sc)
        half_wy = (y1 - y0) / (2.0 * sc)
        fx_lo = min(sxs) + half_wx
        fx_hi = max(sxs) - half_wx
        fy_lo = min(sys_) + half_wy
        fy_hi = max(sys_) - half_wy * 0.3  # top may fall short of the scene
        fxr = (
            fx_lo + (fx_hi - fx_lo) * rng.uniform(0.25, 0.75)
            if fx_hi > fx_lo
            else (min(sxs) + max(sxs)) / 2
        )
        fyr = (
            fy_lo + (fy_hi - fy_lo) * rng.uniform(0.15, 0.5)
            if fy_hi > fy_lo
            else (min(sys_) + max(sys_)) / 2
        )
    else:
        sc = 0.96 * min((x1 - x0) / sw, (y1 - y0) / sh)
        fxr = (min(sxs) + max(sxs)) / 2.0
        fyr = (min(sys_) + max(sys_)) / 2.0
    ox = (x0 + x1) / 2.0 - fxr * sc
    oy = (y0 + y1) / 2.0 - fyr * sc

    def P(a, c, z):
        px, py = raw(a, c, z)
        return (ox + px * sc, oy + py * sc)

    # -- occupancy mask --
    q = mask_res
    nxm = int((x1 - x0) / q) + 2
    nym = int((y1 - y0) / q) + 2
    mask = [bytearray(nxm) for _ in range(nym)]

    def free(px, py):
        mj = int((py - y0) / q)
        mi = int((px - x0) / q)
        if mj < 0 or mj >= nym or mi < 0 or mi >= nxm:
            return True
        return mask[mj][mi] == 0

    def claim_convex(pts):
        """Dilated fill of a convex polygon (screen coords)."""
        npts = len(pts)
        area2 = 0.0
        for k in range(npts):
            xA, yA = pts[k]
            xB, yB = pts[(k + 1) % npts]
            area2 += xA * yB - xB * yA
        if abs(area2) < 1e-9:
            return
        if area2 < 0:
            pts = pts[::-1]
        g = 0.6 * q
        edges = []
        for k in range(len(pts)):
            xA, yA = pts[k]
            xB, yB = pts[(k + 1) % len(pts)]
            ex, ey = xB - xA, yB - yA
            el = math.hypot(ex, ey) or 1.0
            edges.append((xA, yA, ex / el, ey / el))
        mi0 = max(0, int((min(pt[0] for pt in pts) - g - x0) / q))
        mi1 = min(nxm - 1, int((max(pt[0] for pt in pts) + g - x0) / q) + 1)
        mj0 = max(0, int((min(pt[1] for pt in pts) - g - y0) / q))
        mj1 = min(nym - 1, int((max(pt[1] for pt in pts) + g - y0) / q) + 1)
        for mj in range(mj0, mj1 + 1):
            py = y0 + (mj + 0.5) * q
            row = mask[mj]
            for mi in range(mi0, mi1 + 1):
                px = x0 + (mi + 0.5) * q
                ok = True
                for xA, yA, tx, ty in edges:
                    # interior of a CCW polygon: cross(edge_dir, p-A) >= 0
                    if tx * (py - yA) - ty * (px - xA) < -g:
                        ok = False
                        break
                if ok:
                    row[mi] = 1

    def clip_rect(A, B):
        """Liang–Barsky clip of segment A→B to the drawable rect (or None)."""
        t0, t1 = 0.0, 1.0
        dx, dy = B[0] - A[0], B[1] - A[1]
        for pcl, qcl in ((-dx, A[0] - x0), (dx, x1 - A[0]), (-dy, A[1] - y0), (dy, y1 - A[1])):
            if pcl == 0:
                if qcl < 0:
                    return None
                continue
            t = qcl / pcl
            if pcl < 0:
                if t > t1:
                    return None
                t0 = max(t0, t)
            else:
                if t < t0:
                    return None
                t1 = min(t1, t)
        return ((A[0] + dx * t0, A[1] + dy * t0), (A[0] + dx * t1, A[1] + dy * t1))

    def clip_emit(A, B, color):
        clipped = clip_rect(A, B)
        if clipped is None:
            return
        A, B = clipped
        L = math.hypot(B[0] - A[0], B[1] - A[1])
        nseg = max(1, int(L / sample_step))
        first = last = None
        for k in range(nseg + 1):
            t = k / nseg
            px = A[0] + (B[0] - A[0]) * t
            py = A[1] + (B[1] - A[1]) * t
            if free(px, py):
                if first is None:
                    first = (px, py)
                last = (px, py)
            else:
                if (
                    first is not None
                    and math.hypot(last[0] - first[0], last[1] - first[1]) >= min_run
                ):
                    out.extend(
                        _poly(
                            [
                                (_clamp(first[0], x0, x1), _clamp(first[1], y0, y1)),
                                (_clamp(last[0], x0, x1), _clamp(last[1], y0, y1)),
                            ],
                            color=color,
                            f=feed,
                        )
                    )
                first = last = None
        if first is not None and math.hypot(last[0] - first[0], last[1] - first[1]) >= min_run:
            out.extend(
                _poly(
                    [
                        (_clamp(first[0], x0, x1), _clamp(first[1], y0, y1)),
                        (_clamp(last[0], x0, x1), _clamp(last[1], y0, y1)),
                    ],
                    color=color,
                    f=feed,
                )
            )

    # -- column ordering: nearest first --
    order = []
    for j in range(rows):
        for i in range(cols):
            a0, c0 = i * block, j * block
            if cam is None:
                key = i + j  # iso: front = small i+j
            else:
                key = (a0 + block / 2 - cam[0]) ** 2 + (c0 + block / 2 - cam[1]) ** 2
            order.append((key, i, j))
    order.sort()

    def face_world(origin, eu, ev, nu, nv, full=True):
        """Grid segments for a face: origin + s·eu + t·ev, s∈[0,nu], t∈[0,nv].

        ``full=False`` keeps only the outline (LOD for small far blocks)."""
        segs = []
        us = range(nu + 1) if full else (0, nu)
        vs = range(nv + 1) if full else (0, nv)
        for k in us:
            segs.append(
                (
                    (origin[0] + eu[0] * k, origin[1] + eu[1] * k, origin[2] + eu[2] * k),
                    (
                        origin[0] + eu[0] * k + ev[0] * nv,
                        origin[1] + eu[1] * k + ev[1] * nv,
                        origin[2] + eu[2] * k + ev[2] * nv,
                    ),
                )
            )
        for k in vs:
            segs.append(
                (
                    (origin[0] + ev[0] * k, origin[1] + ev[1] * k, origin[2] + ev[2] * k),
                    (
                        origin[0] + ev[0] * k + eu[0] * nu,
                        origin[1] + ev[1] * k + eu[1] * nu,
                        origin[2] + ev[2] * k + eu[2] * nu,
                    ),
                )
            )
        return segs

    out: List[GCodeCommand] = []
    for _key, i, j in order:
        h = H[i][j]
        a0, c0 = float(i * block), float(j * block)
        b = float(block)
        col = _color_for(colors, idx=min(colors - 1, (h * colors) // (hmax + 1)))

        faces = []  # (origin, eu, ev, nu, nv) in world units
        faces.append(((a0, c0, float(h)), (1, 0, 0), (0, 1, 0), block, block))  # top
        if h > 0:
            sides = [
                ((a0, c0, 0.0), (0, 1, 0), (0, 0, 1), block, h, (-1.0, 0.0)),  # -i face
                ((a0 + b, c0, 0.0), (0, 1, 0), (0, 0, 1), block, h, (1.0, 0.0)),  # +i
                ((a0, c0, 0.0), (1, 0, 0), (0, 0, 1), block, h, (0.0, -1.0)),  # -j
                ((a0, c0 + b, 0.0), (1, 0, 0), (0, 0, 1), block, h, (0.0, 1.0)),  # +j
            ]
            for origin, eu, ev, nu, nv, normal in sides:
                if cam is None:
                    visible = normal in ((-1.0, 0.0), (0.0, -1.0))
                else:
                    fcx = origin[0] + eu[0] * nu / 2 + ev[0] * nv / 2
                    fcy = origin[1] + eu[1] * nu / 2 + ev[1] * nv / 2
                    visible = (cam[0] - fcx) * normal[0] + (cam[1] - fcy) * normal[1] > 0
                if visible:
                    faces.append((origin, eu, ev, nu, nv))

        # LOD: when a unit cell projects smaller than ``lod`` mm, drop the
        # inner grid — far blocks read as clean boxes instead of mush.
        pa = P(a0, c0, 0.0)
        pb = P(a0 + 1.0, c0, 0.0)
        unit_mm = math.hypot(pb[0] - pa[0], pb[1] - pa[1])
        full = unit_mm >= lod
        for origin, eu, ev, nu, nv in faces:
            for A, Bw in face_world(origin, eu, ev, nu, nv, full=full):
                clip_emit(P(*A), P(*Bw), col)
            # window detail: inset squares on near (full-LOD) side-face cells
            if full and detail > 0 and ev[2] == 1:
                for u in range(nu):
                    for v in range(nv):
                        if rng.random() >= detail:
                            continue
                        wa, wb = 0.3, 0.7
                        cs = []
                        for ua, va in ((wa, wa), (wb, wa), (wb, wb), (wa, wb)):
                            cs.append(
                                (
                                    origin[0] + eu[0] * (u + ua) + ev[0] * (v + va),
                                    origin[1] + eu[1] * (u + ua) + ev[1] * (v + va),
                                    origin[2] + eu[2] * (u + ua) + ev[2] * (v + va),
                                )
                            )
                        for k4 in range(4):
                            clip_emit(P(*cs[k4]), P(*cs[(k4 + 1) % 4]), col)
        # claim the FULL projected silhouette of the prism (opaque blocks):
        # convex hull of all projected corners — no seams, nothing behind
        # ever peeks through inner edges.
        corners = []
        for da in (0.0, b):
            for dc in (0.0, b):
                corners.append(P(a0 + da, c0 + dc, 0.0))
                if h > 0:
                    corners.append(P(a0 + da, c0 + dc, float(h)))
        hull = _convex_hull(corners)
        if len(hull) >= 3:
            claim_convex(hull)
    return out


# ---------------------------------------------------------------------------
# 29. rounded circuits  (guillotine regions filled with concentric rounded insets)
# ---------------------------------------------------------------------------


def rounded_circuits(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 2,
    pitch: float = 2.2,
    band_lines: int = 6,
    detours: int = 2,
    corner_r: float = -1.0,
    feed: int = 1600,
) -> List[GCodeCommand]:
    """ONE closed conveyor belt: a page-filling self-crossing tour, round turns.

    The centerline visits a seeded anchor in every quadrant of the page (plus
    ``detours`` waypoints between anchors), routed axis-aligned with the LONG
    paper direction first — so the belt spans the whole sheet, crosses itself,
    and closes into a single loop. Drawn as ``band_lines`` concentric offsets
    ``pitch`` apart with auto-sized round corners that keep the offset constant
    through every turn. Lines split across pens in bands.
    """
    x0, y0, x1, y1 = bounds
    K = max(2, band_lines)
    half = (K - 1) / 2.0 * pitch

    G = max(2.6 * pitch + 2 * half, (K - 1) * pitch + 2.4 * pitch)
    r_eff = corner_r if corner_r > 0 else 0.42 * G
    m = half + r_eff * 0.2 + 2.0
    gx0, gy0 = x0 + m, y0 + m
    ncx = max(3, int((x1 - x0 - 2 * m) / G))
    ncy = max(3, int((y1 - y0 - 2 * m) / G))
    long_is_y = (y1 - y0) >= (x1 - x0)

    def node(i, j):
        return (gx0 + i * G, gy0 + j * G)

    def make_walk():
        """Closed rectilinear tour through all four page quadrants."""
        third_x = max(1, ncx // 3)
        third_y = max(1, ncy // 3)
        anchors = [
            (rng.randint(0, third_x), rng.randint(0, third_y)),  # bottom-left
            (rng.randint(ncx - third_x, ncx), rng.randint(0, third_y)),  # bottom-right
            (rng.randint(ncx - third_x, ncx), rng.randint(ncy - third_y, ncy)),  # top-right
            (rng.randint(0, third_x), rng.randint(ncy - third_y, ncy)),  # top-left
        ]
        first = rng.randint(0, 3)
        if rng.random() < 0.5:
            anchors = anchors[::-1]
        seq = anchors[first:] + anchors[:first]

        waypoints = []
        for a, bnext in zip(seq, seq[1:] + [seq[0]]):
            waypoints.append(a)
            for _ in range(max(0, detours)):
                if rng.random() < 0.7:
                    waypoints.append((rng.randint(0, ncx), rng.randint(0, ncy)))
        # route axis-aligned, LONG axis first (long legs along the paper)
        cells = [waypoints[0]]
        for tgt in waypoints[1:] + [waypoints[0]]:
            ci, cj = cells[-1]
            ti, tj = tgt
            if long_is_y:
                if cj != tj:
                    cells.append((ci, tj))
                if ci != ti:
                    cells.append((ti, tj))
            else:
                if ci != ti:
                    cells.append((ti, cj))
                if cj != tj:
                    cells.append((ti, tj))
        if cells[-1] == cells[0]:
            cells.pop()

        verts = []
        for nd in cells:
            pt = node(*nd)
            if verts and abs(pt[0] - verts[-1][0]) < 1e-6 and abs(pt[1] - verts[-1][1]) < 1e-6:
                continue
            if len(verts) >= 2:
                ax, ay = verts[-2]
                bx, by = verts[-1]
                if (abs(ax - bx) < 1e-6 and abs(bx - pt[0]) < 1e-6) or (
                    abs(ay - by) < 1e-6 and abs(by - pt[1]) < 1e-6
                ):
                    verts[-1] = pt
                    continue
            verts.append(pt)
        if len(verts) >= 3:
            ax, ay = verts[-1]
            bx, by = verts[0]
            cxp, cyp = verts[1]
            if (abs(ax - bx) < 1e-6 and abs(bx - cxp) < 1e-6) or (
                abs(ay - by) < 1e-6 and abs(by - cyp) < 1e-6
            ):
                verts.pop(0)
        return verts if len(verts) >= 4 else None

    def offset_loop(base, o):
        nv = len(base)
        shifted = []
        for k in range(nv):
            ax, ay = base[k]
            bx, by = base[(k + 1) % nv]
            dx = 0 if abs(bx - ax) < 1e-6 else (1 if bx > ax else -1)
            dy = 0 if abs(by - ay) < 1e-6 else (1 if by > ay else -1)
            if dy == 0:
                shifted.append(("h", ay + o * dx))
            else:
                shifted.append(("v", ax - o * dy))
        out_v = []
        for k in range(nv):
            t_prev, c_prev = shifted[k - 1]
            t_cur, c_cur = shifted[k]
            if t_prev == t_cur:
                return None
            xv = c_prev if t_prev == "v" else c_cur
            yv = c_prev if t_prev == "h" else c_cur
            out_v.append((xv, yv))
        return out_v

    def rounded_loop(base, o):
        nv = len(base)
        pts = []
        for k in range(nv):
            vv = base[k]
            pa = base[k - 1]
            pb = base[(k + 1) % nv]
            d1 = (vv[0] - pa[0], vv[1] - pa[1])
            d2 = (pb[0] - vv[0], pb[1] - vv[1])
            l1 = math.hypot(*d1) or 1.0
            l2 = math.hypot(*d2) or 1.0
            u1 = (d1[0] / l1, d1[1] / l1)
            u2 = (d2[0] / l2, d2[1] / l2)
            turn = u1[0] * u2[1] - u1[1] * u2[0]
            r = r_eff - o if turn > 0 else r_eff + o
            r = max(0.2, min(r, l1 / 2 - 0.05, l2 / 2 - 0.05))
            p_in = (vv[0] - u1[0] * r, vv[1] - u1[1] * r)
            n1 = (-u1[1], u1[0]) if turn > 0 else (u1[1], -u1[0])
            cxa = p_in[0] + n1[0] * r
            cya = p_in[1] + n1[1] * r
            a0 = math.atan2(p_in[1] - cya, p_in[0] - cxa)
            sweep = (math.pi / 2) * (1 if turn > 0 else -1)
            for kk in range(9):
                a = a0 + sweep * kk / 8
                pts.append((cxa + r * math.cos(a), cya + r * math.sin(a)))
        pts.append(pts[0])
        return [(_clamp(px, x0, x1), _clamp(py, y0, y1)) for px, py in pts]

    def emit_band(base):
        band: List[GCodeCommand] = []
        good = 0
        for k in range(K):
            o = (k - (K - 1) / 2.0) * pitch
            ov = offset_loop(base, o)
            if ov is None:
                continue
            good += 1
            color = (k * colors) // K if colors > 1 else None
            band += _poly(rounded_loop(ov, o), color=color, f=feed)
        return band, good

    best: List[GCodeCommand] = []
    best_good = 0
    for _try in range(8):
        verts = make_walk()
        if verts is None:
            continue
        cand, good = emit_band(verts)
        if good > best_good:
            best, best_good = cand, good
        if best_good >= K:
            break
    return best


# ---------------------------------------------------------------------------
# 30. lissajous swarm  (phase-swept Lissajous families -> 3D tube/butterfly)
# ---------------------------------------------------------------------------


def lissajous_swarm(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 2,
    curves: int = 90,
    points: int = 420,
    sweep: float = 3.14159,
    detune: float = 0.04,
    scale_min: float = 0.5,
    thick_frac: float = 0.3,
    thick_gap: float = 0.35,
    feed: int = 1700,
) -> List[GCodeCommand]:
    """A phase-swept family of Lissajous curves — the 'subversion' surface look.

    ``curves`` closed Lissajous figures share the same frequency pair but sweep
    their phase (and slightly detune + grow in scale), so the family reads as a
    sheared 3D tube/butterfly built from line moiré. The whole composition gets
    a seeded rotation. With 2 pens, the first half of the sweep takes pen 0 and
    the second pen 1 (the classic red/black split).
    """
    x0, y0, x1, y1 = bounds
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    A = (x1 - x0) / 2.0 * 0.94
    B = (y1 - y0) / 2.0 * 0.94

    fa = rng.randint(1, 4)
    fb = rng.randint(2, 6)
    if fb == fa:
        fb += 1
    phase0 = rng.uniform(0, 2 * math.pi)
    rot = rng.uniform(0, math.pi)
    cr, sr = math.cos(rot), math.sin(rot)

    out: List[GCodeCommand] = []
    for kc in range(curves):
        f = kc / max(1, curves - 1)
        delta = phase0 + sweep * f
        db = detune * (f - 0.5)
        s = scale_min + (1.0 - scale_min) * f
        pts = []
        for k in range(points + 1):
            t = 2 * math.pi * k / points
            lx = A * s * math.sin(fa * t + delta)
            ly = B * s * math.sin((fb + db) * t)
            px = cx + lx * cr - ly * sr
            py = cy + lx * sr + ly * cr
            pts.append((_clamp(px, x0, x1), _clamp(py, y0, y1)))
        color = (kc * colors) // curves if colors > 1 else None
        out += _poly(pts, color=color, f=feed)
        # nearest-to-camera curves (end of the sweep) read thicker: double pass
        if thick_frac > 0 and f > 1.0 - thick_frac:
            shifted = [
                (_clamp(px + thick_gap, x0, x1), _clamp(py + thick_gap * 0.6, y0, y1))
                for px, py in pts
            ]
            out += _poly(shifted, color=color, f=feed)
    return out


# ---------------------------------------------------------------------------
# 31. black hole  (Luminet 1979 — EXACT elliptic solver, from eventHorizon)
# ---------------------------------------------------------------------------


def _catmull_subdivide(pts, pens=None, subdiv=3):
    """Smooth a polyline with uniform Catmull-Rom subdivision (pens follow points)."""
    n = len(pts)
    if n < 4:
        return pts, pens
    out_p, out_pen = [], []
    for i in range(n - 1):
        p0 = pts[max(i - 1, 0)]
        p1, p2 = pts[i], pts[i + 1]
        p3 = pts[min(i + 2, n - 1)]
        out_p.append(p1)
        if pens is not None:
            out_pen.append(pens[i])
        for k in range(1, subdiv):
            t = k / subdiv
            t2, t3 = t * t, t * t * t
            x = 0.5 * (
                2 * p1[0]
                + (-p0[0] + p2[0]) * t
                + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3
            )
            y = 0.5 * (
                2 * p1[1]
                + (-p0[1] + p2[1]) * t
                + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3
            )
            out_p.append((x, y))
            if pens is not None:
                out_pen.append(pens[i])
    out_p.append(pts[-1])
    if pens is not None:
        out_pen.append(pens[-1])
    return out_p, out_pen


def _carlson_rf(x, y, z):
    """Carlson symmetric elliptic integral R_F (duplication algorithm)."""
    x, y, z = max(0.0, x), max(0.0, y), max(0.0, z)
    for _ in range(80):
        sx, sy, sz = math.sqrt(x), math.sqrt(y), math.sqrt(z)
        lam = sx * sy + sy * sz + sz * sx
        x, y, z = (x + lam) / 4, (y + lam) / 4, (z + lam) / 4
        avg = (x + y + z) / 3
        if avg > 0 and max(abs(x - avg), abs(y - avg), abs(z - avg)) < 1e-10 * avg:
            break
    return 1.0 / math.sqrt(avg)


def _ellip_f(phi, m):
    """Incomplete elliptic integral F(phi | m); m > 1 via reciprocal modulus."""
    if m > 1.0:
        t = math.sqrt(m) * math.sin(phi)
        if abs(t) > 1.0:
            return float("nan")
        return _ellip_f(math.asin(t), 1.0 / m) / math.sqrt(m)
    sph = math.sin(phi)
    return sph * _carlson_rf(math.cos(phi) ** 2, 1.0 - m * sph * sph, 1.0)


def _ellip_k(m):
    if m > 1.0:
        return _ellip_k(1.0 / m) / math.sqrt(m)
    return _ellip_f(math.pi / 2, m)


def _jacobi_sn(u, m):
    """Jacobi sn(u | m) via the AGM; m > 1 via reciprocal modulus."""
    if m < 1e-12:
        return math.sin(u)
    if m > 1.0 + 1e-9:
        sm = math.sqrt(m)
        return _jacobi_sn(sm * u, 1.0 / m) / sm
    if m > 1.0 - 1e-12:
        return math.tanh(u)
    a = [1.0]
    b = [math.sqrt(1.0 - m)]
    c = [math.sqrt(m)]
    while abs(c[-1]) > 1e-12 and len(a) < 30:
        an = (a[-1] + b[-1]) / 2.0
        bn = math.sqrt(a[-1] * b[-1])
        cn = (a[-1] - b[-1]) / 2.0
        a.append(an)
        b.append(bn)
        c.append(cn)
    n = len(a) - 1
    phi = (2.0**n) * a[n] * u
    for k in range(n, 0, -1):
        phi = (phi + math.asin(max(-1.0, min(1.0, c[k] * math.sin(phi) / a[k])))) / 2.0
    return math.sin(phi)


def _luminet_b_table(inclination, n, alphas, radii):
    """Exact impact parameter b(alpha, r) for image order n (Luminet eq. 13).

    Follows the reference implementation (bgmeulem/luminet): the periastron is
    bracketed ONCE over [3M, r] — the objective has a single sign change there —
    and refined by bisection. M = 1. Front-of-disk rays with no periastron fall
    back to Luminet's weak-field ellipse.
    """
    tan_i = math.tan(inclination) or 1e-9

    def objective(P, r, gamma):
        Q = math.sqrt((P - 2.0) * (P + 6.0))
        k2 = (Q - P + 6.0) / (2.0 * Q)
        num = (Q - P + 2.0) / (Q - P + 6.0)
        zeta_inf = math.asin(math.sqrt(max(0.0, min(1.0, num))))
        F_inf = _ellip_f(zeta_inf, k2)
        if not math.isfinite(F_inf):
            return float("nan")
        sq_pq = math.sqrt(P / Q)
        if n == 0:
            u = gamma / (2.0 * sq_pq) + F_inf
        else:
            K_k = _ellip_k(k2)
            if not math.isfinite(K_k):
                return float("nan")
            u = (gamma - 2.0 * n * math.pi) / (2.0 * sq_pq) - F_inf + 2.0 * K_k
        snv = _jacobi_sn(u, k2)
        if not math.isfinite(snv):
            return float("nan")
        r_inv = (1.0 / (4.0 * P)) * (-(Q - P + 2.0) + (Q - P + 6.0) * snv * snv)
        return 1.0 - r * r_inv

    n_half = len(alphas) // 2
    table = {}
    for r in radii:
        for ki in range(n_half + 1):
            alpha = alphas[ki]
            ca = math.cos(alpha)
            gamma = math.acos(ca / math.sqrt(ca * ca + 1.0 / (tan_i * tan_i)))
            # single bracket over [3M, r], like the reference implementation
            loP = 3.001 + n * 1e-5
            hiP = r * (1.0 - 1e-9)
            root_P = None
            if hiP > loP:
                f_lo = objective(loP, r, gamma)
                f_hi = objective(hiP, r, gamma)
                if math.isfinite(f_lo) and math.isfinite(f_hi) and (f_lo < 0) != (f_hi < 0):
                    for _ in range(48):
                        midP = 0.5 * (loP + hiP)
                        f_mid = objective(midP, r, gamma)
                        if not math.isfinite(f_mid):
                            break
                        if (f_lo < 0) == (f_mid < 0):
                            loP, f_lo = midP, f_mid
                        else:
                            hiP = midP
                    else:
                        root_P = 0.5 * (loP + hiP)
            if root_P is not None:
                b = math.sqrt(root_P**3 / (root_P - 2.0))
            elif n == 0 and math.cos(alpha) > 0.0:
                # near side of the disk: the ray has no periastron (it would
                # plunge) — Luminet's weak-field ellipse; this is the part of
                # the disk that passes IN FRONT of the shadow
                b = r / math.sqrt(1.0 + (tan_i**2) * math.cos(alpha) ** 2)
            else:
                b = float("nan")
            table[(alpha, r)] = b
            table[(alphas[len(alphas) - 1 - ki], r)] = b  # mirror symmetry
    return table


def black_hole(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 1,
    inclination: float = -1.0,
    n_iso: int = 16,
    r_min: float = 6.0,
    r_max: float = 30.0,
    samples: int = 120,
    ghost: bool = True,
    mode: str = "lines",
    dots: int = 2400,
    dot_gamma: float = 1.6,
    dot_size: float = 0.22,
    dot_cell: float = 0.55,
    dot_cap: int = 6,
    isco_line: bool = True,
    flow_rings: int = 88,
    dash_mm: float = 2.4,
    flow_gamma: float = 1.35,
    flow_spacing: float = 1.35,
    double_thresh: float = 0.74,
    feed: int = 1600,
) -> List[GCodeCommand]:
    """Luminet-1979 black hole with the EXACT elliptic-integral solver.

    Ported from 007-eventHorizon (Luminet eq. 13 impact parameters, eq. 19
    redshift, Page–Thorne flux): the direct image (n=0) domes over the shadow
    and the TRUE ghost image (n=1) forms the bright lensed ring below — the
    full classic picture. ``mode``: ``lines`` | ``dots`` | ``both``; dots are
    flux-weighted with Doppler boosting. Seed picks inclination (72–85°).
    """
    x0, y0, x1, y1 = bounds
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0

    inc_deg = inclination if inclination > 0 else rng.uniform(72.0, 85.0)
    inc = math.radians(inc_deg)
    sin_i = math.sin(inc)

    if mode == "flow":
        n_rings = max(24, flow_rings)
    else:
        n_rings = max(6, n_iso + rng.randint(-2, 2))
    rings = [r_min * (r_max / r_min) ** (k / max(1, n_rings - 1)) for k in range(n_rings)]
    alphas = [2.0 * math.pi * k / samples for k in range(samples + 1)]

    # r-grid for dot interpolation shares the exact tables with the rings
    dot_rgrid = (
        [6.001 * (r_max / 6.001) ** (k / 31.0) for k in range(32)] if mode != "lines" else []
    )
    all_r = sorted(set(rings) | set(dot_rgrid))
    t_direct = _luminet_b_table(inc, 0, alphas, all_r)
    t_ghost = _luminet_b_table(inc, 1, alphas, all_r) if ghost else {}

    def screen(alpha, b):
        # eventHorizon convention: X = b·cos(alpha - pi/2), Y = b·sin(alpha - pi/2)
        return (b * math.cos(alpha - math.pi / 2), b * math.sin(alpha - math.pi / 2))

    # fill root-finder gaps by circular interpolation over alpha (both tables,
    # every radius) so curves stay continuous and the dot grain has no wedges
    for tbl in (t_direct, t_ghost):
        if not tbl:
            continue
        for r in all_r:
            bs = [tbl.get((alpha, r), float("nan")) for alpha in alphas]
            nb = len(bs)
            if sum(1 for b in bs if math.isfinite(b)) < nb * 0.5:
                continue
            for k in range(nb):
                if math.isfinite(bs[k]):
                    continue
                lo = k
                while not math.isfinite(bs[lo % nb]):
                    lo -= 1
                hi = k
                while not math.isfinite(bs[hi % nb]):
                    hi += 1
                bs[k] = bs[lo % nb] + (bs[hi % nb] - bs[lo % nb]) * ((k - lo) / (hi - lo))
                tbl[(alphas[k], r)] = bs[k]

    def flux(r):
        if r <= 6.0001:
            return 0.0
        sr, s6, s3 = math.sqrt(r), math.sqrt(6.0), math.sqrt(3.0)
        ln_t = math.log(((sr + s3) * (s6 - s3)) / ((sr - s3) * (s6 + s3)))
        return max(0.0, (sr - s6 + (s3 / 2.0) * ln_t) / ((r - 3.0) * r**2.5))

    def redshift(r, b, alpha):
        return (1.0 + math.sqrt(1.0 / r**3) * b * sin_i * math.sin(alpha)) / math.sqrt(
            max(1e-9, 1.0 - 3.0 / r)
        )

    curves = []  # (pts, per-vertex flux weight list)
    if mode in ("lines", "both"):
        for r in rings:
            fs = flux(r)
            for tbl, rot in ((t_direct, 0.0), (t_ghost, math.pi)):
                if not tbl:
                    continue
                bs = [tbl.get((alpha, r), float("nan")) for alpha in alphas]
                if sum(1 for b in bs if math.isfinite(b)) < len(bs) * 0.5:
                    continue
                # 3-point circular smoothing kills solver jitter at the wing folds
                nb = len(bs) - 1  # last point duplicates the first
                sm = list(bs)
                for k in range(nb):
                    b0, b1, b2 = bs[(k - 1) % nb], bs[k], bs[(k + 1) % nb]
                    if all(math.isfinite(v) for v in (b0, b1, b2)):
                        sm[k] = 0.25 * b0 + 0.5 * b1 + 0.25 * b2
                sm[-1] = sm[0]
                bs = sm
                pts, ws = [], []
                for alpha, b in zip(alphas, bs):
                    if not math.isfinite(b):
                        continue
                    pts.append(screen(alpha + rot, b))
                    ws.append(fs / redshift(r, b, alpha) ** 4)
                curves.append((pts, ws))

    def bilinear(tbl, alpha, r):
        # linear in alpha and r
        da = 2.0 * math.pi / samples
        ai = min(int(alpha / da), samples - 1)
        a0, a1 = alphas[ai], alphas[ai + 1]
        ta = (alpha - a0) / da
        for k in range(len(dot_rgrid) - 1):
            r0g, r1g = dot_rgrid[k], dot_rgrid[k + 1]
            if r0g <= r <= r1g:
                vals = [tbl.get((a, rg), float("nan")) for a in (a0, a1) for rg in (r0g, r1g)]
                if not all(math.isfinite(v) for v in vals):
                    return float("nan")
                tr = (r - r0g) / max(1e-9, r1g - r0g)
                lo = vals[0] + (vals[1] - vals[0]) * tr
                hi = vals[2] + (vals[3] - vals[2]) * tr
                return lo + (hi - lo) * ta
        return float("nan")

    dot_pts = []
    if mode in ("dots", "both"):
        wmax = 0.0
        for r in dot_rgrid:
            for alpha in alphas[:: max(1, samples // 24)]:
                b = t_direct.get((alpha, r), float("nan"))
                if not math.isfinite(b):
                    continue
                opz = (1.0 + math.sqrt(1.0 / r**3) * b * sin_i * math.sin(alpha)) / math.sqrt(
                    max(1e-9, 1.0 - 3.0 / r)
                )
                wmax = max(wmax, flux(r) / opz**4)
        wmax = wmax or 1.0
        cell_counts: dict = {}
        # dot_cell is in paper mm; convert to solver units via the expected fit
        u_cell = max(1e-6, dot_cell * (2.6 * r_max) / max(1.0, (x1 - x0)))
        placed = 0
        guard = 0
        while placed < dots and guard < dots * 160:
            guard += 1
            ghost_pick = ghost and rng.random() < 0.22
            tbl = t_ghost if ghost_pick else t_direct
            r = 6.05 + (r_max - 6.05) * rng.random()
            alpha = 2.0 * math.pi * rng.random()
            b = bilinear(tbl, alpha, r)
            if not math.isfinite(b):
                continue
            opz = (1.0 + math.sqrt(1.0 / r**3) * b * sin_i * math.sin(alpha)) / math.sqrt(
                max(1e-9, 1.0 - 3.0 / r)
            )
            w = flux(r) / opz**4
            # dot_gamma=1 is Luminet's photographic plate; <1 lifts dim regions
            if rng.random() > (max(0.0, w) / wmax) ** dot_gamma:
                continue
            px, py = screen(alpha + (math.pi if ghost_pick else 0.0), b)
            key = (int(px / u_cell), int(py / u_cell))
            if cell_counts.get(key, 0) >= dot_cap:
                continue
            cell_counts[key] = cell_counts.get(key, 0) + 1
            dot_pts.append((px, py, w))
            placed += 1

        if isco_line and t_ghost:
            # the crisp lensed arc of the disk's inner edge (ghost ISCO image)
            r_in = dot_rgrid[0]
            bs = [t_ghost.get((alpha, r_in), float("nan")) for alpha in alphas]
            if sum(1 for b in bs if math.isfinite(b)) > len(bs) * 0.5:
                pts = [
                    screen(alpha + math.pi, b) for alpha, b in zip(alphas, bs) if math.isfinite(b)
                ]
                curves.append((pts, None))

    if mode == "flow":
        # strokes ride the lensed isoradials; dash duty follows observed flux —
        # the physics-native tonal rendering (no raster intermediate)
        ring_data = []
        all_lw = []
        for r in rings:
            fs = flux(r)
            for tbl, rot in ((t_direct, 0.0), (t_ghost, math.pi)):
                if not tbl:
                    continue
                bs = [tbl.get((alpha, r), float("nan")) for alpha in alphas]
                if sum(1 for b in bs if math.isfinite(b)) < len(bs) * 0.5:
                    continue
                pts, ws = [], []
                for alpha, b in zip(alphas, bs):
                    if not math.isfinite(b):
                        continue
                    pts.append(screen(alpha + rot, b))
                    w = fs / redshift(r, b, alpha) ** 4
                    ws.append(w)
                    if w > 0:
                        all_lw.append(math.log10(w))
                ring_data.append((pts, ws))
        all_lw.sort()
        lw_lo = all_lw[int(0.05 * (len(all_lw) - 1))]
        lw_hi = all_lw[int(0.995 * (len(all_lw) - 1))]
        dash_u = dash_mm * (2.6 * r_max) / max(1.0, (x1 - x0))
        # screen-space spacing: one pass per flow_spacing-mm cell, so converging
        # rings thin out instead of pooling into solid black
        u_sp = max(1e-6, flow_spacing * (2.6 * r_max) / max(1.0, (x1 - x0)))
        occ = set()
        for pts, ws in ring_data:
            stroke, stroke_t = [], []
            my_cells: set = set()
            acc = 0.0
            # bright zones get long flowing strokes, dim zones short ticks
            next_cell = dash_u
            drawing = False

            def flush():
                nonlocal stroke, stroke_t, my_cells
                if len(stroke) >= 2:
                    mean_t = sum(stroke_t) / len(stroke_t)
                    wv = 10.0 ** (lw_lo + mean_t * (lw_hi - lw_lo))
                    curves.append((list(stroke), [wv] * len(stroke)))
                    occ.update(my_cells)
                    if mean_t > double_thresh:
                        off = 0.35 * (2.6 * r_max) / max(1.0, (x1 - x0))
                        curves.append(([(px, py + off) for px, py in stroke], [wv] * len(stroke)))
                stroke, stroke_t = [], []
                my_cells = set()

            for i in range(len(pts) - 1):
                (xa, ya), (xb, yb) = pts[i], pts[i + 1]
                wa = ws[i]
                t = 0.0
                if wa > 0:
                    t = (math.log10(wa) - lw_lo) / max(1e-9, lw_hi - lw_lo)
                t = max(0.0, min(1.0, t))
                seg = math.hypot(xb - xa, yb - ya)
                acc += seg
                if acc >= next_cell:
                    acc = 0.0
                    next_cell = dash_u * (0.4 + 2.2 * t + 0.5 * rng.random())
                    duty = t**flow_gamma
                    want = t > 0.04 and rng.random() < duty
                    if want and not drawing:
                        drawing = True
                    elif not want and drawing:
                        flush()
                        drawing = False
                if drawing:
                    cell = (int(xb / u_sp), int(yb / u_sp))
                    if cell in occ and cell not in my_cells:
                        flush()
                        drawing = False
                        continue
                    my_cells.add(cell)
                    if not stroke:
                        stroke.append((xa, ya))
                        stroke_t.append(t)
                    stroke.append((xb, yb))
                    stroke_t.append(t)
            flush()

    # shadow (photon ring critical curve)
    b_crit = math.sqrt(27.0)
    curves.append(
        (
            [
                (
                    b_crit * math.cos(2 * math.pi * k / samples),
                    b_crit * math.sin(2 * math.pi * k / samples),
                )
                for k in range(samples + 1)
            ],
            None,
        )
    )

    xs = [pt[0] for c, _ in curves for pt in c] + [d[0] for d in dot_pts]
    ys = [pt[1] for c, _ in curves for pt in c] + [d[1] for d in dot_pts]
    sc = 0.94 * min((x1 - x0) / (max(xs) - min(xs)), (y1 - y0) / (max(ys) - min(ys)))
    mx = (max(xs) + min(xs)) / 2.0
    my = (max(ys) + min(ys)) / 2.0

    # pen per flux bin (log scale, bgmeulem-style): pen 0 = brightest
    all_w = [w for _, ws in curves if ws for w in ws if w > 0] + [
        w for _, _, w in dot_pts if w and w > 0
    ]
    if all_w and colors > 1:
        logs = sorted(math.log10(w) for w in all_w)
        w_lo = logs[int(0.04 * (len(logs) - 1))]
        w_hi = logs[int(0.995 * (len(logs) - 1))]
    else:
        w_lo, w_hi = 0.0, 1.0

    def pen_of(w):
        if colors <= 1:
            return None
        if w is None or w <= 0:
            return colors - 1
        t = (math.log10(w) - w_lo) / max(1e-9, w_hi - w_lo)
        return colors - 1 - min(colors - 1, max(0, int(t * colors)))

    out: List[GCodeCommand] = []
    for pts, ws in curves:
        spts = [
            (_clamp(cx + (px - mx) * sc, x0, x1), _clamp(cy + (py - my) * sc, y0, y1))
            for px, py in pts
        ]
        if colors <= 1 or not ws:
            spts, _ = _catmull_subdivide(spts)
            out += _poly(spts, color=(colors - 1 if colors > 1 else None), f=feed)
            continue
        pens = [pen_of(w) for w in ws]
        spts, pens = _catmull_subdivide(spts, pens)
        # absorb runs shorter than 4 vertices to avoid pen thrash
        i = 0
        while i < len(pens):
            j = i
            while j < len(pens) and pens[j] == pens[i]:
                j += 1
            if j - i < 4 and i > 0:
                for k in range(i, j):
                    pens[k] = pens[i - 1]
            i = j
        i = 0
        while i < len(spts) - 1:
            j = i
            while j < len(pens) and pens[j] == pens[i]:
                j += 1
            out += _poly(spts[i : j + 1], color=pens[i], f=feed)
            i = j
    for px, py, wgt in dot_pts:
        color = pen_of(wgt)
        out += _dot(
            _clamp(cx + (px - mx) * sc, x0, x1),
            _clamp(cy + (py - my) * sc, y0, y1),
            r=dot_size,
            color=color,
            f=feed,
        )
    return out


# ---------------------------------------------------------------------------
# 35. transformer suite: pe_carpet / attention_arcs / residual_river
# ---------------------------------------------------------------------------


def pe_carpet(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 1,
    rows: int = 44,
    d_model: int = 64,
    pos_span: float = 80.0,
    amp_frac: float = 0.65,
    feed: int = 2200,
) -> List[GCodeCommand]:
    """The transformer's sinusoidal positional encoding as a waveform carpet.

    Row i draws sin(pos / 10000^(2k/d_model)) (cos on odd channels) across the
    page — slow frequencies at the bottom, fast at the top: the exact matrix
    from "Attention Is All You Need" as a joy-division carpet. Pure formula;
    the seed only jitters nothing. Pens: sin rows / cos rows alternate.
    """
    x0, y0, x1, y1 = bounds
    w, h = x1 - x0, y1 - y0
    gap = h / (rows + 1)
    amp = gap * amp_frac
    nx = max(120, int(w / 0.8))
    out: List[GCodeCommand] = []
    for i in range(rows):
        k = (i // 2) * 2
        freq = 1.0 / (10000.0 ** (k / max(1, d_model)))
        phase = 0.0 if i % 2 == 0 else math.pi / 2.0
        yb = y0 + gap * (i + 1)
        pts = []
        for j in range(nx + 1):
            pos = pos_span * j / nx
            x = x0 + w * j / nx
            pts.append((x, _clamp(yb + amp * math.sin(pos * freq + phase), y0, y1)))
        color = (i % 2) % colors if colors > 1 else None
        out += _poly(pts, color=color, f=feed)
    return out


def _attention_matrix(
    rng: SeededRNG, tokens: int, head: int, temp: float, causal: bool, weights: str, block: int
):
    """Per-head attention pattern: real trained Q/K when a .keras path is
    given (pure numpy, no TF), else a seeded synthetic head (diagonal band +
    anchor columns). Rows softmax to 1 at temperature ``temp``."""
    import numpy as np

    X = np.zeros((tokens, 96))
    for pos in range(tokens):
        for d in range(96):
            f = 1.0 / (10000.0 ** ((d // 2 * 2) / 96.0))
            X[pos, d] = math.sin(pos * f) if d % 2 == 0 else math.cos(pos * f)
    scores = None
    if weights:
        try:
            import zipfile, io, h5py

            buf = io.BytesIO(zipfile.ZipFile(weights).read("model.weights.h5"))
            f5 = h5py.File(buf, "r")
            base = "layers/transformer_encoder_block" + ("" if block == 0 else f"_{block}")
            wq = np.array(f5[f"{base}/att/query_dense/vars/0"])[:, head, :]
            bq = np.array(f5[f"{base}/att/query_dense/vars/1"])[head]
            wk = np.array(f5[f"{base}/att/key_dense/vars/0"])[:, head, :]
            bk = np.array(f5[f"{base}/att/key_dense/vars/1"])[head]
            Q = X @ wq + bq
            K = X @ wk + bk
            scores = (Q @ K.T) / math.sqrt(Q.shape[1])
        except Exception:
            scores = None
    if scores is None:
        off = rng.randint(1, 4) * rng.choice([-1, 1])
        anchors = [rng.randint(0, tokens - 1) for _ in range(rng.randint(1, 3))]
        scores = np.zeros((tokens, tokens))
        for q in range(tokens):
            for kk in range(tokens):
                scores[q, kk] = 1.6 * math.exp(-((kk - q - off) ** 2) / 6.0)
                if kk in anchors:
                    scores[q, kk] += 1.1
                scores[q, kk] += 0.35 * rng.random()
    if causal:
        for q in range(tokens):
            scores[q, q + 1 :] = -1e9
    A = np.exp((scores - scores.max(axis=1, keepdims=True)) / max(1e-3, temp))
    return A / A.sum(axis=1, keepdims=True)


def attention_arcs(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 1,
    tokens: int = 44,
    heads: int = 4,
    temp: float = 1.0,
    topk: int = 3,
    causal: bool = True,
    weights: str = "",
    attn_npz: str = "",
    block: int = 0,
    min_w: float = 0.04,
    feed: int = 2000,
) -> List[GCodeCommand]:
    """Attention as a musical score: tokens on a baseline, each arc bows from
    query to key with ink passes scaling with the attention weight; one pen
    per head. ``weights`` = a .keras checkpoint path uses the REAL trained
    Q/K (numpy-only); ``attn_npz`` = a saved (layers, heads, T, T) attention
    stack (see scripts/extract_gpt2_attention.py) — real GPT-2 attention;
    otherwise seeded synthetic heads. ``temp`` is the softmax temperature —
    low collapses onto few thick arcs, high diffuses.
    """
    x0, y0, x1, y1 = bounds
    w = x1 - x0
    y_base = y0 + 0.14 * (y1 - y0)
    max_h = (y1 - y0) * 0.78
    stack = None
    if attn_npz:
        try:
            import numpy as np

            stack = np.load(attn_npz)["attn"][block]  # (heads, T, T)
            tokens = stack.shape[-1]
            if temp != 1.0:
                logw = np.log(np.clip(stack, 1e-12, None)) / max(1e-3, temp)
                stack = np.exp(logw - logw.max(axis=-1, keepdims=True))
                stack = stack / stack.sum(axis=-1, keepdims=True)
        except Exception:
            stack = None
    xs = [x0 + w * (t + 0.5) / tokens for t in range(tokens)]
    out: List[GCodeCommand] = []
    for t in range(tokens):
        out += _poly([(xs[t], y_base - 2.2), (xs[t], y_base)], color=None, f=feed)
    for head in range(heads):
        if stack is not None:
            A = stack[head % stack.shape[0]]
        else:
            A = _attention_matrix(rng, tokens, head % 6, temp, causal, weights, block)
        color = head % colors if colors > 1 else None
        for q in range(tokens):
            row = sorted(range(tokens), key=lambda kk: -A[q][kk])[:topk]
            for kk in row:
                wgt = float(A[q][kk])
                if kk == q or wgt < min_w:
                    continue
                xa, xb = xs[kk], xs[q]
                span = abs(xb - xa)
                hh = min(max_h, 0.62 * span + 2.0)
                passes = 1 + (1 if wgt > 0.25 else 0) + (1 if wgt > 0.5 else 0)
                for pp in range(passes):
                    pts = []
                    for j in range(25):
                        t01 = j / 24.0
                        x = xa + (xb - xa) * t01
                        y = y_base + (hh + 0.35 * pp) * math.sin(math.pi * t01)
                        pts.append((x, _clamp(y, y0, y1)))
                    out += _poly(pts, color=color, f=feed)
    return out


def residual_river(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 1,
    channels: int = 22,
    blocks: int = 4,
    expand: float = 2.4,
    weave_swaps: int = 7,
    band_frac: float = 0.17,
    feed: int = 2200,
) -> List[GCodeCommand]:
    """The transformer residual stream as a river: parallel channel lines flow
    across the page; each block is an attention station (channels weave and
    swap) followed by an FFN lens (the band expands ~4x and contracts, phase-
    continuous). Skip-connection arcs bridge every station. Pens follow the
    original channel index, so the weaving mixes the colors downstream.
    """
    x0, y0, x1, y1 = bounds
    w, h = x1 - x0, y1 - y0
    cy = (y0 + y1) / 2.0
    h0 = h * band_frac
    # block windows: [station][lens] per block, margins between
    seg = w / blocks
    stations = []
    for b in range(blocks):
        bx = x0 + b * seg
        stations.append((bx + 0.18 * seg, bx + 0.46 * seg, bx + 0.56 * seg, bx + 0.88 * seg))

    # cumulative permutations per block (seeded neighbour transpositions)
    perms = []
    cur = list(range(channels))
    for _ in range(blocks):
        nxt = list(cur)
        for _ in range(weave_swaps):
            i = rng.randint(0, channels - 2)
            j = min(channels - 1, i + rng.randint(1, 3))
            nxt[i], nxt[j] = nxt[j], nxt[i]
        perms.append((list(cur), list(nxt)))
        cur = nxt

    def offset_of(idx):
        return -1.0 + 2.0 * idx / max(1, channels - 1)

    def smooth(t):
        return t * t * (3.0 - 2.0 * t)

    nx = max(240, int(w / 0.7))
    out: List[GCodeCommand] = []
    for ch in range(channels):
        pts = []
        for j in range(nx + 1):
            x = x0 + w * j / nx
            b = min(blocks - 1, int((x - x0) / seg))
            s0, s1, l0, l1 = stations[b]
            before, after = perms[b]
            # position slot: interpolate through this block's weave
            u0 = offset_of(before.index(ch))
            u1 = offset_of(after.index(ch))
            if x < s0:
                u = u0
            elif x <= s1:
                u = u0 + (u1 - u0) * smooth((x - s0) / max(1e-9, s1 - s0))
            else:
                u = u1
            env = 1.0
            if l0 <= x <= l1:
                env = 1.0 + (expand - 1.0) * math.sin(math.pi * (x - l0) / (l1 - l0)) ** 2
            pts.append((x, _clamp(cy + u * h0 * env, y0, y1)))
        color = ch % colors if colors > 1 else None
        out += _poly(pts, color=color, f=feed)

    # skip-connection arcs over each block
    top = cy - h0 * expand - 3.0
    for b in range(blocks):
        s0, _, _, l1 = stations[b]
        xa, xb = s0 - 0.06 * seg, l1 + 0.04 * seg
        pts = []
        for j in range(33):
            t01 = j / 32.0
            x = xa + (xb - xa) * t01
            y = top - 6.0 * math.sin(math.pi * t01)
            pts.append((x, _clamp(y, y0, y1)))
        out += _poly(pts, color=(colors - 1 if colors > 1 else None), f=feed)
    return out


# single-stroke vector font (4x6 grid, baseline 0) for pen-drawn legends
_GLYPHS = {
    "A": [[(0, 0), (2, 6), (4, 0)], [(1, 2.4), (3, 2.4)]],
    "B": [
        [(0, 0), (0, 6), (3, 6), (4, 5), (4, 4), (3, 3), (0, 3)],
        [(3, 3), (4, 2), (4, 1), (3, 0), (0, 0)],
    ],
    "C": [[(4, 1), (3, 0), (1, 0), (0, 1), (0, 5), (1, 6), (3, 6), (4, 5)]],
    "D": [[(0, 0), (0, 6), (2, 6), (4, 4), (4, 2), (2, 0), (0, 0)]],
    "E": [[(4, 0), (0, 0), (0, 6), (4, 6)], [(0, 3), (3, 3)]],
    "F": [[(0, 0), (0, 6), (4, 6)], [(0, 3), (3, 3)]],
    "G": [[(4, 5), (3, 6), (1, 6), (0, 5), (0, 1), (1, 0), (3, 0), (4, 1), (4, 3), (2, 3)]],
    "H": [[(0, 0), (0, 6)], [(4, 0), (4, 6)], [(0, 3), (4, 3)]],
    "I": [[(2, 0), (2, 6)], [(1, 0), (3, 0)], [(1, 6), (3, 6)]],
    "J": [[(4, 6), (4, 1), (3, 0), (1, 0), (0, 1)]],
    "K": [[(0, 0), (0, 6)], [(4, 6), (0, 2.5)], [(1.4, 3.4), (4, 0)]],
    "L": [[(0, 6), (0, 0), (4, 0)]],
    "M": [[(0, 0), (0, 6), (2, 3), (4, 6), (4, 0)]],
    "N": [[(0, 0), (0, 6), (4, 0), (4, 6)]],
    "O": [[(1, 0), (0, 1), (0, 5), (1, 6), (3, 6), (4, 5), (4, 1), (3, 0), (1, 0)]],
    "P": [[(0, 0), (0, 6), (3, 6), (4, 5), (4, 3.6), (3, 3), (0, 3)]],
    "Q": [
        [(1, 0), (0, 1), (0, 5), (1, 6), (3, 6), (4, 5), (4, 1), (3, 0), (1, 0)],
        [(2.6, 1.4), (4.2, -0.4)],
    ],
    "R": [[(0, 0), (0, 6), (3, 6), (4, 5), (4, 3.6), (3, 3), (0, 3)], [(2, 3), (4, 0)]],
    "S": [[(4, 5), (3, 6), (1, 6), (0, 5), (0, 4), (4, 2), (4, 1), (3, 0), (1, 0), (0, 1)]],
    "T": [[(2, 0), (2, 6)], [(0, 6), (4, 6)]],
    "U": [[(0, 6), (0, 1), (1, 0), (3, 0), (4, 1), (4, 6)]],
    "V": [[(0, 6), (2, 0), (4, 6)]],
    "W": [[(0, 6), (1, 0), (2, 4), (3, 0), (4, 6)]],
    "X": [[(0, 0), (4, 6)], [(0, 6), (4, 0)]],
    "Y": [[(0, 6), (2, 3), (4, 6)], [(2, 3), (2, 0)]],
    "Z": [[(0, 6), (4, 6), (0, 0), (4, 0)]],
    "0": [
        [(1, 0), (0, 1), (0, 5), (1, 6), (3, 6), (4, 5), (4, 1), (3, 0), (1, 0)],
        [(0.8, 1), (3.2, 5)],
    ],
    "1": [[(1, 5), (2, 6), (2, 0)], [(1, 0), (3, 0)]],
    "2": [[(0, 5), (1, 6), (3, 6), (4, 5), (4, 4), (0, 0), (4, 0)]],
    "3": [[(0, 6), (4, 6), (2, 3.6), (4, 2), (4, 1), (3, 0), (1, 0), (0, 1)]],
    "4": [[(3, 0), (3, 6), (0, 2), (4, 2)]],
    "5": [[(4, 6), (0, 6), (0, 3.4), (3, 3.4), (4, 2.4), (4, 1), (3, 0), (1, 0), (0, 1)]],
    "6": [[(3, 6), (1, 6), (0, 5), (0, 1), (1, 0), (3, 0), (4, 1), (4, 2.4), (3, 3.4), (0, 3.4)]],
    "7": [[(0, 6), (4, 6), (1.6, 0)]],
    "8": [
        [(1, 3), (0, 4), (0, 5), (1, 6), (3, 6), (4, 5), (4, 4), (3, 3), (1, 3)],
        [(1, 3), (0, 2), (0, 1), (1, 0), (3, 0), (4, 1), (4, 2), (3, 3)],
    ],
    "9": [[(1, 0), (3, 0), (4, 1), (4, 5), (3, 6), (1, 6), (0, 5), (0, 3.6), (1, 2.6), (4, 2.6)]],
    "-": [[(0.5, 3), (3.5, 3)]],
    ".": [[(1.7, 0), (2.3, 0), (2.3, 0.5), (1.7, 0.5), (1.7, 0)]],
    " ": [],
}


def _stroke_text(text, x, y, height, color=None, f=2400):
    """Pen-drawn single-stroke text; (x, y) = left baseline. Returns commands."""
    sc = height / 6.0
    adv = 5.6 * sc
    out = []
    cx = x
    for ch in text.upper():
        for stroke in _GLYPHS.get(ch, []):
            pts = [(cx + gx * sc, y + gy * sc) for gx, gy in stroke]
            out += _poly(pts, color=color, f=f)
        cx += adv
    return out


def _text_width(text, height):
    return len(text) * 5.6 * (height / 6.0)


def weight_matrix(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 1,
    weights: str = "",
    tensor: str = "block",
    block: int = 0,
    tick_frac: float = 0.92,
    min_tick: float = 0.12,
    feed: int = 2400,
) -> List[GCodeCommand]:
    """Trained weight matrices as tick-field panels (a plotter Hinton diagram).

    Every weight is a diagonal tick: length ∝ |w| (99th-percentile normalized),
    direction / for positive and \\ for negative — sign stays readable with a
    single pen; with 2+ pens the signs get their own colors. ``tensor``:
    ``block`` = the whole encoder block on one page (query | key | value on the
    top row, ffn1 | ffn2 below); ``qkv`` = just the attention panels;
    ``ffn1``/``ffn2`` = one MLP matrix. Panels stretch to fill the drawable
    area (non-square cells). Fallback without a checkpoint: seeded gaussians.
    """
    import numpy as np

    x0, y0, x1, y1 = bounds

    def load():
        try:
            import zipfile, io, h5py

            buf = io.BytesIO(zipfile.ZipFile(weights).read("model.weights.h5"))
            f5 = h5py.File(buf, "r")
            base = "layers/transformer_encoder_block" + ("" if block == 0 else f"_{block}")

            def att(nm):
                W = np.array(f5[f"{base}/att/{nm}/vars/0"])
                return W.reshape(W.shape[0], -1)

            return {
                "q": att("query_dense"),
                "k": att("key_dense"),
                "v": att("value_dense"),
                "ffn1": np.array(f5[f"{base}/ffn1/vars/0"]),
                "ffn2": np.array(f5[f"{base}/ffn2/vars/0"]),
            }
        except Exception:
            return None

    mats = load() if weights else None
    if mats is None:

        def fake(r_, c_):
            m = np.zeros((r_, c_))
            for i in range(r_):
                for j in range(c_):
                    m[i, j] = rng.random() * 2 - 1
            return m

        mats = {
            "q": fake(72, 48),
            "k": fake(72, 48),
            "v": fake(72, 48),
            "ffn1": fake(72, 96),
            "ffn2": fake(96, 48),
        }

    gap = 6.0
    label_h = 6.0
    W_all, H_all = x1 - x0, y1 - y0
    panels = []  # (matrix, rect, is_qkv, label)
    if tensor == "block":
        h_top = (H_all - gap) * 0.42 - label_h
        h_bot = (H_all - gap) * 0.58 - label_h
        pw = (W_all - 2 * gap) / 3.0
        y_top = y0 + h_bot + label_h + gap
        for i, (key, lab) in enumerate((("q", "QUERY"), ("k", "KEY"), ("v", "VALUE"))):
            panels.append((mats[key], (x0 + i * (pw + gap), y_top, pw, h_top), True, lab))
        c1, c2 = mats["ffn1"].shape[1], mats["ffn2"].shape[1]
        w1 = (W_all - gap) * c1 / (c1 + c2)
        panels.append((mats["ffn1"], (x0, y0, w1, h_bot), False, "FFN 1"))
        panels.append((mats["ffn2"], (x0 + w1 + gap, y0, W_all - gap - w1, h_bot), False, "FFN 2"))
    elif tensor == "qkv":
        pw = (W_all - 2 * gap) / 3.0
        for i, (key, lab) in enumerate((("q", "QUERY"), ("k", "KEY"), ("v", "VALUE"))):
            panels.append((mats[key], (x0 + i * (pw + gap), y0, pw, H_all - label_h), True, lab))
    else:
        panels.append(
            (
                mats.get(tensor, mats["ffn1"]),
                (x0, y0, W_all, H_all - label_h),
                False,
                tensor.upper(),
            )
        )

    out: List[GCodeCommand] = []
    label_pen = (colors - 1) if colors > 1 else None
    for Wm, (rx, ry, rw, rh), is_qkv, lab in panels:
        tw = _text_width(lab, 3.6)
        out += _stroke_text(lab, rx + (rw - tw) / 2.0, ry + rh + 1.2, 3.6, color=label_pen, f=feed)
        rows, cols = Wm.shape
        cw, ch = rw / cols, rh / rows
        half = min(cw, ch) * tick_frac / 2.0
        norm = float(np.percentile(np.abs(Wm), 99)) or 1.0
        for i in range(rows):
            cy_ = ry + ch * (rows - 1 - i + 0.5)
            for j in range(cols):
                w = float(Wm[i, j])
                ln = half * min(1.0, abs(w) / norm)
                if ln < min_tick:
                    continue
                cx_ = rx + cw * (j + 0.5)
                sgn = 1.0 if w >= 0 else -1.0
                color = (0 if w >= 0 else 1) % colors if colors > 1 else None
                out += _poly(
                    [(cx_ - ln, cy_ - ln * sgn), (cx_ + ln, cy_ + ln * sgn)], color=color, f=feed
                )
        if is_qkv and cols % 6 == 0:
            for hsep in range(1, 6):
                xh = rx + cw * (cols // 6) * hsep
                out += _poly(
                    [(xh, ry), (xh, ry + rh)], color=(colors - 1 if colors > 1 else None), f=feed
                )
    return out
