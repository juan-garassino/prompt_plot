"""
Mathematical utilities for PromptPlot v2.0

This module provides mathematical functions for coordinate calculations,
geometric operations, path optimization, and drawing transformations.
"""

import math
from typing import List, Tuple, Optional, Union, Dict, Any
from dataclasses import dataclass
from enum import Enum
import numpy as np


class CoordinateSystem(str, Enum):
    """Coordinate system types"""
    CARTESIAN = "cartesian"
    POLAR = "polar"
    RELATIVE = "relative"
    ABSOLUTE = "absolute"


class DistanceMetric(str, Enum):
    """Distance calculation methods"""
    EUCLIDEAN = "euclidean"
    MANHATTAN = "manhattan"
    CHEBYSHEV = "chebyshev"


@dataclass
class Point2D:
    """2D point representation"""
    x: float
    y: float
    
    def __add__(self, other: 'Point2D') -> 'Point2D':
        return Point2D(self.x + other.x, self.y + other.y)
    
    def __sub__(self, other: 'Point2D') -> 'Point2D':
        return Point2D(self.x - other.x, self.y - other.y)
    
    def __mul__(self, scalar: float) -> 'Point2D':
        return Point2D(self.x * scalar, self.y * scalar)
    
    def distance_to(self, other: 'Point2D', metric: DistanceMetric = DistanceMetric.EUCLIDEAN) -> float:
        """Calculate distance to another point"""
        if metric == DistanceMetric.EUCLIDEAN:
            return math.sqrt((self.x - other.x)**2 + (self.y - other.y)**2)
        elif metric == DistanceMetric.MANHATTAN:
            return abs(self.x - other.x) + abs(self.y - other.y)
        elif metric == DistanceMetric.CHEBYSHEV:
            return max(abs(self.x - other.x), abs(self.y - other.y))
        else:
            raise ValueError(f"Unknown distance metric: {metric}")
    
    def to_tuple(self) -> Tuple[float, float]:
        """Convert to tuple"""
        return (self.x, self.y)
    
    def to_polar(self) -> Tuple[float, float]:
        """Convert to polar coordinates (radius, angle)"""
        radius = math.sqrt(self.x**2 + self.y**2)
        angle = math.atan2(self.y, self.x)
        return (radius, angle)


@dataclass
class Point3D:
    """3D point representation"""
    x: float
    y: float
    z: float
    
    def __add__(self, other: 'Point3D') -> 'Point3D':
        return Point3D(self.x + other.x, self.y + other.y, self.z + other.z)
    
    def __sub__(self, other: 'Point3D') -> 'Point3D':
        return Point3D(self.x - other.x, self.y - other.y, self.z - other.z)
    
    def __mul__(self, scalar: float) -> 'Point3D':
        return Point3D(self.x * scalar, self.y * scalar, self.z * scalar)
    
    def distance_to(self, other: 'Point3D') -> float:
        """Calculate Euclidean distance to another point"""
        return math.sqrt((self.x - other.x)**2 + (self.y - other.y)**2 + (self.z - other.z)**2)
    
    def to_tuple(self) -> Tuple[float, float, float]:
        """Convert to tuple"""
        return (self.x, self.y, self.z)


@dataclass
class BoundingBox:
    """Bounding box representation"""
    min_x: float
    min_y: float
    max_x: float
    max_y: float
    
    @property
    def width(self) -> float:
        return self.max_x - self.min_x
    
    @property
    def height(self) -> float:
        return self.max_y - self.min_y
    
    @property
    def center(self) -> Point2D:
        return Point2D((self.min_x + self.max_x) / 2, (self.min_y + self.max_y) / 2)
    
    @property
    def area(self) -> float:
        return self.width * self.height
    
    def contains_point(self, point: Point2D) -> bool:
        """Check if point is inside bounding box"""
        return (self.min_x <= point.x <= self.max_x and 
                self.min_y <= point.y <= self.max_y)
    
    def expand(self, margin: float) -> 'BoundingBox':
        """Expand bounding box by margin"""
        return BoundingBox(
            self.min_x - margin,
            self.min_y - margin,
            self.max_x + margin,
            self.max_y + margin
        )


