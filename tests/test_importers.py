"""SVG + DXF import: parsing, color/layer grouping, fitting to paper."""

from promptplot.config import PromptPlotConfig, PaperConfig
from promptplot.importers import parse_file, import_file
from promptplot.orchestrate import merge_chunks, split_color_layers

SVG_TWO_COLORS = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100">
  <line x1="10" y1="10" x2="90" y2="10" stroke="red"/>
  <polyline points="10,30 90,30 90,60" stroke="blue" fill="none"/>
  <rect x="20" y="70" width="40" height="20" stroke="red" fill="none"/>
</svg>
"""

DXF_TWO_LAYERS = """0
SECTION
2
ENTITIES
0
LINE
8
frame
10
0.0
20
0.0
11
50.0
21
0.0
0
LINE
8
detail
10
0.0
20
10.0
11
50.0
21
40.0
0
LWPOLYLINE
8
frame
10
0.0
20
0.0
10
50.0
20
0.0
10
50.0
20
50.0
0
ENDSEC
0
EOF
"""


def _cfg():
    cfg = PromptPlotConfig()
    cfg.paper = PaperConfig.from_size("a5")
    return cfg


def test_parse_svg_groups_by_stroke_color(tmp_path):
    f = tmp_path / "two.svg"
    f.write_text(SVG_TWO_COLORS)
    result = parse_file(str(f))
    assert result.y_down is True
    colors = {p.color for p in result.paths}
    assert "red" in colors and "blue" in colors
    # 3 shapes: line, polyline, rect
    assert len(result.paths) == 3


def test_import_svg_builds_color_layers(tmp_path):
    f = tmp_path / "two.svg"
    f.write_text(SVG_TWO_COLORS)
    cfg = _cfg()
    commands, palette, _ = import_file(str(f), cfg, group_by="color")
    assert set(palette) == {"red", "blue"}
    cfg.color.enabled = True
    cfg.color.palette = palette
    prog = merge_chunks([commands], cfg)
    layers = split_color_layers(prog)
    assert len({c for c, _ in layers}) == 2


def test_import_fits_within_drawable_area(tmp_path):
    f = tmp_path / "two.svg"
    f.write_text(SVG_TWO_COLORS)
    cfg = _cfg()
    commands, _, _ = import_file(str(f), cfg, fit=True)
    dx0, dy0, dx1, dy1 = cfg.paper.get_drawable_area()
    for c in commands:
        if c.x is not None:
            assert dx0 - 0.5 <= c.x <= dx1 + 0.5
        if c.y is not None:
            assert dy0 - 0.5 <= c.y <= dy1 + 0.5


def test_parse_dxf_groups_by_layer(tmp_path):
    f = tmp_path / "two.dxf"
    f.write_text(DXF_TWO_LAYERS)
    result = parse_file(str(f))
    assert result.y_down is False
    layers = {p.layer for p in result.paths}
    assert "frame" in layers and "detail" in layers


def test_import_dxf_layer_grouping(tmp_path):
    f = tmp_path / "two.dxf"
    f.write_text(DXF_TWO_LAYERS)
    cfg = _cfg()
    commands, palette, _ = import_file(str(f), cfg, group_by="layer")
    assert set(palette) == {"frame", "detail"}
    assert any(c.command == "G1" for c in commands)
