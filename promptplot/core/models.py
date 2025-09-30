"""
Shared Pydantic models for PromptPlot v2.0

This module contains the core data models used throughout the system,
extracted from the existing boilerplate files and enhanced for v2.0 features.
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from enum import Enum


class DrawingStrategy(str, Enum):
    """Enumeration of available drawing strategies"""
    ORTHOGONAL = "orthogonal"
    NON_ORTHOGONAL = "non_orthogonal"
    AUTO = "auto"


class WorkflowResult(BaseModel):
    """Result of workflow execution"""
    success: bool
    prompt: str
    commands_count: int
    gcode: str
    timestamp: str
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    gcode_program: Optional['GCodeProgram'] = None


class ValidationResult(BaseModel):
    """Result of file validation"""
    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None


class GCodeCommand(BaseModel):
    """
    Model for a single G-code command
    
    Extracted from existing boilerplate files and enhanced with new fields
    for strategy type and visual context support as required by v2.0.
    """
    command: str
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None
    f: Optional[int] = None  # Feed rate
    s: Optional[int] = None  # Speed/Spindle speed
    p: Optional[int] = None  # Pause time
    comment: Optional[str] = None  # Comment for the command
    
    # New fields for v2.0 - strategy type and visual context support
    strategy_type: Optional[DrawingStrategy] = None
    visual_context_id: Optional[str] = None
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)

    @field_validator('command')
    @classmethod
    def validate_command(cls, v):
        """
        Validates that the command is a valid G-code command
        
        Extracted validation logic from existing implementations with
        enhanced error messages and support for COMPLETE command.
        """
        if not isinstance(v, str):
            raise ValueError(f"Command must be a string, got {type(v)}")
            
        v = v.upper().strip()
        
        # Allow COMPLETE as a special control command
        if v == "COMPLETE":
            return v
            
        # Standard G-code validation
        if not v.startswith(('G', 'M')):
            raise ValueError(f"Command must start with G or M, got {v}")
            
        # Enhanced validation with specific allowed commands
        # Extended list to support more G-code commands for file loading
        valid_commands = [
            'G0', 'G1', 'G2', 'G3', 'G4', 'G17', 'G18', 'G19', 'G20', 'G21', 
            'G28', 'G90', 'G91', 'G92', 'M3', 'M5', 'M17', 'M18', 'M30', 'COMPLETE'
        ]
        if v not in valid_commands:
            raise ValueError(f"Command must be one of {valid_commands}, got {v}")
            
        return v

    @field_validator('confidence_score')
    @classmethod
    def validate_confidence_score(cls, v):
        """Validate confidence score is between 0 and 1"""
        if v is not None and (v < 0.0 or v > 1.0):
            raise ValueError("Confidence score must be between 0.0 and 1.0")
        return v

    def to_gcode(self) -> str:
        """
        Convert to G-code string format
        
        Enhanced from existing implementations to handle the COMPLETE command
        and maintain backward compatibility.
        """
        if self.command == "COMPLETE":
            return "COMPLETE"
            
        parts = [self.command]
        
        # Build parameter string from model data
        for attr, value in self.model_dump().items():
            if (value is not None and 
                attr not in ['command', 'strategy_type', 'visual_context_id', 'confidence_score']):
                if isinstance(value, float):
                    parts.append(f"{attr.upper()}{value:.3f}")
                else:
                    parts.append(f"{attr.upper()}{value}")
                    
        return " ".join(parts)

    def is_movement_command(self) -> bool:
        """Check if this is a movement command (G0, G1, G2, G3)"""
        return self.command.startswith('G') and self.command in ['G0', 'G1', 'G2', 'G3']

    def is_pen_command(self) -> bool:
        """Check if this is a pen control command (M3, M5)"""
        return self.command in ['M3', 'M5']

    def is_pen_down(self) -> bool:
        """Check if this command puts the pen down"""
        return self.command == 'M3'

    def is_pen_up(self) -> bool:
        """Check if this command lifts the pen up"""
        return self.command == 'M5'


class GCodeProgram(BaseModel):
    """
    Model for a complete G-code program
    
    Enhanced from existing implementations with additional metadata
    and validation capabilities.
    """
    commands: List[GCodeCommand]
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

    @field_validator('commands')
    @classmethod
    def validate_commands_not_empty(cls, v):
        """Ensure the program has at least one command"""
        if not v:
            raise ValueError("G-code program must contain at least one command")
        return v

    def to_gcode(self) -> str:
        """
        Convert the entire program to G-code string format
        
        Enhanced to handle empty programs gracefully and maintain
        consistent formatting.
        """
        if not self.commands:
            return ""
        return "\n".join(cmd.to_gcode() for cmd in self.commands)

    def get_movement_commands(self) -> List[GCodeCommand]:
        """Get only the movement commands from the program"""
        return [cmd for cmd in self.commands if cmd.is_movement_command()]

    def get_pen_commands(self) -> List[GCodeCommand]:
        """Get only the pen control commands from the program"""
        return [cmd for cmd in self.commands if cmd.is_pen_command()]

    def get_drawing_commands(self) -> List[GCodeCommand]:
        """Get commands that actually draw (G1 with pen down context)"""
        drawing_commands = []
        pen_down = False
        
        for cmd in self.commands:
            if cmd.is_pen_down():
                pen_down = True
            elif cmd.is_pen_up():
                pen_down = False
            elif cmd.command == 'G1' and pen_down:
                drawing_commands.append(cmd)
                
        return drawing_commands

    def get_bounds(self) -> Optional[Dict[str, float]]:
        """
        Calculate the bounding box of all movement commands
        
        Returns:
            Dict with keys: min_x, max_x, min_y, max_y, min_z, max_z
            or None if no movement commands found
        """
        movement_commands = self.get_movement_commands()
        if not movement_commands:
            return None

        # Extract coordinates, filtering out None values
        x_coords = [cmd.x for cmd in movement_commands if cmd.x is not None]
        y_coords = [cmd.y for cmd in movement_commands if cmd.y is not None]
        z_coords = [cmd.z for cmd in movement_commands if cmd.z is not None]

        if not x_coords and not y_coords and not z_coords:
            return None

        bounds = {}
        if x_coords:
            bounds.update({"min_x": min(x_coords), "max_x": max(x_coords)})
        if y_coords:
            bounds.update({"min_y": min(y_coords), "max_y": max(y_coords)})
        if z_coords:
            bounds.update({"min_z": min(z_coords), "max_z": max(z_coords)})

        return bounds

    def count_by_command_type(self) -> Dict[str, int]:
        """Count commands by type"""
        counts = {}
        for cmd in self.commands:
            counts[cmd.command] = counts.get(cmd.command, 0) + 1
        return counts

    def has_strategy_type(self, strategy: DrawingStrategy) -> bool:
        """Check if any commands use the specified strategy"""
        return any(cmd.strategy_type == strategy for cmd in self.commands)

    def get_commands_by_strategy(self, strategy: DrawingStrategy) -> List[GCodeCommand]:
        """Get all commands that use the specified strategy"""
        return [cmd for cmd in self.commands if cmd.strategy_type == strategy]


class ValidationError(BaseModel):
    """
    Model for validation errors
    
    Used to provide structured error information when validation fails.
    """
    field: str
    message: str
    invalid_value: Optional[Any] = None
    
    def __str__(self) -> str:
        if self.invalid_value is not None:
            return f"{self.field}: {self.message} (got: {self.invalid_value})"
        return f"{self.field}: {self.message}"


class WorkflowResult(BaseModel):
    """
    Model for workflow execution results
    
    Provides a standardized format for workflow outputs across different
    workflow types.
    """
    success: bool
    prompt: str
    commands_count: int
    gcode: str
    program: Optional[GCodeProgram] = None
    step_count: Optional[int] = None
    timestamp: str
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for compatibility with existing code"""
        result = self.model_dump()
        if self.program:
            result["program"] = self.program.model_dump()
        return result