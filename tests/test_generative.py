"""Seeded generative pillar: determinism, bounds-safety, colors, schema introspection."""

import pytest

from promptplot.config import PromptPlotConfig, PaperConfig
from promptplot.generative import (
    SeededRNG,
    list_generators,
    run_generator,
    get_generator_schema,
    get_all_generator_schemas,
)
from promptplot.orchestrate import merge_chunks, split_color_layers

BOUNDS = (10.0, 10.0, 138.0, 200.0)  # A5 drawable


def test_rng_is_deterministic():
    a = SeededRNG(42)
    b = SeededRNG(42)
    assert [a.random() for _ in range(5)] == [b.random() for _ in range(5)]
    assert a.noise2d(1.5, 2.5) == b.noise2d(1.5, 2.5)


def test_all_generators_registered():
    gens = list_generators()
    for expected in [
        "tiled_field",
        "ripple_field",
        "flow_field",
        "maze",
        "truchet",
        "wave_bands",
        "stipple",
        "waves_with_circles",
        "crosshatch_weave",
        "turning_weave",
        "wave_gradient",
        "interference_field",
        "frequency_lens",
        "hitomezashi",
        "harmonograph",
        "vortex_field",
        "moire_layers",
        "strange_attractor",
        "domain_warp",
        "contour_field",
        "superformula_bloom",
        "lissajous_carpet",
        "scribble_halftone",
        "comic_panels",
        "line_halftone",
        "scribble_portrait",
        "sparkle_grid",
    ]:
        assert expected in gens


@pytest.mark.parametrize(
    "name",
    [
        "tiled_field",
        "ripple_field",
        "flow_field",
        "maze",
        "truchet",
        "wave_bands",
        "stipple",
        "waves_with_circles",
        "crosshatch_weave",
        "turning_weave",
        "wave_gradient",
        "interference_field",
        "frequency_lens",
        "hitomezashi",
        "harmonograph",
        "vortex_field",
        "moire_layers",
        "strange_attractor",
        "domain_warp",
        "contour_field",
        "superformula_bloom",
        "lissajous_carpet",
        "scribble_halftone",
        "comic_panels",
        "line_halftone",
        "scribble_portrait",
        "sparkle_grid",
    ],
)
def test_generator_deterministic_and_nonempty(name):
    a = run_generator(name, BOUNDS, seed=123)
    b = run_generator(name, BOUNDS, seed=123)
    assert a and b, f"{name} produced no commands"
    assert [c.to_gcode() for c in a] == [c.to_gcode() for c in b], f"{name} not deterministic"


@pytest.mark.parametrize(
    "name", ["tiled_field", "ripple_field", "flow_field", "waves_with_circles", "crosshatch_weave", "turning_weave", "wave_gradient", "interference_field", "frequency_lens", "hitomezashi", "harmonograph", "vortex_field", "strange_attractor", "domain_warp", "contour_field", "superformula_bloom"]
)
def test_different_seed_differs(name):
    a = run_generator(name, BOUNDS, seed=1)
    b = run_generator(name, BOUNDS, seed=2)
    assert [c.to_gcode() for c in a] != [c.to_gcode() for c in b]


@pytest.mark.parametrize(
    "name",
    [
        "tiled_field",
        "ripple_field",
        "flow_field",
        "maze",
        "truchet",
        "wave_bands",
        "stipple",
        "waves_with_circles",
        "crosshatch_weave",
        "turning_weave",
        "wave_gradient",
        "interference_field",
        "frequency_lens",
        "hitomezashi",
        "harmonograph",
        "vortex_field",
        "moire_layers",
        "strange_attractor",
        "domain_warp",
        "contour_field",
        "superformula_bloom",
        "lissajous_carpet",
        "scribble_halftone",
        "comic_panels",
        "line_halftone",
        "scribble_portrait",
        "sparkle_grid",
    ],
)
def test_generator_within_bounds(name):
    x0, y0, x1, y1 = BOUNDS
    cmds = run_generator(name, BOUNDS, seed=7)
    for c in cmds:
        if c.x is not None:
            assert x0 - 0.5 <= c.x <= x1 + 0.5, f"{name} x={c.x} out of bounds"
        if c.y is not None:
            assert y0 - 0.5 <= c.y <= y1 + 0.5, f"{name} y={c.y} out of bounds"


def test_colors_produce_layers():
    cmds = run_generator("tiled_field", BOUNDS, seed=5, colors=3)
    cfg = PromptPlotConfig()
    cfg.paper = PaperConfig.from_size("a5")
    cfg.color.enabled = True
    cfg.color.palette = ["black", "red", "blue"]
    prog = merge_chunks([cmds], cfg)
    layers = split_color_layers(prog)
    # at least 2 distinct color layers should appear
    assert len({c for c, _ in layers}) >= 2


def test_schema_introspection_skips_rng_bounds():
    schema = get_generator_schema("ripple_field")
    assert "rng" not in schema["params"] and "bounds" not in schema["params"]
    assert "wavelength" in schema["params"]
    assert schema["doc"]
    assert len(get_all_generator_schemas()) == len(list_generators())


def test_params_are_applied():
    few = run_generator("wave_bands", BOUNDS, seed=1, params={"bands": 3})
    many = run_generator("wave_bands", BOUNDS, seed=1, params={"bands": 20})
    assert len(many) > len(few)


def test_anaglyph_layers_duplicates_with_pen_tags():
    from promptplot.generative import SeededRNG, anaglyph_layers, run_generator
    cmds = run_generator("vortex_field", BOUNDS, seed=5, params={"line_count": 10})
    n = len(cmds)
    out = anaglyph_layers(cmds, SeededRNG(99), layers=2, glitch_bands=2, bounds=BOUNDS)
    assert len(out) == 2 * n
    pens = {c.color for c in out if c.command == "G1"}
    assert pens == {0, 1}
    # deterministic
    out2 = anaglyph_layers(cmds, SeededRNG(99), layers=2, glitch_bands=2, bounds=BOUNDS)
    assert [c.to_gcode() for c in out] == [c.to_gcode() for c in out2]
    # in bounds
    for c in out:
        if c.x is not None:
            assert BOUNDS[0] - 0.5 <= c.x <= BOUNDS[2] + 0.5
