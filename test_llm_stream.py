import asyncio
import logging
from dataclasses import dataclass
from typing import Optional, Dict, List, Union, Any, Tuple
import time
from colorama import Fore, Style, init
import json
import random
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle
import numpy as np
import os

# Initialize colorama for cross-platform color support
init(autoreset=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class SimulatedPlotterStatus:
    """Tracks the current status of the simulated plotter"""
    is_busy: bool = False
    current_command: Optional[str] = None
    last_response: Optional[str] = None
    pen_down: bool = False
    position: Tuple[float, float, float] = (0.0, 0.0, 5.0)  # x, y, z
    feed_rate: int = 1000
    speed: int = 255
    last_update: float = time.time()

class SimulatedPlotter:
    """Simulates a pen plotter for testing without hardware"""
    
    def __init__(self, port: str = "SIMULATED", commands_log_file: Optional[str] = None):
        """Initialize the simulated plotter
        
        Args:
            port: A placeholder port name (ignored)
            commands_log_file: Optional path to log commands to a file
        """
        self.port = port
        self.status = SimulatedPlotterStatus()
        self._active = False
        self.command_delay = 0.05  # Shorter delay for simulation
        self.command_history = []
        self.commands_log_file = commands_log_file
        
        # Visualization data
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
        print(f"{Fore.YELLOW}Connecting to simulated plotter...{Style.RESET_ALL}")
        await asyncio.sleep(0.2)  # Simulate connection time
        self._active = True
        print(f"{Fore.GREEN}Successfully connected to simulated plotter!{Style.RESET_ALL}")
        return True

    async def disconnect(self):
        """Simulate disconnecting from the plotter"""
        if self._active:
            print(f"{Fore.YELLOW}Disconnecting from simulated plotter...{Style.RESET_ALL}")
            await asyncio.sleep(0.1)  # Simulate disconnection time
            self._active = False
            print(f"{Fore.GREEN}Disconnected successfully{Style.RESET_ALL}")

    async def send_command(self, command: str) -> bool:
        """Simulate sending a command to the plotter"""
        if not self._active:
            print(f"{Fore.RED}Not connected to plotter{Style.RESET_ALL}")
            return False

        try:
            # Simulate small processing time
            self.status.is_busy = True
            self.status.current_command = command
            print(f"{Fore.BLUE}Simulated plotter received: {command}{Style.RESET_ALL}")
            
            # Log the command
            self.command_history.append(command)
            if self.commands_log_file:
                with open(self.commands_log_file, 'a') as f:
                    f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}, {command}, ok\n")
            
            # Process the command - update internal state
            self._process_command(command)
            
            # Simulate some execution time
            await asyncio.sleep(self.command_delay)
            
            # Rarely fail (1% chance) to simulate real-world issues
            should_fail = random.random() < 0.01
            
            response = "error" if should_fail else "ok"
            self.status.last_response = response
            self.status.is_busy = False
            print(f"{Fore.GREEN}Simulated response: {response}{Style.RESET_ALL}")
            
            return not should_fail
            
        except Exception as e:
            print(f"{Fore.RED}Error processing command: {str(e)}{Style.RESET_ALL}")
            return False
    
    def _process_command(self, command: str):
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
            
            # Record for visualization
            self.lines.append((current_x, current_y, new_x, new_y, is_drawing))
            self.path.append((new_x, new_y, is_drawing))
            
            # Update position
            self.status.position = (new_x, new_y, new_z)
        
        # Handle pen up/down
        elif cmd == "M3":  # Pen Down
            self.status.pen_down = True
            if 's' in params:
                self.status.speed = int(params['s'])
        
        elif cmd == "M5":  # Pen Up
            self.status.pen_down = False
    
    def format_command(self, command_dict: Dict[str, Any]) -> str:
        """Convert command dict to G-code string"""
        if command_dict.get("command") == "COMPLETE":
            return "COMPLETE"
            
        gcode = command_dict["command"]
        for key, value in command_dict.items():
            if key != "command" and value is not None:
                gcode += f" {key.upper()}{value}"
        return gcode
    
    def visualize_drawing(self, output_file: str = None, show: bool = True):
        """Visualize the drawing from recorded commands"""
        if not self.lines:
            print(f"{Fore.YELLOW}No drawing commands to visualize{Style.RESET_ALL}")
            return
        
        print(f"{Fore.CYAN}Generating visualization of {len(self.lines)} line segments...{Style.RESET_ALL}")
        
        # Create figure and axis
        fig, ax = plt.subplots(figsize=(8, 8))
        
        # Set aspect ratio to equal to maintain proportions
        ax.set_aspect('equal')
        
        # Plot drawing area (assuming a standard 100x100mm area)
        ax.set_xlim(-10, 110)
        ax.set_ylim(-10, 110)
        ax.grid(True, linestyle='--', alpha=0.7)
        
        # Add a light gray bounding box for the drawing area
        rect = Rectangle((0, 0), 100, 100, linewidth=1, edgecolor='gray', facecolor='none', alpha=0.5)
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
        
        # Mark start (first point) and end (last point) if we have points
        if self.path:
            start_x, start_y, _ = self.path[0]
            end_x, end_y, _ = self.path[-1]
            
            ax.plot(start_x, start_y, 'go', markersize=8)
            ax.text(start_x, start_y-5, 'Start', ha='center', va='top', color='green')
            
            ax.plot(end_x, end_y, 'ro', markersize=8)
            ax.text(end_x, end_y+5, 'End', ha='center', va='bottom', color='red')
        
        # Add title and labels
        ax.set_title('Simulated Plotter Drawing')
        ax.set_xlabel('X axis (mm)')
        ax.set_ylabel('Y axis (mm)')
        
        # Save the figure if an output file is specified
        if output_file:
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            print(f"{Fore.GREEN}Visualization saved to {output_file}{Style.RESET_ALL}")
        
        # Show the plot if requested
        if show:
            plt.show()
        
        plt.close()

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.disconnect()

# Function to allow this module to be imported and used separately
def get_simulated_plotter(commands_log_file: Optional[str] = None) -> SimulatedPlotter:
    """Get a simulated plotter instance for testing"""
    return SimulatedPlotter(port="SIMULATED", commands_log_file=commands_log_file)

# Standalone test function
async def test_simulated_plotter():
    """Test the simulated plotter with some basic commands"""
    # Create the simulated plotter
    plotter = SimulatedPlotter(commands_log_file="simulated_commands.log")
    
    # Connect to the plotter
    await plotter.connect()
    
    try:
        # Send some commands to draw a square
        commands = [
            "G0 X0 Y0 Z5",      # Move to home position
            "M3 S255",          # Pen down
            "G1 X0 Y0 F1000",   # Start at origin
            "G1 X50 Y0 F1000",  # Draw bottom line
            "G1 X50 Y50 F1000", # Draw right line
            "G1 X0 Y50 F1000",  # Draw top line
            "G1 X0 Y0 F1000",   # Draw left line to close the square
            "M5",               # Pen up
            "G0 X0 Y0 Z5",      # Return to home position
        ]
        
        # Execute commands
        for cmd in commands:
            success = await plotter.send_command(cmd)
            if not success:
                print(f"{Fore.RED}Command failed: {cmd}{Style.RESET_ALL}")
        
        # Visualize the drawing
        plotter.visualize_drawing(output_file="simulated_square.png")
        
    finally:
        # Disconnect from the plotter
        await plotter.disconnect()

if __name__ == "__main__":
    # Test the simulated plotter
    asyncio.run(test_simulated_plotter())