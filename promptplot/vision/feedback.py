"""
Visual Feedback Analysis System

This module provides intelligent feedback processing for pen plotter operations,
including progress analysis against target drawing intentions, action suggestion
system based on visual analysis, and grid-based coordinate validation.
"""

import numpy as np
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import time
import logging
from pathlib import Path

from .plot_analyzer import PlotAnalyzer, PlotState, PlotElement, GridInfo, DrawingProgress
from ..core.models import GCodeCommand, GCodeProgram, DrawingStrategy


class FeedbackType(str, Enum):
    """Types of feedback that can be generated"""
    PROGRESS_UPDATE = "progress_update"
    CORRECTION_NEEDED = "correction_needed"
    OPTIMIZATION_SUGGESTION = "optimization_suggestion"
    COMPLETION_DETECTED = "completion_detected"
    ERROR_DETECTED = "error_detected"


class ActionType(str, Enum):
    """Types of actions that can be suggested"""
    CONTINUE_DRAWING = "continue_drawing"
    ADJUST_POSITION = "adjust_position"
    RETRY_COMMAND = "retry_command"
    SKIP_COMMAND = "skip_command"
    OPTIMIZE_PATH = "optimize_path"
    CHANGE_STRATEGY = "change_strategy"
    PAUSE_DRAWING = "pause_drawing"
    COMPLETE_DRAWING = "complete_drawing"


@dataclass
class DrawingIntent:
    """Represents the intended drawing based on original prompt and G-code"""
    target_gcode: GCodeProgram
    expected_elements: List[Dict[str, Any]] = field(default_factory=list)
    drawing_bounds: Optional[Dict[str, float]] = None
    strategy_type: Optional[DrawingStrategy] = None
    completion_criteria: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProgressFeedback:
    """Feedback about drawing progress"""
    feedback_type: FeedbackType
    progress_percentage: float
    current_position: Optional[Tuple[float, float]] = None
    expected_position: Optional[Tuple[float, float]] = None
    position_error: Optional[float] = None
    completion_status: Dict[str, Any] = field(default_factory=dict)
    issues_detected: List[str] = field(default_factory=list)
    confidence_score: float = 1.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class ActionSuggestion:
    """Suggested action based on visual feedback"""
    action_type: ActionType
    priority: int  # 1 (highest) to 10 (lowest)
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    expected_outcome: str = ""
    confidence_score: float = 1.0
    reasoning: str = ""


@dataclass
class CoordinateValidation:
    """Result of coordinate validation against grid system"""
    is_valid: bool
    original_coordinates: Tuple[float, float]
    validated_coordinates: Tuple[float, float]
    grid_coordinates: Optional[Tuple[int, int]] = None
    adjustment_made: bool = False
    validation_error: Optional[str] = None


@dataclass
class OptimizationSuggestion:
    """Suggestion for path or drawing optimization"""
    optimization_type: str
    current_path: List[GCodeCommand]
    optimized_path: List[GCodeCommand]
    improvement_metrics: Dict[str, float] = field(default_factory=dict)
    reasoning: str = ""


