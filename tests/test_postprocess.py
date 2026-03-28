"""Tests for promptplot/postprocess.py — pen safety, optimization, paint dips, dwells, pipeline."""

import pytest
from promptplot.models import GCodeCommand, GCodeProgram
from promptplot.config import PromptPlotConfig, PenConfig, BrushConfig
from promptplot.postprocess import (
    ensure_pen_safety,
    extract_strokes,
    optimize_stroke_order,
    optimize_gcode_program,
    insert_paint_dips,
    insert_pen_dwells,
    run_pipeline,
)


def _make(data):
    return [GCodeCommand(**c) for c in data]


def _prog(data):
    return GCodeProgram(commands=_make(data))


class TestEnsurePenSafety:
    def test_adds_initial_m5(self):
        cmds = _make([
            {"command": "G0", "x": 10, "y": 10},
            {"command": "M3", "s": 1000},
            {"command": "G1", "x": 50, "y": 50, "f": 2000},
            {"command": "M5"},
        ])
        result = ensure_pen_safety(cmds)
        assert result[0].command == "M5"

    def test_inserts_m5_before_g0_when_pen_down(self):
        cmds = _make([
            {"command": "M3", "s": 1000},
            {"command": "G1", "x": 50, "y": 50, "f": 2000},
            {"command": "G0", "x": 100, "y": 100},  # missing M5 before travel
        ])
        result = ensure_pen_safety(cmds)
        # Find the G0 and check M5 comes before it
        for i, cmd in enumerate(result):
            if cmd.command == "G0" and cmd.x == 100:
                assert result[i - 1].command == "M5"
                break

    def test_inserts_m3_before_g1_when_pen_up(self):
        cmds = _make([
            {"command": "M5"},
            {"command": "G0", "x": 10, "y": 10},
            {"command": "G1", "x": 50, "y": 50, "f": 2000},  # missing M3
        ])
        result = ensure_pen_safety(cmds)
        for i, cmd in enumerate(result):
            if cmd.command == "G1":
                assert result[i - 1].command == "M3"
                break

    def test_ensures_final_pen_up(self):
        cmds = _make([
            {"command": "M5"},
            {"command": "G0", "x": 10, "y": 10},
            {"command": "M3", "s": 1000},
            {"command": "G1", "x": 50, "y": 50, "f": 2000},
            # Missing final M5
        ])
        result = ensure_pen_safety(cmds)
        # Should end with M5 then G0 X0 Y0
        pen_up_found = False
        for cmd in reversed(result):
            if cmd.command == "M5":
                pen_up_found = True
                break
        assert pen_up_found

    def test_ensures_return_home(self):
        cmds = _make([
            {"command": "M5"},
            {"command": "G0", "x": 10, "y": 10},
            {"command": "M3", "s": 1000},
            {"command": "G1", "x": 50, "y": 50, "f": 2000},
            {"command": "M5"},
        ])
        result = ensure_pen_safety(cmds)
        last_g0 = None
        for cmd in reversed(result):
            if cmd.command == "G0":
                last_g0 = cmd
                break
        assert last_g0 is not None
        assert last_g0.x == 0.0 and last_g0.y == 0.0

    def test_uses_config_s_value(self):
        pen = PenConfig(pen_down_s_value=500)
        cmds = _make([
            {"command": "M5"},
            {"command": "G0", "x": 10, "y": 10},
            {"command": "G1", "x": 50, "y": 50, "f": 2000},
        ])
        result = ensure_pen_safety(cmds, pen)
        m3_cmds = [c for c in result if c.command == "M3"]
        assert len(m3_cmds) > 0
        assert m3_cmds[0].s == 500


class TestExtractStrokes:
    def test_basic_strokes(self):
        cmds = _make([
            {"command": "M3", "s": 1000},
            {"command": "G1", "x": 50, "y": 50, "f": 2000},
            {"command": "M5"},
            {"command": "M3", "s": 1000},
            {"command": "G1", "x": 100, "y": 100, "f": 2000},
            {"command": "M5"},
        ])
        strokes = extract_strokes(cmds)
        assert len(strokes) == 2

    def test_unclosed_stroke(self):
        cmds = _make([
            {"command": "M3", "s": 1000},
            {"command": "G1", "x": 50, "y": 50, "f": 2000},
        ])
        strokes = extract_strokes(cmds)
        assert len(strokes) == 1
        assert strokes[0][-1].command == "M5"  # Auto-closed


