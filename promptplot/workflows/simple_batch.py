"""
Simple Batch G-Code Workflow

Refactored from boilerplates/generate_llm_simple.py to use the new modular architecture.
This workflow generates G-code in a single batch operation with validation and retry logic.
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
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.text import Text
from rich.tree import Tree
from rich import box

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
GCODE_PROGRAM_TEMPLATE = """
Create G-code for a pen plotter. Prompt: {prompt}

Return a JSON with "commands" list containing G-code commands.
Format:
{{
    "commands": [
        {{"command": "G0", "x": 0, "y": 0}},
        {{"command": "G1", "x": 10, "y": 10, "f": 1000}}
    ]
}}

Include pen up/down movements with M3/M5 commands.
Use realistic coordinates and values.
Ensure the drawing is complete and the pen returns to the starting position.
write just the JSON, no other text.
"""

REFLECTION_PROMPT = """
Your previous response had validation errors and could not be processed correctly.

Previous response: {wrong_answer}

Error details: {error}

Please reflect on these errors and produce a valid response that strictly follows the required JSON format.
Make sure to:
1. Use proper JSON syntax with correct quotes, commas, and brackets
2. Include all required fields 
3. Follow the schema definition precisely
4. Use valid commands (starting with G or M)
5. Use the right data types (numbers for coordinates, strings for command names)

