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
}

_SKIP_PARAMS = {"rng", "bounds"}


def list_generators() -> List[str]:
    return sorted(GENERATOR_REGISTRY)


def get_generator_schema(name: str) -> Dict[str, Any]:
    if name not in GENERATOR_REGISTRY:
        raise KeyError(f"Unknown generator {name!r}. Available: {list_generators()}")
    fn = GENERATOR_REGISTRY[name]
    sig = inspect.signature(fn)
    params: Dict[str, Any] = {}
    for pname, p in sig.parameters.items():
        if pname in _SKIP_PARAMS:
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
