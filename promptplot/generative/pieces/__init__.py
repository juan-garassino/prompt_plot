"""Pieces — the seeded compositions, organized by science domain.

Each function is ``(rng, bounds, colors=3, ...) -> List[GCodeCommand]``;
registered in ``..registry``. Style is applied at the lamina level.
"""

from __future__ import annotations

from .ml import (  # noqa: F401
    bauhaus_attention,
    bauhaus_conveyor,
    bauhaus_decision,
    bauhaus_gradient,
    bauhaus_gradient_v1,
    bauhaus_locality,
    bauhaus_locality_v1,
    bauhaus_loom,
    bauhaus_manifold,
    bauhaus_memory,
    bauhaus_memory_v1,
    bauhaus_perceptron,
    bauhaus_relevance,
    bauhaus_relevance_v1,
    bauhaus_settling,
    bauhaus_weights,
)
from .abstract import (  # noqa: F401
    bauhaus_attractor,
    bauhaus_resonance,
    bauhaus_warped_frame,
)
from .physics import gw150914  # noqa: F401