Return ONLY the corrected JSON with no additional text, code blocks, or explanations.
"""

# Event Classes
class GenerateGCodeEvent(Event):
    """Event to trigger G-code generation."""
    prompt: str

class GCodeExtractionDone(Event):
    """Event indicating G-code extraction is complete but not yet validated."""
    output: str
    prompt: str

class GCodeValidationErrorEvent(Event):
    """Event for validation errors in G-code generation."""
    error: str
    issues: str
    prompt: str

class ValidatedGCodeEvent(Event):
    """Event containing validated G-code program."""
    program: GCodeProgram
    gcode_text: str
    prompt: str

class SimpleGCodeWorkflow(BasePromptPlotWorkflow):
    """Simple workflow for generating and validating G-code in batch mode.
    
    This workflow inherits from BasePromptPlotWorkflow and implements a simple
    batch generation approach where the entire G-code program is generated
    in a single LLM call, then validated and refined if necessary.
    
    Integrates with:
    - Strategy selector for optimal G-code generation approach
    - Configuration system for customizable parameters
    - LLM provider abstraction for flexible LLM backends
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
    async def start(self, ctx: Context, ev: StartEvent) -> GenerateGCodeEvent:
        """Start the workflow and initialize context.
        
        Args:
            ctx: The workflow context
            ev: The start event
            
        Returns:
            GenerateGCodeEvent to trigger G-code generation
        """
        # Get prompt
        prompt = getattr(ev, "prompt", "draw a simple square")
        
        # Display workflow start
        logger.workflow_start("G-Code Generation Workflow", prompt)
        
        # Initialize workflow
        logger.step_start("Initialize Workflow", "Setting up context and configuration")
        
        # Store max retries in context
        await ctx.store.set("max_retries", self.max_retries)
        await ctx.store.set("prompt", prompt)
        
        logger.step_info("Configuration loaded", {
            "Max retries": self.max_retries,
            "Max steps": self.max_steps,
            "Prompt": prompt
        })
        
        # Analyze prompt complexity using strategy selector
        complexity = self.strategy_selector.analyze_prompt_complexity(prompt)
        await ctx.store.set("complexity", complexity)
        
        # Display strategy analysis
        strategy = self.strategy_selector.select_strategy(prompt)
        logger.strategy_analysis(
            strategy.__class__.__name__,
            {
                'complexity_level': complexity.complexity_level.value,
                'requires_curves': complexity.requires_curves,
                'estimated_commands': complexity.estimated_commands,
                'confidence_score': complexity.confidence_score
            }
        )
        
        logger.step_success("Workflow initialized successfully")
        
        return GenerateGCodeEvent(prompt=prompt)
    
    @step
    async def generate_gcode(self, ctx: Context, ev: Union[GenerateGCodeEvent, GCodeValidationErrorEvent]) -> GCodeExtractionDone:
        """Generate G-code for the plotter.
        
        Args:
            ctx: The workflow context
            ev: GenerateGCodeEvent or GCodeValidationErrorEvent
            
        Returns:
            GCodeExtractionDone with raw LLM output
        """
        # Start G-code generation step
        logger.step_start("G-Code Generation", "Using LLM to generate G-code from prompt")
        
        # Track retries for this generation
        task_key = "gcode_generation_retries"
        current_retries = await ctx.store.get(task_key, default=0)
        max_retries = await ctx.store.get("max_retries")
        
        # Check if max retries exceeded
        if current_retries >= max_retries:
            logger.step_error("Maximum retries exceeded", {
                "Attempts": f"{current_retries}/{max_retries}",
                "Action": "Using fallback G-code"
            })
            
            # Return a fallback empty program
            fallback_result = json.dumps({
                "commands": [
                    {"command": "G0", "x": 0, "y": 0},
                    {"command": "G0", "x": 0, "y": 0}
                ]
            })
            
            return GCodeExtractionDone(
                output=fallback_result,
                prompt=ev.prompt
            )
        
        # Increment retry counter
        await ctx.store.set(task_key, current_retries + 1)
        
        # Show retry attempt if this is a retry
        if isinstance(ev, GCodeValidationErrorEvent):
            logger.retry_attempt(current_retries, max_retries, "Previous validation failed")
        # Build prompt based on whether this is initial generation or retry after validation error
        if isinstance(ev, GCodeValidationErrorEvent):
            logger.step_info("Using reflection prompt", {
                "Reason": "Previous validation failed",
                "Error": ev.error[:100] + "..." if len(ev.error) > 100 else ev.error
            })
            
            # Include reflection prompt for retry
            prompt = REFLECTION_PROMPT.format(
                wrong_answer=ev.issues,
                error=ev.error
            )
        else:
            logger.step_info("Using standard G-code template")
            prompt = GCODE_PROGRAM_TEMPLATE.format(
                prompt=ev.prompt
            )
        
        # Generate G-code using the LLM
        llm_type = type(self.llm).__name__
        logger.llm_call(llm_type, "", ev.prompt[:50])
        
        response = await self.llm.acomplete(prompt)
        
        logger.step_success("G-code generation completed")
        
        return GCodeExtractionDone(
            output=response.text,
            prompt=ev.prompt
        )
    
    @step
    async def validate_gcode(self, ctx: Context, ev: GCodeExtractionDone) -> Union[GCodeValidationErrorEvent, ValidatedGCodeEvent]:
        """Validate the generated G-code using the base workflow validation method.
        
        Args:
            ctx: The workflow context
            ev: The G-code extraction done event
            
        Returns:
            GCodeValidationErrorEvent if validation fails, ValidatedGCodeEvent if successful
        """
        # Start validation step
        logger.step_start("G-Code Validation", "Parsing and validating generated G-code")
        
        # Check retry status
        task_key = "gcode_generation_retries"
        current_retries = await ctx.store.get(task_key, default=0)
        max_retries = await ctx.store.get("max_retries")
        
        try:
            # Use the base workflow validation method
            result = await self.validate_gcode_command(ev.output)
            
            if isinstance(result, Exception):
                # Validation failed
                error_msg = str(result)
                logger.validation_result(False, 0, [error_msg])
                
                if current_retries >= max_retries:
                    logger.step_error("Final validation attempt failed", {
                        "Attempts": f"{current_retries}/{max_retries}",
                        "Action": "Will use fallback G-code"
                    })
                else:
                    logger.step_warning("Validation failed, will retry", {
                        "Attempt": f"{current_retries}/{max_retries}",
                        "Error": error_msg[:100] + "..." if len(error_msg) > 100 else error_msg
                    })
                
                return GCodeValidationErrorEvent(
                    error=error_msg,
                    issues=ev.output,
                    prompt=ev.prompt
                )
            
            # Validation successful - result is a GCodeProgram
            program = result
            gcode_text = program.to_gcode()
            
            logger.validation_result(True, len(program.commands))
            logger.step_success("G-code validation completed", {
                "Commands": len(program.commands),
                "Program size": f"{len(gcode_text)} characters"
            })
            
            return ValidatedGCodeEvent(
                program=program,
                gcode_text=gcode_text,
                prompt=ev.prompt
            )
            
        except Exception as e:
            error_msg = str(e)
            logger.step_error("Unexpected validation error", {"Error": error_msg})
            
            return GCodeValidationErrorEvent(
                error=error_msg,
                issues=ev.output,
                prompt=ev.prompt
            )
    
    @step
    async def end(self, ctx: Context, ev: ValidatedGCodeEvent) -> StopEvent:
        """End the workflow and return the G-code program.
        
        Args:
            ctx: The workflow context
            ev: The validated G-code event
            
        Returns:
            StopEvent with the G-code program
        """
        # Prepare G-code preview
        gcode_lines = ev.gcode_text.split('\n')
        
        # Display workflow completion
        logger.workflow_complete(
            success=True,
            commands_count=len(ev.program.commands),
            gcode_preview=gcode_lines
        )
        
        # Return final result
        result = {
            "prompt": ev.prompt,
            "commands_count": len(ev.program.commands),
            "gcode": ev.gcode_text,
            "program": ev.program.model_dump(),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        return StopEvent(result=result)


async def main():
    """Main function for testing the simple batch workflow."""
    from llama_index.llms.ollama import Ollama
    from llama_index.llms.azure_openai import AzureOpenAI
    import os

    # Create LLM instance
    llm = Ollama(model="llama3.2:3b", request_timeout=10000)

    # Optionally use Azure OpenAI if environment variables are set
    if all(os.environ.get(key) for key in ["GPT4_API_KEY", "GPT4_API_VERSION", "GPT4_ENDPOINT"]):
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
        workflow = SimpleGCodeWorkflow(llm=llm, timeout=10000)
        
        # Generate workflow visualization
        try:
            from llama_index.utils.workflow import draw_all_possible_flows
            
            draw_all_possible_flows(
                SimpleGCodeWorkflow, filename="results/visualizations/gcode_workflow_simple.html"
            )
            
            logger.step_success("Workflow visualization saved", {"File": "results/visualizations/gcode_workflow_simple.html"})
        except ImportError:
            logger.step_warning("Workflow visualization not available", {"Reason": "llama_index.utils.workflow not found"})
        
        # Test with a prompt
        prompt = "draw a small house with a door and windows"
        
        # Run workflow
        result = await workflow.run(prompt=prompt)
        
        # Save G-code to file
        if result:
            filename = f"results/gcode/simple_batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(filename, 'w') as f:
                f.write(result.get("gcode", ""))
            logger.step_success("G-code saved", {"File": filename})
    
    except KeyboardInterrupt:
        logger.step_warning("Operation interrupted by user")
    except Exception as e:
        logger.step_error("Workflow execution failed", {"Error": str(e)})


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())