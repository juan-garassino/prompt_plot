"""Tests for LiveDrawWorkflow — real-time LLM-to-plotter streaming."""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

from promptplot.models import GCodeCommand, GCodeProgram
from promptplot.config import PromptPlotConfig
from promptplot.workflow import LiveDrawWorkflow
from promptplot.plotter import SimulatedPlotter
from promptplot.postprocess import validate_single_command


# ---------------------------------------------------------------------------
# Per-command validation
# ---------------------------------------------------------------------------

class TestValidateSingleCommand:
    def test_in_bounds_passthrough(self):
        cfg = PromptPlotConfig()
        cmd = GCodeCommand(command="G1", x=50, y=50, f=2000)
        fixed, warnings, prefix = validate_single_command(cmd, cfg.paper, pen_is_down=True)
        assert fixed.x == 50
        assert fixed.y == 50
        assert warnings == []
        assert prefix == []

    def test_out_of_bounds_clamped(self):
        cfg = PromptPlotConfig()
        cmd = GCodeCommand(command="G1", x=999, y=-10, f=2000)
        fixed, warnings, prefix = validate_single_command(cmd, cfg.paper, pen_is_down=True)
        assert fixed.x == cfg.paper.width  # clamped to max
        assert fixed.y == 0  # clamped to 0
        assert len(warnings) == 2

    def test_pen_safety_travel_without_pen_up(self):
        cfg = PromptPlotConfig()
        cmd = GCodeCommand(command="G0", x=10, y=10)
        fixed, warnings, prefix = validate_single_command(cmd, cfg.paper, pen_is_down=True)
        # Should insert M5 before the G0
        assert len(prefix) == 1
        assert prefix[0].command == "M5"

    def test_pen_safety_draw_without_pen_down(self):
        cfg = PromptPlotConfig()
        cmd = GCodeCommand(command="G1", x=10, y=10, f=2000)
        fixed, warnings, prefix = validate_single_command(cmd, cfg.paper, pen_is_down=False)
        assert len(prefix) == 1
        assert prefix[0].command == "M3"

    def test_no_prefix_when_pen_state_correct(self):
        cfg = PromptPlotConfig()
        # Pen is up, doing travel → no prefix needed
        cmd = GCodeCommand(command="G0", x=10, y=10)
        fixed, warnings, prefix = validate_single_command(cmd, cfg.paper, pen_is_down=False)
        assert prefix == []

        # Pen is down, doing draw → no prefix needed
        cmd = GCodeCommand(command="G1", x=10, y=10, f=2000)
        fixed, warnings, prefix = validate_single_command(cmd, cfg.paper, pen_is_down=True)
        assert prefix == []

    def test_m3_m5_no_prefix(self):
        cfg = PromptPlotConfig()
        cmd = GCodeCommand(command="M3", s=1000)
        fixed, warnings, prefix = validate_single_command(cmd, cfg.paper, pen_is_down=False)
        assert prefix == []
        assert warnings == []


# ---------------------------------------------------------------------------
# LiveDrawWorkflow with SimulatedPlotter
# ---------------------------------------------------------------------------

