"""
Progress Monitoring System

Comprehensive progress tracking with visual and statistical metrics,
drawing completion estimation, and performance monitoring.
"""

import time
import threading
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging
import json
from pathlib import Path

try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
    from matplotlib.animation import FuncAnimation
    import numpy as np
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

from ..core.models import GCodeCommand, GCodeProgram


class ProgressPhase(str, Enum):
    """Phases of drawing progress"""
    INITIALIZING = "initializing"
    HOMING = "homing"
    DRAWING = "drawing"
    MOVING = "moving"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"


class MetricType(str, Enum):
    """Types of progress metrics"""
    DISTANCE = "distance"
    TIME = "time"
    COMMANDS = "commands"
    ACCURACY = "accuracy"
    SPEED = "speed"
    EFFICIENCY = "efficiency"
    FILE_PROGRESS = "file_progress"
    MEMORY_USAGE = "memory_usage"
    CPU_USAGE = "cpu_usage"


@dataclass
class ProgressMetric:
    """Individual progress metric"""
    metric_type: MetricType
    current_value: float
    target_value: float
    unit: str
    timestamp: float = field(default_factory=time.time)
    
    @property
    def percentage(self) -> float:
        """Calculate percentage completion"""
        if self.target_value == 0:
            return 100.0
        return min(100.0, (self.current_value / self.target_value) * 100.0)
    
    @property
    def remaining(self) -> float:
        """Calculate remaining value"""
        return max(0.0, self.target_value - self.current_value)


@dataclass
class ProgressSnapshot:
    """Snapshot of progress at a specific time"""
    timestamp: float
    phase: ProgressPhase
    metrics: Dict[MetricType, ProgressMetric]
    current_command: Optional[GCodeCommand] = None
    current_position: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    pen_down: bool = False
    error_message: Optional[str] = None
    file_info: Optional[Dict[str, Any]] = None
    performance_info: Optional[Dict[str, Any]] = None
    
    @property
    def overall_percentage(self) -> float:
        """Calculate overall progress percentage"""
        if not self.metrics:
            return 0.0
        
        # Weight different metrics
        weights = {
            MetricType.COMMANDS: 0.3,
            MetricType.DISTANCE: 0.2,
            MetricType.TIME: 0.2,
            MetricType.FILE_PROGRESS: 0.3
        }
        
        weighted_sum = 0.0
        total_weight = 0.0
        
        for metric_type, weight in weights.items():
            if metric_type in self.metrics:
                weighted_sum += self.metrics[metric_type].percentage * weight
                total_weight += weight
        
        return weighted_sum / total_weight if total_weight > 0 else 0.0


