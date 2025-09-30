"""
Unit tests for core models (GCodeCommand, GCodeProgram).
"""
import pytest
from pydantic import ValidationError
from typing import List

from promptplot.core.models import GCodeCommand, GCodeProgram
from tests.conftest import assert_valid_gcode_command, assert_valid_gcode_program


class TestGCodeCommand:
    """Test GCodeCommand model."""
    
    @pytest.mark.unit
    def test_create_basic_command(self):
        """Test creating a basic G-code command."""
        cmd = GCodeCommand(command="G1", x=10.0, y=20.0, f=1000)
        
        assert cmd.command == "G1"
        assert cmd.x == 10.0
        assert cmd.y == 20.0
        assert cmd.f == 1000
        assert cmd.z is None
        assert cmd.s is None
        assert cmd.p is None
        
    @pytest.mark.unit
    def test_create_command_with_all_parameters(self):
        """Test creating command with all parameters."""
        cmd = GCodeCommand(
            command="G1",
            x=10.5,
            y=20.5,
            z=5.0,
            f=1500,
            s=255,
            p=100,
            confidence_score=0.8
        )
        
        assert cmd.command == "G1"
        assert cmd.x == 10.5
        assert cmd.y == 20.5
        assert cmd.z == 5.0
        assert cmd.f == 1500
        assert cmd.s == 255
        assert cmd.p == 100
        assert cmd.confidence_score == 0.8
        
    @pytest.mark.unit
    def test_command_validation(self):
        """Test command validation."""
        # Valid commands
        valid_commands = ["G0", "G1", "G28", "M3", "M5"]
        for cmd in valid_commands:
            command = GCodeCommand(command=cmd)
            assert command.command == cmd
            
    @pytest.mark.unit
    def test_invalid_command_empty(self):
        """Test validation fails for empty command."""
        with pytest.raises(ValidationError):
            GCodeCommand(command="")
            
    @pytest.mark.unit
    def test_coordinate_validation(self):
        """Test coordinate validation."""
        # Valid coordinates
        cmd = GCodeCommand(command="G1", x=0.0, y=-10.5, z=100.0)
        assert cmd.x == 0.0
        assert cmd.y == -10.5
        assert cmd.z == 100.0
        
        # Test with integers (should be converted to float)
        cmd = GCodeCommand(command="G1", x=10, y=20)
        assert isinstance(cmd.x, float)
        assert isinstance(cmd.y, float)
        
    @pytest.mark.unit
    def test_feed_rate_validation(self):
        """Test feed rate validation."""
        # Valid feed rates (integers only)
        cmd = GCodeCommand(command="G1", f=1000)
        assert cmd.f == 1000
        
        cmd = GCodeCommand(command="G1", f=500)
        assert cmd.f == 500
        
    @pytest.mark.unit
    def test_spindle_speed_validation(self):
        """Test spindle speed validation."""
        # Valid spindle speeds
        cmd = GCodeCommand(command="M3", s=255)
        assert cmd.s == 255
        
        cmd = GCodeCommand(command="M3", s=0)
        assert cmd.s == 0
        
    @pytest.mark.unit
    def test_command_serialization(self):
        """Test command serialization to dict."""
        cmd = GCodeCommand(
            command="G1",
            x=10.0,
            y=20.0,
            f=1000,
            confidence_score=0.9
        )
        
        data = cmd.model_dump()
        assert data["command"] == "G1"
        assert data["x"] == 10.0
        assert data["y"] == 20.0
        assert data["f"] == 1000
        assert data["confidence_score"] == 0.9
        
    @pytest.mark.unit
    def test_command_json_serialization(self):
        """Test command JSON serialization."""
        cmd = GCodeCommand(command="G1", x=10.0, y=20.0, f=1000)
        json_str = cmd.model_dump_json()
        
        assert "G1" in json_str
        assert "10.0" in json_str
        assert "20.0" in json_str
        assert "1000" in json_str
        
    @pytest.mark.unit
    def test_command_from_dict(self):
        """Test creating command from dictionary."""
        data = {
            "command": "G1",
            "x": 15.0,
            "y": 25.0,
            "f": 1200,
            "confidence_score": 0.7
        }
        
        cmd = GCodeCommand(**data)
        assert cmd.command == "G1"
        assert cmd.x == 15.0
        assert cmd.y == 25.0
        assert cmd.f == 1200
        assert cmd.confidence_score == 0.7
        
    @pytest.mark.unit
    def test_command_equality(self):
        """Test command equality comparison."""
        cmd1 = GCodeCommand(command="G1", x=10.0, y=20.0, f=1000)
        cmd2 = GCodeCommand(command="G1", x=10.0, y=20.0, f=1000)
        cmd3 = GCodeCommand(command="G1", x=15.0, y=20.0, f=1000)
        
        assert cmd1 == cmd2
        assert cmd1 != cmd3
        
    @pytest.mark.unit
    def test_command_string_representation(self):
        """Test command string representation."""
        cmd = GCodeCommand(command="G1", x=10.0, y=20.0, f=1000)
        str_repr = str(cmd)
        
        assert "G1" in str_repr
        assert "10.0" in str_repr
        assert "20.0" in str_repr


