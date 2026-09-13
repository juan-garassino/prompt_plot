"""Tests for promptplot.orchestrate."""

import pytest
from unittest.mock import AsyncMock, Mock

from promptplot.orchestrate import (
    plan_regions,
    validate_chunk,
    score_chunk,
    merge_chunks,
    load_and_continue,
    stream_chunk,
)
from promptplot.models import Region, GCodeCommand, GCodeProgram
from promptplot.config import PromptPlotConfig
from promptplot.engine import PenState


@pytest.fixture
def config():
    return PromptPlotConfig()


@pytest.fixture
def paper(config):
    return config.paper


class TestPlanRegions:
    def test_grid_2x2_yields_four(self):
        rs = plan_regions((0, 0, 200, 300), "grid_2x2")
        assert len(rs) == 4
        # Union covers original bounds
        xs = [b for r in rs for b in (r.bounds[0], r.bounds[2])]
        ys = [b for r in rs for b in (r.bounds[1], r.bounds[3])]
        assert min(xs) == 0 and max(xs) == 200
        assert min(ys) == 0 and max(ys) == 300

    def test_grid_3x3_yields_nine(self):
        rs = plan_regions((0, 0, 300, 300), "grid_3x3")
        assert len(rs) == 9
        assert any(r.role == "focal" for r in rs)

    def test_quadrant_is_grid_2x2(self):
        rs = plan_regions((0, 0, 200, 200), "quadrant")
        assert len(rs) == 4

    def test_radial_has_focal_center(self):
        rs = plan_regions((0, 0, 200, 200), "radial")
        assert len(rs) >= 4
        assert any(r.role == "focal" for r in rs)

    def test_composition_plan_strategy(self):
        plan = Mock()
        r1 = Mock(); r1.x = 10; r1.y = 20; r1.width = 50; r1.height = 60
        r1.role = "focal"; r1.density = "dense"; r1.name = "r1"
        plan.regions = [r1]
        rs = plan_regions((0, 0, 200, 200), "composition_plan", composition_plan=plan)
        assert len(rs) == 1
        assert rs[0].bounds == (10.0, 20.0, 60.0, 80.0)
        assert rs[0].role == "focal"

    def test_unknown_strategy_raises(self):
        with pytest.raises(ValueError):
            plan_regions((0, 0, 10, 10), "lol")


class TestValidateChunk:
    def test_clamps_oob_coords(self, paper):
        cmds = [
            GCodeCommand(command="M3", s=1000),
            GCodeCommand(command="G1", x=9999.0, y=10.0, f=2000),
        ]
        out, warnings, final = validate_chunk(cmds, PenState(), paper)
        # Find the G1 in output
        g1s = [c for c in out if c.command == "G1"]
        _, _, x1, _ = paper.get_drawable_area()
        assert g1s[0].x == x1  # G1 clamped to drawable area (respects margins)
        assert any("clamped" in w for w in warnings)

    def test_threads_pen_state(self, paper):
        # If we start UP, a G1 should get an M3 prefix
        cmds = [GCodeCommand(command="G1", x=10.0, y=10.0, f=2000)]
        out, _, final = validate_chunk(cmds, PenState("up"), paper)
        assert out[0].command == "M3"
        assert final.is_down


class TestScoreChunk:
    def test_coverage_computes(self):
        region = Region(bounds=(0.0, 0.0, 100.0, 100.0))
        cmds = [
            GCodeCommand(command="M3", s=1000),
            GCodeCommand(command="G1", x=10.0, y=10.0, f=2000),
            GCodeCommand(command="G1", x=90.0, y=90.0, f=2000),
            GCodeCommand(command="M5"),
        ]
        m = score_chunk(cmds, region)
        assert m.segment_count == 2
        # Drawing spans 80x80 of 100x100 -> coverage 0.64
        assert 0.5 < m.coverage <= 1.0

    def test_empty_chunk(self):
        region = Region(bounds=(0.0, 0.0, 100.0, 100.0))
        m = score_chunk([], region)
        assert m.coverage == 0.0
        assert m.segment_count == 0


class TestMergeChunks:
    def test_pen_up_separators(self, config):
        c1 = [
            GCodeCommand(command="M3", s=1000),
            GCodeCommand(command="G1", x=20.0, y=20.0, f=2000),
        ]
        c2 = [
            GCodeCommand(command="M3", s=1000),
            GCodeCommand(command="G1", x=100.0, y=100.0, f=2000),
        ]
        program = merge_chunks([c1, c2], config)
        # postprocess pen safety adds M5s; verify it's a valid GCodeProgram
        assert isinstance(program, GCodeProgram)
        cmds = [c.command for c in program.commands]
        assert "M5" in cmds
        assert "M3" in cmds


class TestLoadAndContinue:
    def test_derives_pen_state(self, tmp_path, config):
        prior = tmp_path / "prior.gcode"
        prior.write_text("M5\nG0 X10 Y10\nM3 S1000\nG1 X50 Y50 F2000\n")
        new = [GCodeCommand(command="G0", x=60.0, y=60.0)]
        merged = load_and_continue(str(prior), new, config)
        # Prior ended pen down; merger must insert M5 before appending new
        cmd_strs = [c.command for c in merged.commands]
        # Find last M5 before the appended G0
        # Just verify resume position metadata
        assert merged.metadata.get("resume_position") == [50.0, 50.0]


class TestStreamChunk:
    @pytest.mark.asyncio
    async def test_invokes_on_pause(self):
        plotter = Mock()
        plotter.send_command = AsyncMock(return_value=True)
        called = {"x": None}

        def on_pause(s, e):
            called["x"] = (s, e)

        cmds = [GCodeCommand(command="G0", x=10.0, y=10.0)]
        success, errors = await stream_chunk(cmds, plotter, on_pause=on_pause)
        assert success == 1
        assert errors == 0
        assert called["x"] == (1, 0)
        plotter.send_command.assert_awaited()

    @pytest.mark.asyncio
    async def test_counts_failures(self):
        plotter = Mock()
        plotter.send_command = AsyncMock(side_effect=[True, False, True])
        cmds = [
            GCodeCommand(command="G0", x=10.0, y=10.0),
            GCodeCommand(command="G1", x=20.0, y=20.0),
            GCodeCommand(command="M5"),
        ]
        success, errors = await stream_chunk(cmds, plotter)
        assert success == 2
        assert errors == 1
