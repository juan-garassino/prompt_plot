"""
Non-orthogonal drawing strategy for PromptPlot v2.0

This module implements complex shape handling with curve approximation and
smooth path generation algorithms. It creates advanced G-code instruction
sequences for organic shapes, circles, curves, and artistic drawings.
"""

import math
from typing import List, Tuple, Optional, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum

from ..core.models import GCodeCommand, GCodeProgram, DrawingStrategy


class CurveType(str, Enum):
    """Types of curves that can be drawn"""
    CIRCLE = "circle"
    ELLIPSE = "ellipse"
    ARC = "arc"
    BEZIER = "bezier"
    SPLINE = "spline"
    SPIRAL = "spiral"
    WAVE = "wave"
    FREEFORM = "freeform"


@dataclass
class Point:
    """Point representation with curve support"""
    x: float
    y: float
    
    def distance_to(self, other: 'Point') -> float:
        """Calculate Euclidean distance to another point"""
        return math.sqrt((self.x - other.x)**2 + (self.y - other.y)**2)
    
    def angle_to(self, other: 'Point') -> float:
        """Calculate angle to another point in radians"""
        return math.atan2(other.y - self.y, other.x - self.x)
    
    def rotate_around(self, center: 'Point', angle: float) -> 'Point':
        """Rotate this point around a center point by given angle"""
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        
        # Translate to origin
        x = self.x - center.x
        y = self.y - center.y
        
        # Rotate
        new_x = x * cos_a - y * sin_a
        new_y = x * sin_a + y * cos_a
        
        # Translate back
        return Point(new_x + center.x, new_y + center.y)


@dataclass
class BezierCurve:
    """Cubic Bezier curve definition"""
    p0: Point  # Start point
    p1: Point  # First control point
    p2: Point  # Second control point
    p3: Point  # End point
    
    def point_at(self, t: float) -> Point:
        """Calculate point on curve at parameter t (0 to 1)"""
        # Cubic Bezier formula: B(t) = (1-t)³P₀ + 3(1-t)²tP₁ + 3(1-t)t²P₂ + t³P₃
        t1 = 1 - t
        t1_2 = t1 * t1
        t1_3 = t1_2 * t1
        t_2 = t * t
        t_3 = t_2 * t
        
        x = (t1_3 * self.p0.x + 
             3 * t1_2 * t * self.p1.x + 
             3 * t1 * t_2 * self.p2.x + 
             t_3 * self.p3.x)
        
        y = (t1_3 * self.p0.y + 
             3 * t1_2 * t * self.p1.y + 
             3 * t1 * t_2 * self.p2.y + 
             t_3 * self.p3.y)
        
        return Point(x, y)


@dataclass
class Arc:
    """Arc definition"""
    center: Point
    radius: float
    start_angle: float  # In radians
    end_angle: float    # In radians
    clockwise: bool = False
    
    def point_at_angle(self, angle: float) -> Point:
        """Get point on arc at given angle"""
        x = self.center.x + self.radius * math.cos(angle)
        y = self.center.y + self.radius * math.sin(angle)
        return Point(x, y)


