"""
Image to G-code conversion utilities

This module provides basic functionality for converting simple bitmap images
to G-code paths using edge detection and contour tracing.
"""

from pathlib import Path
from typing import List, Dict, Optional, Union, Tuple, Any
import math

from ..core.models import GCodeCommand, GCodeProgram
from ..core.exceptions import PromptPlotException


class ImageConversionError(PromptPlotException):
    """Exception raised when image conversion fails"""
    pass


class ImageConverter:
    """
    Converts simple bitmap images to G-code for pen plotting
    
    Note: This is a basic implementation for simple black and white images.
    For complex images, consider using specialized software like Inkscape.
    """
    
    def __init__(self, 
                 resolution: float = 1.0,
                 feed_rate: int = 1000,
                 pen_up_command: str = "M5",
                 pen_down_command: str = "M3",
                 threshold: int = 128,
                 scale_factor: float = 0.1):
        """
        Initialize image converter
        
        Args:
            resolution: Resolution for path approximation (mm)
            feed_rate: Default feed rate for movements
            pen_up_command: G-code command for pen up
            pen_down_command: G-code command for pen down
            threshold: Threshold for black/white conversion (0-255)
            scale_factor: Scale factor from pixels to mm
        """
        self.resolution = resolution
        self.feed_rate = feed_rate
        self.pen_up_command = pen_up_command
        self.pen_down_command = pen_down_command
        self.threshold = threshold
        self.scale_factor = scale_factor
        
        # Check for PIL availability
        try:
            from PIL import Image
            self.pil_available = True
        except ImportError:
            self.pil_available = False
            
    def convert_file(self, filepath: Union[str, Path]) -> GCodeProgram:
        """
        Convert an image file to G-code
        
        Args:
            filepath: Path to image file
            
        Returns:
            GCodeProgram object
            
        Raises:
            ImageConversionError: If image conversion fails
            FileNotFoundError: If file doesn't exist
        """
        if not self.pil_available:
            raise ImageConversionError(
                "PIL (Pillow) is required for image conversion. "
                "Install with: pip install Pillow"
            )
            
        filepath = Path(filepath)
        
        if not filepath.exists():
            raise FileNotFoundError(f"Image file not found: {filepath}")
            
        try:
            from PIL import Image
            
            # Load and process image
            image = Image.open(filepath)
            contours = self._extract_contours(image)
            
            # Convert contours to G-code
            commands = self._contours_to_gcode(contours)
            
            # Create program with metadata
            metadata = {
                'source_file': filepath.name,
                'image_size': image.size,
                'contour_count': len(contours),
                'threshold': self.threshold,
                'scale_factor': self.scale_factor,
                'resolution': self.resolution
            }
            
            return GCodeProgram(commands=commands, metadata=metadata)
            
        except Exception as e:
            raise ImageConversionError(f"Failed to convert image: {e}")
            
    def _extract_contours(self, image) -> List[List[Tuple[float, float]]]:
        """Extract contours from image using simple edge detection"""
        from PIL import Image
        
        # Convert to grayscale
        if image.mode != 'L':
            image = image.convert('L')
            
        # Convert to binary
        width, height = image.size
        pixels = list(image.getdata())
        
        # Create binary array
        binary = []
        for y in range(height):
            row = []
            for x in range(width):
                pixel_value = pixels[y * width + x]
                row.append(1 if pixel_value < self.threshold else 0)
            binary.append(row)
            
        # Find contours using simple edge detection
        contours = []
        visited = [[False] * width for _ in range(height)]
        
        for y in range(height):
            for x in range(width):
                if binary[y][x] == 1 and not visited[y][x]:
                    contour = self._trace_contour(binary, visited, x, y, width, height)
                    if len(contour) > 2:  # Only keep contours with multiple points
                        # Convert to real coordinates
                        real_contour = [
                            (px * self.scale_factor, py * self.scale_factor) 
                            for px, py in contour
                        ]
                        contours.append(real_contour)
                        
        return contours
        
    def _trace_contour(self, binary: List[List[int]], visited: List[List[bool]], 
                      start_x: int, start_y: int, width: int, height: int) -> List[Tuple[int, int]]:
        """Trace a contour starting from a given point"""
        contour = []
        
        # Simple flood fill to find connected components
        stack = [(start_x, start_y)]
        points = []
        
        while stack:
            x, y = stack.pop()
            
            if (x < 0 or x >= width or y < 0 or y >= height or 
                visited[y][x] or binary[y][x] == 0):
                continue
                
            visited[y][x] = True
            points.append((x, y))
            
            # Add neighbors
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                stack.append((x + dx, y + dy))
                
        # Sort points to create a reasonable path
        if points:
            contour = self._sort_points_for_path(points)
            
        return contour
        
    def _sort_points_for_path(self, points: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """Sort points to create a reasonable drawing path"""
        if len(points) <= 1:
            return points
            
        # Simple nearest neighbor approach
        path = [points[0]]
        remaining = points[1:]
        
        while remaining:
            current = path[-1]
            
            # Find nearest point
            nearest_idx = 0
            min_dist = float('inf')
            
            for i, point in enumerate(remaining):
                dist = math.sqrt((point[0] - current[0])**2 + (point[1] - current[1])**2)
                if dist < min_dist:
                    min_dist = dist
                    nearest_idx = i
                    
            path.append(remaining.pop(nearest_idx))
            
        return path
        
    def _contours_to_gcode(self, contours: List[List[Tuple[float, float]]]) -> List[GCodeCommand]:
        """Convert contours to G-code commands"""
        commands = []
        
        # Start with pen up and move to origin
        commands.append(GCodeCommand(command=self.pen_up_command))
        commands.append(GCodeCommand(command="G0", x=0.0, y=0.0))
        
        for contour in contours:
            if len(contour) < 2:
                continue
                
            # Move to start of contour
            start_x, start_y = contour[0]
            commands.append(GCodeCommand(command="G0", x=start_x, y=start_y))
            
            # Pen down
            commands.append(GCodeCommand(command=self.pen_down_command))
            
            # Draw contour
            for x, y in contour[1:]:
                commands.append(GCodeCommand(
                    command="G1", 
                    x=x, 
                    y=y, 
                    f=self.feed_rate
                ))
                
            # Pen up
            commands.append(GCodeCommand(command=self.pen_up_command))
            
        # Add completion command
        commands.append(GCodeCommand(command="COMPLETE"))
        
        return commands
        
    def convert_simple_shapes(self, image_path: Union[str, Path]) -> GCodeProgram:
        """
        Convert simple geometric shapes in an image
        
        This method attempts to detect and convert simple shapes like
        rectangles and circles rather than tracing pixel contours.
        """
        if not self.pil_available:
            raise ImageConversionError("PIL (Pillow) is required for image conversion")
            
        try:
            from PIL import Image, ImageFilter
            
            image = Image.open(image_path)
            
            # Convert to grayscale and apply edge detection
            if image.mode != 'L':
                image = image.convert('L')
                
            # Simple edge detection
            edges = image.filter(ImageFilter.FIND_EDGES)
            
            # Extract contours from edges
            contours = self._extract_contours(edges)
            
            # Simplify contours to basic shapes
            simplified_contours = []
            for contour in contours:
                simplified = self._simplify_contour(contour)
                if simplified:
                    simplified_contours.append(simplified)
                    
            # Convert to G-code
            commands = self._contours_to_gcode(simplified_contours)
            
            metadata = {
                'source_file': Path(image_path).name,
                'conversion_method': 'simple_shapes',
                'contour_count': len(simplified_contours),
                'scale_factor': self.scale_factor
            }
            
            return GCodeProgram(commands=commands, metadata=metadata)
            
        except Exception as e:
            raise ImageConversionError(f"Failed to convert image shapes: {e}")
            
    def _simplify_contour(self, contour: List[Tuple[float, float]]) -> Optional[List[Tuple[float, float]]]:
        """Simplify a contour by reducing the number of points"""
        if len(contour) < 3:
            return None
            
        # Simple Douglas-Peucker-like algorithm
        simplified = [contour[0]]
        
        tolerance = self.resolution
        
        for i in range(1, len(contour) - 1):
            # Check if point is far enough from the line between previous and next
            prev_point = simplified[-1]
            curr_point = contour[i]
            
            # Simple distance check
            dist = math.sqrt(
                (curr_point[0] - prev_point[0])**2 + 
                (curr_point[1] - prev_point[1])**2
            )
            
            if dist > tolerance:
                simplified.append(curr_point)
                
        # Add last point
        simplified.append(contour[-1])
        
        return simplified if len(simplified) >= 3 else None
        
    def get_supported_formats(self) -> List[str]:
        """Get list of supported image formats"""
        if not self.pil_available:
            return []
            
        # Common formats supported by PIL
        return ['.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.tif']
        
    def estimate_conversion_time(self, image_path: Union[str, Path]) -> Optional[float]:
        """Estimate conversion time for an image"""
        if not self.pil_available:
            return None
            
        try:
            from PIL import Image
            
            image = Image.open(image_path)
            width, height = image.size
            
            # Rough estimate based on image size
            pixel_count = width * height
            
            # Assume processing time scales with pixel count
            estimated_seconds = pixel_count / 100000  # 100k pixels per second
            
            return max(1.0, estimated_seconds)  # Minimum 1 second
            
        except Exception:
            return None