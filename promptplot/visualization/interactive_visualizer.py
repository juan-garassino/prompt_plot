"""
Interactive Visualization System

Enhanced matplotlib-based visualization with interactive features including
zoom, pan, drawing area selection, and real-time pen position tracking.
"""

import time
import numpy as np
from typing import List, Tuple, Optional, Dict, Any, Callable
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum
import logging

try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
    from matplotlib.widgets import Button, Slider, CheckButtons, RectangleSelector
    from matplotlib.patches import Rectangle, Circle, FancyBboxPatch
    from matplotlib.lines import Line2D
    from matplotlib.collections import LineCollection
    from matplotlib.animation import FuncAnimation
    import matplotlib.gridspec as gridspec
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

from ..core.models import GCodeCommand, GCodeProgram
from ..plotter.visualizer import PlotterVisualizer, GridConfiguration, ProgressMarker, ProgressMarkerType


class InteractionMode(str, Enum):
    """Interaction modes for the visualizer"""
    VIEW = "view"
    ZOOM = "zoom"
    PAN = "pan"
    SELECT = "select"
    MEASURE = "measure"


class ViewMode(str, Enum):
    """View modes for different visualization styles"""
    STANDARD = "standard"
    PREVIEW = "preview"
    ANALYSIS = "analysis"
    COMPARISON = "comparison"


@dataclass
class ViewState:
    """Current view state for the interactive visualizer"""
    x_min: float = 0.0
    x_max: float = 100.0
    y_min: float = 0.0
    y_max: float = 100.0
    zoom_level: float = 1.0
    pan_offset: Tuple[float, float] = (0.0, 0.0)
    interaction_mode: InteractionMode = InteractionMode.VIEW
    view_mode: ViewMode = ViewMode.STANDARD


@dataclass
class SelectionArea:
    """Selected area for detailed analysis"""
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    timestamp: float = field(default_factory=time.time)
    label: str = ""