class NonOrthogonalStrategy:
    """
    Non-orthogonal drawing strategy for complex shapes, curves, and organic forms.
    
    This class implements Requirements 3.2 and 3.5:
    - Curve approximation and smooth path generation algorithms
    - Advanced G-code instruction sequences for organic shapes
    """
    
    def __init__(self, resolution: float = 0.5, max_arc_error: float = 0.1):
        """
        Initialize the non-orthogonal strategy.
        
        Args:
            resolution: Minimum distance between points in curve approximation (mm)
            max_arc_error: Maximum allowable error in arc approximation (mm)
        """
        self.resolution = resolution
        self.max_arc_error = max_arc_error
        self.current_position = Point(0, 0)
        
    def generate_circle(self, center_x: float, center_y: float, radius: float,
                       filled: bool = False) -> List[GCodeCommand]:
        """
        Generate G-code for drawing a circle using arc commands or line approximation.
        
        Args:
            center_x, center_y: Center coordinates
            radius: Circle radius
            filled: Whether to fill the circle with concentric circles
            
        Returns:
            List of G-code commands
        """
        center = Point(center_x, center_y)
        
        if filled:
            return self._generate_filled_circle(center, radius)
        else:
            return self._generate_circle_outline(center, radius)
    
    def generate_ellipse(self, center_x: float, center_y: float, 
                        width: float, height: float) -> List[GCodeCommand]:
        """
        Generate G-code for drawing an ellipse.
        
        Args:
            center_x, center_y: Center coordinates
            width: Ellipse width (major axis)
            height: Ellipse height (minor axis)
            
        Returns:
            List of G-code commands
        """
        center = Point(center_x, center_y)
        a = width / 2  # Semi-major axis
        b = height / 2  # Semi-minor axis
        
        # Generate ellipse points using parametric equations
        points = []
        num_points = max(16, int(2 * math.pi * max(a, b) / self.resolution))
        
        for i in range(num_points + 1):  # +1 to close the ellipse
            t = 2 * math.pi * i / num_points
            x = center.x + a * math.cos(t)
            y = center.y + b * math.sin(t)
            points.append(Point(x, y))
        
        return self._generate_smooth_path(points, closed=True)
    
    def generate_arc(self, center_x: float, center_y: float, radius: float,
                    start_angle: float, end_angle: float, 
                    clockwise: bool = False) -> List[GCodeCommand]:
        """
        Generate G-code for drawing an arc.
        
        Args:
            center_x, center_y: Center coordinates
            radius: Arc radius
            start_angle, end_angle: Start and end angles in degrees
            clockwise: Direction of arc
            
        Returns:
            List of G-code commands
        """
        # Convert degrees to radians
        start_rad = math.radians(start_angle)
        end_rad = math.radians(end_angle)
        
        arc = Arc(Point(center_x, center_y), radius, start_rad, end_rad, clockwise)
        
        # Calculate arc length to determine number of segments
        angle_diff = end_rad - start_rad
        if clockwise and angle_diff > 0:
            angle_diff -= 2 * math.pi
        elif not clockwise and angle_diff < 0:
            angle_diff += 2 * math.pi
        
        arc_length = abs(angle_diff) * radius
        num_segments = max(4, int(arc_length / self.resolution))
        
        # Generate arc points
        points = []
        for i in range(num_segments + 1):
            t = i / num_segments
            if clockwise:
                angle = start_rad - abs(angle_diff) * t
            else:
                angle = start_rad + abs(angle_diff) * t
            points.append(arc.point_at_angle(angle))
        
        return self._generate_smooth_path(points)
    
    def generate_bezier_curve(self, p0: Tuple[float, float], p1: Tuple[float, float],
                             p2: Tuple[float, float], p3: Tuple[float, float]) -> List[GCodeCommand]:
        """
        Generate G-code for drawing a cubic Bezier curve.
        
        Args:
            p0: Start point (x, y)
            p1: First control point (x, y)
            p2: Second control point (x, y)
            p3: End point (x, y)
            
        Returns:
            List of G-code commands
        """
        curve = BezierCurve(
            Point(p0[0], p0[1]),
            Point(p1[0], p1[1]),
            Point(p2[0], p2[1]),
            Point(p3[0], p3[1])
        )
        
        # Adaptive sampling based on curve complexity
        points = self._sample_bezier_adaptive(curve)
        return self._generate_smooth_path(points)
    
    def generate_spiral(self, center_x: float, center_y: float, 
                       start_radius: float, end_radius: float,
                       turns: float, clockwise: bool = False) -> List[GCodeCommand]:
        """
        Generate G-code for drawing a spiral.
        
        Args:
            center_x, center_y: Center coordinates
            start_radius: Starting radius
            end_radius: Ending radius
            turns: Number of complete turns
            clockwise: Direction of spiral
            
        Returns:
            List of G-code commands
        """
        center = Point(center_x, center_y)
        total_angle = 2 * math.pi * turns
        
        # Calculate number of points based on spiral length
        avg_radius = (start_radius + end_radius) / 2
        spiral_length = total_angle * avg_radius
        num_points = max(16, int(spiral_length / self.resolution))
        
        points = []
        for i in range(num_points + 1):
            t = i / num_points
            angle = total_angle * t
            if clockwise:
                angle = -angle
            
            # Linear interpolation of radius
            radius = start_radius + (end_radius - start_radius) * t
            
            x = center.x + radius * math.cos(angle)
            y = center.y + radius * math.sin(angle)
            points.append(Point(x, y))
        
        return self._generate_smooth_path(points)
    
    def generate_wave(self, start_x: float, start_y: float, end_x: float, end_y: float,
                     amplitude: float, frequency: float, phase: float = 0) -> List[GCodeCommand]:
        """
        Generate G-code for drawing a sine wave.
        
        Args:
            start_x, start_y: Starting coordinates
            end_x, end_y: Ending coordinates
            amplitude: Wave amplitude
            frequency: Number of complete cycles
            phase: Phase offset in radians
            
        Returns:
            List of G-code commands
        """
        length = math.sqrt((end_x - start_x)**2 + (end_y - start_y)**2)
        angle = math.atan2(end_y - start_y, end_x - start_x)
        
        # Number of points based on wave complexity
        num_points = max(32, int(length / self.resolution * frequency))
        
        points = []
        for i in range(num_points + 1):
            t = i / num_points
            
            # Base position along the line
            base_x = start_x + (end_x - start_x) * t
            base_y = start_y + (end_y - start_y) * t
            
            # Wave offset perpendicular to the line
            wave_offset = amplitude * math.sin(2 * math.pi * frequency * t + phase)
            offset_x = -wave_offset * math.sin(angle)
            offset_y = wave_offset * math.cos(angle)
            
            points.append(Point(base_x + offset_x, base_y + offset_y))
        
        return self._generate_smooth_path(points)
    
    def generate_freeform_path(self, points: List[Tuple[float, float]], 
                              smoothing: float = 0.5) -> List[GCodeCommand]:
        """
        Generate G-code for a freeform path with optional smoothing.
        
        Args:
            points: List of (x, y) coordinate tuples
            smoothing: Smoothing factor (0 = no smoothing, 1 = maximum smoothing)
            
        Returns:
            List of G-code commands
        """
        if len(points) < 2:
            return []
        
        point_objects = [Point(x, y) for x, y in points]
        
        if smoothing > 0:
            point_objects = self._apply_smoothing(point_objects, smoothing)
        
        return self._generate_smooth_path(point_objects)
    
    def _generate_circle_outline(self, center: Point, radius: float) -> List[GCodeCommand]:
        """Generate commands for circle outline using optimal method"""
        
        # For small circles, use line approximation
        # For larger circles, use G2/G3 arc commands if supported
        circumference = 2 * math.pi * radius
        
        if radius < 5.0:  # Small circles - use line approximation
            num_segments = max(8, int(circumference / self.resolution))
            points = []
            
            for i in range(num_segments + 1):  # +1 to close the circle
                angle = 2 * math.pi * i / num_segments
                x = center.x + radius * math.cos(angle)
                y = center.y + radius * math.sin(angle)
                points.append(Point(x, y))
            
            return self._generate_smooth_path(points, closed=True)
        
        else:  # Large circles - use arc commands
            return self._generate_arc_commands(center, radius)
    
    def _generate_filled_circle(self, center: Point, radius: float) -> List[GCodeCommand]:
        """Generate commands for filled circle using concentric circles"""
        commands = []
        
        # Fill with concentric circles, spacing based on resolution
        spacing = self.resolution * 2
        current_radius = spacing
        
        while current_radius <= radius:
            circle_commands = self._generate_circle_outline(center, current_radius)
            commands.extend(circle_commands)
            current_radius += spacing
        
        # Add outer circle if not already drawn
        if current_radius - spacing < radius:
            commands.extend(self._generate_circle_outline(center, radius))
        
        return commands
    
    def _generate_arc_commands(self, center: Point, radius: float) -> List[GCodeCommand]:
        """Generate G2/G3 arc commands for circle (if plotter supports it)"""
        commands = []
        
        # Move to start position (right side of circle)
        start_point = Point(center.x + radius, center.y)
        commands.append(GCodeCommand(
            command="G0",
            x=start_point.x,
            y=start_point.y,
            strategy_type=DrawingStrategy.NON_ORTHOGONAL
        ))
        
        # Put pen down
        commands.append(GCodeCommand(
            command="M3",
            strategy_type=DrawingStrategy.NON_ORTHOGONAL
        ))
        
        # Draw full circle using two semicircular arcs
        # First semicircle (top half)
        commands.append(GCodeCommand(
            command="G2",  # Clockwise arc
            x=center.x - radius,
            y=center.y,
            # Note: I and J parameters for arc center offset would be added here
            # but they're not in our current GCodeCommand model
            strategy_type=DrawingStrategy.NON_ORTHOGONAL
        ))
        
        # Second semicircle (bottom half)
        commands.append(GCodeCommand(
            command="G2",  # Clockwise arc
            x=start_point.x,
            y=start_point.y,
            strategy_type=DrawingStrategy.NON_ORTHOGONAL
        ))
        
        # Lift pen
        commands.append(GCodeCommand(
            command="M5",
            strategy_type=DrawingStrategy.NON_ORTHOGONAL
        ))
        
        return commands
    
    def _generate_smooth_path(self, points: List[Point], closed: bool = False) -> List[GCodeCommand]:
        """Generate smooth path commands with velocity optimization"""
        if not points:
            return []
        
        commands = []
        
        # Move to start position
        commands.append(GCodeCommand(
            command="G0",
            x=points[0].x,
            y=points[0].y,
            strategy_type=DrawingStrategy.NON_ORTHOGONAL
        ))
        
        # Put pen down
        commands.append(GCodeCommand(
            command="M3",
            strategy_type=DrawingStrategy.NON_ORTHOGONAL
        ))
        
        # Draw path with adaptive feed rates
        for i in range(1, len(points)):
            prev_point = points[i-1]
            curr_point = points[i]
            
            # Calculate curvature to adjust feed rate
            feed_rate = self._calculate_adaptive_feed_rate(points, i)
            
            commands.append(GCodeCommand(
                command="G1",
                x=curr_point.x,
                y=curr_point.y,
                f=feed_rate,
                strategy_type=DrawingStrategy.NON_ORTHOGONAL
            ))
        
        # Close path if requested
        if closed and len(points) > 2:
            commands.append(GCodeCommand(
                command="G1",
                x=points[0].x,
                y=points[0].y,
                f=1000,
                strategy_type=DrawingStrategy.NON_ORTHOGONAL
            ))
        
        # Lift pen
        commands.append(GCodeCommand(
            command="M5",
            strategy_type=DrawingStrategy.NON_ORTHOGONAL
        ))
        
        return commands
    
    def _sample_bezier_adaptive(self, curve: BezierCurve) -> List[Point]:
        """Adaptive sampling of Bezier curve based on curvature"""
        points = []
        
        # Start with coarse sampling
        coarse_samples = 10
        for i in range(coarse_samples + 1):
            t = i / coarse_samples
            points.append(curve.point_at(t))
        
        # Refine based on curvature
        refined_points = [points[0]]
        
        for i in range(len(points) - 1):
            p1 = points[i]
            p2 = points[i + 1]
            
            # Check if we need more points between p1 and p2
            mid_t = (i + 0.5) / coarse_samples
            mid_point = curve.point_at(mid_t)
            
            # Calculate deviation from straight line
            line_mid = Point(
                (p1.x + p2.x) / 2,
                (p1.y + p2.y) / 2
            )
            deviation = mid_point.distance_to(line_mid)
            
            if deviation > self.max_arc_error:
                # Add intermediate points
                num_subdivisions = max(2, int(deviation / self.max_arc_error))
                for j in range(1, num_subdivisions):
                    sub_t = (i + j / num_subdivisions) / coarse_samples
                    refined_points.append(curve.point_at(sub_t))
            
            refined_points.append(p2)
        
        return refined_points
    
    def _apply_smoothing(self, points: List[Point], smoothing: float) -> List[Point]:
        """Apply smoothing filter to reduce sharp corners"""
        if len(points) < 3 or smoothing <= 0:
            return points
        
        smoothed = [points[0]]  # Keep first point unchanged
        
        for i in range(1, len(points) - 1):
            prev_point = points[i - 1]
            curr_point = points[i]
            next_point = points[i + 1]
            
            # Simple averaging with smoothing factor
            smooth_x = (1 - smoothing) * curr_point.x + smoothing * (prev_point.x + next_point.x) / 2
            smooth_y = (1 - smoothing) * curr_point.y + smoothing * (prev_point.y + next_point.y) / 2
            
            smoothed.append(Point(smooth_x, smooth_y))
        
        smoothed.append(points[-1])  # Keep last point unchanged
        return smoothed
    
    def _calculate_adaptive_feed_rate(self, points: List[Point], index: int) -> int:
        """Calculate adaptive feed rate based on local curvature"""
        base_feed_rate = 1000  # Base feed rate in mm/min
        min_feed_rate = 200    # Minimum feed rate for tight curves
        
        if index < 1 or index >= len(points) - 1:
            return base_feed_rate
        
        # Calculate curvature using three consecutive points
        p1 = points[index - 1]
        p2 = points[index]
        p3 = points[index + 1]
        
        # Calculate angles
        angle1 = p1.angle_to(p2)
        angle2 = p2.angle_to(p3)
        
        # Calculate angle change (curvature indicator)
        angle_change = abs(angle2 - angle1)
        if angle_change > math.pi:
            angle_change = 2 * math.pi - angle_change
        
        # Reduce feed rate for sharp curves
        curvature_factor = 1 - (angle_change / math.pi)
        feed_rate = int(min_feed_rate + (base_feed_rate - min_feed_rate) * curvature_factor)
        
        return max(min_feed_rate, min(base_feed_rate, feed_rate))
    
    def calculate_curve_length(self, points: List[Point]) -> float:
        """Calculate the total length of a curve defined by points"""
        if len(points) < 2:
            return 0.0
        
        total_length = 0.0
        for i in range(1, len(points)):
            total_length += points[i-1].distance_to(points[i])
        
        return total_length
    
    def estimate_drawing_time(self, commands: List[GCodeCommand]) -> float:
        """
        Estimate drawing time considering variable feed rates and curve complexity.
        
        Args:
            commands: List of G-code commands
            
        Returns:
            Estimated time in seconds
        """
        total_time = 0.0
        current_pos = Point(0, 0)
        
        for cmd in commands:
            if cmd.command in ["G0", "G1"] and cmd.x is not None and cmd.y is not None:
                new_pos = Point(cmd.x, cmd.y)
                distance = current_pos.distance_to(new_pos)
                
                # Use command's feed rate or default
                feed_rate = cmd.f if cmd.f else 1000
                feed_rate_per_sec = feed_rate / 60.0
                
                total_time += distance / feed_rate_per_sec
                current_pos = new_pos
            
            elif cmd.command in ["M3", "M5"]:
                # Add time for pen operations
                total_time += 0.1
        
        return total_time