class TestGCodeProgram:
    """Test GCodeProgram model."""
    
    @pytest.mark.unit
    def test_create_program_with_single_command(self):
        """Test creating program with single command."""
        cmd = GCodeCommand(command="G28")
        program = GCodeProgram(commands=[cmd])
        assert len(program.commands) == 1
        assert program.metadata == {}
        
    @pytest.mark.unit
    def test_create_program_with_commands(self, sample_gcode_commands):
        """Test creating program with commands."""
        program = GCodeProgram(commands=sample_gcode_commands)
        
        assert len(program.commands) == len(sample_gcode_commands)
        for i, cmd in enumerate(program.commands):
            assert cmd == sample_gcode_commands[i]
            
    @pytest.mark.unit
    def test_create_program_with_metadata(self, sample_gcode_commands):
        """Test creating program with metadata."""
        metadata = {
            "title": "Test Drawing",
            "description": "A test drawing",
            "created_by": "test_suite",
            "version": "1.0"
        }
        
        program = GCodeProgram(commands=sample_gcode_commands, metadata=metadata)
        
        assert program.metadata == metadata
        assert program.metadata["title"] == "Test Drawing"
        
    @pytest.mark.unit
    def test_program_validation(self):
        """Test program validation."""
        # Valid program
        commands = [
            GCodeCommand(command="G28"),
            GCodeCommand(command="G1", x=10.0, y=20.0, f=1000),
            GCodeCommand(command="M3", s=255),
            GCodeCommand(command="M5")
        ]
        
        program = GCodeProgram(commands=commands)
        assert_valid_gcode_program(program)
        
    @pytest.mark.unit
    def test_program_serialization(self, sample_gcode_program):
        """Test program serialization."""
        data = sample_gcode_program.model_dump()
        
        assert "commands" in data
        assert "metadata" in data
        assert len(data["commands"]) == len(sample_gcode_program.commands)
        
    @pytest.mark.unit
    def test_program_json_serialization(self, sample_gcode_program):
        """Test program JSON serialization."""
        json_str = sample_gcode_program.model_dump_json()
        
        assert "commands" in json_str
        assert "metadata" in json_str
        
    @pytest.mark.unit
    def test_add_command_to_program(self):
        """Test adding commands to program."""
        cmd1 = GCodeCommand(command="G28")
        program = GCodeProgram(commands=[cmd1])
        
        cmd2 = GCodeCommand(command="G1", x=10.0, y=20.0, f=1000)
        
        # Add commands (note: this would require implementing an add method)
        program.commands.append(cmd2)
        
        assert len(program.commands) == 2
        assert program.commands[0] == cmd1
        assert program.commands[1] == cmd2
        
    @pytest.mark.unit
    def test_program_from_dict(self):
        """Test creating program from dictionary."""
        data = {
            "commands": [
                {"command": "G28"},
                {"command": "G1", "x": 10.0, "y": 20.0, "f": 1000},
                {"command": "M3", "s": 255}
            ],
            "metadata": {
                "title": "Test",
                "description": "Test program"
            }
        }
        
        program = GCodeProgram(**data)
        
        assert len(program.commands) == 3
        assert program.commands[0].command == "G28"
        assert program.commands[1].x == 10.0
        assert program.commands[2].s == 255
        assert program.metadata["title"] == "Test"
        
    @pytest.mark.unit
    def test_program_equality(self, sample_gcode_commands):
        """Test program equality."""
        metadata = {"title": "Test"}
        
        program1 = GCodeProgram(commands=sample_gcode_commands, metadata=metadata)
        program2 = GCodeProgram(commands=sample_gcode_commands, metadata=metadata)
        program3 = GCodeProgram(commands=sample_gcode_commands[:-1], metadata=metadata)
        
        assert program1 == program2
        assert program1 != program3
        
    @pytest.mark.unit
    def test_program_iteration(self, sample_gcode_program):
        """Test iterating over program commands."""
        commands = list(sample_gcode_program.commands)
        
        for i, cmd in enumerate(sample_gcode_program.commands):
            assert cmd == commands[i]
            
    @pytest.mark.unit
    def test_program_length(self, sample_gcode_program):
        """Test getting program length."""
        assert len(sample_gcode_program.commands) > 0
        
    @pytest.mark.unit
    def test_program_indexing(self, sample_gcode_program):
        """Test accessing commands by index."""
        first_cmd = sample_gcode_program.commands[0]
        last_cmd = sample_gcode_program.commands[-1]
        
        assert isinstance(first_cmd, GCodeCommand)
        assert isinstance(last_cmd, GCodeCommand)