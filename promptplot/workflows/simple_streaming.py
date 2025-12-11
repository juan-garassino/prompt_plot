"""
Simple Streaming G-Code Workflow

Refactored from boilerplates/llm_stream_simple.py to use the new modular architecture.
This workflow generates G-code commands one at a time and streams them directly to
the plotter with real-time execution.
"""

from llama_index.core.workflow import (
    Event,
    StartEvent,
    StopEvent,
    Workflow,
    step,
    Context,
)
from typing import List, Optional, Union, Dict, Any
import json
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

# Event Classes
class GenerateCommandEvent(Event):
    """Event to trigger generation of a new plotter command."""
    prompt: str
    step: int

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

class PlotterCompleteEvent(Event):
    """Event indicating plotter has completed the drawing."""
    prompt: str
    commands_executed: int
    step_count: int

class SimplePlotterStreamWorkflow(BasePromptPlotWorkflow):
    """Simple workflow for controlling a pen plotter with sequential G-code commands.
    
    This workflow generates G-code commands one at a time, validates them,
    and sends them to the plotter (real or simulated) in real-time.
    
    Key features:
    - Real-time command generation and execution
    - Direct plotter communication
    - Robust error handling and recovery
    - Progress tracking and statistics
    """

    def __init__(self, llm: Optional[LLMProvider] = None, plotter: Optional[BasePlotter] = None, *args, **kwargs):
        """Initialize the plotter workflow with integrated components.
        
        Args:
            llm: LLM provider instance (uses config default if None)
            plotter: The plotter instance to use (uses config default if None)
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

    @step
    async def start(self, ctx: Context, ev: StartEvent) -> Union[GenerateCommandEvent, StopEvent]:
        """Start the workflow, connect to plotter, and initialize context.
        
        Args:
            ctx: The workflow context
            ev: The start event
            
        Returns:
            GenerateCommandEvent or StopEvent
        """
        # Get prompt from event
        if not hasattr(ev, "prompt"):
            logger.step_error("No drawing prompt specified", {"Action": "Workflow stopped"})
            return StopEvent(result="No drawing prompt specified")
        
        prompt = ev.prompt
        max_steps = getattr(ev, "max_steps", self.max_steps)
        
        logger.stream_start("Simple Plotter Streaming", prompt, max_steps)
        
        # Initialize context using base workflow method
        await self.initialize_context(ctx, prompt, max_steps=max_steps)
        
        logger.step_success("Workflow parameters initialized", {
            "Prompt": prompt,
            "Max steps": max_steps
        })
        
        # Connect to plotter
        logger.step_start("Connect to Plotter", "Establishing connection with plotter device")
        
        try:
            if not await self.plotter.connect():
                logger.step_error("Failed to connect to plotter", {"Action": "Workflow stopped"})
                return StopEvent(result="Failed to connect to plotter")
        except Exception as e:
            logger.step_error("Plotter connection error", {"Error": str(e)})
            return StopEvent(result=f"Plotter connection error: {str(e)}")
        
        logger.step_success("Successfully connected to plotter")
        
        # Start with step 1
        logger.step_info("Starting command generation sequence")
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
        logger.stream_command(ev.step, f"Generating command #{ev.step}", "executing")
        
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
        
        current_retries = await ctx.get(task_key, default=0)
        max_retries = await ctx.get("max_retries")
        
        logger.step_info(f"Generating command #{ev.step}", {
            "Attempt": f"{current_retries}/{max_retries}",
            "History": f"{len(history.split(chr(10)))} previous commands"
        })
        
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
        
        logger.stream_command(ev.step, f"Command #{ev.step} generated", "success")
        
        return CommandExtractionDone(
            output=response_text,
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
        logger.step_start(f"Validate Command #{ev.step}", "Ensuring LLM output is valid G-code")
        
        # If this is a validation error event, handle the retry
        if isinstance(ev, CommandValidationErrorEvent):
            logger.reflection_prompt(1, 3, ev.error)
            
            # Use base workflow reflection method
            try:
                response_text = await self.handle_retry_with_reflection(
                    ev.error, ev.issues, ev.prompt
                )
            except Exception as e:
                logger.step_error("Reflection failed", {"Error": str(e)})
                # Create a COMPLETE command to terminate
                command = self.create_fallback_command()
                return ValidatedCommandEvent(
                    command=command,
                    prompt=ev.prompt,
                    step=ev.step,
                    is_complete=True
                )
            
            # Create new extraction done event
            ev = CommandExtractionDone(
                output=response_text,
                prompt=ev.prompt,
                step=ev.step
            )
        
        # Check retry status to show proper messaging
        task_key = f"retries_step_{ev.step}"
        current_retries = await ctx.get(task_key, default=0)
        max_retries = await ctx.get("max_retries")
        
        try:
            # Use base workflow validation method
            result = await self.validate_gcode_command(ev.output)
            
            if isinstance(result, Exception):
                # Validation failed
                logger.validation_result(False, 0, [str(result)])
                
                # More detailed error information based on retry count
                if current_retries >= max_retries:
                    logger.step_error("Final attempt failed", {
                        "Attempts": f"{current_retries}/{max_retries}",
                        "Action": "Moving to fallback mechanism"
                    })
                    
                    # Create a COMPLETE command to terminate gracefully
                    command = self.create_fallback_command()
                    return ValidatedCommandEvent(
                        command=command,
                        prompt=ev.prompt,
                        step=ev.step,
                        is_complete=True
                    )
                else:
                    logger.step_warning("Retrying validation", {
                        "Attempt": f"{current_retries}/{max_retries}",
                        "Action": "Returning to validate_command with error details"
                    })
                
                return CommandValidationErrorEvent(
                    error=str(result),
                    issues=ev.output,
                    prompt=ev.prompt,
                    step=ev.step
                )
            
            # Validation successful - result is a GCodeCommand
            command = result
            
            # Check if this is a completion command
            is_complete = command.command == "COMPLETE"
            
            logger.validation_result(True, 1)
            logger.step_success("Command validation successful", {"Command": command.to_gcode()})
            
            if is_complete:
                logger.step_info("Reached completion command", {"Action": "Program generation complete"})
            
            return ValidatedCommandEvent(
                command=command,
                prompt=ev.prompt,
                step=ev.step,
                is_complete=is_complete
            )
            
        except Exception as e:
            logger.step_error("Unexpected validation error", {"Error": str(e)})
            
            return CommandValidationErrorEvent(
                error=str(e),
                issues=ev.output,
                prompt=ev.prompt,
                step=ev.step
            )
    
    @step
    async def execute_command(self, ctx: Context, ev: ValidatedCommandEvent) -> Union[CommandExecutedEvent, PlotterCompleteEvent]:
        """Execute the validated command on the plotter.
        
        Args:
            ctx: The workflow context
            ev: The validated command event
            
        Returns:
            CommandExecutedEvent or PlotterCompleteEvent
        """
        logger.step_start(f"Execute Command #{ev.step}", "Sending validated command to plotter")
        
        success = False
        
        # Execute command if it's not COMPLETE
        if not ev.is_complete:
            logger.plotter_command(ev.command.to_gcode(), "sending", True)
            
            try:
                # Send command to plotter
                success = await self.plotter.send_command(ev.command.to_gcode())
                
                if success:
                    logger.plotter_command(ev.command.to_gcode(), "ok", True)
                    # Add command to history
                    await self.add_command_to_history(ctx, ev.command)
                else:
                    logger.plotter_command(ev.command.to_gcode(), "failed", False)
                    
            except Exception as e:
                logger.step_error("Plotter communication error", {"Error": str(e)})
                success = False
        else:
            logger.step_info("Skipping COMPLETE command execution", {"Reason": "Control command, not sent to plotter"})
            success = True  # COMPLETE is always "successful"
        
        # Update statistics
        await self.update_statistics(ctx, success)
        
        # Check if we should complete the workflow
        if ev.is_complete or not await self.check_step_limits(ctx, ev.step):
            logger.step_success("Plotter workflow complete")
            
            commands_executed = await ctx.get("commands_executed", default=0)
            
            # Disconnect from plotter
            try:
                await self.plotter.disconnect()
                logger.step_success("Plotter disconnected successfully")
            except Exception as e:
                logger.step_warning("Plotter disconnect warning", {"Error": str(e)})
            
            return PlotterCompleteEvent(
                prompt=ev.prompt,
                commands_executed=commands_executed,
                step_count=ev.step
            )
        else:
            # Continue to next command
            logger.step_success("Command executed, continuing to next step")
            
            return CommandExecutedEvent(
                prompt=ev.prompt,
                step=ev.step,
                command=ev.command,
                is_complete=ev.is_complete,
                success=success
            )
    
    @step
    async def continue_execution(self, ctx: Context, ev: CommandExecutedEvent) -> GenerateCommandEvent:
        """Continue to the next command generation.
        
        Args:
            ctx: The workflow context
            ev: The command executed event
            
        Returns:
            GenerateCommandEvent for the next step
        """
        next_step = ev.step + 1
        logger.step_start(f"Continue to Step {next_step}", "Preparing for next command generation")
        
        # Get current statistics for context
        commands_executed = await ctx.get("commands_executed", default=0)
        success_count = await ctx.get("success_count", default=0)
        logger.stream_progress(success_count, commands_executed, f"Step {next_step}")
        
        # Generate next command
        logger.step_success("Preparing for next command generation", {"Action": "Looping back to generate_command"})
        
        return GenerateCommandEvent(
            prompt=ev.prompt,
            step=next_step
        )
    
    @step
    async def finalize_execution(self, ctx: Context, ev: PlotterCompleteEvent) -> StopEvent:
        """Finalize the plotter execution and return results.
        
        Args:
            ctx: The workflow context
            ev: The plotter complete event
            
        Returns:
            StopEvent with execution results
        """
        logger.step_start("Finalize Execution", "Processing execution results and creating summary")
        
        # Get final statistics
        commands = await ctx.get("commands", default=[])
        success_count = await ctx.get("success_count", default=0)
        failed_count = await ctx.get("failed_count", default=0)
        
        # Show execution summary
        elapsed = (datetime.now() - datetime.now()).total_seconds()  # This would be calculated properly in real implementation
        logger.execution_summary(ev.commands_executed, success_count, failed_count, elapsed)
        
        # Create final result
        result = {
            "prompt": ev.prompt,
            "commands_executed": ev.commands_executed,
            "successful_commands": success_count,
            "failed_commands": failed_count,
            "step_count": ev.step_count,
            "commands": [cmd.model_dump() for cmd in commands],
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "plotter_type": type(self.plotter).__name__
        }
        
        logger.workflow_complete(True, ev.commands_executed)
        
        return StopEvent(result=result)


async def main():
    """Main function for testing the simple streaming workflow."""
    from llama_index.llms.ollama import Ollama
    from llama_index.llms.azure_openai import AzureOpenAI
    from ..plotter.simulated import SimulatedPlotter
    import os

    logger.workflow_start("Simple Plotter Streaming Workflow", "Testing workflow with sample prompt")
    
    # Create LLM instance
    logger.step_start("Initialize LLM", "Setting up language model for G-code generation")
    llm = Ollama(model="llama3.2:3b", request_timeout=10000)

    # Optionally use Azure OpenAI if environment variables are set
    if all(os.environ.get(key) for key in ["GPT4_API_KEY", "GPT4_API_VERSION", "GPT4_ENDPOINT"]):
        logger.step_info("Configuring Azure OpenAI", {"Reason": "Environment variables detected"})
        llm = AzureOpenAI(
            model="gpt-4o",
            deployment_name="gpt-4o-gs",
            api_key=os.environ.get("GPT4_API_KEY"),
            api_version=os.environ.get("GPT4_API_VERSION"),
            azure_endpoint=os.environ.get("GPT4_ENDPOINT"),
            timeout=1220,
        )
    
    # Create plotter instance
    logger.step_success("LLM initialized successfully")
    logger.step_start("Initialize Plotter", "Setting up simulated plotter")
    plotter = SimulatedPlotter(
        commands_log_file=f"results/logs/streaming_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
        visualize=True
    )
    
    try:
        # Create workflow
        logger.step_success("Plotter initialized successfully")
        logger.step_start("Create Workflow", "Instantiating SimplePlotterStreamWorkflow")
        workflow = SimplePlotterStreamWorkflow(llm=llm, plotter=plotter, timeout=10000)
        
        # Generate workflow visualization
        logger.step_info("Generating workflow visualization")
        try:
            from llama_index.utils.workflow import draw_all_possible_flows
            
            draw_all_possible_flows(
                SimplePlotterStreamWorkflow, filename="results/visualizations/gcode_workflow_streamer_simple.html"
            )
            
            logger.step_success("Workflow visualization saved", {"File": "results/visualizations/gcode_workflow_streamer_simple.html"})
        except ImportError:
            logger.step_warning("Workflow visualization not available", {"Reason": "llama_index.utils.workflow not found"})
        
        # Test with a prompt
        prompt = "draw a small house with a door and windows"
        logger.step_info("Preparing test prompt", {"Prompt": prompt})
        
        # Run workflow
        logger.step_start("Execute Workflow", "Running streaming workflow with test prompt")
        result = await workflow.run(prompt=prompt, max_steps=30)
        
        # Display results
        if result:
            logger.step_success("Workflow completed successfully", {
                "Commands executed": result.get('commands_executed', 0),
                "Success rate": f"{result.get('successful_commands', 0)}/{result.get('commands_executed', 0)}"
            })
    
    except KeyboardInterrupt:
        logger.step_warning("Operation interrupted by user", {"Action": "Workflow execution stopped"})
        # Ensure plotter is disconnected
        try:
            await plotter.disconnect()
        except:
            pass
    except Exception as e:
        logger.step_error("Workflow execution failed", {"Error": str(e)})
        # Ensure plotter is disconnected
        try:
            await plotter.disconnect()
        except:
            pass


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())