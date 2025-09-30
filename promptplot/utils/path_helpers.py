"""
SVG path processing utilities for PromptPlot v2.0

This module provides utilities for parsing, processing, and converting
SVG path data into coordinate sequences suitable for G-code generation.
"""

import re
from typing import List, Tuple, Dict, Any, Optional, Union, Generator
from dataclasses import dataclass
from enum import Enum
import math

from .math_helpers import (
    Point2D, BoundingBox, calculate_distance, calculate_curve_points,
    calculate_circle_points, transform_path, simplify_path
)


class PathCommand(str, Enum):
    """SVG path command types"""
    MOVE_TO = "M"
    MOVE_TO_REL = "m"
    LINE_TO = "L"
    LINE_TO_REL = "l"
    HORIZONTAL_LINE = "H"
    HORIZONTAL_LINE_REL = "h"
    VERTICAL_LINE = "V"
    VERTICAL_LINE_REL = "v"
    CURVE_TO = "C"
    CURVE_TO_REL = "c"
    SMOOTH_CURVE = "S"
    SMOOTH_CURVE_REL = "s"
    QUADRATIC_CURVE = "Q"
    QUADRATIC_CURVE_REL = "q"
    SMOOTH_QUADRATIC = "T"
    SMOOTH_QUADRATIC_REL = "t"
    ARC = "A"
    ARC_REL = "a"
    CLOSE_PATH = "Z"
    CLOSE_PATH_REL = "z"


@dataclass
class PathSegment:
    """Represents a segment of an SVG path"""
    command: PathCommand
    points: List[Tuple[float, float]]
    start_point: Tuple[float, float]
    end_point: Tuple[float, float]
    is_relative: bool = False
    
    def to_absolute_points(self, resolution: int = 20) -> List[Tuple[float, float]]:
        """Convert segment to list of absolute coordinate points"""
        if self.command in [PathCommand.MOVE_TO, PathCommand.MOVE_TO_REL,
                           PathCommand.LINE_TO, PathCommand.LINE_TO_REL]:
            return [self.end_point]
        
        elif self.command in [PathCommand.HORIZONTAL_LINE, PathCommand.HORIZONTAL_LINE_REL,
                             PathCommand.VERTICAL_LINE, PathCommand.VERTICAL_LINE_REL]:
            return [self.end_point]
        
        elif self.command in [PathCommand.CURVE_TO, PathCommand.CURVE_TO_REL]:
            # Cubic Bezier curve
            if len(self.points) >= 3:
                control1 = self.points[0]
                control2 = self.points[1]
                return calculate_curve_points(
                    self.start_point, self.end_point, control1, control2, resolution
                )
        
        elif self.command in [PathCommand.QUADRATIC_CURVE, PathCommand.QUADRATIC_CURVE_REL]:
            # Quadratic Bezier curve
            if len(self.points) >= 1:
                control = self.points[0]
                return calculate_curve_points(
                    self.start_point, self.end_point, control, None, resolution
                )
        
        elif self.command in [PathCommand.ARC, PathCommand.ARC_REL]:
            # Arc - simplified to line for now
            return [self.end_point]
        
        return [self.end_point]


@dataclass
class ParsedPath:
    """Represents a complete parsed SVG path"""
    segments: List[PathSegment]
    bounding_box: BoundingBox
    total_length: float
    is_closed: bool
    
    def to_coordinate_list(self, resolution: int = 20, simplify_tolerance: float = 0.5) -> List[Tuple[float, float]]:
        """Convert entire path to coordinate list"""
        all_points = []
        
        for segment in self.segments:
            points = segment.to_absolute_points(resolution)
            all_points.extend(points)
        
        # Simplify path if requested
        if simplify_tolerance > 0 and len(all_points) > 2:
            all_points = simplify_path(all_points, simplify_tolerance)
        
        return all_points


