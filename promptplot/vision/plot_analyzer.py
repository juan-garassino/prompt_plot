"""
Matplotlib Plot Analysis Interface

This module provides comprehensive analysis capabilities for matplotlib plots,
including plot state capture, grid-based coordinate analysis, drawing progress
detection, and plot comparison for change detection.
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.figure import Figure
from matplotlib.axes import Axes
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from pathlib import Path
import json
import time
import logging
from enum import Enum

from ..core.models import GCodeCommand, GCodeProgram


class PlotElementType(str, Enum):
    """Types of plot elements that can be detected"""
    LINE = "line"
    POINT = "point"
    RECTANGLE = "rectangle"
    CIRCLE = "circle"
    POLYGON = "polygon"
    TEXT = "text"
    GRID = "grid"


@dataclass
class PlotElement:
    """Represents a detected element in a matplotlib plot"""
    element_type: PlotElementType
    coordinates: List[Tuple[float, float]]
    properties: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class GridInfo:
    """Information about the coordinate grid system"""
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    x_step: Optional[float] = None
    y_step: Optional[float] = None
    grid_lines_x: List[float] = field(default_factory=list)
    grid_lines_y: List[float] = field(default_factory=list)
    origin: Tuple[float, float] = (0.0, 0.0)


@dataclass
class PlotState:
    """Complete state of a matplotlib plot"""
    elements: List[PlotElement] = field(default_factory=list)
    grid_info: Optional[GridInfo] = None
    bounds: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    figure_size: Tuple[float, float] = (10, 10)
    dpi: int = 100


@dataclass
class DrawingProgress:
    """Analysis of drawing progress from plot data"""
    total_elements: int
    completed_elements: int
    progress_percentage: float
    current_position: Optional[Tuple[float, float]] = None
    drawing_bounds: Optional[Dict[str, float]] = None
    estimated_completion_time: Optional[float] = None


@dataclass
class PlotComparison:
    """Result of comparing two plot states"""
    added_elements: List[PlotElement] = field(default_factory=list)
    removed_elements: List[PlotElement] = field(default_factory=list)
    modified_elements: List[Tuple[PlotElement, PlotElement]] = field(default_factory=list)
    similarity_score: float = 0.0
    change_summary: Dict[str, Any] = field(default_factory=dict)


class PlotAnalyzer:
    """
    Matplotlib plot analysis interface for pen plotter integration
    
    Provides comprehensive analysis of matplotlib plots including:
    - Plot state capture and serialization
    - Grid-based coordinate analysis
    - Drawing progress detection from figure data
    - Plot comparison and change detection capabilities
    """
    
    def __init__(self, grid_resolution: float = 1.0, 
                 coordinate_precision: int = 3,
                 enable_caching: bool = True):
        """
        Initialize the plot analyzer
        
        Args:
            grid_resolution: Resolution for grid-based coordinate analysis
            coordinate_precision: Decimal precision for coordinate calculations
            enable_caching: Whether to cache analysis results
        """
        self.grid_resolution = grid_resolution
        self.coordinate_precision = coordinate_precision
        self.enable_caching = enable_caching
        
        # Analysis cache
        self._plot_cache: Dict[str, PlotState] = {}
        self._analysis_cache: Dict[str, Any] = {}
        
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
    
    def capture_plot_state(self, figure: Figure, 
                          include_grid_analysis: bool = True) -> PlotState:
        """
        Capture complete state of a matplotlib figure
        
        Args:
            figure: Matplotlib figure to analyze
            include_grid_analysis: Whether to perform grid analysis
            
        Returns:
            Complete plot state with detected elements and metadata
        """
        plot_state = PlotState(
            figure_size=figure.get_size_inches(),
            dpi=figure.dpi,
            timestamp=time.time()
        )
        
        # Analyze each axis in the figure
        for ax in figure.get_axes():
            # Extract plot elements from axis
            elements = self._extract_plot_elements(ax)
            plot_state.elements.extend(elements)
            
            # Analyze grid if requested
            if include_grid_analysis:
                grid_info = self._analyze_grid_system(ax)
                if grid_info:
                    plot_state.grid_info = grid_info
            
            # Calculate bounds
            bounds = self._calculate_plot_bounds(ax)
            plot_state.bounds.update(bounds)
        
        # Add metadata
        plot_state.metadata = {
            "num_axes": len(figure.get_axes()),
            "total_elements": len(plot_state.elements),
            "element_types": list(set(elem.element_type for elem in plot_state.elements)),
            "analysis_timestamp": time.time()
        }
        
        # Cache if enabled
        if self.enable_caching:
            cache_key = f"plot_{id(figure)}_{plot_state.timestamp}"
            self._plot_cache[cache_key] = plot_state
        
        return plot_state
    
    def _extract_plot_elements(self, ax: Axes) -> List[PlotElement]:
        """Extract plot elements from a matplotlib axis"""
        elements = []
        
        # Extract line elements
        for line in ax.get_lines():
            xdata, ydata = line.get_data()
            if len(xdata) > 0 and len(ydata) > 0:
                coordinates = list(zip(xdata, ydata))
                properties = {
                    "color": line.get_color(),
                    "linewidth": line.get_linewidth(),
                    "linestyle": line.get_linestyle(),
                    "marker": line.get_marker(),
                    "alpha": line.get_alpha() or 1.0
                }
                
                element = PlotElement(
                    element_type=PlotElementType.LINE,
                    coordinates=coordinates,
                    properties=properties
                )
                elements.append(element)
        
        # Extract patch elements (rectangles, circles, polygons)
        for patch in ax.get_children():
            if isinstance(patch, patches.Rectangle):
                x, y = patch.get_x(), patch.get_y()
                width, height = patch.get_width(), patch.get_height()
                coordinates = [
                    (x, y), (x + width, y), 
                    (x + width, y + height), (x, y + height)
                ]
                
                properties = {
                    "facecolor": patch.get_facecolor(),
                    "edgecolor": patch.get_edgecolor(),
                    "linewidth": patch.get_linewidth(),
                    "alpha": patch.get_alpha() or 1.0,
                    "width": width,
                    "height": height
                }
                
                element = PlotElement(
                    element_type=PlotElementType.RECTANGLE,
                    coordinates=coordinates,
                    properties=properties
                )
                elements.append(element)
            
            elif isinstance(patch, patches.Circle):
                center = patch.center
                radius = patch.radius
                # Approximate circle with points
                angles = np.linspace(0, 2*np.pi, 32)
                coordinates = [
                    (center[0] + radius * np.cos(angle),
                     center[1] + radius * np.sin(angle))
                    for angle in angles
                ]
                
                properties = {
                    "center": center,
                    "radius": radius,
                    "facecolor": patch.get_facecolor(),
                    "edgecolor": patch.get_edgecolor(),
                    "linewidth": patch.get_linewidth(),
                    "alpha": patch.get_alpha() or 1.0
                }
                
                element = PlotElement(
                    element_type=PlotElementType.CIRCLE,
                    coordinates=coordinates,
                    properties=properties
                )
                elements.append(element)
        
        # Extract text elements
        for text in ax.get_children():
            if hasattr(text, 'get_text') and hasattr(text, 'get_position'):
                try:
                    text_content = text.get_text()
                    if text_content.strip():  # Only non-empty text
                        position = text.get_position()
                        coordinates = [position]
                        
                        properties = {
                            "text": text_content,
                            "fontsize": getattr(text, 'get_fontsize', lambda: 12)(),
                            "color": getattr(text, 'get_color', lambda: 'black')(),
                            "ha": getattr(text, 'get_ha', lambda: 'left')(),
                            "va": getattr(text, 'get_va', lambda: 'bottom')()
                        }
                        
                        element = PlotElement(
                            element_type=PlotElementType.TEXT,
                            coordinates=coordinates,
                            properties=properties
                        )
                        elements.append(element)
                except (AttributeError, TypeError):
                    # Skip elements that don't have expected text properties
                    continue
        
        return elements
    
    def _analyze_grid_system(self, ax: Axes) -> Optional[GridInfo]:
        """Analyze the coordinate grid system of an axis"""
        try:
            # Get axis limits
            xlim = ax.get_xlim()
            ylim = ax.get_ylim()
            
            # Get grid lines if visible
            grid_lines_x = []
            grid_lines_y = []
            
            # Try to extract grid information from ticks
            xticks = ax.get_xticks()
            yticks = ax.get_yticks()
            
            # Filter ticks within axis limits
            xticks = [x for x in xticks if xlim[0] <= x <= xlim[1]]
            yticks = [y for y in yticks if ylim[0] <= y <= ylim[1]]
            
            # Calculate grid steps
            x_step = None
            y_step = None
            
            if len(xticks) > 1:
                x_diffs = np.diff(sorted(xticks))
                x_step = np.median(x_diffs) if len(x_diffs) > 0 else None
                grid_lines_x = list(xticks)
            
            if len(yticks) > 1:
                y_diffs = np.diff(sorted(yticks))
                y_step = np.median(y_diffs) if len(y_diffs) > 0 else None
                grid_lines_y = list(yticks)
            
            # Find origin (closest point to 0,0 within limits)
            origin_x = 0.0 if xlim[0] <= 0.0 <= xlim[1] else xlim[0]
            origin_y = 0.0 if ylim[0] <= 0.0 <= ylim[1] else ylim[0]
            
            return GridInfo(
                x_min=xlim[0],
                x_max=xlim[1],
                y_min=ylim[0],
                y_max=ylim[1],
                x_step=x_step,
                y_step=y_step,
                grid_lines_x=grid_lines_x,
                grid_lines_y=grid_lines_y,
                origin=(origin_x, origin_y)
            )
            
        except Exception as e:
            self.logger.warning(f"Failed to analyze grid system: {str(e)}")
            return None
    
    def _calculate_plot_bounds(self, ax: Axes) -> Dict[str, float]:
        """Calculate the bounds of all plot elements"""
        bounds = {}
        
        try:
            # Get data limits
            xlim = ax.get_xlim()
            ylim = ax.get_ylim()
            
            bounds.update({
                "x_min": xlim[0],
                "x_max": xlim[1],
                "y_min": ylim[0],
                "y_max": ylim[1]
            })
            
            # Calculate data bounds from actual plot elements
            all_x_coords = []
            all_y_coords = []
            
            for line in ax.get_lines():
                xdata, ydata = line.get_data()
                all_x_coords.extend(xdata)
                all_y_coords.extend(ydata)
            
            if all_x_coords and all_y_coords:
                bounds.update({
                    "data_x_min": min(all_x_coords),
                    "data_x_max": max(all_x_coords),
                    "data_y_min": min(all_y_coords),
                    "data_y_max": max(all_y_coords)
                })
            
        except Exception as e:
            self.logger.warning(f"Failed to calculate plot bounds: {str(e)}")
        
        return bounds
    
    def analyze_drawing_progress(self, plot_state: PlotState,
                               target_gcode: Optional[GCodeProgram] = None) -> DrawingProgress:
        """
        Analyze drawing progress from matplotlib figure data
        
        Args:
            plot_state: Current plot state to analyze
            target_gcode: Optional target G-code program for comparison
            
        Returns:
            Drawing progress analysis with completion metrics
        """
        # Count total elements and analyze completion
        total_elements = len(plot_state.elements)
        
        # Analyze drawing elements (lines that represent actual drawing)
        drawing_elements = [
            elem for elem in plot_state.elements 
            if elem.element_type == PlotElementType.LINE and 
            elem.properties.get("linewidth", 0) > 1  # Assume drawing lines are thicker
        ]
        
        completed_elements = len(drawing_elements)
        
        # Calculate progress percentage
        if target_gcode:
            # Use target G-code to estimate total expected elements
            expected_drawing_commands = len(target_gcode.get_drawing_commands())
            progress_percentage = (completed_elements / max(expected_drawing_commands, 1)) * 100
        else:
            # Use heuristic based on plot complexity
            estimated_total = max(total_elements, completed_elements * 1.2)
            progress_percentage = (completed_elements / estimated_total) * 100
        
        # Find current position (last point of last drawing element)
        current_position = None
        if drawing_elements:
            last_element = drawing_elements[-1]
            if last_element.coordinates:
                current_position = last_element.coordinates[-1]
        
        # Calculate drawing bounds
        drawing_bounds = None
        if drawing_elements:
            all_coords = []
            for elem in drawing_elements:
                all_coords.extend(elem.coordinates)
            
            if all_coords:
                x_coords = [coord[0] for coord in all_coords]
                y_coords = [coord[1] for coord in all_coords]
                drawing_bounds = {
                    "min_x": min(x_coords),
                    "max_x": max(x_coords),
                    "min_y": min(y_coords),
                    "max_y": max(y_coords)
                }
        
        # Estimate completion time (simple heuristic)
        estimated_completion_time = None
        if progress_percentage > 0 and progress_percentage < 100:
            elapsed_time = time.time() - plot_state.timestamp
            if elapsed_time > 0:
                estimated_total_time = elapsed_time * (100 / progress_percentage)
                estimated_completion_time = estimated_total_time - elapsed_time
        
        return DrawingProgress(
            total_elements=total_elements,
            completed_elements=completed_elements,
            progress_percentage=min(progress_percentage, 100.0),
            current_position=current_position,
            drawing_bounds=drawing_bounds,
            estimated_completion_time=estimated_completion_time
        )
    
    def compare_plots(self, plot_state_1: PlotState, 
                     plot_state_2: PlotState,
                     tolerance: float = 0.01) -> PlotComparison:
        """
        Compare two plot states to detect changes
        
        Args:
            plot_state_1: First plot state (baseline)
            plot_state_2: Second plot state (comparison)
            tolerance: Coordinate tolerance for element matching
            
        Returns:
            Detailed comparison results with added, removed, and modified elements
        """
        comparison = PlotComparison()
        
        # Create element matching based on coordinates and type
        matched_elements = set()
        
        # Find added and modified elements
        for elem2 in plot_state_2.elements:
            best_match = None
            best_distance = float('inf')
            
            for i, elem1 in enumerate(plot_state_1.elements):
                if i in matched_elements:
                    continue
                
                if elem1.element_type == elem2.element_type:
                    # Calculate coordinate distance
                    distance = self._calculate_element_distance(elem1, elem2)
                    if distance < best_distance and distance <= tolerance:
                        best_distance = distance
                        best_match = i
            
            if best_match is not None:
                # Element exists in both plots
                matched_elements.add(best_match)
                elem1 = plot_state_1.elements[best_match]
                
                # Check if element was modified
                if not self._elements_equal(elem1, elem2, tolerance):
                    comparison.modified_elements.append((elem1, elem2))
            else:
                # New element added
                comparison.added_elements.append(elem2)
        
        # Find removed elements
        for i, elem1 in enumerate(plot_state_1.elements):
            if i not in matched_elements:
                comparison.removed_elements.append(elem1)
        
        # Calculate similarity score
        total_elements = len(plot_state_1.elements) + len(plot_state_2.elements)
        if total_elements > 0:
            changes = (len(comparison.added_elements) + 
                      len(comparison.removed_elements) + 
                      len(comparison.modified_elements))
            comparison.similarity_score = 1.0 - (changes / total_elements)
        else:
            comparison.similarity_score = 1.0
        
        # Generate change summary
        comparison.change_summary = {
            "added_count": len(comparison.added_elements),
            "removed_count": len(comparison.removed_elements),
            "modified_count": len(comparison.modified_elements),
            "similarity_score": comparison.similarity_score,
            "significant_change": comparison.similarity_score < 0.8,
            "timestamp_diff": plot_state_2.timestamp - plot_state_1.timestamp
        }
        
        return comparison
    
    def _calculate_element_distance(self, elem1: PlotElement, 
                                  elem2: PlotElement) -> float:
        """Calculate distance between two plot elements"""
        if elem1.element_type != elem2.element_type:
            return float('inf')
        
        # For elements with coordinates, calculate average coordinate distance
        if elem1.coordinates and elem2.coordinates:
            # Use first coordinate for simple distance calculation
            coord1 = elem1.coordinates[0]
            coord2 = elem2.coordinates[0]
            return np.sqrt((coord1[0] - coord2[0])**2 + (coord1[1] - coord2[1])**2)
        
        return 0.0
    
    def _elements_equal(self, elem1: PlotElement, elem2: PlotElement, 
                       tolerance: float) -> bool:
        """Check if two elements are equal within tolerance"""
        if elem1.element_type != elem2.element_type:
            return False
        
        # Compare coordinates
        if len(elem1.coordinates) != len(elem2.coordinates):
            return False
        
        for coord1, coord2 in zip(elem1.coordinates, elem2.coordinates):
            if (abs(coord1[0] - coord2[0]) > tolerance or 
                abs(coord1[1] - coord2[1]) > tolerance):
                return False
        
        # Compare key properties
        key_props = ['color', 'linewidth', 'marker']
        for prop in key_props:
            val1 = elem1.properties.get(prop)
            val2 = elem2.properties.get(prop)
            if val1 != val2:
                return False
        
        return True
    
    def serialize_plot_state(self, plot_state: PlotState, 
                           output_path: Optional[str] = None) -> str:
        """
        Serialize plot state to JSON for analysis purposes
        
        Args:
            plot_state: Plot state to serialize
            output_path: Optional file path to save serialized data
            
        Returns:
            JSON string representation of plot state
        """
        # Convert to serializable format
        serializable_data = {
            "timestamp": plot_state.timestamp,
            "figure_size": plot_state.figure_size,
            "dpi": plot_state.dpi,
            "bounds": plot_state.bounds,
            "metadata": plot_state.metadata,
            "elements": [],
            "grid_info": None
        }
        
        # Serialize elements
        for elem in plot_state.elements:
            elem_data = {
                "element_type": elem.element_type.value,
                "coordinates": elem.coordinates,
                "properties": elem.properties,
                "confidence": elem.confidence,
                "timestamp": elem.timestamp
            }
            serializable_data["elements"].append(elem_data)
        
        # Serialize grid info
        if plot_state.grid_info:
            serializable_data["grid_info"] = {
                "x_min": plot_state.grid_info.x_min,
                "x_max": plot_state.grid_info.x_max,
                "y_min": plot_state.grid_info.y_min,
                "y_max": plot_state.grid_info.y_max,
                "x_step": plot_state.grid_info.x_step,
                "y_step": plot_state.grid_info.y_step,
                "grid_lines_x": plot_state.grid_info.grid_lines_x,
                "grid_lines_y": plot_state.grid_info.grid_lines_y,
                "origin": plot_state.grid_info.origin
            }
        
        # Convert to JSON
        json_data = json.dumps(serializable_data, indent=2, default=str)
        
        # Save to file if requested
        if output_path:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(json_data)
            self.logger.info(f"Plot state serialized to {output_path}")
        
        return json_data
    
    def deserialize_plot_state(self, json_data: str) -> PlotState:
        """
        Deserialize plot state from JSON
        
        Args:
            json_data: JSON string representation of plot state
            
        Returns:
            Reconstructed plot state object
        """
        data = json.loads(json_data)
        
        # Reconstruct elements
        elements = []
        for elem_data in data.get("elements", []):
            element = PlotElement(
                element_type=PlotElementType(elem_data["element_type"]),
                coordinates=elem_data["coordinates"],
                properties=elem_data["properties"],
                confidence=elem_data["confidence"],
                timestamp=elem_data["timestamp"]
            )
            elements.append(element)
        
        # Reconstruct grid info
        grid_info = None
        if data.get("grid_info"):
            grid_data = data["grid_info"]
            grid_info = GridInfo(
                x_min=grid_data["x_min"],
                x_max=grid_data["x_max"],
                y_min=grid_data["y_min"],
                y_max=grid_data["y_max"],
                x_step=grid_data["x_step"],
                y_step=grid_data["y_step"],
                grid_lines_x=grid_data["grid_lines_x"],
                grid_lines_y=grid_data["grid_lines_y"],
                origin=tuple(grid_data["origin"])
            )
        
        # Reconstruct plot state
        plot_state = PlotState(
            elements=elements,
            grid_info=grid_info,
            bounds=data.get("bounds", {}),
            metadata=data.get("metadata", {}),
            timestamp=data["timestamp"],
            figure_size=tuple(data["figure_size"]),
            dpi=data["dpi"]
        )
        
        return plot_state
    
    def get_grid_coordinates(self, plot_state: PlotState, 
                           point: Tuple[float, float]) -> Optional[Tuple[int, int]]:
        """
        Convert plot coordinates to grid coordinates
        
        Args:
            plot_state: Plot state with grid information
            point: (x, y) coordinates in plot space
            
        Returns:
            (grid_x, grid_y) coordinates or None if no grid available
        """
        if not plot_state.grid_info:
            return None
        
        grid = plot_state.grid_info
        x, y = point
        
        # Calculate grid coordinates relative to origin
        if grid.x_step and grid.y_step:
            grid_x = round((x - grid.origin[0]) / grid.x_step)
            grid_y = round((y - grid.origin[1]) / grid.y_step)
            return (grid_x, grid_y)
        
        return None
    
    def clear_cache(self) -> None:
        """Clear analysis cache"""
        self._plot_cache.clear()
        self._analysis_cache.clear()
        self.logger.info("Analysis cache cleared")