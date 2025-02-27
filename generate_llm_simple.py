from llama_index.core.workflow import (
    Event,
    StartEvent,
    StopEvent,
    Workflow,
    step,
    Context,
)
from llama_index.llms.ollama import Ollama
from llama_index.llms.azure_openai import AzureOpenAI
from pydantic import BaseModel, Field, field_validator  # Changed to field_validator
from typing import List, Optional, Union, Dict, Any
import json
from colorama import Fore, Style, init
from datetime import datetime

# Initialize colorama for cross-platform color support
init(autoreset=True)

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

    # Updated to use field_validator instead of validator
    @field_validator('command')
    @classmethod
    def validate_command(cls, v):
        """Validates that the command is a valid G-code command"""
        if not v.startswith(('G', 'M')):
            raise ValueError(f"Command must start with G or M, got {v}")
        return v

    def to_gcode(self) -> str:
        """Convert to G-code string format"""
        parts = [self.command]
        for attr, value in self.__dict__.items():
            if value is not None and attr != 'command':
                parts.append(f"{attr.upper()}{value:.3f}" if isinstance(value, float) else f"{attr.upper()}{value}")
        return " ".join(parts)

class GCodeProgram(BaseModel):
    """Model for a complete G-code program"""
    commands: List[GCodeCommand]

    def to_gcode(self) -> str:
        """Convert the entire program to G-code string format"""
        return "\n".join(cmd.to_gcode() for cmd in self.commands)

