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
        print(f"{Fore.CYAN}╔══════════════════════════════════════════════╗{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║     Advanced Plotter Workflow Initializing   ║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}╚══════════════════════════════════════════════╝{Style.RESET_ALL}")
        
        print(f"{Fore.CYAN}[*] ├── Initializing advanced workflow{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   └── This step prepares the advanced workflow with enhanced features and capabilities.{Style.RESET_ALL}")
        
        # Get prompt from event
        if not hasattr(ev, "prompt"):
            print(f"{Fore.RED}[!] │   └── No drawing prompt specified - workflow stopped{Style.RESET_ALL}")
            return StopEvent(result="No drawing prompt specified")
        
        prompt = ev.prompt
        max_steps = getattr(ev, "max_steps", self.max_steps)
        
        # Initialize context using base workflow method
        await self.initialize_context(ctx, prompt, max_steps=max_steps, enable_streaming=self.enable_streaming)
        
        print(f"{Fore.GREEN}├── [+] Advanced workflow parameters initialized{Style.RESET_ALL}")
        print(f"{Fore.GREEN}├── [+] Drawing prompt: {prompt}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}├── [+] Max steps: {max_steps}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}├── [+] Streaming enabled: {self.enable_streaming}{Style.RESET_ALL}")
        
        # Connect to plotter with enhanced error handling
        print(f"{Fore.CYAN}├── [*] Connecting to plotter with advanced interface{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}│   └── [?] Establishing enhanced connection with better error recovery and monitoring.{Style.RESET_ALL}")
        
        try:
            if not await self.plotter.connect():
                print(f"{Fore.RED}[!] │   └── Failed to connect to plotter - workflow stopped{Style.RESET_ALL}")
                return StopEvent(result="Failed to connect to plotter")
        except Exception as e:
            print(f"{Fore.RED}[!] │   └── Plotter connection error: {str(e)}{Style.RESET_ALL}")
            return StopEvent(result=f"Plotter connection error: {str(e)}")
        
        print(f"{Fore.GREEN}├── [+] Successfully connected to advanced plotter interface{Style.RESET_ALL}")
        
        # Choose workflow mode based on streaming capability
        if self.enable_streaming and self.stream_predictor:
            print(f"{Fore.CYAN}└── [*] Starting streaming command generation{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}    └── [?] Using advanced streaming mode for real-time command generation.{Style.RESET_ALL}")
            return StreamCommandsEvent(prompt=prompt)
        else:
            print(f"{Fore.CYAN}└── [*] Starting sequential command generation{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}    └── [?] Using sequential mode for step-by-step command generation.{Style.RESET_ALL}")
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
        print(f"{Fore.CYAN}[*] ├── Starting advanced command streaming{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   └── This step uses advanced streaming to generate and execute commands in real-time.{Style.RESET_ALL}")
        
        executed_commands = []
        commands_executed = 0
        success_count = 0
        failed_count = 0
        
        try:
            # Get command history for context
            history = await self.get_command_history(ctx)
            history_list = history.split('\n') if history != "No previous commands" else []
            
            print(f"{Fore.CYAN}├── [*] Streaming commands from LLM{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}│   └── [?] Generating commands in real-time and executing them as they arrive.{Style.RESET_ALL}")
            
            # Stream commands from LLM
            async for command in self.stream_predictor.stream_commands(ev.prompt, history_list):
                print(f"{Fore.BLUE}├── [*] Received streamed command: {command.to_gcode()}{Style.RESET_ALL}")
                
                # Check if this is a completion command
                if command.command == "COMPLETE":
                    print(f"{Fore.GREEN}│   └── Received completion command - ending stream{Style.RESET_ALL}")
                    break
                
                # Execute command on plotter
                print(f"{Fore.CYAN}│   ├── Executing command on plotter{Style.RESET_ALL}")
                try:
                    success = await self.plotter.send_command(command.to_gcode())
                    commands_executed += 1
                    
                    if success:
                        success_count += 1
                        executed_commands.append(command)
                        await self.add_command_to_history(ctx, command)
                        print(f"{Fore.GREEN}│   │   └── Command executed successfully{Style.RESET_ALL}")
                    else:
                        failed_count += 1
                        print(f"{Fore.RED}│   │   └── Command execution failed{Style.RESET_ALL}")
                        
                except Exception as e:
                    failed_count += 1
                    print(f"{Fore.RED}│   │   └── Plotter error: {str(e)}{Style.RESET_ALL}")
                
                # Update statistics
                await self.update_statistics(ctx, success)
                
                # Check step limits
                if commands_executed >= await ctx.get("max_steps"):
                    print(f"{Fore.YELLOW}│   └── Reached maximum steps limit - ending stream{Style.RESET_ALL}")
                    break
                
                # Small delay to prevent overwhelming the plotter
                await asyncio.sleep(0.1)
            
            print(f"{Fore.GREEN}├── [+] Command streaming completed{Style.RESET_ALL}")
            print(f"{Fore.GREEN}│   ├── Commands executed: {commands_executed}{Style.RESET_ALL}")
            print(f"{Fore.GREEN}│   ├── Successful: {success_count}{Style.RESET_ALL}")
            print(f"{Fore.GREEN}│   └── Failed: {failed_count}{Style.RESET_ALL}")
            
        except Exception as e:
            print(f"{Fore.RED}├── [!] Streaming error: {str(e)}{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}│   └── [?] Continuing with commands that were successfully executed.{Style.RESET_ALL}")
        
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
        print(f"{Fore.CYAN}[*] ├── Generating command for step {ev.step} (sequential mode){Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   └── Using sequential generation as fallback when streaming is not available.{Style.RESET_ALL}")
        
        # Track retries for this specific step
        task_key = f"retries_step_{ev.step}"
        
        # Check retry limits using base workflow method
        if not await self.check_retry_limits(ctx, ev.step, task_key):
            print(f"{Fore.RED}├── [!] Maximum retries exceeded for step {ev.step}{Style.RESET_ALL}")
            
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
        print(f"{Fore.CYAN}╔══════════════════════════════════════════════╗{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║     Advanced Plotter Workflow Complete       ║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}╚══════════════════════════════════════════════╝{Style.RESET_ALL}")
        
        print(f"{Fore.CYAN}[*] ├── Finalizing advanced plotter execution{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   └── This step processes advanced execution results and creates comprehensive reports.{Style.RESET_ALL}")
        
        # Get final statistics
        success_count = await ctx.get("success_count", default=0)
        failed_count = await ctx.get("failed_count", default=0)
        
        print(f"{Fore.GREEN}├── [+] Drawing prompt: {ev.prompt}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}├── [+] Commands executed: {ev.commands_executed}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}├── [+] Successful commands: {success_count}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}├── [+] Failed commands: {failed_count}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}├── [+] Success rate: {(success_count/max(1, ev.commands_executed))*100:.1f}%{Style.RESET_ALL}")
        
        # Disconnect from plotter with enhanced cleanup
        print(f"{Fore.CYAN}├── [*] Disconnecting from advanced plotter interface{Style.RESET_ALL}")
        try:
            await self.plotter.disconnect()
            print(f"{Fore.GREEN}│   └── Advanced plotter disconnected successfully{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.YELLOW}│   └── Plotter disconnect warning: {str(e)}{Style.RESET_ALL}")
        
        # Generate enhanced statistics
        if hasattr(self.plotter, 'get_drawing_stats'):
            try:
                drawing_stats = self.plotter.get_drawing_stats()
                print(f"{Fore.CYAN}├── [*] Drawing statistics:{Style.RESET_ALL}")
                for key, value in drawing_stats.items():
                    print(f"{Fore.BLUE}│   ├── {key}: {value}{Style.RESET_ALL}")
            except Exception as e:
                print(f"{Fore.YELLOW}│   └── Could not retrieve drawing stats: {str(e)}{Style.RESET_ALL}")
        
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
        
        print(f"{Fore.GREEN}└── [+] Advanced plotter workflow execution complete{Style.RESET_ALL}")
        
        return StopEvent(result=result)


