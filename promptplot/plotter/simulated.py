"""
Simulated Plotter Implementation

Extracted and enhanced from existing SimulatedPenPlotter implementations.
Provides a simulated plotter for testing without hardware with enhanced visualization features.
"""

import asyncio
import random
import time
from typing import Optional, Tuple, List
from dataclasses import dataclass

from .base import BasePlotter
from .visualizer import PlotterVisualizer, MATPLOTLIB_AVAILABLE
from ..core.models import GCodeCommand


@dataclass
class SimulatedPlotterStatus:
    """Extended status for simulated plotter"""
    is_busy: bool = False
    current_command: Optional[str] = None
    last_response: Optional[str] = None
    pen_down: bool = False
    position: Tuple[float, float, float] = (0.0, 0.0, 5.0)  # x, y, z
    feed_rate: int = 1000
    speed: int = 255
    last_update: float = time.time()


class SimulatedPlotter(BasePlotter):
    """
    Simulates a pen plotter for testing without hardware
    
    Enhanced from existing SimulatedPenPlotter with better visualization
    and more realistic behavior simulation.
    """
    
    def __init__(self, port: str = "SIMULATED", commands_log_file: Optional[str] = None,
                 visualize: bool = True, command_delay: float = 0.05,
                 drawing_area: Tuple[float, float] = (100.0, 100.0),
                 enable_real_time_viz: bool = False, failure_rate: float = 0.01):
        """Initialize the simulated plotter
        
        Args:
            port: Port identifier (default: "SIMULATED")
            commands_log_file: Optional path to log commands to a file
            visualize: Whether to enable visualization features
            command_delay: Delay between commands to simulate execution time
            drawing_area: (width, height) of drawing area in mm
            enable_real_time_viz: Whether to show real-time visualization
            failure_rate: Probability of command failure (0.0 to 1.0)
        """
        super().__init__(port)
        self.status = SimulatedPlotterStatus()
        self.command_delay = command_delay
        self.command_history = []
        self.commands_log_file = commands_log_file
        self.visualize = visualize
        self.drawing_area = drawing_area
        self.enable_real_time_viz = enable_real_time_viz
        self.failure_rate = max(0.0, min(1.0, failure_rate))  # Clamp to [0, 1]
        
        # Enhanced visualization with PlotterVisualizer
        self.visualizer: Optional[PlotterVisualizer] = None
        if self.visualize and MATPLOTLIB_AVAILABLE:
            self.visualizer = PlotterVisualizer(
                drawing_area=drawing_area,
                enable_animation=enable_real_time_viz
            )
        elif self.visualize and not MATPLOTLIB_AVAILABLE:
            self.logger.warning("Matplotlib not available - visualization disabled")
            self.visualize = False
        
        # Legacy visualization data (for backward compatibility)
        self.lines = []  # List of (start_x, start_y, end_x, end_y, is_drawing)
        self.path = []   # List of (x, y, is_drawing)
        
        # Create log file if specified
        if self.commands_log_file:
            with open(self.commands_log_file, 'w') as f:
                f.write("# Simulated Plotter Command Log\n")
                f.write("# Format: timestamp, command, response\n")
                f.write("# Created: " + time.strftime("%Y-%m-%d %H:%M:%S") + "\n\n")
    
    async def connect(self) -> bool:
        """Simulate connecting to the plotter"""
        self.logger.info(f"Connecting to simulated plotter...")
        await asyncio.sleep(0.2)  # Simulate connection time
        self._active = True
        self.update_status(is_busy=False)
        
        # Initialize visualizer if enabled
        if self.visualizer:
            self.visualizer.setup_figure("Simulated Plotter - Real-time View")
            if self.enable_real_time_viz:
                self.visualizer.show(block=False)
        
        self.logger.info(f"Successfully connected to simulated plotter!")
        return True

    async def disconnect(self) -> None:
        """Simulate disconnecting from the plotter"""
        if self._active:
            self.logger.info(f"Disconnecting from simulated plotter...")
            await asyncio.sleep(0.1)  # Simulate disconnection time
            self._active = False
            self.update_status(is_busy=False)
            
            # Generate final visualization if enabled
            if self.visualizer:
                self._generate_enhanced_visualization()
            elif self.visualize and self.lines:
                self._generate_legacy_visualization()
            
            self.logger.info(f"Disconnected successfully")

    async def send_command(self, command: str) -> bool:
        """Simulate sending a command to the plotter"""
        if not self._active:
            self.logger.warning(f"Not connected to plotter")
            return False

        try:
            # Simulate processing time
            self.update_status(is_busy=True, current_command=command)
            self.logger.debug(f"Simulated plotter received: {command}")
            
            # Log the command
            self.command_history.append(command)
            if self.commands_log_file:
                with open(self.commands_log_file, 'a') as f:
                    f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}, {command}, ok\n")
            
            # Process the command - update internal state
            self._process_command(command)
            
            # Simulate execution time
            await asyncio.sleep(self.command_delay)
            
            # Simulate failure based on failure rate
            should_fail = random.random() < self.failure_rate
            
            response = "error" if should_fail else "ok"
            self.update_status(is_busy=False, last_response=response)
            self.logger.debug(f"Simulated response: {response}")
            
            # Update real-time visualization if enabled
            if self.enable_real_time_viz and self.visualizer:
                self._update_real_time_visualization()
            
            return not should_fail
            
        except Exception as e:
            self.logger.error(f"Error processing command: {str(e)}")
            self.update_status(is_busy=False, last_response="error")
            return False
    
    def _process_command(self, command: str) -> None:
        """Update the internal state based on the command"""
        if command == "COMPLETE":
            return
            
        parts = command.split()
        cmd = parts[0].upper()
        
        # Parse parameters
        params = {}
        for part in parts[1:]:
            if len(part) >= 2:
                param_name = part[0].lower()
                try:
                    param_value = float(part[1:])
                    params[param_name] = param_value
                except ValueError:
                    continue
        
        # Get current position
        current_x, current_y, current_z = self.status.position
        
        # Handle movement commands
        if cmd in ["G0", "G1"]:
            # Extract new position
            new_x = params.get('x', current_x)
            new_y = params.get('y', current_y)
            new_z = params.get('z', current_z)
            
            # Update feed rate if provided
            if 'f' in params:
                self.status.feed_rate = int(params['f'])
            
            # Determine if drawing (pen down and G1)
            is_drawing = self.status.pen_down and cmd == "G1"
            
            # Record for visualization (both legacy and enhanced)
            if self.visualize:
                # Legacy visualization data
                self.lines.append((current_x, current_y, new_x, new_y, is_drawing))
                self.path.append((new_x, new_y, is_drawing))
                
                # Enhanced visualization with PlotterVisualizer
                if self.visualizer:
                    self.visualizer.add_line(current_x, current_y, new_x, new_y, is_drawing, command)
            
            # Update position
            self.status.position = (new_x, new_y, new_z)
        
        # Handle pen up/down
        elif cmd == "M3":  # Pen Down
            self.status.pen_down = True
            if 's' in params:
                self.status.speed = int(params['s'])
            
            # Update visualizer pen state
            if self.visualizer:
                self.visualizer.pen_down = True
        
        elif cmd == "M5":  # Pen Up
            self.status.pen_down = False
            
            # Update visualizer pen state
            if self.visualizer:
                self.visualizer.pen_down = False
    
    def _update_real_time_visualization(self) -> None:
        """Update the real-time visualization display"""
        if not self.visualizer or not self.enable_real_time_viz:
            return
        
        try:
            # Re-render the visualization with current data
            self.visualizer.render_static(show_statistics=True, color_by_time=True)
            
            # Update the display (non-blocking)
            import matplotlib.pyplot as plt
            plt.draw()
            plt.pause(0.001)  # Small pause to allow display update
            
        except Exception as e:
            self.logger.warning(f"Error updating real-time visualization: {str(e)}")
    
    def _generate_enhanced_visualization(self) -> None:
        """Generate enhanced visualization using PlotterVisualizer"""
        if not self.visualizer:
            return
        
        try:
            self.logger.info(f"Generating enhanced visualization...")
            
            # Render static visualization with all features
            self.visualizer.render_static(
                show_movements=True,
                show_statistics=True,
                color_by_time=True
            )
            
            # Save multiple formats
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            base_filename = f"simulated_plotter_enhanced_{timestamp}"
            
            # Save PNG (high quality)
            png_path = self.visualizer.save_visualization(base_filename, 'png', dpi=300)
            self.logger.info(f"Enhanced visualization saved: {png_path}")
            
            # Save PDF (vector format)
            try:
                pdf_path = self.visualizer.save_visualization(base_filename, 'pdf')
                self.logger.info(f"PDF visualization saved: {pdf_path}")
            except Exception as e:
                self.logger.warning(f"Could not save PDF: {str(e)}")
            
            # Create animation if we have enough data
            if len(self.visualizer.lines) > 10:
                try:
                    animation_path = f"results/visualizations/{base_filename}_animation.gif"
                    self.visualizer.create_animation(interval=50, save_path=animation_path)
                except Exception as e:
                    self.logger.warning(f"Could not create animation: {str(e)}")
            
            # Print statistics
            stats = self.visualizer.get_statistics()
            self.logger.info("Drawing Statistics:")
            for key, value in stats.items():
                if isinstance(value, float):
                    self.logger.info(f"  {key}: {value:.2f}")
                else:
                    self.logger.info(f"  {key}: {value}")
            
        except Exception as e:
            self.logger.error(f"Error generating enhanced visualization: {str(e)}")
    
    def _generate_legacy_visualization(self) -> None:
        """Generate a legacy visualization of the drawing (fallback method)"""
        try:
            import matplotlib.pyplot as plt
            from matplotlib.patches import Rectangle, Circle
            
            self.logger.info(f"Generating legacy visualization of {len(self.lines)} line segments...")
            
            # Create figure and axis
            fig, ax = plt.subplots(figsize=(8, 8))
            
            # Set aspect ratio to equal to maintain proportions
            ax.set_aspect('equal')
            
            # Plot drawing area
            width, height = self.drawing_area
            ax.set_xlim(-10, width + 10)
            ax.set_ylim(-10, height + 10)
            ax.grid(True, linestyle='--', alpha=0.7)
            
            # Add a light gray bounding box for the drawing area
            rect = Rectangle((0, 0), width, height, linewidth=1, edgecolor='gray', 
                           facecolor='none', alpha=0.5)
            ax.add_patch(rect)
            
            # Draw home position
            home_marker = Circle((0, 0), 2, color='blue', alpha=0.7)
            ax.add_patch(home_marker)
            ax.text(0, -5, 'Home', ha='center', va='top', color='blue')
            
            # Plot each line segment
            for i, (x1, y1, x2, y2, is_drawing) in enumerate(self.lines):
                if is_drawing:
                    # Drawing lines (pen down) - dark green, solid
                    ax.plot([x1, x2], [y1, y2], 'g-', linewidth=2, alpha=0.8)
                else:
                    # Movement lines (pen up) - light blue, dashed
                    ax.plot([x1, x2], [y1, y2], 'b--', linewidth=1, alpha=0.3)
            
            # Mark start and end if we have points
            if self.path:
                start_x, start_y, _ = self.path[0]
                end_x, end_y, _ = self.path[-1]
                
                ax.plot(start_x, start_y, 'go', markersize=8)
                ax.text(start_x, start_y-5, 'Start', ha='center', va='top', color='green')
                
                ax.plot(end_x, end_y, 'ro', markersize=8)
                ax.text(end_x, end_y+5, 'End', ha='center', va='bottom', color='red')
            
            # Add title and labels
            ax.set_title('Simulated Plotter Drawing (Legacy)')
            ax.set_xlabel('X axis (mm)')
            ax.set_ylabel('Y axis (mm)')
            
            # Save the figure
            output_file = f"results/visualizations/plotter_visualization_legacy_{time.strftime('%Y%m%d_%H%M%S')}.png"
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            self.logger.info(f"Legacy visualization saved to {output_file}")
            
            plt.close()
            
        except ImportError:
            self.logger.warning("Matplotlib not available - skipping legacy visualization")
        except Exception as e:
            self.logger.error(f"Error generating legacy visualization: {str(e)}")

    def get_drawing_stats(self) -> dict:
        """Get comprehensive statistics about the drawing"""
        # Legacy statistics
        drawing_lines = sum(1 for _, _, _, _, is_drawing in self.lines if is_drawing)
        movement_lines = len(self.lines) - drawing_lines
        
        base_stats = {
            "total_commands": len(self.command_history),
            "total_lines": len(self.lines),
            "drawing_lines": drawing_lines,
            "movement_lines": movement_lines,
            "final_position": self.status.position,
            "pen_down": self.status.pen_down,
            "failure_rate": self.failure_rate,
            "command_delay": self.command_delay
        }
        
        # Enhanced statistics from visualizer if available
        if self.visualizer:
            enhanced_stats = self.visualizer.get_statistics()
            base_stats.update(enhanced_stats)
        
        return base_stats
    
    def save_current_visualization(self, filename: Optional[str] = None, 
                                 format: str = 'png') -> Optional[str]:
        """Save the current visualization to file
        
        Args:
            filename: Optional filename (timestamp will be added if not provided)
            format: Output format ('png', 'pdf', 'svg')
            
        Returns:
            Path to saved file, or None if visualization not available
        """
        if not self.visualizer:
            self.logger.warning("Enhanced visualizer not available")
            return None
        
        if filename is None:
            filename = f"simulated_plotter_{time.strftime('%Y%m%d_%H%M%S')}"
        
        try:
            # Render current state
            self.visualizer.render_static(show_statistics=True, color_by_time=True)
            
            # Save visualization
            saved_path = self.visualizer.save_visualization(filename, format)
            return saved_path
            
        except Exception as e:
            self.logger.error(f"Error saving visualization: {str(e)}")
            return None
    
    def create_drawing_animation(self, filename: Optional[str] = None,
                               interval: int = 100) -> Optional[str]:
        """Create an animated visualization of the drawing process
        
        Args:
            filename: Optional filename for the animation
            interval: Animation interval in milliseconds
            
        Returns:
            Path to saved animation, or None if not available
        """
        if not self.visualizer:
            self.logger.warning("Enhanced visualizer not available")
            return None
        
        if filename is None:
            filename = f"results/visualizations/simulated_plotter_animation_{time.strftime('%Y%m%d_%H%M%S')}.gif"
        
        try:
            self.visualizer.create_animation(interval=interval, save_path=filename)
            return filename
            
        except Exception as e:
            self.logger.error(f"Error creating animation: {str(e)}")
            return None
    
    def show_live_visualization(self) -> None:
        """Show live visualization window (non-blocking)"""
        if not self.visualizer:
            self.logger.warning("Enhanced visualizer not available")
            return
        
        try:
            self.visualizer.render_static(show_statistics=True)
            self.visualizer.show(block=False)
            
        except Exception as e:
            self.logger.error(f"Error showing live visualization: {str(e)}")
    
    def clear_drawing_data(self) -> None:
        """Clear all drawing data and reset to initial state"""
        # Clear legacy data
        self.lines.clear()
        self.path.clear()
        self.command_history.clear()
        
        # Reset status
        self.status.position = (0.0, 0.0, 5.0)
        self.status.pen_down = False
        
        # Clear enhanced visualizer
        if self.visualizer:
            self.visualizer.clear()
        
        self.logger.info("Drawing data cleared")
    
    async def __aenter__(self):
        """Enhanced context manager entry"""
        await super().__aenter__()
        
        # Setup visualization if enabled
        if self.visualizer and self.enable_real_time_viz:
            self.show_live_visualization()
        
        return self
    
    async def __aexit__(self, exc_type, exc, tb):
        """Enhanced context manager exit"""
        # Generate final visualization before disconnecting
        if self._active and self.visualizer:
            self._generate_enhanced_visualization()
        
        await super().__aexit__(exc_type, exc, tb)
        
        # Close visualizer
        if self.visualizer:
            self.visualizer.close()