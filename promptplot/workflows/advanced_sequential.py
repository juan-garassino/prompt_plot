"""
Advanced Sequential G-Code Workflow

Refactored from boilerplates/generate_llm_advanced.py to use the new modular architecture.
This workflow generates G-code commands one at a time with step-by-step generation logic
and enhanced error handling.
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
from ..core.models import GCodeCommand, GCodeProgram
from ..core.exceptions import WorkflowException
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

# Event Classes
class GenerateNextCommandEvent(Event):
    """Event to trigger generation of next G-code command."""
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
    """Event containing a validated G-code command."""
    command: GCodeCommand
    prompt: str
    step: int
    is_complete: bool

class ContinueGenerationEvent(Event):
    """Event to signal continuing to next command."""
    prompt: str
    step: int

class ProgramCompleteEvent(Event):
    """Event indicating program is complete."""
    prompt: str
    commands: List[GCodeCommand]
    step_count: int

class SequentialGCodeWorkflow(BasePromptPlotWorkflow):
    """Advanced workflow for generating G-code commands one at a time.
    
    This workflow inherits from BasePromptPlotWorkflow and implements a sequential
    generation approach where commands are generated one at a time, with each
    command building on the context of previous commands.
    
    Integrates with:
    - Strategy selector for optimal G-code generation approach
    - Configuration system for customizable parameters
    - LLM provider abstraction for flexible LLM backends
    
    Workflow steps in sequential order:
    1. start → Initialize workflow and begin with first command
    2. generate_next_command → Create single next G-code command
    3. validate_command → Ensure command follows correct format
       → If validation fails: retry via CommandValidationErrorEvent back to step 2
    4. process_command → Add command to program and check completion conditions
       → If program is complete: go to step 6 via ProgramCompleteEvent
       → If more commands needed: go to step 5 via ContinueGenerationEvent
    5. continue_generation → Set up for next command and loop back to step 2
    6. finalize_program → Create final program and return results
    """
    
    def __init__(self, llm: Optional[LLMProvider] = None, **kwargs):
        """Initialize workflow with integrated components.
        
        Args:
            llm: LLM provider instance (uses config default if None)
            **kwargs: Additional arguments passed to base workflow
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
        
        super().__init__(llm=llm, **kwargs)

    @step
    async def start(self, ctx: Context, ev: StartEvent) -> GenerateNextCommandEvent:
        """Start the workflow and initialize context.
        
        Args:
            ctx: The workflow context
            ev: The start event
            
        Returns:
            GenerateNextCommandEvent to trigger command generation
        """
        print(f"{Fore.CYAN}╔══════════════════════════════════════════════╗{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║ Sequential G-Code Generation Workflow Start  ║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}╚══════════════════════════════════════════════╝{Style.RESET_ALL}")
        
        print(f"{Fore.CYAN}[*] ├── Initializing workflow{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   └── This step prepares the workflow by setting up context variables and parameters needed for G-code generation.{Style.RESET_ALL}")
        
        # Get prompt from event
        prompt = getattr(ev, "prompt", "draw a simple square")
        max_steps = getattr(ev, "max_steps", self.max_steps)
        
        # Initialize context using base workflow method
        await self.initialize_context(ctx, prompt, max_steps=max_steps)
        
        print(f"{Fore.GREEN}├── [+] Workflow initialization complete{Style.RESET_ALL}")
        print(f"{Fore.GREEN}├── [+] Drawing prompt: {prompt}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}├── [+] Max steps: {max_steps}{Style.RESET_ALL}")
        
        # Start with step 1
        print(f"{Fore.CYAN}└── [*] Starting first command generation{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}    └── [?] Moving to generate_next_command step to create the first G-code command.{Style.RESET_ALL}")
        return GenerateNextCommandEvent(prompt=prompt, step=1)
    
    @step
    async def generate_next_command(self, ctx: Context, ev: Union[GenerateNextCommandEvent, CommandValidationErrorEvent]) -> CommandExtractionDone:
        """Generate the next G-code command.
        
        Args:
            ctx: The workflow context
            ev: GenerateNextCommandEvent or CommandValidationErrorEvent
            
        Returns:
            CommandExtractionDone with raw LLM output
        """
        print(f"{Fore.CYAN}[*] ├── Generating command for step {ev.step}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   └── This step uses the LLM to generate a single G-code command based on the drawing prompt and previous commands.{Style.RESET_ALL}")
        
        # Track retries for this specific step
        task_key = f"retries_step_{ev.step}"
        
        # Check retry limits using base workflow method
        if not await self.check_retry_limits(ctx, ev.step, task_key):
            print(f"{Fore.RED}├── [!] Maximum retries exceeded for step {ev.step}{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}│   └── [?] After multiple failed attempts, using a COMPLETE command to gracefully terminate the workflow.{Style.RESET_ALL}")
            
            # Return a COMPLETE command to force termination
            fallback_result = json.dumps({"command": "COMPLETE"})
            
            print(f"{Fore.GREEN}└── [+] Fallback command generated{Style.RESET_ALL}")
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
        
        # Build prompt based on whether this is initial generation or retry after validation error
        print(f"{Fore.CYAN}├── [*] Building LLM prompt{Style.RESET_ALL}")
        if isinstance(ev, CommandValidationErrorEvent):
            print(f"{Fore.YELLOW}│   ├── Previous generation failed validation{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}│   │   └── [?] Using reflection prompt to help LLM correct previous errors.{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}│   └── Error: {ev.error}{Style.RESET_ALL}")
            
            # Use base workflow reflection method
            try:
                response_text = await self.handle_retry_with_reflection(
                    ev.error, ev.issues, ev.prompt
                )
            except Exception as e:
                print(f"{Fore.RED}│   └── [!] Reflection failed: {str(e)}{Style.RESET_ALL}")
                # Fallback to COMPLETE command
                fallback_result = json.dumps({"command": "COMPLETE"})
                return CommandExtractionDone(
                    output=fallback_result,
                    prompt=ev.prompt,
                    step=ev.step
                )
        else:
            print(f"{Fore.CYAN}│   └── Using standard next command template{Style.RESET_ALL}")
            prompt = NEXT_COMMAND_TEMPLATE.format(
                prompt=ev.prompt,
                history=history
            )
            
            # Generate command using the LLM
            print(f"{Fore.CYAN}├── [*] Calling LLM API{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}│   └── [?] Sending prompt to language model to generate the next G-code command.{Style.RESET_ALL}")
            
            try:
                if hasattr(self.llm, 'acomplete'):
                    response = await self.llm.acomplete(prompt)
                    response_text = response.text
                else:
                    response = self.llm.complete(prompt)
                    response_text = response.text
            except Exception as e:
                print(f"{Fore.RED}│   └── [!] LLM call failed: {str(e)}{Style.RESET_ALL}")
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
    async def validate_command(self, ctx: Context, ev: CommandExtractionDone) -> Union[CommandValidationErrorEvent, ValidatedCommandEvent]:
        """Validate the generated command.
        
        Args:
            ctx: The workflow context
            ev: The command extraction done event
            
        Returns:
            CommandValidationErrorEvent if validation fails, ValidatedCommandEvent if successful
        """
        print(f"{Fore.CYAN}[*] ├── Validating command for step {ev.step}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   └── This step ensures the LLM output is a valid G-code command by parsing JSON and checking format.{Style.RESET_ALL}")
        
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
                else:
                    print(f"{Fore.YELLOW}├── [!] Retrying - Attempt {current_retries}/{max_retries} failed{Style.RESET_ALL}")
                    print(f"{Fore.YELLOW}└── [?] Returning to generate_next_command with error details to help LLM correct its output.{Style.RESET_ALL}")
                
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
    async def process_command(self, ctx: Context, ev: ValidatedCommandEvent) -> Union[ContinueGenerationEvent, ProgramCompleteEvent]:
        """Process the validated command and decide whether to continue or complete.
        
        Args:
            ctx: The workflow context
            ev: The validated command event
            
        Returns:
            ContinueGenerationEvent or ProgramCompleteEvent
        """
        print(f"{Fore.CYAN}[*] ├── Processing command for step {ev.step}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   └── This step adds the validated command to the program and determines if generation should continue or end.{Style.RESET_ALL}")
        
        # Add command to history if it's not a COMPLETE command
        if not ev.is_complete:
            print(f"{Fore.CYAN}├── [*] Adding command to program{Style.RESET_ALL}")
            await self.add_command_to_history(ctx, ev.command)
            print(f"{Fore.GREEN}│   └── Command added successfully{Style.RESET_ALL}")
        else:
            print(f"{Fore.CYAN}├── [*] Skipping COMPLETE command{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}│   └── [?] COMPLETE is a control command, not part of the actual G-code program.{Style.RESET_ALL}")
        
        # Check completion conditions
        print(f"{Fore.CYAN}├── [*] Checking completion conditions{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}│   └── [?] Determining if workflow should end based on COMPLETE command or max steps limit.{Style.RESET_ALL}")
        
        # Get current commands for the result
        commands = await ctx.get("commands", default=[])
        
        if ev.is_complete:
            print(f"{Fore.GREEN}└── [+] Program complete via COMPLETE command{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}    └── [?] Moving to finalize_program step to process results.{Style.RESET_ALL}")
            return ProgramCompleteEvent(
                prompt=ev.prompt,
                commands=commands,
                step_count=ev.step
            )
        elif not await self.check_step_limits(ctx, ev.step):
            max_steps = await ctx.get("max_steps")
            print(f"{Fore.YELLOW}└── [!] Program complete via max steps limit ({max_steps}){Style.RESET_ALL}")
            print(f"{Fore.YELLOW}    └── [?] Reached maximum allowed steps, moving to finalize_program to prevent infinite loops.{Style.RESET_ALL}")
            return ProgramCompleteEvent(
                prompt=ev.prompt,
                commands=commands,
                step_count=ev.step
            )
        else:
            # Continue to next step
            next_step = ev.step + 1
            print(f"{Fore.GREEN}└── [+] Continuing to step {next_step}{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}    └── [?] Moving to continue_generation step to prepare for next command.{Style.RESET_ALL}")
            return ContinueGenerationEvent(
                prompt=ev.prompt,
                step=next_step
            )
    
    @step
    async def continue_generation(self, ctx: Context, ev: ContinueGenerationEvent) -> GenerateNextCommandEvent:
        """Continue to the next command generation step.
        
        Args:
            ctx: The workflow context
            ev: The continue generation event
            
        Returns:
            GenerateNextCommandEvent for the next step
        """
        print(f"{Fore.CYAN}[*] ├── Continuing to next command (step {ev.step}){Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   └── This step prepares for generating the next command by resetting retry counters and context.{Style.RESET_ALL}")
        
        # Get current command list for context
        print(f"{Fore.CYAN}├── [*] Checking current program state{Style.RESET_ALL}")
        commands = await ctx.get("commands", default=[])
        print(f"{Fore.CYAN}│   └── Current program has {len(commands)} commands{Style.RESET_ALL}")
        
        # Generate next command
        print(f"{Fore.CYAN}└── [*] Preparing for next command generation{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}    └── [?] Looping back to generate_next_command step with incremented step counter.{Style.RESET_ALL}")
        return GenerateNextCommandEvent(
            prompt=ev.prompt,
            step=ev.step
        )
    
    @step
    async def finalize_program(self, ctx: Context, ev: ProgramCompleteEvent) -> StopEvent:
        """Finalize the G-code program and return results.
        
        Args:
            ctx: The workflow context
            ev: The program complete event
            
        Returns:
            StopEvent with the complete G-code program
        """
        print(f"{Fore.CYAN}╔══════════════════════════════════════════════╗{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║ Sequential G-Code Generation Workflow End    ║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}╚══════════════════════════════════════════════╝{Style.RESET_ALL}")
        
        print(f"{Fore.CYAN}[*] ├── Finalizing G-code program{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   └── This step processes all generated commands into a complete G-code program and saves results.{Style.RESET_ALL}")
        
        print(f"{Fore.GREEN}├── [+] Drawing prompt: {ev.prompt}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}├── [+] Commands generated: {len(ev.commands)}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}└── [+] Steps taken: {ev.step_count}{Style.RESET_ALL}")
        
        # Create final program
        print(f"{Fore.CYAN}[*] ├── Creating final G-code program{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   └── Converting command objects to formatted G-code text.{Style.RESET_ALL}")
        program = GCodeProgram(commands=ev.commands)
        gcode_text = program.to_gcode()
        
        # Show some of the G-code
        print(f"{Fore.CYAN}├── [*] Generating program preview{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}│   └── [?] Showing a sample of the generated G-code to verify output quality.{Style.RESET_ALL}")
        preview_lines = min(10, len(ev.commands))
        for i in range(preview_lines):
            cmd = ev.commands[i]
            print(f"{Fore.BLUE}    {cmd.to_gcode()}{Style.RESET_ALL}")
            
        if len(ev.commands) > preview_lines:
            print(f"{Fore.BLUE}    ... ({len(ev.commands) - preview_lines} more lines) ...{Style.RESET_ALL}")
        
        # Update context with final step count
        await ctx.set("step_count", ev.step_count)
        
        # Create workflow result using base workflow method
        result_obj = await self.create_workflow_result(ctx, success=True)
        
        # Convert to dictionary for compatibility
        result = {
            "prompt": ev.prompt,
            "commands_count": len(ev.commands),
            "gcode": gcode_text,
            "step_count": ev.step_count,
            "program": program.model_dump(),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        print(f"{Fore.GREEN}└── [+] Workflow execution complete{Style.RESET_ALL}")
        return StopEvent(result=result)


async def main():
    """Main function for testing the advanced sequential workflow."""
    from llama_index.llms.ollama import Ollama
    from llama_index.llms.azure_openai import AzureOpenAI
    import os

    print(f"{Fore.CYAN}[*] ├── Starting G-code generation workflow{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}[?] │   └── This is the main entry point that initializes the LLM and runs the workflow.{Style.RESET_ALL}")
    
    # Create LLM instance
    print(f"{Fore.CYAN}├── [*] Initializing language model{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}│   └── [?] Setting up the LLM that will generate G-code commands based on prompts.{Style.RESET_ALL}")
    
    llm = Ollama(model="llama3.2:3b", request_timeout=10000)

    # Optionally use Azure OpenAI if environment variables are set
    if all(os.environ.get(key) for key in ["GPT4_API_KEY", "GPT4_API_VERSION", "GPT4_ENDPOINT"]):
        print(f"{Fore.CYAN}├── [*] Configuring Azure OpenAI{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}│   └── [?] Switching to Azure OpenAI for more advanced capabilities.{Style.RESET_ALL}")
        
        llm = AzureOpenAI(
            model="gpt-4o",
            deployment_name="gpt-4o-gs",
            api_key=os.environ.get("GPT4_API_KEY"),
            api_version=os.environ.get("GPT4_API_VERSION"),
            azure_endpoint=os.environ.get("GPT4_ENDPOINT"),
            timeout=1220,
        )
    
    try:
        # Create workflow
        print(f"{Fore.CYAN}├── [*] Creating workflow instance{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}│   └── [?] Instantiating the SequentialGCodeWorkflow with configured LLM.{Style.RESET_ALL}")
        workflow = SequentialGCodeWorkflow(llm=llm, timeout=10000)
        
        # Generate workflow visualization
        print(f"{Fore.CYAN}├── [*] Generating workflow visualization{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}│   └── [?] Creating a visual representation of the workflow to aid understanding.{Style.RESET_ALL}")
        try:
            from llama_index.utils.workflow import draw_all_possible_flows
            
            draw_all_possible_flows(
                SequentialGCodeWorkflow, filename="results/visualizations/gcode_workflow_sequential.html"
            )
            
            print(f"{Fore.GREEN}│   └── Workflow visualization saved to results/visualizations/gcode_workflow_sequential.html{Style.RESET_ALL}")
        except ImportError:
            print(f"{Fore.YELLOW}│   └── Workflow visualization not available - llama_index.utils.workflow not found{Style.RESET_ALL}")
        
        # Test with a prompt
        print(f"{Fore.CYAN}├── [*] Preparing test prompt{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}│   └── [?] Setting up a sample prompt to test the G-code generation workflow.{Style.RESET_ALL}")
        prompt = "draw a small house with a door and windows"
        
        # Run workflow
        print(f"{Fore.CYAN}├── [*] Executing workflow{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}│   └── [?] Running the workflow with the test prompt and maximum 50 steps.{Style.RESET_ALL}")
        result = await workflow.run(prompt=prompt, max_steps=50)
        
        # Save G-code to file
        if result:
            filename = f"results/gcode/sequential_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(filename, 'w') as f:
                f.write(result.get("gcode", ""))
            print(f"{Fore.GREEN}├── [+] G-code saved to {filename}{Style.RESET_ALL}")
            print(f"{Fore.GREEN}└── [+] Generated {result.get('commands_count', 0)} commands{Style.RESET_ALL}")
    
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}[!] └── Operation interrupted by user{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?]     └── Workflow execution was manually stopped before completion.{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}[!] └── Error: {str(e)}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?]     └── An unexpected error occurred during workflow execution.{Style.RESET_ALL}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())