import asyncio
import logging
from dataclasses import dataclass
from typing import Optional, Dict, List, Union, Any, Tuple, AsyncGenerator
import time
from collections import deque
import json
import random
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
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle
import numpy as np
import os
import argparse

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

# Base Plotter Interface
class BasePlotter:
    """Base interface for all plotter implementations"""
    
    async def connect(self) -> bool:
        """Connect to the plotter"""
        raise NotImplementedError()
    
    async def disconnect(self):
        """Disconnect from the plotter"""
        raise NotImplementedError()
    
    async def send_command(self, command: str) -> bool:
        """Send a command to the plotter"""
        raise NotImplementedError()
    
    def format_command(self, command_dict: Dict[str, Any]) -> str:
        """Format a command dictionary as a G-code string"""
        raise NotImplementedError()
    
    async def __aenter__(self):
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc, tb):
        await self.disconnect()

@dataclass
class PlotterStatus:
    """Tracks the current status of the plotter"""
    is_busy: bool = False
    current_command: Optional[str] = None
    last_response: Optional[str] = None
    queue_size: int = 0
    last_update: float = time.time()

class PenPlotter(BasePlotter):
    """Manages the plotter connection and command streaming"""
    
    def __init__(self, port: str, baud_rate: int = 115200, buffer_size: int = 5):
        self.port = port
        self.baud_rate = baud_rate
        self.reader = None
        self.writer = None
        self.command_queue = deque(maxlen=buffer_size)
        self.status = PlotterStatus()
        self.command_delay = 0.1
        self._active = False
        self.command_history = []

    async def connect(self) -> bool:
        """Establish connection with the plotter"""
        try:
            from serial_asyncio import open_serial_connection
            print(f"{Fore.YELLOW}Connecting to plotter on {self.port}...{Style.RESET_ALL}")
            self.reader, self.writer = await open_serial_connection(
                url=self.port, baudrate=self.baud_rate
            )
            self._active = True
            print(f"{Fore.GREEN}Successfully connected to plotter!{Style.RESET_ALL}")
            return True
        except Exception as e:
            print(f"{Fore.RED}Failed to connect: {str(e)}{Style.RESET_ALL}")
            return False

    async def disconnect(self):
        """Disconnect from the plotter"""
        if self.writer:
            print(f"{Fore.YELLOW}Disconnecting from plotter...{Style.RESET_ALL}")
            self.writer.close()
            await self.writer.wait_closed()
            self._active = False
            print(f"{Fore.GREEN}Disconnected successfully{Style.RESET_ALL}")

    async def send_command(self, command: str) -> bool:
        """Send a single command and wait for response"""
        if not self._active:
            print(f"{Fore.RED}Not connected to plotter{Style.RESET_ALL}")
            return False

        try:
            print(f"{Fore.BLUE}Sending: {command}{Style.RESET_ALL}")
            self.writer.write(f"{command}\n".encode())
            await self.writer.drain()
            
            response = await asyncio.wait_for(self.reader.readline(), timeout=5.0)
            response_text = response.decode().strip()
            print(f"{Fore.GREEN}Response: {response_text}{Style.RESET_ALL}")
            
            return response_text == 'ok'
        except asyncio.TimeoutError:
            print(f"{Fore.RED}Timeout waiting for plotter response{Style.RESET_ALL}")
            return False
        except Exception as e:
            print(f"{Fore.RED}Error sending command: {str(e)}{Style.RESET_ALL}")
            return False
            
    def format_command(self, command_dict: Dict[str, Any]) -> str:
        """Convert command dict to G-code string"""
        if command_dict.get("command") == "COMPLETE":
            return "COMPLETE"
            
        gcode = command_dict["command"]
        for key, value in command_dict.items():
            if key != "command" and value is not None:
                gcode += f" {key.upper()}{value}"
        return gcode
        
    def add_to_history(self, command: Dict[str, Any]):
        """Add a command to history"""
        self.command_history.append(command)

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

class SimulatedPlotter(BasePlotter):
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
6. Feed rate (f) and speed (s) should be integers

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

class StreamCommandsEvent(Event):
    """Event to stream G-code commands to the plotter."""
    prompt: str = Field(description="Drawing prompt")

