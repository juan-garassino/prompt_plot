"""Multi-color pen layering: grouping, per-color optimization, streaming, round-trip."""

import asyncio

import pytest

from promptplot.config import PromptPlotConfig, PaperConfig, ColorConfig
from promptplot.models import GCodeCommand, GCodeProgram
from promptplot.orchestrate import merge_chunks, split_color_layers, stream_pen_layers
from promptplot.postprocess import group_strokes_by_color, reorder_by_color
from promptplot.plotter import SimulatedPlotter


def _stroke(x0, y0, x1, y1, color):
    return [
        GCodeCommand(command="G0", x=x0, y=y0),
        GCodeCommand(command="M3", s=1000, color=color),
        GCodeCommand(command="G1", x=x1, y=y1, f=1500, color=color),
        GCodeCommand(command="M5"),
    ]


def _cfg():
    cfg = PromptPlotConfig()
    cfg.paper = PaperConfig.from_size("a5")
    cfg.color.enabled = True
    cfg.color.palette = ["black", "red", "blue"]
    cfg.color.pause_for_swap = False
    return cfg


def test_paper_from_size():
    a5 = PaperConfig.from_size("a5")
    assert (a5.width, a5.height) == (148.0, 210.0)
    a3l = PaperConfig.from_size("a3", orientation="landscape")
    assert (a3l.width, a3l.height) == (420.0, 297.0)
    with pytest.raises(ValueError):
        PaperConfig.from_size("b2")


def test_color_roundtrip_through_gcode():
    cmd = GCodeCommand(command="G1", x=10, y=20, f=1500, color=2)
    text = cmd.to_gcode()
    assert "color=2" in text
    # color is a comment, not a machine token
    assert "COLOR" not in text.split(";")[0]
    back = GCodeCommand.from_string(text)
    assert back.color == 2 and back.command == "G1" and back.x == 10.0


def test_group_strokes_by_color_orders_ascending():
    cmds = (
        _stroke(1, 1, 2, 2, color=2) + _stroke(3, 3, 4, 4, color=0) + _stroke(5, 5, 6, 6, color=1)
    )
    buckets, seq = group_strokes_by_color(cmds, _cfg().color)
    assert seq == [0, 1, 2]
    assert all(len(v) == 1 for v in buckets.values())


def test_reorder_groups_by_color():
    cmds = (
        _stroke(1, 1, 2, 2, color=2) + _stroke(3, 3, 4, 4, color=0) + _stroke(5, 5, 6, 6, color=1)
    )
    prog = reorder_by_color(GCodeProgram(commands=cmds), _cfg().color)
    draw_colors = [c.color for c in prog.commands if c.command == "G1"]
    assert draw_colors == [0, 1, 2]
    assert prog.metadata["color_sequence"] == [0, 1, 2]


def test_merge_chunks_color_pipeline_and_split():
    cfg = _cfg()
    raw = _stroke(20, 20, 40, 20, 2) + _stroke(20, 40, 40, 40, 0) + _stroke(20, 60, 40, 60, 1)
    prog = merge_chunks([raw], cfg)
    assert prog.metadata.get("color_sequence") == [0, 1, 2]
    layers = split_color_layers(prog)
    assert [c for c, _ in layers] == [0, 1, 2]


def test_round_robin_assignment():
    cfg = _cfg()
    cfg.color.assign_mode = "round_robin"
    cfg.color.strokes_before_swap = 1
    # three uncolored strokes -> assigned 0,1,2 by index
    raw = _stroke(1, 1, 2, 2, None) + _stroke(3, 3, 4, 4, None) + _stroke(5, 5, 6, 6, None)
    buckets, seq = group_strokes_by_color(raw, cfg.color)
    assert seq == [0, 1, 2]


def test_single_color_is_one_layer():
    cfg = _cfg()
    raw = _stroke(20, 20, 40, 20, 0) + _stroke(20, 40, 40, 40, 0)
    prog = merge_chunks([raw], cfg)
    layers = split_color_layers(prog)
    assert len(layers) == 1


def test_stream_pen_layers_runs_all_layers():
    cfg = _cfg()
    raw = _stroke(20, 20, 40, 20, 0) + _stroke(20, 40, 40, 40, 1) + _stroke(20, 60, 40, 60, 2)
    prog = merge_chunks([raw], cfg)

    swaps = []

    async def go():
        p = SimulatedPlotter()
        await p.connect()
        return await stream_pen_layers(
            prog, p, cfg, on_swap=lambda idx, name: swaps.append((idx, name))
        )

    ok, err = asyncio.run(go())
    assert err == 0 and ok > 0
    # two swaps between three color layers
    assert swaps == [(1, "red"), (2, "blue")]
