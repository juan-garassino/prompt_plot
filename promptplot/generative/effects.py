"""Seeded post-effects applied to generated command lists.

Effects transform a raw ``List[GCodeCommand]`` before merge/postprocess, so they
work with ANY generator. Deterministic: all randomness comes from the SeededRNG.
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

from ..models import GCodeCommand
from .rng import SeededRNG

Bounds = Tuple[float, float, float, float]


def anaglyph_layers(
    commands: List[GCodeCommand],
    rng: SeededRNG,
    offset: Tuple[float, float] = (1.6, 0.9),
    layers: int = 2,
    glitch_bands: int = 0,
    band_shift: float = 4.0,
    bounds: Optional[Bounds] = None,
) -> List[GCodeCommand]:
    """Duplicate a drawing into offset pen layers — 3D-anaglyph / glitch effect.

    Each layer is the full drawing shifted by a fraction of ``offset`` (mm) and
    tagged with its own pen (layer 0 → pen 0, classic red/cyan). With
    ``glitch_bands`` > 0, seeded horizontal bands tear sideways by up to
    ``band_shift`` mm with alternating sign per layer — the glitchy scanline rip.
    """
    layers = max(2, layers)
    ox, oy = offset

    bands: List[Tuple[float, float, float]] = []
    if glitch_bands > 0:
        ys = [c.y for c in commands if c.y is not None]
        if ys:
            ylo, yhi = min(ys), max(ys)
            span = max(1e-6, yhi - ylo)
            for _ in range(glitch_bands):
                b0 = ylo + rng.uniform(0.05, 0.85) * span
                bh = span * rng.uniform(0.03, 0.10)
                shift = band_shift * rng.uniform(0.4, 1.0) * rng.choice([-1.0, 1.0])
                bands.append((b0, b0 + bh, shift))

    def clampx(v: float) -> float:
        if bounds is None:
            return round(v, 2)
        return round(min(max(v, bounds[0]), bounds[2]), 2)

    def clampy(v: float) -> float:
        if bounds is None:
            return round(v, 2)
        return round(min(max(v, bounds[1]), bounds[3]), 2)

    out: List[GCodeCommand] = []
    for L in range(layers):
        frac = L - (layers - 1) / 2.0
        dx, dy = ox * frac, oy * frac
        sign = 1.0 if L % 2 == 0 else -1.0
        for c in commands:
            nc = c.model_copy()
            if nc.x is not None:
                gx = 0.0
                if bands and nc.y is not None:
                    for b0, b1, shift in bands:
                        if b0 <= nc.y <= b1:
                            gx += shift * sign
                nc.x = clampx(nc.x + dx + gx)
            if nc.y is not None:
                nc.y = clampy(nc.y + dy)
            if nc.command in ("M3", "G1"):
                nc.color = L
            out.append(nc)
    return out


def limit_ink_density(
    commands: List[GCodeCommand],
    cell: float = 1.0,
    max_passes: int = 8,
    min_run: float = 2.0,
    decimate: float = 2.0,
) -> List[GCodeCommand]:
    """Cap how many times the pen may pass over any ``cell``-mm spot.

    A deterministic post-process applicable to ANY generator's output: strokes
    are re-sampled and split wherever a cell has already been inked
    ``max_passes`` times, so dense knots (attractor/harmonograph convergence
    zones, interference pileups) thin out instead of chewing through the paper.
    """
    counts: dict = {}

    def cell_of(x, y):
        return (int(x / cell), int(y / cell))

    out: List[GCodeCommand] = []
    i = 0
    n = len(commands)
    while i < n:
        c = commands[i]
        if c.command != "M3":
            out.append(c)
            i += 1
            continue
        m3 = c
        # stroke start = trailing G0 we already emitted
        start = None
        if out and out[-1].command == "G0" and out[-1].x is not None:
            start = (out[-1].x, out[-1].y)
            out.pop()
        j = i + 1
        g1s = []
        while j < n and commands[j].command == "G1":
            g1s.append(commands[j])
            j += 1
        if j < n and commands[j].command == "M5":
            j += 1
        template = g1s[0] if g1s else None
        path = ([start] if start else []) + [(g.x, g.y) for g in g1s if g.x is not None]

        # never densify beyond the stroke's native vertex spacing
        path_len = sum(
            math.hypot(bpt[0] - apt[0], bpt[1] - apt[1]) for apt, bpt in zip(path, path[1:])
        )
        dec = max(decimate, 0.95 * path_len / max(1, len(path) - 1))

        runs = []
        cur: list = []
        prev_cell = None
        for (xa, ya), (xb, yb) in zip(path, path[1:]):
            seg_len = math.hypot(xb - xa, yb - ya)
            ns = max(1, int(seg_len / 0.4))
            for k in range(1, ns + 1):
                px = xa + (xb - xa) * k / ns
                py = ya + (yb - ya) * k / ns
                cl = cell_of(px, py)
                if cl != prev_cell:
                    prev_cell = cl
                    cnt = counts.get(cl, 0)
                    if cnt >= max_passes:
                        if len(cur) >= 2:
                            runs.append(cur)
                        cur = []
                        continue
                    counts[cl] = cnt + 1
                cur.append((px, py)) if cur else cur.extend([(px, py)])
        if len(cur) >= 2:
            runs.append(cur)

        for r in runs:
            # decimate resampled points back to a plottable polyline
            slim = [r[0]]
            for pnt in r[1:-1]:
                if math.hypot(pnt[0] - slim[-1][0], pnt[1] - slim[-1][1]) >= dec:
                    slim.append(pnt)
            slim.append(r[-1])
            total_len = sum(
                math.hypot(bpt[0] - apt[0], bpt[1] - apt[1]) for apt, bpt in zip(slim, slim[1:])
            )
            if len(slim) < 2 or total_len < min_run:
                continue
            out.append(GCodeCommand(command="G0", x=round(slim[0][0], 2), y=round(slim[0][1], 2)))
            out.append(m3.model_copy())
            for pnt in slim[1:]:
                g = template.model_copy() if template else GCodeCommand(command="G1", f=1500)
                g.x = round(pnt[0], 2)
                g.y = round(pnt[1], 2)
                out.append(g)
            out.append(GCodeCommand(command="M5"))
        i = j
    return out
