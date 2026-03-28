"""Tests for bounds validation."""

import pytest

from promptplot.models import GCodeCommand, GCodeProgram
from promptplot.config import PaperConfig
from promptplot.postprocess import validate_bounds


def _make_program(commands_data):
    """Helper to create a GCodeProgram from dicts."""
    commands = [GCodeCommand(**c) for c in commands_data]
    return GCodeProgram(commands=commands)


class TestValidateBounds:
    def test_all_in_bounds_unchanged(self):
        """All-in-bounds program should pass through unchanged."""
        program = _make_program([
            {"command": "M5"},
            {"command": "G0", "x": 50, "y": 50},
            {"command": "M3", "s": 1000},
            {"command": "G1", "x": 100, "y": 100, "f": 2000},
            {"command": "M5"},
            {"command": "G0", "x": 0, "y": 0},
        ])
        paper = PaperConfig(width=210, height=297)
        result, violations = validate_bounds(program, paper)
        assert len(violations) == 0
        assert len(result.commands) == len(program.commands)

    def test_out_of_bounds_x_clamp(self):
        """Out-of-bounds X in clamp mode should be clamped to paper width."""
        program = _make_program([
            {"command": "M5"},
            {"command": "G1", "x": 500, "y": 50, "f": 2000},
            {"command": "M5"},
        ])
        paper = PaperConfig(width=210, height=297)
        result, violations = validate_bounds(program, paper, mode="clamp")
        assert len(violations) > 0
        # The G1 command should be clamped
        g1_cmd = [c for c in result.commands if c.command == "G1"][0]
        assert g1_cmd.x == 210.0

    def test_out_of_bounds_y_clamp(self):
        """Out-of-bounds Y in clamp mode should be clamped."""
        program = _make_program([
            {"command": "M5"},
            {"command": "G1", "x": 50, "y": 500, "f": 2000},
            {"command": "M5"},
        ])
        paper = PaperConfig(width=210, height=297)
        result, violations = validate_bounds(program, paper, mode="clamp")
        g1_cmd = [c for c in result.commands if c.command == "G1"][0]
        assert g1_cmd.y == 297.0

    def test_negative_coordinates_clamp(self):
        """Negative coordinates should be clamped to 0."""
        program = _make_program([
            {"command": "M5"},
            {"command": "G1", "x": -10, "y": -20, "f": 2000},
            {"command": "M5"},
        ])
        paper = PaperConfig(width=210, height=297)
        result, violations = validate_bounds(program, paper, mode="clamp")
        g1_cmd = [c for c in result.commands if c.command == "G1"][0]
        assert g1_cmd.x == 0.0
        assert g1_cmd.y == 0.0

    def test_out_of_bounds_reject_mode(self):
        """Out-of-bounds command in reject mode should be removed."""
        program = _make_program([
            {"command": "M5"},
            {"command": "G1", "x": 500, "y": 50, "f": 2000},
            {"command": "G1", "x": 50, "y": 50, "f": 2000},
            {"command": "M5"},
        ])
        paper = PaperConfig(width=210, height=297)
        result, violations = validate_bounds(program, paper, mode="reject")
        assert len(violations) > 0
        # The out-of-bounds G1 should be removed
        g1_cmds = [c for c in result.commands if c.command == "G1"]
        assert len(g1_cmds) == 1
        assert g1_cmds[0].x == 50

    def test_out_of_bounds_warn_mode(self):
        """Warn mode should keep commands but report violations."""
        program = _make_program([
            {"command": "M5"},
            {"command": "G1", "x": 500, "y": 50, "f": 2000},
            {"command": "M5"},
        ])
        paper = PaperConfig(width=210, height=297)
        result, violations = validate_bounds(program, paper, mode="warn")
        assert len(violations) > 0
        # Command should still be present with original coordinates
        g1_cmd = [c for c in result.commands if c.command == "G1"][0]
        assert g1_cmd.x == 500

    def test_exactly_at_boundary(self):
        """Coordinates exactly at paper boundary should pass."""
        program = _make_program([
            {"command": "M5"},
            {"command": "G0", "x": 0, "y": 0},
            {"command": "M3", "s": 1000},
            {"command": "G1", "x": 210, "y": 297, "f": 2000},
            {"command": "M5"},
        ])
        paper = PaperConfig(width=210, height=297)
        result, violations = validate_bounds(program, paper)
        assert len(violations) == 0

    def test_commands_without_coordinates(self):
        """Commands without X/Y (M3, M5) should pass through unchanged."""
        program = _make_program([
            {"command": "M5"},
            {"command": "M3", "s": 1000},
            {"command": "M5"},
        ])
        paper = PaperConfig(width=210, height=297)
        result, violations = validate_bounds(program, paper)
        assert len(violations) == 0
        assert len(result.commands) == 3

    def test_metadata_records_violations(self):
        """Metadata should record violation count and mode."""
        program = _make_program([
            {"command": "M5"},
            {"command": "G1", "x": 500, "y": 50, "f": 2000},
            {"command": "M5"},
        ])
        paper = PaperConfig(width=210, height=297)
        result, _ = validate_bounds(program, paper, mode="clamp")
        assert result.metadata["bounds_violations"] > 0
        assert result.metadata["bounds_mode"] == "clamp"

    def test_reject_all_creates_fallback(self):
        """If all commands are rejected, a minimal fallback program is created."""
        program = _make_program([
            {"command": "G1", "x": 500, "y": 500, "f": 2000},
        ])
        paper = PaperConfig(width=210, height=297)
        result, violations = validate_bounds(program, paper, mode="reject")
        assert len(result.commands) >= 1  # Should have fallback commands