def calculate_distance(p1: Tuple[float, float], p2: Tuple[float, float], 
                      metric: DistanceMetric = DistanceMetric.EUCLIDEAN) -> float:
    """Calculate distance between two points
    
    Args:
        p1: First point (x, y)
        p2: Second point (x, y)
        metric: Distance calculation method
        
    Returns:
        Distance between points
    """
    point1 = Point2D(p1[0], p1[1])
    point2 = Point2D(p2[0], p2[1])
    return point1.distance_to(point2, metric)


def calculate_path_length(points: List[Tuple[float, float]]) -> float:
    """Calculate total length of a path
    
    Args:
        points: List of (x, y) coordinates
        
    Returns:
        Total path length
    """
    if len(points) < 2:
        return 0.0
    
    total_length = 0.0
    for i in range(1, len(points)):
        total_length += calculate_distance(points[i-1], points[i])
    
    return total_length


def calculate_bounding_box(points: List[Tuple[float, float]]) -> BoundingBox:
    """Calculate bounding box for a set of points
    
    Args:
        points: List of (x, y) coordinates
        
    Returns:
        Bounding box containing all points
    """
    if not points:
        return BoundingBox(0, 0, 0, 0)
    
    x_coords = [p[0] for p in points]
    y_coords = [p[1] for p in points]
    
    return BoundingBox(
        min(x_coords),
        min(y_coords),
        max(x_coords),
        max(y_coords)
    )


def rotate_point(point: Tuple[float, float], angle: float, center: Tuple[float, float] = (0, 0)) -> Tuple[float, float]:
    """Rotate point around center by angle
    
    Args:
        point: Point to rotate (x, y)
        angle: Rotation angle in radians
        center: Center of rotation (x, y)
        
    Returns:
        Rotated point (x, y)
    """
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    
    # Translate to origin
    x = point[0] - center[0]
    y = point[1] - center[1]
    
    # Rotate
    new_x = x * cos_a - y * sin_a
    new_y = x * sin_a + y * cos_a
    
    # Translate back
    return (new_x + center[0], new_y + center[1])


def scale_point(point: Tuple[float, float], scale_x: float, scale_y: float, 
                center: Tuple[float, float] = (0, 0)) -> Tuple[float, float]:
    """Scale point around center
    
    Args:
        point: Point to scale (x, y)
        scale_x: X-axis scale factor
        scale_y: Y-axis scale factor
        center: Center of scaling (x, y)
        
    Returns:
        Scaled point (x, y)
    """
    # Translate to origin
    x = point[0] - center[0]
    y = point[1] - center[1]
    
    # Scale
    new_x = x * scale_x
    new_y = y * scale_y
    
    # Translate back
    return (new_x + center[0], new_y + center[1])


def translate_point(point: Tuple[float, float], offset: Tuple[float, float]) -> Tuple[float, float]:
    """Translate point by offset
    
    Args:
        point: Point to translate (x, y)
        offset: Translation offset (dx, dy)
        
    Returns:
        Translated point (x, y)
    """
    return (point[0] + offset[0], point[1] + offset[1])


def transform_path(points: List[Tuple[float, float]], 
                   rotation: float = 0.0,
                   scale: Tuple[float, float] = (1.0, 1.0),
                   translation: Tuple[float, float] = (0.0, 0.0),
                   center: Optional[Tuple[float, float]] = None) -> List[Tuple[float, float]]:
    """Apply transformations to a path
    
    Args:
        points: List of points to transform
        rotation: Rotation angle in radians
        scale: Scale factors (x, y)
        translation: Translation offset (dx, dy)
        center: Center point for rotation and scaling
        
    Returns:
        Transformed path
    """
    if not points:
        return points
    
    # Use path center if no center specified
    if center is None:
        bbox = calculate_bounding_box(points)
        center = bbox.center.to_tuple()
    
    transformed = []
    for point in points:
        # Apply transformations in order: scale, rotate, translate
        new_point = scale_point(point, scale[0], scale[1], center)
        new_point = rotate_point(new_point, rotation, center)
        new_point = translate_point(new_point, translation)
        transformed.append(new_point)
    
    return transformed


