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
from colorama import Fore, Style, init
from datetime import datetime

from ..core.base_workflow import BasePromptPlotWorkflow
from ..core.models import GCodeCommand
from ..core.exceptions import WorkflowException, PlotterException
from ..plotter.base import BasePlotter
from ..strategies import StrategySelector, PromptComplexity
from ..config import get_config
from ..llm import LLMProvider

# Initialize colorama for cross-platform color support
init(autoreset=True)

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
        print(f"{Fore.CYAN}╔══════════════════════════════════════╗{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║     Plotter Workflow Initializing    ║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}╚══════════════════════════════════════╝{Style.RESET_ALL}")
        
        print(f"{Fore.CYAN}[*] ├── Initializing workflow{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   └── This step prepares the workflow by setting up context variables and parameters needed for G-code generation.{Style.RESET_ALL}")
        
        # Get prompt from event
        if not hasattr(ev, "prompt"):
            print(f"{Fore.RED}[!] │   └── No drawing prompt specified - workflow stopped{Style.RESET_ALL}")
            return StopEvent(result="No drawing prompt specified")
        
        prompt = ev.prompt
        max_steps = getattr(ev, "max_steps", self.max_steps)
        
        # Initialize context using base workflow method
        await self.initialize_context(ctx, prompt, max_steps=max_steps)
        
        print(f"{Fore.GREEN}├── [+] Workflow parameters initialized successfully{Style.RESET_ALL}")
        print(f"{Fore.GREEN}├── [+] Drawing prompt: {prompt}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}├── [+] Max steps: {max_steps}{Style.RESET_ALL}")
        
        # Connect to plotter
        print(f"{Fore.CYAN}├── [*] Connecting to plotter device{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}│   └── [?] Establishing connection with the plotter (real or simulated) to prepare for command execution.{Style.RESET_ALL}")
        
        try:
            if not await self.plotter.connect():
                print(f"{Fore.RED}[!] │   └── Failed to connect to plotter - workflow stopped{Style.RESET_ALL}")
                return StopEvent(result="Failed to connect to plotter")
        except Exception as e:
            print(f"{Fore.RED}[!] │   └── Plotter connection error: {str(e)}{Style.RESET_ALL}")
            return StopEvent(result=f"Plotter connection error: {str(e)}")
        
        print(f"{Fore.GREEN}├── [+] Successfully connected to plotter{Style.RESET_ALL}")
        
        # Start with step 1
        print(f"{Fore.CYAN}└── [*] Starting command generation sequence{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}    └── [?] Now that initialization is complete, the workflow will begin generating the first G-code command.{Style.RESET_ALL}")
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
        
        # Check retry limits using base workflow method
        if not await self.check_retry_limits(ctx, ev.step, task_key):
            print(f"{Fore.RED}├── [!] Maximum retries exceeded for step {ev.step}{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}│   └── [?] After multiple failed attempts, returning a COMPLETE command to gracefully terminate the workflow.{Style.RESET_ALL}")
            
            # Return a COMPLETE command to force termination
            fallback_result = json.dumps({"command": "COMPLETE"})
            
            return CommandExtractionDone(
                output=fallback_result,
                prompt=ev.prompt,
                step=ev.step
            )
        
        # Get command history using base workflow method
        print(f"{Fore.CYAN}├── [*] Retrieving command history{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}│   └── [?] Collecting previously executed commands to provide context for the LLM to generate the next command.{Style.RESET_ALL}")
        history = await self.get_command_history(ctx)
        
        current_retries = await ctx.get(task_key, default=0)
        max_retries = await ctx.get("max_retries")
        print(f"{Fore.YELLOW}├── [*] Attempt {current_retries}/{max_retries}{Style.RESET_ALL}")
        
        # Build prompt for command generation
        print(f"{Fore.CYAN}├── [*] Building LLM prompt{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}│   └── [?] Creating a structured prompt with instructions, drawing requirements, and command history.{Style.RESET_ALL}")
        prompt = NEXT_COMMAND_TEMPLATE.format(
            prompt=ev.prompt,
            history=history
        )
        
        # Generate command using the LLM
        print(f"{Fore.CYAN}├── [*] Sending request to LLM{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}│   └── [?] Querying the language model to generate the next G-code command based on the prompt.{Style.RESET_ALL}")
        
        try:
            if hasattr(self.llm, 'acomplete'):
                response = await self.llm.acomplete(prompt)
                response_text = response.text
            else:
                response = self.llm.complete(prompt)
                response_text = response.text
        except Exception as e:
            print(f"{Fore.RED}├── [!] LLM call failed: {str(e)}{Style.RESET_ALL}")
            # Fallback to COMPLETE command
            fallback_result = json.dumps({"command": "COMPLETE"})
            return CommandExtractionDone(
                output=fallback_result,
                prompt=ev.prompt,
                step=ev.step
            )
        
        print(f"{Fore.GREEN}└── [+] Command generation complete{Style.RESET_ALL}")
        
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
        print(f"{Fore.CYAN}[*] ├── Validating command for step {ev.step}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   └── This step ensures the LLM output is a valid G-code command by parsing JSON and checking format.{Style.RESET_ALL}")
        
        # If this is a validation error event, handle the retry
        if isinstance(ev, CommandValidationErrorEvent):
            print(f"{Fore.YELLOW}├── [!] Retrying with reflection after validation error{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}│   └── Error: {ev.error}{Style.RESET_ALL}")
            
            # Use base workflow reflection method
            try:
                response_text = await self.handle_retry_with_reflection(
                    ev.error, ev.issues, ev.prompt
                )
            except Exception as e:
                print(f"{Fore.RED}│   └── [!] Reflection failed: {str(e)}{Style.RESET_ALL}")
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
                print(f"{Fore.RED}├── [!] Command validation failed{Style.RESET_ALL}")
                print(f"{Fore.RED}│   └── Error: {str(result)}{Style.RESET_ALL}")
                
                # More detailed error information based on retry count
                if current_retries >= max_retries:
                    print(f"{Fore.RED}├── [!] Final attempt failed - Validation errors persist after {current_retries} attempts{Style.RESET_ALL}")
                    print(f"{Fore.YELLOW}└── [?] Moving to fallback mechanism after exhausting retry attempts.{Style.RESET_ALL}")
                    
                    # Create a COMPLETE command to terminate gracefully
                    command = self.create_fallback_command()
                    return ValidatedCommandEvent(
                        command=command,
                        prompt=ev.prompt,
                        step=ev.step,
                        is_complete=True
                    )
                else:
                    print(f"{Fore.YELLOW}├── [!] Retrying - Attempt {current_retries}/{max_retries} failed{Style.RESET_ALL}")
                    print(f"{Fore.YELLOW}└── [?] Returning to validate_command with error details to help LLM correct its output.{Style.RESET_ALL}")
                
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
            
            print(f"{Fore.GREEN}├── [+] Command validation successful{Style.RESET_ALL}")
            print(f"{Fore.GREEN}│   └── Command: {command.to_gcode()}{Style.RESET_ALL}")
            
            if is_complete:
                print(f"{Fore.GREEN}└── [+] Reached completion command{Style.RESET_ALL}")
                print(f"{Fore.YELLOW}    └── [?] The COMPLETE command signals the end of the G-code program generation.{Style.RESET_ALL}")
            
            return ValidatedCommandEvent(
                command=command,
                prompt=ev.prompt,
                step=ev.step,
                is_complete=is_complete
            )
            
        except Exception as e:
            print(f"{Fore.RED}├── [!] Unexpected validation error{Style.RESET_ALL}")
            print(f"{Fore.RED}│   └── Error: {str(e)}{Style.RESET_ALL}")
            
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
        print(f"{Fore.CYAN}[*] ├── Executing command for step {ev.step}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   └── This step sends the validated command to the plotter and tracks execution results.{Style.RESET_ALL}")
        
        success = False
        
        # Execute command if it's not COMPLETE
        if not ev.is_complete:
            print(f"{Fore.CYAN}├── [*] Sending command to plotter{Style.RESET_ALL}")
            print(f"{Fore.BLUE}│   └── Command: {ev.command.to_gcode()}{Style.RESET_ALL}")
            
            try:
                # Send command to plotter
                success = await self.plotter.send_command(ev.command.to_gcode())
                
                if success:
                    print(f"{Fore.GREEN}│   └── Command executed successfully{Style.RESET_ALL}")
                    # Add command to history
                    await self.add_command_to_history(ctx, ev.command)
                else:
                    print(f"{Fore.RED}│   └── Command execution failed{Style.RESET_ALL}")
                    
            except Exception as e:
                print(f"{Fore.RED}│   └── Plotter communication error: {str(e)}{Style.RESET_ALL}")
                success = False
        else:
            print(f"{Fore.CYAN}├── [*] Skipping COMPLETE command execution{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}│   └── [?] COMPLETE is a control command, not sent to the plotter.{Style.RESET_ALL}")
            success = True  # COMPLETE is always "successful"
        
        # Update statistics
        await self.update_statistics(ctx, success)
        
        # Check if we should complete the workflow
        if ev.is_complete or not await self.check_step_limits(ctx, ev.step):
            print(f"{Fore.GREEN}└── [+] Plotter workflow complete{Style.RESET_ALL}")
            
            commands_executed = await ctx.get("commands_executed", default=0)
            
            # Disconnect from plotter
            try:
                await self.plotter.disconnect()
                print(f"{Fore.GREEN}    └── Plotter disconnected successfully{Style.RESET_ALL}")
            except Exception as e:
                print(f"{Fore.YELLOW}    └── Plotter disconnect warning: {str(e)}{Style.RESET_ALL}")
            
            return PlotterCompleteEvent(
                prompt=ev.prompt,
                commands_executed=commands_executed,
                step_count=ev.step
            )
        else:
            # Continue to next command
            print(f"{Fore.GREEN}└── [+] Command executed, continuing to next step{Style.RESET_ALL}")
            
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
        print(f"{Fore.CYAN}[*] ├── Continuing to next command (step {ev.step + 1}){Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   └── This step prepares for generating the next command.{Style.RESET_ALL}")
        
        # Get current statistics for context
        commands_executed = await ctx.get("commands_executed", default=0)
        success_count = await ctx.get("success_count", default=0)
        print(f"{Fore.CYAN}├── [*] Progress: {commands_executed} commands executed, {success_count} successful{Style.RESET_ALL}")
        
        # Generate next command
        next_step = ev.step + 1
        print(f"{Fore.CYAN}└── [*] Preparing for command generation step {next_step}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}    └── [?] Looping back to generate_command step with incremented step counter.{Style.RESET_ALL}")
        
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
        print(f"{Fore.CYAN}╔══════════════════════════════════════╗{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║     Plotter Workflow Complete        ║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}╚══════════════════════════════════════╝{Style.RESET_ALL}")
        
        print(f"{Fore.CYAN}[*] ├── Finalizing plotter execution{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   └── This step processes execution results and creates a comprehensive summary.{Style.RESET_ALL}")
        
        # Get final statistics
        commands = await ctx.get("commands", default=[])
        success_count = await ctx.get("success_count", default=0)
        failed_count = await ctx.get("failed_count", default=0)
        
        print(f"{Fore.GREEN}├── [+] Drawing prompt: {ev.prompt}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}├── [+] Commands executed: {ev.commands_executed}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}├── [+] Successful commands: {success_count}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}├── [+] Failed commands: {failed_count}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}└── [+] Steps taken: {ev.step_count}{Style.RESET_ALL}")
        
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
        
        print(f"{Fore.GREEN}└── [+] Plotter workflow execution complete{Style.RESET_ALL}")
        
        return StopEvent(result=result)


