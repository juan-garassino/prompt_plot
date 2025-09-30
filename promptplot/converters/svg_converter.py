"""
SVG to G-code conversion utilities

This module provides functionality for converting SVG files to G-code,
including path parsing, geometric shape extraction, and optimization
for pen plotting.
"""

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Optional, Union, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import math

from ..core.models import GCodeCommand, GCodeProgram
from ..core.exceptions import PromptPlotException


class SVGUnit(str, Enum):
    """SVG unit types"""
    PX = "px"
    MM = "mm"
    CM = "cm"
    IN = "in"
    PT = "pt"
    PC = "pc"


@dataclass
class SVGTransform:
    """SVG transformation matrix"""
    a: float = 1.0  # scale x
    b: float = 0.0  # skew y
    c: float = 0.0  # skew x
    d: float = 1.0  # scale y
    e: float = 0.0  # translate x
    f: float = 0.0  # translate y
    
    def apply(self, x: float, y: float) -> Tuple[float, float]:
        """Apply transformation to coordinates"""
        new_x = self.a * x + self.c * y + self.e
        new_y = self.b * x + self.d * y + self.f
        return new_x, new_y
    
    def combine(self, other: 'SVGTransform') -> 'SVGTransform':
        """Combine with another transformation"""
        return SVGTransform(
            a=self.a * other.a + self.b * other.c,
            b=self.a * other.b + self.b * other.d,
            c=self.c * other.a + self.d * other.c,
            d=self.c * other.b + self.d * other.d,
            e=self.e * other.a + self.f * other.c + other.e,
            f=self.e * other.b + self.f * other.d + other.f
        )


@dataclass
class SVGPath:
    """Represents an SVG path with commands"""
    commands: List[Dict[str, Any]]
    transform: Optional[SVGTransform] = None
    stroke_width: float = 1.0
    fill: Optional[str] = None
    stroke: Optional[str] = None
    
    def get_bounds(self) -> Optional[Dict[str, float]]:
        """Calculate bounding box of the path"""
        if not self.commands:
            return None
            
        x_coords = []
        y_coords = []
        
        for cmd in self.commands:
            if 'x' in cmd:
                x_coords.append(cmd['x'])
            if 'y' in cmd:
                y_coords.append(cmd['y'])
            if 'x1' in cmd:
                x_coords.append(cmd['x1'])
            if 'y1' in cmd:
                y_coords.append(cmd['y1'])
            if 'x2' in cmd:
                x_coords.append(cmd['x2'])
            if 'y2' in cmd:
                y_coords.append(cmd['y2'])
                
        if not x_coords or not y_coords:
            return None
            
        return {
            'min_x': min(x_coords),
            'max_x': max(x_coords),
            'min_y': min(y_coords),
            'max_y': max(y_coords)
        }


class SVGParseError(PromptPlotException):
    """Exception raised when SVG parsing fails"""
    pass


