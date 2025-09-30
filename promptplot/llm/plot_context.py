"""
Plot Context Management System

This module implements a comprehensive system for managing plot state throughout
the drawing process, including plot history and progress tracking for LLM context,
plot state validation and error recovery mechanisms, and coordinate grid reference
system for precise positioning.

Requirements addressed:
- 4.4: Plot state management throughout drawing process
- 5.4: Coordinate grid reference system for precise positioning
"""

import asyncio
import json
import time
import logging
from typing import List, Dict, Any, Optional, Tuple, Union, Callable
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum
from collections import deque
import threading
from concurrent.futures import ThreadPoolExecutor

import matplotlib.pyplot as plt
import matplotlib.figure
import numpy as np

from ..vision.plot_analyzer import PlotAnalyzer, PlotState, DrawingProgress, GridInfo, PlotComparison
from ..plotter.visualizer import PlotterVisualizer, GridConfiguration, ProgressMarkerType
from ..core.models import GCodeCommand, GCodeProgram, DrawingStrategy


class PlotContextState(str, Enum):
    """States of plot context management"""
    INITIALIZING = "initializing"
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"
    COMPLETED = "completed"


class ValidationLevel(str, Enum):
    """Levels of plot state validation"""
    NONE = "none"
    BASIC = "basic"
    COMPREHENSIVE = "comprehensive"
    STRICT = "strict"


@dataclass
class PlotSnapshot:
    """Snapshot of plot state at a specific point in time"""
    plot_state: PlotState
    command_index: int
    timestamp: float
    drawing_progress: Optional[DrawingProgress] = None
    validation_result: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlotContextConfig:
    """Configuration for plot context management"""
    max_history_size: int = 100
    snapshot_interval: int = 5  # Take snapshot every N commands
    validation_level: ValidationLevel = ValidationLevel.BASIC
    enable_auto_recovery: bool = True
    coordinate_precision: int = 3
    grid_snap_tolerance: float = 0.5
    progress_tracking_enabled: bool = True
    async_processing: bool = True
    backup_enabled: bool = True
    backup_interval: int = 20  # Backup every N snapshots


@dataclass
class RecoveryAction:
    """Action to take for plot state recovery"""
    action_type: str  # "rollback", "correct", "skip", "manual"
    target_command_index: Optional[int] = None
    correction_commands: List[GCodeCommand] = field(default_factory=list)
    description: str = ""
    confidence: float = 0.0


@dataclass
class ValidationResult:
    """Result of plot state validation"""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    recovery_actions: List[RecoveryAction] = field(default_factory=list)
    validation_score: float = 1.0  # 0.0 to 1.0