async def main():
    """Main function for testing the simple streaming workflow."""
    from llama_index.llms.ollama import Ollama
    from llama_index.llms.azure_openai import AzureOpenAI
    from ..plotter.simulated import SimulatedPlotter
    import os

    print(f"{Fore.CYAN}[*] ├── Starting plotter streaming workflow{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}[?] │   └── This is the main entry point that initializes the LLM, plotter, and runs the workflow.{Style.RESET_ALL}")
    
    # Create LLM instance
    print(f"{Fore.CYAN}├── [*] Initializing language model{Style.RESET_ALL}")
    llm = Ollama(model="llama3.2:3b", request_timeout=10000)

    # Optionally use Azure OpenAI if environment variables are set
    if all(os.environ.get(key) for key in ["GPT4_API_KEY", "GPT4_API_VERSION", "GPT4_ENDPOINT"]):
        print(f"{Fore.CYAN}├── [*] Configuring Azure OpenAI{Style.RESET_ALL}")
        llm = AzureOpenAI(
            model="gpt-4o",
            deployment_name="gpt-4o-gs",
            api_key=os.environ.get("GPT4_API_KEY"),
            api_version=os.environ.get("GPT4_API_VERSION"),
            azure_endpoint=os.environ.get("GPT4_ENDPOINT"),
            timeout=1220,
        )
    
    # Create plotter instance
    print(f"{Fore.CYAN}├── [*] Initializing simulated plotter{Style.RESET_ALL}")
    plotter = SimulatedPlotter(
        commands_log_file=f"results/logs/streaming_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
        visualize=True
    )
    
    try:
        # Create workflow
        print(f"{Fore.CYAN}├── [*] Creating workflow instance{Style.RESET_ALL}")
        workflow = SimplePlotterStreamWorkflow(llm=llm, plotter=plotter, timeout=10000)
        
        # Generate workflow visualization
        print(f"{Fore.CYAN}├── [*] Generating workflow visualization{Style.RESET_ALL}")
        try:
            from llama_index.utils.workflow import draw_all_possible_flows
            
            draw_all_possible_flows(
                SimplePlotterStreamWorkflow, filename="results/visualizations/gcode_workflow_streamer_simple.html"
            )
            
            print(f"{Fore.GREEN}│   └── Workflow visualization saved to results/visualizations/gcode_workflow_streamer_simple.html{Style.RESET_ALL}")
        except ImportError:
            print(f"{Fore.YELLOW}│   └── Workflow visualization not available - llama_index.utils.workflow not found{Style.RESET_ALL}")
        
        # Test with a prompt
        print(f"{Fore.CYAN}├── [*] Preparing test prompt{Style.RESET_ALL}")
        prompt = "draw a small house with a door and windows"
        
        # Run workflow
        print(f"{Fore.CYAN}├── [*] Executing streaming workflow{Style.RESET_ALL}")
        result = await workflow.run(prompt=prompt, max_steps=30)
        
        # Display results
        if result:
            print(f"\n{Fore.GREEN}[+] ├── Workflow completed successfully{Style.RESET_ALL}")
            print(f"{Fore.GREEN}[+] ├── Commands executed: {result.get('commands_executed', 0)}{Style.RESET_ALL}")
            print(f"{Fore.GREEN}[+] └── Success rate: {result.get('successful_commands', 0)}/{result.get('commands_executed', 0)}{Style.RESET_ALL}")
    
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}[!] └── Operation interrupted by user{Style.RESET_ALL}")
        # Ensure plotter is disconnected
        try:
            await plotter.disconnect()
        except:
            pass
    except Exception as e:
        print(f"{Fore.RED}[!] └── Error: {str(e)}{Style.RESET_ALL}")
        # Ensure plotter is disconnected
        try:
            await plotter.disconnect()
        except:
            pass


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())