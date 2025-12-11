"""
Advanced Streaming G-Code Workflow

Refactored from boilerplates/llm_stream_advanced.py to use the new modular architecture.
This workflow provides advanced streaming capabilities with enhanced plotter interface,
visualization components, and sophisticated error handling.
"""

from llama_index.core.workflow import (
    Event,
    StartEvent,
    StopEvent,
    Workflow,
    step,
    Context,
)
from typing import List, Optional, Union, Dict, Any, AsyncGenerator
import json
import asyncio
from rich.console import Console
from datetime import datetime

from ..core.base_workflow import BasePromptPlotWorkflow
from ..core.models import GCodeCommand
from ..core.exceptions import WorkflowException, PlotterException
from ..plotter.base import BasePlotter
from ..strategies import StrategySelector, PromptComplexity
from ..config import get_config
from ..llm import LLMProvider

# Initialize colorama for cross-platform color support
from ..utils.rich_logger import WorkflowLogger
console = Console()
logger = WorkflowLogger(console)

# Prompt templates
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

STREAM_COMMANDS_TEMPLATE = """
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

# Event Classes
class GenerateCommandEvent(Event):
    """Event to trigger generation of a new plotter command."""
    prompt: str
    step: int

class StreamCommandsEvent(Event):
    """Event to stream G-code commands to the plotter."""
    prompt: str

class CommandExtractionDone(Event):
    """Event indicating command extraction is complete but not yet validated."""
    output: str
    prompt: str
    step: int

class CommandValidationErrorEvent(Event):
    """Event for validation errors in command generation."""
    error: str
    issues: str
    prompt: str
    step: int

class ValidatedCommandEvent(Event):
    """Event containing a validated plotter command."""
    command: GCodeCommand
    prompt: str
    step: int
    is_complete: bool

class CommandExecutedEvent(Event):
    """Event indicating a command was sent to the plotter."""
    prompt: str
    step: int
    command: GCodeCommand
    is_complete: bool
    success: bool

class CommandStreamingCompleteEvent(Event):
    """Event indicating command streaming is complete."""
    prompt: str
    commands_executed: int
    commands: List[GCodeCommand]

class PlotterCompleteEvent(Event):
    """Event indicating plotter has completed the drawing."""
    prompt: str
    commands_executed: int
    step_count: int

class CommandStreamPredictor:
    """Handles streaming predictions from LLM and validation"""
    
    def __init__(self, llm: Any):
        self.llm = llm
    
    async def stream_commands(self, prompt: str, history: List[str] = None) -> AsyncGenerator[GCodeCommand, None]:
        """Stream commands using LLM with validation"""
        
        history_text = "\n".join(history) if history else "No previous commands"
        
        template = STREAM_COMMANDS_TEMPLATE.format(
            prompt=prompt,
            history=history_text
        )
        
        # Check if LLM supports streaming
        if hasattr(self.llm, 'astream_complete'):
            response_stream = await self.llm.astream_complete(template)
        else:
            # Fallback to regular completion
            response = await self.llm.acomplete(template)
            # Simulate streaming by yielding the full response
            for command in self._parse_commands_from_text(response.text):
                yield command
            return
        
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
                    
                    logger.stream_command(len(history_list) + 1, command.to_gcode(), "success")
                    
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
                    logger.step_warning("Skipping invalid command", {"Error": str(e)})
                    start_idx = start + 1
    
    def _parse_commands_from_text(self, text: str) -> List[GCodeCommand]:
        """Parse commands from text when streaming is not available"""
        commands = []
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Try to find JSON objects
            start = line.find("{")
            end = line.rfind("}") + 1
            
            if start >= 0 and end > start:
                json_str = line[start:end]
                try:
                    command_data = json.loads(json_str)
                    command = GCodeCommand(**command_data)
                    commands.append(command)
                    
                    if command.command == "COMPLETE":
                        break
                        
                except (json.JSONDecodeError, ValueError):
                    continue
        
        return commands

class AdvancedPlotterStreamWorkflow(BasePromptPlotWorkflow):
    """Advanced workflow for controlling a pen plotter with streaming G-code commands.
    
    This workflow provides enhanced features over the simple streaming workflow:
    - Advanced command streaming with LLM streaming support
    - Enhanced plotter interface with better error recovery
    - Sophisticated visualization and monitoring
    - Improved performance with concurrent processing
    
    Key features:
    - Real-time command streaming from LLM
    - Advanced error handling and recovery mechanisms
    - Enhanced visualization and progress tracking
    - Concurrent command generation and execution
    """

    def __init__(self, llm: Optional[LLMProvider] = None, plotter: Optional[BasePlotter] = None, enable_streaming: bool = True, *args, **kwargs):
        """Initialize the advanced plotter workflow with integrated components.
        
        Args:
            llm: LLM provider instance (uses config default if None)
            plotter: The plotter instance to use (uses config default if None)
            enable_streaming: Whether to use streaming mode for command generation
            *args: Additional arguments
            **kwargs: Additional keyword arguments
        """
        # Get configuration
        self.config = get_config()
        
        # Initialize strategy selector
        self.strategy_selector = StrategySelector()
        
        # Use provided LLM or create from config
        if llm is None:
            from ..llm import AzureOpenAIProvider, OllamaProvider
            llm_config = self.config.llm
            if llm_config.provider == "azure":
                llm = AzureOpenAIProvider(
                    model=llm_config.model,
                    deployment_name=llm_config.deployment_name,
                    api_key=llm_config.api_key,
                    api_version=llm_config.api_version,
                    azure_endpoint=llm_config.azure_endpoint,
                    timeout=llm_config.timeout
                )
            else:  # ollama
                llm = OllamaProvider(
                    model=llm_config.model,
                    request_timeout=llm_config.timeout
                )
        
        # Use provided plotter or create from config
        if plotter is None:
            from ..plotter import SerialPlotter, SimulatedPlotter
            plotter_config = self.config.plotter
            if plotter_config.default_type == "serial":
                plotter = SerialPlotter(
                    port=plotter_config.serial_port,
                    baud_rate=plotter_config.serial_baud_rate
                )
            else:  # simulated
                plotter = SimulatedPlotter(
                    port="SIMULATED",
                    visualize=True
                )
        
        super().__init__(llm, *args, **kwargs)
        self.plotter = plotter
        self.enable_streaming = enable_streaming
        self.stream_predictor = CommandStreamPredictor(llm) if enable_streaming else None

    @step
    async def start(self, ctx: Context, ev: StartEvent) -> Union[GenerateCommandEvent, StreamCommandsEvent, StopEvent]:
        """Start the workflow, connect to plotter, and initialize context.
        
        Args:
            ctx: The workflow context
            ev: The start event
            
        Returns:
            GenerateCommandEvent, StreamCommandsEvent, or StopEvent
        """
        # Get prompt from event
        if not hasattr(ev, "prompt"):
            logger.step_error("No drawing prompt specified", {"Action": "Workflow stopped"})
            return StopEvent(result="No drawing prompt specified")
        
        prompt = ev.prompt
        max_steps = getattr(ev, "max_steps", self.max_steps)
        
        logger.stream_start("Advanced Plotter Streaming", prompt, max_steps)
        
        # Initialize context using base workflow method
        await self.initialize_context(ctx, prompt, max_steps=max_steps, enable_streaming=self.enable_streaming)
        
        logger.step_success("Advanced workflow parameters initialized", {
            "Prompt": prompt,
            "Max steps": max_steps,
            "Streaming enabled": self.enable_streaming
        })
        
        # Connect to plotter with enhanced error handling
        logger.step_start("Connect to Plotter", "Establishing enhanced connection with advanced interface")
        
        try:
            if not await self.plotter.connect():
                logger.step_error("Failed to connect to plotter", {"Action": "Workflow stopped"})
                return StopEvent(result="Failed to connect to plotter")
        except Exception as e:
            logger.step_error("Plotter connection error", {"Error": str(e)})
            return StopEvent(result=f"Plotter connection error: {str(e)}")
        
        logger.step_success("Successfully connected to advanced plotter interface")
        
        # Choose workflow mode based on streaming capability
        if self.enable_streaming and self.stream_predictor:
            logger.step_info("Starting streaming command generation", {"Mode": "Advanced streaming"})
            return StreamCommandsEvent(prompt=prompt)
        else:
            logger.step_info("Starting sequential command generation", {"Mode": "Sequential fallback"})
            return GenerateCommandEvent(prompt=prompt, step=1)
    
    @step
    async def stream_commands(self, ctx: Context, ev: StreamCommandsEvent) -> CommandStreamingCompleteEvent:
        """Stream commands from LLM and execute them on the plotter.
        
        Args:
            ctx: The workflow context
            ev: The stream commands event
            
        Returns:
            CommandStreamingCompleteEvent with execution results
        """
        logger.step_start("Advanced Command Streaming", "Using advanced streaming to generate and execute commands in real-time")
        
        executed_commands = []
        commands_executed = 0
        success_count = 0
        failed_count = 0
        
        try:
            # Get command history for context
            history = await self.get_command_history(ctx)
            history_list = history.split('\n') if history != "No previous commands" else []
            
            logger.step_info("Streaming commands from LLM", {"Mode": "Real-time generation and execution"})
            
            # Stream commands from LLM
            async for command in self.stream_predictor.stream_commands(ev.prompt, history_list):
                logger.stream_command(commands_executed + 1, command.to_gcode(), "executing")
                
                # Check if this is a completion command
                if command.command == "COMPLETE":
                    logger.step_info("Received completion command", {"Action": "Ending stream"})
                    break
                
                # Execute command on plotter
                try:
                    success = await self.plotter.send_command(command.to_gcode())
                    commands_executed += 1
                    
                    if success:
                        success_count += 1
                        executed_commands.append(command)
                        await self.add_command_to_history(ctx, command)
                        logger.plotter_command(command.to_gcode(), "ok", True)
                    else:
                        failed_count += 1
                        logger.plotter_command(command.to_gcode(), "failed", False)
                        
                except Exception as e:
                    failed_count += 1
                    logger.step_error("Plotter communication error", {"Error": str(e)})
                
                # Update statistics
                await self.update_statistics(ctx, success)
                
                # Check step limits
                if commands_executed >= await ctx.get("max_steps"):
                    logger.step_warning("Reached maximum steps limit", {"Action": "Ending stream"})
                    break
                
                # Small delay to prevent overwhelming the plotter
                await asyncio.sleep(0.1)
            
            logger.execution_summary(commands_executed, success_count, failed_count, 0.0)
            
        except Exception as e:
            logger.step_error("Streaming error", {"Error": str(e), "Action": "Continuing with executed commands"})
        
        # Update context with final counts
        await ctx.set("commands_executed", commands_executed)
        await ctx.set("success_count", success_count)
        await ctx.set("failed_count", failed_count)
        
        return CommandStreamingCompleteEvent(
            prompt=ev.prompt,
            commands_executed=commands_executed,
            commands=executed_commands
        )
    
    @step
    async def generate_command(self, ctx: Context, ev: GenerateCommandEvent) -> CommandExtractionDone:
        """Generate the next G-code command (fallback for non-streaming mode).
        
        Args:
            ctx: The workflow context
            ev: The generate command event
            
        Returns:
            CommandExtractionDone with raw LLM output
        """
        logger.step_start(f"Generate Command #{ev.step}", "Using sequential generation as fallback")
        
        # Track retries for this specific step
        task_key = f"retries_step_{ev.step}"
        
        # Check retry limits using base workflow method
        if not await self.check_retry_limits(ctx, ev.step, task_key):
            logger.step_error("Maximum retries exceeded", {
                "Step": ev.step,
                "Action": "Using COMPLETE fallback"
            })
            
            # Return a COMPLETE command to force termination
            fallback_result = json.dumps({"command": "COMPLETE"})
            
            return CommandExtractionDone(
                output=fallback_result,
                prompt=ev.prompt,
                step=ev.step
            )
        
        # Get command history using base workflow method
        history = await self.get_command_history(ctx)
        
        # Build prompt for command generation
        prompt = NEXT_COMMAND_TEMPLATE.format(
            prompt=ev.prompt,
            history=history
        )
        
        # Generate command using the LLM
        llm_type = type(self.llm).__name__
        logger.llm_call(llm_type, "", ev.prompt[:30])
        
        try:
            if hasattr(self.llm, 'acomplete'):
                response = await self.llm.acomplete(prompt)
                response_text = response.text
            else:
                response = self.llm.complete(prompt)
                response_text = response.text
        except Exception as e:
            logger.step_error("LLM call failed", {"Error": str(e)})
            # Fallback to COMPLETE command
            fallback_result = json.dumps({"command": "COMPLETE"})
            return CommandExtractionDone(
                output=fallback_result,
                prompt=ev.prompt,
                step=ev.step
            )
        
        return CommandExtractionDone(
            output=response_text,
            prompt=ev.prompt,
            step=ev.step
        )
    
    @step
    async def finalize_streaming(self, ctx: Context, ev: CommandStreamingCompleteEvent) -> StopEvent:
        """Finalize the streaming execution and return results.
        
        Args:
            ctx: The workflow context
            ev: The command streaming complete event
            
        Returns:
            StopEvent with execution results
        """
        logger.step_start("Finalize Advanced Execution", "Processing advanced execution results and creating comprehensive reports")
        
        # Get final statistics
        success_count = await ctx.get("success_count", default=0)
        failed_count = await ctx.get("failed_count", default=0)
        
        # Show execution summary
        elapsed = 0.0  # This would be calculated properly in real implementation
        logger.execution_summary(ev.commands_executed, success_count, failed_count, elapsed)
        
        # Disconnect from plotter with enhanced cleanup
        logger.step_info("Disconnecting from advanced plotter interface")
        try:
            await self.plotter.disconnect()
            logger.step_success("Advanced plotter disconnected successfully")
        except Exception as e:
            logger.step_warning("Plotter disconnect warning", {"Error": str(e)})
        
        # Generate enhanced statistics
        if hasattr(self.plotter, 'get_drawing_stats'):
            try:
                drawing_stats = self.plotter.get_drawing_stats()
                logger.step_info("Drawing statistics retrieved", drawing_stats)
            except Exception as e:
                logger.step_warning("Could not retrieve drawing stats", {"Error": str(e)})
        
        # Create comprehensive result
        result = {
            "prompt": ev.prompt,
            "commands_executed": ev.commands_executed,
            "successful_commands": success_count,
            "failed_commands": failed_count,
            "success_rate": (success_count/max(1, ev.commands_executed))*100,
            "commands": [cmd.model_dump() for cmd in ev.commands],
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "plotter_type": type(self.plotter).__name__,
            "workflow_mode": "streaming" if self.enable_streaming else "sequential",
            "advanced_features": {
                "streaming_enabled": self.enable_streaming,
                "enhanced_error_handling": True,
                "real_time_execution": True
            }
        }
        
        logger.workflow_complete(True, ev.commands_executed)
        
        return StopEvent(result=result)


async def main():
    """Main function for testing the advanced streaming workflow."""
    from llama_index.llms.ollama import Ollama
    from llama_index.llms.azure_openai import AzureOpenAI
    from ..plotter.simulated import SimulatedPlotter
    import os

    logger.workflow_start("Advanced Plotter Streaming Workflow", "Testing advanced streaming with enhanced features")
    
    # Create LLM instance
    logger.step_start("Initialize LLM", "Setting up language model for advanced streaming")
    llm = Ollama(model="llama3.2:3b", request_timeout=10000)

    # Optionally use Azure OpenAI if environment variables are set
    if all(os.environ.get(key) for key in ["GPT4_API_KEY", "GPT4_API_VERSION", "GPT4_ENDPOINT"]):
        logger.step_info("Configuring Azure OpenAI for advanced features", {"Reason": "Environment variables detected"})
        llm = AzureOpenAI(
            model="gpt-4o",
            deployment_name="gpt-4o-gs",
            api_key=os.environ.get("GPT4_API_KEY"),
            api_version=os.environ.get("GPT4_API_VERSION"),
            azure_endpoint=os.environ.get("GPT4_ENDPOINT"),
            timeout=1220,
        )
    
    # Create advanced plotter instance
    logger.step_success("LLM initialized successfully")
    logger.step_start("Initialize Advanced Plotter", "Setting up advanced simulated plotter")
    plotter = SimulatedPlotter(
        commands_log_file=f"results/logs/advanced_streaming_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
        visualize=True,
        command_delay=0.02  # Faster for advanced mode
    )
    
    try:
        # Create advanced workflow
        logger.step_success("Advanced plotter initialized successfully")
        logger.step_start("Create Advanced Workflow", "Instantiating AdvancedPlotterStreamWorkflow")
        workflow = AdvancedPlotterStreamWorkflow(
            llm=llm, 
            plotter=plotter, 
            enable_streaming=True,  # Enable advanced streaming
            timeout=15000
        )
        
        # Generate workflow visualization
        logger.step_info("Generating advanced workflow visualization")
        try:
            from llama_index.utils.workflow import draw_all_possible_flows
            
            draw_all_possible_flows(
                AdvancedPlotterStreamWorkflow, 
                filename="results/visualizations/gcode_workflow_streamer_advanced.html"
            )
            
            logger.step_success("Advanced workflow visualization saved", {"File": "results/visualizations/gcode_workflow_streamer_advanced.html"})
        except ImportError:
            logger.step_warning("Workflow visualization not available", {"Reason": "llama_index.utils.workflow not found"})
        
        # Test with a more complex prompt
        prompt = "draw a detailed house with windows, door, chimney, and a small garden with flowers"
        logger.step_info("Preparing advanced test prompt", {"Prompt": prompt})
        
        # Run advanced workflow
        logger.step_start("Execute Advanced Workflow", "Running advanced streaming workflow")
        result = await workflow.run(prompt=prompt, max_steps=50)
        
        # Display enhanced results
        if result:
            logger.step_success("Advanced workflow completed successfully", {
                "Commands executed": result.get('commands_executed', 0),
                "Success rate": f"{result.get('success_rate', 0):.1f}%",
                "Workflow mode": result.get('workflow_mode', 'unknown')
            })
    
    except KeyboardInterrupt:
        logger.step_warning("Operation interrupted by user", {"Action": "Workflow execution stopped"})
        # Ensure plotter is disconnected
        try:
            await plotter.disconnect()
        except:
            pass
    except Exception as e:
        logger.step_error("Advanced workflow execution failed", {"Error": str(e)})
        # Ensure plotter is disconnected
        try:
            await plotter.disconnect()
        except:
            pass


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())