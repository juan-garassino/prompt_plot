"""
HPGL to G-code conversion utilities

This module provides functionality for converting HPGL (Hewlett-Packard Graphics Language)
files to G-code for pen plotting, supporting legacy plotter file formats.
"""

import re
from pathlib import Path
from typing import List, Dict, Optional, Union, Tuple, Any
from dataclasses import dataclass
import math

from ..core.models import GCodeCommand, GCodeProgram
from ..core.exceptions import PromptPlotException


@dataclass
class HPGLCommand:
    """Represents an HPGL command"""
    command: str
    parameters: List[float]
    raw_text: str


class HPGLParseError(PromptPlotException):
    """Exception raised when HPGL parsing fails"""
    pass


class HPGLConverter:
    """
    Converts HPGL files to G-code for pen plotting
    """
    
    # HPGL command patterns
    COMMAND_PATTERN = re.compile(r'([A-Z]{2})([^A-Z]*)', re.IGNORECASE)
    
    def __init__(self, 
                 feed_rate: int = 1000,
                 pen_up_command: str = "M5",
                 pen_down_command: str = "M3",
                 scale_factor: float = 0.025):  # HPGL units to mm
        """
        Initialize HPGL converter
        
        Args:
            feed_rate: Default feed rate for movements
            pen_up_command: G-code command for pen up
            pen_down_command: G-code command for pen down
            scale_factor: Scale factor from HPGL units to mm (default: 0.025mm per unit)
        """
        self.feed_rate = feed_rate
        self.pen_up_command = pen_up_command
        self.pen_down_command = pen_down_command
        self.scale_factor = scale_factor
        
        # HPGL state
        self.current_position = (0.0, 0.0)
        self.pen_down = False
        self.current_pen = 1
        
    def convert_file(self, filepath: Union[str, Path]) -> GCodeProgram:
        """
        Convert an HPGL file to G-code
        
        Args:
            filepath: Path to HPGL file
            
        Returns:
            GCodeProgram object
            
        Raises:
            HPGLParseError: If HPGL parsing fails
            FileNotFoundError: If file doesn't exist
        """
        filepath = Path(filepath)
        
        if not filepath.exists():
            raise FileNotFoundError(f"HPGL file not found: {filepath}")
            
        # Parse HPGL file
        hpgl_commands = self._parse_hpgl_file(filepath)
        
        # Convert to G-code commands
        gcode_commands = self._hpgl_to_gcode(hpgl_commands)
        
        # Create program with metadata
        metadata = {
            'source_file': filepath.name,
            'hpgl_command_count': len(hpgl_commands),
            'scale_factor': self.scale_factor,
            'feed_rate': self.feed_rate
        }
        
        return GCodeProgram(commands=gcode_commands, metadata=metadata)
        
    def _parse_hpgl_file(self, filepath: Path) -> List[HPGLCommand]:
        """Parse HPGL file and extract commands"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # Try with different encoding
            with open(filepath, 'r', encoding='latin-1') as f:
                content = f.read()
                
        # Clean content - remove extra whitespace and normalize
        content = re.sub(r'\s+', ' ', content.strip())
        
        # Parse commands
        commands = []
        matches = self.COMMAND_PATTERN.findall(content)
        
        for command, params_str in matches:
            command = command.upper()
            parameters = self._parse_parameters(params_str)
            
            hpgl_cmd = HPGLCommand(
                command=command,
                parameters=parameters,
                raw_text=f"{command}{params_str}"
            )
            commands.append(hpgl_cmd)
            
        return commands
        
    def _parse_parameters(self, params_str: str) -> List[float]:
        """Parse parameter string into list of floats"""
        if not params_str.strip():
            return []
            
        # Remove semicolons and split by commas or spaces
        params_str = params_str.replace(';', '').strip()
        
        # Split by comma or space
        if ',' in params_str:
            parts = params_str.split(',')
        else:
            parts = params_str.split()
            
        parameters = []
        for part in parts:
            part = part.strip()
            if part:
                try:
                    parameters.append(float(part))
                except ValueError:
                    # Skip invalid parameters
                    continue
                    
        return parameters
        
    def _hpgl_to_gcode(self, hpgl_commands: List[HPGLCommand]) -> List[GCodeCommand]:
        """Convert HPGL commands to G-code commands"""
        gcode_commands = []
        
        # Initialize state
        self.current_position = (0.0, 0.0)
        self.pen_down = False
        
        # Start with pen up and move to origin
        gcode_commands.append(GCodeCommand(command=self.pen_up_command))
        gcode_commands.append(GCodeCommand(command="G0", x=0.0, y=0.0))
        
        for hpgl_cmd in hpgl_commands:
            converted_commands = self._convert_hpgl_command(hpgl_cmd)
            gcode_commands.extend(converted_commands)
            
        # End with pen up
        if self.pen_down:
            gcode_commands.append(GCodeCommand(command=self.pen_up_command))
            
        # Add completion command
        gcode_commands.append(GCodeCommand(command="COMPLETE"))
        
        return gcode_commands
        
    def _convert_hpgl_command(self, hpgl_cmd: HPGLCommand) -> List[GCodeCommand]:
        """Convert a single HPGL command to G-code commands"""
        command = hpgl_cmd.command
        params = hpgl_cmd.parameters
        
        if command == "IN":  # Initialize
            return self._handle_initialize()
        elif command == "PU":  # Pen Up
            return self._handle_pen_up(params)
        elif command == "PD":  # Pen Down
            return self._handle_pen_down(params)
        elif command == "PA":  # Plot Absolute
            return self._handle_plot_absolute(params)
        elif command == "PR":  # Plot Relative
            return self._handle_plot_relative(params)
        elif command == "SP":  # Select Pen
            return self._handle_select_pen(params)
        elif command == "CI":  # Circle
            return self._handle_circle(params)
        elif command == "AA":  # Arc Absolute
            return self._handle_arc_absolute(params)
        elif command == "AR":  # Arc Relative
            return self._handle_arc_relative(params)
        elif command == "LT":  # Line Type
            return []  # Ignore line type for now
        elif command == "VS":  # Velocity Select
            return self._handle_velocity_select(params)
        else:
            # Unknown command - ignore
            return []
            
    def _handle_initialize(self) -> List[GCodeCommand]:
        """Handle IN (Initialize) command"""
        self.current_position = (0.0, 0.0)
        self.pen_down = False
        return []
        
    def _handle_pen_up(self, params: List[float]) -> List[GCodeCommand]:
        """Handle PU (Pen Up) command"""
        commands = []
        
        # Pen up
        if self.pen_down:
            commands.append(GCodeCommand(command=self.pen_up_command))
            self.pen_down = False
            
        # Move if coordinates provided
        if len(params) >= 2:
            x = params[0] * self.scale_factor
            y = params[1] * self.scale_factor
            commands.append(GCodeCommand(command="G0", x=x, y=y))
            self.current_position = (x, y)
            
        return commands
        
    def _handle_pen_down(self, params: List[float]) -> List[GCodeCommand]:
        """Handle PD (Pen Down) command"""
        commands = []
        
        # Pen down
        if not self.pen_down:
            commands.append(GCodeCommand(command=self.pen_down_command))
            self.pen_down = True
            
        # Draw if coordinates provided
        if len(params) >= 2:
            x = params[0] * self.scale_factor
            y = params[1] * self.scale_factor
            commands.append(GCodeCommand(command="G1", x=x, y=y, f=self.feed_rate))
            self.current_position = (x, y)
            
        return commands
        
    def _handle_plot_absolute(self, params: List[float]) -> List[GCodeCommand]:
        """Handle PA (Plot Absolute) command"""
        commands = []
        
        # Process coordinate pairs
        for i in range(0, len(params) - 1, 2):
            x = params[i] * self.scale_factor
            y = params[i + 1] * self.scale_factor
            
            if self.pen_down:
                commands.append(GCodeCommand(command="G1", x=x, y=y, f=self.feed_rate))
            else:
                commands.append(GCodeCommand(command="G0", x=x, y=y))
                
            self.current_position = (x, y)
            
        return commands
        
    def _handle_plot_relative(self, params: List[float]) -> List[GCodeCommand]:
        """Handle PR (Plot Relative) command"""
        commands = []
        
        # Process coordinate pairs
        for i in range(0, len(params) - 1, 2):
            dx = params[i] * self.scale_factor
            dy = params[i + 1] * self.scale_factor
            
            x = self.current_position[0] + dx
            y = self.current_position[1] + dy
            
            if self.pen_down:
                commands.append(GCodeCommand(command="G1", x=x, y=y, f=self.feed_rate))
            else:
                commands.append(GCodeCommand(command="G0", x=x, y=y))
                
            self.current_position = (x, y)
            
        return commands
        
    def _handle_select_pen(self, params: List[float]) -> List[GCodeCommand]:
        """Handle SP (Select Pen) command"""
        if params:
            self.current_pen = int(params[0])
        return []  # No G-code equivalent for pen selection
        
    def _handle_circle(self, params: List[float]) -> List[GCodeCommand]:
        """Handle CI (Circle) command"""
        if len(params) < 1:
            return []
            
        radius = params[0] * self.scale_factor
        chord_angle = params[1] if len(params) > 1 else 5.0  # Default 5 degrees
        
        # Calculate number of segments
        circumference = 2 * math.pi * radius
        num_segments = max(8, int(360 / chord_angle))
        
        commands = []
        cx, cy = self.current_position
        
        # Start point
        start_x = cx + radius
        start_y = cy
        
        # Move to start if pen is up
        if not self.pen_down:
            commands.append(GCodeCommand(command="G0", x=start_x, y=start_y))
        else:
            commands.append(GCodeCommand(command="G1", x=start_x, y=start_y, f=self.feed_rate))
            
        # Ensure pen is down for drawing
        if not self.pen_down:
            commands.append(GCodeCommand(command=self.pen_down_command))
            self.pen_down = True
            
        # Generate circle segments
        angle_step = 2 * math.pi / num_segments
        for i in range(1, num_segments + 1):
            angle = i * angle_step
            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle)
            commands.append(GCodeCommand(command="G1", x=x, y=y, f=self.feed_rate))
            
        self.current_position = (start_x, start_y)  # Return to start
        return commands
        
    def _handle_arc_absolute(self, params: List[float]) -> List[GCodeCommand]:
        """Handle AA (Arc Absolute) command"""
        if len(params) < 3:
            return []
            
        cx = params[0] * self.scale_factor
        cy = params[1] * self.scale_factor
        angle = math.radians(params[2])
        
        # Calculate arc
        start_x, start_y = self.current_position
        radius = math.sqrt((start_x - cx)**2 + (start_y - cy)**2)
        
        if radius == 0:
            return []
            
        # Calculate start and end angles
        start_angle = math.atan2(start_y - cy, start_x - cx)
        end_angle = start_angle + angle
        
        return self._generate_arc_commands(cx, cy, radius, start_angle, end_angle)
        
    def _handle_arc_relative(self, params: List[float]) -> List[GCodeCommand]:
        """Handle AR (Arc Relative) command"""
        if len(params) < 3:
            return []
            
        dx = params[0] * self.scale_factor
        dy = params[1] * self.scale_factor
        angle = math.radians(params[2])
        
        cx = self.current_position[0] + dx
        cy = self.current_position[1] + dy
        
        # Calculate arc
        start_x, start_y = self.current_position
        radius = math.sqrt((start_x - cx)**2 + (start_y - cy)**2)
        
        if radius == 0:
            return []
            
        # Calculate start and end angles
        start_angle = math.atan2(start_y - cy, start_x - cx)
        end_angle = start_angle + angle
        
        return self._generate_arc_commands(cx, cy, radius, start_angle, end_angle)
        
    def _handle_velocity_select(self, params: List[float]) -> List[GCodeCommand]:
        """Handle VS (Velocity Select) command"""
        if params:
            # Convert HPGL velocity to feed rate (approximate)
            velocity = params[0]
            self.feed_rate = max(100, int(velocity * 10))  # Scale and clamp
        return []
        
    def _generate_arc_commands(self, cx: float, cy: float, radius: float, 
                             start_angle: float, end_angle: float) -> List[GCodeCommand]:
        """Generate G-code commands for an arc"""
        commands = []
        
        # Calculate arc length and segments
        angle_diff = end_angle - start_angle
        arc_length = abs(radius * angle_diff)
        num_segments = max(2, int(arc_length / 1.0))  # 1mm resolution
        
        angle_step = angle_diff / num_segments
        
        # Generate arc points
        for i in range(1, num_segments + 1):
            angle = start_angle + i * angle_step
            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle)
            
            if self.pen_down:
                commands.append(GCodeCommand(command="G1", x=x, y=y, f=self.feed_rate))
            else:
                commands.append(GCodeCommand(command="G0", x=x, y=y))
                
        # Update position to end of arc
        end_x = cx + radius * math.cos(end_angle)
        end_y = cy + radius * math.sin(end_angle)
        self.current_position = (end_x, end_y)
        
        return commands