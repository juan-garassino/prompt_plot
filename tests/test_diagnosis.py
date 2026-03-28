"""Tests for diagnostic retry in promptplot/workflow.py."""

import pytest
from promptplot.models import GCodeCommand, GCodeProgram
from promptplot.config import PromptPlotConfig
from promptplot.workflow import diagnose_failure


def _prog(data):
    return GCodeProgram(commands=[GCodeCommand(**c) for c in data])


@pytest.fixture
def config():
    return PromptPlotConfig()


class TestDiagnoseFailure:
    def test_too_few_commands(self, config):
        prog = _prog([
            {"command": "M5"},
            {"command": "G0", "x": 10, "y": 10},
        ])
        msg = diagnose_failure(prog, config)
        assert "at least 30" in msg.lower() or "only 2" in msg

    def test_out_of_bounds(self, config):
        prog = _prog([
            {"command": "M5"},
            {"command": "G1", "x": 500, "y": 500, "f": 2000},
            {"command": "M5"},
        ])
        msg = diagnose_failure(prog, config)
        assert "X=500" in msg or "out" in msg.lower()

    def test_missing_pen_commands(self, config):
        # Program with no M3 or M5
        prog = _prog([
            {"command": "G0", "x": 10, "y": 10},
            {"command": "G1", "x": 50, "y": 50, "f": 2000},
        ])
        msg = diagnose_failure(prog, config)
        assert "M5" in msg or "M3" in msg

    def test_no_drawing_commands(self, config):
        prog = _prog([
            {"command": "M5"},
            {"command": "G0", "x": 10, "y": 10},
            {"command": "G0", "x": 50, "y": 50},
            {"command": "M5"},
        ])
        msg = diagnose_failure(prog, config)
        assert "G1" in msg or "drawing" in msg.lower()

    def test_with_error_message(self, config):
        msg = diagnose_failure(None, config, error="Invalid JSON")
        assert "Invalid JSON" in msg

    def test_none_program(self, config):
        msg = diagnose_failure(None, config)
        assert len(msg) > 0