def interpolate_points(p1: Tuple[float, float], p2: Tuple[float, float], 
                      num_points: int) -> List[Tuple[float, float]]:
    """Interpolate points between two endpoints
    
    Args:
        p1: Start point (x, y)
        p2: End point (x, y)
        num_points: Number of interpolated points (including endpoints)
        
    Returns:
        List of interpolated points
    """
    if num_points < 2:
        return [p1, p2]
    
    points = []
    for i in range(num_points):
        t = i / (num_points - 1)
        x = p1[0] + t * (p2[0] - p1[0])
        y = p1[1] + t * (p2[1] - p1[1])
        points.append((x, y))
    
    return points


def simplify_path(points: List[Tuple[float, float]], tolerance: float = 1.0) -> List[Tuple[float, float]]:
    """Simplify path using Douglas-Peucker algorithm
    
    Args:
        points: Original path points
        tolerance: Simplification tolerance
        
    Returns:
        Simplified path
    """
    if len(points) <= 2:
        return points
    
    def perpendicular_distance(point: Tuple[float, float], 
                             line_start: Tuple[float, float], 
                             line_end: Tuple[float, float]) -> float:
        """Calculate perpendicular distance from point to line"""
        if line_start == line_end:
            return calculate_distance(point, line_start)
        
        # Line equation: ax + by + c = 0
        a = line_end[1] - line_start[1]
        b = line_start[0] - line_end[0]
        c = line_end[0] * line_start[1] - line_start[0] * line_end[1]
        
        # Distance formula
        return abs(a * point[0] + b * point[1] + c) / math.sqrt(a**2 + b**2)
    
    def douglas_peucker(points_list: List[Tuple[float, float]], 
                       start: int, end: int, tolerance: float) -> List[int]:
        """Recursive Douglas-Peucker implementation"""
        if end - start <= 1:
            return [start, end]
        
        # Find point with maximum distance
        max_distance = 0.0
        max_index = start
        
        for i in range(start + 1, end):
            distance = perpendicular_distance(points_list[i], points_list[start], points_list[end])
            if distance > max_distance:
                max_distance = distance
                max_index = i
        
        # If max distance is greater than tolerance, recursively simplify
        if max_distance > tolerance:
            # Recursively simplify both segments
            left_indices = douglas_peucker(points_list, start, max_index, tolerance)
            right_indices = douglas_peucker(points_list, max_index, end, tolerance)
            
            # Combine results (remove duplicate middle point)
            return left_indices[:-1] + right_indices
        else:
            # All points between start and end can be removed
            return [start, end]
    
    # Apply Douglas-Peucker algorithm
    keep_indices = douglas_peucker(points, 0, len(points) - 1, tolerance)
    return [points[i] for i in sorted(set(keep_indices))]


def optimize_path_order(points: List[Tuple[float, float]], 
                       start_point: Optional[Tuple[float, float]] = None) -> List[Tuple[float, float]]:
    """Optimize path order to minimize travel distance (nearest neighbor heuristic)
    
    Args:
        points: Unordered list of points
        start_point: Starting point (uses first point if None)
        
    Returns:
        Optimized path order
    """
    if len(points) <= 2:
        return points
    
    remaining = points.copy()
    optimized = []
    
    # Start from specified point or first point
    if start_point and start_point in remaining:
        current = start_point
        remaining.remove(current)
    else:
        current = remaining.pop(0)
    
    optimized.append(current)
    
    # Greedy nearest neighbor
    while remaining:
        nearest = min(remaining, key=lambda p: calculate_distance(current, p))
        remaining.remove(nearest)
        optimized.append(nearest)
        current = nearest
    
    return optimized


