"""
File format detection utilities

This module provides functionality to detect file formats and determine
the appropriate converter for different file types.
"""

import mimetypes
from pathlib import Path
from typing import Optional, Dict, Any
from enum import Enum


class SupportedFormat(str, Enum):
    """Supported file formats for conversion"""
    GCODE = "gcode"
    SVG = "svg"
    DXF = "dxf"
    HPGL = "hpgl"
    JSON = "json"
    IMAGE = "image"
    UNKNOWN = "unknown"


class FileFormatDetector:
    """
    Detects file formats based on extension and content analysis
    """
    
    # File extension mappings
    EXTENSION_MAP = {
        '.gcode': SupportedFormat.GCODE,
        '.gc': SupportedFormat.GCODE,
        '.nc': SupportedFormat.GCODE,
        '.cnc': SupportedFormat.GCODE,
        '.tap': SupportedFormat.GCODE,
        '.svg': SupportedFormat.SVG,
        '.dxf': SupportedFormat.DXF,
        '.hpgl': SupportedFormat.HPGL,
        '.plt': SupportedFormat.HPGL,
        '.json': SupportedFormat.JSON,
        '.png': SupportedFormat.IMAGE,
        '.jpg': SupportedFormat.IMAGE,
        '.jpeg': SupportedFormat.IMAGE,
        '.bmp': SupportedFormat.IMAGE,
        '.gif': SupportedFormat.IMAGE,
        '.tiff': SupportedFormat.IMAGE,
        '.tif': SupportedFormat.IMAGE,
    }
    
    # MIME type mappings
    MIME_MAP = {
        'image/svg+xml': SupportedFormat.SVG,
        'application/json': SupportedFormat.JSON,
        'image/png': SupportedFormat.IMAGE,
        'image/jpeg': SupportedFormat.IMAGE,
        'image/bmp': SupportedFormat.IMAGE,
        'image/gif': SupportedFormat.IMAGE,
        'image/tiff': SupportedFormat.IMAGE,
        'text/plain': None,  # Could be G-code or other
    }
    
    # Content signatures for format detection
    CONTENT_SIGNATURES = {
        SupportedFormat.JSON: [
            b'{"', b'[\n', b'{\n'
        ],
        SupportedFormat.SVG: [
            b'<svg', b'<?xml', b'<SVG'
        ],
        SupportedFormat.DXF: [
            b'0\nSECTION', b'0\r\nSECTION', b'999\nDXF', b'AutoCAD'
        ],
        SupportedFormat.HPGL: [
            b'IN;', b'SP', b'PU', b'PD', b'PA', b'PR'
        ],
        SupportedFormat.IMAGE: [
            b'\x89PNG', b'\xff\xd8\xff', b'BM', b'GIF8'  # PNG, JPEG, BMP, GIF signatures
        ],
        SupportedFormat.GCODE: [
            b'G0', b'G1', b'G2', b'G3', b'M3', b'M5',
            b'g0', b'g1', b'g2', b'g3', b'm3', b'm5'
        ]
    }
    
    def __init__(self):
        """Initialize the file format detector"""
        # Initialize mimetypes
        mimetypes.init()
        
    def detect_format(self, filepath: Path) -> SupportedFormat:
        """
        Detect the format of a file
        
        Args:
            filepath: Path to the file to analyze
            
        Returns:
            Detected file format
        """
        if not filepath.exists():
            return SupportedFormat.UNKNOWN
            
        # First try extension-based detection
        format_by_ext = self._detect_by_extension(filepath)
        if format_by_ext != SupportedFormat.UNKNOWN:
            # Verify with content analysis if possible
            format_by_content = self._detect_by_content(filepath)
            if format_by_content == SupportedFormat.UNKNOWN or format_by_content == format_by_ext:
                return format_by_ext
            # If content disagrees with extension, trust content more
            return format_by_content
            
        # Try MIME type detection
        format_by_mime = self._detect_by_mime_type(filepath)
        if format_by_mime != SupportedFormat.UNKNOWN:
            return format_by_mime
            
        # Finally try content analysis
        return self._detect_by_content(filepath)
        
    def _detect_by_extension(self, filepath: Path) -> SupportedFormat:
        """Detect format by file extension"""
        extension = filepath.suffix.lower()
        return self.EXTENSION_MAP.get(extension, SupportedFormat.UNKNOWN)
        
    def _detect_by_mime_type(self, filepath: Path) -> SupportedFormat:
        """Detect format by MIME type"""
        mime_type, _ = mimetypes.guess_type(str(filepath))
        if mime_type:
            return self.MIME_MAP.get(mime_type, SupportedFormat.UNKNOWN)
        return SupportedFormat.UNKNOWN
        
    def _detect_by_content(self, filepath: Path) -> SupportedFormat:
        """Detect format by analyzing file content"""
        try:
            # Read first 1KB of file for analysis
            with open(filepath, 'rb') as f:
                content = f.read(1024)
                
            # Check against content signatures
            for format_type, signatures in self.CONTENT_SIGNATURES.items():
                for signature in signatures:
                    if signature in content:
                        return format_type
                        
        except Exception:
            # If we can't read the file, return unknown
            pass
            
        return SupportedFormat.UNKNOWN
        
    def get_converter_class(self, file_format: SupportedFormat) -> Optional[str]:
        """
        Get the appropriate converter class name for a format
        
        Args:
            file_format: Detected file format
            
        Returns:
            Converter class name or None if not supported
        """
        converter_map = {
            SupportedFormat.GCODE: 'GCodeLoader',
            SupportedFormat.SVG: 'SVGConverter',
            SupportedFormat.DXF: 'DXFConverter',
            SupportedFormat.HPGL: 'HPGLConverter',
            SupportedFormat.JSON: 'JSONConverter',
            SupportedFormat.IMAGE: 'ImageConverter'
        }
        
        return converter_map.get(file_format)
        
    def is_supported(self, filepath: Path) -> bool:
        """
        Check if a file format is supported
        
        Args:
            filepath: Path to check
            
        Returns:
            True if format is supported, False otherwise
        """
        detected_format = self.detect_format(filepath)
        return detected_format != SupportedFormat.UNKNOWN
        
    def get_file_info(self, filepath: Path) -> Dict[str, Any]:
        """
        Get comprehensive information about a file
        
        Args:
            filepath: Path to analyze
            
        Returns:
            Dictionary with file information
        """
        if not filepath.exists():
            return {
                'exists': False,
                'format': SupportedFormat.UNKNOWN,
                'supported': False
            }
            
        detected_format = self.detect_format(filepath)
        stat = filepath.stat()
        
        return {
            'exists': True,
            'format': detected_format,
            'supported': self.is_supported(filepath),
            'converter_class': self.get_converter_class(detected_format),
            'size_bytes': stat.st_size,
            'extension': filepath.suffix.lower(),
            'mime_type': mimetypes.guess_type(str(filepath))[0],
            'filename': filepath.name,
            'stem': filepath.stem
        }