# Custom exception for workflow errors
class WorkflowException(Exception):
    def __init__(self, message: str, details: Dict = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

# Constants and Prompt templates
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
    prompt: str = Field(description="Drawing prompt")

class GCodeExtractionDone(Event):
    """Event indicating G-code extraction is complete but not yet validated."""
    output: str = Field(description="Raw output from LLM")
    prompt: str = Field(description="Drawing prompt")

class GCodeValidationErrorEvent(Event):
    """Event for validation errors in G-code generation."""
    error: str = Field(description="Error message from validation")
    issues: str = Field(description="Raw output that failed validation")
    prompt: str = Field(description="Drawing prompt")

class ValidatedGCodeEvent(Event):
    """Event containing validated G-code program."""
    program: GCodeProgram = Field(description="Validated G-code program")
    gcode_text: str = Field(description="G-code as text")
    prompt: str = Field(description="Drawing prompt")

# Main Workflow
class SimpleGCodeWorkflow(Workflow):
    """Simple workflow for generating and validating G-code."""
    
    max_retries: int = 3  # Maximum number of retry attempts

    def __init__(self, llm: Any, *args, **kwargs):
        """Initialize the G-code workflow.
        
        Args:
            llm: The language model to use for generation
            *args: Additional arguments
            **kwargs: Additional keyword arguments
        """
        super().__init__(*args, **kwargs)
        self.llm = llm

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
        await ctx.set("max_retries", self.max_retries)
        print(f"{Fore.CYAN}├── [*] Configuring retry settings{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}│   └── [?] Setting max_retries={self.max_retries} to handle potential LLM generation failures{Style.RESET_ALL}")
        
        # Store the drawing prompt
        print(f"{Fore.CYAN}├── [*] Processing drawing prompt{Style.RESET_ALL}")
        if not hasattr(ev, "prompt"):
            print(f"{Fore.RED}│   ├── [!] No drawing prompt specified - using default{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}│   └── [?] Fallback to default prompt ensures workflow can continue even without input{Style.RESET_ALL}")
            await ctx.set("prompt", "draw a simple square")
        else:
            print(f"{Fore.GREEN}│   ├── [+] Drawing prompt received{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}│   └── [?] Using user-provided prompt for G-code generation{Style.RESET_ALL}")
            await ctx.set("prompt", ev.prompt)
            
        prompt = await ctx.get("prompt")
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
        current_retries = await ctx.get(task_key, default=0)
        max_retries = await ctx.get("max_retries")
        
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
        await ctx.set(task_key, current_retries + 1)
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
        """Validate the generated G-code.
        
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
        current_retries = await ctx.get(task_key, default=0)
        max_retries = await ctx.get("max_retries")
        
        print(f"{Fore.CYAN}├── [*] Validating G-code (Attempt {current_retries}/{max_retries}){Style.RESET_ALL}")
        print(f"{Fore.YELLOW}│   └── [?] Parsing LLM output to extract valid JSON and convert to G-code{Style.RESET_ALL}")
        
        try:
            # Clean the output
            print(f"{Fore.CYAN}├── [*] Cleaning LLM output{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}│   └── [?] Removing code blocks and extra text to extract JSON{Style.RESET_ALL}")
            output = ev.output.strip()
            
            # Remove any code blocks or extra text
            if "```json" in output:
                print(f"{Fore.CYAN}│   ├── [*] Detected JSON code block{Style.RESET_ALL}")
                start = output.find("```json") + 7
                end = output.rfind("```")
                output = output[start:end].strip()
            elif "```" in output:
                print(f"{Fore.CYAN}│   ├── [*] Detected generic code block{Style.RESET_ALL}")
                start = output.find("```") + 3
                end = output.rfind("```")
                output = output[start:end].strip()
                
            # Find JSON object if there's extra text
            print(f"{Fore.CYAN}│   ├── [*] Extracting JSON object{Style.RESET_ALL}")
            start = output.find("{")
            end = output.rfind("}") + 1
            
            if start < 0 or end <= start:
                print(f"{Fore.RED}│   └── [!] No valid JSON found{Style.RESET_ALL}")
                raise ValueError("No valid JSON found in response")
                
            json_str = output[start:end]
            
            # Parse JSON and validate with Pydantic
            print(f"{Fore.CYAN}├── [*] Parsing and validating JSON{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}│   └── [?] Using Pydantic to validate the structure of the G-code program{Style.RESET_ALL}")
            data = json.loads(json_str)
            program = GCodeProgram(**data)
            
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
            print(f"{Fore.RED}├── [!] G-code validation failed{Style.RESET_ALL}")
            print(f"{Fore.RED}├── [!] Error: {str(e)}{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}│   └── [?] Validation errors trigger a retry with more specific instructions{Style.RESET_ALL}")
            
            # More detailed error information based on retry count
            if current_retries >= max_retries:
                print(f"{Fore.RED}├── [!] Final attempt failed - Validation errors persist after {current_retries} attempts{Style.RESET_ALL}")
                print(f"{Fore.YELLOW}└── [?] Workflow will proceed with fallback G-code in the next step{Style.RESET_ALL}")
            else:
                print(f"{Fore.YELLOW}├── [!] Retrying - Attempt {current_retries}/{max_retries} failed{Style.RESET_ALL}")
                print(f"{Fore.YELLOW}└── [?] Next step will regenerate G-code with error feedback{Style.RESET_ALL}")
            
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
            "program": ev.program.model_dump(),  # Changed from dict() to model_dump()
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        print(f"{Fore.GREEN}└── [+] Workflow completed successfully{Style.RESET_ALL}")
        
        return StopEvent(result=result)

async def main():
    # Create LLM instance
    llm = Ollama(model="llama3.2:3b", request_timeout=10000)

    import os

    llm = AzureOpenAI(
                model="gpt-4o",
                deployment_name="gpt-4o-gs",
                api_key=os.environ.get("GPT4_API_KEY"),
                api_version=os.environ.get("GPT4_API_VERSION"),
                azure_endpoint=os.environ.get("GPT4_ENDPOINT"),
                timeout=1220,)
        
    try:
        # Create workflow
        workflow = SimpleGCodeWorkflow(llm=llm, timeout=10000)
        
        # Generate workflow visualization
        from llama_index.utils.workflow import draw_all_possible_flows
        
        draw_all_possible_flows(
            SimpleGCodeWorkflow, filename="gcode_workflow_simple.html"
        )
        
        print(f"{Fore.GREEN}[+] Workflow visualization saved to gcode_workflow.html{Style.RESET_ALL}")
        
        # Test with a prompt
        prompt = "draw a small house with a door and windows"
        
        # Run workflow - using execute method instead of aexecute
        #start_event = StartEvent(prompt=prompt)
        result = await workflow.run(prompt=prompt)
        
        # Save G-code to file
        if result:
            filename = f"gcode_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
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