class SVGConverter:
    """
    Converts SVG files to G-code for pen plotting
    """
    
    # SVG namespace
    SVG_NS = {'svg': 'http://www.w3.org/2000/svg'}
    
    # Unit conversion to millimeters
    UNIT_TO_MM = {
        SVGUnit.PX: 0.264583,  # 96 DPI
        SVGUnit.MM: 1.0,
        SVGUnit.CM: 10.0,
        SVGUnit.IN: 25.4,
        SVGUnit.PT: 0.352778,
        SVGUnit.PC: 4.233333
    }
    
    def __init__(self, 
                 resolution: float = 0.1,
                 feed_rate: int = 1000,
                 pen_up_command: str = "M5",
                 pen_down_command: str = "M3"):
        """
        Initialize SVG converter
        
        Args:
            resolution: Resolution for curve approximation (mm)
            feed_rate: Default feed rate for movements
            pen_up_command: G-code command for pen up
            pen_down_command: G-code command for pen down
        """
        self.resolution = resolution
        self.feed_rate = feed_rate
        self.pen_up_command = pen_up_command
        self.pen_down_command = pen_down_command
        self.current_position = (0.0, 0.0)
        
    def convert_file(self, filepath: Union[str, Path]) -> GCodeProgram:
        """
        Convert an SVG file to G-code
        
        Args:
            filepath: Path to SVG file
            
        Returns:
            GCodeProgram object
            
        Raises:
            SVGParseError: If SVG parsing fails
            FileNotFoundError: If file doesn't exist
        """
        filepath = Path(filepath)
        
        if not filepath.exists():
            raise FileNotFoundError(f"SVG file not found: {filepath}")
            
        try:
            tree = ET.parse(filepath)
            root = tree.getroot()
        except ET.ParseError as e:
            raise SVGParseError(f"Failed to parse SVG: {e}")
            
        # Extract SVG dimensions and viewBox
        svg_info = self._extract_svg_info(root)
        
        # Extract all drawable paths
        paths = self._extract_paths(root)
        
        # Convert paths to G-code commands
        commands = self._paths_to_gcode(paths, svg_info)
        
        # Create program with metadata
        metadata = {
            'source_file': filepath.name,
            'svg_width': svg_info.get('width'),
            'svg_height': svg_info.get('height'),
            'path_count': len(paths),
            'resolution': self.resolution,
            'feed_rate': self.feed_rate
        }
        
        return GCodeProgram(commands=commands, metadata=metadata)
        
    def _extract_svg_info(self, root: ET.Element) -> Dict[str, Any]:
        """Extract SVG dimensions and viewBox information"""
        info = {}
        
        # Get width and height
        width_str = root.get('width', '100')
        height_str = root.get('height', '100')
        
        info['width'] = self._parse_dimension(width_str)
        info['height'] = self._parse_dimension(height_str)
        
        # Get viewBox
        viewbox_str = root.get('viewBox')
        if viewbox_str:
            try:
                viewbox = [float(x) for x in viewbox_str.split()]
                if len(viewbox) == 4:
                    info['viewBox'] = {
                        'x': viewbox[0],
                        'y': viewbox[1], 
                        'width': viewbox[2],
                        'height': viewbox[3]
                    }
            except ValueError:
                pass
                
        return info
        
    def _parse_dimension(self, dim_str: str) -> float:
        """Parse SVG dimension string to millimeters"""
        if not dim_str:
            return 100.0
            
        # Extract number and unit
        match = re.match(r'([+-]?\d*\.?\d+)([a-zA-Z%]*)', dim_str.strip())
        if not match:
            return 100.0
            
        value = float(match.group(1))
        unit = match.group(2).lower() or 'px'
        
        # Convert to millimeters
        if unit in self.UNIT_TO_MM:
            return value * self.UNIT_TO_MM[unit]
        elif unit == '%':
            return value  # Handle percentage separately
        else:
            return value * self.UNIT_TO_MM[SVGUnit.PX]  # Default to pixels
            
    def _extract_paths(self, root: ET.Element) -> List[SVGPath]:
        """Extract all drawable paths from SVG"""
        paths = []
        
        # Process different SVG elements
        self._process_element(root, paths, SVGTransform())
        
        return paths
        
    def _process_element(self, element: ET.Element, paths: List[SVGPath], parent_transform: SVGTransform):
        """Recursively process SVG elements"""
        # Get element transform
        transform = self._parse_transform(element.get('transform', ''))
        combined_transform = parent_transform.combine(transform)
        
        # Get style attributes
        style = self._parse_style(element)
        
        # Process based on element type
        tag = element.tag.split('}')[-1] if '}' in element.tag else element.tag
        
        if tag == 'path':
            path = self._parse_path_element(element, combined_transform, style)
            if path:
                paths.append(path)
        elif tag == 'line':
            path = self._parse_line_element(element, combined_transform, style)
            if path:
                paths.append(path)
        elif tag == 'rect':
            path = self._parse_rect_element(element, combined_transform, style)
            if path:
                paths.append(path)
        elif tag == 'circle':
            path = self._parse_circle_element(element, combined_transform, style)
            if path:
                paths.append(path)
        elif tag == 'ellipse':
            path = self._parse_ellipse_element(element, combined_transform, style)
            if path:
                paths.append(path)
        elif tag == 'polyline' or tag == 'polygon':
            path = self._parse_poly_element(element, combined_transform, style)
            if path:
                paths.append(path)
        elif tag in ['g', 'svg']:
            # Process group children
            for child in element:
                self._process_element(child, paths, combined_transform)
                
    def _parse_transform(self, transform_str: str) -> SVGTransform:
        """Parse SVG transform attribute"""
        if not transform_str:
            return SVGTransform()
            
        # Simple transform parsing - handle basic cases
        transform = SVGTransform()
        
        # Parse translate
        translate_match = re.search(r'translate\s*\(\s*([^)]+)\)', transform_str)
        if translate_match:
            values = [float(x) for x in translate_match.group(1).split(',')]
            transform.e = values[0]
            if len(values) > 1:
                transform.f = values[1]
                
        # Parse scale
        scale_match = re.search(r'scale\s*\(\s*([^)]+)\)', transform_str)
        if scale_match:
            values = [float(x) for x in scale_match.group(1).split(',')]
            transform.a = values[0]
            if len(values) > 1:
                transform.d = values[1]
            else:
                transform.d = values[0]
                
        # Parse rotate
        rotate_match = re.search(r'rotate\s*\(\s*([^)]+)\)', transform_str)
        if rotate_match:
            values = [float(x) for x in rotate_match.group(1).split(',')]
            angle = math.radians(values[0])
            cos_a = math.cos(angle)
            sin_a = math.sin(angle)
            
            # Apply rotation matrix
            old_a, old_b, old_c, old_d = transform.a, transform.b, transform.c, transform.d
            transform.a = old_a * cos_a - old_b * sin_a
            transform.b = old_a * sin_a + old_b * cos_a
            transform.c = old_c * cos_a - old_d * sin_a
            transform.d = old_c * sin_a + old_d * cos_a
            
        return transform
        
    def _parse_style(self, element: ET.Element) -> Dict[str, str]:
        """Parse style attributes from element"""
        style = {}
        
        # Parse style attribute
        style_attr = element.get('style', '')
        if style_attr:
            for item in style_attr.split(';'):
                if ':' in item:
                    key, value = item.split(':', 1)
                    style[key.strip()] = value.strip()
                    
        # Add direct attributes
        for attr in ['fill', 'stroke', 'stroke-width']:
            value = element.get(attr)
            if value:
                style[attr] = value
                
        return style
        
    def _parse_path_element(self, element: ET.Element, transform: SVGTransform, style: Dict[str, str]) -> Optional[SVGPath]:
        """Parse SVG path element"""
        d = element.get('d')
        if not d:
            return None
            
        commands = self._parse_path_data(d)
        if not commands:
            return None
            
        return SVGPath(
            commands=commands,
            transform=transform,
            stroke_width=float(style.get('stroke-width', '1')),
            fill=style.get('fill'),
            stroke=style.get('stroke')
        )
        
    def _parse_path_data(self, path_data: str) -> List[Dict[str, Any]]:
        """Parse SVG path data string"""
        commands = []
        
        # Simple path data parser - handles basic commands
        # This is a simplified version; a full implementation would be more complex
        
        # Remove extra whitespace and normalize
        path_data = re.sub(r'\s+', ' ', path_data.strip())
        
        # Split into command segments
        segments = re.findall(r'[MmLlHhVvCcSsQqTtAaZz][^MmLlHhVvCcSsQqTtAaZz]*', path_data)
        
        current_pos = [0.0, 0.0]
        
        for segment in segments:
            cmd_char = segment[0]
            params_str = segment[1:].strip()
            
            if params_str:
                # Parse parameters
                params = [float(x) for x in re.findall(r'[+-]?\d*\.?\d+', params_str)]
            else:
                params = []
                
            if cmd_char.upper() == 'M':  # Move to
                if len(params) >= 2:
                    x, y = params[0], params[1]
                    if cmd_char.islower():  # Relative
                        x += current_pos[0]
                        y += current_pos[1]
                    commands.append({'type': 'move', 'x': x, 'y': y})
                    current_pos = [x, y]
                    
            elif cmd_char.upper() == 'L':  # Line to
                if len(params) >= 2:
                    x, y = params[0], params[1]
                    if cmd_char.islower():  # Relative
                        x += current_pos[0]
                        y += current_pos[1]
                    commands.append({'type': 'line', 'x': x, 'y': y})
                    current_pos = [x, y]
                    
            elif cmd_char.upper() == 'H':  # Horizontal line
                if len(params) >= 1:
                    x = params[0]
                    if cmd_char.islower():  # Relative
                        x += current_pos[0]
                    commands.append({'type': 'line', 'x': x, 'y': current_pos[1]})
                    current_pos[0] = x
                    
            elif cmd_char.upper() == 'V':  # Vertical line
                if len(params) >= 1:
                    y = params[0]
                    if cmd_char.islower():  # Relative
                        y += current_pos[1]
                    commands.append({'type': 'line', 'x': current_pos[0], 'y': y})
                    current_pos[1] = y
                    
            elif cmd_char.upper() == 'C':  # Cubic Bezier curve
                if len(params) >= 6:
                    x1, y1, x2, y2, x, y = params[:6]
                    if cmd_char.islower():  # Relative
                        x1 += current_pos[0]
                        y1 += current_pos[1]
                        x2 += current_pos[0]
                        y2 += current_pos[1]
                        x += current_pos[0]
                        y += current_pos[1]
                    commands.append({
                        'type': 'cubic_bezier',
                        'x1': x1, 'y1': y1,
                        'x2': x2, 'y2': y2,
                        'x': x, 'y': y
                    })
                    current_pos = [x, y]
                    
            elif cmd_char.upper() == 'Z':  # Close path
                commands.append({'type': 'close'})
                
        return commands 
       
    def _parse_line_element(self, element: ET.Element, transform: SVGTransform, style: Dict[str, str]) -> Optional[SVGPath]:
        """Parse SVG line element"""
        x1 = float(element.get('x1', '0'))
        y1 = float(element.get('y1', '0'))
        x2 = float(element.get('x2', '0'))
        y2 = float(element.get('y2', '0'))
        
        commands = [
            {'type': 'move', 'x': x1, 'y': y1},
            {'type': 'line', 'x': x2, 'y': y2}
        ]
        
        return SVGPath(
            commands=commands,
            transform=transform,
            stroke_width=float(style.get('stroke-width', '1')),
            stroke=style.get('stroke')
        )
        
    def _parse_rect_element(self, element: ET.Element, transform: SVGTransform, style: Dict[str, str]) -> Optional[SVGPath]:
        """Parse SVG rectangle element"""
        x = float(element.get('x', '0'))
        y = float(element.get('y', '0'))
        width = float(element.get('width', '0'))
        height = float(element.get('height', '0'))
        
        if width <= 0 or height <= 0:
            return None
            
        # Create rectangle path
        commands = [
            {'type': 'move', 'x': x, 'y': y},
            {'type': 'line', 'x': x + width, 'y': y},
            {'type': 'line', 'x': x + width, 'y': y + height},
            {'type': 'line', 'x': x, 'y': y + height},
            {'type': 'close'}
        ]
        
        return SVGPath(
            commands=commands,
            transform=transform,
            stroke_width=float(style.get('stroke-width', '1')),
            fill=style.get('fill'),
            stroke=style.get('stroke')
        )
        
    def _parse_circle_element(self, element: ET.Element, transform: SVGTransform, style: Dict[str, str]) -> Optional[SVGPath]:
        """Parse SVG circle element"""
        cx = float(element.get('cx', '0'))
        cy = float(element.get('cy', '0'))
        r = float(element.get('r', '0'))
        
        if r <= 0:
            return None
            
        # Approximate circle with line segments
        commands = self._approximate_circle(cx, cy, r)
        
        return SVGPath(
            commands=commands,
            transform=transform,
            stroke_width=float(style.get('stroke-width', '1')),
            fill=style.get('fill'),
            stroke=style.get('stroke')
        )
        
    def _parse_ellipse_element(self, element: ET.Element, transform: SVGTransform, style: Dict[str, str]) -> Optional[SVGPath]:
        """Parse SVG ellipse element"""
        cx = float(element.get('cx', '0'))
        cy = float(element.get('cy', '0'))
        rx = float(element.get('rx', '0'))
        ry = float(element.get('ry', '0'))
        
        if rx <= 0 or ry <= 0:
            return None
            
        # Approximate ellipse with line segments
        commands = self._approximate_ellipse(cx, cy, rx, ry)
        
        return SVGPath(
            commands=commands,
            transform=transform,
            stroke_width=float(style.get('stroke-width', '1')),
            fill=style.get('fill'),
            stroke=style.get('stroke')
        )
        
    def _parse_poly_element(self, element: ET.Element, transform: SVGTransform, style: Dict[str, str]) -> Optional[SVGPath]:
        """Parse SVG polyline or polygon element"""
        points_str = element.get('points', '')
        if not points_str:
            return None
            
        # Parse points
        points = []
        coords = re.findall(r'[+-]?\d*\.?\d+', points_str)
        
        for i in range(0, len(coords) - 1, 2):
            x = float(coords[i])
            y = float(coords[i + 1])
            points.append((x, y))
            
        if len(points) < 2:
            return None
            
        # Create path commands
        commands = [{'type': 'move', 'x': points[0][0], 'y': points[0][1]}]
        
        for x, y in points[1:]:
            commands.append({'type': 'line', 'x': x, 'y': y})
            
        # Close polygon if it's a polygon element
        if element.tag.split('}')[-1] == 'polygon':
            commands.append({'type': 'close'})
            
        return SVGPath(
            commands=commands,
            transform=transform,
            stroke_width=float(style.get('stroke-width', '1')),
            fill=style.get('fill'),
            stroke=style.get('stroke')
        )
        
    def _approximate_circle(self, cx: float, cy: float, r: float) -> List[Dict[str, Any]]:
        """Approximate circle with line segments"""
        # Calculate number of segments based on resolution
        circumference = 2 * math.pi * r
        num_segments = max(8, int(circumference / self.resolution))
        
        commands = []
        angle_step = 2 * math.pi / num_segments
        
        # Start point
        start_x = cx + r
        start_y = cy
        commands.append({'type': 'move', 'x': start_x, 'y': start_y})
        
        # Generate segments
        for i in range(1, num_segments + 1):
            angle = i * angle_step
            x = cx + r * math.cos(angle)
            y = cy + r * math.sin(angle)
            commands.append({'type': 'line', 'x': x, 'y': y})
            
        return commands
        
    def _approximate_ellipse(self, cx: float, cy: float, rx: float, ry: float) -> List[Dict[str, Any]]:
        """Approximate ellipse with line segments"""
        # Calculate number of segments based on resolution and larger radius
        max_radius = max(rx, ry)
        circumference = 2 * math.pi * max_radius
        num_segments = max(8, int(circumference / self.resolution))
        
        commands = []
        angle_step = 2 * math.pi / num_segments
        
        # Start point
        start_x = cx + rx
        start_y = cy
        commands.append({'type': 'move', 'x': start_x, 'y': start_y})
        
        # Generate segments
        for i in range(1, num_segments + 1):
            angle = i * angle_step
            x = cx + rx * math.cos(angle)
            y = cy + ry * math.sin(angle)
            commands.append({'type': 'line', 'x': x, 'y': y})
            
        return commands
        
    def _approximate_bezier(self, x0: float, y0: float, x1: float, y1: float, 
                           x2: float, y2: float, x3: float, y3: float) -> List[Dict[str, Any]]:
        """Approximate cubic Bezier curve with line segments"""
        # Calculate curve length approximation
        chord_length = math.sqrt((x3 - x0)**2 + (y3 - y0)**2)
        control_length = (math.sqrt((x1 - x0)**2 + (y1 - y0)**2) + 
                         math.sqrt((x2 - x1)**2 + (y2 - y1)**2) + 
                         math.sqrt((x3 - x2)**2 + (y3 - y2)**2))
        
        # Estimate curve length
        curve_length = (chord_length + control_length) / 2
        num_segments = max(2, int(curve_length / self.resolution))
        
        commands = []
        
        # Generate points along the curve
        for i in range(1, num_segments + 1):
            t = i / num_segments
            
            # Cubic Bezier formula
            x = ((1-t)**3 * x0 + 
                 3*(1-t)**2*t * x1 + 
                 3*(1-t)*t**2 * x2 + 
                 t**3 * x3)
            y = ((1-t)**3 * y0 + 
                 3*(1-t)**2*t * y1 + 
                 3*(1-t)*t**2 * y2 + 
                 t**3 * y3)
                 
            commands.append({'type': 'line', 'x': x, 'y': y})
            
        return commands
        
    def _paths_to_gcode(self, paths: List[SVGPath], svg_info: Dict[str, Any]) -> List[GCodeCommand]:
        """Convert SVG paths to G-code commands"""
        gcode_commands = []
        
        # Start with pen up and move to origin
        gcode_commands.append(GCodeCommand(command=self.pen_up_command))
        gcode_commands.append(GCodeCommand(command="G0", x=0.0, y=0.0))
        
        pen_is_down = False
        
        for path in paths:
            # Skip paths that shouldn't be drawn
            if not self._should_draw_path(path):
                continue
                
            path_commands = self._convert_path_to_gcode(path)
            
            for cmd_dict in path_commands:
                if cmd_dict['type'] == 'move':
                    # Pen up, move, pen down
                    if pen_is_down:
                        gcode_commands.append(GCodeCommand(command=self.pen_up_command))
                        pen_is_down = False
                        
                    x, y = cmd_dict['x'], cmd_dict['y']
                    if path.transform:
                        x, y = path.transform.apply(x, y)
                        
                    gcode_commands.append(GCodeCommand(command="G0", x=x, y=y))
                    
                elif cmd_dict['type'] == 'line':
                    # Ensure pen is down for drawing
                    if not pen_is_down:
                        gcode_commands.append(GCodeCommand(command=self.pen_down_command))
                        pen_is_down = True
                        
                    x, y = cmd_dict['x'], cmd_dict['y']
                    if path.transform:
                        x, y = path.transform.apply(x, y)
                        
                    gcode_commands.append(GCodeCommand(command="G1", x=x, y=y, f=self.feed_rate))
                    
                elif cmd_dict['type'] == 'close':
                    # Close path by drawing back to start if pen is down
                    if pen_is_down and path.commands:
                        first_cmd = path.commands[0]
                        if first_cmd['type'] == 'move':
                            x, y = first_cmd['x'], first_cmd['y']
                            if path.transform:
                                x, y = path.transform.apply(x, y)
                            gcode_commands.append(GCodeCommand(command="G1", x=x, y=y, f=self.feed_rate))
                            
        # End with pen up
        if pen_is_down:
            gcode_commands.append(GCodeCommand(command=self.pen_up_command))
            
        # Add completion command
        gcode_commands.append(GCodeCommand(command="COMPLETE"))
        
        return gcode_commands
        
    def _should_draw_path(self, path: SVGPath) -> bool:
        """Determine if a path should be drawn based on style"""
        # Don't draw if explicitly no stroke and no fill
        if (path.stroke == 'none' and 
            (path.fill == 'none' or path.fill is None)):
            return False
            
        # Don't draw if stroke width is 0
        if path.stroke_width <= 0:
            return False
            
        return True
        
    def _convert_path_to_gcode(self, path: SVGPath) -> List[Dict[str, Any]]:
        """Convert a single SVG path to G-code command dictionaries"""
        gcode_commands = []
        
        for cmd in path.commands:
            if cmd['type'] == 'move':
                gcode_commands.append(cmd)
            elif cmd['type'] == 'line':
                gcode_commands.append(cmd)
            elif cmd['type'] == 'cubic_bezier':
                # Approximate Bezier curve
                if gcode_commands:
                    # Get current position from last command
                    last_cmd = gcode_commands[-1]
                    x0, y0 = last_cmd.get('x', 0), last_cmd.get('y', 0)
                else:
                    x0, y0 = 0, 0
                    
                bezier_commands = self._approximate_bezier(
                    x0, y0, cmd['x1'], cmd['y1'],
                    cmd['x2'], cmd['y2'], cmd['x'], cmd['y']
                )
                gcode_commands.extend(bezier_commands)
            elif cmd['type'] == 'close':
                gcode_commands.append(cmd)
                
        return gcode_commands
        
    def optimize_pen_movements(self, program: GCodeProgram) -> GCodeProgram:
        """
        Optimize pen movements to reduce plotting time
        
        This implements basic optimizations like removing redundant pen up/down
        commands and optimizing travel paths.
        """
        optimized_commands = []
        pen_state = None  # None, 'up', 'down'
        
        for cmd in program.commands:
            if cmd.command == self.pen_up_command:
                if pen_state != 'up':
                    optimized_commands.append(cmd)
                    pen_state = 'up'
            elif cmd.command == self.pen_down_command:
                if pen_state != 'down':
                    optimized_commands.append(cmd)
                    pen_state = 'down'
            else:
                optimized_commands.append(cmd)
                
        return GCodeProgram(
            commands=optimized_commands,
            metadata={
                **program.metadata,
                'pen_optimized': True,
                'original_commands': len(program.commands),
                'optimized_commands': len(optimized_commands)
            }
        )