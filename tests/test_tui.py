"""Tests for the TUI module — layout builders and state management."""

import pytest
from rich.panel import Panel
from rich.layout import Layout

from promptplot.config import PromptPlotConfig
from promptplot.tui import TUIState, _header, _command_log, _footer, _build_layout


class TestTUIState:
    def test_default_state(self):
        state = TUIState(PromptPlotConfig())
        assert state.phase == "idle"
        assert state.connected is False
        assert state.sent == 0
        assert state.grade == "-"

    def test_paper_string(self):
        state = TUIState(PromptPlotConfig())
        assert "210" in state.paper
        assert "297" in state.paper


class TestLayoutBuilders:
    @pytest.fixture
    def state(self):
        return TUIState(PromptPlotConfig())

    def test_header_idle(self, state):
        panel = _header(state)
        assert isinstance(panel, Panel)

    def test_header_connected(self, state):
        state.connected = True
        state.plotter_port = "/dev/test"
        panel = _header(state)
        assert isinstance(panel, Panel)

    def test_command_log_empty(self, state):
        panel = _command_log(state)
        assert isinstance(panel, Panel)

    def test_command_log_with_entries(self, state):
        state.commands.append((1, "M5", "ok", []))
        state.commands.append((2, "G0 X10 Y10", "ok", []))
        state.commands.append((3, "G1 X50 Y50 F2000", "err", ["bounds"]))
        state.sent = 2
        state.errors = 1
        panel = _command_log(state)
        assert isinstance(panel, Panel)

    def test_footer_idle(self, state):
        panel = _footer(state)
        assert isinstance(panel, Panel)

    def test_footer_generating(self, state):
        state.phase = "generating"
        state.elapsed = 3.5
        panel = _footer(state)
        assert isinstance(panel, Panel)

    def test_footer_done(self, state):
        state.phase = "done"
        state.grade = "B"
        state.utilization = 0.65
        state.strokes = 12
        state.draw_travel = 3.2
        state.elapsed = 8.1
        panel = _footer(state)
        assert isinstance(panel, Panel)

    def test_build_layout(self, state):
        layout = _build_layout(state)
        assert isinstance(layout, Layout)

    def test_build_layout_streaming(self, state):
        state.phase = "streaming"
        state.connected = True
        state.sent = 15
        for i in range(20):
            state.commands.append((i, f"G1 X{i*5} Y{i*5} F2000", "ok", []))
        layout = _build_layout(state)
        assert isinstance(layout, Layout)
