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
