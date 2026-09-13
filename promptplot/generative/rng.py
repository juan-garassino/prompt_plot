"""Deterministic seeded randomness for the generative pillar.

Every generator draws all of its randomness from a single ``SeededRNG`` so that
the same seed + params + version always produce byte-identical GCode. Never use
the global ``random``/``numpy.random`` inside a generator.
"""

from __future__ import annotations

import math
import random
from typing import Any, Optional, Sequence

try:
    import numpy as _np

    NUMPY_AVAILABLE = True
except ImportError:  # numpy is a hard dep via viz extra, but stay import-safe
    _np = None
    NUMPY_AVAILABLE = False


class SeededRNG:
    """Wraps a stdlib Random + (optional) numpy Generator, plus value noise."""

    def __init__(self, seed: int):
        self.seed = int(seed)
        self.py = random.Random(self.seed)
        self.np = _np.random.default_rng(self.seed) if _np is not None else None

    # --- scalar helpers (stdlib-backed, always available) ---
    def random(self) -> float:
        return self.py.random()

    def uniform(self, a: float, b: float) -> float:
        return self.py.uniform(a, b)

    def randint(self, a: float, b: float) -> int:
        return self.py.randint(int(a), int(b))

    def choice(self, seq: Sequence[Any]) -> Any:
        return self.py.choice(list(seq))

    def choices(self, seq: Sequence[Any], weights: Optional[Sequence[float]] = None, k: int = 1):
        return self.py.choices(list(seq), weights=weights, k=k)

    def gauss(self, mu: float = 0.0, sigma: float = 1.0) -> float:
        return self.py.gauss(mu, sigma)

    def shuffle(self, x: list) -> list:
        self.py.shuffle(x)
        return x

    # --- deterministic 2D value noise in [0, 1] ---
    def _hash01(self, i: int, j: int) -> float:
        h = (i * 374761393 + j * 668265263 + self.seed * 2654435761) & 0xFFFFFFFF
        h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
        return (h & 0xFFFFFFFF) / 0xFFFFFFFF

    def noise2d(self, x: float, y: float) -> float:
        """Smooth value noise in [0, 1] at (x, y). Deterministic for this seed."""
        x0, y0 = math.floor(x), math.floor(y)
        fx, fy = x - x0, y - y0

        def sm(t: float) -> float:
            return t * t * (3.0 - 2.0 * t)

        n00 = self._hash01(x0, y0)
        n10 = self._hash01(x0 + 1, y0)
        n01 = self._hash01(x0, y0 + 1)
        n11 = self._hash01(x0 + 1, y0 + 1)
        u, v = sm(fx), sm(fy)
        return (n00 * (1 - u) + n10 * u) * (1 - v) + (n01 * (1 - u) + n11 * u) * v

    def fbm(
        self, x: float, y: float, octaves: int = 4, lacunarity: float = 2.0, gain: float = 0.5
    ) -> float:
        """Fractal (multi-octave) value noise in ~[0, 1]."""
        total = 0.0
        amp = 1.0
        freq = 1.0
        norm = 0.0
        for _ in range(max(1, octaves)):
            total += amp * self.noise2d(x * freq, y * freq)
            norm += amp
            amp *= gain
            freq *= lacunarity
        return total / norm if norm else 0.0