class PlotContextManager:
    """
    Comprehensive plot context management system
    
    Manages plot state throughout the drawing process with features including:
    - Plot history and progress tracking for LLM context
    - Plot state validation and error recovery mechanisms  
    - Coordinate grid reference system for precise positioning
    - Automatic backup and recovery capabilities
    - Asynchronous processing for performance
    """
    
    def __init__(
        self,
        config: Optional[PlotContextConfig] = None,
        plot_analyzer: Optional[PlotAnalyzer] = None,
        visualizer: Optional[PlotterVisualizer] = None
    ):
        """
        Initialize plot context manager
        
        Args:
            config: Configuration for context management
            plot_analyzer: Plot analyzer for state analysis
            visualizer: Visualizer for plot rendering and grid management
        """
        self.config = config or PlotContextConfig()
        self.plot_analyzer = plot_analyzer or PlotAnalyzer(
            coordinate_precision=self.config.coordinate_precision,
            enable_caching=True
        )
        self.visualizer = visualizer or PlotterVisualizer(
            enable_plot_analysis=True,
            grid_config=GridConfiguration()
        )
        
        # State management
        self.state = PlotContextState.INITIALIZING
        self.current_figure: Optional[matplotlib.figure.Figure] = None
        self.current_plot_state: Optional[PlotState] = None
        
        # History management
        self.plot_history: deque = deque(maxlen=self.config.max_history_size)
        self.command_history: List[GCodeCommand] = []
        self.snapshot_history: List[PlotSnapshot] = []
        
        # Grid and coordinate system
        self.grid_info: Optional[GridInfo] = None
        self.coordinate_bounds: Optional[Dict[str, float]] = None
        
        # Progress tracking
        self.drawing_progress: Optional[DrawingProgress] = None
        self.progress_callbacks: List[Callable] = []
        
        # Error handling and recovery
        self.validation_errors: List[Dict[str, Any]] = []
        self.recovery_stack: List[PlotSnapshot] = []
        
        # Async processing
        self.executor = ThreadPoolExecutor(max_workers=2) if self.config.async_processing else None
        self._processing_lock = threading.Lock()
        
        # Backup system
        self.backup_directory: Optional[Path] = None
        self.last_backup_time: float = 0
        
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
    
    async def initialize(
        self,
        figure: Optional[matplotlib.figure.Figure] = None,
        coordinate_bounds: Optional[Tuple[float, float, float, float]] = None,
        grid_enabled: bool = True
    ) -> bool:
        """
        Initialize plot context management
        
        Args:
            figure: Optional matplotlib figure to use
            coordinate_bounds: Optional coordinate bounds (x_min, x_max, y_min, y_max)
            grid_enabled: Whether to enable grid system
            
        Returns:
            True if initialization successful
        """
        try:
            self.logger.info("Initializing plot context manager")
            
            # Set up coordinate system
            if coordinate_bounds:
                self.coordinate_bounds = {
                    "x_min": coordinate_bounds[0],
                    "x_max": coordinate_bounds[1],
                    "y_min": coordinate_bounds[2],
                    "y_max": coordinate_bounds[3]
                }
            
            # Initialize figure
            if figure is not None:
                self.current_figure = figure
            else:
                self.current_figure = self.visualizer.create_figure()
            
            # Set up grid system
            if grid_enabled:
                await self._setup_grid_system()
            
            # Capture initial plot state
            initial_state = await self._capture_plot_state()
            if initial_state:
                self.current_plot_state = initial_state
                await self._add_to_history(initial_state)
            
            # Set up backup system
            if self.config.backup_enabled:
                await self._setup_backup_system()
            
            self.state = PlotContextState.ACTIVE
            self.logger.info("Plot context manager initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize plot context manager: {str(e)}")
            self.state = PlotContextState.ERROR
            return False
    
    async def _setup_grid_system(self) -> None:
        """Set up coordinate grid reference system"""
        try:
            # Configure grid in visualizer
            if self.coordinate_bounds:
                bounds = (
                    self.coordinate_bounds["x_min"],
                    self.coordinate_bounds["x_max"],
                    self.coordinate_bounds["y_min"],
                    self.coordinate_bounds["y_max"]
                )
                
                self.visualizer.setup_grid(
                    self.current_figure,
                    bounds=bounds,
                    grid_spacing=5.0
                )
            
            # Extract grid information
            self.grid_info = self.visualizer.get_grid_info()
            
            if self.grid_info:
                self.logger.info(f"Grid system initialized: {self.grid_info.x_step}x{self.grid_info.y_step}")
            
        except Exception as e:
            self.logger.warning(f"Failed to setup grid system: {str(e)}")
    
    async def _setup_backup_system(self) -> None:
        """Set up automatic backup system"""
        try:
            self.backup_directory = Path("results/backups/plot_context")
            self.backup_directory.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"Backup system initialized: {self.backup_directory}")
        except Exception as e:
            self.logger.warning(f"Failed to setup backup system: {str(e)}")
    
    async def add_command(self, command: GCodeCommand) -> bool:
        """
        Add G-code command and update plot context
        
        Args:
            command: G-code command to add
            
        Returns:
            True if command added successfully
        """
        if self.state != PlotContextState.ACTIVE:
            self.logger.warning(f"Cannot add command in state: {self.state}")
            return False
        
        try:
            # Add to command history
            self.command_history.append(command)
            command_index = len(self.command_history) - 1
            
            # Execute command in visualizer
            if self.current_figure:
                success = await self.visualizer.execute_command(command, self.current_figure)
                if not success:
                    self.logger.warning(f"Command execution failed: {command.to_gcode()}")
            
            # Update plot state
            await self._update_plot_state(command_index)
            
            # Take snapshot if needed
            if command_index % self.config.snapshot_interval == 0:
                await self._take_snapshot(command_index)
            
            # Validate state if enabled
            if self.config.validation_level != ValidationLevel.NONE:
                validation_result = await self._validate_current_state()
                if not validation_result.is_valid:
                    await self._handle_validation_error(validation_result, command_index)
            
            # Update progress tracking
            if self.config.progress_tracking_enabled:
                await self._update_progress_tracking()
            
            # Backup if needed
            if self.config.backup_enabled:
                await self._check_backup_needed()
            
            # Notify progress callbacks
            await self._notify_progress_callbacks()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to add command: {str(e)}")
            await self._handle_error(e, command)
            return False
    
    async def _capture_plot_state(self) -> Optional[PlotState]:
        """Capture current plot state"""
        if not self.current_figure:
            return None
        
        try:
            if self.config.async_processing and self.executor:
                # Async processing
                loop = asyncio.get_event_loop()
                plot_state = await loop.run_in_executor(
                    self.executor,
                    self.plot_analyzer.capture_plot_state,
                    self.current_figure,
                    True  # include_grid_analysis
                )
            else:
                # Sync processing
                plot_state = self.plot_analyzer.capture_plot_state(
                    self.current_figure,
                    include_grid_analysis=True
                )
            
            return plot_state
            
        except Exception as e:
            self.logger.error(f"Failed to capture plot state: {str(e)}")
            return None
    
    async def _update_plot_state(self, command_index: int) -> None:
        """Update current plot state after command execution"""
        new_state = await self._capture_plot_state()
        if new_state:
            self.current_plot_state = new_state
            await self._add_to_history(new_state)
    
    async def _add_to_history(self, plot_state: PlotState) -> None:
        """Add plot state to history"""
        with self._processing_lock:
            self.plot_history.append(plot_state)
    
    async def _take_snapshot(self, command_index: int) -> None:
        """Take snapshot of current plot context"""
        if not self.current_plot_state:
            return
        
        try:
            # Analyze drawing progress
            drawing_progress = None
            if self.command_history:
                target_program = GCodeProgram(commands=self.command_history)
                drawing_progress = self.plot_analyzer.analyze_drawing_progress(
                    self.current_plot_state,
                    target_program
                )
            
            # Create snapshot
            snapshot = PlotSnapshot(
                plot_state=self.current_plot_state,
                command_index=command_index,
                timestamp=time.time(),
                drawing_progress=drawing_progress,
                metadata={
                    "total_commands": len(self.command_history),
                    "grid_info": self.grid_info.model_dump() if self.grid_info else None,
                    "coordinate_bounds": self.coordinate_bounds
                }
            )
            
            # Validate snapshot if enabled
            if self.config.validation_level != ValidationLevel.NONE:
                validation_result = await self._validate_snapshot(snapshot)
                snapshot.validation_result = validation_result.model_dump() if hasattr(validation_result, 'model_dump') else validation_result.__dict__
            
            self.snapshot_history.append(snapshot)
            
            # Add to recovery stack for error recovery
            self.recovery_stack.append(snapshot)
            if len(self.recovery_stack) > 10:  # Keep last 10 snapshots
                self.recovery_stack.pop(0)
            
            self.logger.debug(f"Snapshot taken at command {command_index}")
            
        except Exception as e:
            self.logger.error(f"Failed to take snapshot: {str(e)}")
    
    async def _validate_current_state(self) -> ValidationResult:
        """Validate current plot state"""
        if not self.current_plot_state:
            return ValidationResult(
                is_valid=False,
                errors=["No current plot state available"],
                validation_score=0.0
            )
        
        try:
            errors = []
            warnings = []
            suggestions = []
            recovery_actions = []
            score = 1.0
            
            # Basic validation
            if self.config.validation_level in [ValidationLevel.BASIC, ValidationLevel.COMPREHENSIVE, ValidationLevel.STRICT]:
                # Check for plot elements
                if not self.current_plot_state.elements:
                    warnings.append("No plot elements detected")
                    score -= 0.1
                
                # Check coordinate bounds
                if self.coordinate_bounds and self.current_plot_state.bounds:
                    bounds = self.current_plot_state.bounds
                    if (bounds.get("data_x_min", 0) < self.coordinate_bounds["x_min"] or
                        bounds.get("data_x_max", 0) > self.coordinate_bounds["x_max"] or
                        bounds.get("data_y_min", 0) < self.coordinate_bounds["y_min"] or
                        bounds.get("data_y_max", 0) > self.coordinate_bounds["y_max"]):
                        warnings.append("Drawing extends beyond coordinate bounds")
                        score -= 0.2
            
            # Comprehensive validation
            if self.config.validation_level in [ValidationLevel.COMPREHENSIVE, ValidationLevel.STRICT]:
                # Check grid alignment
                if self.grid_info:
                    misaligned_elements = await self._check_grid_alignment()
                    if misaligned_elements > 0:
                        warnings.append(f"{misaligned_elements} elements not aligned to grid")
                        score -= 0.1
                        suggestions.append("Consider using grid snapping for better alignment")
                
                # Check drawing continuity
                continuity_issues = await self._check_drawing_continuity()
                if continuity_issues:
                    warnings.extend(continuity_issues)
                    score -= 0.1 * len(continuity_issues)
            
            # Strict validation
            if self.config.validation_level == ValidationLevel.STRICT:
                # Check for overlapping elements
                overlaps = await self._check_element_overlaps()
                if overlaps > 0:
                    warnings.append(f"{overlaps} overlapping elements detected")
                    score -= 0.05 * overlaps
                
                # Check drawing efficiency
                efficiency_score = await self._calculate_drawing_efficiency()
                if efficiency_score < 0.7:
                    suggestions.append("Drawing path could be optimized for efficiency")
                    score -= 0.1
            
            # Generate recovery actions if needed
            if score < 0.8 and self.config.enable_auto_recovery:
                recovery_actions = await self._generate_recovery_actions(errors, warnings)
            
            return ValidationResult(
                is_valid=len(errors) == 0,
                errors=errors,
                warnings=warnings,
                suggestions=suggestions,
                recovery_actions=recovery_actions,
                validation_score=max(0.0, score)
            )
            
        except Exception as e:
            self.logger.error(f"Validation failed: {str(e)}")
            return ValidationResult(
                is_valid=False,
                errors=[f"Validation error: {str(e)}"],
                validation_score=0.0
            )
    
    async def _validate_snapshot(self, snapshot: PlotSnapshot) -> ValidationResult:
        """Validate a specific snapshot"""
        # Store current state temporarily
        temp_state = self.current_plot_state
        
        # Set snapshot state for validation
        self.current_plot_state = snapshot.plot_state
        
        try:
            result = await self._validate_current_state()
            return result
        finally:
            # Restore current state
            self.current_plot_state = temp_state
    
    async def _check_grid_alignment(self) -> int:
        """Check how many elements are not aligned to grid"""
        if not self.grid_info or not self.current_plot_state:
            return 0
        
        misaligned_count = 0
        tolerance = self.config.grid_snap_tolerance
        
        for element in self.current_plot_state.elements:
            for coord in element.coordinates:
                grid_coord = self.plot_analyzer.get_grid_coordinates(self.current_plot_state, coord)
                if grid_coord:
                    # Check if coordinate is close to grid point
                    expected_x = grid_coord[0] * self.grid_info.x_step + self.grid_info.origin[0]
                    expected_y = grid_coord[1] * self.grid_info.y_step + self.grid_info.origin[1]
                    
                    if (abs(coord[0] - expected_x) > tolerance or 
                        abs(coord[1] - expected_y) > tolerance):
                        misaligned_count += 1
        
        return misaligned_count
    
    async def _check_drawing_continuity(self) -> List[str]:
        """Check for drawing continuity issues"""
        issues = []
        
        if not self.current_plot_state or not self.command_history:
            return issues
        
        # Check for gaps in drawing
        drawing_commands = [cmd for cmd in self.command_history if cmd.is_movement_command()]
        
        pen_down = False
        last_position = None
        
        for cmd in drawing_commands:
            if cmd.is_pen_down():
                pen_down = True
            elif cmd.is_pen_up():
                pen_down = False
            elif cmd.command == 'G1' and pen_down:
                current_position = (cmd.x, cmd.y)
                
                if last_position and pen_down:
                    # Check for large gaps
                    distance = np.sqrt(
                        (current_position[0] - last_position[0])**2 + 
                        (current_position[1] - last_position[1])**2
                    )
                    
                    if distance > 20:  # Arbitrary threshold
                        issues.append(f"Large drawing gap detected: {distance:.1f}mm")
                
                last_position = current_position
        
        return issues
    
    async def _check_element_overlaps(self) -> int:
        """Check for overlapping drawing elements"""
        if not self.current_plot_state:
            return 0
        
        # Simple overlap detection - count elements with similar coordinates
        overlap_count = 0
        tolerance = 1.0
        
        elements = self.current_plot_state.elements
        for i, elem1 in enumerate(elements):
            for j, elem2 in enumerate(elements[i+1:], i+1):
                if elem1.element_type == elem2.element_type:
                    # Check coordinate similarity
                    for coord1 in elem1.coordinates:
                        for coord2 in elem2.coordinates:
                            if (abs(coord1[0] - coord2[0]) < tolerance and 
                                abs(coord1[1] - coord2[1]) < tolerance):
                                overlap_count += 1
                                break
        
        return overlap_count
    
    async def _calculate_drawing_efficiency(self) -> float:
        """Calculate drawing path efficiency score"""
        if not self.command_history:
            return 1.0
        
        # Simple efficiency calculation based on pen up/down ratio
        drawing_commands = len([cmd for cmd in self.command_history if cmd.command == 'G1'])
        movement_commands = len([cmd for cmd in self.command_history if cmd.command == 'G0'])
        
        if drawing_commands + movement_commands == 0:
            return 1.0
        
        efficiency = drawing_commands / (drawing_commands + movement_commands)
        return efficiency
    
    async def _generate_recovery_actions(self, errors: List[str], warnings: List[str]) -> List[RecoveryAction]:
        """Generate recovery actions for validation issues"""
        actions = []
        
        # Generate actions based on errors and warnings
        if "coordinate bounds" in " ".join(warnings).lower():
            actions.append(RecoveryAction(
                action_type="correct",
                description="Adjust coordinates to fit within bounds",
                confidence=0.8
            ))
        
        if "grid" in " ".join(warnings).lower():
            actions.append(RecoveryAction(
                action_type="correct",
                description="Snap coordinates to grid",
                confidence=0.7
            ))
        
        if "gap" in " ".join(warnings).lower():
            actions.append(RecoveryAction(
                action_type="correct",
                description="Add connecting lines to fill gaps",
                confidence=0.6
            ))
        
        return actions
    
    async def _handle_validation_error(self, validation_result: ValidationResult, command_index: int) -> None:
        """Handle validation errors"""
        self.validation_errors.append({
            "command_index": command_index,
            "timestamp": time.time(),
            "validation_result": validation_result.__dict__,
            "command": self.command_history[command_index].to_gcode() if command_index < len(self.command_history) else None
        })
        
        self.logger.warning(f"Validation failed at command {command_index}: {validation_result.errors}")
        
        # Attempt auto-recovery if enabled
        if self.config.enable_auto_recovery and validation_result.recovery_actions:
            await self._attempt_auto_recovery(validation_result.recovery_actions, command_index)
    
    async def _attempt_auto_recovery(self, recovery_actions: List[RecoveryAction], command_index: int) -> bool:
        """Attempt automatic recovery from validation errors"""
        try:
            # Try the highest confidence recovery action
            best_action = max(recovery_actions, key=lambda a: a.confidence)
            
            if best_action.action_type == "rollback" and best_action.target_command_index is not None:
                return await self.rollback_to_command(best_action.target_command_index)
            elif best_action.action_type == "correct" and best_action.correction_commands:
                return await self._apply_corrections(best_action.correction_commands)
            
            self.logger.info(f"Auto-recovery attempted: {best_action.description}")
            return True
            
        except Exception as e:
            self.logger.error(f"Auto-recovery failed: {str(e)}")
            return False
    
    async def _apply_corrections(self, correction_commands: List[GCodeCommand]) -> bool:
        """Apply correction commands"""
        try:
            for cmd in correction_commands:
                await self.add_command(cmd)
            return True
        except Exception as e:
            self.logger.error(f"Failed to apply corrections: {str(e)}")
            return False
    
    async def _update_progress_tracking(self) -> None:
        """Update drawing progress tracking"""
        if not self.current_plot_state or not self.command_history:
            return
        
        try:
            target_program = GCodeProgram(commands=self.command_history)
            self.drawing_progress = self.plot_analyzer.analyze_drawing_progress(
                self.current_plot_state,
                target_program
            )
        except Exception as e:
            self.logger.warning(f"Failed to update progress tracking: {str(e)}")
    
    async def _notify_progress_callbacks(self) -> None:
        """Notify registered progress callbacks"""
        if not self.progress_callbacks or not self.drawing_progress:
            return
        
        for callback in self.progress_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(self.drawing_progress)
                else:
                    callback(self.drawing_progress)
            except Exception as e:
                self.logger.warning(f"Progress callback failed: {str(e)}")
    
    async def _check_backup_needed(self) -> None:
        """Check if backup is needed and create if necessary"""
        if not self.config.backup_enabled or not self.backup_directory:
            return
        
        current_time = time.time()
        snapshots_since_backup = len(self.snapshot_history) - int(self.last_backup_time)
        
        if snapshots_since_backup >= self.config.backup_interval:
            await self._create_backup()
            self.last_backup_time = current_time
    
    async def _create_backup(self) -> None:
        """Create backup of current context"""
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            backup_file = self.backup_directory / f"plot_context_backup_{timestamp}.json"
            
            backup_data = {
                "timestamp": time.time(),
                "state": self.state.value,
                "command_count": len(self.command_history),
                "snapshot_count": len(self.snapshot_history),
                "grid_info": self.grid_info.model_dump() if self.grid_info else None,
                "coordinate_bounds": self.coordinate_bounds,
                "drawing_progress": self.drawing_progress.model_dump() if self.drawing_progress else None,
                "validation_errors": self.validation_errors,
                "commands": [cmd.model_dump() for cmd in self.command_history]
            }
            
            with open(backup_file, 'w') as f:
                json.dump(backup_data, f, indent=2, default=str)
            
            self.logger.info(f"Backup created: {backup_file}")
            
        except Exception as e:
            self.logger.error(f"Failed to create backup: {str(e)}")
    
    async def _handle_error(self, error: Exception, command: GCodeCommand) -> None:
        """Handle errors during command processing"""
        self.logger.error(f"Error processing command {command.to_gcode()}: {str(error)}")
        
        # Add error to validation errors
        self.validation_errors.append({
            "command_index": len(self.command_history) - 1,
            "timestamp": time.time(),
            "error": str(error),
            "command": command.to_gcode()
        })
        
        # Attempt recovery if enabled
        if self.config.enable_auto_recovery and self.recovery_stack:
            self.logger.info("Attempting error recovery...")
            last_good_snapshot = self.recovery_stack[-1]
            await self.restore_from_snapshot(last_good_snapshot)
    
    async def rollback_to_command(self, command_index: int) -> bool:
        """
        Rollback to a specific command index
        
        Args:
            command_index: Index to rollback to
            
        Returns:
            True if rollback successful
        """
        try:
            if command_index < 0 or command_index >= len(self.command_history):
                self.logger.error(f"Invalid command index for rollback: {command_index}")
                return False
            
            # Find snapshot closest to target command
            target_snapshot = None
            for snapshot in reversed(self.snapshot_history):
                if snapshot.command_index <= command_index:
                    target_snapshot = snapshot
                    break
            
            if not target_snapshot:
                self.logger.error("No suitable snapshot found for rollback")
                return False
            
            # Restore from snapshot
            success = await self.restore_from_snapshot(target_snapshot)
            if success:
                # Truncate command history
                self.command_history = self.command_history[:command_index + 1]
                self.logger.info(f"Rolled back to command {command_index}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Rollback failed: {str(e)}")
            return False
    
    async def restore_from_snapshot(self, snapshot: PlotSnapshot) -> bool:
        """
        Restore context from a snapshot
        
        Args:
            snapshot: Snapshot to restore from
            
        Returns:
            True if restore successful
        """
        try:
            # Restore plot state
            self.current_plot_state = snapshot.plot_state
            
            # Restore drawing progress
            self.drawing_progress = snapshot.drawing_progress
            
            # Restore command history up to snapshot point
            if snapshot.command_index < len(self.command_history):
                self.command_history = self.command_history[:snapshot.command_index + 1]
            
            # Clear visualizer and redraw
            if self.current_figure:
                self.visualizer.clear()
                
                # Re-execute commands up to snapshot point
                for cmd in self.command_history:
                    await self.visualizer.execute_command(cmd, self.current_figure)
            
            self.logger.info(f"Restored from snapshot at command {snapshot.command_index}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to restore from snapshot: {str(e)}")
            return False
    
    def snap_to_grid(self, position: Tuple[float, float]) -> Tuple[float, float]:
        """
        Snap position to nearest grid point
        
        Args:
            position: (x, y) position to snap
            
        Returns:
            Snapped (x, y) position
        """
        if not self.grid_info:
            return position
        
        return self.visualizer.snap_to_grid(position)
    
    def get_grid_coordinates(self, position: Tuple[float, float]) -> Optional[Tuple[int, int]]:
        """
        Convert position to grid coordinates
        
        Args:
            position: (x, y) position in plot space
            
        Returns:
            (grid_x, grid_y) coordinates or None if no grid
        """
        if not self.current_plot_state:
            return None
        
        return self.plot_analyzer.get_grid_coordinates(self.current_plot_state, position)
    
    def add_progress_callback(self, callback: Callable) -> None:
        """Add callback for progress updates"""
        self.progress_callbacks.append(callback)
    
    def remove_progress_callback(self, callback: Callable) -> None:
        """Remove progress callback"""
        if callback in self.progress_callbacks:
            self.progress_callbacks.remove(callback)
    
    def get_context_summary(self) -> Dict[str, Any]:
        """Get summary of current context state"""
        return {
            "state": self.state.value,
            "command_count": len(self.command_history),
            "snapshot_count": len(self.snapshot_history),
            "validation_errors": len(self.validation_errors),
            "drawing_progress": self.drawing_progress.model_dump() if self.drawing_progress else None,
            "grid_enabled": self.grid_info is not None,
            "coordinate_bounds": self.coordinate_bounds,
            "last_backup": self.last_backup_time
        }
    
    def get_plot_history(self) -> List[PlotState]:
        """Get plot state history"""
        return list(self.plot_history)
    
    def get_command_history(self) -> List[GCodeCommand]:
        """Get command history"""
        return self.command_history.copy()
    
    def get_snapshot_history(self) -> List[PlotSnapshot]:
        """Get snapshot history"""
        return self.snapshot_history.copy()
    
    def get_validation_errors(self) -> List[Dict[str, Any]]:
        """Get validation error history"""
        return self.validation_errors.copy()
    
    async def save_context(self, output_path: str) -> bool:
        """
        Save complete context to file
        
        Args:
            output_path: Path to save context data
            
        Returns:
            True if save successful
        """
        try:
            context_data = {
                "timestamp": time.time(),
                "config": self.config.__dict__,
                "summary": self.get_context_summary(),
                "command_history": [cmd.model_dump() for cmd in self.command_history],
                "validation_errors": self.validation_errors,
                "grid_info": self.grid_info.model_dump() if self.grid_info else None
            }
            
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_file, 'w') as f:
                json.dump(context_data, f, indent=2, default=str)
            
            self.logger.info(f"Context saved to {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save context: {str(e)}")
            return False
    
    async def cleanup(self) -> None:
        """Clean up resources"""
        try:
            # Close executor
            if self.executor:
                self.executor.shutdown(wait=True)
            
            # Clear histories
            self.plot_history.clear()
            self.command_history.clear()
            self.snapshot_history.clear()
            self.validation_errors.clear()
            self.recovery_stack.clear()
            
            # Close visualizer
            if self.visualizer:
                self.visualizer.close()
            
            self.state = PlotContextState.COMPLETED
            self.logger.info("Plot context manager cleaned up")
            
        except Exception as e:
            self.logger.error(f"Cleanup failed: {str(e)}")