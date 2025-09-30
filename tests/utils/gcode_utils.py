"""
Utilities for G-code testing and validation.
"""
from typing import List, Dict, Any, Tuple, Optional
import re
import math

from promptplot.core.models import GCodeCommand, GCodeProgram


class GCodeTestValidator:
    """Validator for G-code commands in tests."""
    
    VALID_COMMANDS = {
        'G0', 'G1', 'G2', 'G3', 'G4', 'G28', 'G90', 'G91',
        'M3', 'M5', 'M17', 'M18', 'M84', 'M104', 'M109'
    }
    
    @classmethod
    def validate_command(cls, command: GCodeCommand) -> Tuple[bool, List[str]]:
        """Validate a single G-code command."""
        errors = []
        
        # Check command format
        if not command.command:
            errors.append("Command cannot be empty")
            return False, errors
            
        # Check if command is recognized
        cmd = command.command.upper()
        if cmd not in cls.VALID_COMMANDS:
            errors.append(f"Unknown command: {cmd}")
            
        # Validate coordinates
        if command.x is not None and not isinstance(command.x, (int, float)):
            errors.append("X coordinate must be numeric")
            
        if command.y is not None and not isinstance(command.y, (int, float)):
            errors.append("Y coordinate must be numeric")
            
        if command.z is not None and not isinstance(command.z, (int, float)):
            errors.append("Z coordinate must be numeric")
            
        # Validate feed rate
        if command.f is not None:
            if not isinstance(command.f, (int, float)) or command.f <= 0:
                errors.append("Feed rate must be positive numeric value")
                
        # Validate spindle speed
        if command.s is not None:
            if not isinstance(command.s, (int, float)) or command.s < 0:
                errors.append("Spindle speed must be non-negative numeric value")
                
        return len(errors) == 0, errors
        
    @classmethod
    def validate_program(cls, program: GCodeProgram) -> Tuple[bool, List[str]]:
        """Validate a complete G-code program."""
        errors = []
        
        if not program.commands:
            errors.append("Program cannot be empty")
            return False, errors
            
        # Validate each command
        for i, command in enumerate(program.commands):
            is_valid, cmd_errors = cls.validate_command(command)
            if not is_valid:
                for error in cmd_errors:
                    errors.append(f"Command {i}: {error}")
                    
        # Check for logical sequence
        has_home = any(cmd.command.upper() == 'G28' for cmd in program.commands)
        if not has_home:
            errors.append("Program should include homing command (G28)")
            
        return len(errors) == 0, errors


class GCodeComparator:
    """Compare G-code programs for testing."""
    
    @staticmethod
    def commands_equal(cmd1: GCodeCommand, cmd2: GCodeCommand, tolerance: float = 0.001) -> bool:
        """Check if two commands are equal within tolerance."""
        if cmd1.command.upper() != cmd2.command.upper():
            return False
            
        # Compare coordinates with tolerance
        for attr in ['x', 'y', 'z']:
            val1 = getattr(cmd1, attr)
            val2 = getattr(cmd2, attr)
            
            if val1 is None and val2 is None:
                continue
            if val1 is None or val2 is None:
                return False
            if abs(val1 - val2) > tolerance:
                return False
                
        # Compare other parameters exactly
        for attr in ['f', 's', 'p']:
            if getattr(cmd1, attr) != getattr(cmd2, attr):
                return False
                
        return True
        
    @classmethod
    def programs_equal(cls, prog1: GCodeProgram, prog2: GCodeProgram, tolerance: float = 0.001) -> bool:
        """Check if two programs are equal within tolerance."""
        if len(prog1.commands) != len(prog2.commands):
            return False
            
        for cmd1, cmd2 in zip(prog1.commands, prog2.commands):
            if not cls.commands_equal(cmd1, cmd2, tolerance):
                return False
                
        return True
        
    @classmethod
    def find_differences(cls, prog1: GCodeProgram, prog2: GCodeProgram, tolerance: float = 0.001) -> List[Dict[str, Any]]:
        """Find differences between two programs."""
        differences = []
        
        max_len = max(len(prog1.commands), len(prog2.commands))
        
        for i in range(max_len):
            cmd1 = prog1.commands[i] if i < len(prog1.commands) else None
            cmd2 = prog2.commands[i] if i < len(prog2.commands) else None
            
            if cmd1 is None:
                differences.append({
                    "index": i,
                    "type": "missing_in_first",
                    "command": cmd2.command if cmd2 else None
                })
            elif cmd2 is None:
                differences.append({
                    "index": i,
                    "type": "missing_in_second", 
                    "command": cmd1.command if cmd1 else None
                })
            elif not cls.commands_equal(cmd1, cmd2, tolerance):
                differences.append({
                    "index": i,
                    "type": "different",
                    "first": cmd1.dict(),
                    "second": cmd2.dict()
                })
                
        return differences


