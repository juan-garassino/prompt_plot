"""
JSON to G-code conversion utilities

This module provides functionality for converting JSON files containing
programmatic G-code definitions to executable G-code programs.
"""

import json
from pathlib import Path
from typing import List, Dict, Optional, Union, Any
from dataclasses import dataclass

from ..core.models import GCodeCommand, GCodeProgram, ValidationError
from ..core.exceptions import PromptPlotException


class JSONParseError(PromptPlotException):
    """Exception raised when JSON parsing fails"""
    pass


class JSONConverter:
    """
    Converts JSON files to G-code programs
    
    Supports multiple JSON formats:
    1. Direct command list format
    2. Structured drawing format with shapes
    3. Path-based format with coordinates
    """
    
    def __init__(self, 
                 feed_rate: int = 1000,
                 pen_up_command: str = "M5",
                 pen_down_command: str = "M3"):
        """
        Initialize JSON converter
        
        Args:
            feed_rate: Default feed rate for movements
            pen_up_command: G-code command for pen up
            pen_down_command: G-code command for pen down
        """
        self.feed_rate = feed_rate
        self.pen_up_command = pen_up_command
        self.pen_down_command = pen_down_command
        
    def convert_file(self, filepath: Union[str, Path]) -> GCodeProgram:
        """
        Convert a JSON file to G-code
        
        Args:
            filepath: Path to JSON file
            
        Returns:
            GCodeProgram object
            
        Raises:
            JSONParseError: If JSON parsing fails
            FileNotFoundError: If file doesn't exist
        """
        filepath = Path(filepath)
        
        if not filepath.exists():
            raise FileNotFoundError(f"JSON file not found: {filepath}")
            
        # Load and parse JSON
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise JSONParseError(f"Invalid JSON format: {e}")
        except Exception as e:
            raise JSONParseError(f"Failed to read JSON file: {e}")
            
        # Detect format and convert
        commands = self._convert_json_data(data)
        
        # Create program with metadata
        metadata = {
            'source_file': filepath.name,
            'json_format': self._detect_format(data),
            'feed_rate': self.feed_rate
        }
        
        return GCodeProgram(commands=commands, metadata=metadata)
        
    def _detect_format(self, data: Dict[str, Any]) -> str:
        """Detect the JSON format type"""
        if isinstance(data, list):
            return "command_list"
        elif "commands" in data:
            return "direct_commands"
        elif "shapes" in data:
            return "shapes"
        elif "paths" in data:
            return "paths"
        elif "drawing" in data:
            return "drawing"
        else:
            return "unknown"
            
    def _convert_json_data(self, data: Any) -> List[GCodeCommand]:
        """Convert JSON data to G-code commands based on format"""
        
        # Handle list format (direct command list)
        if isinstance(data, list):
            return self._convert_command_list(data)
            
        # Handle dictionary formats
        if isinstance(data, dict):
            if "commands" in data:
                return self._convert_direct_commands(data)
            elif "shapes" in data:
                return self._convert_shapes_format(data)
            elif "paths" in data:
                return self._convert_paths_format(data)
            elif "drawing" in data:
                return self._convert_drawing_format(data)
                
        raise JSONParseError("Unsupported JSON format")
        
    def _convert_command_list(self, commands_data: List[Dict[str, Any]]) -> List[GCodeCommand]:
        """Convert direct command list format"""
        commands = []
        
        for cmd_data in commands_data:
            try:
                # Create GCodeCommand from dictionary
                command = GCodeCommand(**cmd_data)
                commands.append(command)
            except Exception as e:
                raise JSONParseError(f"Invalid command data: {cmd_data}, error: {e}")
                
        return commands
        
    def _convert_direct_commands(self, data: Dict[str, Any]) -> List[GCodeCommand]:
        """Convert direct commands format"""
        commands_data = data.get("commands", [])
        settings = data.get("settings", {})
        
        # Apply settings
        if "feed_rate" in settings:
            self.feed_rate = settings["feed_rate"]
            
        return self._convert_command_list(commands_data)
        
    def _convert_shapes_format(self, data: Dict[str, Any]) -> List[GCodeCommand]:
        """Convert shapes-based format"""
        shapes = data.get("shapes", [])
        settings = data.get("settings", {})
        
        # Apply settings
        if "feed_rate" in settings:
            self.feed_rate = settings["feed_rate"]
            
        commands = []
        
        # Start with pen up and move to origin
        commands.append(GCodeCommand(command=self.pen_up_command))
        commands.append(GCodeCommand(command="G0", x=0.0, y=0.0))
        
        pen_is_down = False
        
        for shape in shapes:
            shape_commands = self._convert_shape(shape)
            
            for cmd_dict in shape_commands:
                if cmd_dict['type'] == 'move':
                    # Pen up, move
                    if pen_is_down:
                        commands.append(GCodeCommand(command=self.pen_up_command))
                        pen_is_down = False
                        
                    commands.append(GCodeCommand(
                        command="G0", 
                        x=cmd_dict['x'], 
                        y=cmd_dict['y']
                    ))
                    
                elif cmd_dict['type'] == 'line':
                    # Ensure pen is down for drawing
                    if not pen_is_down:
                        commands.append(GCodeCommand(command=self.pen_down_command))
                        pen_is_down = True
                        
                    commands.append(GCodeCommand(
                        command="G1", 
                        x=cmd_dict['x'], 
                        y=cmd_dict['y'], 
                        f=self.feed_rate
                    ))
                    
        # End with pen up
        if pen_is_down:
            commands.append(GCodeCommand(command=self.pen_up_command))
            
        # Add completion command
        commands.append(GCodeCommand(command="COMPLETE"))
        
        return commands
        
    def _convert_paths_format(self, data: Dict[str, Any]) -> List[GCodeCommand]:
        """Convert paths-based format"""
        paths = data.get("paths", [])
        settings = data.get("settings", {})
        
        # Apply settings
        if "feed_rate" in settings:
            self.feed_rate = settings["feed_rate"]
            
        commands = []
        
        # Start with pen up and move to origin
        commands.append(GCodeCommand(command=self.pen_up_command))
        commands.append(GCodeCommand(command="G0", x=0.0, y=0.0))
        
        for path in paths:
            path_commands = self._convert_path(path)
            commands.extend(path_commands)
            
        # Add completion command
        commands.append(GCodeCommand(command="COMPLETE"))
        
        return commands
        
    def _convert_drawing_format(self, data: Dict[str, Any]) -> List[GCodeCommand]:
        """Convert drawing-based format (high-level description)"""
        drawing = data.get("drawing", {})
        elements = drawing.get("elements", [])
        settings = drawing.get("settings", {})
        
        # Apply settings
        if "feed_rate" in settings:
            self.feed_rate = settings["feed_rate"]
            
        commands = []
        
        # Start with pen up and move to origin
        commands.append(GCodeCommand(command=self.pen_up_command))
        commands.append(GCodeCommand(command="G0", x=0.0, y=0.0))
        
        pen_is_down = False
        
        for element in elements:
            element_commands = self._convert_drawing_element(element)
            
            for cmd_dict in element_commands:
                if cmd_dict['type'] == 'move':
                    if pen_is_down:
                        commands.append(GCodeCommand(command=self.pen_up_command))
                        pen_is_down = False
                        
                    commands.append(GCodeCommand(
                        command="G0", 
                        x=cmd_dict['x'], 
                        y=cmd_dict['y']
                    ))
                    
                elif cmd_dict['type'] == 'line':
                    if not pen_is_down:
                        commands.append(GCodeCommand(command=self.pen_down_command))
                        pen_is_down = True
                        
                    commands.append(GCodeCommand(
                        command="G1", 
                        x=cmd_dict['x'], 
                        y=cmd_dict['y'], 
                        f=self.feed_rate
                    ))
                    
        # End with pen up
        if pen_is_down:
            commands.append(GCodeCommand(command=self.pen_up_command))
            
        commands.append(GCodeCommand(command="COMPLETE"))
        
        return commands
        
    def _convert_shape(self, shape: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert a single shape to command dictionaries"""
        shape_type = shape.get("type", "").lower()
        
        if shape_type == "line":
            return self._convert_line_shape(shape)
        elif shape_type == "rectangle":
            return self._convert_rectangle_shape(shape)
        elif shape_type == "circle":
            return self._convert_circle_shape(shape)
        elif shape_type == "polygon":
            return self._convert_polygon_shape(shape)
        else:
            raise JSONParseError(f"Unsupported shape type: {shape_type}")
            
    def _convert_line_shape(self, shape: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert line shape"""
        start = shape.get("start", [0, 0])
        end = shape.get("end", [0, 0])
        
        return [
            {'type': 'move', 'x': start[0], 'y': start[1]},
            {'type': 'line', 'x': end[0], 'y': end[1]}
        ]
        
    def _convert_rectangle_shape(self, shape: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert rectangle shape"""
        x = shape.get("x", 0)
        y = shape.get("y", 0)
        width = shape.get("width", 10)
        height = shape.get("height", 10)
        
        return [
            {'type': 'move', 'x': x, 'y': y},
            {'type': 'line', 'x': x + width, 'y': y},
            {'type': 'line', 'x': x + width, 'y': y + height},
            {'type': 'line', 'x': x, 'y': y + height},
            {'type': 'line', 'x': x, 'y': y}  # Close rectangle
        ]
        
    def _convert_circle_shape(self, shape: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert circle shape"""
        import math
        
        cx = shape.get("cx", 0)
        cy = shape.get("cy", 0)
        radius = shape.get("radius", 5)
        segments = shape.get("segments", 16)
        
        commands = []
        angle_step = 2 * math.pi / segments
        
        # Start point
        start_x = cx + radius
        start_y = cy
        commands.append({'type': 'move', 'x': start_x, 'y': start_y})
        
        # Generate segments
        for i in range(1, segments + 1):
            angle = i * angle_step
            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle)
            commands.append({'type': 'line', 'x': x, 'y': y})
            
        return commands
        
    def _convert_polygon_shape(self, shape: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert polygon shape"""
        points = shape.get("points", [])
        if len(points) < 3:
            raise JSONParseError("Polygon must have at least 3 points")
            
        commands = []
        
        # Move to first point
        commands.append({'type': 'move', 'x': points[0][0], 'y': points[0][1]})
        
        # Draw lines to other points
        for point in points[1:]:
            commands.append({'type': 'line', 'x': point[0], 'y': point[1]})
            
        # Close polygon
        commands.append({'type': 'line', 'x': points[0][0], 'y': points[0][1]})
        
        return commands
        
    def _convert_path(self, path: Dict[str, Any]) -> List[GCodeCommand]:
        """Convert a single path to G-code commands"""
        points = path.get("points", [])
        closed = path.get("closed", False)
        
        if not points:
            return []
            
        commands = []
        
        # Move to first point
        commands.append(GCodeCommand(command="G0", x=points[0][0], y=points[0][1]))
        
        # Pen down
        commands.append(GCodeCommand(command=self.pen_down_command))
        
        # Draw to subsequent points
        for point in points[1:]:
            commands.append(GCodeCommand(
                command="G1", 
                x=point[0], 
                y=point[1], 
                f=self.feed_rate
            ))
            
        # Close path if specified
        if closed and len(points) > 2:
            commands.append(GCodeCommand(
                command="G1", 
                x=points[0][0], 
                y=points[0][1], 
                f=self.feed_rate
            ))
            
        # Pen up
        commands.append(GCodeCommand(command=self.pen_up_command))
        
        return commands
        
    def _convert_drawing_element(self, element: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert a drawing element to command dictionaries"""
        element_type = element.get("type", "").lower()
        
        if element_type == "text":
            return self._convert_text_element(element)
        elif element_type == "grid":
            return self._convert_grid_element(element)
        else:
            # Treat as shape
            return self._convert_shape(element)
            
    def _convert_text_element(self, element: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert text element (simplified - just draws a box)"""
        x = element.get("x", 0)
        y = element.get("y", 0)
        width = element.get("width", len(element.get("text", "")) * 5)
        height = element.get("height", 10)
        
        # For now, just draw a bounding box
        return [
            {'type': 'move', 'x': x, 'y': y},
            {'type': 'line', 'x': x + width, 'y': y},
            {'type': 'line', 'x': x + width, 'y': y + height},
            {'type': 'line', 'x': x, 'y': y + height},
            {'type': 'line', 'x': x, 'y': y}
        ]
        
    def _convert_grid_element(self, element: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert grid element"""
        x = element.get("x", 0)
        y = element.get("y", 0)
        width = element.get("width", 50)
        height = element.get("height", 50)
        rows = element.get("rows", 5)
        cols = element.get("cols", 5)
        
        commands = []
        
        # Draw horizontal lines
        for i in range(rows + 1):
            line_y = y + (height * i / rows)
            commands.extend([
                {'type': 'move', 'x': x, 'y': line_y},
                {'type': 'line', 'x': x + width, 'y': line_y}
            ])
            
        # Draw vertical lines
        for i in range(cols + 1):
            line_x = x + (width * i / cols)
            commands.extend([
                {'type': 'move', 'x': line_x, 'y': y},
                {'type': 'line', 'x': line_x, 'y': y + height}
            ])
            
        return commands
        
    def validate_json_format(self, data: Any) -> List[ValidationError]:
        """Validate JSON data format"""
        errors = []
        
        try:
            format_type = self._detect_format(data)
            
            if format_type == "unknown":
                errors.append(ValidationError(
                    field="format",
                    message="Unknown JSON format - must contain 'commands', 'shapes', 'paths', or 'drawing'"
                ))
                
            # Format-specific validation
            if format_type == "command_list" and isinstance(data, list):
                for i, cmd in enumerate(data):
                    if not isinstance(cmd, dict) or "command" not in cmd:
                        errors.append(ValidationError(
                            field=f"commands[{i}]",
                            message="Command must be a dictionary with 'command' field"
                        ))
                        
        except Exception as e:
            errors.append(ValidationError(
                field="json",
                message=f"Validation error: {e}"
            ))
            
        return errors