class SVGPathParser:
    """Parser for SVG path data strings"""
    
    def __init__(self):
        """Initialize parser"""
        self.current_point = (0.0, 0.0)
        self.last_control_point = None
        self.path_start = (0.0, 0.0)
    
    def parse_path_data(self, path_data: str) -> ParsedPath:
        """Parse SVG path data string into structured format
        
        Args:
            path_data: SVG path data string (d attribute)
            
        Returns:
            ParsedPath object with segments and metadata
        """
        # Clean and tokenize path data
        tokens = self._tokenize_path_data(path_data)
        segments = []
        
        # Reset parser state
        self.current_point = (0.0, 0.0)
        self.last_control_point = None
        self.path_start = (0.0, 0.0)
        
        i = 0
        while i < len(tokens):
            token = tokens[i]
            
            if token.upper() in [cmd.value.upper() for cmd in PathCommand]:
                command = PathCommand(token)
                i += 1
                
                # Parse command parameters
                segment, consumed = self._parse_command(command, tokens[i:])
                if segment:
                    segments.append(segment)
                i += consumed
            else:
                i += 1
        
        # Calculate metadata
        bounding_box = self._calculate_bounding_box(segments)
        total_length = self._calculate_total_length(segments)
        is_closed = self._is_path_closed(segments)
        
        return ParsedPath(segments, bounding_box, total_length, is_closed)
    
    def _tokenize_path_data(self, path_data: str) -> List[str]:
        """Tokenize path data string into commands and numbers"""
        # Replace commas with spaces and normalize whitespace
        cleaned = re.sub(r'[,\s]+', ' ', path_data.strip())
        
        # Split on command letters, keeping the letters
        tokens = re.split(r'([MmLlHhVvCcSsQqTtAaZz])', cleaned)
        
        # Filter empty tokens and split number sequences
        result = []
        for token in tokens:
            token = token.strip()
            if not token:
                continue
            
            if token in 'MmLlHhVvCcSsQqTtAaZz':
                result.append(token)
            else:
                # Split numbers (including negative numbers)
                numbers = re.findall(r'-?\d*\.?\d+(?:[eE][+-]?\d+)?', token)
                result.extend(numbers)
        
        return result
    
    def _parse_command(self, command: PathCommand, tokens: List[str]) -> Tuple[Optional[PathSegment], int]:
        """Parse a single path command and its parameters"""
        start_point = self.current_point
        consumed = 0
        
        try:
            if command in [PathCommand.MOVE_TO, PathCommand.MOVE_TO_REL]:
                if len(tokens) >= 2:
                    x, y = float(tokens[0]), float(tokens[1])
                    if command == PathCommand.MOVE_TO_REL:
                        x += self.current_point[0]
                        y += self.current_point[1]
                    
                    self.current_point = (x, y)
                    self.path_start = self.current_point
                    consumed = 2
                    
                    return PathSegment(
                        command=command,
                        points=[],
                        start_point=start_point,
                        end_point=self.current_point,
                        is_relative=(command == PathCommand.MOVE_TO_REL)
                    ), consumed
            
            elif command in [PathCommand.LINE_TO, PathCommand.LINE_TO_REL]:
                if len(tokens) >= 2:
                    x, y = float(tokens[0]), float(tokens[1])
                    if command == PathCommand.LINE_TO_REL:
                        x += self.current_point[0]
                        y += self.current_point[1]
                    
                    end_point = (x, y)
                    self.current_point = end_point
                    consumed = 2
                    
                    return PathSegment(
                        command=command,
                        points=[],
                        start_point=start_point,
                        end_point=end_point,
                        is_relative=(command == PathCommand.LINE_TO_REL)
                    ), consumed
            
            elif command in [PathCommand.HORIZONTAL_LINE, PathCommand.HORIZONTAL_LINE_REL]:
                if len(tokens) >= 1:
                    x = float(tokens[0])
                    if command == PathCommand.HORIZONTAL_LINE_REL:
                        x += self.current_point[0]
                    
                    end_point = (x, self.current_point[1])
                    self.current_point = end_point
                    consumed = 1
                    
                    return PathSegment(
                        command=command,
                        points=[],
                        start_point=start_point,
                        end_point=end_point,
                        is_relative=(command == PathCommand.HORIZONTAL_LINE_REL)
                    ), consumed
            
            elif command in [PathCommand.VERTICAL_LINE, PathCommand.VERTICAL_LINE_REL]:
                if len(tokens) >= 1:
                    y = float(tokens[0])
                    if command == PathCommand.VERTICAL_LINE_REL:
                        y += self.current_point[1]
                    
                    end_point = (self.current_point[0], y)
                    self.current_point = end_point
                    consumed = 1
                    
                    return PathSegment(
                        command=command,
                        points=[],
                        start_point=start_point,
                        end_point=end_point,
                        is_relative=(command == PathCommand.VERTICAL_LINE_REL)
                    ), consumed
            
            elif command in [PathCommand.CURVE_TO, PathCommand.CURVE_TO_REL]:
                if len(tokens) >= 6:
                    x1, y1 = float(tokens[0]), float(tokens[1])
                    x2, y2 = float(tokens[2]), float(tokens[3])
                    x, y = float(tokens[4]), float(tokens[5])
                    
                    if command == PathCommand.CURVE_TO_REL:
                        x1 += self.current_point[0]
                        y1 += self.current_point[1]
                        x2 += self.current_point[0]
                        y2 += self.current_point[1]
                        x += self.current_point[0]
                        y += self.current_point[1]
                    
                    control1 = (x1, y1)
                    control2 = (x2, y2)
                    end_point = (x, y)
                    
                    self.current_point = end_point
                    self.last_control_point = control2
                    consumed = 6
                    
                    return PathSegment(
                        command=command,
                        points=[control1, control2],
                        start_point=start_point,
                        end_point=end_point,
                        is_relative=(command == PathCommand.CURVE_TO_REL)
                    ), consumed
            
            elif command in [PathCommand.QUADRATIC_CURVE, PathCommand.QUADRATIC_CURVE_REL]:
                if len(tokens) >= 4:
                    x1, y1 = float(tokens[0]), float(tokens[1])
                    x, y = float(tokens[2]), float(tokens[3])
                    
                    if command == PathCommand.QUADRATIC_CURVE_REL:
                        x1 += self.current_point[0]
                        y1 += self.current_point[1]
                        x += self.current_point[0]
                        y += self.current_point[1]
                    
                    control = (x1, y1)
                    end_point = (x, y)
                    
                    self.current_point = end_point
                    self.last_control_point = control
                    consumed = 4
                    
                    return PathSegment(
                        command=command,
                        points=[control],
                        start_point=start_point,
                        end_point=end_point,
                        is_relative=(command == PathCommand.QUADRATIC_CURVE_REL)
                    ), consumed
            
            elif command in [PathCommand.CLOSE_PATH, PathCommand.CLOSE_PATH_REL]:
                end_point = self.path_start
                self.current_point = end_point
                
                return PathSegment(
                    command=command,
                    points=[],
                    start_point=start_point,
                    end_point=end_point,
                    is_relative=False
                ), consumed
        
        except (ValueError, IndexError):
            pass
        
        return None, consumed
    
    def _calculate_bounding_box(self, segments: List[PathSegment]) -> BoundingBox:
        """Calculate bounding box for all segments"""
        if not segments:
            return BoundingBox(0, 0, 0, 0)
        
        all_points = []
        for segment in segments:
            all_points.append(segment.start_point)
            all_points.append(segment.end_point)
            all_points.extend(segment.points)
        
        if not all_points:
            return BoundingBox(0, 0, 0, 0)
        
        x_coords = [p[0] for p in all_points]
        y_coords = [p[1] for p in all_points]
        
        return BoundingBox(
            min(x_coords), min(y_coords),
            max(x_coords), max(y_coords)
        )
    
    def _calculate_total_length(self, segments: List[PathSegment]) -> float:
        """Calculate total path length"""
        total = 0.0
        for segment in segments:
            if segment.command not in [PathCommand.MOVE_TO, PathCommand.MOVE_TO_REL]:
                total += calculate_distance(segment.start_point, segment.end_point)
        return total
    
    def _is_path_closed(self, segments: List[PathSegment]) -> bool:
        """Check if path is closed"""
        if not segments:
            return False
        
        # Check for explicit close command
        if segments[-1].command in [PathCommand.CLOSE_PATH, PathCommand.CLOSE_PATH_REL]:
            return True
        
        # Check if end point matches start point
        start = segments[0].start_point
        end = segments[-1].end_point
        return calculate_distance(start, end) < 0.01


