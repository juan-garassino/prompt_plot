"""
Drawing strategy system for PromptPlot v2.0

This module provides intelligent strategy selection and implementation
for different types of drawing tasks, optimizing G-code generation
based on the complexity and nature of the drawing requirements.
"""

from .selector import StrategySelector, PromptComplexity, ComplexityLevel
from .orthogonal import OrthogonalStrategy
from .non_orthogonal import NonOrthogonalStrategy

__all__ = [
    'StrategySelector',
    'PromptComplexity', 
    'ComplexityLevel',
    'OrthogonalStrategy',
    'NonOrthogonalStrategy'
]