class CommandStreamingCompleteEvent(Event):
    """Event indicating command streaming is complete."""
    prompt: str = Field(description="Drawing prompt that was completed")
    commands_executed: int = Field(description="Number of commands executed")
    commands: List[GCodeCommand] = Field(description="All executed commands")

class CommandStreamPredictor:
    """Handles streaming predictions from LLM and validation"""
    
    def __init__(self, llm: Ollama):
        self.llm = llm
    
    async def stream_commands(self, prompt: str, history: List[str] = None) -> AsyncGenerator[GCodeCommand, None]:
        """Stream commands using LLM with validation"""
        template = """
        Create G-code commands for a pen plotter based on this prompt: {prompt}
        
        Previous commands:
        {history}
        
        Rules:
        1. Use G0 for rapid movements (no drawing)
        2. Use G1 for drawing lines with feed rate (f)
        3. Use M3/M5 for pen up/down (s value should be 0-255)
        4. Use only commands: G0, G1, M3, M5
        5. All coordinates (x, y, z) should be float numbers
        6. Feed rate (f) and speed (s) should be integers
        
        Generate one command at a time, formatted as JSON:
        {{"command": "G0", "x": 0.0, "y": 0.0, "z": 5.0}}
        
        When the drawing is complete, output:
        {{"command": "COMPLETE"}}
        
        Return only the JSON objects, no additional text.
        """
        
        history_text = "\n".join(history) if history else "No previous commands"
        
        response_stream = await self.llm.astream_complete(template.format(
            prompt=prompt,
            history=history_text
        ))
        
        buffer = ""
        
        async for chunk in response_stream:
            buffer += chunk.text
            
            # Try to find complete JSON objects
            start_idx = 0
            while True:
                # Find opening and closing braces
                start = buffer.find("{", start_idx)
                if start == -1:
                    break
                    
                # Find matching closing brace
                brace_count = 1
                end = start + 1
                while end < len(buffer) and brace_count > 0:
                    if buffer[end] == "{":
                        brace_count += 1
                    elif buffer[end] == "}":
                        brace_count -= 1
                    end += 1
                
                if brace_count > 0:
                    # Unmatched braces, wait for more chunks
                    break
                
                # Extract potentially valid JSON
                json_str = buffer[start:end]
                
                try:
                    command_data = json.loads(json_str)
                    
                    # Validate with GCodeCommand
                    command = GCodeCommand(**command_data)
                    
                    print(f"{Fore.CYAN}Generated command: {command.to_gcode()}{Style.RESET_ALL}")
                    
                    # Yield valid command
                    yield command
                    
                    # Remove processed part from buffer
                    buffer = buffer[end:]
                    
                    # Reset start_idx for next search
                    start_idx = 0
                    
                    # Break if this was a COMPLETE command
                    if command.command == "COMPLETE":
                        return
                    
                except (json.JSONDecodeError, ValueError) as e:
                    # Invalid JSON or validation error, move to next potential JSON object
                    print(f"{Fore.YELLOW}Skipping invalid command: {e}{Style.RESET_ALL}")
                    start_idx = start + 1