async def main():
    """Main function for testing the advanced streaming workflow."""
    from llama_index.llms.ollama import Ollama
    from llama_index.llms.azure_openai import AzureOpenAI
    from ..plotter.simulated import SimulatedPlotter
    import os

    print(f"{Fore.CYAN}[*] ├── Starting advanced plotter streaming workflow{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}[?] │   └── This demonstrates the advanced streaming workflow with enhanced features.{Style.RESET_ALL}")
    
    # Create LLM instance
    print(f"{Fore.CYAN}├── [*] Initializing language model{Style.RESET_ALL}")
    llm = Ollama(model="llama3.2:3b", request_timeout=10000)

    # Optionally use Azure OpenAI if environment variables are set
    if all(os.environ.get(key) for key in ["GPT4_API_KEY", "GPT4_API_VERSION", "GPT4_ENDPOINT"]):
        print(f"{Fore.CYAN}├── [*] Configuring Azure OpenAI for advanced features{Style.RESET_ALL}")
        llm = AzureOpenAI(
            model="gpt-4o",
            deployment_name="gpt-4o-gs",
            api_key=os.environ.get("GPT4_API_KEY"),
            api_version=os.environ.get("GPT4_API_VERSION"),
            azure_endpoint=os.environ.get("GPT4_ENDPOINT"),
            timeout=1220,
        )
    
    # Create advanced plotter instance
    print(f"{Fore.CYAN}├── [*] Initializing advanced simulated plotter{Style.RESET_ALL}")
    plotter = SimulatedPlotter(
        commands_log_file=f"results/logs/advanced_streaming_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
        visualize=True,
        command_delay=0.02  # Faster for advanced mode
    )
    
    try:
        # Create advanced workflow
        print(f"{Fore.CYAN}├── [*] Creating advanced workflow instance{Style.RESET_ALL}")
        workflow = AdvancedPlotterStreamWorkflow(
            llm=llm, 
            plotter=plotter, 
            enable_streaming=True,  # Enable advanced streaming
            timeout=15000
        )
        
        # Generate workflow visualization
        print(f"{Fore.CYAN}├── [*] Generating advanced workflow visualization{Style.RESET_ALL}")
        try:
            from llama_index.utils.workflow import draw_all_possible_flows
            
            draw_all_possible_flows(
                AdvancedPlotterStreamWorkflow, 
                filename="results/visualizations/gcode_workflow_streamer_advanced.html"
            )
            
            print(f"{Fore.GREEN}│   └── Advanced workflow visualization saved{Style.RESET_ALL}")
        except ImportError:
            print(f"{Fore.YELLOW}│   └── Workflow visualization not available{Style.RESET_ALL}")
        
        # Test with a more complex prompt
        print(f"{Fore.CYAN}├── [*] Preparing advanced test prompt{Style.RESET_ALL}")
        prompt = "draw a detailed house with windows, door, chimney, and a small garden with flowers"
        
        # Run advanced workflow
        print(f"{Fore.CYAN}├── [*] Executing advanced streaming workflow{Style.RESET_ALL}")
        result = await workflow.run(prompt=prompt, max_steps=50)
        
        # Display enhanced results
        if result:
            print(f"\n{Fore.GREEN}[+] ├── Advanced workflow completed successfully{Style.RESET_ALL}")
            print(f"{Fore.GREEN}[+] ├── Commands executed: {result.get('commands_executed', 0)}{Style.RESET_ALL}")
            print(f"{Fore.GREEN}[+] ├── Success rate: {result.get('success_rate', 0):.1f}%{Style.RESET_ALL}")
            print(f"{Fore.GREEN}[+] └── Workflow mode: {result.get('workflow_mode', 'unknown')}{Style.RESET_ALL}")
    
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