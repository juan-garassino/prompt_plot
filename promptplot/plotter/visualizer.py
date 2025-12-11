"""
Plotter Visualization Module

Enhanced matplotlib-based visualization for pen plotter operations.
Provides real-time drawing preview and progress tracking capabilities.
Enhanced with grid overlay system, coordinate grid display, plot state
serialization, and visual markers for drawing progress.
"""

import time
import numpy as np
import json
from typing import List, Tuple, Optional, Dict, Any, Union
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum
import logging

try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
    from matplotlib.animation import FuncAnimation
    from matplotlib.patches import Rectangle, Circle
    from matplotlib.lines import Line2D
    from matplotlib.collections import LineCollection
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

# Import vision components for enhanced analysis
from ..vision.plot_analyzer import PlotAnalyzer, PlotState, GridInfo


class GridType(str, Enum):
    """Types of grid overlays"""
    NONE = "none"
    MAJOR = "major"
    MINOR = "minor"
    BOTH = "both"
    CUSTOM = "custom"


class ProgressMarkerType(str, Enum):
    """Types of progress markers"""
    CURRENT_POSITION = "current_position"
    START_POINT = "start_point"
    END_POINT = "end_point"
    WAYPOINT = "waypoint"
    ERROR_POINT = "error_point"


@dataclass
class DrawingPoint:
    """Represents a point in the drawing"""
    x: float
    y: float
    is_drawing: bool
    timestamp: float = field(default_factory=time.time)
    command: Optional[str] = None


@dataclass
class DrawingLine:
    """Represents a line segment in the drawing"""
    start_x: float
    start_y: float
    end_x: float
    end_y: float
    is_drawing: bool
    timestamp: float = field(default_factory=time.time)
    command: Optional[str] = None


@dataclass
class GridConfiguration:
    """Configuration for grid overlay system"""
    grid_type: GridType = GridType.MAJOR
    major_grid_spacing: Tuple[float, float] = (10.0, 10.0)  # (x_spacing, y_spacing)
    minor_grid_spacing: Tuple[float, float] = (1.0, 1.0)
    major_grid_color: str = "gray"
    minor_grid_color: str = "lightgray"
    major_grid_alpha: float = 0.6
    minor_grid_alpha: float = 0.3
    major_grid_linewidth: float = 1.0
    minor_grid_linewidth: float = 0.5
    show_coordinates: bool = True
    coordinate_font_size: int = 8
    origin_marker: bool = True
    origin_marker_size: float = 3.0
    origin_marker_color: str = "red"


@dataclass
class ProgressMarker:
    """Visual marker for drawing progress and completion status"""
    marker_type: ProgressMarkerType
    position: Tuple[float, float]
    label: str = ""
    color: str = "blue"
    size: float = 8.0
    alpha: float = 1.0
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


