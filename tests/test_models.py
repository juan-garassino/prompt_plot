"""Tests for promptplot/models.py — GCodeCommand, GCodeProgram, WorkflowResult."""

import pytest
from promptplot.models import GCodeCommand, GCodeProgram, WorkflowResult


class TestGCodeCommand:
    def test_from_string_g1(self):
        cmd = GCodeCommand.from_string("G1 X10 Y20 F3000")
        assert cmd.command == "G1"
        assert cmd.x == 10.0
        assert cmd.y == 20.0
        assert cmd.f == 3000

    def test_from_string_g0(self):
        cmd = GCodeCommand.from_string("G0 X5 Y5")
        assert cmd.command == "G0"
        assert cmd.x == 5.0
        assert cmd.y == 5.0

    def test_from_string_m3_with_s(self):
        cmd = GCodeCommand.from_string("M3 S1000")
        assert cmd.command == "M3"
        assert cmd.s == 1000

    def test_from_string_m5(self):
        cmd = GCodeCommand.from_string("M5")
        assert cmd.command == "M5"

    def test_from_string_with_comment(self):
        cmd = GCodeCommand.from_string("G1 X50 Y30 F2000 ; move to center")
        assert cmd.command == "G1"
        assert cmd.x == 50.0
        assert cmd.comment == "move to center"

    def test_to_gcode_roundtrip(self):
        cmd = GCodeCommand(command="G1", x=10.0, y=20.0, f=3000)
        text = cmd.to_gcode()
        assert "G1" in text
        assert "X10.000" in text
        assert "Y20.000" in text
        assert "F3000" in text

    def test_to_gcode_m3(self):
        cmd = GCodeCommand(command="M3", s=1000)
        assert "M3" in cmd.to_gcode()
        assert "S1000" in cmd.to_gcode()

    def test_to_gcode_complete(self):
        cmd = GCodeCommand(command="COMPLETE")
        assert cmd.to_gcode() == "COMPLETE"

    def test_invalid_command_rejected(self):
        with pytest.raises(Exception):
            GCodeCommand(command="INVALID")

    def test_is_movement(self):
        assert GCodeCommand(command="G0", x=0, y=0).is_movement_command()
        assert GCodeCommand(command="G1", x=0, y=0, f=2000).is_movement_command()
        assert not GCodeCommand(command="M3", s=1000).is_movement_command()

    def test_is_pen_command(self):
        assert GCodeCommand(command="M3", s=1000).is_pen_command()
        assert GCodeCommand(command="M5").is_pen_command()
        assert not GCodeCommand(command="G0", x=0, y=0).is_pen_command()

    def test_is_pen_down_up(self):
        assert GCodeCommand(command="M3", s=1000).is_pen_down()
        assert GCodeCommand(command="M5").is_pen_up()

    def test_is_dwell(self):
        assert GCodeCommand(command="G4", p=200).is_dwell()
        assert not GCodeCommand(command="G1", x=0, y=0, f=2000).is_dwell()

    def test_from_string_empty_line(self):
        cmd = GCodeCommand.from_string("")
        assert cmd.command == "G0"

    def test_from_string_comment_only(self):
        cmd = GCodeCommand.from_string("; just a comment")
        assert cmd.command == "G0"
        assert cmd.comment == "just a comment"

    def test_g4_dwell(self):
        cmd = GCodeCommand.from_string("G4 P500")
        assert cmd.command == "G4"
        assert cmd.p == 500


class TestGCodeProgram:
    def test_construction(self):
        cmds = [GCodeCommand(command="M5"), GCodeCommand(command="G0", x=10, y=10)]
        prog = GCodeProgram(commands=cmds)
        assert len(prog.commands) == 2

    def test_empty_program_rejected(self):
        with pytest.raises(Exception):
            GCodeProgram(commands=[])

    def test_to_gcode(self):
        cmds = [
            GCodeCommand(command="M5"),
            GCodeCommand(command="G0", x=10, y=10),
        ]
        prog = GCodeProgram(commands=cmds)
        text = prog.to_gcode()
        assert "M5" in text
        assert "\n" in text

    def test_get_bounds(self):
        cmds = [
            GCodeCommand(command="M5"),
            GCodeCommand(command="G0", x=10, y=20),
            GCodeCommand(command="G1", x=100, y=200, f=2000),
        ]
        prog = GCodeProgram(commands=cmds)
        bounds = prog.get_bounds()
        assert bounds is not None
        assert bounds["min_x"] == 10.0
        assert bounds["max_x"] == 100.0
        assert bounds["min_y"] == 20.0
        assert bounds["max_y"] == 200.0

    def test_get_bounds_no_movement(self):
        cmds = [GCodeCommand(command="M5"), GCodeCommand(command="M3", s=1000)]
        prog = GCodeProgram(commands=cmds)
        assert prog.get_bounds() is None

    def test_get_drawing_commands(self):
        cmds = [
            GCodeCommand(command="M5"),
            GCodeCommand(command="G0", x=10, y=10),
            GCodeCommand(command="M3", s=1000),
            GCodeCommand(command="G1", x=50, y=50, f=2000),
            GCodeCommand(command="G1", x=80, y=80, f=2000),
            GCodeCommand(command="M5"),
            GCodeCommand(command="G1", x=90, y=90, f=2000),  # pen is up, not a drawing cmd
        ]
        prog = GCodeProgram(commands=cmds)
        drawing = prog.get_drawing_commands()
        assert len(drawing) == 2
        assert drawing[0].x == 50.0
        assert drawing[1].x == 80.0

    def test_get_movement_commands(self):
        cmds = [
            GCodeCommand(command="M5"),
            GCodeCommand(command="G0", x=10, y=10),
            GCodeCommand(command="M3", s=1000),
            GCodeCommand(command="G1", x=50, y=50, f=2000),
        ]
        prog = GCodeProgram(commands=cmds)
        moves = prog.get_movement_commands()
        assert len(moves) == 2

    def test_count_by_command_type(self):
        cmds = [
            GCodeCommand(command="M5"),
            GCodeCommand(command="G0", x=10, y=10),
            GCodeCommand(command="M3", s=1000),
            GCodeCommand(command="G1", x=50, y=50, f=2000),
            GCodeCommand(command="G1", x=80, y=80, f=2000),
            GCodeCommand(command="M5"),
        ]
        prog = GCodeProgram(commands=cmds)
        counts = prog.count_by_command_type()
        assert counts["M5"] == 2
        assert counts["G1"] == 2
        assert counts["G0"] == 1
        assert counts["M3"] == 1

    def test_metadata(self):
        cmds = [GCodeCommand(command="M5")]
        prog = GCodeProgram(commands=cmds, metadata={"source": "test"})
        assert prog.metadata["source"] == "test"


class TestWorkflowResult:
    def test_construction(self):
        result = WorkflowResult(
            success=True,
            prompt="draw a square",
            commands_count=10,
            gcode="G0 X0 Y0",
            timestamp="2024-01-01 00:00:00",
        )
        assert result.success is True
        assert result.prompt == "draw a square"
        assert result.commands_count == 10

    def test_to_dict(self):
        result = WorkflowResult(
            success=True,
            prompt="test",
            commands_count=5,
            gcode="M5",
            timestamp="2024-01-01",
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["commands_count"] == 5

    def test_error_result(self):
        result = WorkflowResult(
            success=False,
            prompt="test",
            commands_count=0,
            gcode="",
            timestamp="2024-01-01",
            error_message="LLM timeout",
        )
        assert result.success is False
        assert result.error_message == "LLM timeout"
