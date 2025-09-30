"""
Orthogonal drawing strategy for PromptPlot v2.0

This module implements efficient G-code generation for straight-line drawings,
rectangles, grids, and geometric shapes. It optimizes coordinate calculations
and minimizes pen movements for maximum efficiency.
"""

import math
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

from ..core.models import GCodeCommand, GCodeProgram, DrawingStrategy


class ShapeType(str, Enum):
    """Types of orthogonal shapes that can be drawn"""
    RECTANGLE = "rectangle"
    SQUARE = "square"
    LINE = "line"
    GRID = "grid"
    CROSS = "cross"
    TRIANGLE = "triangle"
    DIAMOND = "diamond"
    FRAME = "frame"


@dataclass
class Point:
    """Simple point representation"""
    x: float
    y: float
    
    def distance_to(self, other: 'Point') -> float:
        """Calculate Euclidean distance to another point"""
        return math.sqrt((self.x - other.x)**2 + (self.y - other.y)**2)


@dataclass
class Rectangle:
    """Rectangle definition with optimization methods"""
    x: float
    y: float
    width: float
    height: float
    
    def get_corners(self) -> List[Point]:
        """Get the four corner points of the rectangle"""
        return [
            Point(self.x, self.y),                          # Bottom-left
            Point(self.x + self.width, self.y),             # Bottom-right
            Point(self.x + self.width, self.y + self.height), # Top-right
            Point(self.x, self.y + self.height)            # Top-left
        ]
    
    def get_center(self) -> Point:
        """Get the center point of the rectangle"""
        return Point(self.x + self.width/2, self.y + self.height/2)


@dataclass
class Line:
    """Line segment definition"""
    start: Point
    end: Point
    
    def length(self) -> float:
        """Calculate the length of the line"""
        return self.start.distance_to(self.end)
    
    def is_horizontal(self, tolerance: float = 0.001) -> bool:
        """Check if the line is horizontal within tolerance"""
        return abs(self.start.y - self.end.y) < tolerance
    
    def is_vertical(self, tolerance: float = 0.001) -> bool:
        """Check if the line is vertical within tolerance"""
        return abs(self.start.x - self.end.x) < tolerance