class FeedbackAnalyzer:
    """
    Visual feedback analysis system for intelligent pen plotter control
    
    Provides comprehensive analysis of drawing progress against target intentions,
    generates action suggestions based on visual analysis of matplotlib plots,
    and offers grid-based coordinate validation and optimization suggestions.
    """
    
    def __init__(self, plot_analyzer: Optional[PlotAnalyzer] = None,
                 position_tolerance: float = 1.0,
                 progress_threshold: float = 0.05,
                 enable_optimization: bool = True):
        """
        Initialize the feedback analyzer
        
        Args:
            plot_analyzer: PlotAnalyzer instance for plot analysis
            position_tolerance: Tolerance for position accuracy (mm)
            progress_threshold: Minimum progress change to trigger feedback
            enable_optimization: Whether to generate optimization suggestions
        """
        self.plot_analyzer = plot_analyzer or PlotAnalyzer()
        self.position_tolerance = position_tolerance
        self.progress_threshold = progress_threshold
        self.enable_optimization = enable_optimization
        
        # Analysis state
        self._previous_progress: Optional[DrawingProgress] = None
        self._feedback_history: List[ProgressFeedback] = []
        self._action_history: List[ActionSuggestion] = []
        
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
    
    def analyze_progress_against_intent(self, plot_state: PlotState,
                                      drawing_intent: DrawingIntent,
                                      current_command_index: int = 0) -> ProgressFeedback:
        """
        Analyze drawing progress against target drawing intentions using plot data
        
        Args:
            plot_state: Current plot state from matplotlib analysis
            drawing_intent: Target drawing intentions and G-code
            current_command_index: Index of current command being executed
            
        Returns:
            Detailed progress feedback with completion analysis
        """
        # Get drawing progress from plot analyzer
        drawing_progress = self.plot_analyzer.analyze_drawing_progress(
            plot_state, drawing_intent.target_gcode
        )
        
        # Analyze progress against intent
        feedback_type = self._determine_feedback_type(drawing_progress, drawing_intent)
        
        # Calculate position accuracy
        current_pos = drawing_progress.current_position
        expected_pos = self._get_expected_position(drawing_intent, current_command_index)
        position_error = None
        
        if current_pos and expected_pos:
            position_error = np.sqrt(
                (current_pos[0] - expected_pos[0])**2 + 
                (current_pos[1] - expected_pos[1])**2
            )
        
        # Detect issues
        issues_detected = self._detect_drawing_issues(
            plot_state, drawing_intent, drawing_progress, position_error
        )
        
        # Calculate confidence score
        confidence_score = self._calculate_progress_confidence(
            drawing_progress, position_error, len(issues_detected)
        )
        
        # Analyze completion status
        completion_status = self._analyze_completion_status(
            drawing_progress, drawing_intent, current_command_index
        )
        
        feedback = ProgressFeedback(
            feedback_type=feedback_type,
            progress_percentage=drawing_progress.progress_percentage,
            current_position=current_pos,
            expected_position=expected_pos,
            position_error=position_error,
            completion_status=completion_status,
            issues_detected=issues_detected,
            confidence_score=confidence_score
        )
        
        # Store for history tracking
        self._feedback_history.append(feedback)
        self._previous_progress = drawing_progress
        
        return feedback
    
    def _determine_feedback_type(self, progress: DrawingProgress, 
                               intent: DrawingIntent) -> FeedbackType:
        """Determine the type of feedback based on progress analysis"""
        if progress.progress_percentage >= 100:
            return FeedbackType.COMPLETION_DETECTED
        
        # Check for significant progress change
        if self._previous_progress:
            progress_change = (progress.progress_percentage - 
                             self._previous_progress.progress_percentage)
            if progress_change >= self.progress_threshold:
                return FeedbackType.PROGRESS_UPDATE
        
        # Check for errors or issues
        if progress.current_position is None and progress.completed_elements > 0:
            return FeedbackType.ERROR_DETECTED
        
        return FeedbackType.PROGRESS_UPDATE
    
    def _get_expected_position(self, intent: DrawingIntent, 
                             command_index: int) -> Optional[Tuple[float, float]]:
        """Get expected position based on command index"""
        if command_index >= len(intent.target_gcode.commands):
            return None
        
        # Find the last movement command up to current index
        for i in range(command_index, -1, -1):
            cmd = intent.target_gcode.commands[i]
            if cmd.is_movement_command() and cmd.x is not None and cmd.y is not None:
                return (cmd.x, cmd.y)
        
        return (0.0, 0.0)  # Default to origin
    
    def _detect_drawing_issues(self, plot_state: PlotState, intent: DrawingIntent,
                             progress: DrawingProgress, 
                             position_error: Optional[float]) -> List[str]:
        """Detect potential issues with the drawing"""
        issues = []
        
        # Position accuracy issues
        if position_error and position_error > self.position_tolerance:
            issues.append(f"Position error: {position_error:.2f}mm exceeds tolerance")
        
        # Progress stagnation
        if (self._previous_progress and 
            progress.progress_percentage == self._previous_progress.progress_percentage and
            len(self._feedback_history) > 3):
            issues.append("Drawing progress appears stagnant")
        
        # Bounds checking
        if progress.drawing_bounds and intent.drawing_bounds:
            expected_bounds = intent.drawing_bounds
            actual_bounds = progress.drawing_bounds
            
            # Check if drawing is going outside expected bounds
            if (actual_bounds["min_x"] < expected_bounds.get("min_x", float('-inf')) or
                actual_bounds["max_x"] > expected_bounds.get("max_x", float('inf')) or
                actual_bounds["min_y"] < expected_bounds.get("min_y", float('-inf')) or
                actual_bounds["max_y"] > expected_bounds.get("max_y", float('inf'))):
                issues.append("Drawing exceeds expected bounds")
        
        # Element count validation
        expected_elements = len(intent.target_gcode.get_drawing_commands())
        if progress.completed_elements > expected_elements * 1.2:
            issues.append("More drawing elements than expected")
        
        return issues
    
    def _calculate_progress_confidence(self, progress: DrawingProgress,
                                     position_error: Optional[float],
                                     issue_count: int) -> float:
        """Calculate confidence score for progress analysis"""
        base_confidence = 1.0
        
        # Reduce confidence based on position error
        if position_error:
            error_penalty = min(position_error / (self.position_tolerance * 2), 0.5)
            base_confidence -= error_penalty
        
        # Reduce confidence based on detected issues
        issue_penalty = min(issue_count * 0.1, 0.3)
        base_confidence -= issue_penalty
        
        # Reduce confidence if no current position available
        if progress.current_position is None:
            base_confidence -= 0.2
        
        return max(base_confidence, 0.1)
    
    def _analyze_completion_status(self, progress: DrawingProgress,
                                 intent: DrawingIntent,
                                 command_index: int) -> Dict[str, Any]:
        """Analyze completion status against drawing intent"""
        total_commands = len(intent.target_gcode.commands)
        drawing_commands = len(intent.target_gcode.get_drawing_commands())
        
        return {
            "commands_completed": command_index,
            "total_commands": total_commands,
            "command_progress": (command_index / max(total_commands, 1)) * 100,
            "drawing_elements_completed": progress.completed_elements,
            "expected_drawing_elements": drawing_commands,
            "element_progress": progress.progress_percentage,
            "estimated_time_remaining": progress.estimated_completion_time,
            "is_complete": progress.progress_percentage >= 100
        }
    
    def suggest_actions_from_visual_analysis(self, plot_state: PlotState,
                                           feedback: ProgressFeedback,
                                           drawing_intent: DrawingIntent,
                                           command_history: List[GCodeCommand]) -> List[ActionSuggestion]:
        """
        Create action suggestion system based on visual analysis of matplotlib plots
        
        Args:
            plot_state: Current plot state
            feedback: Progress feedback analysis
            drawing_intent: Target drawing intentions
            command_history: History of executed commands
            
        Returns:
            List of prioritized action suggestions
        """
        suggestions = []
        
        # Completion detection
        if feedback.feedback_type == FeedbackType.COMPLETION_DETECTED:
            suggestions.append(ActionSuggestion(
                action_type=ActionType.COMPLETE_DRAWING,
                priority=1,
                description="Drawing appears complete based on visual analysis",
                expected_outcome="Finalize drawing and return to home position",
                confidence_score=feedback.confidence_score,
                reasoning="Progress analysis indicates 100% completion"
            ))
        
        # Error handling suggestions
        elif feedback.feedback_type == FeedbackType.ERROR_DETECTED:
            suggestions.extend(self._generate_error_recovery_suggestions(
                feedback, drawing_intent, command_history
            ))
        
        # Position correction suggestions
        if (feedback.position_error and 
            feedback.position_error > self.position_tolerance):
            suggestions.append(ActionSuggestion(
                action_type=ActionType.ADJUST_POSITION,
                priority=2,
                description=f"Adjust position to correct {feedback.position_error:.2f}mm error",
                parameters={
                    "target_position": feedback.expected_position,
                    "current_position": feedback.current_position,
                    "correction_vector": self._calculate_correction_vector(feedback)
                },
                expected_outcome="Improve drawing accuracy",
                confidence_score=0.8,
                reasoning=f"Position error exceeds tolerance of {self.position_tolerance}mm"
            ))
        
        # Progress optimization suggestions
        if self.enable_optimization:
            optimization_suggestions = self._generate_optimization_suggestions(
                plot_state, drawing_intent, command_history
            )
            suggestions.extend(optimization_suggestions)
        
        # Strategy change suggestions
        strategy_suggestions = self._analyze_strategy_effectiveness(
            plot_state, drawing_intent, feedback
        )
        suggestions.extend(strategy_suggestions)
        
        # Sort by priority and confidence
        suggestions.sort(key=lambda s: (s.priority, -s.confidence_score))
        
        # Store in history
        self._action_history.extend(suggestions)
        
        return suggestions
    
    def _generate_error_recovery_suggestions(self, feedback: ProgressFeedback,
                                           intent: DrawingIntent,
                                           history: List[GCodeCommand]) -> List[ActionSuggestion]:
        """Generate suggestions for error recovery"""
        suggestions = []
        
        if "stagnant" in " ".join(feedback.issues_detected).lower():
            suggestions.append(ActionSuggestion(
                action_type=ActionType.RETRY_COMMAND,
                priority=3,
                description="Retry last command due to stagnant progress",
                parameters={"retry_count": 1},
                expected_outcome="Resume drawing progress",
                confidence_score=0.7,
                reasoning="Progress appears stagnant, retry may resolve issue"
            ))
        
        if "bounds" in " ".join(feedback.issues_detected).lower():
            suggestions.append(ActionSuggestion(
                action_type=ActionType.PAUSE_DRAWING,
                priority=2,
                description="Pause drawing due to bounds violation",
                expected_outcome="Prevent further out-of-bounds drawing",
                confidence_score=0.9,
                reasoning="Drawing exceeds expected bounds, manual intervention needed"
            ))
        
        return suggestions
    
    def _calculate_correction_vector(self, feedback: ProgressFeedback) -> Optional[Tuple[float, float]]:
        """Calculate position correction vector"""
        if not (feedback.current_position and feedback.expected_position):
            return None
        
        current = feedback.current_position
        expected = feedback.expected_position
        
        return (expected[0] - current[0], expected[1] - current[1])
    
    def _generate_optimization_suggestions(self, plot_state: PlotState,
                                         intent: DrawingIntent,
                                         history: List[GCodeCommand]) -> List[ActionSuggestion]:
        """Generate optimization suggestions based on visual analysis"""
        suggestions = []
        
        # Analyze drawing efficiency
        if len(history) > 10:
            # Check for excessive pen movements
            movement_commands = [cmd for cmd in history if cmd.command == 'G0']
            drawing_commands = [cmd for cmd in history if cmd.command == 'G1']
            
            if len(movement_commands) > len(drawing_commands) * 0.5:
                suggestions.append(ActionSuggestion(
                    action_type=ActionType.OPTIMIZE_PATH,
                    priority=5,
                    description="Optimize path to reduce pen movements",
                    parameters={"movement_ratio": len(movement_commands) / len(drawing_commands)},
                    expected_outcome="Reduce drawing time and improve efficiency",
                    confidence_score=0.6,
                    reasoning="High ratio of movement to drawing commands detected"
                ))
        
        return suggestions
    
    def _analyze_strategy_effectiveness(self, plot_state: PlotState,
                                      intent: DrawingIntent,
                                      feedback: ProgressFeedback) -> List[ActionSuggestion]:
        """Analyze effectiveness of current drawing strategy"""
        suggestions = []
        
        # Check if strategy change might be beneficial
        if (feedback.confidence_score < 0.7 and 
            intent.strategy_type and 
            len(self._feedback_history) > 5):
            
            # Analyze recent feedback trends
            recent_confidence = [f.confidence_score for f in self._feedback_history[-5:]]
            avg_confidence = sum(recent_confidence) / len(recent_confidence)
            
            if avg_confidence < 0.6:
                alternative_strategy = (DrawingStrategy.NON_ORTHOGONAL 
                                      if intent.strategy_type == DrawingStrategy.ORTHOGONAL 
                                      else DrawingStrategy.ORTHOGONAL)
                
                suggestions.append(ActionSuggestion(
                    action_type=ActionType.CHANGE_STRATEGY,
                    priority=6,
                    description=f"Consider switching to {alternative_strategy.value} strategy",
                    parameters={"current_strategy": intent.strategy_type.value,
                              "suggested_strategy": alternative_strategy.value},
                    expected_outcome="Improve drawing accuracy and confidence",
                    confidence_score=0.5,
                    reasoning=f"Low confidence trend with {intent.strategy_type.value} strategy"
                ))
        
        return suggestions
    
    def validate_coordinates_against_grid(self, coordinates: Tuple[float, float],
                                        grid_info: GridInfo,
                                        snap_to_grid: bool = True) -> CoordinateValidation:
        """
        Add grid-based coordinate validation and optimization suggestions
        
        Args:
            coordinates: (x, y) coordinates to validate
            grid_info: Grid system information
            snap_to_grid: Whether to snap coordinates to nearest grid points
            
        Returns:
            Coordinate validation result with potential corrections
        """
        x, y = coordinates
        original_coords = coordinates
        
        # Check if coordinates are within grid bounds
        is_within_bounds = (grid_info.x_min <= x <= grid_info.x_max and
                           grid_info.y_min <= y <= grid_info.y_max)
        
        validation_error = None
        if not is_within_bounds:
            validation_error = f"Coordinates ({x:.3f}, {y:.3f}) outside grid bounds"
        
        # Calculate grid coordinates
        grid_coords = self.plot_analyzer.get_grid_coordinates(
            PlotState(grid_info=grid_info), coordinates
        )
        
        # Snap to grid if requested and grid step is available
        validated_coords = coordinates
        adjustment_made = False
        
        if (snap_to_grid and grid_info.x_step and grid_info.y_step and 
            is_within_bounds):
            # Snap to nearest grid points
            grid_x = round((x - grid_info.origin[0]) / grid_info.x_step)
            grid_y = round((y - grid_info.origin[1]) / grid_info.y_step)
            
            snapped_x = grid_info.origin[0] + grid_x * grid_info.x_step
            snapped_y = grid_info.origin[1] + grid_y * grid_info.y_step
            
            # Check if snapping made a significant change
            snap_distance = np.sqrt((x - snapped_x)**2 + (y - snapped_y)**2)
            if snap_distance > 0.01:  # 0.01mm threshold
                validated_coords = (snapped_x, snapped_y)
                adjustment_made = True
        
        return CoordinateValidation(
            is_valid=is_within_bounds and validation_error is None,
            original_coordinates=original_coords,
            validated_coordinates=validated_coords,
            grid_coordinates=grid_coords,
            adjustment_made=adjustment_made,
            validation_error=validation_error
        )
    
    def generate_optimization_suggestions(self, command_sequence: List[GCodeCommand],
                                        plot_state: PlotState) -> List[OptimizationSuggestion]:
        """
        Generate path and drawing optimization suggestions
        
        Args:
            command_sequence: Current sequence of G-code commands
            plot_state: Current plot state for analysis
            
        Returns:
            List of optimization suggestions with improved command sequences
        """
        suggestions = []
        
        # Analyze pen movement efficiency
        pen_lift_optimization = self._optimize_pen_movements(command_sequence)
        if pen_lift_optimization:
            suggestions.append(pen_lift_optimization)
        
        # Analyze path ordering
        path_optimization = self._optimize_path_ordering(command_sequence, plot_state)
        if path_optimization:
            suggestions.append(path_optimization)
        
        # Analyze coordinate precision
        precision_optimization = self._optimize_coordinate_precision(command_sequence)
        if precision_optimization:
            suggestions.append(precision_optimization)
        
        return suggestions
    
    def _optimize_pen_movements(self, commands: List[GCodeCommand]) -> Optional[OptimizationSuggestion]:
        """Optimize pen up/down movements to reduce unnecessary lifts"""
        if len(commands) < 3:
            return None
        
        optimized_commands = []
        pen_down = False
        unnecessary_lifts = 0
        
        for i, cmd in enumerate(commands):
            if cmd.command == 'M3':  # Pen down
                if not pen_down:
                    optimized_commands.append(cmd)
                    pen_down = True
                else:
                    unnecessary_lifts += 1
            elif cmd.command == 'M5':  # Pen up
                if pen_down:
                    # Check if next command is immediate pen down
                    if (i + 1 < len(commands) and 
                        commands[i + 1].command == 'M3'):
                        unnecessary_lifts += 1
                        continue  # Skip this pen up
                    optimized_commands.append(cmd)
                    pen_down = False
            else:
                optimized_commands.append(cmd)
        
        if unnecessary_lifts > 0:
            improvement_metrics = {
                "commands_removed": len(commands) - len(optimized_commands),
                "unnecessary_lifts_eliminated": unnecessary_lifts,
                "efficiency_improvement": unnecessary_lifts / len(commands)
            }
            
            return OptimizationSuggestion(
                optimization_type="pen_movement",
                current_path=commands,
                optimized_path=optimized_commands,
                improvement_metrics=improvement_metrics,
                reasoning=f"Eliminated {unnecessary_lifts} unnecessary pen movements"
            )
        
        return None
    
    def _optimize_path_ordering(self, commands: List[GCodeCommand],
                              plot_state: PlotState) -> Optional[OptimizationSuggestion]:
        """Optimize the ordering of drawing paths to minimize travel distance"""
        # Extract drawing segments (sequences between pen down/up)
        segments = []
        current_segment = []
        
        for cmd in commands:
            if cmd.command == 'M3':  # Start new segment
                current_segment = []
            elif cmd.command == 'M5':  # End segment
                if current_segment:
                    segments.append(current_segment)
                current_segment = []
            elif cmd.is_movement_command():
                current_segment.append(cmd)
        
        if len(segments) < 2:
            return None
        
        # Simple nearest-neighbor optimization for segment ordering
        optimized_segments = [segments[0]]
        remaining_segments = segments[1:]
        
        while remaining_segments:
            last_point = self._get_segment_end_point(optimized_segments[-1])
            
            # Find nearest segment start
            nearest_idx = 0
            min_distance = float('inf')
            
            for i, segment in enumerate(remaining_segments):
                start_point = self._get_segment_start_point(segment)
                if start_point and last_point:
                    distance = np.sqrt((start_point[0] - last_point[0])**2 + 
                                     (start_point[1] - last_point[1])**2)
                    if distance < min_distance:
                        min_distance = distance
                        nearest_idx = i
            
            optimized_segments.append(remaining_segments.pop(nearest_idx))
        
        # Rebuild command sequence
        optimized_commands = []
        for segment in optimized_segments:
            optimized_commands.append(GCodeCommand(command='M3'))  # Pen down
            optimized_commands.extend(segment)
            optimized_commands.append(GCodeCommand(command='M5'))  # Pen up
        
        # Calculate improvement
        original_distance = self._calculate_total_travel_distance(commands)
        optimized_distance = self._calculate_total_travel_distance(optimized_commands)
        
        if optimized_distance < original_distance:
            improvement_metrics = {
                "original_travel_distance": original_distance,
                "optimized_travel_distance": optimized_distance,
                "distance_reduction": original_distance - optimized_distance,
                "efficiency_improvement": (original_distance - optimized_distance) / original_distance
            }
            
            return OptimizationSuggestion(
                optimization_type="path_ordering",
                current_path=commands,
                optimized_path=optimized_commands,
                improvement_metrics=improvement_metrics,
                reasoning=f"Reduced travel distance by {improvement_metrics['distance_reduction']:.2f}mm"
            )
        
        return None
    
    def _optimize_coordinate_precision(self, commands: List[GCodeCommand]) -> Optional[OptimizationSuggestion]:
        """Optimize coordinate precision to reduce command complexity"""
        optimized_commands = []
        precision_improvements = 0
        
        for cmd in commands:
            if cmd.is_movement_command():
                # Round coordinates to reasonable precision (0.1mm)
                new_cmd = cmd.model_copy()
                if cmd.x is not None:
                    rounded_x = round(cmd.x, 1)
                    if abs(rounded_x - cmd.x) < 0.05:  # Within 0.05mm tolerance
                        new_cmd.x = rounded_x
                        precision_improvements += 1
                
                if cmd.y is not None:
                    rounded_y = round(cmd.y, 1)
                    if abs(rounded_y - cmd.y) < 0.05:
                        new_cmd.y = rounded_y
                        precision_improvements += 1
                
                optimized_commands.append(new_cmd)
            else:
                optimized_commands.append(cmd)
        
        if precision_improvements > 0:
            improvement_metrics = {
                "coordinates_optimized": precision_improvements,
                "precision_improvement": precision_improvements / len(commands)
            }
            
            return OptimizationSuggestion(
                optimization_type="coordinate_precision",
                current_path=commands,
                optimized_path=optimized_commands,
                improvement_metrics=improvement_metrics,
                reasoning=f"Optimized precision for {precision_improvements} coordinates"
            )
        
        return None
    
    def _get_segment_start_point(self, segment: List[GCodeCommand]) -> Optional[Tuple[float, float]]:
        """Get the starting point of a drawing segment"""
        for cmd in segment:
            if cmd.is_movement_command() and cmd.x is not None and cmd.y is not None:
                return (cmd.x, cmd.y)
        return None
    
    def _get_segment_end_point(self, segment: List[GCodeCommand]) -> Optional[Tuple[float, float]]:
        """Get the ending point of a drawing segment"""
        for cmd in reversed(segment):
            if cmd.is_movement_command() and cmd.x is not None and cmd.y is not None:
                return (cmd.x, cmd.y)
        return None
    
    def _calculate_total_travel_distance(self, commands: List[GCodeCommand]) -> float:
        """Calculate total travel distance for a command sequence"""
        total_distance = 0.0
        current_pos = (0.0, 0.0)
        
        for cmd in commands:
            if cmd.is_movement_command() and cmd.x is not None and cmd.y is not None:
                new_pos = (cmd.x, cmd.y)
                distance = np.sqrt((new_pos[0] - current_pos[0])**2 + 
                                 (new_pos[1] - current_pos[1])**2)
                total_distance += distance
                current_pos = new_pos
        
        return total_distance
    
    def get_feedback_history(self) -> List[ProgressFeedback]:
        """Get history of progress feedback"""
        return self._feedback_history.copy()
    
    def get_action_history(self) -> List[ActionSuggestion]:
        """Get history of action suggestions"""
        return self._action_history.copy()
    
    def clear_history(self) -> None:
        """Clear feedback and action history"""
        self._feedback_history.clear()
        self._action_history.clear()
        self._previous_progress = None
        self.logger.info("Feedback analysis history cleared")