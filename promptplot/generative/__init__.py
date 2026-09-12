"""Seeded generative art pillar — plug-and-play, deterministic-from-seed generators.

Same seed + params + version → identical GCode. Generators return color-tagged
strokes that flow through the normal postprocess / preview / streaming pipeline.
"""

from .rng import SeededRNG
from .effects import anaglyph_layers
from .registry import (
    GENERATOR_REGISTRY,
    list_generators,
    get_generator_schema,
    get_all_generator_schemas,
    format_generators_for_help,
    run_generator,
)

__all__ = [
    "SeededRNG",
    "anaglyph_layers",
    "GENERATOR_REGISTRY",
    "list_generators",
    "get_generator_schema",
    "get_all_generator_schemas",
    "format_generators_for_help",
    "run_generator",
]