class SimplePlotterWorkflow(Workflow):
    """Simple workflow for controlling a pen plotter with sequential G-code commands.
    
    This workflow follows a step-by-step approach:
    1. Generate a command
    2. Validate the command
    3. Execute the command on the plotter
    4. Decide whether to generate another command or complete the drawing
    
    Key features:
    - One command at a time generation with context from previous commands
    - Robust validation and error recovery
    - Automatic retries with reflection on errors
    """
    
    max_retries: int = 3  # Maximum number of retry attempts per command
    max_steps: int = 50   # Maximum total steps to prevent infinite loops

    def __init__(self, llm: Any, plotter: BasePlotter, *args, **kwargs):
        """Initialize the plotter workflow.
        
        Args:
            llm: The language model to use for command generation
            plotter: The plotter instance to use
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
        
        # Store workflow parameters in context
        await ctx.set("max_retries", self.max_retries)
        await ctx.set("max_steps", getattr(ev, "max_steps", self.max_steps))
        
        # Initialize statistics
        await ctx.set("commands", [])
        await ctx.set("commands_executed", 0)
        await ctx.set("success_count", 0)
        await ctx.set("failed_count", 0)
        
        # Store the drawing prompt
        if not hasattr(ev, "prompt"):
            print(f"{Fore.RED}No drawing prompt specified - workflow stopped{Style.RESET_ALL}")
            return StopEvent(result="No drawing prompt specified")
        
        await ctx.set("prompt", ev.prompt)
        
        print(f"{Fore.GREEN}[+] Workflow initialized{Style.RESET_ALL}")
        print(f"{Fore.GREEN}[+] Drawing prompt: {ev.prompt}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}[+] Max steps: {await ctx.get('max_steps')}{Style.RESET_ALL}")
        
        # Connect to plotter
        if not await self.plotter.connect():
            print(f"{Fore.RED}Failed to connect to plotter - workflow stopped{Style.RESET_ALL}")
            return StopEvent(result="Failed to connect to plotter")
        
        print(f"{Fore.GREEN}[+] Successfully connected to plotter{Style.RESET_ALL}")
        
        # Start with step 1
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
        # Track retries for this specific step
        task_key = f"retries_step_{ev.step}"
        current_retries = await ctx.get(task_key, default=0)
        max_retries = await ctx.get("max_retries")
        
        # Get command history
        commands = await ctx.get("commands", default=[])
        history = "\n".join([f"Step {i+1}: {cmd.to_gcode()}" for i, cmd in enumerate(commands)])
        
        print(f"{Fore.CYAN}[*] Generating command for step {ev.step}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[*] Attempt {current_retries + 1}/{max_retries}{Style.RESET_ALL}")
        
        # Check if max retries exceeded
        if current_retries >= max_retries:
            print(f"{Fore.RED}[!] Maximum retries exceeded for step {ev.step}{Style.RESET_ALL}")
            
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
        prompt = NEXT_COMMAND_TEMPLATE.format(
            prompt=ev.prompt,
            history=history if commands else "No previous commands"
        )
        
        # Generate command using the LLM
        response = await self.llm.acomplete(prompt)
        
        print(f"{Fore.GREEN}[+] Command generation complete{Style.RESET_ALL}")
        
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
        # If this is a validation error event, handle the retry
        if isinstance(ev, CommandValidationErrorEvent):
            # Build reflection prompt for retry
            prompt = REFLECTION_PROMPT.format(
                wrong_answer=ev.issues,
                error=ev.error
            )
            
            print(f"{Fore.YELLOW}[!] Retrying with reflection after validation error{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}[!] Error: {ev.error}{Style.RESET_ALL}")
            
            # Generate new command with reflection
            response = await self.llm.acomplete(prompt)
            
            # Create new extraction done event
            ev = CommandExtractionDone(
                output=response.text,
                prompt=ev.prompt,
                step=ev.step
            )
        
        print(f"{Fore.CYAN}[*] Validating command for step {ev.step}{Style.RESET_ALL}")
        
        # Check retry status to show proper messaging
        task_key = f"retries_step_{ev.step}"
        current_retries = await ctx.get(task_key, default=0)
        max_retries = await ctx.get("max_retries")
        
        try:
            # Clean the output
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
            data = json.loads(json_str)
            
            # Create and validate command
            command = GCodeCommand(**data)
            
            # Check if this is a completion command
            is_complete = command.command == "COMPLETE"
            
            print(f"{Fore.GREEN}[+] Command validation successful{Style.RESET_ALL}")
            print(f"{Fore.GREEN}[+] Command: {command.to_gcode()}{Style.RESET_ALL}")
            
            if is_complete:
                print(f"{Fore.GREEN}[+] Reached completion command{Style.RESET_ALL}")
            
            return ValidatedCommandEvent(
                command=command,
                prompt=ev.prompt,
                step=ev.step,
                is_complete=is_complete
            )
            
        except Exception as e:
            print(f"{Fore.RED}[!] Command validation failed{Style.RESET_ALL}")
            print(f"{Fore.RED}[!] Error: {str(e)}{Style.RESET_ALL}")
            
            # More detailed error information based on retry count
            if current_retries >= max_retries:
                print(f"{Fore.RED}[!] Final attempt failed - Validation errors persist after {current_retries} attempts{Style.RESET_ALL}")
            else:
                print(f"{Fore.YELLOW}[!] Retrying - Attempt {current_retries}/{max_retries} failed{Style.RESET_ALL}")
            
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
        print(f"{Fore.CYAN}[*] Executing command for step {ev.step}{Style.RESET_ALL}")
        
        # Get the current command lists and stats
        commands = await ctx.get("commands", default=[])
        commands_executed = await ctx.get("commands_executed", default=0)
        success_count = await ctx.get("success_count", default=0)
        failed_count = await ctx.get("failed_count", default=0)
        
        # Check if this is a completion command
        if ev.is_complete:
            print(f"{Fore.GREEN}[+] Drawing complete, no command to execute{Style.RESET_ALL}")
            
            return CommandExecutedEvent(
                prompt=ev.prompt,
                step=ev.step,
                command=ev.command,
                is_complete=True,
                success=True
            )
        
        # Add command to history
        commands.append(ev.command)
        await ctx.set("commands", commands)
        
        # Format command for plotter
        gcode = ev.command.to_gcode()
        
        # Send command to plotter
        success = await self.plotter.send_command(gcode)
        
        # Update statistics
        await ctx.set("commands_executed", commands_executed + 1)
        if success:
            await ctx.set("success_count", success_count + 1)
            print(f"{Fore.GREEN}[+] Command executed successfully{Style.RESET_ALL}")
        else:
            await ctx.set("failed_count", failed_count + 1)
            print(f"{Fore.RED}[!] Failed to execute command{Style.RESET_ALL}")
        
        # Add small delay between commands
        await asyncio.sleep(0.1)
        
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
        print(f"{Fore.CYAN}[*] Processing result for step {ev.step}{Style.RESET_ALL}")
        
        # Get statistics
        commands_executed = await ctx.get("commands_executed", default=0)
        success_count = await ctx.get("success_count", default=0)
        failed_count = await ctx.get("failed_count", default=0)
        
        # Check completion conditions
        if ev.is_complete:
            print(f"{Fore.GREEN}[+] Drawing complete via COMPLETE command{Style.RESET_ALL}")
            return PlotterCompleteEvent(
                prompt=ev.prompt,
                commands_executed=commands_executed,
                step_count=ev.step
            )
            
        # Check max steps
        max_steps = await ctx.get("max_steps")
        if ev.step >= max_steps:
            print(f"{Fore.YELLOW}[!] Reached maximum steps ({max_steps}){Style.RESET_ALL}")
            return PlotterCompleteEvent(
                prompt=ev.prompt,
                commands_executed=commands_executed,
                step_count=ev.step
            )
            
        # Check if execution failed - we'll still continue but log the failure
        if not ev.success:
            print(f"{Fore.YELLOW}[!] Command execution failed but continuing{Style.RESET_ALL}")
        
        # Continue to next step
        next_step = ev.step + 1
        print(f"{Fore.GREEN}[+] Continuing to step {next_step}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}[+] Stats: {commands_executed} commands, {success_count} successful, {failed_count} failed{Style.RESET_ALL}")
        
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
        
        # Get statistics
        commands = await ctx.get("commands", default=[])
        success_count = await ctx.get("success_count", default=0)
        failed_count = await ctx.get("failed_count", default=0)
        
        print(f"{Fore.GREEN}[+] Drawing prompt: {ev.prompt}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}[+] Commands executed: {ev.commands_executed}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}[+] Successful commands: {success_count}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}[+] Failed commands: {failed_count}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}[+] Steps taken: {ev.step_count}{Style.RESET_ALL}")
        
        # Create program from commands
        if commands:
            program = GCodeProgram(commands=commands)
            gcode_text = program.to_gcode()
            
            # Save to file
            filename = f"plotter_gcode_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            try:
                with open(filename, 'w') as f:
                    f.write(gcode_text)
                print(f"{Fore.GREEN}[+] G-code saved to {filename}{Style.RESET_ALL}")
            except Exception as e:
                print(f"{Fore.RED}[!] Failed to save G-code to file: {str(e)}{Style.RESET_ALL}")
                
            # Check if we have a simulated plotter and visualize the drawing
            if isinstance(self.plotter, SimulatedPlotter):
                try:
                    viz_filename = f"plotter_visualization_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                    self.plotter.visualize_drawing(output_file=viz_filename, show=True)
                except Exception as e:
                    print(f"{Fore.RED}[!] Failed to visualize drawing: {str(e)}{Style.RESET_ALL}")
        
        # Disconnect from plotter
        await self.plotter.disconnect()
        print(f"{Fore.GREEN}[+] Disconnected from plotter{Style.RESET_ALL}")
        
        # Return final result
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

class AdvancedPlotterWorkflow(Workflow):
    """Advanced workflow for streaming G-code commands directly to a pen plotter.
    
    This workflow uses streaming LLM output to generate commands in real-time
    and validates them before sending to the plotter, providing more efficient
    command generation with less overhead between steps.
    
    Key features:
    - Real-time streaming of commands directly from the LLM
    - On-the-fly validation and error handling
    - Efficient processing without waiting for complete generation
    """
    
    max_commands: int = 100  # Maximum number of commands to generate

    def __init__(self, llm: Any, plotter: BasePlotter, *args, **kwargs):
        """Initialize the streamer workflow.
        
        Args:
            llm: The language model to use for command generation
            plotter: The plotter instance to use
            *args: Additional arguments
            **kwargs: Additional keyword arguments
        """
        super().__init__(*args, **kwargs)
        self.llm = llm
        self.plotter = plotter

    @step
    async def start(self, ctx: Context, ev: StartEvent) -> Union[StreamCommandsEvent, StopEvent]:
        """Start the workflow and connect to plotter.
        
        Args:
            ctx: The workflow context
            ev: The start event
            
        Returns:
            StreamCommandsEvent or StopEvent
        """
        print(f"{Fore.CYAN}╔═══════════════════════════════════════════════╗{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║    Streaming Plotter Workflow Initializing    ║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}╚═══════════════════════════════════════════════╝{Style.RESET_ALL}")
        
        # Store workflow parameters
        await ctx.set("max_commands", getattr(ev, "max_commands", self.max_commands))
        
        # Store the drawing prompt
        if not hasattr(ev, "prompt"):
            print(f"{Fore.RED}No drawing prompt specified - workflow stopped{Style.RESET_ALL}")
            return StopEvent(result="No drawing prompt specified")
        
        await ctx.set("prompt", ev.prompt)
        
        print(f"{Fore.GREEN}[+] Workflow initialized{Style.RESET_ALL}")
        print(f"{Fore.GREEN}[+] Drawing prompt: {ev.prompt}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}[+] Max commands: {await ctx.get('max_commands')}{Style.RESET_ALL}")
        
        # Connect to plotter
        if not await self.plotter.connect():
            print(f"{Fore.RED}Failed to connect to plotter - workflow stopped{Style.RESET_ALL}")
            return StopEvent(result="Failed to connect to plotter")
        
        print(f"{Fore.GREEN}[+] Successfully connected to plotter{Style.RESET_ALL}")
        
        # Start streaming commands
        prompt = await ctx.get("prompt")
        return StreamCommandsEvent(prompt=prompt)
    
    @step
    async def stream_commands(self, ctx: Context, ev: StreamCommandsEvent) -> CommandStreamingCompleteEvent:
        """Stream commands to the plotter with direct validation.
        
        Args:
            ctx: The workflow context
            ev: The stream commands event
            
        Returns:
            CommandStreamingCompleteEvent when done
        """
        print(f"{Fore.CYAN}[*] Starting command streaming for prompt: {ev.prompt}{Style.RESET_ALL}")
        
        # Create command predictor
        predictor = CommandStreamPredictor(self.llm)
        
        # Track statistics
        commands_executed = 0
        success_count = 0
        failed_count = 0
        commands = []
        command_history = []
        max_commands = await ctx.get("max_commands")
        
        try:
            # Stream commands from LLM
            async for command in predictor.stream_commands(ev.prompt, command_history):
                # Check if we've reached the max commands
                if commands_executed >= max_commands:
                    print(f"{Fore.YELLOW}[!] Reached maximum command limit ({max_commands}){Style.RESET_ALL}")
                    break
                
                # Check if this is a completion command
                if command.command == "COMPLETE":
                    print(f"{Fore.GREEN}[+] Received COMPLETE command, finishing drawing{Style.RESET_ALL}")
                    break
                
                # Add command to history
                commands.append(command)
                command_history.append(f"Step {len(commands)}: {command.to_gcode()}")
                
                # Format command for plotter
                gcode = command.to_gcode()
                
                # Send command to plotter
                success = await self.plotter.send_command(gcode)
                commands_executed += 1
                
                if success:
                    success_count += 1
                    print(f"{Fore.GREEN}[+] Command executed successfully ({commands_executed}/{max_commands}){Style.RESET_ALL}")
                else:
                    failed_count += 1
                    print(f"{Fore.RED}[!] Failed to execute command ({commands_executed}/{max_commands}){Style.RESET_ALL}")
                
                # Add small delay between commands
                await asyncio.sleep(0.1)
        
        except Exception as e:
            print(f"{Fore.RED}[!] Error during command streaming: {str(e)}{Style.RESET_ALL}")
        
        # Print summary
        print(f"{Fore.CYAN}[*] Command streaming complete{Style.RESET_ALL}")
        print(f"{Fore.CYAN}[*] Commands executed: {commands_executed}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}[*] Successful: {success_count}, Failed: {failed_count}{Style.RESET_ALL}")
        
        # Save commands to file
        if commands:
            program = GCodeProgram(commands=commands)
            gcode_text = program.to_gcode()
            
            filename = f"streamed_gcode_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            try:
                with open(filename, 'w') as f:
                    f.write(gcode_text)
                print(f"{Fore.GREEN}[+] G-code saved to {filename}{Style.RESET_ALL}")
            except Exception as e:
                print(f"{Fore.RED}[!] Failed to save G-code to file: {str(e)}{Style.RESET_ALL}")
        
        return CommandStreamingCompleteEvent(
            prompt=ev.prompt,
            commands_executed=commands_executed,
            commands=commands
        )
    
    @step
    async def end(self, ctx: Context, ev: CommandStreamingCompleteEvent) -> StopEvent:
        """End the workflow and disconnect from plotter.
        
        Args:
            ctx: The workflow context
            ev: The command streaming complete event
            
        Returns:
            StopEvent with final results
        """
        print(f"{Fore.CYAN}╔═══════════════════════════════════════════════╗{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║     Streaming Plotter Workflow Complete       ║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}╚═══════════════════════════════════════════════╝{Style.RESET_ALL}")
        
        # Print summary
        print(f"{Fore.GREEN}[+] Drawing prompt: {ev.prompt}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}[+] Commands executed: {ev.commands_executed}{Style.RESET_ALL}")
        
        # Check if we have a simulated plotter and visualize the drawing
        if isinstance(self.plotter, SimulatedPlotter):
            try:
                viz_filename = f"streamed_visualization_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                self.plotter.visualize_drawing(output_file=viz_filename, show=True)
            except Exception as e:
                print(f"{Fore.RED}[!] Failed to visualize drawing: {str(e)}{Style.RESET_ALL}")
        
        # Disconnect from plotter
        await self.plotter.disconnect()
        print(f"{Fore.GREEN}[+] Disconnected from plotter{Style.RESET_ALL}")
        
        # Return final result
        result = {
            "prompt": ev.prompt,
            "commands_count": len(ev.commands),
            "commands_executed": ev.commands_executed,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        return StopEvent(result=result)

def get_plotter(port: str, simulate: bool = False) -> BasePlotter:
    """Get a plotter instance based on settings.
    
    Args:
        port: The serial port to connect to (ignored if simulate is True)
        simulate: Whether to use a simulated plotter
        
    Returns:
        A BasePlotter instance
    """
    if simulate:
        log_file = f"simulated_commands_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        return SimulatedPlotter(commands_log_file=log_file)
    else:
        return PenPlotter(port=port)

async def run_simple_workflow(prompt: str, port: str, model_name: str = "llama3.2:3b", max_steps: int = 50, simulate: bool = False):
    """Run the simple plotter workflow with a given prompt and port."""
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
        
        # Create plotter
        plotter = get_plotter(port, simulate)
        
        # Create workflow
        workflow = SimplePlotterWorkflow(llm=llm, plotter=plotter, timeout=10000, verbose=True)

        # Generate workflow visualization
        from llama_index.utils.workflow import draw_all_possible_flows

        draw_all_possible_flows(
            SimplePlotterWorkflow, filename="gcode_workflow_streamer_simple.html"
        )
        
        # Run workflow
        #start_event = StartEvent(prompt=prompt, max_steps=max_steps)
        result = await workflow.run(prompt=prompt, max_steps=max_steps)

        return result
    except Exception as e:
        print(f"{Fore.RED}Error running workflow: {str(e)}{Style.RESET_ALL}")
        return {"error": str(e)}

async def run_advanced_workflow(prompt: str, port: str, model_name: str = "llama3.2:3b", max_commands: int = 100, simulate: bool = False):
    """Run the advanced streaming workflow with a given prompt and port."""
    try:
        # Create LLM instance
        llm = Ollama(model=model_name, request_timeout=10000)

        from llama_index.llms.azure_openai import AzureOpenAI

        gpt4_api_key = "95139ba7e1cb4168b1eb02e78214491d"
        gpt4_api_version = "2024-06-01"
        gpt4_endpoint = "https://caideraoai.openai.azure.com/openai/deployments/gpt-4o-mini/chat/completions?api-version=2024-08-01-preview"

        llm = AzureOpenAI(
                    model="gpt-4o",
                    deployment_name="gpt-4o-gs",
                    api_key=gpt4_api_key,
                    api_version=gpt4_api_version,
                    azure_endpoint=gpt4_endpoint,
                    timeout=1220,)
        
        # Create plotter
        plotter = get_plotter(port, simulate)
        
        # Create workflow
        workflow = AdvancedPlotterWorkflow(llm=llm, plotter=plotter, timeout=10000, verbose=True)

        # Generate workflow visualization
        from llama_index.utils.workflow import draw_all_possible_flows

        draw_all_possible_flows(
            AdvancedPlotterWorkflow, filename="gcode_workflow_streamer_advanced.html"
        )
        
        # Run workflow
        #start_event = StartEvent(prompt=prompt, max_commands=max_commands)
        result = await workflow.run(prompt=prompt, max_commands=max_commands)
        
        return result
    except Exception as e:
        print(f"{Fore.RED}Error running workflow: {str(e)}{Style.RESET_ALL}")
        return {"error": str(e)}

async def main():
    """Main entry point for the application."""
    # Set up argument parser
    parser = argparse.ArgumentParser(description='G-code generation and plotter control')
    parser.add_argument('--port', default='/dev/ttyUSB0', help='Serial port for plotter (default: /dev/ttyUSB0)')
    parser.add_argument('--prompt', default='draw a small house with a door and windows', help='Drawing prompt')
    parser.add_argument('--model', default='llama3.2:3b', help='Ollama model to use')
    parser.add_argument('--mode', choices=['simple', 'advanced'], default='simple',
                       help='Workflow mode: simple (step-by-step) or advanced (streaming)')
    parser.add_argument('--max', type=int, default=50, help='Maximum steps/commands')
    parser.add_argument('--simulate', action='store_true', help='Use simulated plotter instead of hardware')
    
    # Parse arguments
    args = parser.parse_args()
    
    print(f"{Fore.CYAN}Starting plotter workflow{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Port: {args.port if not args.simulate else 'SIMULATED'}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Prompt: {args.prompt}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Model: {args.model}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Mode: {args.mode}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Max steps/commands: {args.max}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Simulation mode: {'Enabled' if args.simulate else 'Disabled'}{Style.RESET_ALL}")
    
    # Run selected workflow
    if args.mode == 'simple':
        result = await run_simple_workflow(args.prompt, args.port, args.model, args.max, args.simulate)
    else:
        result = await run_advanced_workflow(args.prompt, args.port, args.model, args.max, args.simulate)
    
    # Print summary
    if "error" not in result:
        print(f"\n{Fore.GREEN}[+] Workflow completed successfully{Style.RESET_ALL}")
        print(f"{Fore.GREEN}[+] Commands executed: {result.get('commands_executed', 0)}{Style.RESET_ALL}")
        if "success_count" in result:
            print(f"{Fore.GREEN}[+] Success: {result['success_count']}, Failed: {result['failed_count']}{Style.RESET_ALL}")
    else:
        print(f"\n{Fore.RED}[!] Workflow failed: {result['error']}{Style.RESET_ALL}")

if __name__ == "__main__":
    asyncio.run(main())


# # Simple mode (step-by-step with careful validation)
# python llm_stream_advanced.py --mode simple --port /dev/ttyUSB0 --prompt "draw a square"

# # Advanced mode (streaming with on-the-fly validation)
# python llm_stream_advanced.py --mode advanced --port /dev/ttyUSB0 --prompt "draw a spiral"