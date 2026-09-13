"""COMPAT SHIM — the historical home of the kit, engine and pieces.

The framework is style-neutral ("it's not just Bauhaus"): the code now lives in
``kit.py`` (2D design kit), ``engine3d.py`` (z-buffer hidden-line renderer) and
``pieces/`` (compositions by domain); style is chosen at the LAMINA level.
Every name that used to live here keeps importing from this module.
"""

from __future__ import annotations

from .kit import (  # noqa: F401
    BAUHAUS_PALETTE,
    BLACK,
    BLUE,
    Bounds,
    PINK,
    _attention_matrix,
    _catmull_subdivide,
    _chain_segments,
    _clip_runs,
    _cut,
    _dot,
    _emit_runs,
    _fit_runs_cover,
    _limit_overdraw,
    _marching_squares,
    _pen,
    _poly,
    _rect_keep,
    _runs_from_cmds,
    _spaced,
    _stroke_text,
    _text_width,
    circle,
    crosshair_rules,
    dotted_circle,
    fill_disc,
    fill_quarter,
    fill_rect,
    fill_ring,
    plus_mark,
    scale_footer,
    swatch_bar,
    type_block,
)
from .engine3d import _fit_out, _zbuf_terrain  # noqa: F401
from .pieces.ml import (  # noqa: F401
    _load_qkv,
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
from .pieces.abstract import (  # noqa: F401
    bauhaus_attractor,
    bauhaus_resonance,
    bauhaus_warped_frame,
)
