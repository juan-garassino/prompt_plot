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
from datetime import datetime
from rich.console import Console

from ..core.base_workflow import BasePromptPlotWorkflow
from ..core.models import GCodeCommand, GCodeProgram
from ..core.exceptions import WorkflowException
from ..strategies import StrategySelector, PromptComplexity
from ..config import get_config
from ..llm import LLMProvider
from ..utils.rich_logger import WorkflowLogger

# Initialize Rich console and logger
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
        # Get prompt from event
        prompt = getattr(ev, "prompt", "draw a simple square")
        max_steps = getattr(ev, "max_steps", self.max_steps)
        
        # Display workflow start
        logger.stream_start("Sequential G-Code Generation", prompt, max_steps)
        
        # Initialize workflow
        logger.step_start("Initialize Workflow", "Setting up sequential command generation")
        
        # Initialize context using base workflow method
        await self.initialize_context(ctx, prompt, max_steps=max_steps)
        
        logger.step_info("Configuration loaded", {
            "Max steps": max_steps,
            "Max retries": self.max_retries,
            "Prompt": prompt
        })
        
        logger.step_success("Workflow initialized, starting command generation")
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
        logger.step_start(f"Generate Command #{ev.step}", "Creating next G-code command")
        
        # Track retries for this specific step
        task_key = f"retries_step_{ev.step}"
        
        # Check retry limits using base workflow method
        if not await self.check_retry_limits(ctx, ev.step, task_key):
            logger.step_error("Maximum retries exceeded", {"Step": ev.step, "Action": "Using COMPLETE fallback"})
            fallback_result = json.dumps({"command": "COMPLETE"})
            return CommandExtractionDone(output=fallback_result, prompt=ev.prompt, step=ev.step)
        
        # Get command history using base workflow method
        history = await self.get_command_history(ctx)
        
        current_retries = await ctx.get(task_key, default=0)
        max_retries = await ctx.get("max_retries")
        
        # Build prompt based on whether this is initial generation or retry after validation error
        if isinstance(ev, CommandValidationErrorEvent):
            logger.reflection_prompt(current_retries, max_retries, ev.error)
            
            try:
                response_text = await self.handle_retry_with_reflection(ev.error, ev.issues, ev.prompt)
            except Exception as e:
                logger.step_error("Reflection failed", {"Error": str(e)})
                fallback_result = json.dumps({"command": "COMPLETE"})
                return CommandExtractionDone(output=fallback_result, prompt=ev.prompt, step=ev.step)
        else:
            logger.step_info(f"Generating command #{ev.step}", {"History": f"{len(history.split(chr(10)))} previous commands"})
            prompt = NEXT_COMMAND_TEMPLATE.format(prompt=ev.prompt, history=history)
            
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
                fallback_result = json.dumps({"command": "COMPLETE"})
                return CommandExtractionDone(output=fallback_result, prompt=ev.prompt, step=ev.step)
        
        logger.step_success("Command generated")
        
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
        logger.step_start(f"Validate Command #{ev.step}", "Ensuring LLM output is valid G-code")
        
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
                else:
                    logger.step_warning("Retrying validation", {
                        "Attempt": f"{current_retries}/{max_retries}",
                        "Action": "Returning to generate_next_command with error details"
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
    async def process_command(self, ctx: Context, ev: ValidatedCommandEvent) -> Union[ContinueGenerationEvent, ProgramCompleteEvent]:
        """Process the validated command and decide whether to continue or complete.
        
        Args:
            ctx: The workflow context
            ev: The validated command event
            
        Returns:
            ContinueGenerationEvent or ProgramCompleteEvent
        """
        logger.step_start(f"Process Command #{ev.step}", "Adding command to program and checking completion")
        
        # Add command to history if it's not a COMPLETE command
        if not ev.is_complete:
            logger.step_info("Adding command to program")
            await self.add_command_to_history(ctx, ev.command)
            logger.step_success("Command added successfully")
        else:
            logger.step_info("Skipping COMPLETE command", {"Reason": "Control command, not part of G-code program"})
        
        # Check completion conditions
        logger.step_info("Checking completion conditions")
        
        # Get current commands for the result
        commands = await ctx.get("commands", default=[])
        
        if ev.is_complete:
            logger.step_success("Program complete via COMPLETE command", {"Action": "Moving to finalize_program"})
            return ProgramCompleteEvent(
                prompt=ev.prompt,
                commands=commands,
                step_count=ev.step
            )
        elif not await self.check_step_limits(ctx, ev.step):
            max_steps = await ctx.get("max_steps")
            logger.step_warning(f"Program complete via max steps limit ({max_steps})", {"Action": "Moving to finalize_program"})
            return ProgramCompleteEvent(
                prompt=ev.prompt,
                commands=commands,
                step_count=ev.step
            )
        else:
            # Continue to next step
            next_step = ev.step + 1
            logger.step_success(f"Continuing to step {next_step}", {"Action": "Moving to continue_generation"})
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
        logger.step_start(f"Continue to Step {ev.step}", "Preparing for next command generation")
        
        # Get current command list for context
        commands = await ctx.get("commands", default=[])
        logger.step_info("Checking current program state", {"Commands": len(commands)})
        
        # Generate next command
        logger.step_success("Preparing for next command generation", {"Action": "Looping back to generate_next_command"})
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
        logger.step_start("Finalize Program", "Processing all commands into complete G-code program")
        
        logger.step_info("Program summary", {
            "Prompt": ev.prompt,
            "Commands": len(ev.commands),
            "Steps": ev.step_count
        })
        
        # Create final program
        logger.step_info("Creating final G-code program")
        program = GCodeProgram(commands=ev.commands)
        gcode_text = program.to_gcode()
        
        # Show G-code preview
        if ev.commands:
            gcode_lines = [cmd.to_gcode() for cmd in ev.commands]
            logger.gcode_preview(gcode_lines, "Generated G-code Program")
        
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
        
        logger.workflow_complete(True, len(ev.commands), gcode_lines[:5] if ev.commands else None)
        return StopEvent(result=result)


async def main():
    """Main function for testing the advanced sequential workflow."""
    from llama_index.llms.ollama import Ollama
    from llama_index.llms.azure_openai import AzureOpenAI
    import os

    logger.workflow_start("Advanced Sequential G-Code Workflow", "Testing workflow with sample prompt")
    
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
    
    try:
        # Create workflow
        logger.step_success("LLM initialized successfully")
        logger.step_start("Create Workflow", "Instantiating SequentialGCodeWorkflow")
        workflow = SequentialGCodeWorkflow(llm=llm, timeout=10000)
        
        # Generate workflow visualization
        logger.step_info("Generating workflow visualization")
        try:
            from llama_index.utils.workflow import draw_all_possible_flows
            
            draw_all_possible_flows(
                SequentialGCodeWorkflow, filename="results/visualizations/gcode_workflow_sequential.html"
            )
            
            logger.step_success("Workflow visualization saved", {"File": "results/visualizations/gcode_workflow_sequential.html"})
        except ImportError:
            logger.step_warning("Workflow visualization not available", {"Reason": "llama_index.utils.workflow not found"})
        
        # Test with a prompt
        prompt = "draw a small house with a door and windows"
        logger.step_info("Preparing test prompt", {"Prompt": prompt})
        
        # Run workflow
        logger.step_start("Execute Workflow", "Running workflow with test prompt")
        result = await workflow.run(prompt=prompt, max_steps=50)
        
        # Save G-code to file
        if result:
            filename = f"results/gcode/sequential_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(filename, 'w') as f:
                f.write(result.get("gcode", ""))
            logger.step_success("G-code saved", {
                "File": filename,
                "Commands": result.get('commands_count', 0)
            })
    
    except KeyboardInterrupt:
        logger.step_warning("Operation interrupted by user", {"Action": "Workflow execution stopped"})
    except Exception as e:
        logger.step_error("Workflow execution failed", {"Error": str(e)})


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())