class GCodeAnalyzer:
    """Analyze G-code programs for testing."""
    
    @staticmethod
    def calculate_drawing_bounds(program: GCodeProgram) -> Dict[str, float]:
        """Calculate the bounding box of a drawing."""
        x_coords = []
        y_coords = []
        
        for command in program.commands:
            if command.x is not None:
                x_coords.append(command.x)
            if command.y is not None:
                y_coords.append(command.y)
                
        if not x_coords or not y_coords:
            return {"min_x": 0, "max_x": 0, "min_y": 0, "max_y": 0, "width": 0, "height": 0}
            
        min_x, max_x = min(x_coords), max(x_coords)
        min_y, max_y = min(y_coords), max(y_coords)
        
        return {
            "min_x": min_x,
            "max_x": max_x,
            "min_y": min_y,
            "max_y": max_y,
            "width": max_x - min_x,
            "height": max_y - min_y
        }
        
    @staticmethod
    def calculate_total_distance(program: GCodeProgram) -> float:
        """Calculate total drawing distance."""
        total_distance = 0.0
        current_x, current_y = 0.0, 0.0
        
        for command in program.commands:
            if command.command.upper() in ['G0', 'G1'] and command.x is not None and command.y is not None:
                distance = math.sqrt((command.x - current_x)**2 + (command.y - current_y)**2)
                total_distance += distance
                current_x, current_y = command.x, command.y
                
        return total_distance
        
    @staticmethod
    def count_pen_movements(program: GCodeProgram) -> Dict[str, int]:
        """Count pen up/down movements."""
        pen_down_count = 0
        pen_up_count = 0
        
        for command in program.commands:
            if command.command.upper() == 'M3':
                pen_down_count += 1
            elif command.command.upper() == 'M5':
                pen_up_count += 1
                
        return {
            "pen_down": pen_down_count,
            "pen_up": pen_up_count
        }
        
    @staticmethod
    def analyze_complexity(program: GCodeProgram) -> Dict[str, Any]:
        """Analyze drawing complexity."""
        move_commands = sum(1 for cmd in program.commands if cmd.command.upper() in ['G0', 'G1'])
        curve_commands = sum(1 for cmd in program.commands if cmd.command.upper() in ['G2', 'G3'])
        
        bounds = GCodeAnalyzer.calculate_drawing_bounds(program)
        distance = GCodeAnalyzer.calculate_total_distance(program)
        pen_movements = GCodeAnalyzer.count_pen_movements(program)
        
        return {
            "total_commands": len(program.commands),
            "move_commands": move_commands,
            "curve_commands": curve_commands,
            "bounds": bounds,
            "total_distance": distance,
            "pen_movements": pen_movements,
            "complexity_score": (move_commands + curve_commands * 2) / len(program.commands) if program.commands else 0
        }


def create_test_gcode_program(pattern: str = "simple") -> GCodeProgram:
    """Create test G-code programs for various patterns."""
    if pattern == "simple":
        commands = [
            GCodeCommand(command="G28", comment="Home"),
            GCodeCommand(command="G1", x=10.0, y=10.0, f=1000, comment="Move to start"),
            GCodeCommand(command="M3", s=255, comment="Pen down"),
            GCodeCommand(command="G1", x=20.0, y=20.0, f=1000, comment="Draw line"),
            GCodeCommand(command="M5", comment="Pen up"),
            GCodeCommand(command="G28", comment="Return home")
        ]
    elif pattern == "rectangle":
        commands = [
            GCodeCommand(command="G28"),
            GCodeCommand(command="G1", x=0.0, y=0.0, f=1000),
            GCodeCommand(command="M3", s=255),
            GCodeCommand(command="G1", x=10.0, y=0.0, f=1000),
            GCodeCommand(command="G1", x=10.0, y=5.0, f=1000),
            GCodeCommand(command="G1", x=0.0, y=5.0, f=1000),
            GCodeCommand(command="G1", x=0.0, y=0.0, f=1000),
            GCodeCommand(command="M5"),
            GCodeCommand(command="G28")
        ]
    elif pattern == "circle":
        commands = [
            GCodeCommand(command="G28"),
            GCodeCommand(command="G1", x=5.0, y=0.0, f=1000),
            GCodeCommand(command="M3", s=255),
            GCodeCommand(command="G2", x=5.0, y=0.0, i=-5.0, j=0.0, f=1000),
            GCodeCommand(command="M5"),
            GCodeCommand(command="G28")
        ]
    else:
        commands = [GCodeCommand(command="G28")]
        
    return GCodeProgram(
        commands=commands,
        metadata={"pattern": pattern, "test": True}
    )