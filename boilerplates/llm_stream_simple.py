import asyncio
import logging
from dataclasses import dataclass
from typing import Optional, Dict, List, Union, Any, Tuple
import time
from collections import deque
import json
import os
from colorama import Fore, Style, init
from llama_index.llms.ollama import Ollama
from llama_index.core.workflow import (
    Event,
    StartEvent,
    StopEvent,
    Workflow,
    step,
    Context,
)
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
import argparse
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle

# Import serial communication tools when needed
try:
    from serial_asyncio import open_serial_connection
except ImportError:
    print(f"{Fore.YELLOW}Warning: serial_asyncio not found. Real plotter functionality will be limited.{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}To enable real plotter support, install with: pip install pyserial-asyncio{Style.RESET_ALL}")

# Initialize colorama for cross-platform color support
init(autoreset=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Pydantic models for G-code validation
class GCodeCommand(BaseModel):
    """Model for a single G-code command"""
    command: str
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None
    f: Optional[int] = None
    s: Optional[int] = None
    p: Optional[int] = None

    # Validate command format
    @field_validator('command')
    @classmethod
    def validate_command(cls, v):
        """Validates that the command is a valid G-code command"""
        valid_commands = ['G0', 'G1', 'G2', 'G3', 'G4', 'M3', 'M5', 'COMPLETE']
        v = v.upper().strip()
        if v == "COMPLETE":
            return v
        if not v.startswith(('G', 'M')):
            raise ValueError(f"Command must start with G or M, got {v}")
        if v not in valid_commands:
            raise ValueError(f"Command must be one of {valid_commands}")
        return v

    def to_gcode(self) -> str:
        """Convert to G-code string format"""
        if self.command == "COMPLETE":
            return "COMPLETE"
            
        parts = [self.command]
        for attr, value in self.model_dump().items():
            if value is not None and attr != 'command':
                parts.append(f"{attr.upper()}{value:.3f}" if isinstance(value, float) else f"{attr.upper()}{value}")
        return " ".join(parts)

class GCodeProgram(BaseModel):
    """Model for a complete G-code program"""
    commands: List[GCodeCommand]

    def to_gcode(self) -> str:
        """Convert the entire program to G-code string format"""
        return "\n".join(cmd.to_gcode() for cmd in self.commands)

@dataclass
class PlotterStatus:
    """Tracks the current status of the plotter"""
    is_busy: bool = False
    current_command: Optional[str] = None
    last_response: Optional[str] = None
    queue_size: int = 0
    last_update: float = time.time()

class PlotterVisualizer:
    """Visualizes the plotter's drawing in real-time"""
    
    def __init__(self, interactive: bool = True, bounds: Tuple[float, float, float, float] = (-10, 10, -10, 10)):
        """Initialize the visualizer
        
        Args:
            interactive: Whether to show the plot interactively (True) or save to file (False)
            bounds: The drawing bounds as (xmin, xmax, ymin, ymax)
        """
        self.paths = []
        self.current_path = []
        self.pen_down = False
        self.current_pos = (0, 0, 0)  # x, y, z
        self.interactive = interactive
        self.bounds = bounds
        self.created_figure = False
        
        if interactive:
            plt.ion()  # Turn on interactive mode
            self.setup_plot()
        
    def setup_plot(self):
        """Set up the plot for visualization"""
        if not self.created_figure:
            self.fig, self.ax = plt.subplots(figsize=(10, 10))
            self.ax.set_aspect('equal')
            self.ax.grid(True)
            self.ax.set_xlim(self.bounds[0], self.bounds[1])
            self.ax.set_ylim(self.bounds[2], self.bounds[3])
            self.ax.set_title('G-code Visualization')
            self.ax.set_xlabel('X')
            self.ax.set_ylabel('Y')
            
            # Add a marker for the current position
            self.pos_marker = self.ax.plot(0, 0, 'ro', markersize=8)[0]
            
            # Add a pen status indicator
            self.pen_circle = Circle((0.9, 0.9), 0.05, transform=self.ax.transAxes, 
                                    facecolor='red', edgecolor='black')
            self.ax.add_patch(self.pen_circle)
            self.ax.text(0.93, 0.9, 'Pen', transform=self.ax.transAxes,
                         verticalalignment='center')
            
            self.created_figure = True
            
            if self.interactive:
                plt.show(block=False)
    
    def process_command(self, command: GCodeCommand):
        """Process a G-code command and update the visualization
        
        Args:
            command: The G-code command to process
        """
        if not self.created_figure:
            self.setup_plot()
            
        cmd = command.command
        
        # Handle pen up/down commands
        if cmd == 'M3':  # Pen down
            self.pen_down = True
            self.pen_circle.set_facecolor('green')
            # Start a new path if we don't have one
            if not self.current_path:
                self.current_path = [self.current_pos[:2]]
        
        elif cmd == 'M5':  # Pen up
            self.pen_down = False
            self.pen_circle.set_facecolor('red')
            # Close current path if we have one
            if self.current_path:
                self.paths.append(self.current_path)
                self.current_path = []
        
        # Handle movement commands
        elif cmd in ['G0', 'G1']:
            x = command.x if command.x is not None else self.current_pos[0]
            y = command.y if command.y is not None else self.current_pos[1]
            z = command.z if command.z is not None else self.current_pos[2]
            
            # If pen is down, add to current path
            if self.pen_down:
                if not self.current_path:
                    self.current_path = [self.current_pos[:2]]
                self.current_path.append((x, y))
                
                # Draw the new line segment
                self.ax.plot([self.current_pos[0], x], [self.current_pos[1], y], 'b-', linewidth=2)
            else:
                # Draw a dotted line for movement without drawing
                self.ax.plot([self.current_pos[0], x], [self.current_pos[1], y], 'g--', linewidth=1, alpha=0.5)
            
            # Update current position
            self.current_pos = (x, y, z)
            
            # Update position marker
            self.pos_marker.set_data(x, y)
        
        # Update the plot if interactive
        if self.interactive:
            self.fig.canvas.draw_idle()
            self.fig.canvas.flush_events()
    
    def save_visualization(self, filename='gcode_visualization.png'):
        """Save the current visualization to a file
        
        Args:
            filename: The filename to save the visualization to
        """
        # Close any open path
        if self.current_path:
            self.paths.append(self.current_path)
            self.current_path = []
        
        # Create a new figure if we're not using interactive mode
        if not self.created_figure:
            self.setup_plot()
        
        # Draw all paths
        for path in self.paths:
            if len(path) > 1:
                xs, ys = zip(*path)
                self.ax.plot(xs, ys, 'b-', linewidth=2)
        
        # Save the figure
        plt.savefig(filename, dpi=150, bbox_inches='tight')
        print(f"{Fore.GREEN}[+] Visualization saved to {filename}{Style.RESET_ALL}")
        
        # Close the figure if not interactive
        if not self.interactive:
            plt.close(self.fig)
    
    def close(self):
        """Close the visualization"""
        if self.created_figure:
            plt.close(self.fig)
            self.created_figure = False

class SimulatedPenPlotter:
    """Simulates a pen plotter for testing without hardware"""
    
    def __init__(self, port: str = "SIMULATED", visualize: bool = True):
        self.port = port
        self.status = PlotterStatus()
        self.command_delay = 0.1
        self._active = False
        self.commands = []
        self.visualize = visualize
        self.visualizer = PlotterVisualizer(interactive=visualize) if visualize else None

    async def connect(self) -> bool:
        """Simulate connection to the plotter"""
        print(f"{Fore.YELLOW}Connecting to simulated plotter on {self.port}...{Style.RESET_ALL}")
        # Simulate a small delay
        await asyncio.sleep(0.5)
        self._active = True
        print(f"{Fore.GREEN}Successfully connected to simulated plotter!{Style.RESET_ALL}")
        return True

    async def disconnect(self):
        """Simulate disconnection from the plotter"""
        if self._active:
            print(f"{Fore.YELLOW}Disconnecting from simulated plotter...{Style.RESET_ALL}")
            await asyncio.sleep(0.3)
            self._active = False
            print(f"{Fore.GREEN}Disconnected successfully{Style.RESET_ALL}")
            
            # Save the visualization
            if self.visualize and self.visualizer:
                self.visualizer.save_visualization()
                self.visualizer.close()

    async def send_command(self, command: str) -> bool:
        """Simulate sending a command to the plotter"""
        if not self._active:
            print(f"{Fore.RED}Not connected to plotter{Style.RESET_ALL}")
            return False

        try:
            print(f"{Fore.BLUE}Sending: {command}{Style.RESET_ALL}")
            self.commands.append(command)
            
            # Simulate a small delay
            await asyncio.sleep(self.command_delay)
            
            # Update visualization if enabled
            if self.visualize and self.visualizer and command != "COMPLETE":
                # Parse the command
                parts = command.split()
                cmd_parts = {}
                
                for part in parts:
                    if part[0] in ['G', 'M']:  # Command part
                        cmd_parts["command"] = part
                    elif len(part) > 1:  # Parameter part
                        param = part[0].lower()
                        value = float(part[1:])
                        cmd_parts[param] = value
                
                # Create a GCodeCommand and process it
                cmd_obj = GCodeCommand(**cmd_parts)
                self.visualizer.process_command(cmd_obj)
            
            # Simulate a response
            response_text = 'ok'
            print(f"{Fore.GREEN}Response: {response_text}{Style.RESET_ALL}")
            
            return True
        except Exception as e:
            print(f"{Fore.RED}Error sending command: {str(e)}{Style.RESET_ALL}")
            return False

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.disconnect()

class RealPenPlotter:
    """Controls a physical pen plotter via serial connection"""
    
    def __init__(self, port: str, baud_rate: int = 115200):
        self.port = port
        self.baud_rate = baud_rate
        self.controller = None
        self.status = PlotterStatus()
        self.command_delay = 0.1
        self._active = False

    async def connect(self) -> bool:
        """Connect to the physical plotter"""
        try:
            print(f"{Fore.YELLOW}Connecting to physical plotter on {self.port} at {self.baud_rate} baud...{Style.RESET_ALL}")
            
            # Import here to avoid dependency issues if not using real plotter
            from serial_asyncio import open_serial_connection
            
            # Create controller for serial communication
            self.controller = AsyncController(self.port, self.baud_rate)
            success = await self.controller.wire_up()
            
            if success:
                self._active = True
                print(f"{Fore.GREEN}Successfully connected to physical plotter!{Style.RESET_ALL}")
                return True
            else:
                print(f"{Fore.RED}Failed to connect to physical plotter on {self.port}{Style.RESET_ALL}")
                return False
                
        except Exception as e:
            print(f"{Fore.RED}Error connecting to plotter: {str(e)}{Style.RESET_ALL}")
            import traceback
            traceback.print_exc()
            return False

    async def disconnect(self):
        """Disconnect from the physical plotter"""
        if self._active and self.controller:
            print(f"{Fore.YELLOW}Disconnecting from physical plotter...{Style.RESET_ALL}")
            await self.controller.disconnect()
            self._active = False
            self.controller = None
            print(f"{Fore.GREEN}Disconnected successfully{Style.RESET_ALL}")

    async def send_command(self, command: str) -> bool:
        """Send a command to the physical plotter"""
        if not self._active or not self.controller:
            print(f"{Fore.RED}Not connected to plotter{Style.RESET_ALL}")
            return False

        try:
            print(f"{Fore.BLUE}Sending to physical plotter: {command}{Style.RESET_ALL}")
            
            # Send the command via the controller
            response = await self.controller.send_signal(command)
            
            if response is None:
                print(f"{Fore.RED}No response from plotter{Style.RESET_ALL}")
                return False
                
            print(f"{Fore.GREEN}Response: {response}{Style.RESET_ALL}")
            return True
            
        except Exception as e:
            print(f"{Fore.RED}Error sending command to physical plotter: {str(e)}{Style.RESET_ALL}")
            return False

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.disconnect()

class Dispatcher:
    """Manages the real-time streaming of plotting tasks."""

    def __init__(self, max_buffer_size=5, command_delay=0.1):
        self.command_queue = deque(maxlen=max_buffer_size)
        self.max_buffer_size = max_buffer_size
        self.command_delay = command_delay
        self.status = PlotterStatus()
        self._active = False
        self._processing = False

    def is_buffer_full(self) -> bool:
        """Check if the command buffer is full"""
        return len(self.command_queue) >= self.max_buffer_size

    async def add_command(self, command: str) -> bool:
        """Add a command to the queue if there's space"""
        if self.is_buffer_full():
            await asyncio.sleep(self.command_delay)
            if self.is_buffer_full():
                return False
        
        self.command_queue.append(command)
        self.status.queue_size = len(self.command_queue)
        return True

    async def get_next_command(self) -> Optional[str]:
        """Get the next command from the queue"""
        if self.command_queue:
            command = self.command_queue.popleft()
            self.status.queue_size = len(self.command_queue)
            return command
        return None

    def stop_processing(self):
        """Stop processing commands"""
        self._active = False

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def is_processing(self) -> bool:
        return self._processing

class AsyncController:
    def __init__(self, port: str, baud_rate: int):
        self.port = port
        self.baud_rate = baud_rate
        self.reader = None
        self.writer = None
        self.logger = logging.getLogger(__name__)
        self.dispatcher = Dispatcher()
        self._active = False

    async def wire_up(self) -> bool:
        """Establish connection with the plotter"""
        try:
            self.reader, self.writer = await open_serial_connection(
                url=self.port, baudrate=self.baud_rate)
            self.logger.info(f"Connection established on {self.port}")
            self._active = True
            return True
        except Exception as e:
            self.logger.error(f"Failed to open serial port: {e}")
            return False

    async def send_signal(self, signal: str) -> Optional[str]:
        """Send a single command and wait for response"""
        if not self.writer:
            self.logger.error("Cannot send signal: Not connected to the plotter.")
            return None

        try:
            self.writer.write(f"{signal}\n".encode())
            await self.writer.drain()
            response = await asyncio.wait_for(self.reader.readline(), timeout=5.0)
            return response.decode().strip()
        except asyncio.TimeoutError:
            self.logger.error("Timeout waiting for plotter response")
            return None
        except Exception as e:
            self.logger.error(f"Error sending signal to plotter: {e}")
            return None

    async def disconnect(self):
        """Disconnect from the plotter"""
        self.dispatcher.stop_processing()
        
        if self.writer:
            self.writer.close()
            try:
                await asyncio.wait_for(self.writer.wait_closed(), timeout=5.0)
                self.logger.info("Serial connection closed")
            except asyncio.TimeoutError:
                self.logger.warning("Timeout while closing serial connection")
        
        self.reader = None
        self.writer = None
        self._active = False

# Event Classes
class GenerateCommandEvent(Event):
    """Event to trigger generation of a new plotter command."""
    prompt: str = Field(description="Drawing prompt")
    step: int = Field(description="Current step number")

class CommandExtractionDone(Event):
    """Event indicating command extraction is complete but not yet validated."""
    output: str = Field(description="Raw output from LLM")
    prompt: str = Field(description="Drawing prompt")
    step: int = Field(description="Current step number")

class CommandValidationErrorEvent(Event):
    """Event for validation errors in command generation."""
    error: str = Field(description="Error message from validation")
    issues: str = Field(description="Raw output that failed validation")
    prompt: str = Field(description="Drawing prompt")
    step: int = Field(description="Current step number")

class ValidatedCommandEvent(Event):
    """Event containing a validated plotter command."""
    command: GCodeCommand = Field(description="Validated command")
    prompt: str = Field(description="Drawing prompt")
    step: int = Field(description="Current step number")
    is_complete: bool = Field(description="Whether this is the final command")

class CommandExecutedEvent(Event):
    """Event indicating a command was sent to the plotter."""
    prompt: str = Field(description="Drawing prompt")
    step: int = Field(description="Current step number")
    command: GCodeCommand = Field(description="Executed command")
    is_complete: bool = Field(description="Whether this is the final command")
    success: bool = Field(description="Whether the command was successfully executed")

class PlotterCompleteEvent(Event):
    """Event indicating plotter has completed the drawing."""
    prompt: str = Field(description="Drawing prompt that was completed")
    commands_executed: int = Field(description="Number of commands executed")
    step_count: int = Field(description="Number of steps taken")

# Constants and Prompt templates
NEXT_COMMAND_TEMPLATE = """
Generate the NEXT single G-code command for a pen plotter based on this prompt: {prompt}

Previous commands:
{history}

Rules:
1. Use G0 for rapid movements (no drawing)
2. Use G1 for drawing lines with feed rate (f)
3. Use M3/M5 for pen up/down (s value should be 0-255)
4. Use only commands: G0, G1, M3, M5
5. All coordinates (x, y, z) should be float numbers
   - Use coordinates between -100 and 100
   - Start with pen up (M5)
   - Move to starting position (G0)
   - Lower pen (M3)
   - Draw (G1)
   - Raise pen (M5) when done
6. Feed rate (f) and speed (s) should be integers, and a value of 2000 is recommended

Return ONLY ONE command as a JSON object like:
{{"command": "G0", "x": 10.0, "y": 20.0, "z": 0.0}}

If the drawing is complete, return:
{{"command": "COMPLETE"}}

Do not include any explanations, just the JSON object.
"""

REFLECTION_PROMPT = """
Your previous response had validation errors and could not be processed correctly.

Previous response: {wrong_answer}

Error details: {error}

Please reflect on these errors and produce a valid response that strictly follows the required JSON format.
Make sure to:
1. Use proper JSON syntax with correct quotes, commas, and brackets
2. Only include fields that are needed for this specific command
3. Use valid commands (G0, G1, M3, M5)
4. Use the right data types (floats for coordinates, integers for feed rate and speed)
5. Return ONLY the JSON object, no explanations or code blocks

Return ONLY one command as a JSON object.
"""

class SimplePlotterStreamWorkflow(Workflow):
    """Simple workflow for controlling a pen plotter with sequential G-code commands.
    
    This workflow generates G-code commands one at a time, validates them,
    and sends them to the plotter (real or simulated).
    """
    
    max_retries: int = 3  # Maximum number of retry attempts per command
    max_steps: int = 50   # Maximum total steps to prevent infinite loops

    def __init__(self, llm: Any, plotter: Union[SimulatedPenPlotter, Any], *args, **kwargs):
        """Initialize the plotter workflow.
        
        Args:
            llm: The language model to use for command generation
            plotter: The plotter instance to use (real or simulated)
            *args: Additional arguments
            **kwargs: Additional keyword arguments
        """
        super().__init__(*args, **kwargs)
        self.llm = llm
        self.plotter = plotter

    @step
    async def start(self, ctx: Context, ev: StartEvent) -> Union[GenerateCommandEvent, StopEvent]:
        """Start the workflow, connect to plotter, and initialize context.
        
        Args:
            ctx: The workflow context
            ev: The start event
            
        Returns:
            GenerateCommandEvent or StopEvent
        """
        print(f"{Fore.CYAN}╔══════════════════════════════════════╗{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║     Plotter Workflow Initializing    ║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}╚══════════════════════════════════════╝{Style.RESET_ALL}")
        
        print(f"{Fore.CYAN}[*] ├── Initializing workflow{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   └── This step prepares the workflow by setting up context variables and parameters needed for G-code generation.{Style.RESET_ALL}")
        
        # Store workflow parameters in context
        print(f"{Fore.CYAN}[*] │   ├── Setting workflow parameters{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   │   └── Storing configuration values like max_retries and max_steps in the context for later use.{Style.RESET_ALL}")
        await ctx.set("max_retries", self.max_retries)
        await ctx.set("max_steps", getattr(ev, "max_steps", self.max_steps))
        
        # Initialize statistics
        print(f"{Fore.CYAN}[*] │   ├── Initializing statistics tracking{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   │   └── Setting up counters to track command execution success and failure rates throughout the workflow.{Style.RESET_ALL}")
        await ctx.set("commands", [])
        await ctx.set("commands_executed", 0)
        await ctx.set("success_count", 0)
        await ctx.set("failed_count", 0)
        
        # Store the drawing prompt
        print(f"{Fore.CYAN}[*] │   ├── Validating drawing prompt{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   │   └── Checking if a drawing prompt was provided, which is required to generate G-code commands.{Style.RESET_ALL}")
        if not hasattr(ev, "prompt"):
            print(f"{Fore.RED}[!] │   │       └── No drawing prompt specified - workflow stopped{Style.RESET_ALL}")
            return StopEvent(result="No drawing prompt specified")
        
        await ctx.set("prompt", ev.prompt)
        
        print(f"{Fore.GREEN}[+] │   ├── Workflow parameters initialized successfully{Style.RESET_ALL}")
        print(f"{Fore.GREEN}[+] │   ├── Drawing prompt: {ev.prompt}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}[+] │   ├── Max steps: {await ctx.get('max_steps')}{Style.RESET_ALL}")
        
        # Connect to plotter
        print(f"{Fore.CYAN}[*] │   ├── Connecting to plotter device{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   │   └── Establishing connection with the plotter (real or simulated) to prepare for command execution.{Style.RESET_ALL}")
        if not await self.plotter.connect():
            print(f"{Fore.RED}[!] │   │       └── Failed to connect to plotter - workflow stopped{Style.RESET_ALL}")
            return StopEvent(result="Failed to connect to plotter")
        
        print(f"{Fore.GREEN}[+] │   └── Successfully connected to plotter{Style.RESET_ALL}")
        
        # Start with step 1
        print(f"{Fore.CYAN}[*] └── Starting command generation sequence{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?]     └── Now that initialization is complete, the workflow will begin generating the first G-code command.{Style.RESET_ALL}")
        prompt = await ctx.get("prompt")
        return GenerateCommandEvent(prompt=prompt, step=1)
    
    @step
    async def generate_command(self, ctx: Context, ev: GenerateCommandEvent) -> CommandExtractionDone:
        """Generate the next G-code command for the plotter.
        
        Args:
            ctx: The workflow context
            ev: The generate command event
            
        Returns:
            CommandExtractionDone with raw LLM output
        """
        print(f"{Fore.CYAN}[*] ├── Generating command for step {ev.step}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   └── This step uses the LLM to generate the next G-code command based on the drawing prompt and previous commands.{Style.RESET_ALL}")
        
        # Track retries for this specific step
        task_key = f"retries_step_{ev.step}"
        current_retries = await ctx.get(task_key, default=0)
        max_retries = await ctx.get("max_retries")
        
        # Get command history
        print(f"{Fore.CYAN}[*] │   ├── Retrieving command history{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   │   └── Collecting previously executed commands to provide context for the LLM to generate the next command.{Style.RESET_ALL}")
        commands = await ctx.get("commands", default=[])
        history = "\n".join([f"Step {i+1}: {cmd.to_gcode()}" for i, cmd in enumerate(commands)])
        
        print(f"{Fore.YELLOW}[*] │   ├── Attempt {current_retries + 1}/{max_retries}{Style.RESET_ALL}")
        
        # Check if max retries exceeded
        if current_retries >= max_retries:
            print(f"{Fore.RED}[!] │   │   └── Maximum retries exceeded for step {ev.step}{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}[?] │   │       └── After multiple failed attempts, returning a COMPLETE command to gracefully terminate the workflow.{Style.RESET_ALL}")
            
            # Return a COMPLETE command to force termination
            fallback_result = json.dumps({"command": "COMPLETE"})
            
            return CommandExtractionDone(
                output=fallback_result,
                prompt=ev.prompt,
                step=ev.step
            )
        
        # Increment retry counter
        await ctx.set(task_key, current_retries + 1)
        
        # Build prompt for command generation
        print(f"{Fore.CYAN}[*] │   ├── Building LLM prompt{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   │   └── Creating a structured prompt with instructions, drawing requirements, and command history.{Style.RESET_ALL}")
        prompt = NEXT_COMMAND_TEMPLATE.format(
            prompt=ev.prompt,
            history=history if commands else "No previous commands"
        )
        
        # Generate command using the LLM
        print(f"{Fore.CYAN}[*] │   ├── Sending request to LLM{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   │   └── Querying the language model to generate the next G-code command based on the prompt.{Style.RESET_ALL}")
        response = self.llm.complete(prompt)
        
        print(f"{Fore.GREEN}[+] │   └── Command generation complete{Style.RESET_ALL}")
        
        return CommandExtractionDone(
            output=response.text,
            prompt=ev.prompt,
            step=ev.step
        )
    
    @step
    async def validate_command(self, ctx: Context, ev: Union[CommandExtractionDone, CommandValidationErrorEvent]) -> Union[CommandValidationErrorEvent, ValidatedCommandEvent]:
        """Validate the generated command.
        
        Args:
            ctx: The workflow context
            ev: The command extraction done event or validation error event
            
        Returns:
            CommandValidationErrorEvent if validation fails, ValidatedCommandEvent if successful
        """
        print(f"{Fore.CYAN}[*] ├── Validating command for step {ev.step}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   └── This step ensures the generated command is valid JSON and follows G-code formatting rules.{Style.RESET_ALL}")
        
        # If this is a validation error event, handle the retry
        if isinstance(ev, CommandValidationErrorEvent):
            # Build reflection prompt for retry
            print(f"{Fore.CYAN}[*] │   ├── Retrying with reflection after validation error{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}[?] │   │   └── Previous attempt failed validation, so we're sending the error details back to the LLM to help it correct the issues.{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}[!] │   │       └── Error: {ev.error}{Style.RESET_ALL}")
            
            prompt = REFLECTION_PROMPT.format(
                wrong_answer=ev.issues,
                error=ev.error
            )
            
            # Generate new command with reflection
            print(f"{Fore.CYAN}[*] │   │   ├── Sending reflection prompt to LLM{Style.RESET_ALL}")
            response = self.llm.complete(prompt)
            
            # Create new extraction done event
            ev = CommandExtractionDone(
                output=response.text,
                prompt=ev.prompt,
                step=ev.step
            )
        
        # Check retry status to show proper messaging
        task_key = f"retries_step_{ev.step}"
        current_retries = await ctx.get(task_key, default=0)
        max_retries = await ctx.get("max_retries")
        
        try:
            # Clean the output
            print(f"{Fore.CYAN}[*] │   ├── Cleaning LLM output{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}[?] │   │   └── Extracting the JSON object from the LLM response, removing any markdown or explanatory text.{Style.RESET_ALL}")
            output = ev.output.strip()
            
            # Remove any code blocks or extra text
            if "```json" in output:
                start = output.find("```json") + 7
                end = output.rfind("```")
                output = output[start:end].strip()
            elif "```" in output:
                start = output.find("```") + 3
                end = output.rfind("```")
                output = output[start:end].strip()
                
            # Find JSON object if there's extra text
            start = output.find("{")
            end = output.rfind("}") + 1
            
            if start < 0 or end <= start:
                raise ValueError("No valid JSON found in response")
                
            json_str = output[start:end]
            
            # Parse JSON 
            print(f"{Fore.CYAN}[*] │   ├── Parsing JSON data{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}[?] │   │   └── Converting the JSON string into a structured object and validating its format.{Style.RESET_ALL}")
            data = json.loads(json_str)
            
            # Create and validate command
            print(f"{Fore.CYAN}[*] │   ├── Creating GCodeCommand object{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}[?] │   │   └── Instantiating a GCodeCommand object which will validate the command structure and parameters.{Style.RESET_ALL}")
            command = GCodeCommand(**data)
            
            # Check if this is a completion command
            is_complete = command.command == "COMPLETE"
            
            print(f"{Fore.GREEN}[+] │   ├── Command validation successful{Style.RESET_ALL}")
            print(f"{Fore.GREEN}[+] │   ├── Command: {command.to_gcode()}{Style.RESET_ALL}")
            
            if is_complete:
                print(f"{Fore.GREEN}[+] │   └── Reached completion command{Style.RESET_ALL}")
            
            return ValidatedCommandEvent(
                command=command,
                prompt=ev.prompt,
                step=ev.step,
                is_complete=is_complete
            )
            
        except Exception as e:
            print(f"{Fore.RED}[!] │   ├── Command validation failed{Style.RESET_ALL}")
            print(f"{Fore.RED}[!] │   ├── Error: {str(e)}{Style.RESET_ALL}")
            
            # More detailed error information based on retry count
            if current_retries >= max_retries:
                print(f"{Fore.RED}[!] │   └── Final attempt failed - Validation errors persist after {current_retries} attempts{Style.RESET_ALL}")
                print(f"{Fore.YELLOW}[?]     └── After exhausting all retry attempts, the workflow will need to handle this failure gracefully.{Style.RESET_ALL}")
            else:
                print(f"{Fore.YELLOW}[!] │   └── Retrying - Attempt {current_retries}/{max_retries} failed{Style.RESET_ALL}")
                print(f"{Fore.YELLOW}[?]     └── The validation will be retried with additional error context to help the LLM correct its output.{Style.RESET_ALL}")
            
            return CommandValidationErrorEvent(
                error=str(e),
                issues=ev.output,
                prompt=ev.prompt,
                step=ev.step
            )
    
    @step
    async def execute_command(self, ctx: Context, ev: ValidatedCommandEvent) -> CommandExecutedEvent:
        """Execute the validated command on the plotter.
        
        Args:
            ctx: The workflow context
            ev: The validated command event
            
        Returns:
            CommandExecutedEvent with execution results
        """
        print(f"{Fore.CYAN}[*] ├── Executing command for step {ev.step}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   └── This step sends the validated G-code command to the plotter device for execution.{Style.RESET_ALL}")
        
        # Get the current command lists and stats
        print(f"{Fore.CYAN}[*] │   ├── Retrieving execution statistics{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   │   └── Gathering current execution metrics to update after this command is processed.{Style.RESET_ALL}")
        commands = await ctx.get("commands", default=[])
        commands_executed = await ctx.get("commands_executed", default=0)
        success_count = await ctx.get("success_count", default=0)
        failed_count = await ctx.get("failed_count", default=0)
        
        # Check if this is a completion command
        if ev.is_complete:
            print(f"{Fore.GREEN}[+] │   └── Drawing complete, no command to execute{Style.RESET_ALL}")
            
            return CommandExecutedEvent(
                prompt=ev.prompt,
                step=ev.step,
                command=ev.command,
                is_complete=True,
                success=True
            )
        
        # Add command to history
        print(f"{Fore.CYAN}[*] │   ├── Adding command to history{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   │   └── Storing the command in the context to provide history for future command generation.{Style.RESET_ALL}")
        commands.append(ev.command)
        await ctx.set("commands", commands)
        
        # Format command for plotter
        print(f"{Fore.CYAN}[*] │   ├── Formatting command for plotter{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   │   └── Converting the GCodeCommand object to a string format that the plotter can understand.{Style.RESET_ALL}")
        gcode = ev.command.to_gcode()
        
        # Send command to plotter
        print(f"{Fore.CYAN}[*] │   ├── Sending command to plotter{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   │   └── Transmitting the G-code command to the plotter device for physical execution.{Style.RESET_ALL}")
        success = await self.plotter.send_command(gcode)
        
        # Update statistics
        print(f"{Fore.CYAN}[*] │   ├── Updating execution statistics{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   │   └── Recording the result of this command execution for workflow metrics.{Style.RESET_ALL}")
        await ctx.set("commands_executed", commands_executed + 1)
        if success:
            await ctx.set("success_count", success_count + 1)
            print(f"{Fore.GREEN}[+] │   ├── Command executed successfully{Style.RESET_ALL}")
        else:
            await ctx.set("failed_count", failed_count + 1)
            print(f"{Fore.RED}[!] │   ├── Failed to execute command{Style.RESET_ALL}")
        
        # Add small delay between commands
        print(f"{Fore.CYAN}[*] │   └── Adding delay between commands{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?]     └── A short pause helps ensure the plotter has time to complete the current command before receiving the next one.{Style.RESET_ALL}")
        await asyncio.sleep(self.plotter.command_delay)
        
        return CommandExecutedEvent(
            prompt=ev.prompt,
            step=ev.step,
            command=ev.command,
            is_complete=False,
            success=success
        )
    
    @step
    async def process_result(self, ctx: Context, ev: CommandExecutedEvent) -> Union[GenerateCommandEvent, PlotterCompleteEvent]:
        """Process the command execution result and decide next steps.
        
        Args:
            ctx: The workflow context
            ev: The command executed event
            
        Returns:
            GenerateCommandEvent for next command or PlotterCompleteEvent if done
        """
        print(f"{Fore.CYAN}[*] ├── Processing result for step {ev.step}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   └── This step evaluates the execution result and determines whether to continue with the next command or complete the workflow.{Style.RESET_ALL}")
        
        # Get statistics
        print(f"{Fore.CYAN}[*] │   ├── Retrieving current workflow statistics{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   │   └── Gathering metrics to evaluate workflow progress and make decisions about next steps.{Style.RESET_ALL}")
        commands_executed = await ctx.get("commands_executed", default=0)
        success_count = await ctx.get("success_count", default=0)
        failed_count = await ctx.get("failed_count", default=0)
        
        # Check completion conditions
        print(f"{Fore.CYAN}[*] │   ├── Checking completion conditions{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   │   └── Evaluating whether the workflow should continue or terminate based on command status and step count.{Style.RESET_ALL}")
        if ev.is_complete:
            print(f"{Fore.GREEN}[+] │   │   └── Drawing complete via COMPLETE command{Style.RESET_ALL}")
            return PlotterCompleteEvent(
                prompt=ev.prompt,
                commands_executed=commands_executed,
                step_count=ev.step
            )
            
        # Check max steps
        max_steps = await ctx.get("max_steps")
        if ev.step >= max_steps:
            print(f"{Fore.YELLOW}[!] │   │   └── Reached maximum steps ({max_steps}){Style.RESET_ALL}")
            return PlotterCompleteEvent(
                prompt=ev.prompt,
                commands_executed=commands_executed,
                step_count=ev.step
            )
            
        # Check if execution failed - we'll still continue but log the failure
        if not ev.success:
            print(f"{Fore.YELLOW}[!] │   │   └── Command execution failed but continuing{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}[?] │   │       └── Despite the execution failure, the workflow will proceed to generate the next command.{Style.RESET_ALL}")
        
        # Continue to next step
        next_step = ev.step + 1
        print(f"{Fore.GREEN}[+] │   ├── Continuing to step {next_step}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}[+] │   └── Stats: {commands_executed} commands, {success_count} successful, {failed_count} failed{Style.RESET_ALL}")
        
        return GenerateCommandEvent(
            prompt=ev.prompt,
            step=next_step
        )
    
    @step
    async def end(self, ctx: Context, ev: PlotterCompleteEvent) -> StopEvent:
        """End the workflow, disconnect from plotter, and return results.
        
        Args:
            ctx: The workflow context
            ev: The plotter complete event
            
        Returns:
            StopEvent with final results
        """
        print(f"{Fore.CYAN}╔══════════════════════════════════════╗{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║      Plotter Workflow Complete       ║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}╚══════════════════════════════════════╝{Style.RESET_ALL}")
        
        print(f"{Fore.CYAN}[*] ├── Finalizing workflow{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   └── This step wraps up the workflow by collecting final statistics, saving results, and cleaning up resources.{Style.RESET_ALL}")
        
        # Get statistics
        print(f"{Fore.CYAN}[*] │   ├── Collecting final statistics{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   │   └── Gathering all execution metrics to provide a comprehensive summary of the workflow run.{Style.RESET_ALL}")
        commands = await ctx.get("commands", default=[])
        success_count = await ctx.get("success_count", default=0)
        failed_count = await ctx.get("failed_count", default=0)
        
        print(f"{Fore.GREEN}[+] │   ├── Drawing prompt: {ev.prompt}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}[+] │   ├── Commands executed: {ev.commands_executed}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}[+] │   ├── Successful commands: {success_count}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}[+] │   ├── Failed commands: {failed_count}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}[+] │   ├── Steps taken: {ev.step_count}{Style.RESET_ALL}")
        
        # Create program from commands
        if commands:
            print(f"{Fore.CYAN}[*] │   ├── Creating complete G-code program{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}[?] │   │   └── Combining all individual commands into a complete G-code program that can be saved or reused.{Style.RESET_ALL}")
            program = GCodeProgram(commands=commands)
            gcode_text = program.to_gcode()
            
            # Save to file
            print(f"{Fore.CYAN}[*] │   ├── Saving G-code to file{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}[?] │   │   └── Writing the complete G-code program to a timestamped file for future reference or use.{Style.RESET_ALL}")
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"plotter_gcode_{timestamp}.txt"
            try:
                with open(filename, 'w') as f:
                    f.write(gcode_text)
                print(f"{Fore.GREEN}[+] │   │   └── G-code saved to {filename}{Style.RESET_ALL}")
            except Exception as e:
                print(f"{Fore.RED}[!] │   │   └── Failed to save G-code to file: {str(e)}{Style.RESET_ALL}")
        
        # Disconnect from plotter
        print(f"{Fore.CYAN}[*] │   ├── Disconnecting from plotter{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   │   └── Properly closing the connection to the plotter device to release resources.{Style.RESET_ALL}")
        await self.plotter.disconnect()
        print(f"{Fore.GREEN}[+] │   └── Disconnected from plotter{Style.RESET_ALL}")
        
        # Return final result
        print(f"{Fore.CYAN}[*] └── Preparing final result{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?]     └── Creating a structured result object containing all workflow metrics and outcomes.{Style.RESET_ALL}")
        result = {
            "prompt": ev.prompt,
            "commands_count": len(commands),
            "commands_executed": ev.commands_executed,
            "success_count": success_count,
            "failed_count": failed_count,
            "step_count": ev.step_count,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        return StopEvent(result=result)

async def run_plotter_workflow(prompt: str, model_name: str = "llama3.2:3b", max_steps: int = 30, 
                              simulation: bool = True, interactive_viz: bool = True,
                              port: str = "SIMULATED"):
    """Run the plotter workflow with a given prompt."""
    try:
        # Create LLM instance
        llm = Ollama(model=model_name, request_timeout=10000)

        from llama_index.llms.azure_openai import AzureOpenAI

        import os
        
        llm = AzureOpenAI(
                    model="gpt-4o",
                    deployment_name="gpt-4o-gs",
                    api_key=os.environ.get("GPT4_API_KEY"),
                    api_version=os.environ.get("GPT4_API_VERSION"),
                    azure_endpoint=os.environ.get("GPT4_ENDPOINT"),
                    timeout=1220,)
        
        # Create plotter (real or simulated)
        if simulation:
            plotter = SimulatedPenPlotter(port=port, visualize=interactive_viz)
        else:
            # Use a real plotter with the provided port
            # Default baud rate is 115200, adjust if your plotter uses a different rate
            plotter = RealPenPlotter(port=port, baud_rate=115200)

        # Create workflow
        workflow = SimplePlotterStreamWorkflow(llm=llm, plotter=plotter, timeout=10000, verbose=True)

        # Generate workflow visualization
        from llama_index.utils.workflow import draw_all_possible_flows

        draw_all_possible_flows(
            SimplePlotterStreamWorkflow, filename="gcode_workflow_streamer_simple.html"
        )
        
        # Run workflow
        result = await workflow.run(prompt=prompt, max_steps=max_steps)
        
        return result
        
    except Exception as e:
        print(f"{Fore.RED}Error running workflow: {str(e)}{Style.RESET_ALL}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}

async def main():
    """Main entry point for the application."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='G-code Generation Workflow with Plotter Simulation')
    parser.add_argument('--prompt', type=str, default='draw a small house with a door and windows',
                        help='Drawing prompt for the plotter')
    parser.add_argument('--model', type=str, default='llama3.2:3b',
                        help='Ollama model to use for generation')
    parser.add_argument('--max-steps', type=int, default=30,
                        help='Maximum number of steps to generate')
    parser.add_argument('--no-simulation', action='store_true',
                        help='Disable simulation mode (will try to connect to a real plotter)')
    parser.add_argument('--no-visualization', action='store_true',
                        help='Disable interactive visualization')
    parser.add_argument('--port', type=str, default='/dev/ttyUSB0',
                        help='Serial port for real plotter (only used if --no-simulation is set)')
    
    # python llm_stream_simple.py --no-simulation --port /dev/tty.usbserial-14220 --max-steps 300
    
    args = parser.parse_args()
    
    # Print configuration
    print(f"{Fore.CYAN}╔══════════════════════════════════════╗{Style.RESET_ALL}")
    print(f"{Fore.CYAN}║   G-code Plotter Workflow Starter    ║{Style.RESET_ALL}")
    print(f"{Fore.CYAN}╚══════════════════════════════════════╝{Style.RESET_ALL}")
    print(f"{Fore.CYAN}[*] Configuration:{Style.RESET_ALL}")
    print(f"{Fore.CYAN}[*] Prompt: {args.prompt}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}[*] Model: {args.model}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}[*] Max Steps: {args.max_steps}{Style.RESET_ALL}")
    
    if args.no_simulation:
        print(f"{Fore.CYAN}[*] Mode: Real Plotter{Style.RESET_ALL}")
        print(f"{Fore.CYAN}[*] Port: {args.port}{Style.RESET_ALL}")
    else:
        print(f"{Fore.CYAN}[*] Mode: Simulated Plotter{Style.RESET_ALL}")
        print(f"{Fore.CYAN}[*] Visualization: {'Disabled' if args.no_visualization else 'Enabled'}{Style.RESET_ALL}")
    
    # Run the workflow
    result = await run_plotter_workflow(
        prompt=args.prompt,
        model_name=args.model,
        max_steps=args.max_steps,
        simulation=not args.no_simulation,
        interactive_viz=not args.no_visualization,
        port=args.port
    )
    
    # Print summary
    if "error" not in result:
        print(f"\n{Fore.GREEN}[+] Workflow completed successfully{Style.RESET_ALL}")
        print(f"{Fore.GREEN}[+] Generated {result.get('commands_count', 0)} commands{Style.RESET_ALL}")
        print(f"{Fore.GREEN}[+] Executed {result.get('commands_executed', 0)} commands{Style.RESET_ALL}")
        print(f"{Fore.GREEN}[+] Success: {result.get('success_count', 0)}, Failed: {result.get('failed_count', 0)}{Style.RESET_ALL}")
    else:
        print(f"\n{Fore.RED}[!] Workflow failed: {result['error']}{Style.RESET_ALL}")

if __name__ == "__main__":
    asyncio.run(main())