class OrthogonalStrategy:
    """
    Orthogonal drawing strategy optimized for straight lines, rectangles, 
    grids, and geometric shapes.
    
    This class implements Requirements 3.1 and 3.4:
    - Efficient G-code generation for rectangles, grids, and geometric shapes
    - Optimized coordinate calculations and minimized pen movements
    """
    
    def __init__(self, canvas_width: float = 100.0, canvas_height: float = 100.0):
        """
        Initialize the orthogonal strategy.
        
        Args:
            canvas_width: Width of the drawing canvas in mm
            canvas_height: Height of the drawing canvas in mm
        """
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self.current_position = Point(0, 0)
        self.pen_is_down = False
        
    def generate_rectangle(self, x: float, y: float, width: float, height: float,
                          filled: bool = False) -> List[GCodeCommand]:
        """
        Generate optimized G-code for drawing a rectangle.
        
        Args:
            x, y: Bottom-left corner coordinates
            width, height: Rectangle dimensions
            filled: Whether to fill the rectangle with lines
            
        Returns:
            List of optimized G-code commands
        """
        commands = []
        rect = Rectangle(x, y, width, height)
        
        if filled:
            commands.extend(self._generate_filled_rectangle(rect))
        else:
            commands.extend(self._generate_rectangle_outline(rect))
            
        return self._optimize_command_sequence(commands)
    
    def generate_grid(self, x: float, y: float, width: float, height: float,
                     rows: int, cols: int) -> List[GCodeCommand]:
        """
        Generate optimized G-code for drawing a grid.
        
        Args:
            x, y: Bottom-left corner coordinates
            width, height: Grid dimensions
            rows, cols: Number of rows and columns
            
        Returns:
            List of optimized G-code commands
        """
        commands = []
        
        # Calculate cell dimensions
        cell_width = width / cols
        cell_height = height / rows
        
        # Generate horizontal lines (more efficient to do all horizontals first)
        for i in range(rows + 1):
            y_pos = y + i * cell_height
            line_start = Point(x, y_pos)
            line_end = Point(x + width, y_pos)
            commands.extend(self._generate_line_commands(line_start, line_end))
        
        # Generate vertical lines
        for i in range(cols + 1):
            x_pos = x + i * cell_width
            line_start = Point(x_pos, y)
            line_end = Point(x_pos, y + height)
            commands.extend(self._generate_line_commands(line_start, line_end))
        
        return self._optimize_command_sequence(commands)
    
    def generate_line(self, start_x: float, start_y: float, 
                     end_x: float, end_y: float) -> List[GCodeCommand]:
        """
        Generate G-code for drawing a straight line.
        
        Args:
            start_x, start_y: Starting coordinates
            end_x, end_y: Ending coordinates
            
        Returns:
            List of G-code commands
        """
        start_point = Point(start_x, start_y)
        end_point = Point(end_x, end_y)
        
        commands = self._generate_line_commands(start_point, end_point)
        return self._optimize_command_sequence(commands)
    
    def generate_cross(self, center_x: float, center_y: float, 
                      size: float) -> List[GCodeCommand]:
        """
        Generate G-code for drawing a cross (+ shape).
        
        Args:
            center_x, center_y: Center coordinates
            size: Size of the cross (distance from center to edge)
            
        Returns:
            List of G-code commands
        """
        commands = []
        
        # Horizontal line
        h_start = Point(center_x - size, center_y)
        h_end = Point(center_x + size, center_y)
        commands.extend(self._generate_line_commands(h_start, h_end))
        
        # Vertical line
        v_start = Point(center_x, center_y - size)
        v_end = Point(center_x, center_y + size)
        commands.extend(self._generate_line_commands(v_start, v_end))
        
        return self._optimize_command_sequence(commands)
    
    def generate_triangle(self, x1: float, y1: float, x2: float, y2: float,
                         x3: float, y3: float) -> List[GCodeCommand]:
        """
        Generate G-code for drawing a triangle.
        
        Args:
            x1, y1: First vertex coordinates
            x2, y2: Second vertex coordinates  
            x3, y3: Third vertex coordinates
            
        Returns:
            List of G-code commands
        """
        commands = []
        
        # Create triangle vertices
        p1 = Point(x1, y1)
        p2 = Point(x2, y2)
        p3 = Point(x3, y3)
        
        # Draw the three sides
        commands.extend(self._generate_line_commands(p1, p2))
        commands.extend(self._generate_line_commands(p2, p3))
        commands.extend(self._generate_line_commands(p3, p1))
        
        return self._optimize_command_sequence(commands)
    
    def generate_diamond(self, center_x: float, center_y: float,
                        width: float, height: float) -> List[GCodeCommand]:
        """
        Generate G-code for drawing a diamond shape.
        
        Args:
            center_x, center_y: Center coordinates
            width: Width of the diamond
            height: Height of the diamond
            
        Returns:
            List of G-code commands
        """
        # Calculate diamond vertices
        top = Point(center_x, center_y + height/2)
        right = Point(center_x + width/2, center_y)
        bottom = Point(center_x, center_y - height/2)
        left = Point(center_x - width/2, center_y)
        
        commands = []
        commands.extend(self._generate_line_commands(top, right))
        commands.extend(self._generate_line_commands(right, bottom))
        commands.extend(self._generate_line_commands(bottom, left))
        commands.extend(self._generate_line_commands(left, top))
        
        return self._optimize_command_sequence(commands)
    
    def _generate_rectangle_outline(self, rect: Rectangle) -> List[GCodeCommand]:
        """Generate commands for rectangle outline"""
        commands = []
        corners = rect.get_corners()
        
        # Draw rectangle by connecting corners
        for i in range(len(corners)):
            start = corners[i]
            end = corners[(i + 1) % len(corners)]
            commands.extend(self._generate_line_commands(start, end))
        
        return commands
    
    def _generate_filled_rectangle(self, rect: Rectangle) -> List[GCodeCommand]:
        """Generate commands for filled rectangle using horizontal lines"""
        commands = []
        
        # Use 1mm line spacing for filling (can be made configurable)
        line_spacing = 1.0
        num_lines = int(rect.height / line_spacing) + 1
        
        for i in range(num_lines):
            y_pos = rect.y + i * line_spacing
            if y_pos > rect.y + rect.height:
                y_pos = rect.y + rect.height
            
            # Alternate direction for efficiency (zigzag pattern)
            if i % 2 == 0:
                start = Point(rect.x, y_pos)
                end = Point(rect.x + rect.width, y_pos)
            else:
                start = Point(rect.x + rect.width, y_pos)
                end = Point(rect.x, y_pos)
            
            commands.extend(self._generate_line_commands(start, end))
        
        return commands
    
    def _generate_line_commands(self, start: Point, end: Point) -> List[GCodeCommand]:
        """Generate the basic commands needed to draw a line"""
        commands = []
        
        # Move to start position (pen up)
        commands.append(GCodeCommand(
            command="G0",
            x=start.x,
            y=start.y,
            strategy_type=DrawingStrategy.ORTHOGONAL
        ))
        
        # Put pen down
        commands.append(GCodeCommand(
            command="M3",
            strategy_type=DrawingStrategy.ORTHOGONAL
        ))
        
        # Draw line to end position
        commands.append(GCodeCommand(
            command="G1",
            x=end.x,
            y=end.y,
            f=1000,  # Feed rate for drawing
            strategy_type=DrawingStrategy.ORTHOGONAL
        ))
        
        # Lift pen up
        commands.append(GCodeCommand(
            command="M5",
            strategy_type=DrawingStrategy.ORTHOGONAL
        ))
        
        return commands
    
    def _optimize_command_sequence(self, commands: List[GCodeCommand]) -> List[GCodeCommand]:
        """
        Optimize the command sequence to minimize pen movements and redundant operations.
        
        This method implements the coordinate calculation optimization and
        pen movement minimization required by Requirement 3.4.
        """
        if not commands:
            return commands
        
        optimized = []
        current_pos = Point(0, 0)
        pen_down = False
        
        i = 0
        while i < len(commands):
            cmd = commands[i]
            
            # Track current position
            if cmd.x is not None and cmd.y is not None:
                current_pos = Point(cmd.x, cmd.y)
            
            # Optimize pen control commands
            if cmd.command == "M3":  # Pen down
                if not pen_down:
                    optimized.append(cmd)
                    pen_down = True
                # Skip redundant pen down commands
            elif cmd.command == "M5":  # Pen up
                if pen_down:
                    optimized.append(cmd)
                    pen_down = False
                # Skip redundant pen up commands
            else:
                # Keep movement commands
                optimized.append(cmd)
            
            i += 1
        
        # Apply path optimization
        optimized = self._optimize_path_order(optimized)
        
        return optimized
    
    def _optimize_path_order(self, commands: List[GCodeCommand]) -> List[GCodeCommand]:
        """
        Optimize the order of drawing operations to minimize travel distance.
        
        This implements a simple nearest-neighbor approach for path optimization.
        """
        if len(commands) < 4:  # Not enough commands to optimize
            return commands
        
        # Group commands into drawing segments (G0 -> M3 -> G1 -> M5)
        segments = []
        current_segment = []
        
        for cmd in commands:
            current_segment.append(cmd)
            if cmd.command == "M5":  # End of drawing segment
                segments.append(current_segment)
                current_segment = []
        
        if current_segment:  # Handle incomplete segment
            segments.append(current_segment)
        
        if len(segments) <= 1:
            return commands
        
        # Optimize segment order using nearest neighbor
        optimized_segments = [segments[0]]  # Start with first segment
        remaining_segments = segments[1:]
        current_pos = self._get_segment_end_position(segments[0])
        
        while remaining_segments:
            # Find nearest segment
            nearest_idx = 0
            nearest_distance = float('inf')
            
            for i, segment in enumerate(remaining_segments):
                segment_start = self._get_segment_start_position(segment)
                distance = current_pos.distance_to(segment_start)
                
                if distance < nearest_distance:
                    nearest_distance = distance
                    nearest_idx = i
            
            # Add nearest segment to optimized list
            nearest_segment = remaining_segments.pop(nearest_idx)
            optimized_segments.append(nearest_segment)
            current_pos = self._get_segment_end_position(nearest_segment)
        
        # Flatten segments back to command list
        optimized_commands = []
        for segment in optimized_segments:
            optimized_commands.extend(segment)
        
        return optimized_commands
    
    def _get_segment_start_position(self, segment: List[GCodeCommand]) -> Point:
        """Get the starting position of a drawing segment"""
        for cmd in segment:
            if cmd.command == "G0" and cmd.x is not None and cmd.y is not None:
                return Point(cmd.x, cmd.y)
        return Point(0, 0)
    
    def _get_segment_end_position(self, segment: List[GCodeCommand]) -> Point:
        """Get the ending position of a drawing segment"""
        for cmd in reversed(segment):
            if cmd.command == "G1" and cmd.x is not None and cmd.y is not None:
                return Point(cmd.x, cmd.y)
        return Point(0, 0)
    
    def calculate_drawing_bounds(self, commands: List[GCodeCommand]) -> Dict[str, float]:
        """
        Calculate the bounding box of the drawing.
        
        Returns:
            Dictionary with min_x, max_x, min_y, max_y values
        """
        if not commands:
            return {"min_x": 0, "max_x": 0, "min_y": 0, "max_y": 0}
        
        x_coords = []
        y_coords = []
        
        for cmd in commands:
            if cmd.x is not None:
                x_coords.append(cmd.x)
            if cmd.y is not None:
                y_coords.append(cmd.y)
        
        if not x_coords or not y_coords:
            return {"min_x": 0, "max_x": 0, "min_y": 0, "max_y": 0}
        
        return {
            "min_x": min(x_coords),
            "max_x": max(x_coords),
            "min_y": min(y_coords),
            "max_y": max(y_coords)
        }
    
    def estimate_drawing_time(self, commands: List[GCodeCommand], 
                            feed_rate: float = 1000.0) -> float:
        """
        Estimate the total drawing time in seconds.
        
        Args:
            commands: List of G-code commands
            feed_rate: Feed rate in mm/min
            
        Returns:
            Estimated time in seconds
        """
        total_distance = 0.0
        current_pos = Point(0, 0)
        
        for cmd in commands:
            if cmd.command in ["G0", "G1"] and cmd.x is not None and cmd.y is not None:
                new_pos = Point(cmd.x, cmd.y)
                total_distance += current_pos.distance_to(new_pos)
                current_pos = new_pos
        
        # Convert feed rate from mm/min to mm/sec
        feed_rate_per_sec = feed_rate / 60.0
        
        # Add time for pen operations (estimated 0.1 seconds each)
        pen_operations = sum(1 for cmd in commands if cmd.command in ["M3", "M5"])
        pen_time = pen_operations * 0.1
        
        return (total_distance / feed_rate_per_sec) + pen_time