class PlotterVisualizer:
    """
    Enhanced matplotlib-based visualization for plotter operations
    
    Features:
    - Real-time drawing preview
    - Progress tracking with statistics
    - Multiple visualization modes (lines, points, heatmap)
    - Export capabilities (PNG, PDF, SVG)
    - Animation support for drawing playback
    - Grid overlay system with coordinate display
    - Plot state serialization for analysis
    - Visual markers for drawing progress and completion status
    """
    
    def __init__(self, drawing_area: Tuple[float, float] = (100.0, 100.0),
                 figure_size: Tuple[float, float] = (10, 10),
                 dpi: int = 100, enable_animation: bool = False,
                 grid_config: Optional[GridConfiguration] = None,
                 enable_plot_analysis: bool = True):
        """Initialize the visualizer
        
        Args:
            drawing_area: (width, height) of drawing area in mm
            figure_size: (width, height) of figure in inches
            dpi: Dots per inch for figure resolution
            enable_animation: Whether to enable real-time animation
            grid_config: Configuration for grid overlay system
            enable_plot_analysis: Whether to enable plot state analysis
        """
        if not MATPLOTLIB_AVAILABLE:
            raise ImportError("Matplotlib is required for visualization. Install with: pip install matplotlib")
        
        self.drawing_area = drawing_area
        self.figure_size = figure_size
        self.dpi = dpi
        self.enable_animation = enable_animation
        self.enable_plot_analysis = enable_plot_analysis
        
        # Grid configuration
        self.grid_config = grid_config or GridConfiguration()
        
        # Drawing data
        self.points: List[DrawingPoint] = []
        self.lines: List[DrawingLine] = []
        self.progress_markers: List[ProgressMarker] = []
        self.current_position = (0.0, 0.0, 5.0)  # x, y, z
        self.pen_down = False
        
        # Visualization state
        self.fig = None
        self.ax = None
        self.animation = None
        self.is_live = False
        
        # Plot analysis
        self.plot_analyzer = PlotAnalyzer() if enable_plot_analysis else None
        self._plot_state_history: List[PlotState] = []
        
        # Statistics
        self.stats = {
            "total_distance": 0.0,
            "drawing_distance": 0.0,
            "movement_distance": 0.0,
            "total_time": 0.0,
            "drawing_time": 0.0,
            "pen_up_count": 0,
            "pen_down_count": 0
        }
        
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
    
    def setup_figure(self, title: str = "Plotter Visualization") -> None:
        """Setup the matplotlib figure and axis with enhanced grid system"""
        if self.fig is not None:
            plt.close(self.fig)
        
        self.fig, self.ax = plt.subplots(figsize=self.figure_size, dpi=self.dpi)
        
        # Configure axis
        margin = 10
        self.ax.set_xlim(-margin, self.drawing_area[0] + margin)
        self.ax.set_ylim(-margin, self.drawing_area[1] + margin)
        self.ax.set_aspect('equal')
        self.ax.set_title(title)
        self.ax.set_xlabel('X axis (mm)')
        self.ax.set_ylabel('Y axis (mm)')
        
        # Setup enhanced grid system
        self._setup_grid_overlay()
        
        # Draw drawing area boundary (very subtle)
        boundary = Rectangle((0, 0), self.drawing_area[0], self.drawing_area[1],
                           linewidth=0.5, edgecolor='lightgray', facecolor='none', alpha=0.2)
        self.ax.add_patch(boundary)
        
        # Mark home position with enhanced origin marker
        if self.grid_config.origin_marker:
            home_marker = Circle((0, 0), self.grid_config.origin_marker_size, 
                               color=self.grid_config.origin_marker_color, alpha=0.7)
            self.ax.add_patch(home_marker)
            self.ax.text(0, -5, 'Home (0,0)', ha='center', va='top', 
                        color=self.grid_config.origin_marker_color, fontsize=8, fontweight='bold')
    
    def _setup_grid_overlay(self) -> None:
        """Setup enhanced grid overlay system with coordinate display"""
        if self.grid_config.grid_type == GridType.NONE:
            self.ax.grid(False)
            return
        
        # Clear existing grid
        self.ax.grid(False)
        
        # Calculate grid bounds
        x_min, x_max = self.ax.get_xlim()
        y_min, y_max = self.ax.get_ylim()
        
        # Setup major grid
        if self.grid_config.grid_type in [GridType.MAJOR, GridType.BOTH]:
            self._draw_grid_lines(
                x_min, x_max, y_min, y_max,
                self.grid_config.major_grid_spacing,
                self.grid_config.major_grid_color,
                self.grid_config.major_grid_alpha,
                self.grid_config.major_grid_linewidth,
                is_major=True
            )
        
        # Setup minor grid
        if self.grid_config.grid_type in [GridType.MINOR, GridType.BOTH]:
            self._draw_grid_lines(
                x_min, x_max, y_min, y_max,
                self.grid_config.minor_grid_spacing,
                self.grid_config.minor_grid_color,
                self.grid_config.minor_grid_alpha,
                self.grid_config.minor_grid_linewidth,
                is_major=False
            )
        
        # Add coordinate labels if enabled
        if self.grid_config.show_coordinates:
            self._add_coordinate_labels(x_min, x_max, y_min, y_max)
    
    def _draw_grid_lines(self, x_min: float, x_max: float, y_min: float, y_max: float,
                        spacing: Tuple[float, float], color: str, alpha: float,
                        linewidth: float, is_major: bool = True) -> None:
        """Draw grid lines with specified parameters"""
        x_spacing, y_spacing = spacing
        
        # Vertical lines (constant x)
        x_start = np.ceil(x_min / x_spacing) * x_spacing
        x_positions = np.arange(x_start, x_max + x_spacing, x_spacing)
        
        for x_pos in x_positions:
            if x_min <= x_pos <= x_max:
                line = Line2D([x_pos, x_pos], [y_min, y_max], 
                            color=color, alpha=alpha, linewidth=linewidth,
                            linestyle='-' if is_major else ':')
                self.ax.add_line(line)
        
        # Horizontal lines (constant y)
        y_start = np.ceil(y_min / y_spacing) * y_spacing
        y_positions = np.arange(y_start, y_max + y_spacing, y_spacing)
        
        for y_pos in y_positions:
            if y_min <= y_pos <= y_max:
                line = Line2D([x_min, x_max], [y_pos, y_pos], 
                            color=color, alpha=alpha, linewidth=linewidth,
                            linestyle='-' if is_major else ':')
                self.ax.add_line(line)
    
    def _add_coordinate_labels(self, x_min: float, x_max: float, 
                             y_min: float, y_max: float) -> None:
        """Add coordinate labels for precise positioning reference"""
        x_spacing, y_spacing = self.grid_config.major_grid_spacing
        font_size = self.grid_config.coordinate_font_size
        
        # X-axis labels
        x_start = np.ceil(x_min / x_spacing) * x_spacing
        x_positions = np.arange(x_start, x_max + x_spacing, x_spacing)
        
        for x_pos in x_positions:
            if 0 <= x_pos <= self.drawing_area[0] and x_pos % (x_spacing * 2) == 0:
                self.ax.text(x_pos, -2, f'{x_pos:.0f}', ha='center', va='top',
                           fontsize=font_size, color='darkgray', alpha=0.8)
        
        # Y-axis labels
        y_start = np.ceil(y_min / y_spacing) * y_spacing
        y_positions = np.arange(y_start, y_max + y_spacing, y_spacing)
        
        for y_pos in y_positions:
            if 0 <= y_pos <= self.drawing_area[1] and y_pos % (y_spacing * 2) == 0:
                self.ax.text(-2, y_pos, f'{y_pos:.0f}', ha='right', va='center',
                           fontsize=font_size, color='darkgray', alpha=0.8)
    
    def add_point(self, x: float, y: float, is_drawing: bool, command: Optional[str] = None) -> None:
        """Add a point to the visualization
        
        Args:
            x: X coordinate
            y: Y coordinate
            is_drawing: Whether the pen is drawing (down)
            command: Optional G-code command that created this point
        """
        point = DrawingPoint(x, y, is_drawing, command=command)
        self.points.append(point)
        
        # Update statistics
        if len(self.points) > 1:
            prev_point = self.points[-2]
            distance = np.sqrt((x - prev_point.x)**2 + (y - prev_point.y)**2)
            self.stats["total_distance"] += distance
            
            if is_drawing:
                self.stats["drawing_distance"] += distance
            else:
                self.stats["movement_distance"] += distance
        
        # Update pen state statistics
        if len(self.points) > 1:
            prev_point = self.points[-2]
            if is_drawing and not prev_point.is_drawing:
                self.stats["pen_down_count"] += 1
            elif not is_drawing and prev_point.is_drawing:
                self.stats["pen_up_count"] += 1
    
    def add_line(self, start_x: float, start_y: float, end_x: float, end_y: float,
                 is_drawing: bool, command: Optional[str] = None) -> None:
        """Add a line segment to the visualization
        
        Args:
            start_x: Start X coordinate
            start_y: Start Y coordinate
            end_x: End X coordinate
            end_y: End Y coordinate
            is_drawing: Whether this is a drawing line (pen down)
            command: Optional G-code command that created this line
        """
        line = DrawingLine(start_x, start_y, end_x, end_y, is_drawing, command=command)
        self.lines.append(line)
        
        # Also add points
        self.add_point(start_x, start_y, is_drawing, command)
        self.add_point(end_x, end_y, is_drawing, command)
    
    def update_position(self, x: float, y: float, z: float = None, pen_down: bool = None) -> None:
        """Update current position and pen state
        
        Args:
            x: New X coordinate
            y: New Y coordinate
            z: New Z coordinate (optional)
            pen_down: New pen state (optional)
        """
        old_x, old_y, old_z = self.current_position
        new_z = z if z is not None else old_z
        old_pen_down = self.pen_down
        new_pen_down = pen_down if pen_down is not None else self.pen_down
        
        # Add line from old position to new position
        if (old_x, old_y) != (x, y):
            self.add_line(old_x, old_y, x, y, new_pen_down)
        
        # Update state
        self.current_position = (x, y, new_z)
        self.pen_down = new_pen_down
        
        # Update current position marker
        self.add_progress_marker(
            ProgressMarkerType.CURRENT_POSITION,
            (x, y),
            label="Current",
            color="red" if new_pen_down else "blue"
        )
    
    def render_static(self, show_movements: bool = True, show_statistics: bool = True,
                     color_by_time: bool = False) -> None:
        """Render a static visualization of the drawing
        
        Args:
            show_movements: Whether to show pen-up movements
            show_statistics: Whether to show drawing statistics
            color_by_time: Whether to color lines by time (gradient effect)
        """
        if self.fig is None:
            self.setup_figure()
        
        # Clear previous drawings
        self.ax.clear()
        self.setup_figure("Plotter Drawing")
        
        if not self.lines:
            self.logger.warning("No drawing data to visualize")
            return
        
        # Plot lines
        drawing_lines = [line for line in self.lines if line.is_drawing]
        movement_lines = [line for line in self.lines if not line.is_drawing]
        
        # Plot drawing lines (pen down)
        if drawing_lines:
            if color_by_time:
                # Color by time for gradient effect
                times = [line.timestamp for line in drawing_lines]
                min_time, max_time = min(times), max(times)
                
                for line in drawing_lines:
                    # Normalize time to [0, 1] for colormap
                    if max_time > min_time:
                        time_norm = (line.timestamp - min_time) / (max_time - min_time)
                    else:
                        time_norm = 0.5
                    
                    color = plt.cm.viridis(time_norm)
                    self.ax.plot([line.start_x, line.end_x], [line.start_y, line.end_y],
                               color=color, linewidth=2, alpha=0.8)
            else:
                # Single color for all drawing lines - BLUE for drawing
                for line in drawing_lines:
                    self.ax.plot([line.start_x, line.end_x], [line.start_y, line.end_y],
                               'b-', linewidth=2, alpha=0.8)
        
        # Plot movement lines (pen up) - GRAY for movements
        if show_movements and movement_lines:
            for line in movement_lines:
                self.ax.plot([line.start_x, line.end_x], [line.start_y, line.end_y],
                           '--', color='lightgray', linewidth=1, alpha=0.5)
        
        # Mark start and end points
        if self.points:
            start_point = next((p for p in self.points if p.is_drawing), self.points[0])
            end_point = next((p for p in reversed(self.points) if p.is_drawing), self.points[-1])
            
            self.ax.plot(start_point.x, start_point.y, 'go', markersize=8, label='Start')
            self.ax.plot(end_point.x, end_point.y, 'ro', markersize=8, label='End')
            
            # Current position
            curr_x, curr_y, _ = self.current_position
            self.ax.plot(curr_x, curr_y, 'ko', markersize=6, label='Current')
        
        # Draw progress markers
        self._draw_progress_markers()
        
        # Add legend
        self.ax.legend(loc='upper right')
        
        # Add statistics text
        if show_statistics:
            self._add_statistics_text()
    
    def _add_statistics_text(self) -> None:
        """Add statistics text to the plot"""
        stats_text = (
            f"Drawing Stats:\n"
            f"Total Distance: {self.stats['total_distance']:.1f} mm\n"
            f"Drawing Distance: {self.stats['drawing_distance']:.1f} mm\n"
            f"Movement Distance: {self.stats['movement_distance']:.1f} mm\n"
            f"Pen Lifts: {self.stats['pen_up_count']}\n"
            f"Drawing Segments: {len([l for l in self.lines if l.is_drawing])}\n"
            f"Total Commands: {len(self.lines)}"
        )
        
        # Add text box with statistics
        self.ax.text(0.02, 0.98, stats_text, transform=self.ax.transAxes,
                    verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8),
                    fontsize=9, family='monospace')
    
    def save_visualization(self, filename: str, format: str = 'png', **kwargs) -> str:
        """Save the current visualization to file
        
        Args:
            filename: Output filename (without extension)
            format: Output format ('png', 'pdf', 'svg', 'eps')
            **kwargs: Additional arguments passed to savefig
            
        Returns:
            Full path to saved file
        """
        if self.fig is None:
            self.render_static()
        
        # Ensure results directory exists
        output_dir = Path("results/visualizations")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Add timestamp if not in filename
        if "visualization" not in filename:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"{filename}_{timestamp}"
        
        output_path = output_dir / f"{filename}.{format}"
        
        # Default save parameters
        save_kwargs = {
            'dpi': self.dpi,
            'bbox_inches': 'tight',
            'facecolor': 'white',
            'edgecolor': 'none'
        }
        save_kwargs.update(kwargs)
        
        self.fig.savefig(output_path, **save_kwargs)
        self.logger.info(f"Visualization saved to {output_path}")
        
        return str(output_path)
    
    def create_animation(self, interval: int = 100, save_path: Optional[str] = None) -> None:
        """Create an animated visualization of the drawing process
        
        Args:
            interval: Animation interval in milliseconds
            save_path: Optional path to save animation as GIF or MP4
        """
        if not self.lines:
            self.logger.warning("No drawing data for animation")
            return
        
        if self.fig is None:
            self.setup_figure("Plotter Animation")
        
        # Prepare animation data
        sorted_lines = sorted(self.lines, key=lambda l: l.timestamp)
        
        def animate(frame):
            self.ax.clear()
            self.setup_figure(f"Plotter Animation - Step {frame + 1}/{len(sorted_lines)}")
            
            # Draw lines up to current frame
            for i in range(min(frame + 1, len(sorted_lines))):
                line = sorted_lines[i]
                if line.is_drawing:
                    self.ax.plot([line.start_x, line.end_x], [line.start_y, line.end_y],
                               'b-', linewidth=2, alpha=0.8)
                else:
                    self.ax.plot([line.start_x, line.end_x], [line.start_y, line.end_y],
                               '--', color='lightgray', linewidth=1, alpha=0.5)
            
            # Show current position
            if frame < len(sorted_lines):
                current_line = sorted_lines[frame]
                self.ax.plot(current_line.end_x, current_line.end_y, 'ro', markersize=8)
        
        # Create animation
        self.animation = FuncAnimation(self.fig, animate, frames=len(sorted_lines),
                                     interval=interval, repeat=True, blit=False)
        
        # Save animation if requested
        if save_path:
            try:
                self.animation.save(save_path, writer='pillow' if save_path.endswith('.gif') else 'ffmpeg')
                self.logger.info(f"Animation saved to {save_path}")
            except Exception as e:
                self.logger.error(f"Failed to save animation: {str(e)}")
    
    def show(self, block: bool = True) -> None:
        """Display the visualization
        
        Args:
            block: Whether to block execution until window is closed
        """
        if self.fig is None:
            self.render_static()
        
        plt.show(block=block)
    
    def close(self) -> None:
        """Close the visualization"""
        if self.fig is not None:
            plt.close(self.fig)
            self.fig = None
            self.ax = None
        
        if self.animation is not None:
            self.animation = None
    
    def clear(self) -> None:
        """Clear all drawing data"""
        self.points.clear()
        self.lines.clear()
        self.progress_markers.clear()
        self._plot_state_history.clear()
        self.current_position = (0.0, 0.0, 5.0)
        self.pen_down = False
        
        # Reset statistics
        self.stats = {
            "total_distance": 0.0,
            "drawing_distance": 0.0,
            "movement_distance": 0.0,
            "total_time": 0.0,
            "drawing_time": 0.0,
            "pen_up_count": 0,
            "pen_down_count": 0
        }
    
    def add_progress_marker(self, marker_type: ProgressMarkerType,
                          position: Tuple[float, float],
                          label: str = "",
                          color: str = "blue",
                          size: float = 8.0,
                          metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Add visual marker for drawing progress and completion status
        
        Args:
            marker_type: Type of progress marker
            position: (x, y) position for the marker
            label: Optional label text
            color: Marker color
            size: Marker size
            metadata: Optional metadata dictionary
        """
        # Remove existing markers of the same type (for current position)
        if marker_type == ProgressMarkerType.CURRENT_POSITION:
            self.progress_markers = [
                m for m in self.progress_markers 
                if m.marker_type != ProgressMarkerType.CURRENT_POSITION
            ]
        
        marker = ProgressMarker(
            marker_type=marker_type,
            position=position,
            label=label,
            color=color,
            size=size,
            metadata=metadata or {}
        )
        
        self.progress_markers.append(marker)
    
    def _draw_progress_markers(self) -> None:
        """Draw all progress markers on the plot"""
        for marker in self.progress_markers:
            x, y = marker.position
            
            # Choose marker style based on type
            marker_style = 'o'  # Default circle
            if marker.marker_type == ProgressMarkerType.START_POINT:
                marker_style = '^'  # Triangle up
            elif marker.marker_type == ProgressMarkerType.END_POINT:
                marker_style = 's'  # Square
            elif marker.marker_type == ProgressMarkerType.ERROR_POINT:
                marker_style = 'x'  # X mark
            elif marker.marker_type == ProgressMarkerType.WAYPOINT:
                marker_style = 'd'  # Diamond
            
            # Draw marker
            self.ax.plot(x, y, marker=marker_style, color=marker.color,
                        markersize=marker.size, alpha=marker.alpha,
                        markeredgecolor='black', markeredgewidth=0.5)
            
            # Add label if provided
            if marker.label:
                self.ax.text(x + 1, y + 1, marker.label, fontsize=8,
                           color=marker.color, fontweight='bold')
    
    def capture_plot_state(self) -> Optional[PlotState]:
        """
        Capture current plot state for analysis purposes
        
        Returns:
            PlotState object with current visualization state
        """
        if not self.enable_plot_analysis or not self.fig:
            return None
        
        try:
            plot_state = self.plot_analyzer.capture_plot_state(self.fig)
            self._plot_state_history.append(plot_state)
            return plot_state
        except Exception as e:
            self.logger.warning(f"Failed to capture plot state: {str(e)}")
            return None
    
    def serialize_plot_state(self, output_path: Optional[str] = None) -> Optional[str]:
        """
        Serialize current plot state to JSON for analysis purposes
        
        Args:
            output_path: Optional file path to save serialized data
            
        Returns:
            JSON string representation or None if analysis disabled
        """
        if not self.enable_plot_analysis:
            return None
        
        plot_state = self.capture_plot_state()
        if not plot_state:
            return None
        
        try:
            # Add visualizer-specific metadata
            plot_state.metadata.update({
                "visualizer_stats": self.get_statistics(),
                "drawing_area": self.drawing_area,
                "grid_config": {
                    "grid_type": self.grid_config.grid_type.value,
                    "major_spacing": self.grid_config.major_grid_spacing,
                    "minor_spacing": self.grid_config.minor_grid_spacing
                },
                "progress_markers": [
                    {
                        "type": marker.marker_type.value,
                        "position": marker.position,
                        "label": marker.label,
                        "color": marker.color,
                        "timestamp": marker.timestamp
                    }
                    for marker in self.progress_markers
                ]
            })
            
            return self.plot_analyzer.serialize_plot_state(plot_state, output_path)
        except Exception as e:
            self.logger.error(f"Failed to serialize plot state: {str(e)}")
            return None
    
    def get_grid_info(self) -> Optional[GridInfo]:
        """
        Get current grid information for coordinate analysis
        
        Returns:
            GridInfo object with current grid configuration
        """
        if self.grid_config.grid_type == GridType.NONE:
            return None
        
        x_min, x_max = 0, self.drawing_area[0]
        y_min, y_max = 0, self.drawing_area[1]
        
        return GridInfo(
            x_min=x_min,
            x_max=x_max,
            y_min=y_min,
            y_max=y_max,
            x_step=self.grid_config.major_grid_spacing[0],
            y_step=self.grid_config.major_grid_spacing[1],
            grid_lines_x=list(np.arange(0, x_max + self.grid_config.major_grid_spacing[0], 
                                       self.grid_config.major_grid_spacing[0])),
            grid_lines_y=list(np.arange(0, y_max + self.grid_config.major_grid_spacing[1], 
                                       self.grid_config.major_grid_spacing[1])),
            origin=(0.0, 0.0)
        )
    
    def update_grid_configuration(self, grid_config: GridConfiguration) -> None:
        """
        Update grid configuration and refresh display
        
        Args:
            grid_config: New grid configuration
        """
        self.grid_config = grid_config
        if self.fig and self.ax:
            self._setup_grid_overlay()
            self.fig.canvas.draw_idle()
    
    def snap_to_grid(self, position: Tuple[float, float]) -> Tuple[float, float]:
        """
        Snap position to nearest grid point
        
        Args:
            position: (x, y) position to snap
            
        Returns:
            Snapped (x, y) position
        """
        if self.grid_config.grid_type == GridType.NONE:
            return position
        
        x, y = position
        x_spacing, y_spacing = self.grid_config.major_grid_spacing
        
        # Snap to nearest grid points
        snapped_x = round(x / x_spacing) * x_spacing
        snapped_y = round(y / y_spacing) * y_spacing
        
        return (snapped_x, snapped_y)
    
    def get_plot_state_history(self) -> List[PlotState]:
        """Get history of captured plot states"""
        return self._plot_state_history.copy()
    
    def clear_progress_markers(self) -> None:
        """Clear all progress markers"""
        self.progress_markers.clear()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get drawing statistics
        
        Returns:
            Dictionary with drawing statistics
        """
        stats = self.stats.copy()
        
        # Add derived statistics
        if self.points:
            stats["total_points"] = len(self.points)
            stats["drawing_points"] = len([p for p in self.points if p.is_drawing])
            stats["movement_points"] = len([p for p in self.points if not p.is_drawing])
            
            # Time statistics
            if len(self.points) > 1:
                total_time = self.points[-1].timestamp - self.points[0].timestamp
                stats["total_time"] = total_time
                
                # Estimate drawing efficiency
                if stats["total_distance"] > 0:
                    stats["drawing_efficiency"] = stats["drawing_distance"] / stats["total_distance"]
                else:
                    stats["drawing_efficiency"] = 0.0
        
        stats["total_lines"] = len(self.lines)
        stats["drawing_lines"] = len([l for l in self.lines if l.is_drawing])
        stats["movement_lines"] = len([l for l in self.lines if not l.is_drawing])
        
        # Add grid and marker statistics
        stats["progress_markers"] = len(self.progress_markers)
        stats["grid_enabled"] = self.grid_config.grid_type != GridType.NONE
        stats["plot_states_captured"] = len(self._plot_state_history)
        
        return stats
    
    def save_frame(self, frame_number: int, output_dir: str = "results/frames") -> str:
        """Save current visualization state as PNG frame
        
        Args:
            frame_number: Frame number for filename
            output_dir: Directory to save frames
            
        Returns:
            Path to saved frame
        """
        try:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            frame_filename = f"frame_{frame_number:04d}.png"
            frame_path = output_path / frame_filename
            
            if self.fig and self.ax:
                # Clear the axes but keep the figure
                self.ax.clear()
                
                # Redraw the basic setup
                self.ax.set_xlim(-5, self.drawing_area[0] + 5)
                self.ax.set_ylim(-5, self.drawing_area[1] + 5)
                self.ax.set_aspect('equal')
                self.ax.grid(True, alpha=0.3)
                self.ax.set_xlabel('X (mm)')
                self.ax.set_ylabel('Y (mm)')
                self.ax.set_title(f'Frame {frame_number}')
                
                # Draw all lines accumulated so far
                for line in self.lines:
                    if line.is_drawing:
                        # Drawing lines in BLUE
                        self.ax.plot([line.start_x, line.end_x], [line.start_y, line.end_y],
                                   'b-', linewidth=2.5, solid_capstyle='round')
                    else:
                        # Movement lines in light gray
                        self.ax.plot([line.start_x, line.end_x], [line.start_y, line.end_y],
                                   '--', color='lightgray', linewidth=1, alpha=0.4)
                
                # Draw current position marker
                if self.lines:
                    last_line = self.lines[-1]
                    self.ax.plot(last_line.end_x, last_line.end_y, 'ro', markersize=8)
                
                # Force canvas update and save
                self.fig.canvas.draw()
                self.fig.savefig(frame_path, dpi=100, bbox_inches='tight')
                self.logger.debug(f"Saved frame {frame_number}: {frame_path}")
            
            return str(frame_path)
            
        except Exception as e:
            self.logger.error(f"Failed to save frame {frame_number}: {str(e)}")
            return ""
    
    def create_animation_from_frames(self, frames_dir: str, output_path: str, 
                                   duration: float = 0.5) -> bool:
        """Create animated GIF from saved frames
        
        Args:
            frames_dir: Directory containing frame PNG files
            output_path: Output path for GIF
            duration: Duration per frame in seconds
            
        Returns:
            True if successful, False otherwise
        """
        try:
            from PIL import Image
            import glob
            
            # Get all frame files
            frame_pattern = str(Path(frames_dir) / "frame_*.png")
            frame_files = sorted(glob.glob(frame_pattern))
            
            if not frame_files:
                self.logger.warning(f"No frame files found in {frames_dir}")
                return False
            
            # Load images
            images = []
            for frame_file in frame_files:
                img = Image.open(frame_file)
                images.append(img)
            
            # Save as animated GIF
            if images:
                images[0].save(
                    output_path,
                    save_all=True,
                    append_images=images[1:],
                    duration=int(duration * 1000),  # Convert to milliseconds
                    loop=0
                )
                self.logger.info(f"Created animation: {output_path}")
                return True
            
        except ImportError:
            self.logger.error("PIL (Pillow) not available for GIF creation")
        except Exception as e:
            self.logger.error(f"Failed to create animation: {str(e)}")
        
        return False
    
    def generate_final_png(self, output_path: str, title: str = None, 
                          execution_stats: dict = None) -> bool:
        """Generate final PNG with title and statistics
        
        Args:
            output_path: Output path for PNG
            title: Optional title for the plot
            execution_stats: Optional execution statistics
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.fig or not self.ax:
                self.logger.error("No figure available for PNG generation")
                return False
            
            # Update title with statistics if provided
            if title or execution_stats:
                plot_title = title or "Plotter Drawing"
                if execution_stats:
                    plot_title += f"\nTime: {execution_stats.get('total_time', 0):.1f}s, "
                    plot_title += f"Distance: {execution_stats.get('drawing_distance', 0):.1f}mm"
                
                self.ax.set_title(plot_title, fontsize=12, pad=20)
            
            # Add start and end markers if we have drawing data
            if self.lines:
                # Find first and last drawing positions
                drawing_lines = [l for l in self.lines if l.is_drawing]
                if drawing_lines:
                    first_line = drawing_lines[0]
                    last_line = drawing_lines[-1]
                    
                    self.ax.plot(first_line.start_x, first_line.start_y, 'go', 
                               markersize=8, label='Start', zorder=10)
                    self.ax.plot(last_line.end_x, last_line.end_y, 'ro', 
                               markersize=8, label='End', zorder=10)
                    self.ax.legend()
            
            # Save the figure
            self.fig.savefig(output_path, dpi=150, bbox_inches='tight')
            self.logger.info(f"Generated final PNG: {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to generate final PNG: {str(e)}")
            return False
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()