"""
File conversion utilities for PromptPlot v2.0

This module provides converters for various file formats to G-code,
enabling direct plotting of existing files without LLM generation.
"""

from .gcode_loader import GCodeLoader, GCodeProcessor
from .svg_converter import SVGConverter
from .dxf_converter import DXFConverter
from .hpgl_converter import HPGLConverter
from .json_converter import JSONConverter
from .image_converter import ImageConverter
from .file_detector import FileFormatDetector, SupportedFormat

__all__ = [
    'GCodeLoader',
    'GCodeProcessor',
    'SVGConverter',
    'DXFConverter',
    'HPGLConverter', 
    'JSONConverter',
    'ImageConverter',
    'FileFormatDetector',
    'SupportedFormat'
]