class PathOptimizer:
    """Optimizer for SVG paths to improve plotting efficiency"""
    
    def __init__(self):
        """Initialize optimizer"""
        pass
    
    def optimize_for_plotting(self, parsed_path: ParsedPath, 
                            resolution: int = 20,
                            simplify_tolerance: float = 0.5,
                            merge_close_points: float = 0.1) -> List[Tuple[float, float]]:
        """Optimize path for efficient plotting
        
        Args:
            parsed_path: Parsed SVG path
            resolution: Points per curve segment
            simplify_tolerance: Path simplification tolerance
            merge_close_points: Distance threshold for merging points
            
        Returns:
            Optimized coordinate list
        """
        # Convert to coordinate list
        coordinates = parsed_path.to_coordinate_list(resolution, simplify_tolerance)
        
        # Merge close points
        if merge_close_points > 0:
            coordinates = self._merge_close_points(coordinates, merge_close_points)
        
        # Remove duplicate consecutive points
        coordinates = self._remove_duplicates(coordinates)
        
        return coordinates
    
    def _merge_close_points(self, points: List[Tuple[float, float]], 
                           threshold: float) -> List[Tuple[float, float]]:
        """Merge points that are very close together"""
        if len(points) <= 1:
            return points
        
        merged = [points[0]]
        
        for point in points[1:]:
            if calculate_distance(merged[-1], point) > threshold:
                merged.append(point)
        
        return merged
    
    def _remove_duplicates(self, points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """Remove consecutive duplicate points"""
        if len(points) <= 1:
            return points
        
        unique = [points[0]]
        
        for point in points[1:]:
            if point != unique[-1]:
                unique.append(point)
        
        return unique


def parse_svg_path(path_data: str) -> ParsedPath:
    """Parse SVG path data string
    
    Args:
        path_data: SVG path data string
        
    Returns:
        ParsedPath object
    """
    parser = SVGPathParser()
    return parser.parse_path_data(path_data)


def svg_path_to_coordinates(path_data: str, 
                           resolution: int = 20,
                           simplify_tolerance: float = 0.5) -> List[Tuple[float, float]]:
    """Convert SVG path to coordinate list
    
    Args:
        path_data: SVG path data string
        resolution: Points per curve segment
        simplify_tolerance: Path simplification tolerance
        
    Returns:
        List of (x, y) coordinates
    """
    parsed = parse_svg_path(path_data)
    optimizer = PathOptimizer()
    return optimizer.optimize_for_plotting(parsed, resolution, simplify_tolerance)


def extract_paths_from_svg_content(svg_content: str) -> List[str]:
    """Extract path data from SVG content
    
    Args:
        svg_content: Complete SVG file content
        
    Returns:
        List of path data strings
    """
    # Find all path elements
    path_pattern = r'<path[^>]*\sd\s*=\s*["\']([^"\']*)["\'][^>]*>'
    matches = re.findall(path_pattern, svg_content, re.IGNORECASE)
    
    return matches


def calculate_path_bounds(coordinates: List[Tuple[float, float]]) -> Dict[str, float]:
    """Calculate bounds and statistics for coordinate path
    
    Args:
        coordinates: List of (x, y) coordinates
        
    Returns:
        Dictionary with bounds and statistics
    """
    if not coordinates:
        return {
            'min_x': 0, 'max_x': 0, 'min_y': 0, 'max_y': 0,
            'width': 0, 'height': 0, 'center_x': 0, 'center_y': 0,
            'total_length': 0, 'num_points': 0
        }
    
    x_coords = [p[0] for p in coordinates]
    y_coords = [p[1] for p in coordinates]
    
    min_x, max_x = min(x_coords), max(x_coords)
    min_y, max_y = min(y_coords), max(y_coords)
    
    return {
        'min_x': min_x,
        'max_x': max_x,
        'min_y': min_y,
        'max_y': max_y,
        'width': max_x - min_x,
        'height': max_y - min_y,
        'center_x': (min_x + max_x) / 2,
        'center_y': (min_y + max_y) / 2,
        'total_length': sum(calculate_distance(coordinates[i], coordinates[i+1]) 
                           for i in range(len(coordinates)-1)),
        'num_points': len(coordinates)
    }