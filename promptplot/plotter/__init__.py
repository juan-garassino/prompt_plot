"""
PromptPlot Plotter Module

This module contains plotter interfaces and implementations:
- base: Base plotter interface with unified API
- serial_plotter: Real hardware plotter via serial connection
- simulated: Enhanced simulated plotter for testing
- visualizer: Matplotlib-based visualization system
"""

from .base import BasePlotter, PlotterStatus
from .simulated import SimulatedPlotter, SimulatedPlotterStatus
from .serial_plotter import SerialPlotter, SerialPlotterStatus

# Import visualizer components if matplotlib is available
try:
    from .visualizer import PlotterVisualizer, DrawingPoint, DrawingLine, MATPLOTLIB_AVAILABLE
    __all__ = [
        "BasePlotter", 
        "PlotterStatus",
        "SimulatedPlotter",
        "SimulatedPlotterStatus", 
        "SerialPlotter",
        "SerialPlotterStatus",
        "PlotterVisualizer",
        "DrawingPoint",
        "DrawingLine",
        "MATPLOTLIB_AVAILABLE"
    ]
except ImportError:
    # Matplotlib not available, skip visualizer
    __all__ = [
        "BasePlotter", 
        "PlotterStatus",
        "SimulatedPlotter",
        "SimulatedPlotterStatus",
        "SerialPlotter", 
        "SerialPlotterStatus"
    ]