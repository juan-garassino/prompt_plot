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
        "iso_city",
        "rounded_circuits",
        "lissajous_swarm",
        "black_hole",
        "pe_carpet",
        "attention_arcs",
        "residual_river",
        "weight_matrix",
        "attention_matrix",
        "black_hole_bauhaus",
        "bauhaus_attractor",
        "bauhaus_attention",
        "bauhaus_weights",
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
        "iso_city",
        "rounded_circuits",
        "lissajous_swarm",
        "black_hole",
        "pe_carpet",
        "attention_arcs",
        "residual_river",
        "weight_matrix",
        "attention_matrix",
        "black_hole_bauhaus",
        "bauhaus_attractor",
        "bauhaus_attention",
        "bauhaus_weights",
    ],
)
def test_generator_deterministic_and_nonempty(name):
    a = run_generator(name, BOUNDS, seed=123)
    b = run_generator(name, BOUNDS, seed=123)
    assert a and b, f"{name} produced no commands"
    assert [c.to_gcode() for c in a] == [c.to_gcode() for c in b], f"{name} not deterministic"


@pytest.mark.parametrize(
    "name",
    [
        "tiled_field",
        "ripple_field",
        "flow_field",
        "waves_with_circles",
        "crosshatch_weave",
        "turning_weave",
        "wave_gradient",
        "interference_field",
        "frequency_lens",
        "hitomezashi",
        "harmonograph",
        "vortex_field",
        "strange_attractor",
        "domain_warp",
        "contour_field",
        "superformula_bloom",
        "attention_arcs",
        "residual_river",
        "weight_matrix",
        "attention_matrix",
    ],
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
        "iso_city",
        "rounded_circuits",
        "lissajous_swarm",
        "black_hole",
        "pe_carpet",
        "attention_arcs",
        "residual_river",
        "weight_matrix",
        "attention_matrix",
        "black_hole_bauhaus",
        "bauhaus_attractor",
        "bauhaus_attention",
        "bauhaus_weights",
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


def _mk_gradient_png(tmp_path, name="grad.png", dark_left=True):
    PIL = pytest.importorskip("PIL.Image")
    img = PIL.new("L", (60, 40))
    for x in range(60):
        v = int(255 * (x / 59)) if dark_left else int(255 * (1 - x / 59))
        for y in range(40):
            img.putpixel((x, y), v)
    p = tmp_path / name
    img.save(p)
    return str(p)


def test_line_halftone_stays_inside_image_band(tmp_path):
    img = _mk_gradient_png(tmp_path)
    from promptplot.generative.generators import _image_tone_grid
    from promptplot.generative import SeededRNG

    rng = SeededRNG(3)
    gw, gh, off_x, off_y, _ = _image_tone_grid(SeededRNG(3), BOUNDS, img, 1.6, False)
    top = off_y + gh * 1.6
    cmds = run_generator("line_halftone", BOUNDS, seed=3, params={"image": img, "pitch": 1.6})
    assert cmds
    for c in cmds:
        if c.y is not None:
            assert c.y <= top + 0.6, f"command above image band: y={c.y} top={top}"


def test_line_halftone_dark_runs_are_multi_pass(tmp_path):
    img = _mk_gradient_png(tmp_path)
    cmds = run_generator("line_halftone", BOUNDS, seed=3, params={"image": img, "pitch": 1.6})
    # count distinct x positions per ~vertical stroke: dark side should produce
    # parallel passes offset by <1mm around some lines
    xs = sorted({c.x for c in cmds if c.command == "G0" and c.x is not None})
    close_pairs = sum(1 for a, b in zip(xs, xs[1:]) if 0.1 < b - a < 0.6)
    assert close_pairs >= 3, f"expected multi-pass offsets, close pairs={close_pairs}"


def test_sparkle_grid_spurs_never_overlap():
    cmds = run_generator("sparkle_grid", BOUNDS, seed=9, params={"fill": 1.0})
    # collect 2-point axis-aligned strokes (the spurs) grouped by their line
    horiz = {}
    vert = {}
    stroke = []
    for c in cmds:
        if c.command == "G0":
            stroke = [c]
        elif c.command == "G1":
            stroke.append(c)
        elif c.command == "M5" and len(stroke) == 2:
            a, b = stroke
            if a.y == b.y:
                horiz.setdefault(a.y, []).append(tuple(sorted((a.x, b.x))))
            elif a.x == b.x:
                vert.setdefault(a.x, []).append(tuple(sorted((a.y, b.y))))
    for groups in (horiz, vert):
        for key, ivs in groups.items():
            ivs = sorted(ivs)
            for (a1, b1), (a2, b2) in zip(ivs, ivs[1:]):
                assert a2 >= b1 - 0.01, f"overlapping spurs on line {key}: {(a1,b1)} vs {(a2,b2)}"


@pytest.mark.parametrize(
    "system",
    [
        "lorenz",
        "rossler",
        "halvorsen",
        "aizawa",
        "rabinovich_fabrikant",
        "chen",
        "newton_leipnik",
        "burke_shaw",
        "finance",
        "three_scroll",
        "qi",
    ],
)
def test_every_attractor_system_healthy(system):
    cmds = run_generator(
        "strange_attractor", BOUNDS, seed=5, params={"system": system, "steps": 6000}
    )
    a = [c.to_gcode() for c in cmds]
    b = [
        c.to_gcode()
        for c in run_generator(
            "strange_attractor", BOUNDS, seed=5, params={"system": system, "steps": 6000}
        )
    ]
    assert len(cmds) > 50, f"{system} produced too little"
    assert a == b, f"{system} not deterministic"
    for c in cmds:
        if c.x is not None:
            assert BOUNDS[0] - 0.5 <= c.x <= BOUNDS[2] + 0.5
        if c.y is not None:
            assert BOUNDS[1] - 0.5 <= c.y <= BOUNDS[3] + 0.5


def test_black_hole_retro80_smoke():
    a = run_generator(
        "black_hole",
        BOUNDS,
        seed=5,
        params=dict(
            mode="flow",
            bg_lines=8,
            backdrop="grid",
            stars=6,
            sun_slits=True,
            legend=True,
            glitch_strip=True,
            samples=40,
            n_iso=8,
            flow_rings=24,
        ),
    )
    b = run_generator(
        "black_hole",
        BOUNDS,
        seed=5,
        params=dict(
            mode="flow",
            bg_lines=8,
            backdrop="grid",
            stars=6,
            sun_slits=True,
            legend=True,
            glitch_strip=True,
            samples=40,
            n_iso=8,
            flow_rings=24,
        ),
    )
    assert a and [c.to_gcode() for c in a] == [c.to_gcode() for c in b]
    for c in a:
        if c.x is not None:
            assert BOUNDS[0] - 0.5 <= c.x <= BOUNDS[2] + 0.5
        if c.y is not None:
            assert BOUNDS[1] - 0.5 <= c.y <= BOUNDS[3] + 0.5
