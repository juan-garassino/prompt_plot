"""
Vision Module for PromptPlot v2.0

This module provides computer vision capabilities for pen plotter operations,
including matplotlib plot analysis, visual feedback processing, and intelligent
drawing decision support.
"""

from .plot_analyzer import (
    PlotAnalyzer,
    PlotState,
    PlotElement,
    PlotElementType,
    GridInfo,
    DrawingProgress,
    PlotComparison
)

from .feedback import (
    FeedbackAnalyzer,
    DrawingIntent,
    ProgressFeedback,
    ActionSuggestion,
    CoordinateValidation,
    OptimizationSuggestion,
    FeedbackType,
    ActionType
)

__all__ = [
    # Plot Analysis
    "PlotAnalyzer",
    "PlotState", 
    "PlotElement",
    "PlotElementType",
    "GridInfo",
    "DrawingProgress",
    "PlotComparison",
    
    # Feedback Analysis
    "FeedbackAnalyzer",
    "DrawingIntent",
    "ProgressFeedback", 
    "ActionSuggestion",
    "CoordinateValidation",
    "OptimizationSuggestion",
    "FeedbackType",
    "ActionType"
]