"""
G-code file loading and processing utilities

This module provides functionality for loading, validating, and processing
G-code files for direct plotting, including support for different G-code
dialects and coordinate systems.
"""

import re
import os
from pathlib import Path
from typing import List, Dict, Optional, Union, Tuple, Any
from dataclasses import dataclass
from enum import Enum

from ..core.models import GCodeCommand, GCodeProgram, ValidationError
from ..core.exceptions import PromptPlotException


class GCodeDialect(str, Enum):
    """Supported G-code dialects"""
    STANDARD = "standard"
    MARLIN = "marlin"
    GRBL = "grbl"
    REPRAP = "reprap"
    LINUXCNC = "linuxcnc"


class CoordinateSystem(str, Enum):
    """Coordinate system types"""
    ABSOLUTE = "absolute"  # G90
    RELATIVE = "relative"  # G91
    MIXED = "mixed"


@dataclass
class GCodeFileInfo:
    """Information about a G-code file"""
    filename: str
    file_size: int
    line_count: int
    command_count: int
    dialect: Optional[GCodeDialect] = None
    coordinate_system: CoordinateSystem = CoordinateSystem.ABSOLUTE
    bounds: Optional[Dict[str, float]] = None
    estimated_time: Optional[float] = None  # in seconds
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class GCodeParseError(PromptPlotException):
    """Exception raised when G-code parsing fails"""
    
    def __init__(self, message: str, line_number: Optional[int] = None, line_content: Optional[str] = None):
        self.line_number = line_number
        self.line_content = line_content
        
        if line_number is not None:
            message = f"Line {line_number}: {message}"
        if line_content is not None:
            message = f"{message} ('{line_content.strip()}')"
            
        super().__init__(message)