def calculate_curve_points(start: Tuple[float, float], 
                          end: Tuple[float, float],
                          control1: Tuple[float, float],
                          control2: Optional[Tuple[float, float]] = None,
                          num_points: int = 20) -> List[Tuple[float, float]]:
    """Calculate points along a Bezier curve
    
    Args:
        start: Start point
        end: End point
        control1: First control point
        control2: Second control point (for cubic Bezier)
        num_points: Number of points to generate
        
    Returns:
        List of points along the curve
    """
    points = []
    
    for i in range(num_points):
        t = i / (num_points - 1)
        
        if control2 is None:
            # Quadratic Bezier
            x = (1-t)**2 * start[0] + 2*(1-t)*t * control1[0] + t**2 * end[0]
            y = (1-t)**2 * start[1] + 2*(1-t)*t * control1[1] + t**2 * end[1]
        else:
            # Cubic Bezier
            x = ((1-t)**3 * start[0] + 
                 3*(1-t)**2*t * control1[0] + 
                 3*(1-t)*t**2 * control2[0] + 
                 t**3 * end[0])
            y = ((1-t)**3 * start[1] + 
                 3*(1-t)**2*t * control1[1] + 
                 3*(1-t)*t**2 * control2[1] + 
                 t**3 * end[1])
        
        points.append((x, y))
    
    return points


def calculate_circle_points(center: Tuple[float, float], 
                           radius: float,
                           start_angle: float = 0.0,
                           end_angle: float = 2 * math.pi,
                           num_points: int = 36) -> List[Tuple[float, float]]:
    """Calculate points along a circle or arc
    
    Args:
        center: Circle center (x, y)
        radius: Circle radius
        start_angle: Start angle in radians
        end_angle: End angle in radians
        num_points: Number of points to generate
        
    Returns:
        List of points along the circle/arc
    """
    points = []
    angle_step = (end_angle - start_angle) / (num_points - 1)
    
    for i in range(num_points):
        angle = start_angle + i * angle_step
        x = center[0] + radius * math.cos(angle)
        y = center[1] + radius * math.sin(angle)
        points.append((x, y))
    
    return points


def fit_circle_to_points(points: List[Tuple[float, float]]) -> Tuple[Tuple[float, float], float]:
    """Fit a circle to a set of points using least squares
    
    Args:
        points: List of points to fit
        
    Returns:
        Tuple of (center, radius)
    """
    if len(points) < 3:
        raise ValueError("Need at least 3 points to fit a circle")
    
    # Convert to numpy arrays for easier calculation
    x = np.array([p[0] for p in points])
    y = np.array([p[1] for p in points])
    
    # Set up system of equations
    A = np.column_stack([2*x, 2*y, np.ones(len(points))])
    b = x**2 + y**2
    
    # Solve least squares
    try:
        coeffs = np.linalg.lstsq(A, b, rcond=None)[0]
        center_x, center_y, c = coeffs
        radius = math.sqrt(center_x**2 + center_y**2 + c)
        return ((center_x, center_y), radius)
    except np.linalg.LinAlgError:
        # Fallback to centroid and average distance
        center_x = np.mean(x)
        center_y = np.mean(y)
        center = (center_x, center_y)
        radius = np.mean([calculate_distance(p, center) for p in points])
        return (center, radius)


def calculate_angle(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """Calculate angle from p1 to p2 in radians
    
    Args:
        p1: Start point
        p2: End point
        
    Returns:
        Angle in radians
    """
    return math.atan2(p2[1] - p1[1], p2[0] - p1[0])


def normalize_angle(angle: float) -> float:
    """Normalize angle to [-π, π] range
    
    Args:
        angle: Angle in radians
        
    Returns:
        Normalized angle
    """
    while angle > math.pi:
        angle -= 2 * math.pi
    while angle < -math.pi:
        angle += 2 * math.pi
    return angle


def degrees_to_radians(degrees: float) -> float:
    """Convert degrees to radians"""
    return degrees * math.pi / 180.0


def radians_to_degrees(radians: float) -> float:
    """Convert radians to degrees"""
    return radians * 180.0 / math.pi