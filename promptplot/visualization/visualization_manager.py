"""
Visualization Manager

Coordinates all visualization components and provides a unified interface
for managing interactive visualization, progress monitoring, and reporting.
"""

import time
import threading
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
import logging

from ..core.models import GCodeCommand, GCodeProgram
from .interactive_visualizer import InteractiveVisualizer, ViewMode
from .progress_monitor import ProgressMonitor, ProgressPhase
from .visual_reporter import VisualReporter, ReportData, ReportFormat


class VisualizationManager:
    """
    Unified visualization manager that coordinates interactive visualization,
    progress monitoring, and report generation.
    
    Features:
    - Centralized management of all visualization components
    - Real-time coordination between visualizer and progress monitor
    - Automated report generation
    - Session management and data persistence
    """
    
    def __init__(self, drawing_area: tuple = (100.0, 100.0),
                 enable_interactive: bool = True,
                 enable_progress_monitoring: bool = True,
                 enable_reporting: bool = True,
                 output_dir: str = "results"):
        """Initialize visualization manager
        
        Args:
            drawing_area: (width, height) of drawing area in mm
            enable_interactive: Enable interactive visualization
            enable_progress_monitoring: Enable progress monitoring
            enable_reporting: Enable report generation
            output_dir: Output directory for results
        """
        self.drawing_area = drawing_area
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize components
        self.visualizer = None
        self.progress_monitor = None
        self.reporter = None
        
        if enable_interactive:
            self.visualizer = InteractiveVisualizer(
                drawing_area=drawing_area,
                enable_interaction=True
            )
        
        if enable_progress_monitoring:
            self.progress_monitor = ProgressMonitor(
                enable_visualization=True,
                update_interval=1.0
            )
        
        if enable_reporting:
            self.reporter = VisualReporter(
                output_dir=str(self.output_dir / "reports")
            )
        
        # Session state
        self.current_session = None
        self.session_data = {}
        
        # Callbacks and coordination
        self._setup_component_coordination()
        
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
    
    def start_session(self, program: GCodeProgram, session_name: str = None) -> str:
        """Start a new visualization session
        
        Args:
            program: G-code program to visualize
            session_name: Optional session name
            
        Returns:
            Session ID
        """
        if session_name is None:
            session_name = f"session_{time.strftime('%Y%m%d_%H%M%S')}"
        
        self.current_session = session_name
        self.session_data = {
            'session_id': session_name,
            'program': program,
            'start_time': time.time(),
            'commands_executed': 0,
            'current_position': (0.0, 0.0, 0.0),
            'pen_down': False,
            'execution_stats': {
                'total_time': 0.0,
                'total_distance': 0.0,
                'drawing_distance': 0.0,
                'command_count': len(program.commands)
            }
        }
        
        # Initialize visualizer
        if self.visualizer:
            self.visualizer.clear()
            self.visualizer.setup_interactive_figure(f"Session: {session_name}")
            
            # Enable real-time tracking
            self.visualizer.enable_real_time_tracking(update_interval=0.5)
        
        # Start progress monitoring
        if self.progress_monitor:
            estimated_duration = self._estimate_session_duration(program)
            self.progress_monitor.start_monitoring(program, estimated_duration)
        
        self.logger.info(f"Started visualization session: {session_name}")
        return session_name
    
    def update_execution_progress(self, command_index: int, command: GCodeCommand,
                                execution_time: float, position: tuple = None,
                                pen_down: bool = None) -> None:
        """Update execution progress across all components
        
        Args:
            command_index: Index of executed command
            command: The executed command
            execution_time: Time taken to execute command
            position: Current position (x, y, z)
            pen_down: Current pen state
        """
        if not self.current_session:
            self.logger.warning("No active session for progress update")
            return
        
        # Update session data
        self.session_data['commands_executed'] = command_index + 1
        self.session_data['execution_stats']['total_time'] += execution_time
        
        if position:
            old_pos = self.session_data['current_position']
            distance = ((position[0] - old_pos[0])**2 + 
                       (position[1] - old_pos[1])**2 + 
                       (position[2] - old_pos[2])**2)**0.5
            
            self.session_data['execution_stats']['total_distance'] += distance
            self.session_data['current_position'] = position
            
            if pen_down:
                self.session_data['execution_stats']['drawing_distance'] += distance
        
        if pen_down is not None:
            self.session_data['pen_down'] = pen_down
        
        # Update visualizer
        if self.visualizer and position:
            self.visualizer.update_position(position[0], position[1], position[2], pen_down)
        
        # Update progress monitor
        if self.progress_monitor:
            self.progress_monitor.update_command_progress(command_index, command, execution_time)
            if position:
                self.progress_monitor.update_position(position, pen_down or False)
    
    def pause_session(self) -> None:
        """Pause current session"""
        if self.progress_monitor:
            self.progress_monitor.pause_monitoring()
        
        if self.visualizer:
            self.visualizer.disable_real_time_tracking()
        
        self.logger.info("Session paused")
    
    def resume_session(self) -> None:
        """Resume current session"""
        if self.progress_monitor:
            self.progress_monitor.resume_monitoring()
        
        if self.visualizer:
            self.visualizer.enable_real_time_tracking()
        
        self.logger.info("Session resumed")
    
    def end_session(self, generate_report: bool = True) -> Optional[str]:
        """End current session and optionally generate report
        
        Args:
            generate_report: Whether to generate session report
            
        Returns:
            Path to generated report if created
        """
        if not self.current_session:
            return None
        
        # Update session end time
        self.session_data['end_time'] = time.time()
        self.session_data['execution_stats']['total_time'] = (
            self.session_data['end_time'] - self.session_data['start_time']
        )
        
        # Stop progress monitoring
        if self.progress_monitor:
            self.progress_monitor.stop_monitoring()
        
        # Disable real-time tracking
        if self.visualizer:
            self.visualizer.disable_real_time_tracking()
        
        report_path = None
        if generate_report and self.reporter:
            report_path = self._generate_session_report()
        
        session_id = self.current_session
        self.current_session = None
        
        self.logger.info(f"Ended visualization session: {session_id}")
        return report_path
    
    def show_interactive_visualization(self, block: bool = False) -> None:
        """Show interactive visualization window
        
        Args:
            block: Whether to block execution until window is closed
        """
        if self.visualizer:
            self.visualizer.show_interactive(block=block)
        else:
            self.logger.warning("Interactive visualization not enabled")
    
    def get_progress_summary(self) -> Dict[str, Any]:
        """Get current progress summary"""
        summary = {
            'session_active': self.current_session is not None,
            'session_id': self.current_session,
            'session_data': self.session_data.copy() if self.current_session else {}
        }
        
        if self.progress_monitor and self.current_session:
            summary['progress'] = self.progress_monitor.get_progress_summary()
        
        return summary
    
    def save_current_view(self, filename: str = None, format: str = 'png') -> str:
        """Save current visualization view
        
        Args:
            filename: Output filename (auto-generated if None)
            format: Output format
            
        Returns:
            Path to saved file
        """
        if not self.visualizer:
            raise RuntimeError("Interactive visualization not enabled")
        
        if filename is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            session_name = self.current_session or "no_session"
            filename = f"{session_name}_view_{timestamp}"
        
        return self.visualizer.save_visualization(filename, format)
    
    def generate_comprehensive_report(self, format: ReportFormat = ReportFormat.PDF) -> str:
        """Generate comprehensive session report
        
        Args:
            format: Report format
            
        Returns:
            Path to generated report
        """
        if not self.reporter:
            raise RuntimeError("Reporting not enabled")
        
        if not self.current_session:
            raise RuntimeError("No active session to report on")
        
        return self._generate_session_report(format)
    
    def add_file_preview(self, file_path: str, color: str = 'blue') -> None:
        """Add file preview to visualization
        
        Args:
            file_path: Path to file to preview
            color: Preview color
        """
        if self.visualizer:
            self.visualizer.add_file_preview(file_path, color)
        else:
            self.logger.warning("Interactive visualization not enabled")
    
    def set_view_mode(self, mode: ViewMode) -> None:
        """Set visualization view mode
        
        Args:
            mode: View mode to set
        """
        if self.visualizer:
            self.visualizer.view_state.view_mode = mode
            self.logger.info(f"View mode set to: {mode.value}")
        else:
            self.logger.warning("Interactive visualization not enabled")
    
    def add_progress_callback(self, callback: Callable) -> None:
        """Add progress update callback
        
        Args:
            callback: Callback function
        """
        if self.progress_monitor:
            self.progress_monitor.add_progress_callback(callback)
        
        if self.visualizer:
            self.visualizer.add_update_callback(callback)
    
    def _setup_component_coordination(self) -> None:
        """Setup coordination between visualization components"""
        if self.progress_monitor and self.visualizer:
            # Add callback to update visualizer when progress changes
            def sync_progress_to_visualizer(snapshot):
                if self.visualizer:
                    # Update visualizer with progress information
                    self.visualizer.add_progress_marker(
                        'current_position',
                        snapshot.current_position[:2],
                        label=f"{snapshot.overall_percentage:.1f}%",
                        color='red' if snapshot.pen_down else 'blue'
                    )
            
            self.progress_monitor.add_progress_callback(sync_progress_to_visualizer)
    
    def _estimate_session_duration(self, program: GCodeProgram) -> float:
        """Estimate session duration based on program"""
        # Simple estimation - could be enhanced with more sophisticated analysis
        base_time_per_command = 0.15  # seconds
        return len(program.commands) * base_time_per_command
    
    def _generate_session_report(self, format: ReportFormat = ReportFormat.PDF) -> str:
        """Generate report for current session"""
        if not self.current_session or not self.reporter:
            return None
        
        # Collect visualizer data
        visualizer_data = {}
        if self.visualizer:
            visualizer_data = {
                'lines': [
                    {
                        'start_x': line.start_x,
                        'start_y': line.start_y,
                        'end_x': line.end_x,
                        'end_y': line.end_y,
                        'is_drawing': line.is_drawing,
                        'timestamp': line.timestamp
                    }
                    for line in self.visualizer.lines
                ],
                'statistics': self.visualizer.get_statistics(),
                'drawing_area': self.visualizer.drawing_area
            }
        
        # Collect progress history
        progress_history = []
        if self.progress_monitor:
            progress_history = self.progress_monitor.progress_history
        
        # Create report data
        report_data = ReportData(
            program=self.session_data['program'],
            progress_history=progress_history,
            visualizer_data=visualizer_data,
            execution_stats=self.session_data['execution_stats'],
            title=f"PromptPlot Session Report: {self.current_session}",
            description=f"Complete visualization and execution report for session {self.current_session}"
        )
        
        return self.reporter.generate_comprehensive_report(report_data, format=format)
    
    def close(self) -> None:
        """Close visualization manager and cleanup resources"""
        # End current session if active
        if self.current_session:
            self.end_session(generate_report=False)
        
        # Close components
        if self.visualizer:
            self.visualizer.close()
        
        if self.progress_monitor:
            self.progress_monitor.close()
        
        if self.reporter:
            self.reporter.close()
        
        self.logger.info("Visualization manager closed")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()