class GCodeLoader:
    """
    Loads and validates G-code files with support for different dialects
    """
    
    # Common G-code command patterns
    GCODE_PATTERN = re.compile(r'^([GM])(\d+(?:\.\d+)?)', re.IGNORECASE)
    PARAMETER_PATTERN = re.compile(r'([XYZFSPIJKR])(-?\d+(?:\.\d+)?)', re.IGNORECASE)
    COMMENT_PATTERN = re.compile(r';.*$|%.*$|\(.*?\)')
    
    # Dialect-specific command sets
    DIALECT_COMMANDS = {
        GCodeDialect.STANDARD: {
            'G': [0, 1, 2, 3, 4, 17, 18, 19, 20, 21, 28, 90, 91, 92],
            'M': [3, 5, 17, 18, 30, 84, 104, 106, 107, 109, 140, 190]
        },
        GCodeDialect.GRBL: {
            'G': [0, 1, 2, 3, 4, 10, 17, 18, 19, 20, 21, 28, 30, 38.2, 43.1, 49, 54, 80, 90, 91, 92, 93, 94],
            'M': [3, 4, 5, 7, 8, 9, 30]
        },
        GCodeDialect.MARLIN: {
            'G': [0, 1, 2, 3, 4, 10, 11, 17, 18, 19, 20, 21, 28, 29, 90, 91, 92],
            'M': [3, 5, 17, 18, 20, 21, 42, 80, 81, 82, 83, 84, 104, 105, 106, 107, 109, 140, 190, 220]
        }
    }
    
    def __init__(self, dialect: GCodeDialect = GCodeDialect.STANDARD):
        """
        Initialize G-code loader
        
        Args:
            dialect: G-code dialect to use for validation
        """
        self.dialect = dialect
        self.coordinate_system = CoordinateSystem.ABSOLUTE
        self.current_position = {'X': 0.0, 'Y': 0.0, 'Z': 0.0}
        
    def load_file(self, filepath: Union[str, Path]) -> Tuple[GCodeProgram, GCodeFileInfo]:
        """
        Load and parse a G-code file
        
        Args:
            filepath: Path to the G-code file
            
        Returns:
            Tuple of (GCodeProgram, GCodeFileInfo)
            
        Raises:
            GCodeParseError: If parsing fails
            FileNotFoundError: If file doesn't exist
        """
        filepath = Path(filepath)
        
        if not filepath.exists():
            raise FileNotFoundError(f"G-code file not found: {filepath}")
            
        if not filepath.is_file():
            raise GCodeParseError(f"Path is not a file: {filepath}")
            
        # Get file info
        file_size = filepath.stat().st_size
        
        # Read and parse file
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            # Try with different encoding
            with open(filepath, 'r', encoding='latin-1') as f:
                lines = f.readlines()
                
        commands = []
        line_count = len(lines)
        
        for line_num, line in enumerate(lines, 1):
            try:
                parsed_commands = self._parse_line(line, line_num)
                commands.extend(parsed_commands)
            except GCodeParseError as e:
                # Re-raise with line context
                raise GCodeParseError(
                    str(e), 
                    line_number=line_num, 
                    line_content=line
                )
                
        if not commands:
            raise GCodeParseError("No valid G-code commands found in file")
            
        # Create program
        program = GCodeProgram(commands=commands)
        
        # Create file info
        file_info = GCodeFileInfo(
            filename=filepath.name,
            file_size=file_size,
            line_count=line_count,
            command_count=len(commands),
            dialect=self.dialect,
            coordinate_system=self.coordinate_system,
            bounds=program.get_bounds()
        )
        
        return program, file_info
        
    def _parse_line(self, line: str, line_number: int) -> List[GCodeCommand]:
        """
        Parse a single line of G-code
        
        Args:
            line: Line to parse
            line_number: Line number for error reporting
            
        Returns:
            List of GCodeCommand objects (may be empty for comments/empty lines)
        """
        # Remove comments and whitespace
        line = self.COMMENT_PATTERN.sub('', line).strip()
        
        if not line:
            return []
            
        # Handle special cases
        if line.upper() in ['%', 'COMPLETE']:
            if line.upper() == 'COMPLETE':
                return [GCodeCommand(command='COMPLETE')]
            return []  # Skip program delimiters
            
        commands = []
        
        # Split line by commands (G or M followed by number)
        parts = re.split(r'(?=[GM]\d)', line, flags=re.IGNORECASE)
        parts = [p.strip() for p in parts if p.strip()]
        
        for part in parts:
            command = self._parse_command(part, line_number)
            if command:
                commands.append(command)
                
        return commands
        
    def _parse_command(self, command_str: str, line_number: int) -> Optional[GCodeCommand]:
        """
        Parse a single G-code command
        
        Args:
            command_str: Command string to parse
            line_number: Line number for error reporting
            
        Returns:
            GCodeCommand object or None if not a valid command
        """
        # Match G or M command
        cmd_match = self.GCODE_PATTERN.match(command_str)
        if not cmd_match:
            return None
            
        cmd_type = cmd_match.group(1).upper()
        cmd_num = float(cmd_match.group(2))
        
        # Validate command against dialect
        if not self._is_valid_command(cmd_type, cmd_num):
            raise GCodeParseError(
                f"Invalid {cmd_type}{cmd_num} command for dialect {self.dialect.value}"
            )
            
        # Build command
        command = f"{cmd_type}{int(cmd_num) if cmd_num.is_integer() else cmd_num}"
        
        # Parse parameters
        parameters = {}
        param_matches = self.PARAMETER_PATTERN.findall(command_str)
        
        for param_name, param_value in param_matches:
            param_name = param_name.upper()
            param_value = float(param_value)
            
            # Map parameter names to model fields
            if param_name == 'X':
                parameters['x'] = param_value
            elif param_name == 'Y':
                parameters['y'] = param_value
            elif param_name == 'Z':
                parameters['z'] = param_value
            elif param_name == 'F':
                parameters['f'] = int(param_value)
            elif param_name == 'S':
                parameters['s'] = int(param_value)
            elif param_name == 'P':
                parameters['p'] = int(param_value)
            # Note: I, J, K, R parameters are not supported in current model
            
        # Update coordinate system tracking
        if command == 'G90':
            self.coordinate_system = CoordinateSystem.ABSOLUTE
        elif command == 'G91':
            self.coordinate_system = CoordinateSystem.RELATIVE
            
        return GCodeCommand(command=command, **parameters)
        
    def _is_valid_command(self, cmd_type: str, cmd_num: float) -> bool:
        """
        Check if command is valid for the current dialect
        
        Args:
            cmd_type: Command type ('G' or 'M')
            cmd_num: Command number
            
        Returns:
            True if valid, False otherwise
        """
        if self.dialect not in self.DIALECT_COMMANDS:
            return True  # Allow all commands for unknown dialects
            
        valid_commands = self.DIALECT_COMMANDS[self.dialect].get(cmd_type, [])
        return cmd_num in valid_commands
        
    def validate_file(self, filepath: Union[str, Path]) -> List[ValidationError]:
        """
        Validate a G-code file without loading it completely
        
        Args:
            filepath: Path to the G-code file
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        filepath = Path(filepath)
        
        if not filepath.exists():
            errors.append(ValidationError(
                field="file",
                message="File does not exist",
                invalid_value=str(filepath)
            ))
            return errors
            
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        self._parse_line(line, line_num)
                    except GCodeParseError as e:
                        errors.append(ValidationError(
                            field=f"line_{line_num}",
                            message=str(e),
                            invalid_value=line.strip()
                        ))
        except Exception as e:
            errors.append(ValidationError(
                field="file",
                message=f"Failed to read file: {e}",
                invalid_value=str(filepath)
            ))
            
        return errors


class GCodeProcessor:
    """
    Processes and optimizes G-code programs
    """
    
    def __init__(self):
        self.optimization_enabled = True
        
    def optimize_program(self, program: GCodeProgram) -> GCodeProgram:
        """
        Optimize a G-code program for efficiency
        
        Args:
            program: Original G-code program
            
        Returns:
            Optimized G-code program
        """
        if not self.optimization_enabled:
            return program
            
        optimized_commands = []
        
        # Remove duplicate consecutive commands
        optimized_commands = self._remove_duplicates(program.commands)
        
        # Optimize pen movements
        optimized_commands = self._optimize_pen_movements(optimized_commands)
        
        # Merge consecutive G1 commands with same parameters
        optimized_commands = self._merge_movements(optimized_commands)
        
        return GCodeProgram(
            commands=optimized_commands,
            metadata={
                **program.metadata,
                'optimized': True,
                'original_command_count': len(program.commands),
                'optimized_command_count': len(optimized_commands)
            }
        )
        
    def _remove_duplicates(self, commands: List[GCodeCommand]) -> List[GCodeCommand]:
        """Remove duplicate consecutive commands"""
        if not commands:
            return commands
            
        result = [commands[0]]
        
        for cmd in commands[1:]:
            if not self._commands_equal(cmd, result[-1]):
                result.append(cmd)
                
        return result
        
    def _optimize_pen_movements(self, commands: List[GCodeCommand]) -> List[GCodeCommand]:
        """Optimize pen up/down movements"""
        result = []
        pen_state = None  # None, 'up', 'down'
        
        for cmd in commands:
            if cmd.command == 'M5':  # Pen up
                if pen_state != 'up':
                    result.append(cmd)
                    pen_state = 'up'
            elif cmd.command == 'M3':  # Pen down
                if pen_state != 'down':
                    result.append(cmd)
                    pen_state = 'down'
            else:
                result.append(cmd)
                
        return result
        
    def _merge_movements(self, commands: List[GCodeCommand]) -> List[GCodeCommand]:
        """Merge consecutive G1 commands with same feed rate"""
        if not commands:
            return commands
            
        result = []
        current_group = []
        
        for cmd in commands:
            if (cmd.command == 'G1' and 
                current_group and 
                current_group[-1].command == 'G1' and
                cmd.f == current_group[-1].f):
                current_group.append(cmd)
            else:
                if current_group:
                    # Add the group (for now, just add all commands)
                    # In a more advanced implementation, we could merge paths
                    result.extend(current_group)
                    current_group = []
                    
                if cmd.command == 'G1':
                    current_group = [cmd]
                else:
                    result.append(cmd)
                    
        # Add remaining group
        if current_group:
            result.extend(current_group)
            
        return result
        
    def _commands_equal(self, cmd1: GCodeCommand, cmd2: GCodeCommand) -> bool:
        """Check if two commands are equal"""
        return (cmd1.command == cmd2.command and
                cmd1.x == cmd2.x and
                cmd1.y == cmd2.y and
                cmd1.z == cmd2.z and
                cmd1.f == cmd2.f and
                cmd1.s == cmd2.s and
                cmd1.p == cmd2.p)
                
    def transform_coordinates(
        self, 
        program: GCodeProgram, 
        scale: Tuple[float, float, float] = (1.0, 1.0, 1.0),
        offset: Tuple[float, float, float] = (0.0, 0.0, 0.0),
        rotation: float = 0.0
    ) -> GCodeProgram:
        """
        Transform coordinates in a G-code program
        
        Args:
            program: Original program
            scale: Scale factors for X, Y, Z axes
            offset: Offset values for X, Y, Z axes  
            rotation: Rotation angle in degrees (around Z axis)
            
        Returns:
            Transformed G-code program
        """
        import math
        
        transformed_commands = []
        
        # Convert rotation to radians
        rotation_rad = math.radians(rotation)
        cos_r = math.cos(rotation_rad)
        sin_r = math.sin(rotation_rad)
        
        for cmd in program.commands:
            new_cmd = GCodeCommand(**cmd.model_dump())
            
            # Transform coordinates for movement commands
            if cmd.is_movement_command() and (cmd.x is not None or cmd.y is not None):
                x = cmd.x if cmd.x is not None else 0.0
                y = cmd.y if cmd.y is not None else 0.0
                z = cmd.z if cmd.z is not None else 0.0
                
                # Apply scaling
                x *= scale[0]
                y *= scale[1] 
                z *= scale[2]
                
                # Apply rotation (around Z axis)
                if rotation != 0.0:
                    new_x = x * cos_r - y * sin_r
                    new_y = x * sin_r + y * cos_r
                    x, y = new_x, new_y
                    
                # Apply offset
                x += offset[0]
                y += offset[1]
                z += offset[2]
                
                # Update command
                if cmd.x is not None:
                    new_cmd.x = round(x, 3)
                if cmd.y is not None:
                    new_cmd.y = round(y, 3)
                if cmd.z is not None:
                    new_cmd.z = round(z, 3)
                    
            transformed_commands.append(new_cmd)
            
        return GCodeProgram(
            commands=transformed_commands,
            metadata={
                **program.metadata,
                'transformed': True,
                'scale': scale,
                'offset': offset,
                'rotation': rotation
            }
        )
        
    def batch_process_files(
        self, 
        filepaths: List[Union[str, Path]], 
        output_dir: Optional[Union[str, Path]] = None
    ) -> List[Tuple[Path, GCodeProgram, GCodeFileInfo]]:
        """
        Process multiple G-code files in batch
        
        Args:
            filepaths: List of file paths to process
            output_dir: Optional output directory for processed files
            
        Returns:
            List of tuples (filepath, program, file_info)
        """
        results = []
        loader = GCodeLoader()
        
        for filepath in filepaths:
            filepath = Path(filepath)
            
            try:
                program, file_info = loader.load_file(filepath)
                
                # Optimize program
                optimized_program = self.optimize_program(program)
                
                # Save to output directory if specified
                if output_dir:
                    output_dir = Path(output_dir)
                    output_dir.mkdir(parents=True, exist_ok=True)
                    
                    output_file = output_dir / f"optimized_{filepath.name}"
                    with open(output_file, 'w') as f:
                        f.write(optimized_program.to_gcode())
                        
                results.append((filepath, optimized_program, file_info))
                
            except Exception as e:
                # Log error but continue processing other files
                print(f"Error processing {filepath}: {e}")
                continue
                
        return results