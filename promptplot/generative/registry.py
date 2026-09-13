"""Generator registry + signature-introspected schemas.

Mirrors the self-describing pattern in ``primitives.py``: parameter schemas are
read from each generator's function signature, so adding a generator and
registering it here is all that's needed — ``art --list`` and any prompt/help
text update themselves.
"""

from __future__ import annotations

import inspect
from typing import Any, Dict, List, Optional, Tuple

from . import generators as _g
from .pieces import abstract as _ab
from .pieces import ml as _ml
from .pieces import physics as _ph
from .rng import SeededRNG

GENERATOR_REGISTRY = {
    "tiled_field": _g.tiled_field,
    "ripple_field": _g.ripple_field,
    "flow_field": _g.flow_field,
    "maze": _g.maze,
    "truchet": _g.truchet,
    "wave_bands": _g.wave_bands,
    "stipple": _g.stipple,
    "waves_with_circles": _g.waves_with_circles,
    "crosshatch_weave": _g.crosshatch_weave,
    "turning_weave": _g.turning_weave,
    "wave_gradient": _g.wave_gradient,
    "interference_field": _g.interference_field,
    "frequency_lens": _g.frequency_lens,
    "hitomezashi": _g.hitomezashi,
    "harmonograph": _g.harmonograph,
    "vortex_field": _g.vortex_field,
    "moire_layers": _g.moire_layers,
    "strange_attractor": _g.strange_attractor,
    "domain_warp": _g.domain_warp,
    "contour_field": _g.contour_field,
    "superformula_bloom": _g.superformula_bloom,
    "lissajous_carpet": _g.lissajous_carpet,
    "scribble_halftone": _g.scribble_halftone,
    "comic_panels": _g.comic_panels,
    "line_halftone": _g.line_halftone,
    "scribble_portrait": _g.scribble_portrait,
    "sparkle_grid": _g.sparkle_grid,
    "iso_city": _g.iso_city,
    "rounded_circuits": _g.rounded_circuits,
    "lissajous_swarm": _g.lissajous_swarm,
    "black_hole": _g.black_hole,
    "pe_carpet": _g.pe_carpet,
    "attention_arcs": _g.attention_arcs,
    "residual_river": _g.residual_river,
    "weight_matrix": _g.weight_matrix,
    "attention_matrix": _g.attention_matrix,
    "black_hole_bauhaus": _g.black_hole_bauhaus,
    "big_bang": _g.big_bang,
    "big_bang_v1": _g.big_bang_v1,
    "bauhaus_attractor": _ab.bauhaus_attractor,
    "bauhaus_attention": _ml.bauhaus_attention,
    "bauhaus_weights": _ml.bauhaus_weights,
    "bauhaus_gradient": _ml.bauhaus_gradient,
    "bauhaus_resonance": _ab.bauhaus_resonance,
    "bauhaus_loom": _ml.bauhaus_loom,
    "bauhaus_decision": _ml.bauhaus_decision,
    "bauhaus_warped_frame": _ab.bauhaus_warped_frame,
    "bauhaus_conveyor": _ml.bauhaus_conveyor,
    "bauhaus_settling": _ml.bauhaus_settling,
    "bauhaus_relevance": _ml.bauhaus_relevance,
    "bauhaus_relevance_v1": _ml.bauhaus_relevance_v1,
    "bauhaus_memory": _ml.bauhaus_memory,
    "bauhaus_memory_v1": _ml.bauhaus_memory_v1,
    "bauhaus_locality": _ml.bauhaus_locality,
    "bauhaus_locality_v1": _ml.bauhaus_locality_v1,
    "bauhaus_manifold": _ml.bauhaus_manifold,
    "gw150914": _ph.gw150914,
}

_SKIP_PARAMS = {"rng", "bounds"}

# Two kinds of art (see ARCHITECTURE.md): GENERATORS are parametric families
# where the seed is a creative axis; COMPOSITIONS are designed singletons where
# the seed only fine-tunes detail. Everything not listed here is a generator.
COMPOSITIONS = {
    "black_hole_bauhaus",
    "big_bang",
    "big_bang_v1",
    "bauhaus_attractor",
    "bauhaus_attention",
    "bauhaus_weights",
    "bauhaus_gradient",
    "bauhaus_resonance",
    "bauhaus_loom",
    "bauhaus_decision",
    "bauhaus_warped_frame",
    "bauhaus_conveyor",
    "bauhaus_settling",
    "bauhaus_relevance",
    "bauhaus_relevance_v1",
    "bauhaus_memory",
    "bauhaus_memory_v1",
    "bauhaus_locality",
    "bauhaus_locality_v1",
    "bauhaus_manifold",
    "gw150914",
}


def generator_kind(name: str) -> str:
    """ "generator" (parametric family) | "composition" (designed singleton)."""
    return "composition" if name in COMPOSITIONS else "generator"


def list_generators(kind: Optional[str] = None) -> List[str]:
    names = sorted(GENERATOR_REGISTRY)
    if kind is not None:
        names = [n for n in names if generator_kind(n) == kind]
    return names


def get_generator_schema(name: str) -> Dict[str, Any]:
    if name not in GENERATOR_REGISTRY:
        raise KeyError(f"Unknown generator {name!r}. Available: {list_generators()}")
    fn = GENERATOR_REGISTRY[name]
    sig = inspect.signature(fn)
    params: Dict[str, Any] = {}
    for pname, p in sig.parameters.items():
        if pname in _SKIP_PARAMS or pname.startswith("_"):
            continue
        params[pname] = None if p.default is inspect._empty else p.default
    doc = (fn.__doc__ or "").strip().split("\n")[0]
    return {"name": name, "doc": doc, "params": params}


def get_all_generator_schemas() -> List[Dict[str, Any]]:
    return [get_generator_schema(n) for n in list_generators()]


def format_generators_for_help() -> str:
    lines = []
    for schema in get_all_generator_schemas():
        lines.append(f"{schema['name']}: {schema['doc']}")
        pstr = ", ".join(f"{k}={v}" for k, v in schema["params"].items() if k != "colors")
        if pstr:
            lines.append(f"    params: {pstr}")
    return "\n".join(lines)


def run_generator(
    name: str,
    bounds: Tuple[float, float, float, float],
    seed: int,
    colors: int = 1,
    params: Optional[Dict[str, Any]] = None,
):
    """Run a generator deterministically. Returns a list of GCodeCommand."""
    if name not in GENERATOR_REGISTRY:
        raise KeyError(f"Unknown generator {name!r}. Available: {list_generators()}")
    fn = GENERATOR_REGISTRY[name]
    sig = inspect.signature(fn)
    kwargs: Dict[str, Any] = {"colors": colors}
    for k, v in (params or {}).items():
        if k in sig.parameters and k not in _SKIP_PARAMS:
            kwargs[k] = v
    rng = SeededRNG(seed)
    return fn(rng, bounds, **kwargs)