class TestOptimizeStrokeOrder:
    def test_single_stroke_unchanged(self):
        cmds = _make([
            {"command": "M3", "s": 1000},
            {"command": "G1", "x": 50, "y": 50, "f": 2000},
            {"command": "M5"},
        ])
        strokes = extract_strokes(cmds)
        ordered = optimize_stroke_order(strokes)
        assert len(ordered) == 1

    def test_reorders_to_minimize_travel(self):
        # Stroke 1: far away (100, 100)
        # Stroke 2: near origin (5, 5)
        # Starting from (0,0), should pick stroke 2 first
        cmds = _make([
            {"command": "M3", "s": 1000},
            {"command": "G1", "x": 100, "y": 100, "f": 2000},
            {"command": "M5"},
            {"command": "M3", "s": 1000},
            {"command": "G1", "x": 5, "y": 5, "f": 2000},
            {"command": "M5"},
        ])
        strokes = extract_strokes(cmds)
        ordered = optimize_stroke_order(strokes)
        # The stroke near origin should come first
        first_g1 = [c for c in ordered[0] if c.command == "G1"][0]
        assert first_g1.x == 5.0


class TestOptimizeGCodeProgram:
    def test_single_stroke_passthrough(self):
        prog = _prog([
            {"command": "M3", "s": 1000},
            {"command": "G1", "x": 50, "y": 50, "f": 2000},
            {"command": "M5"},
        ])
        result = optimize_gcode_program(prog)
        assert len(result.commands) >= 1


class TestInsertPaintDips:
    def test_disabled_passthrough(self):
        prog = _prog([
            {"command": "M5"},
            {"command": "M3", "s": 1000},
            {"command": "G1", "x": 50, "y": 50, "f": 2000},
            {"command": "M5"},
        ])
        brush = BrushConfig(enabled=False)
        result = insert_paint_dips(prog, brush)
        assert len(result.commands) == len(prog.commands)

    def test_inserts_dip_at_interval(self):
        cmds_data = [{"command": "M5"}]
        for i in range(5):
            cmds_data.extend([
                {"command": "M3", "s": 1000},
                {"command": "G1", "x": i * 10 + 10, "y": i * 10 + 10, "f": 2000},
                {"command": "M5"},
            ])
        prog = _prog(cmds_data)
        brush = BrushConfig(enabled=True, strokes_before_reload=2)
        result = insert_paint_dips(prog, brush)
        # Should have more commands due to dip sequences
        assert len(result.commands) > len(prog.commands)
        # Should have G4 dwell commands (hold in ink)
        g4_cmds = [c for c in result.commands if c.command == "G4"]
        assert len(g4_cmds) > 0


class TestInsertPenDwells:
    def test_adds_dwells_after_m3_m5(self):
        prog = _prog([
            {"command": "M5"},
            {"command": "G0", "x": 10, "y": 10},
            {"command": "M3", "s": 1000},
            {"command": "G1", "x": 50, "y": 50, "f": 2000},
            {"command": "M5"},
        ])
        pen = PenConfig(pen_down_delay=0.2, pen_up_delay=0.2)
        result = insert_pen_dwells(prog, pen)
        g4_cmds = [c for c in result.commands if c.command == "G4"]
        assert len(g4_cmds) >= 2  # At least one after M3 and one after M5

    def test_zero_delay_no_dwells(self):
        prog = _prog([
            {"command": "M5"},
            {"command": "M3", "s": 1000},
            {"command": "G1", "x": 50, "y": 50, "f": 2000},
            {"command": "M5"},
        ])
        pen = PenConfig(pen_down_delay=0.0, pen_up_delay=0.0)
        result = insert_pen_dwells(prog, pen)
        g4_cmds = [c for c in result.commands if c.command == "G4"]
        assert len(g4_cmds) == 0


class TestRunPipeline:
    def test_full_pipeline(self):
        prog = _prog([
            {"command": "M5"},
            {"command": "G0", "x": 10, "y": 10},
            {"command": "M3", "s": 1000},
            {"command": "G1", "x": 50, "y": 50, "f": 2000},
            {"command": "G1", "x": 80, "y": 80, "f": 2000},
            {"command": "M5"},
            {"command": "G0", "x": 0, "y": 0},
        ])
        config = PromptPlotConfig()
        result = run_pipeline(prog, config)
        assert isinstance(result, GCodeProgram)
        assert len(result.commands) > 0
        # Should start with M5 and end with G0 X0 Y0
        assert result.commands[0].command == "M5"

    def test_pipeline_handles_single_command(self):
        prog = _prog([
            {"command": "M5"},
            {"command": "G0", "x": 10, "y": 10},
        ])
        config = PromptPlotConfig()
        result = run_pipeline(prog, config)
        assert isinstance(result, GCodeProgram)