class InteractiveVisualizer(PlotterVisualizer):
    """
    Enhanced interactive visualization system with zoom, pan, and selection capabilities.
    
    Features:
    - Interactive zoom and pan
    - Drawing area selection
    - Real-time pen position tracking
    - Multiple view modes
    - File plotting visualization with path preview
    - Measurement tools
    - Interactive grid configuration
    """
    
    def __init__(self, drawing_area: Tuple[float, float] = (100.0, 100.0),
                 figure_size: Tuple[float, float] = (12, 10),
                 dpi: int = 100, enable_interaction: bool = True,
                 grid_config: Optional[GridConfiguration] = None):
        """Initialize the interactive visualizer
        
        Args:
            drawing_area: (width, height) of drawing area in mm
            figure_size: (width, height) of figure in inches
            dpi: Dots per inch for figure resolution
            enable_interaction: Whether to enable interactive features
            grid_config: Configuration for grid overlay system
        """
        super().__init__(drawing_area, figure_size, dpi, False, grid_config, True)
        
        if not MATPLOTLIB_AVAILABLE:
            raise ImportError("Matplotlib is required for interactive visualization")
        
        self.enable_interaction = enable_interaction
        
        # Interactive state
        self.view_state = ViewState()
        self.selection_areas: List[SelectionArea] = []
        self.current_selection: Optional[SelectionArea] = None
        
        # Interactive widgets
        self.widgets = {}
        self.selector = None
        
        # Real-time tracking
        self.real_time_enabled = False
        self.update_callbacks: List[Callable] = []
        
        # File plotting preview
        self.preview_paths: List[List[Tuple[float, float]]] = []
        self.preview_colors: List[str] = []
        
        # Measurement tools
        self.measurement_points: List[Tuple[float, float]] = []
        self.measurement_lines: List[Line2D] = []
        
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
    
    def setup_interactive_figure(self, title: str = "Interactive Plotter Visualization") -> None:
        """Setup the interactive matplotlib figure with controls"""
        if self.fig is not None:
            plt.close(self.fig)
        
        # Create figure with subplots for controls
        self.fig = plt.figure(figsize=self.figure_size, dpi=self.dpi)
        
        # Create grid layout
        gs = gridspec.GridSpec(4, 4, figure=self.fig, 
                              height_ratios=[0.8, 3, 0.3, 0.3],
                              width_ratios=[3, 0.3, 0.3, 0.3])
        
        # Main plot area
        self.ax = self.fig.add_subplot(gs[1, :])
        
        # Control panels
        self.control_ax = self.fig.add_subplot(gs[0, :])
        self.zoom_ax = self.fig.add_subplot(gs[2, 0])
        self.mode_ax = self.fig.add_subplot(gs[2, 1])
        self.grid_ax = self.fig.add_subplot(gs[2, 2])
        self.tools_ax = self.fig.add_subplot(gs[2, 3])
        
        # Info panel
        self.info_ax = self.fig.add_subplot(gs[3, :])
        
        # Configure main axis
        self._setup_main_axis(title)
        
        # Setup interactive controls
        if self.enable_interaction:
            self._setup_interactive_controls()
            self._setup_event_handlers()
        
        # Setup info panel
        self._setup_info_panel()
    
    def _setup_main_axis(self, title: str) -> None:
        """Setup the main plotting axis"""
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
        
        # Draw drawing area boundary
        boundary = Rectangle((0, 0), self.drawing_area[0], self.drawing_area[1],
                           linewidth=2, edgecolor='gray', facecolor='none', alpha=0.5)
        self.ax.add_patch(boundary)
        
        # Mark home position
        if self.grid_config.origin_marker:
            home_marker = Circle((0, 0), self.grid_config.origin_marker_size, 
                               color=self.grid_config.origin_marker_color, alpha=0.7)
            self.ax.add_patch(home_marker)
            self.ax.text(0, -5, 'Home (0,0)', ha='center', va='top', 
                        color=self.grid_config.origin_marker_color, fontsize=8, fontweight='bold')
    
    def _setup_interactive_controls(self) -> None:
        """Setup interactive control widgets"""
        # Clear control axes
        for ax in [self.control_ax, self.zoom_ax, self.mode_ax, self.grid_ax, self.tools_ax]:
            ax.clear()
            ax.set_xticks([])
            ax.set_yticks([])
        
        # Zoom controls
        self.zoom_ax.set_title("Zoom", fontsize=10)
        zoom_in_btn = Button(plt.axes([0.02, 0.45, 0.08, 0.04]), 'Zoom In')
        zoom_out_btn = Button(plt.axes([0.11, 0.45, 0.08, 0.04]), 'Zoom Out')
        fit_btn = Button(plt.axes([0.20, 0.45, 0.08, 0.04]), 'Fit All')
        
        zoom_in_btn.on_clicked(lambda x: self.zoom_in())
        zoom_out_btn.on_clicked(lambda x: self.zoom_out())
        fit_btn.on_clicked(lambda x: self.fit_to_drawing())
        
        self.widgets.update({
            'zoom_in': zoom_in_btn,
            'zoom_out': zoom_out_btn,
            'fit': fit_btn
        })
        
        # Mode controls
        self.mode_ax.set_title("Mode", fontsize=10)
        mode_labels = ['View', 'Zoom', 'Pan', 'Select', 'Measure']
        mode_check = CheckButtons(plt.axes([0.30, 0.42, 0.15, 0.08]), mode_labels, 
                                 [True, False, False, False, False])
        mode_check.on_clicked(self._on_mode_change)
        self.widgets['mode'] = mode_check
        
        # Grid controls
        self.grid_ax.set_title("Grid", fontsize=10)
        grid_btn = Button(plt.axes([0.47, 0.45, 0.08, 0.04]), 'Toggle Grid')
        snap_btn = Button(plt.axes([0.56, 0.45, 0.08, 0.04]), 'Snap Grid')
        
        grid_btn.on_clicked(lambda x: self.toggle_grid())
        snap_btn.on_clicked(lambda x: self.toggle_snap_to_grid())
        
        self.widgets.update({
            'grid_toggle': grid_btn,
            'snap_toggle': snap_btn
        })
        
        # Tool controls
        self.tools_ax.set_title("Tools", fontsize=10)
        clear_btn = Button(plt.axes([0.66, 0.45, 0.08, 0.04]), 'Clear')
        save_btn = Button(plt.axes([0.75, 0.45, 0.08, 0.04]), 'Save')
        
        clear_btn.on_clicked(lambda x: self.clear_selection())
        save_btn.on_clicked(lambda x: self.save_current_view())
        
        self.widgets.update({
            'clear': clear_btn,
            'save': save_btn
        })
        
        # Rectangle selector for area selection
        self.selector = RectangleSelector(
            self.ax, self._on_area_selected,
            useblit=True, button=[1], minspanx=5, minspany=5,
            spancoords='pixels', interactive=True
        )
        self.selector.set_active(False)
    
    def _setup_event_handlers(self) -> None:
        """Setup matplotlib event handlers"""
        if not self.enable_interaction:
            return
        
        # Mouse events
        self.fig.canvas.mpl_connect('button_press_event', self._on_mouse_press)
        self.fig.canvas.mpl_connect('button_release_event', self._on_mouse_release)
        self.fig.canvas.mpl_connect('motion_notify_event', self._on_mouse_move)
        self.fig.canvas.mpl_connect('scroll_event', self._on_scroll)
        
        # Keyboard events
        self.fig.canvas.mpl_connect('key_press_event', self._on_key_press)
    
    def _setup_info_panel(self) -> None:
        """Setup information panel"""
        self.info_ax.clear()
        self.info_ax.set_xlim(0, 1)
        self.info_ax.set_ylim(0, 1)
        self.info_ax.set_xticks([])
        self.info_ax.set_yticks([])
        
        # Add info text
        info_text = "Interactive Mode: Use mouse to zoom/pan, select areas for analysis"
        self.info_ax.text(0.02, 0.5, info_text, transform=self.info_ax.transAxes,
                         fontsize=9, verticalalignment='center')
    
    def _on_mode_change(self, label: str) -> None:
        """Handle mode change from checkbox"""
        mode_map = {
            'View': InteractionMode.VIEW,
            'Zoom': InteractionMode.ZOOM,
            'Pan': InteractionMode.PAN,
            'Select': InteractionMode.SELECT,
            'Measure': InteractionMode.MEASURE
        }
        
        if label in mode_map:
            self.view_state.interaction_mode = mode_map[label]
            
            # Update selector state
            if self.selector:
                self.selector.set_active(label == 'Select')
            
            self._update_cursor()
            self.logger.info(f"Interaction mode changed to: {label}")
    
    def _on_mouse_press(self, event) -> None:
        """Handle mouse press events"""
        if not event.inaxes == self.ax:
            return
        
        if self.view_state.interaction_mode == InteractionMode.MEASURE:
            self._add_measurement_point(event.xdata, event.ydata)
        elif self.view_state.interaction_mode == InteractionMode.PAN:
            self._start_pan(event.xdata, event.ydata)
    
    def _on_mouse_release(self, event) -> None:
        """Handle mouse release events"""
        if not event.inaxes == self.ax:
            return
        
        if self.view_state.interaction_mode == InteractionMode.PAN:
            self._end_pan()
    
    def _on_mouse_move(self, event) -> None:
        """Handle mouse move events"""
        if not event.inaxes == self.ax:
            return
        
        # Update cursor position in info panel
        if event.xdata is not None and event.ydata is not None:
            self._update_cursor_info(event.xdata, event.ydata)
        
        if self.view_state.interaction_mode == InteractionMode.PAN:
            self._update_pan(event.xdata, event.ydata)
    
    def _on_scroll(self, event) -> None:
        """Handle scroll events for zooming"""
        if not event.inaxes == self.ax:
            return
        
        if event.button == 'up':
            self.zoom_in(center=(event.xdata, event.ydata))
        elif event.button == 'down':
            self.zoom_out(center=(event.xdata, event.ydata))
    
    def _on_key_press(self, event) -> None:
        """Handle keyboard events"""
        if event.key == 'r':
            self.fit_to_drawing()
        elif event.key == 'c':
            self.clear_selection()
        elif event.key == 'g':
            self.toggle_grid()
        elif event.key == 's':
            self.save_current_view()
        elif event.key == 'escape':
            self.view_state.interaction_mode = InteractionMode.VIEW
            if self.selector:
                self.selector.set_active(False)
    
    def _on_area_selected(self, eclick, erelease) -> None:
        """Handle area selection"""
        x1, y1 = eclick.xdata, eclick.ydata
        x2, y2 = erelease.xdata, erelease.ydata
        
        if None in [x1, y1, x2, y2]:
            return
        
        # Create selection area
        selection = SelectionArea(
            x_min=min(x1, x2),
            x_max=max(x1, x2),
            y_min=min(y1, y2),
            y_max=max(y1, y2),
            label=f"Selection {len(self.selection_areas) + 1}"
        )
        
        self.selection_areas.append(selection)
        self.current_selection = selection
        
        self._highlight_selection(selection)
        self.logger.info(f"Area selected: {selection.x_min:.1f},{selection.y_min:.1f} to {selection.x_max:.1f},{selection.y_max:.1f}")
    
    def zoom_in(self, factor: float = 1.5, center: Optional[Tuple[float, float]] = None) -> None:
        """Zoom in on the plot
        
        Args:
            factor: Zoom factor (>1 zooms in)
            center: Center point for zoom, defaults to current view center
        """
        if center is None:
            x_center = (self.view_state.x_min + self.view_state.x_max) / 2
            y_center = (self.view_state.y_min + self.view_state.y_max) / 2
            center = (x_center, y_center)
        
        x_center, y_center = center
        
        # Calculate new bounds
        x_range = (self.view_state.x_max - self.view_state.x_min) / factor
        y_range = (self.view_state.y_max - self.view_state.y_min) / factor
        
        self.view_state.x_min = x_center - x_range / 2
        self.view_state.x_max = x_center + x_range / 2
        self.view_state.y_min = y_center - y_range / 2
        self.view_state.y_max = y_center + y_range / 2
        self.view_state.zoom_level *= factor
        
        self._update_view()
    
    def zoom_out(self, factor: float = 1.5, center: Optional[Tuple[float, float]] = None) -> None:
        """Zoom out of the plot
        
        Args:
            factor: Zoom factor (>1 zooms out)
            center: Center point for zoom, defaults to current view center
        """
        self.zoom_in(1.0 / factor, center)
    
    def pan(self, dx: float, dy: float) -> None:
        """Pan the view by specified amounts
        
        Args:
            dx: Pan distance in X direction
            dy: Pan distance in Y direction
        """
        self.view_state.x_min += dx
        self.view_state.x_max += dx
        self.view_state.y_min += dy
        self.view_state.y_max += dy
        
        self.view_state.pan_offset = (
            self.view_state.pan_offset[0] + dx,
            self.view_state.pan_offset[1] + dy
        )
        
        self._update_view()
    
    def fit_to_drawing(self) -> None:
        """Fit view to show all drawing content"""
        if not self.lines and not self.points:
            # No drawing data, fit to drawing area
            margin = 10
            self.view_state.x_min = -margin
            self.view_state.x_max = self.drawing_area[0] + margin
            self.view_state.y_min = -margin
            self.view_state.y_max = self.drawing_area[1] + margin
        else:
            # Calculate bounds of all drawing data
            all_x = []
            all_y = []
            
            for line in self.lines:
                all_x.extend([line.start_x, line.end_x])
                all_y.extend([line.start_y, line.end_y])
            
            for point in self.points:
                all_x.append(point.x)
                all_y.append(point.y)
            
            if all_x and all_y:
                margin = max(5, (max(all_x) - min(all_x)) * 0.1)
                self.view_state.x_min = min(all_x) - margin
                self.view_state.x_max = max(all_x) + margin
                self.view_state.y_min = min(all_y) - margin
                self.view_state.y_max = max(all_y) + margin
        
        self.view_state.zoom_level = 1.0
        self.view_state.pan_offset = (0.0, 0.0)
        self._update_view()
    
    def _update_view(self) -> None:
        """Update the view based on current view state"""
        self.ax.set_xlim(self.view_state.x_min, self.view_state.x_max)
        self.ax.set_ylim(self.view_state.y_min, self.view_state.y_max)
        
        if self.fig:
            self.fig.canvas.draw_idle()
    
    def _update_cursor(self) -> None:
        """Update cursor based on interaction mode"""
        cursor_map = {
            InteractionMode.VIEW: 'arrow',
            InteractionMode.ZOOM: 'crosshair',
            InteractionMode.PAN: 'move',
            InteractionMode.SELECT: 'crosshair',
            InteractionMode.MEASURE: 'crosshair'
        }
        
        if self.fig and self.fig.canvas:
            cursor = cursor_map.get(self.view_state.interaction_mode, 'arrow')
            # Note: cursor setting is backend-dependent
    
    def _update_cursor_info(self, x: float, y: float) -> None:
        """Update cursor position information"""
        # Snap to grid if enabled
        if hasattr(self, '_snap_to_grid_enabled') and self._snap_to_grid_enabled:
            x, y = self.snap_to_grid((x, y))
        
        info_text = f"Position: ({x:.2f}, {y:.2f}) mm | Mode: {self.view_state.interaction_mode.value}"
        
        # Add selection info if available
        if self.current_selection:
            sel = self.current_selection
            area = (sel.x_max - sel.x_min) * (sel.y_max - sel.y_min)
            info_text += f" | Selection: {area:.1f} mm²"
        
        # Update info panel
        self.info_ax.clear()
        self.info_ax.set_xlim(0, 1)
        self.info_ax.set_ylim(0, 1)
        self.info_ax.set_xticks([])
        self.info_ax.set_yticks([])
        self.info_ax.text(0.02, 0.5, info_text, transform=self.info_ax.transAxes,
                         fontsize=9, verticalalignment='center')
    
    def add_file_preview(self, file_path: str, color: str = 'blue', alpha: float = 0.5) -> None:
        """Add enhanced file plotting preview with path preview before execution
        
        Args:
            file_path: Path to file to preview
            color: Preview color
            alpha: Preview transparency
        """
        try:
            preview_data = self._generate_enhanced_file_preview(file_path)
            if preview_data:
                self.preview_paths.append(preview_data['path'])
                self.preview_colors.append(color)
                self._draw_enhanced_file_preview(preview_data, color, alpha)
                self.logger.info(f"Added enhanced file preview for: {file_path}")
        except Exception as e:
            self.logger.error(f"Failed to add file preview: {str(e)}")
    
    def _generate_enhanced_file_preview(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Generate enhanced preview data from file
        
        Args:
            file_path: Path to file to preview
            
        Returns:
            Dictionary with preview data including path, metadata, and statistics
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            self.logger.warning(f"File not found: {file_path}")
            return None
        
        # This would integrate with actual file converters
        # For now, generate different preview patterns based on file extension
        if file_path.suffix.lower() == '.svg':
            preview_path = self._generate_svg_preview(file_path)
        elif file_path.suffix.lower() in ['.gcode', '.nc']:
            preview_path = self._generate_gcode_preview(file_path)
        elif file_path.suffix.lower() == '.dxf':
            preview_path = self._generate_dxf_preview(file_path)
        else:
            # Default geometric pattern
            preview_path = [(10, 10), (50, 10), (50, 50), (10, 50), (10, 10)]
        
        # Calculate preview statistics
        total_distance = 0.0
        drawing_distance = 0.0
        pen_up_moves = 0
        
        for i in range(1, len(preview_path)):
            x1, y1 = preview_path[i-1]
            x2, y2 = preview_path[i]
            distance = np.sqrt((x2-x1)**2 + (y2-y1)**2)
            total_distance += distance
            
            # Assume continuous drawing for preview
            drawing_distance += distance
        
        return {
            'path': preview_path,
            'file_path': str(file_path),
            'file_type': file_path.suffix.upper(),
            'file_size': file_path.stat().st_size,
            'total_distance': total_distance,
            'drawing_distance': drawing_distance,
            'estimated_time': len(preview_path) * 0.1,  # Simple time estimate
            'point_count': len(preview_path)
        }
    
    def _generate_svg_preview(self, file_path: Path) -> List[Tuple[float, float]]:
        """Generate preview for SVG file"""
        # Placeholder - would use actual SVG parser
        return [
            (20, 20), (80, 20), (80, 80), (20, 80), (20, 20),  # Outer rectangle
            (30, 30), (70, 30), (70, 70), (30, 70), (30, 30)   # Inner rectangle
        ]
    
    def _generate_gcode_preview(self, file_path: Path) -> List[Tuple[float, float]]:
        """Generate preview for G-code file"""
        # Placeholder - would parse actual G-code
        return [
            (0, 0), (25, 25), (50, 0), (75, 25), (100, 0)  # Zigzag pattern
        ]
    
    def _generate_dxf_preview(self, file_path: Path) -> List[Tuple[float, float]]:
        """Generate preview for DXF file"""
        # Placeholder - would use actual DXF parser
        return [
            (15, 15), (85, 15), (85, 85), (15, 85), (15, 15),  # Square
            (50, 15), (50, 85)  # Vertical line through center
        ]
    
    def _draw_enhanced_file_preview(self, preview_data: Dict[str, Any], color: str, alpha: float) -> None:
        """Draw enhanced file preview with metadata
        
        Args:
            preview_data: Preview data dictionary
            color: Preview color
            alpha: Preview transparency
        """
        path = preview_data['path']
        if len(path) < 2:
            return
        
        x_coords = [p[0] for p in path]
        y_coords = [p[1] for p in path]
        
        # Draw preview path
        self.ax.plot(x_coords, y_coords, color=color, alpha=alpha, 
                    linewidth=2, linestyle='--', label=f'Preview: {preview_data["file_type"]}')
        
        # Add start and end markers
        self.ax.plot(x_coords[0], y_coords[0], 'go', markersize=8, alpha=alpha, label='Start')
        self.ax.plot(x_coords[-1], y_coords[-1], 'ro', markersize=8, alpha=alpha, label='End')
        
        # Add preview info box
        info_text = (
            f"File: {Path(preview_data['file_path']).name}\n"
            f"Type: {preview_data['file_type']}\n"
            f"Points: {preview_data['point_count']}\n"
            f"Distance: {preview_data['total_distance']:.1f}mm\n"
            f"Est. Time: {preview_data['estimated_time']:.1f}s"
        )
        
        # Position info box near the preview
        info_x = min(x_coords) + (max(x_coords) - min(x_coords)) * 0.1
        info_y = max(y_coords) + 5
        
        self.ax.text(info_x, info_y, info_text, fontsize=8,
                    bbox=dict(boxstyle='round,pad=0.5', facecolor='white', alpha=0.8, edgecolor=color))
    
    def clear_file_previews(self) -> None:
        """Clear all file previews"""
        self.preview_paths.clear()
        self.preview_colors.clear()
        
        # Remove preview elements from plot
        # This would need to track preview elements to remove them properly
        self.logger.info("Cleared all file previews")
    
    def get_file_preview_info(self) -> List[Dict[str, Any]]:
        """Get information about current file previews
        
        Returns:
            List of preview information dictionaries
        """
        return [
            {
                'path_points': len(path),
                'color': color,
                'bounds': {
                    'x_min': min(p[0] for p in path) if path else 0,
                    'x_max': max(p[0] for p in path) if path else 0,
                    'y_min': min(p[1] for p in path) if path else 0,
                    'y_max': max(p[1] for p in path) if path else 0
                }
            }
            for path, color in zip(self.preview_paths, self.preview_colors)
        ]
    
    def toggle_grid(self) -> None:
        """Toggle grid visibility"""
        from ..plotter.visualizer import GridType
        
        if self.grid_config.grid_type == GridType.NONE:
            self.grid_config.grid_type = GridType.MAJOR
        else:
            self.grid_config.grid_type = GridType.NONE
        
        self._setup_grid_overlay()
        if self.fig:
            self.fig.canvas.draw_idle()
    
    def toggle_snap_to_grid(self) -> None:
        """Toggle snap to grid functionality"""
        self._snap_to_grid_enabled = getattr(self, '_snap_to_grid_enabled', False)
        self._snap_to_grid_enabled = not self._snap_to_grid_enabled
        self.logger.info(f"Snap to grid: {'enabled' if self._snap_to_grid_enabled else 'disabled'}")
    
    def clear_selection(self) -> None:
        """Clear current selection and measurement tools"""
        self.selection_areas.clear()
        self.current_selection = None
        self.measurement_points.clear()
        
        # Clear measurement lines
        for line in self.measurement_lines:
            line.remove()
        self.measurement_lines.clear()
        
        if self.fig:
            self.fig.canvas.draw_idle()
    
    def save_current_view(self) -> str:
        """Save current view to file"""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"interactive_view_{timestamp}"
        return self.save_visualization(filename, format='png')
    
    def _add_measurement_point(self, x: float, y: float) -> None:
        """Add measurement point and draw measurement lines"""
        if hasattr(self, '_snap_to_grid_enabled') and self._snap_to_grid_enabled:
            x, y = self.snap_to_grid((x, y))
        
        self.measurement_points.append((x, y))
        
        # Draw point
        self.ax.plot(x, y, 'ro', markersize=6, markeredgecolor='black')
        
        # Draw line to previous point if exists
        if len(self.measurement_points) > 1:
            prev_x, prev_y = self.measurement_points[-2]
            line = Line2D([prev_x, x], [prev_y, y], color='red', linewidth=2, alpha=0.7)
            self.ax.add_line(line)
            self.measurement_lines.append(line)
            
            # Calculate and display distance
            distance = np.sqrt((x - prev_x)**2 + (y - prev_y)**2)
            mid_x, mid_y = (x + prev_x) / 2, (y + prev_y) / 2
            self.ax.text(mid_x, mid_y, f'{distance:.1f}mm', 
                        ha='center', va='bottom', fontsize=8,
                        bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7))
        
        if self.fig:
            self.fig.canvas.draw_idle()
    
    def _highlight_selection(self, selection: SelectionArea) -> None:
        """Highlight selected area"""
        rect = Rectangle(
            (selection.x_min, selection.y_min),
            selection.x_max - selection.x_min,
            selection.y_max - selection.y_min,
            linewidth=2, edgecolor='red', facecolor='red', alpha=0.2
        )
        self.ax.add_patch(rect)
        
        # Add label
        self.ax.text(selection.x_min + 2, selection.y_max - 2, selection.label,
                    fontsize=10, color='red', fontweight='bold',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))
        
        if self.fig:
            self.fig.canvas.draw_idle()
    
    def _start_pan(self, x: float, y: float) -> None:
        """Start panning operation"""
        self._pan_start = (x, y)
    
    def _update_pan(self, x: float, y: float) -> None:
        """Update panning operation"""
        if hasattr(self, '_pan_start') and self._pan_start:
            start_x, start_y = self._pan_start
            dx = start_x - x
            dy = start_y - y
            self.pan(dx, dy)
            self._pan_start = (x, y)
    
    def _end_pan(self) -> None:
        """End panning operation"""
        if hasattr(self, '_pan_start'):
            delattr(self, '_pan_start')
    
    def enable_real_time_tracking(self, update_interval: float = 0.1) -> None:
        """Enable real-time pen position tracking with enhanced features
        
        Args:
            update_interval: Update interval in seconds
        """
        self.real_time_enabled = True
        self.update_interval = update_interval
        
        # Initialize real-time tracking state
        self.path_preview_points = []
        self.velocity_history = []
        self.acceleration_history = []
        self.last_update_time = time.time()
        
        # Start real-time animation
        if self.fig:
            self.real_time_animation = FuncAnimation(
                self.fig, self._update_real_time,
                interval=int(update_interval * 1000),
                blit=False, repeat=True
            )
            
        self.logger.info(f"Real-time tracking enabled with {update_interval}s interval")
    
    def disable_real_time_tracking(self) -> None:
        """Disable real-time pen position tracking"""
        self.real_time_enabled = False
        if hasattr(self, 'real_time_animation'):
            self.real_time_animation.event_source.stop()
            delattr(self, 'real_time_animation')
    
    def _update_real_time(self, frame) -> None:
        """Update real-time visualization with enhanced tracking"""
        if not self.real_time_enabled:
            return
        
        current_time = time.time()
        curr_x, curr_y, curr_z = self.current_position
        
        # Calculate velocity and acceleration
        if hasattr(self, 'last_position') and hasattr(self, 'last_update_time'):
            dt = current_time - self.last_update_time
            if dt > 0:
                # Calculate velocity (mm/s)
                dx = curr_x - self.last_position[0]
                dy = curr_y - self.last_position[1]
                velocity = np.sqrt(dx**2 + dy**2) / dt
                self.velocity_history.append(velocity)
                
                # Calculate acceleration (mm/s²)
                if len(self.velocity_history) > 1:
                    dv = self.velocity_history[-1] - self.velocity_history[-2]
                    acceleration = dv / dt
                    self.acceleration_history.append(acceleration)
                
                # Limit history size
                if len(self.velocity_history) > 100:
                    self.velocity_history.pop(0)
                if len(self.acceleration_history) > 100:
                    self.acceleration_history.pop(0)
        
        # Update path preview
        self.path_preview_points.append((curr_x, curr_y, current_time))
        if len(self.path_preview_points) > 50:  # Keep last 50 points
            self.path_preview_points.pop(0)
        
        # Remove old current position markers
        for marker in self.progress_markers[:]:
            if marker.marker_type == ProgressMarkerType.CURRENT_POSITION:
                self.progress_markers.remove(marker)
        
        # Add enhanced current position marker with velocity info
        velocity_text = ""
        if self.velocity_history:
            current_velocity = self.velocity_history[-1]
            velocity_text = f" ({current_velocity:.1f}mm/s)"
        
        self.add_progress_marker(
            ProgressMarkerType.CURRENT_POSITION,
            (curr_x, curr_y),
            label=f"Current{velocity_text}",
            color="red" if self.pen_down else "blue"
        )
        
        # Draw path preview trail
        self._draw_path_preview()
        
        # Update velocity indicator
        self._update_velocity_indicator()
        
        # Redraw progress markers
        self._draw_progress_markers()
        
        # Store current state for next update
        self.last_position = (curr_x, curr_y, curr_z)
        self.last_update_time = current_time
        
        # Call update callbacks
        for callback in self.update_callbacks:
            try:
                callback(self)
            except Exception as e:
                self.logger.error(f"Update callback error: {str(e)}")
    
    def add_update_callback(self, callback: Callable) -> None:
        """Add callback for real-time updates
        
        Args:
            callback: Function to call on each update, receives visualizer as argument
        """
        self.update_callbacks.append(callback)
    
    def remove_update_callback(self, callback: Callable) -> None:
        """Remove update callback"""
        if callback in self.update_callbacks:
            self.update_callbacks.remove(callback)
    
    def _draw_path_preview(self) -> None:
        """Draw real-time path preview trail"""
        if not self.path_preview_points or len(self.path_preview_points) < 2:
            return
        
        # Remove old preview lines
        for line in getattr(self, '_preview_lines', []):
            try:
                line.remove()
            except ValueError:
                pass
        
        self._preview_lines = []
        
        # Draw fading trail
        current_time = time.time()
        for i in range(1, len(self.path_preview_points)):
            x1, y1, t1 = self.path_preview_points[i-1]
            x2, y2, t2 = self.path_preview_points[i]
            
            # Calculate fade based on age
            age = current_time - t2
            alpha = max(0.1, 1.0 - (age / 10.0))  # Fade over 10 seconds
            
            # Color based on pen state and age
            color = 'red' if self.pen_down else 'blue'
            
            line = Line2D([x1, x2], [y1, y2], 
                         color=color, alpha=alpha, linewidth=2, linestyle='-')
            self.ax.add_line(line)
            self._preview_lines.append(line)
    
    def _update_velocity_indicator(self) -> None:
        """Update velocity indicator in corner of plot"""
        if not hasattr(self, 'velocity_text'):
            # Create velocity text object
            self.velocity_text = self.ax.text(
                0.02, 0.98, "", transform=self.ax.transAxes,
                fontsize=10, verticalalignment='top',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7)
            )
        
        # Update velocity display
        if self.velocity_history:
            current_velocity = self.velocity_history[-1]
            avg_velocity = np.mean(self.velocity_history[-10:]) if len(self.velocity_history) >= 10 else current_velocity
            
            velocity_text = f"Velocity: {current_velocity:.1f} mm/s\nAvg: {avg_velocity:.1f} mm/s"
            
            if self.acceleration_history:
                current_accel = self.acceleration_history[-1]
                velocity_text += f"\nAccel: {current_accel:.1f} mm/s²"
            
            self.velocity_text.set_text(velocity_text)
        else:
            self.velocity_text.set_text("Velocity: 0.0 mm/s")
    
    def add_drawing_area_selection(self, x_min: float, y_min: float, 
                                 x_max: float, y_max: float, 
                                 label: str = "Selected Area") -> None:
        """Add drawing area selection for detailed analysis
        
        Args:
            x_min, y_min, x_max, y_max: Selection bounds
            label: Label for the selection
        """
        selection = SelectionArea(x_min, x_max, y_min, y_max, label=label)
        self.selection_areas.append(selection)
        self.current_selection = selection
        self._highlight_selection(selection)
        
        # Zoom to selection if requested
        if hasattr(self, '_auto_zoom_to_selection') and self._auto_zoom_to_selection:
            self.zoom_to_area(x_min, y_min, x_max, y_max)
    
    def zoom_to_area(self, x_min: float, y_min: float, x_max: float, y_max: float) -> None:
        """Zoom view to specific area
        
        Args:
            x_min, y_min, x_max, y_max: Area bounds
        """
        # Add margin around selection
        margin_x = (x_max - x_min) * 0.1
        margin_y = (y_max - y_min) * 0.1
        
        self.view_state.x_min = x_min - margin_x
        self.view_state.x_max = x_max + margin_x
        self.view_state.y_min = y_min - margin_y
        self.view_state.y_max = y_max + margin_y
        
        self._update_view()
        self.logger.info(f"Zoomed to area: ({x_min:.1f},{y_min:.1f}) to ({x_max:.1f},{y_max:.1f})")
    
    def enable_auto_zoom_to_selection(self, enabled: bool = True) -> None:
        """Enable automatic zoom to selection areas
        
        Args:
            enabled: Whether to enable auto-zoom
        """
        self._auto_zoom_to_selection = enabled
        self.logger.info(f"Auto-zoom to selection: {'enabled' if enabled else 'disabled'}")
    
    def set_path_preview_length(self, length: int) -> None:
        """Set length of path preview trail
        
        Args:
            length: Number of points to keep in preview trail
        """
        self.path_preview_length = max(10, min(200, length))
        
        # Trim existing preview if needed
        if hasattr(self, 'path_preview_points') and len(self.path_preview_points) > self.path_preview_length:
            self.path_preview_points = self.path_preview_points[-self.path_preview_length:]
        
        self.logger.info(f"Path preview length set to: {self.path_preview_length}")
    
    def get_real_time_statistics(self) -> Dict[str, Any]:
        """Get real-time performance statistics
        
        Returns:
            Dictionary with current statistics
        """
        stats = {
            "current_position": self.current_position,
            "pen_down": self.pen_down,
            "real_time_enabled": self.real_time_enabled
        }
        
        if self.velocity_history:
            stats.update({
                "current_velocity": self.velocity_history[-1],
                "average_velocity": np.mean(self.velocity_history),
                "max_velocity": np.max(self.velocity_history),
                "velocity_samples": len(self.velocity_history)
            })
        
        if self.acceleration_history:
            stats.update({
                "current_acceleration": self.acceleration_history[-1],
                "average_acceleration": np.mean(self.acceleration_history),
                "acceleration_samples": len(self.acceleration_history)
            })
        
        if hasattr(self, 'path_preview_points'):
            stats["preview_points"] = len(self.path_preview_points)
        
        return stats
    
    def get_selection_analysis(self, selection: SelectionArea) -> Dict[str, Any]:
        """Analyze selected area and return statistics
        
        Args:
            selection: Selection area to analyze
            
        Returns:
            Dictionary with analysis results
        """
        # Find lines and points within selection
        selected_lines = []
        selected_points = []
        
        for line in self.lines:
            if (selection.x_min <= line.start_x <= selection.x_max and
                selection.y_min <= line.start_y <= selection.y_max and
                selection.x_min <= line.end_x <= selection.x_max and
                selection.y_min <= line.end_y <= selection.y_max):
                selected_lines.append(line)
        
        for point in self.points:
            if (selection.x_min <= point.x <= selection.x_max and
                selection.y_min <= point.y <= selection.y_max):
                selected_points.append(point)
        
        # Calculate statistics
        drawing_lines = [line for line in selected_lines if line.is_drawing]
        movement_lines = [line for line in selected_lines if not line.is_drawing]
        
        total_drawing_distance = sum(
            np.sqrt((line.end_x - line.start_x)**2 + (line.end_y - line.start_y)**2)
            for line in drawing_lines
        )
        
        total_movement_distance = sum(
            np.sqrt((line.end_x - line.start_x)**2 + (line.end_y - line.start_y)**2)
            for line in movement_lines
        )
        
        return {
            "area": (selection.x_max - selection.x_min) * (selection.y_max - selection.y_min),
            "total_lines": len(selected_lines),
            "drawing_lines": len(drawing_lines),
            "movement_lines": len(movement_lines),
            "total_points": len(selected_points),
            "drawing_distance": total_drawing_distance,
            "movement_distance": total_movement_distance,
            "bounds": {
                "x_min": selection.x_min,
                "x_max": selection.x_max,
                "y_min": selection.y_min,
                "y_max": selection.y_max
            }
        }
    
    def show_interactive(self, block: bool = True) -> None:
        """Display the interactive visualization
        
        Args:
            block: Whether to block execution until window is closed
        """
        if self.fig is None:
            self.setup_interactive_figure()
        
        # Render current drawing data
        self.render_static(show_movements=True, show_statistics=False)
        
        plt.show(block=block)
    
    def close(self) -> None:
        """Close the interactive visualization"""
        self.disable_real_time_tracking()
        super().close()