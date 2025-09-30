"""
Common validation utilities for PromptPlot v2.0

This module provides validation functions used across different components
for G-code commands, coordinates, file formats, and configuration values.
"""

import re
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Tuple, Set
from enum import Enum
from dataclasses import dataclass

from ..core.models import GCodeCommand, DrawingStrategy
from ..core.exceptions import ValidationException


class ValidationLevel(str, Enum):
    """Validation strictness levels"""
    STRICT = "strict"      # Fail on any validation error
    MODERATE = "moderate"  # Warn on minor issues, fail on major ones
    LENIENT = "lenient"    # Warn on issues but don't fail


@dataclass
class ValidationResult:
    """Result of a validation operation"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    suggestions: List[str]
    
    def __bool__(self) -> bool:
        """Allow boolean evaluation"""
        return self.is_valid
    
    def add_error(self, message: str) -> None:
        """Add validation error"""
        self.errors.append(message)
        self.is_valid = False
    
    def add_warning(self, message: str) -> None:
        """Add validation warning"""
        self.warnings.append(message)
    
    def add_suggestion(self, message: str) -> None:
        """Add validation suggestion"""
        self.suggestions.append(message)
    
    def merge(self, other: 'ValidationResult') -> 'ValidationResult':
        """Merge with another validation result"""
        return ValidationResult(
            is_valid=self.is_valid and other.is_valid,
            errors=self.errors + other.errors,
            warnings=self.warnings + other.warnings,
            suggestions=self.suggestions + other.suggestions
        )


class CoordinateValidator:
    """Validator for coordinate values and ranges"""
    
    def __init__(self, 
                 x_range: Tuple[float, float] = (-1000.0, 1000.0),
                 y_range: Tuple[float, float] = (-1000.0, 1000.0),
                 z_range: Tuple[float, float] = (-100.0, 100.0)):
        """Initialize coordinate validator
        
        Args:
            x_range: Valid X coordinate range (min, max)
            y_range: Valid Y coordinate range (min, max)
            z_range: Valid Z coordinate range (min, max)
        """
        self.x_range = x_range
        self.y_range = y_range
        self.z_range = z_range
    
    def validate_coordinate(self, x: Optional[float], y: Optional[float], z: Optional[float] = None) -> ValidationResult:
        """Validate individual coordinates"""
        result = ValidationResult(True, [], [], [])
        
        if x is not None:
            if not isinstance(x, (int, float)):
                result.add_error(f"X coordinate must be numeric, got {type(x)}")
            elif not (self.x_range[0] <= x <= self.x_range[1]):
                result.add_error(f"X coordinate {x} outside valid range {self.x_range}")
        
        if y is not None:
            if not isinstance(y, (int, float)):
                result.add_error(f"Y coordinate must be numeric, got {type(y)}")
            elif not (self.y_range[0] <= y <= self.y_range[1]):
                result.add_error(f"Y coordinate {y} outside valid range {self.y_range}")
        
        if z is not None:
            if not isinstance(z, (int, float)):
                result.add_error(f"Z coordinate must be numeric, got {type(z)}")
            elif not (self.z_range[0] <= z <= self.z_range[1]):
                result.add_error(f"Z coordinate {z} outside valid range {self.z_range}")
        
        return result
    
    def validate_path(self, coordinates: List[Tuple[float, float]]) -> ValidationResult:
        """Validate a path of coordinates"""
        result = ValidationResult(True, [], [], [])
        
        if not coordinates:
            result.add_error("Path cannot be empty")
            return result
        
        for i, (x, y) in enumerate(coordinates):
            coord_result = self.validate_coordinate(x, y)
            if not coord_result:
                result.add_error(f"Invalid coordinate at index {i}: {coord_result.errors}")
        
        # Check for reasonable path length
        if len(coordinates) > 10000:
            result.add_warning(f"Path has {len(coordinates)} points, which may be excessive")
        
        return result


class GCodeValidator:
    """Validator for G-code commands and programs"""
    
    VALID_COMMANDS = {'G0', 'G1', 'G2', 'G3', 'G28', 'G90', 'G91', 'M3', 'M5', 'M17', 'M18'}
    MOVEMENT_COMMANDS = {'G0', 'G1', 'G2', 'G3'}
    PEN_COMMANDS = {'M3', 'M5'}
    
    def __init__(self, coordinate_validator: Optional[CoordinateValidator] = None):
        """Initialize G-code validator
        
        Args:
            coordinate_validator: Coordinate validator to use
        """
        self.coordinate_validator = coordinate_validator or CoordinateValidator()
    
    def validate_command(self, command: Union[str, GCodeCommand, Dict[str, Any]]) -> ValidationResult:
        """Validate a single G-code command"""
        result = ValidationResult(True, [], [], [])
        
        # Convert to GCodeCommand if needed
        if isinstance(command, str):
            try:
                command_dict = json.loads(command)
                gcode_cmd = GCodeCommand(**command_dict)
            except (json.JSONDecodeError, TypeError, ValueError) as e:
                result.add_error(f"Invalid command format: {e}")
                return result
        elif isinstance(command, dict):
            try:
                gcode_cmd = GCodeCommand(**command)
            except (TypeError, ValueError) as e:
                result.add_error(f"Invalid command data: {e}")
                return result
        else:
            gcode_cmd = command
        
        # Validate command type
        if gcode_cmd.command not in self.VALID_COMMANDS:
            result.add_error(f"Unknown command: {gcode_cmd.command}")
        
        # Validate coordinates for movement commands
        if gcode_cmd.command in self.MOVEMENT_COMMANDS:
            coord_result = self.coordinate_validator.validate_coordinate(
                gcode_cmd.x, gcode_cmd.y, gcode_cmd.z
            )
            result = result.merge(coord_result)
            
            # Check for required coordinates
            if gcode_cmd.command in {'G0', 'G1'} and gcode_cmd.x is None and gcode_cmd.y is None:
                result.add_warning("Movement command without coordinates")
        
        # Validate feed rate
        if gcode_cmd.f is not None:
            if not isinstance(gcode_cmd.f, int) or gcode_cmd.f <= 0:
                result.add_error(f"Feed rate must be positive integer, got {gcode_cmd.f}")
            elif gcode_cmd.f > 10000:
                result.add_warning(f"Feed rate {gcode_cmd.f} is very high")
        
        # Validate spindle speed
        if gcode_cmd.s is not None:
            if not isinstance(gcode_cmd.s, int) or not (0 <= gcode_cmd.s <= 255):
                result.add_error(f"Spindle speed must be 0-255, got {gcode_cmd.s}")
        
        return result
    
    def validate_program(self, commands: List[Union[GCodeCommand, Dict[str, Any]]]) -> ValidationResult:
        """Validate a complete G-code program"""
        result = ValidationResult(True, [], [], [])
        
        if not commands:
            result.add_error("Program cannot be empty")
            return result
        
        pen_state = None  # Track pen up/down state
        current_pos = (0.0, 0.0, 0.0)  # Track current position
        
        for i, command in enumerate(commands):
            # Validate individual command
            cmd_result = self.validate_command(command)
            if not cmd_result:
                result.add_error(f"Command {i}: {cmd_result.errors}")
            result.warnings.extend(cmd_result.warnings)
            
            # Convert to GCodeCommand for analysis
            if isinstance(command, dict):
                try:
                    gcode_cmd = GCodeCommand(**command)
                except:
                    continue
            else:
                gcode_cmd = command
            
            # Track pen state
            if gcode_cmd.command == 'M3':
                if pen_state == 'down':
                    result.add_warning(f"Command {i}: Pen already down")
                pen_state = 'down'
            elif gcode_cmd.command == 'M5':
                if pen_state == 'up':
                    result.add_warning(f"Command {i}: Pen already up")
                pen_state = 'up'
            
            # Track position and check for large movements
            if gcode_cmd.command in self.MOVEMENT_COMMANDS:
                new_x = gcode_cmd.x if gcode_cmd.x is not None else current_pos[0]
                new_y = gcode_cmd.y if gcode_cmd.y is not None else current_pos[1]
                new_z = gcode_cmd.z if gcode_cmd.z is not None else current_pos[2]
                
                # Check for large movements
                distance = ((new_x - current_pos[0])**2 + (new_y - current_pos[1])**2)**0.5
                if distance > 100:
                    result.add_warning(f"Command {i}: Large movement distance {distance:.1f}")
                
                current_pos = (new_x, new_y, new_z)
        
        # Check program structure
        if pen_state == 'down':
            result.add_warning("Program ends with pen down")
        
        # Check for reasonable program length
        if len(commands) > 1000:
            result.add_warning(f"Program has {len(commands)} commands, which may be excessive")
        
        return result


class FileValidator:
    """Validator for file formats and content"""
    
    SUPPORTED_EXTENSIONS = {'.gcode', '.nc', '.svg', '.dxf', '.hpgl', '.plt', '.json', '.png', '.jpg', '.jpeg'}
    
    def validate_file_path(self, filepath: Union[str, Path]) -> ValidationResult:
        """Validate file path and accessibility"""
        result = ValidationResult(True, [], [], [])
        
        path = Path(filepath)
        
        # Check if file exists
        if not path.exists():
            result.add_error(f"File does not exist: {filepath}")
            return result
        
        # Check if it's a file (not directory)
        if not path.is_file():
            result.add_error(f"Path is not a file: {filepath}")
            return result
        
        # Check file extension
        if path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            result.add_warning(f"Unsupported file extension: {path.suffix}")
        
        # Check file size
        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > 100:
            result.add_warning(f"Large file size: {size_mb:.1f}MB")
        elif size_mb == 0:
            result.add_error("File is empty")
        
        # Check read permissions
        try:
            with open(path, 'r') as f:
                f.read(1)
        except PermissionError:
            result.add_error(f"No read permission for file: {filepath}")
        except UnicodeDecodeError:
            # Binary file, try reading as binary
            try:
                with open(path, 'rb') as f:
                    f.read(1)
            except PermissionError:
                result.add_error(f"No read permission for file: {filepath}")
        except Exception as e:
            result.add_error(f"Cannot read file: {e}")
        
        return result
    
    def validate_json_content(self, content: str) -> ValidationResult:
        """Validate JSON content structure"""
        result = ValidationResult(True, [], [], [])
        
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            result.add_error(f"Invalid JSON: {e}")
            return result
        
        # Check for expected G-code structure
        if isinstance(data, dict) and 'commands' in data:
            if not isinstance(data['commands'], list):
                result.add_error("'commands' field must be a list")
            else:
                # Validate each command
                gcode_validator = GCodeValidator()
                for i, cmd in enumerate(data['commands']):
                    cmd_result = gcode_validator.validate_command(cmd)
                    if not cmd_result:
                        result.add_error(f"Invalid command {i}: {cmd_result.errors}")
        
        return result


class ConfigValidator:
    """Validator for configuration values"""
    
    def validate_llm_config(self, config: Dict[str, Any]) -> ValidationResult:
        """Validate LLM configuration"""
        result = ValidationResult(True, [], [], [])
        
        required_fields = ['provider', 'model']
        for field in required_fields:
            if field not in config:
                result.add_error(f"Missing required LLM config field: {field}")
        
        # Validate provider-specific fields
        if config.get('provider') == 'azure':
            azure_fields = ['deployment_name', 'api_key', 'azure_endpoint']
            for field in azure_fields:
                if field not in config or not config[field]:
                    result.add_error(f"Missing Azure OpenAI config field: {field}")
        
        # Validate timeout
        if 'timeout' in config:
            timeout = config['timeout']
            if not isinstance(timeout, int) or timeout <= 0:
                result.add_error(f"Timeout must be positive integer, got {timeout}")
            elif timeout > 3600:
                result.add_warning(f"Very long timeout: {timeout}s")
        
        return result
    
    def validate_plotter_config(self, config: Dict[str, Any]) -> ValidationResult:
        """Validate plotter configuration"""
        result = ValidationResult(True, [], [], [])
        
        # Validate plotter type
        if 'type' not in config:
            result.add_error("Missing plotter type")
        elif config['type'] not in ['serial', 'simulated']:
            result.add_error(f"Invalid plotter type: {config['type']}")
        
        # Validate serial-specific fields
        if config.get('type') == 'serial':
            if 'port' not in config or not config['port']:
                result.add_error("Missing serial port for serial plotter")
            
            if 'baud_rate' in config:
                baud_rate = config['baud_rate']
                valid_rates = [9600, 19200, 38400, 57600, 115200, 230400]
                if baud_rate not in valid_rates:
                    result.add_warning(f"Unusual baud rate: {baud_rate}")
        
        return result


# Convenience functions
def validate_gcode_command(command: Union[str, GCodeCommand, Dict[str, Any]]) -> ValidationResult:
    """Validate a single G-code command"""
    validator = GCodeValidator()
    return validator.validate_command(command)


def validate_gcode_program(commands: List[Union[GCodeCommand, Dict[str, Any]]]) -> ValidationResult:
    """Validate a G-code program"""
    validator = GCodeValidator()
    return validator.validate_program(commands)


def validate_coordinates(x: Optional[float], y: Optional[float], z: Optional[float] = None) -> ValidationResult:
    """Validate coordinates"""
    validator = CoordinateValidator()
    return validator.validate_coordinate(x, y, z)


def validate_file(filepath: Union[str, Path]) -> ValidationResult:
    """Validate file path and basic properties"""
    validator = FileValidator()
    return validator.validate_file_path(filepath)


def validate_json_gcode(content: str) -> ValidationResult:
    """Validate JSON G-code content"""
    validator = FileValidator()
    return validator.validate_json_content(content)


def is_valid_gcode_command(command: str) -> bool:
    """Quick check if command is valid G-code"""
    return command.upper() in GCodeValidator.VALID_COMMANDS


def sanitize_coordinate(value: Any, default: float = 0.0) -> float:
    """Sanitize coordinate value"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def sanitize_integer_parameter(value: Any, default: int = 0, min_val: int = 0, max_val: int = 10000) -> int:
    """Sanitize integer parameter with bounds"""
    try:
        val = int(value)
        return max(min_val, min(max_val, val))
    except (TypeError, ValueError):
        return default