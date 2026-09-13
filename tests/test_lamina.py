"""Lamina layer: style presets, panel layout math, plate composition."""

import pytest

from promptplot.lamina import (
    STYLE_PRESETS,
    Panel,
    PlateSpec,
    compose_plate,
    get_style,
    spec_from_json,
    spec_to_json,
)
from promptplot.lamina.layout import reserve_bands, split_panels
from promptplot.orchestrate import split_color_layers


def test_style_presets_wellformed():
    assert set(STYLE_PRESETS) == {"bauhaus", "swiss", "deco", "pop", "radial_viz", "science_poster"}
    for name, p in STYLE_PRESETS.items():
        assert p.name == name
        assert len(p.pens) >= 2
        assert p.type_align in ("left", "center")
        assert 0 <= p.accent_pen < len(p.pens)
    with pytest.raises(KeyError):
        get_style("memphis")


def test_reserve_bands():
    title, content, footer = reserve_bands((0, 0, 100, 200), title_h=16, footer_h=8)
    assert title == (0, 184, 100, 200)
    assert footer == (0, 0, 100, 8)
    assert content == (0, 8, 100, 184)
    t2, c2, f2 = reserve_bands((0, 0, 100, 200))
    assert t2 is None and f2 is None and c2 == (0, 0, 100, 200)


def test_split_panels_math():
    content = (10.0, 10.0, 130.0, 190.0)
    panels = split_panels(content, 3, gutter=6.0)
    assert len(panels) == 3
    for x0, y0, x1, y1 in panels:
        assert x0 >= content[0] - 1e-9 and x1 <= content[2] + 1e-9
        assert y0 >= content[1] - 1e-9 and y1 <= content[3] + 1e-9
        assert x1 > x0 and y1 > y0
    # exact gutters, no overlap
    assert panels[1][0] - panels[0][2] == pytest.approx(6.0)
    assert panels[2][0] - panels[1][2] == pytest.approx(6.0)
    # widths equal
    w = [p[2] - p[0] for p in panels]
    assert w[0] == pytest.approx(w[1]) == pytest.approx(w[2])


def test_split_panels_grid_rows():
    panels = split_panels((0, 0, 100, 100), 4, rows=2, gutter=4.0)
    assert len(panels) == 4
    # first row is at the TOP
    assert panels[0][3] == pytest.approx(100.0)
    assert panels[2][3] < panels[0][3]
    with pytest.raises(ValueError):
        split_panels((0, 0, 100, 100), 2, rows=5)


def _spec(**kw):
    d = dict(
        panels=[Panel(generator="truchet", seed=8)],
        style="bauhaus",
        paper="a5",
        orientation="portrait",
    )
    d.update(kw)
    return PlateSpec(**d)


def test_compose_deterministic():
    a, _ = compose_plate(_spec())
    b, _ = compose_plate(_spec())
    assert [c.to_gcode() for c in a.commands] == [c.to_gcode() for c in b.commands]


def test_compose_layers_within_palette():
    spec = _spec(panels=[Panel(generator="bauhaus_relevance", seed=7)], style="bauhaus")
    program, pen_plan = compose_plate(spec)
    preset = get_style("bauhaus")
    layers = split_color_layers(program)
    for color_idx, _cmds in layers:
        assert color_idx is None or color_idx < len(preset.pens)
    assert len(pen_plan) <= len(preset.pens)


def test_compose_three_panel_smoke():
    spec = _spec(
        panels=[Panel("truchet", 8), Panel("hitomezashi", 9), Panel("wave_bands", 10)],
        style="science_poster",
        title="THREE PANEL",
        paper="a4",
        orientation="landscape",
    )
    program, pen_plan = compose_plate(spec)
    assert len(program.commands) > 100
    assert pen_plan


def test_spec_json_roundtrip():
    spec = _spec(title="T", subtitle="S", rows=1)
    back = spec_from_json(spec_to_json(spec))
    assert back == spec


def test_empty_spec_raises():
    with pytest.raises(ValueError):
        compose_plate(PlateSpec(panels=[]))
