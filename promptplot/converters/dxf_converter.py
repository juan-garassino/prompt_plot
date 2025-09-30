"""
DXF to G-code conversion utilities

This module provides functionality for converting DXF (Drawing Exchange Format)
files to G-code for pen plotting, supporting basic CAD drawing elements.
"""

import re
from pathlib import Path
from typing import List, Dict, Optional, Union, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import math

from ..core.models import GCodeCommand, GCodeProgram
from ..core.exceptions import PromptPlotException


class DXFEntityType(str, Enum):
    """DXF entity types supported"""
    LINE = "LINE"
    CIRCLE = "CIRCLE"
    ARC = "ARC"
    POLYLINE = "POLYLINE"
    LWPOLYLINE = "LWPOLYLINE"
    SPLINE = "SPLINE"
    POINT = "POINT"
    TEXT = "TEXT"


@dataclass
class DXFEntity:
    """Represents a DXF entity"""
    entity_type: DXFEntityType
    layer: str = "0"
    color: int = 7  # Default white
    coordinates: List[Tuple[float, float]] = None
    properties: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.coordinates is None:
            self.coordinates = []
        if self.properties is None:
            self.properties = {}


class DXFParseError(PromptPlotException):
    """Exception raised when DXF parsing fails"""
    pass


class DXFConverter:
    """
    Converts DXF files to G-code for pen plotting
    """
    
    def __init__(self, 
                 resolution: float = 0.1,
                 feed_rate: int = 1000,
                 pen_up_command: str = "M5",
                 pen_down_command: str = "M3"):
        """
        Initialize DXF converter
        
        Args:
            resolution: Resolution for curve approximation (mm)
            feed_rate: Default feed rate for movements
            pen_up_command: G-code command for pen up
            pen_down_command: G-code command for pen down
        """
        self.resolution = resolution
        self.feed_rate = feed_rate
        self.pen_up_command = pen_up_command
        self.pen_down_command = pen_down_command
        
    def convert_file(self, filepath: Union[str, Path]) -> GCodeProgram:
        """
        Convert a DXF file to G-code
        
        Args:
            filepath: Path to DXF file
            
        Returns:
            GCodeProgram object
            
        Raises:
            DXFParseError: If DXF parsing fails
            FileNotFoundError: If file doesn't exist
        """
        filepath = Path(filepath)
        
        if not filepath.exists():
            raise FileNotFoundError(f"DXF file not found: {filepath}")
            
        # Parse DXF file
        entities = self._parse_dxf_file(filepath)
        
        # Convert entities to G-code commands
        commands = self._entities_to_gcode(entities)
        
        # Create program with metadata
        metadata = {
            'source_file': filepath.name,
            'entity_count': len(entities),
            'resolution': self.resolution,
            'feed_rate': self.feed_rate,
            'entities_by_type': self._count_entities_by_type(entities)
        }
        
        return GCodeProgram(commands=commands, metadata=metadata)
        
    def _parse_dxf_file(self, filepath: Path) -> List[DXFEntity]:
        """Parse DXF file and extract entities"""
        entities = []
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            # Try with different encoding
            with open(filepath, 'r', encoding='latin-1') as f:
                lines = f.readlines()
                
        # Clean lines
        lines = [line.strip() for line in lines]
        
        # Find ENTITIES section
        entities_start = None
        entities_end = None
        
        for i, line in enumerate(lines):
            if line == "ENTITIES":
                entities_start = i
            elif line == "ENDSEC" and entities_start is not None:
                entities_end = i
                break
                
        if entities_start is None:
            raise DXFParseError("No ENTITIES section found in DXF file")
            
        # Parse entities
        entity_lines = lines[entities_start:entities_end] if entities_end else lines[entities_start:]
        entities = self._parse_entities_section(entity_lines)
        
        return entities
        
    def _parse_entities_section(self, lines: List[str]) -> List[DXFEntity]:
        """Parse the ENTITIES section of a DXF file"""
        entities = []
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            # Look for entity start
            if line == "0" and i + 1 < len(lines):
                entity_type = lines[i + 1]
                
                if entity_type in [e.value for e in DXFEntityType]:
                    entity = self._parse_entity(lines, i, DXFEntityType(entity_type))
                    if entity:
                        entities.append(entity)
                        
            i += 1
            
        return entities
        
    def _parse_entity(self, lines: List[str], start_idx: int, entity_type: DXFEntityType) -> Optional[DXFEntity]:
        """Parse a single DXF entity"""
        entity = DXFEntity(entity_type=entity_type)
        i = start_idx + 2  # Skip "0" and entity type
        
        # Parse entity data until next entity or end
        while i < len(lines) - 1:
            code = lines[i]
            value = lines[i + 1] if i + 1 < len(lines) else ""
            
            # Stop at next entity
            if code == "0":
                break
                
            # Parse common properties
            if code == "8":  # Layer
                entity.layer = value
            elif code == "62":  # Color
                try:
                    entity.color = int(value)
                except ValueError:
                    pass
                    
            # Parse entity-specific data
            elif entity_type == DXFEntityType.LINE:
                self._parse_line_data(entity, code, value)
            elif entity_type == DXFEntityType.CIRCLE:
                self._parse_circle_data(entity, code, value)
            elif entity_type == DXFEntityType.ARC:
                self._parse_arc_data(entity, code, value)
            elif entity_type in [DXFEntityType.POLYLINE, DXFEntityType.LWPOLYLINE]:
                self._parse_polyline_data(entity, code, value)
                
            i += 2
            
        return entity if self._is_valid_entity(entity) else None
        
    def _parse_line_data(self, entity: DXFEntity, code: str, value: str):
        """Parse LINE entity data"""
        try:
            if code == "10":  # Start X
                entity.properties["x1"] = float(value)
            elif code == "20":  # Start Y
                entity.properties["y1"] = float(value)
            elif code == "11":  # End X
                entity.properties["x2"] = float(value)
            elif code == "21":  # End Y
                entity.properties["y2"] = float(value)
        except ValueError:
            pass
            
    def _parse_circle_data(self, entity: DXFEntity, code: str, value: str):
        """Parse CIRCLE entity data"""
        try:
            if code == "10":  # Center X
                entity.properties["cx"] = float(value)
            elif code == "20":  # Center Y
                entity.properties["cy"] = float(value)
            elif code == "40":  # Radius
                entity.properties["radius"] = float(value)
        except ValueError:
            pass
            
    def _parse_arc_data(self, entity: DXFEntity, code: str, value: str):
        """Parse ARC entity data"""
        try:
            if code == "10":  # Center X
                entity.properties["cx"] = float(value)
            elif code == "20":  # Center Y
                entity.properties["cy"] = float(value)
            elif code == "40":  # Radius
                entity.properties["radius"] = float(value)
            elif code == "50":  # Start angle
                entity.properties["start_angle"] = float(value)
            elif code == "51":  # End angle
                entity.properties["end_angle"] = float(value)
        except ValueError:
            pass
            
    def _parse_polyline_data(self, entity: DXFEntity, code: str, value: str):
        """Parse POLYLINE/LWPOLYLINE entity data"""
        try:
            if code == "10":  # X coordinate
                if "vertices" not in entity.properties:
                    entity.properties["vertices"] = []
                entity.properties["vertices"].append([float(value), None])
            elif code == "20":  # Y coordinate
                if "vertices" in entity.properties and entity.properties["vertices"]:
                    entity.properties["vertices"][-1][1] = float(value)
        except ValueError:
            pass
            
    def _is_valid_entity(self, entity: DXFEntity) -> bool:
        """Check if entity has valid data for conversion"""
        if entity.entity_type == DXFEntityType.LINE:
            required = ["x1", "y1", "x2", "y2"]
            return all(prop in entity.properties for prop in required)
        elif entity.entity_type == DXFEntityType.CIRCLE:
            required = ["cx", "cy", "radius"]
            return all(prop in entity.properties for prop in required)
        elif entity.entity_type == DXFEntityType.ARC:
            required = ["cx", "cy", "radius", "start_angle", "end_angle"]
            return all(prop in entity.properties for prop in required)
        elif entity.entity_type in [DXFEntityType.POLYLINE, DXFEntityType.LWPOLYLINE]:
            vertices = entity.properties.get("vertices", [])
            return len(vertices) >= 2 and all(len(v) == 2 and v[1] is not None for v in vertices)
            
        return False
        
    def _entities_to_gcode(self, entities: List[DXFEntity]) -> List[GCodeCommand]:
        """Convert DXF entities to G-code commands"""
        commands = []
        
        # Start with pen up and move to origin
        commands.append(GCodeCommand(command=self.pen_up_command))
        commands.append(GCodeCommand(command="G0", x=0.0, y=0.0))
        
        pen_is_down = False
        
        for entity in entities:
            entity_commands = self._convert_entity_to_gcode(entity)
            
            for cmd_dict in entity_commands:
                if cmd_dict['type'] == 'move':
                    # Pen up, move, pen down
                    if pen_is_down:
                        commands.append(GCodeCommand(command=self.pen_up_command))
                        pen_is_down = False
                        
                    commands.append(GCodeCommand(
                        command="G0", 
                        x=cmd_dict['x'], 
                        y=cmd_dict['y']
                    ))
                    
                elif cmd_dict['type'] == 'line':
                    # Ensure pen is down for drawing
                    if not pen_is_down:
                        commands.append(GCodeCommand(command=self.pen_down_command))
                        pen_is_down = True
                        
                    commands.append(GCodeCommand(
                        command="G1", 
                        x=cmd_dict['x'], 
                        y=cmd_dict['y'], 
                        f=self.feed_rate
                    ))
                    
        # End with pen up
        if pen_is_down:
            commands.append(GCodeCommand(command=self.pen_up_command))
            
        # Add completion command
        commands.append(GCodeCommand(command="COMPLETE"))
        
        return commands
        
    def _convert_entity_to_gcode(self, entity: DXFEntity) -> List[Dict[str, Any]]:
        """Convert a single DXF entity to G-code command dictionaries"""
        if entity.entity_type == DXFEntityType.LINE:
            return self._convert_line_entity(entity)
        elif entity.entity_type == DXFEntityType.CIRCLE:
            return self._convert_circle_entity(entity)
        elif entity.entity_type == DXFEntityType.ARC:
            return self._convert_arc_entity(entity)
        elif entity.entity_type in [DXFEntityType.POLYLINE, DXFEntityType.LWPOLYLINE]:
            return self._convert_polyline_entity(entity)
            
        return []
        
    def _convert_line_entity(self, entity: DXFEntity) -> List[Dict[str, Any]]:
        """Convert LINE entity to G-code commands"""
        props = entity.properties
        return [
            {'type': 'move', 'x': props['x1'], 'y': props['y1']},
            {'type': 'line', 'x': props['x2'], 'y': props['y2']}
        ]
        
    def _convert_circle_entity(self, entity: DXFEntity) -> List[Dict[str, Any]]:
        """Convert CIRCLE entity to G-code commands"""
        props = entity.properties
        cx, cy, radius = props['cx'], props['cy'], props['radius']
        
        # Approximate circle with line segments
        circumference = 2 * math.pi * radius
        num_segments = max(8, int(circumference / self.resolution))
        
        commands = []
        angle_step = 2 * math.pi / num_segments
        
        # Start point
        start_x = cx + radius
        start_y = cy
        commands.append({'type': 'move', 'x': start_x, 'y': start_y})
        
        # Generate segments
        for i in range(1, num_segments + 1):
            angle = i * angle_step
            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle)
            commands.append({'type': 'line', 'x': x, 'y': y})
            
        return commands
        
    def _convert_arc_entity(self, entity: DXFEntity) -> List[Dict[str, Any]]:
        """Convert ARC entity to G-code commands"""
        props = entity.properties
        cx, cy, radius = props['cx'], props['cy'], props['radius']
        start_angle = math.radians(props['start_angle'])
        end_angle = math.radians(props['end_angle'])
        
        # Handle angle wrapping
        if end_angle < start_angle:
            end_angle += 2 * math.pi
            
        arc_length = radius * (end_angle - start_angle)
        num_segments = max(2, int(arc_length / self.resolution))
        
        commands = []
        angle_step = (end_angle - start_angle) / num_segments
        
        # Start point
        start_x = cx + radius * math.cos(start_angle)
        start_y = cy + radius * math.sin(start_angle)
        commands.append({'type': 'move', 'x': start_x, 'y': start_y})
        
        # Generate segments
        for i in range(1, num_segments + 1):
            angle = start_angle + i * angle_step
            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle)
            commands.append({'type': 'line', 'x': x, 'y': y})
            
        return commands
        
    def _convert_polyline_entity(self, entity: DXFEntity) -> List[Dict[str, Any]]:
        """Convert POLYLINE/LWPOLYLINE entity to G-code commands"""
        vertices = entity.properties.get("vertices", [])
        if len(vertices) < 2:
            return []
            
        commands = []
        
        # Move to first vertex
        first_vertex = vertices[0]
        commands.append({'type': 'move', 'x': first_vertex[0], 'y': first_vertex[1]})
        
        # Draw lines to subsequent vertices
        for vertex in vertices[1:]:
            commands.append({'type': 'line', 'x': vertex[0], 'y': vertex[1]})
            
        return commands
        
    def _count_entities_by_type(self, entities: List[DXFEntity]) -> Dict[str, int]:
        """Count entities by type"""
        counts = {}
        for entity in entities:
            entity_type = entity.entity_type.value
            counts[entity_type] = counts.get(entity_type, 0) + 1
        return counts