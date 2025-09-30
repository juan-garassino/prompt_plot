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
        print(f"{Fore.CYAN}╔══════════════════════════════════════╗{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║   G-Code Generation Workflow Start   ║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}╚══════════════════════════════════════╝{Style.RESET_ALL}")
        
        print(f"{Fore.CYAN}[*] Initialize Workflow{Style.RESET_ALL}")
        print(f"{Fore.CYAN}├── [*] Setting up workflow context{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}│   └── [?] The context stores workflow state that persists across steps{Style.RESET_ALL}")
        
        # Store max retries in context
        await ctx.store.set("max_retries", self.max_retries)
        print(f"{Fore.CYAN}├── [*] Configuring retry settings{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}│   └── [?] Setting max_retries={self.max_retries} to handle potential LLM generation failures{Style.RESET_ALL}")
        
        # Store the drawing prompt
        print(f"{Fore.CYAN}├── [*] Processing drawing prompt{Style.RESET_ALL}")
        if not hasattr(ev, "prompt"):
            print(f"{Fore.RED}│   ├── [!] No drawing prompt specified - using default{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}│   └── [?] Fallback to default prompt ensures workflow can continue even without input{Style.RESET_ALL}")
            await ctx.store.set("prompt", "draw a simple square")
        else:
            print(f"{Fore.GREEN}│   ├── [+] Drawing prompt received{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}│   └── [?] Using user-provided prompt for G-code generation{Style.RESET_ALL}")
            await ctx.store.set("prompt", ev.prompt)
            
        prompt = await ctx.store.get("prompt")
        
        # Analyze prompt complexity using strategy selector
        print(f"{Fore.CYAN}├── [*] Analyzing prompt complexity{Style.RESET_ALL}")
        complexity = self.strategy_selector.analyze_prompt_complexity(prompt)
        await ctx.store.set("complexity", complexity)
        print(f"{Fore.GREEN}│   ├── [+] Complexity level: {complexity.complexity_level.value}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}│   ├── [+] Requires curves: {complexity.requires_curves}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}│   └── [+] Estimated commands: {complexity.estimated_commands}{Style.RESET_ALL}")
        
        print(f"{Fore.GREEN}├── [+] Workflow initialized{Style.RESET_ALL}")
        print(f"{Fore.GREEN}└── [+] Drawing prompt: {prompt}{Style.RESET_ALL}")
        
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
        print(f"{Fore.CYAN}[*] G-Code Generation Step{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}├── [?] This step uses the LLM to generate G-code based on the drawing prompt{Style.RESET_ALL}")
        
        # Track retries for this generation
        task_key = "gcode_generation_retries"
        current_retries = await ctx.store.get(task_key, default=0)
        max_retries = await ctx.store.get("max_retries")
        
        print(f"{Fore.CYAN}├── [*] Generating G-code for prompt: {ev.prompt}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}│   └── [?] The prompt describes what the plotter should draw{Style.RESET_ALL}")
        print(f"{Fore.CYAN}├── [*] Attempt {current_retries + 1}/{max_retries}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}│   └── [?] Tracking retry attempts to prevent infinite loops{Style.RESET_ALL}")
        
        # Check if max retries exceeded
        if current_retries >= max_retries:
            print(f"{Fore.RED}├── [!] Maximum retries exceeded{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}│   └── [?] After {max_retries} failed attempts, using fallback G-code{Style.RESET_ALL}")
            
            # Return a fallback empty program
            fallback_result = json.dumps({
                "commands": [
                    {"command": "G0", "x": 0, "y": 0},
                    {"command": "G0", "x": 0, "y": 0}
                ]
            })
            
            print(f"{Fore.CYAN}└── [*] Returning fallback G-code{Style.RESET_ALL}")
            
            return GCodeExtractionDone(
                output=fallback_result,
                prompt=ev.prompt
            )
        
        # Increment retry counter
        await ctx.store.set(task_key, current_retries + 1)
        print(f"{Fore.CYAN}├── [*] Updated retry counter: {current_retries + 1}{Style.RESET_ALL}")
        
        # Build prompt based on whether this is initial generation or retry after validation error
        if isinstance(ev, GCodeValidationErrorEvent):
            print(f"{Fore.YELLOW}├── [!] Previous generation failed validation{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}│   └── [?] Using reflection prompt to help LLM correct previous errors{Style.RESET_ALL}")
            print(f"{Fore.RED}├── [!] Error: {ev.error}{Style.RESET_ALL}")
            
            # Include reflection prompt for retry
            prompt = REFLECTION_PROMPT.format(
                wrong_answer=ev.issues,
                error=ev.error
            )
        else:
            print(f"{Fore.CYAN}├── [*] First generation attempt{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}│   └── [?] Using standard template for initial G-code generation{Style.RESET_ALL}")
            prompt = GCODE_PROGRAM_TEMPLATE.format(
                prompt=ev.prompt
            )
        
        # Generate G-code using the LLM
        print(f"{Fore.CYAN}├── [*] Calling LLM API{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}│   └── [?] Sending prompt to LLM and waiting for response{Style.RESET_ALL}")
        response = await self.llm.acomplete(prompt)
        
        print(f"{Fore.GREEN}└── [+] G-code generation complete{Style.RESET_ALL}")
        
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
        print(f"{Fore.CYAN}[*] G-Code Validation Step{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}├── [?] This step ensures the generated G-code is valid and can be executed by the plotter{Style.RESET_ALL}")
        
        # Check retry status to show proper messaging
        task_key = "gcode_generation_retries"
        current_retries = await ctx.store.get(task_key, default=0)
        max_retries = await ctx.store.get("max_retries")
        
        print(f"{Fore.CYAN}├── [*] Validating G-code (Attempt {current_retries}/{max_retries}){Style.RESET_ALL}")
        print(f"{Fore.YELLOW}│   └── [?] Parsing LLM output to extract valid JSON and convert to G-code{Style.RESET_ALL}")
        
        try:
            # Use the base workflow validation method
            result = await self.validate_gcode_command(ev.output)
            
            if isinstance(result, Exception):
                # Validation failed
                print(f"{Fore.RED}├── [!] G-code validation failed{Style.RESET_ALL}")
                print(f"{Fore.RED}├── [!] Error: {str(result)}{Style.RESET_ALL}")
                print(f"{Fore.YELLOW}│   └── [?] Validation errors trigger a retry with more specific instructions{Style.RESET_ALL}")
                
                # More detailed error information based on retry count
                if current_retries >= max_retries:
                    print(f"{Fore.RED}├── [!] Final attempt failed - Validation errors persist after {current_retries} attempts{Style.RESET_ALL}")
                    print(f"{Fore.YELLOW}└── [?] Workflow will proceed with fallback G-code in the next step{Style.RESET_ALL}")
                else:
                    print(f"{Fore.YELLOW}├── [!] Retrying - Attempt {current_retries}/{max_retries} failed{Style.RESET_ALL}")
                    print(f"{Fore.YELLOW}└── [?] Next step will regenerate G-code with error feedback{Style.RESET_ALL}")
                
                return GCodeValidationErrorEvent(
                    error=str(result),
                    issues=ev.output,
                    prompt=ev.prompt
                )
            
            # Validation successful - result is a GCodeProgram
            program = result
            
            # Generate the G-code text
            print(f"{Fore.CYAN}├── [*] Converting to G-code text format{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}│   └── [?] Converting JSON representation to actual G-code commands{Style.RESET_ALL}")
            gcode_text = program.to_gcode()
            
            print(f"{Fore.GREEN}├── [+] G-code validation successful{Style.RESET_ALL}")
            print(f"{Fore.GREEN}└── [+] Generated {len(program.commands)} commands{Style.RESET_ALL}")
            
            return ValidatedGCodeEvent(
                program=program,
                gcode_text=gcode_text,
                prompt=ev.prompt
            )
            
        except Exception as e:
            print(f"{Fore.RED}├── [!] Unexpected validation error{Style.RESET_ALL}")
            print(f"{Fore.RED}├── [!] Error: {str(e)}{Style.RESET_ALL}")
            
            return GCodeValidationErrorEvent(
                error=str(e),
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
        print(f"{Fore.CYAN}╔══════════════════════════════════════╗{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║  G-Code Generation Workflow Complete ║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}╚══════════════════════════════════════╝{Style.RESET_ALL}")
        
        print(f"{Fore.CYAN}[*] Workflow Completion Step{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}├── [?] This final step prepares the results and terminates the workflow{Style.RESET_ALL}")
        
        print(f"{Fore.GREEN}├── [+] Drawing prompt: {ev.prompt}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}├── [+] Commands generated: {len(ev.program.commands)}{Style.RESET_ALL}")
        
        # Show some of the G-code
        preview_lines = min(5, len(ev.program.commands))
        print(f"{Fore.CYAN}├── [*] G-code preview (first {preview_lines} lines):{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}│   └── [?] Showing a sample of the generated commands for quick verification{Style.RESET_ALL}")
        for i in range(preview_lines):
            cmd = ev.program.commands[i]
            print(f"{Fore.BLUE}│       {cmd.to_gcode()}{Style.RESET_ALL}")
        
        # Return final result
        print(f"{Fore.CYAN}├── [*] Preparing final result{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}│   └── [?] Packaging all generated data into a structured result object{Style.RESET_ALL}")
        result = {
            "prompt": ev.prompt,
            "commands_count": len(ev.program.commands),
            "gcode": ev.gcode_text,
            "program": ev.program.model_dump(),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        print(f"{Fore.GREEN}└── [+] Workflow completed successfully{Style.RESET_ALL}")
        
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
            
            print(f"{Fore.GREEN}[+] Workflow visualization saved to results/visualizations/gcode_workflow_simple.html{Style.RESET_ALL}")
        except ImportError:
            print(f"{Fore.YELLOW}[!] Workflow visualization not available - llama_index.utils.workflow not found{Style.RESET_ALL}")
        
        # Test with a prompt
        prompt = "draw a small house with a door and windows"
        
        # Run workflow
        result = await workflow.run(prompt=prompt)
        
        # Save G-code to file
        if result:
            filename = f"results/gcode/simple_batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(filename, 'w') as f:
                f.write(result.get("gcode", ""))
            print(f"{Fore.GREEN}[+] G-code saved to {filename}{Style.RESET_ALL}")
    
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Operation interrupted by user{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}Error: {str(e)}{Style.RESET_ALL}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())