class ProgressMonitor:
    """
    Comprehensive progress monitoring system with visual and statistical metrics.
    
    Features:
    - Real-time progress tracking
    - Drawing completion estimation
    - Performance monitoring and bottleneck identification
    - Visual progress indicators
    - Statistical analysis and reporting
    """
    
    def __init__(self, enable_visualization: bool = True,
                 update_interval: float = 1.0,
                 history_size: int = 1000,
                 enable_performance_monitoring: bool = True):
        """Initialize progress monitor
        
        Args:
            enable_visualization: Whether to enable visual progress indicators
            update_interval: Update interval in seconds
            history_size: Maximum number of snapshots to keep in history
            enable_performance_monitoring: Whether to enable system performance monitoring
        """
        self.enable_visualization = enable_visualization and MATPLOTLIB_AVAILABLE
        self.update_interval = update_interval
        self.history_size = history_size
        self.enable_performance_monitoring = enable_performance_monitoring
        
        # Progress state
        self.current_phase = ProgressPhase.INITIALIZING
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.is_monitoring = False
        
        # Metrics tracking
        self.metrics: Dict[MetricType, ProgressMetric] = {}
        self.progress_history: List[ProgressSnapshot] = []
        
        # Target values (set when starting monitoring)
        self.target_program: Optional[GCodeProgram] = None
        self.estimated_duration: Optional[float] = None
        
        # Current state
        self.current_command_index = 0
        self.current_position = (0.0, 0.0, 0.0)
        self.pen_down = False
        self.total_distance_traveled = 0.0
        self.drawing_distance_traveled = 0.0
        
        # Performance tracking
        self.command_times: List[float] = []
        self.bottlenecks: List[Dict[str, Any]] = []
        self.performance_samples: List[Dict[str, Any]] = []
        
        # File plotting specific tracking
        self.file_info: Optional[Dict[str, Any]] = None
        self.file_progress_metrics: Dict[str, Any] = {}
        
        # Time estimation and completion tracking
        self.completion_estimates: List[float] = []
        self.time_remaining_estimates: List[float] = []
        
        # Callbacks
        self.progress_callbacks: List[Callable[[ProgressSnapshot], None]] = []
        self.phase_change_callbacks: List[Callable[[ProgressPhase, ProgressPhase], None]] = []
        self.bottleneck_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        
        # Visualization
        self.progress_fig = None
        self.progress_ax = None
        self.progress_animation = None
        
        # Threading
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_monitoring = threading.Event()
        
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
    
    def start_monitoring(self, program: GCodeProgram,
                        estimated_duration: Optional[float] = None,
                        file_info: Optional[Dict[str, Any]] = None) -> None:
        """Start progress monitoring for a G-code program
        
        Args:
            program: G-code program to monitor
            estimated_duration: Estimated execution duration in seconds
        """
        if self.is_monitoring:
            self.logger.warning("Already monitoring, stopping previous session")
            self.stop_monitoring()
        
        self.target_program = program
        self.estimated_duration = estimated_duration or self._estimate_duration(program)
        self.start_time = time.time()
        self.end_time = None
        self.is_monitoring = True
        self.file_info = file_info
        
        # Initialize metrics
        self._initialize_metrics(program, file_info)
        
        # Reset state
        self.current_command_index = 0
        self.current_position = (0.0, 0.0, 0.0)
        self.pen_down = False
        self.total_distance_traveled = 0.0
        self.drawing_distance_traveled = 0.0
        self.progress_history.clear()
        self.command_times.clear()
        self.bottlenecks.clear()
        
        # Change phase
        self._change_phase(ProgressPhase.HOMING)
        
        # Start monitoring thread
        self._stop_monitoring.clear()
        self._monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._monitor_thread.start()
        
        # Setup visualization
        if self.enable_visualization:
            self._setup_progress_visualization()
        
        self.logger.info(f"Started monitoring program with {len(program.commands)} commands")
    
    def stop_monitoring(self) -> None:
        """Stop progress monitoring"""
        if not self.is_monitoring:
            return
        
        self.is_monitoring = False
        self.end_time = time.time()
        
        # Stop monitoring thread
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._stop_monitoring.set()
            self._monitor_thread.join(timeout=2.0)
        
        # Change phase
        self._change_phase(ProgressPhase.COMPLETED)
        
        # Stop visualization
        if self.progress_animation:
            self.progress_animation.event_source.stop()
            self.progress_animation = None
        
        self.logger.info("Stopped progress monitoring")
    
    def update_command_progress(self, command_index: int, command: GCodeCommand,
                              execution_time: float) -> None:
        """Update progress for a completed command
        
        Args:
            command_index: Index of completed command
            command: The completed command
            execution_time: Time taken to execute command in seconds
        """
        if not self.is_monitoring:
            return
        
        self.current_command_index = command_index
        self.command_times.append(execution_time)
        
        # Update position if it's a movement command
        if command.is_movement_command():
            old_pos = self.current_position
            new_pos = (
                command.x if command.x is not None else old_pos[0],
                command.y if command.y is not None else old_pos[1],
                command.z if command.z is not None else old_pos[2]
            )
            
            # Calculate distance
            distance = np.sqrt(
                (new_pos[0] - old_pos[0])**2 + 
                (new_pos[1] - old_pos[1])**2 + 
                (new_pos[2] - old_pos[2])**2
            )
            
            self.total_distance_traveled += distance
            
            if self.pen_down:
                self.drawing_distance_traveled += distance
            
            self.current_position = new_pos
        
        # Update pen state
        if command.is_pen_down():
            self.pen_down = True
            self._change_phase(ProgressPhase.DRAWING)
        elif command.is_pen_up():
            self.pen_down = False
            self._change_phase(ProgressPhase.MOVING)
        
        # Update metrics
        self._update_metrics()
        
        # Check for bottlenecks
        self._check_bottlenecks(command, execution_time)
    
    def update_position(self, position: Tuple[float, float, float],
                       pen_down: bool) -> None:
        """Update current position and pen state
        
        Args:
            position: Current (x, y, z) position
            pen_down: Current pen state
        """
        if not self.is_monitoring:
            return
        
        # Calculate distance if position changed
        if position != self.current_position:
            distance = np.sqrt(
                (position[0] - self.current_position[0])**2 + 
                (position[1] - self.current_position[1])**2 + 
                (position[2] - self.current_position[2])**2
            )
            
            self.total_distance_traveled += distance
            
            if pen_down:
                self.drawing_distance_traveled += distance
        
        self.current_position = position
        self.pen_down = pen_down
        
        # Update phase based on pen state
        if pen_down:
            self._change_phase(ProgressPhase.DRAWING)
        else:
            self._change_phase(ProgressPhase.MOVING)
    
    def pause_monitoring(self) -> None:
        """Pause progress monitoring"""
        if self.is_monitoring:
            self._change_phase(ProgressPhase.PAUSED)
    
    def resume_monitoring(self) -> None:
        """Resume progress monitoring"""
        if self.is_monitoring:
            if self.pen_down:
                self._change_phase(ProgressPhase.DRAWING)
            else:
                self._change_phase(ProgressPhase.MOVING)
    
    def report_error(self, error_message: str) -> None:
        """Report an error during execution
        
        Args:
            error_message: Description of the error
        """
        self._change_phase(ProgressPhase.ERROR)
        
        # Create error snapshot
        snapshot = self._create_snapshot()
        snapshot.error_message = error_message
        self.progress_history.append(snapshot)
        
        self.logger.error(f"Progress monitoring error: {error_message}")
    
    def get_current_progress(self) -> ProgressSnapshot:
        """Get current progress snapshot"""
        return self._create_snapshot()
    
    def get_progress_summary(self) -> Dict[str, Any]:
        """Get comprehensive progress summary"""
        current = self.get_current_progress()
        
        # Calculate timing statistics
        elapsed_time = time.time() - (self.start_time or time.time())
        estimated_remaining = self._calculate_remaining_time()
        
        # Calculate efficiency metrics
        efficiency_metrics = self._calculate_efficiency_metrics()
        
        return {
            "overall_progress": current.overall_percentage,
            "current_phase": current.phase.value,
            "elapsed_time": elapsed_time,
            "estimated_remaining": estimated_remaining,
            "estimated_total": self.estimated_duration,
            "current_position": current.current_position,
            "pen_down": current.pen_down,
            "metrics": {
                metric_type.value: {
                    "current": metric.current_value,
                    "target": metric.target_value,
                    "percentage": metric.percentage,
                    "unit": metric.unit
                }
                for metric_type, metric in current.metrics.items()
            },
            "efficiency": efficiency_metrics,
            "bottlenecks": self.bottlenecks[-5:] if self.bottlenecks else [],  # Last 5 bottlenecks
            "command_progress": {
                "current": self.current_command_index,
                "total": len(self.target_program.commands) if self.target_program else 0
            }
        }
    
    def _initialize_metrics(self, program: GCodeProgram, file_info: Optional[Dict[str, Any]] = None) -> None:
        """Initialize progress metrics based on program and file info"""
        # Calculate target values
        total_commands = len(program.commands)
        estimated_distance = self._estimate_total_distance(program)
        
        self.metrics = {
            MetricType.COMMANDS: ProgressMetric(
                MetricType.COMMANDS, 0, total_commands, "commands"
            ),
            MetricType.DISTANCE: ProgressMetric(
                MetricType.DISTANCE, 0.0, estimated_distance, "mm"
            ),
            MetricType.TIME: ProgressMetric(
                MetricType.TIME, 0.0, self.estimated_duration, "seconds"
            )
        }
        
        # Add file-specific metrics if file info is available
        if file_info:
            self.metrics[MetricType.FILE_PROGRESS] = ProgressMetric(
                MetricType.FILE_PROGRESS, 0.0, 100.0, "percent"
            )
        
        # Add performance metrics if enabled
        if self.enable_performance_monitoring:
            self.metrics[MetricType.MEMORY_USAGE] = ProgressMetric(
                MetricType.MEMORY_USAGE, 0.0, 100.0, "percent"
            )
            self.metrics[MetricType.CPU_USAGE] = ProgressMetric(
                MetricType.CPU_USAGE, 0.0, 100.0, "percent"
            )
    
    def _update_metrics(self) -> None:
        """Update all progress metrics"""
        if not self.start_time:
            return
        
        elapsed_time = time.time() - self.start_time
        
        # Update metrics
        if MetricType.COMMANDS in self.metrics:
            self.metrics[MetricType.COMMANDS].current_value = self.current_command_index
        
        if MetricType.DISTANCE in self.metrics:
            self.metrics[MetricType.DISTANCE].current_value = self.total_distance_traveled
        
        if MetricType.TIME in self.metrics:
            self.metrics[MetricType.TIME].current_value = elapsed_time
    
    def _estimate_duration(self, program: GCodeProgram) -> float:
        """Estimate program execution duration"""
        # Simple estimation based on command count and typical speeds
        base_time_per_command = 0.1  # seconds
        movement_time_factor = 1.5
        drawing_time_factor = 2.0
        
        total_time = 0.0
        
        for command in program.commands:
            if command.is_movement_command():
                if command.f:  # Has feed rate
                    # Estimate based on distance and feed rate
                    # This is a simplified calculation
                    total_time += movement_time_factor
                else:
                    total_time += base_time_per_command
            elif command.is_pen_command():
                total_time += base_time_per_command * 0.5
            else:
                total_time += base_time_per_command
        
        return total_time
    
    def _estimate_total_distance(self, program: GCodeProgram) -> float:
        """Estimate total distance to be traveled"""
        total_distance = 0.0
        current_pos = (0.0, 0.0, 0.0)
        
        for command in program.commands:
            if command.is_movement_command():
                new_pos = (
                    command.x if command.x is not None else current_pos[0],
                    command.y if command.y is not None else current_pos[1],
                    command.z if command.z is not None else current_pos[2]
                )
                
                distance = np.sqrt(
                    (new_pos[0] - current_pos[0])**2 + 
                    (new_pos[1] - current_pos[1])**2 + 
                    (new_pos[2] - current_pos[2])**2
                )
                
                total_distance += distance
                current_pos = new_pos
        
        return total_distance
    
    def _calculate_remaining_time(self) -> float:
        """Calculate estimated remaining time"""
        if not self.start_time or not self.target_program:
            return 0.0
        
        elapsed_time = time.time() - self.start_time
        
        # Calculate progress ratio
        commands_progress = self.current_command_index / len(self.target_program.commands)
        
        if commands_progress <= 0:
            return self.estimated_duration
        
        # Estimate based on current progress rate
        estimated_total = elapsed_time / commands_progress
        return max(0.0, estimated_total - elapsed_time)
    
    def _calculate_efficiency_metrics(self) -> Dict[str, float]:
        """Calculate efficiency metrics"""
        if not self.command_times:
            return {}
        
        avg_command_time = np.mean(self.command_times)
        command_time_std = np.std(self.command_times)
        
        # Calculate efficiency score (lower is better)
        efficiency_score = avg_command_time / (self.estimated_duration / len(self.target_program.commands)) if self.target_program else 1.0
        
        return {
            "average_command_time": avg_command_time,
            "command_time_variance": command_time_std,
            "efficiency_score": efficiency_score,
            "drawing_efficiency": self.drawing_distance_traveled / max(1.0, self.total_distance_traveled),
            "time_efficiency": (time.time() - (self.start_time or time.time())) / max(1.0, self.estimated_duration)
        }
    
    def _check_bottlenecks(self, command: GCodeCommand, execution_time: float) -> None:
        """Check for performance bottlenecks"""
        if not self.command_times:
            return
        
        avg_time = np.mean(self.command_times[-10:])  # Average of last 10 commands
        
        # Check if this command took significantly longer
        if execution_time > avg_time * 2.0 and execution_time > 0.5:
            bottleneck = {
                "timestamp": time.time(),
                "command_index": self.current_command_index,
                "command": command.command,
                "execution_time": execution_time,
                "average_time": avg_time,
                "slowdown_factor": execution_time / avg_time,
                "position": self.current_position
            }
            
            self.bottlenecks.append(bottleneck)
            self.logger.warning(f"Performance bottleneck detected: {command.command} took {execution_time:.2f}s")
    
    def _change_phase(self, new_phase: ProgressPhase) -> None:
        """Change current phase and notify callbacks"""
        if new_phase == self.current_phase:
            return
        
        old_phase = self.current_phase
        self.current_phase = new_phase
        
        # Notify callbacks
        for callback in self.phase_change_callbacks:
            try:
                callback(old_phase, new_phase)
            except Exception as e:
                self.logger.error(f"Phase change callback error: {str(e)}")
        
        self.logger.info(f"Phase changed: {old_phase.value} -> {new_phase.value}")
    
    def _create_snapshot(self) -> ProgressSnapshot:
        """Create current progress snapshot"""
        return ProgressSnapshot(
            timestamp=time.time(),
            phase=self.current_phase,
            metrics=self.metrics.copy(),
            current_position=self.current_position,
            pen_down=self.pen_down
        )
    
    def _monitoring_loop(self) -> None:
        """Main monitoring loop (runs in separate thread)"""
        while not self._stop_monitoring.is_set() and self.is_monitoring:
            try:
                # Update metrics
                self._update_metrics()
                
                # Collect performance metrics
                performance_info = self.collect_performance_metrics()
                
                # Update performance metrics
                if performance_info and self.enable_performance_monitoring:
                    if MetricType.CPU_USAGE in self.metrics:
                        self.metrics[MetricType.CPU_USAGE].current_value = performance_info.get('system_cpu_percent', 0)
                    if MetricType.MEMORY_USAGE in self.metrics:
                        self.metrics[MetricType.MEMORY_USAGE].current_value = performance_info.get('system_memory_percent', 0)
                
                # Detect bottlenecks
                new_bottlenecks = self.detect_performance_bottlenecks()
                self.bottlenecks.extend(new_bottlenecks)
                
                # Limit bottleneck history
                if len(self.bottlenecks) > 50:
                    self.bottlenecks = self.bottlenecks[-50:]
                
                # Create snapshot
                snapshot = self._create_snapshot()
                snapshot.performance_info = performance_info
                snapshot.file_info = self.get_file_plotting_statistics() if self.file_info else None
                
                self.progress_history.append(snapshot)
                
                # Limit history size
                if len(self.progress_history) > self.history_size:
                    self.progress_history.pop(0)
                
                # Notify callbacks
                for callback in self.progress_callbacks:
                    try:
                        callback(snapshot)
                    except Exception as e:
                        self.logger.error(f"Progress callback error: {str(e)}")
                
                # Wait for next update
                self._stop_monitoring.wait(self.update_interval)
                
            except Exception as e:
                self.logger.error(f"Monitoring loop error: {str(e)}")
                break
    
    def _setup_progress_visualization(self) -> None:
        """Setup progress visualization"""
        if not self.enable_visualization:
            return
        
        try:
            # Create progress figure
            self.progress_fig, axes = plt.subplots(2, 2, figsize=(12, 8))
            self.progress_fig.suptitle("Progress Monitoring Dashboard")
            
            # Progress bars
            self.progress_ax = axes[0, 0]
            self.progress_ax.set_title("Overall Progress")
            
            # Time chart
            self.time_ax = axes[0, 1]
            self.time_ax.set_title("Time Progress")
            
            # Distance chart
            self.distance_ax = axes[1, 0]
            self.distance_ax.set_title("Distance Progress")
            
            # Performance chart
            self.performance_ax = axes[1, 1]
            self.performance_ax.set_title("Performance Metrics")
            
            # Start animation
            self.progress_animation = FuncAnimation(
                self.progress_fig, self._update_progress_visualization,
                interval=int(self.update_interval * 1000),
                blit=False, repeat=True
            )
            
            plt.tight_layout()
            plt.show(block=False)
            
        except Exception as e:
            self.logger.error(f"Failed to setup progress visualization: {str(e)}")
            self.enable_visualization = False
    
    def _update_progress_visualization(self, frame) -> None:
        """Update progress visualization"""
        if not self.is_monitoring or not self.progress_history:
            return
        
        try:
            current = self.progress_history[-1]
            
            # Clear axes
            self.progress_ax.clear()
            self.time_ax.clear()
            self.distance_ax.clear()
            self.performance_ax.clear()
            
            # Progress bars
            self.progress_ax.set_title("Overall Progress")
            progress_data = []
            labels = []
            
            for metric_type, metric in current.metrics.items():
                progress_data.append(metric.percentage)
                labels.append(f"{metric_type.value.title()}\n{metric.current_value:.1f}/{metric.target_value:.1f} {metric.unit}")
            
            bars = self.progress_ax.barh(range(len(progress_data)), progress_data, color=['green', 'blue', 'orange'])
            self.progress_ax.set_yticks(range(len(labels)))
            self.progress_ax.set_yticklabels(labels)
            self.progress_ax.set_xlim(0, 100)
            self.progress_ax.set_xlabel("Progress (%)")
            
            # Add percentage labels on bars
            for i, (bar, percentage) in enumerate(zip(bars, progress_data)):
                self.progress_ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height()/2, 
                                    f'{percentage:.1f}%', va='center')
            
            # Time progress
            if len(self.progress_history) > 1:
                times = [(s.timestamp - self.start_time) / 60 for s in self.progress_history]  # Convert to minutes
                percentages = [s.overall_percentage for s in self.progress_history]
                
                self.time_ax.plot(times, percentages, 'b-', linewidth=2)
                self.time_ax.set_xlabel("Time (minutes)")
                self.time_ax.set_ylabel("Progress (%)")
                self.time_ax.set_ylim(0, 100)
                self.time_ax.grid(True, alpha=0.3)
            
            # Distance progress
            if MetricType.DISTANCE in current.metrics:
                distance_metric = current.metrics[MetricType.DISTANCE]
                drawing_percentage = (self.drawing_distance_traveled / max(1.0, distance_metric.target_value)) * 100
                movement_percentage = ((self.total_distance_traveled - self.drawing_distance_traveled) / max(1.0, distance_metric.target_value)) * 100
                
                self.distance_ax.bar(['Drawing', 'Movement'], [drawing_percentage, movement_percentage], 
                                   color=['green', 'lightblue'])
                self.distance_ax.set_ylabel("Distance Progress (%)")
                self.distance_ax.set_ylim(0, 100)
            
            # Performance metrics
            if self.command_times:
                recent_times = self.command_times[-20:]  # Last 20 commands
                self.performance_ax.plot(range(len(recent_times)), recent_times, 'r-', linewidth=1)
                self.performance_ax.set_xlabel("Recent Commands")
                self.performance_ax.set_ylabel("Execution Time (s)")
                self.performance_ax.set_title(f"Command Performance (avg: {np.mean(recent_times):.3f}s)")
                
                # Add bottleneck markers
                for bottleneck in self.bottlenecks[-5:]:
                    if bottleneck['command_index'] >= len(self.command_times) - 20:
                        idx = bottleneck['command_index'] - (len(self.command_times) - 20)
                        if 0 <= idx < len(recent_times):
                            self.performance_ax.plot(idx, bottleneck['execution_time'], 'ro', markersize=8)
            
            plt.tight_layout()
            
        except Exception as e:
            self.logger.error(f"Progress visualization update error: {str(e)}")
    
    def add_progress_callback(self, callback: Callable[[ProgressSnapshot], None]) -> None:
        """Add progress update callback"""
        self.progress_callbacks.append(callback)
    
    def add_phase_change_callback(self, callback: Callable[[ProgressPhase, ProgressPhase], None]) -> None:
        """Add phase change callback"""
        self.phase_change_callbacks.append(callback)
    
    def add_bottleneck_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Add bottleneck detection callback"""
        self.bottleneck_callbacks.append(callback)
    
    def start_file_monitoring(self, program: GCodeProgram, file_path: str,
                            file_type: str, original_file_size: int = 0,
                            estimated_duration: Optional[float] = None) -> None:
        """Start monitoring for file plotting with file-specific metrics
        
        Args:
            program: G-code program to monitor
            file_path: Path to original file being plotted
            file_type: Type of original file (SVG, DXF, etc.)
            original_file_size: Size of original file in bytes
            estimated_duration: Estimated execution duration
        """
        file_info = {
            'file_path': file_path,
            'file_type': file_type,
            'file_size': original_file_size,
            'conversion_time': 0.0,  # Would be set by converter
            'optimization_applied': False,
            'original_commands': 0,  # Would be set if known
            'converted_commands': len(program.commands)
        }
        
        self.start_monitoring(program, estimated_duration, file_info)
        self.logger.info(f"Started file monitoring for {file_type} file: {file_path}")
    
    def update_file_progress(self, bytes_processed: int, total_bytes: int) -> None:
        """Update file processing progress
        
        Args:
            bytes_processed: Number of bytes processed
            total_bytes: Total bytes to process
        """
        if not self.is_monitoring or not self.file_info:
            return
        
        file_progress_percentage = (bytes_processed / max(1, total_bytes)) * 100.0
        
        # Update file progress metric
        if MetricType.FILE_PROGRESS in self.metrics:
            self.metrics[MetricType.FILE_PROGRESS].current_value = file_progress_percentage
        
        self.file_progress_metrics.update({
            'bytes_processed': bytes_processed,
            'total_bytes': total_bytes,
            'progress_percentage': file_progress_percentage,
            'processing_rate': bytes_processed / max(1.0, time.time() - (self.start_time or time.time()))
        })
    
    def get_time_remaining_estimate(self) -> float:
        """Get improved time remaining estimate with multiple methods
        
        Returns:
            Estimated time remaining in seconds
        """
        if not self.start_time or not self.target_program:
            return 0.0
        
        elapsed_time = time.time() - self.start_time
        
        # Method 1: Based on command progress
        commands_progress = self.current_command_index / len(self.target_program.commands)
        if commands_progress > 0:
            command_based_estimate = (elapsed_time / commands_progress) - elapsed_time
        else:
            command_based_estimate = self.estimated_duration
        
        # Method 2: Based on distance progress
        distance_based_estimate = self.estimated_duration
        if MetricType.DISTANCE in self.metrics:
            distance_metric = self.metrics[MetricType.DISTANCE]
            if distance_metric.current_value > 0:
                distance_progress = distance_metric.current_value / distance_metric.target_value
                distance_based_estimate = (elapsed_time / distance_progress) - elapsed_time
        
        # Method 3: Based on recent command timing
        timing_based_estimate = self.estimated_duration
        if len(self.command_times) >= 10:
            recent_avg_time = np.mean(self.command_times[-10:])
            remaining_commands = len(self.target_program.commands) - self.current_command_index
            timing_based_estimate = remaining_commands * recent_avg_time
        
        # Weighted average of estimates
        estimates = [command_based_estimate, distance_based_estimate, timing_based_estimate]
        weights = [0.4, 0.3, 0.3]
        
        weighted_estimate = sum(est * weight for est, weight in zip(estimates, weights))
        
        # Store estimate for trend analysis
        self.time_remaining_estimates.append(weighted_estimate)
        if len(self.time_remaining_estimates) > 20:
            self.time_remaining_estimates.pop(0)
        
        return max(0.0, weighted_estimate)
    
    def get_completion_estimate(self) -> Dict[str, Any]:
        """Get comprehensive completion estimate with confidence intervals
        
        Returns:
            Dictionary with completion estimates and confidence metrics
        """
        time_remaining = self.get_time_remaining_estimate()
        current_time = time.time()
        
        # Calculate confidence based on estimate stability
        confidence = 0.5  # Default medium confidence
        if len(self.time_remaining_estimates) >= 5:
            recent_estimates = self.time_remaining_estimates[-5:]
            estimate_variance = np.var(recent_estimates)
            # Lower variance = higher confidence
            confidence = max(0.1, min(0.95, 1.0 - (estimate_variance / (time_remaining + 1.0))))
        
        estimated_completion_time = current_time + time_remaining
        
        # Calculate confidence interval
        confidence_interval = time_remaining * (1.0 - confidence) * 0.5
        
        return {
            'estimated_completion_time': estimated_completion_time,
            'time_remaining_seconds': time_remaining,
            'time_remaining_formatted': self._format_duration(time_remaining),
            'confidence_score': confidence,
            'confidence_interval_seconds': confidence_interval,
            'earliest_completion': estimated_completion_time - confidence_interval,
            'latest_completion': estimated_completion_time + confidence_interval,
            'estimate_method': 'weighted_average',
            'estimate_stability': 1.0 - (np.std(self.time_remaining_estimates[-10:]) / max(1.0, time_remaining)) if len(self.time_remaining_estimates) >= 10 else 0.5
        }
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format"""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"
    
    def collect_performance_metrics(self) -> Dict[str, Any]:
        """Collect system performance metrics
        
        Returns:
            Dictionary with current performance metrics
        """
        if not self.enable_performance_monitoring:
            return {}
        
        try:
            import psutil
            
            # CPU and memory usage
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            
            # Process-specific metrics
            process = psutil.Process()
            process_memory = process.memory_info()
            process_cpu = process.cpu_percent()
            
            performance_data = {
                'timestamp': time.time(),
                'system_cpu_percent': cpu_percent,
                'system_memory_percent': memory.percent,
                'system_memory_available': memory.available,
                'process_memory_rss': process_memory.rss,
                'process_memory_vms': process_memory.vms,
                'process_cpu_percent': process_cpu,
                'command_queue_size': len(self.command_times),
                'bottleneck_count': len(self.bottlenecks)
            }
            
            # Store performance sample
            self.performance_samples.append(performance_data)
            if len(self.performance_samples) > 100:
                self.performance_samples.pop(0)
            
            return performance_data
            
        except ImportError:
            self.logger.warning("psutil not available for performance monitoring")
            return {}
        except Exception as e:
            self.logger.error(f"Error collecting performance metrics: {str(e)}")
            return {}
    
    def detect_performance_bottlenecks(self) -> List[Dict[str, Any]]:
        """Detect and analyze performance bottlenecks
        
        Returns:
            List of detected bottlenecks with analysis
        """
        bottlenecks = []
        
        # Analyze command timing patterns
        if len(self.command_times) >= 20:
            recent_times = self.command_times[-20:]
            avg_time = np.mean(recent_times)
            std_time = np.std(recent_times)
            
            # Detect commands that are significantly slower
            for i, cmd_time in enumerate(recent_times[-10:]):
                if cmd_time > avg_time + 2 * std_time and cmd_time > 0.5:
                    bottlenecks.append({
                        'type': 'slow_command',
                        'severity': 'medium' if cmd_time < avg_time + 3 * std_time else 'high',
                        'command_index': len(self.command_times) - 10 + i,
                        'execution_time': cmd_time,
                        'average_time': avg_time,
                        'slowdown_factor': cmd_time / avg_time,
                        'timestamp': time.time()
                    })
        
        # Analyze system performance
        if self.performance_samples:
            recent_performance = self.performance_samples[-10:]
            
            # Check for high CPU usage
            avg_cpu = np.mean([p.get('system_cpu_percent', 0) for p in recent_performance])
            if avg_cpu > 80:
                bottlenecks.append({
                    'type': 'high_cpu_usage',
                    'severity': 'medium' if avg_cpu < 90 else 'high',
                    'cpu_percent': avg_cpu,
                    'timestamp': time.time()
                })
            
            # Check for high memory usage
            avg_memory = np.mean([p.get('system_memory_percent', 0) for p in recent_performance])
            if avg_memory > 85:
                bottlenecks.append({
                    'type': 'high_memory_usage',
                    'severity': 'medium' if avg_memory < 95 else 'high',
                    'memory_percent': avg_memory,
                    'timestamp': time.time()
                })
        
        # Notify bottleneck callbacks
        for bottleneck in bottlenecks:
            for callback in self.bottleneck_callbacks:
                try:
                    callback(bottleneck)
                except Exception as e:
                    self.logger.error(f"Bottleneck callback error: {str(e)}")
        
        return bottlenecks
    
    def get_file_plotting_statistics(self) -> Dict[str, Any]:
        """Get file plotting specific statistics
        
        Returns:
            Dictionary with file plotting metrics
        """
        if not self.file_info:
            return {}
        
        stats = {
            'file_info': self.file_info.copy(),
            'file_progress_metrics': self.file_progress_metrics.copy(),
            'conversion_efficiency': 0.0,
            'plotting_efficiency': 0.0
        }
        
        # Calculate conversion efficiency
        if self.file_info.get('original_commands', 0) > 0:
            stats['conversion_efficiency'] = (
                self.file_info['converted_commands'] / self.file_info['original_commands']
            )
        
        # Calculate plotting efficiency (drawing vs movement ratio)
        if self.total_distance_traveled > 0:
            stats['plotting_efficiency'] = (
                self.drawing_distance_traveled / self.total_distance_traveled
            )
        
        return stats
    
    def save_progress_report(self, output_path: Optional[str] = None) -> str:
        """Save comprehensive progress report to file
        
        Args:
            output_path: Optional output file path
            
        Returns:
            Path to saved report
        """
        if output_path is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output_dir = Path("results/progress_reports")
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"progress_report_{timestamp}.json"
        
        report = {
            "session_info": {
                "start_time": self.start_time,
                "end_time": self.end_time,
                "duration": (self.end_time or time.time()) - (self.start_time or time.time()),
                "program_commands": len(self.target_program.commands) if self.target_program else 0
            },
            "final_progress": self.get_progress_summary(),
            "history": [
                {
                    "timestamp": snapshot.timestamp,
                    "phase": snapshot.phase.value,
                    "overall_percentage": snapshot.overall_percentage,
                    "position": snapshot.current_position,
                    "pen_down": snapshot.pen_down
                }
                for snapshot in self.progress_history
            ],
            "bottlenecks": self.bottlenecks,
            "performance_stats": {
                "total_commands": len(self.command_times),
                "average_command_time": np.mean(self.command_times) if self.command_times else 0,
                "command_time_std": np.std(self.command_times) if self.command_times else 0,
                "total_distance": self.total_distance_traveled,
                "drawing_distance": self.drawing_distance_traveled
            }
        }
        
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        self.logger.info(f"Progress report saved to: {output_path}")
        return str(output_path)
    
    def close(self) -> None:
        """Close progress monitor and cleanup resources"""
        self.stop_monitoring()
        
        if self.progress_fig:
            plt.close(self.progress_fig)
            self.progress_fig = None