class TestLiveDrawWorkflow:
    @pytest.fixture
    def mock_llm(self):
        """LLM that returns a sequence of commands then COMPLETE."""
        llm = AsyncMock()
        responses = [
            json.dumps({"command": "M5"}),
            json.dumps({"command": "G0", "x": 50, "y": 50}),
            json.dumps({"command": "M3", "s": 1000}),
            json.dumps({"command": "G1", "x": 100, "y": 100, "f": 2000}),
            json.dumps({"command": "M5"}),
            json.dumps({"command": "COMPLETE"}),
        ]
        llm.acomplete = AsyncMock(side_effect=responses)
        return llm

    @pytest.mark.asyncio
    async def test_live_draw_basic(self, mock_llm):
        """Live draw should send commands to plotter in real-time."""
        plotter = SimulatedPlotter(command_delay=0)
        await plotter.connect()

        wf = LiveDrawWorkflow(
            llm=mock_llm, plotter=plotter, max_steps=20,
        )
        result = await wf.run("draw a line")

        assert result["success"] is True
        assert result["sent_count"] > 0
        assert result["error_count"] == 0
        # Plotter should have received commands
        assert len(plotter.collected) > 0
        await plotter.disconnect()

    @pytest.mark.asyncio
    async def test_live_draw_ends_with_pen_up_and_home(self, mock_llm):
        """Live draw should always end with M5 + G0 X0 Y0."""
        plotter = SimulatedPlotter(command_delay=0)
        await plotter.connect()

        wf = LiveDrawWorkflow(llm=mock_llm, plotter=plotter, max_steps=20)
        result = await wf.run("draw something")

        cmds = result["commands"]
        # Last two commands should be M5 and G0 X0 Y0
        assert cmds[-2].command == "M5"
        assert cmds[-1].command == "G0"
        assert cmds[-1].x == 0
        assert cmds[-1].y == 0
        await plotter.disconnect()

    @pytest.mark.asyncio
    async def test_live_draw_callback(self, mock_llm):
        """on_step callback should be called for each LLM step."""
        plotter = SimulatedPlotter(command_delay=0)
        await plotter.connect()

        steps_received = []

        async def on_step(step_num, max_s, gcode, ok, warnings):
            steps_received.append((step_num, gcode, ok))

        wf = LiveDrawWorkflow(
            llm=mock_llm, plotter=plotter, max_steps=20,
            on_step=on_step,
        )
        await wf.run("draw a line")

        assert len(steps_received) > 0
        # Last callback should be COMPLETE
        assert steps_received[-1][1] == "COMPLETE"
        await plotter.disconnect()

    @pytest.mark.asyncio
    async def test_live_draw_handles_llm_errors(self):
        """LLM errors should be skipped, not crash the workflow."""
        llm = AsyncMock()
        responses = [
            "not valid json at all",
            json.dumps({"command": "M5"}),
            json.dumps({"command": "COMPLETE"}),
        ]
        llm.acomplete = AsyncMock(side_effect=responses)

        plotter = SimulatedPlotter(command_delay=0)
        await plotter.connect()

        wf = LiveDrawWorkflow(llm=llm, plotter=plotter, max_steps=10)
        result = await wf.run("draw anything")

        assert result["skipped_count"] >= 1
        assert result["sent_count"] > 0  # at least M5 startup + end commands
        await plotter.disconnect()

    @pytest.mark.asyncio
    async def test_live_draw_max_steps_limit(self):
        """Workflow should stop after max_steps even without COMPLETE."""
        llm = AsyncMock()
        # Always return a draw command, never COMPLETE
        llm.acomplete = AsyncMock(
            return_value=json.dumps({"command": "G1", "x": 10, "y": 10, "f": 2000})
        )

        plotter = SimulatedPlotter(command_delay=0)
        await plotter.connect()

        wf = LiveDrawWorkflow(llm=llm, plotter=plotter, max_steps=5)
        result = await wf.run("draw forever")

        # Should have exactly 5 drawing commands + startup M5 + end M5+G0
        assert llm.acomplete.call_count == 5
        await plotter.disconnect()

    @pytest.mark.asyncio
    async def test_live_draw_out_of_bounds_clamped(self):
        """Out-of-bounds commands should be clamped, not rejected."""
        llm = AsyncMock()
        responses = [
            json.dumps({"command": "M5"}),
            json.dumps({"command": "G0", "x": 9999, "y": 9999}),
            json.dumps({"command": "COMPLETE"}),
        ]
        llm.acomplete = AsyncMock(side_effect=responses)

        plotter = SimulatedPlotter(command_delay=0)
        await plotter.connect()

        wf = LiveDrawWorkflow(llm=llm, plotter=plotter, max_steps=10)
        result = await wf.run("draw off screen")

        # Commands should have been sent (clamped, not rejected)
        assert result["sent_count"] > 0
        assert result["error_count"] == 0
        await plotter.disconnect()

    @pytest.mark.asyncio
    async def test_live_draw_returns_gcode_string(self, mock_llm):
        """Result should include a valid gcode string."""
        plotter = SimulatedPlotter(command_delay=0)
        await plotter.connect()

        wf = LiveDrawWorkflow(llm=mock_llm, plotter=plotter, max_steps=20)
        result = await wf.run("draw a line")

        assert isinstance(result["gcode"], str)
        assert len(result["gcode"]) > 0
        assert "G0" in result["gcode"] or "M5" in result["gcode"]
        await plotter.disconnect()

    @pytest.mark.asyncio
    async def test_live_draw_pen_safety_auto_insert(self):
        """Pen safety commands should be auto-inserted when needed."""
        llm = AsyncMock()
        # G1 without prior M3 — should auto-insert M3
        responses = [
            json.dumps({"command": "G1", "x": 50, "y": 50, "f": 2000}),
            json.dumps({"command": "COMPLETE"}),
        ]
        llm.acomplete = AsyncMock(side_effect=responses)

        plotter = SimulatedPlotter(command_delay=0)
        await plotter.connect()

        warnings_seen = []

        async def on_step(step_num, max_s, gcode, ok, warnings):
            warnings_seen.extend(warnings)

        wf = LiveDrawWorkflow(
            llm=llm, plotter=plotter, max_steps=10, on_step=on_step,
        )
        result = await wf.run("draw without pen down")

        # M3 should have been auto-inserted
        m3_cmds = [c for c in result["commands"] if c.command == "M3"]
        assert len(m3_cmds) >= 1
        await plotter.disconnect()
