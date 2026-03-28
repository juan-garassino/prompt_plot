from llama_index.core.workflow import (
    Event,
    StartEvent,
    StopEvent,
    Workflow,
    step,
    Context,
)
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Union, Any
import json
from llama_index.llms.ollama import Ollama
from colorama import Fore, Style, init
from datetime import datetime
from llama_index.llms.azure_openai import AzureOpenAI

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

class WorkflowException(Exception):
    """Custom exception for workflow errors"""
    def __init__(self, message: str, details: Dict = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

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
class GenerateNextCommandEvent(Event):
    """Event to trigger generation of next G-code command."""
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
    """Event containing a validated G-code command."""
    command: GCodeCommand = Field(description="Validated command")
    prompt: str = Field(description="Drawing prompt")
    step: int = Field(description="Current step number")
    is_complete: bool = Field(description="Whether this is the final command")

class ContinueGenerationEvent(Event):
    """Event to signal continuing to next command."""
    prompt: str = Field(description="Drawing prompt")
    step: int = Field(description="Next step number")

class ProgramCompleteEvent(Event):
    """Event indicating program is complete."""
    prompt: str = Field(description="Drawing prompt that was completed")
    commands: List[GCodeCommand] = Field(description="All generated commands")
    step_count: int = Field(description="Number of steps taken")

# Main Workflow
class SequentialGCodeWorkflow(Workflow):
    """Advanced workflow for generating G-code commands one at a time.
    
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
    
    max_retries: int = 3  # Maximum number of retry attempts per command
    max_steps: int = 50   # Maximum total steps to prevent infinite loops

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
        
        # Store workflow parameters in context
        print(f"{Fore.CYAN}[*] │   ├── Setting workflow parameters{Style.RESET_ALL}")
        await ctx.set("max_retries", self.max_retries)
        await ctx.set("max_steps", getattr(ev, "max_steps", self.max_steps))
        print(f"{Fore.GREEN}[+] │   │   └── Parameters stored in context{Style.RESET_ALL}")
        
        # Initialize command storage
        print(f"{Fore.CYAN}[*] │   ├── Initializing command storage{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   │   └── Creating an empty list to store G-code commands as they are generated.{Style.RESET_ALL}")
        await ctx.set("commands", [])
        
        # Store the drawing prompt
        print(f"{Fore.CYAN}[*] │   ├── Processing drawing prompt{Style.RESET_ALL}")
        if not hasattr(ev, "prompt"):
            print(f"{Fore.RED}[!] │   │   ├── No drawing prompt specified{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}[?] │   │   │   └── Using default prompt as fallback since none was provided.{Style.RESET_ALL}")
            await ctx.set("prompt", "draw a simple square")
        else:
            print(f"{Fore.CYAN}[*] │   │   ├── Using provided prompt{Style.RESET_ALL}")
            await ctx.set("prompt", ev.prompt)
            
        prompt = await ctx.get("prompt")
        print(f"{Fore.GREEN}[+] │   └── Workflow initialization complete{Style.RESET_ALL}")
        print(f"{Fore.GREEN}[+] ├── Drawing prompt: {prompt}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}[+] ├── Max steps: {await ctx.get('max_steps')}{Style.RESET_ALL}")
        
        # Start with step 1
        print(f"{Fore.CYAN}[*] └── Starting first command generation{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?]     └── Moving to generate_next_command step to create the first G-code command.{Style.RESET_ALL}")
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
        current_retries = await ctx.get(task_key, default=0)
        max_retries = await ctx.get("max_retries")
        
        print(f"{Fore.CYAN}[*] │   ├── Managing retry state{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[*] │   │   └── Attempt {current_retries + 1}/{max_retries}{Style.RESET_ALL}")
        
        # Get command history
        print(f"{Fore.CYAN}[*] │   ├── Retrieving command history{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   │   └── Previous commands provide context to the LLM for generating coherent G-code sequences.{Style.RESET_ALL}")
        commands = await ctx.get("commands", default=[])
        history = "\n".join([f"Step {i+1}: {cmd.to_gcode()}" for i, cmd in enumerate(commands)])
        
        # Check if max retries exceeded
        if current_retries >= max_retries:
            print(f"{Fore.RED}[!] │   ├── Maximum retries exceeded for step {ev.step}{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}[?] │   │   └── After multiple failed attempts, using a COMPLETE command to gracefully terminate the workflow.{Style.RESET_ALL}")
            
            # Return a COMPLETE command to force termination
            fallback_result = json.dumps({"command": "COMPLETE"})
            
            print(f"{Fore.GREEN}[+] │   └── Fallback command generated{Style.RESET_ALL}")
            return CommandExtractionDone(
                output=fallback_result,
                prompt=ev.prompt,
                step=ev.step
            )
        
        # Increment retry counter
        await ctx.set(task_key, current_retries + 1)
        
        # Build prompt based on whether this is initial generation or retry after validation error
        print(f"{Fore.CYAN}[*] │   ├── Building LLM prompt{Style.RESET_ALL}")
        if isinstance(ev, CommandValidationErrorEvent):
            print(f"{Fore.YELLOW}[!] │   │   ├── Previous generation failed validation{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}[?] │   │   │   └── Using reflection prompt to help LLM correct previous errors.{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}[!] │   │   └── Error: {ev.error}{Style.RESET_ALL}")
            
            # Include reflection prompt for retry
            prompt = REFLECTION_PROMPT.format(
                wrong_answer=ev.issues,
                error=ev.error
            )
        else:
            print(f"{Fore.CYAN}[*] │   │   └── Using standard next command template{Style.RESET_ALL}")
            prompt = NEXT_COMMAND_TEMPLATE.format(
                prompt=ev.prompt,
                history=history if commands else "No previous commands"
            )
        
        # Generate command using the LLM
        print(f"{Fore.CYAN}[*] │   ├── Calling LLM API{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   │   └── Sending prompt to language model to generate the next G-code command.{Style.RESET_ALL}")
        response = self.llm.complete(prompt)
        
        print(f"{Fore.GREEN}[+] │   └── Command generation complete{Style.RESET_ALL}")
        
        return CommandExtractionDone(
            output=response.text,
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
            # Clean the output
            print(f"{Fore.CYAN}[*] │   ├── Cleaning LLM output{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}[?] │   │   └── Removing code blocks, extra text, and extracting just the JSON object.{Style.RESET_ALL}")
            output = ev.output.strip()
            
            # Remove any code blocks or extra text
            if "```json" in output:
                print(f"{Fore.CYAN}[*] │   │   ├── Detected JSON code block{Style.RESET_ALL}")
                start = output.find("```json") + 7
                end = output.rfind("```")
                output = output[start:end].strip()
            elif "```" in output:
                print(f"{Fore.CYAN}[*] │   │   ├── Detected generic code block{Style.RESET_ALL}")
                start = output.find("```") + 3
                end = output.rfind("```")
                output = output[start:end].strip()
                
            # Find JSON object if there's extra text
            print(f"{Fore.CYAN}[*] │   │   └── Extracting JSON object{Style.RESET_ALL}")
            start = output.find("{")
            end = output.rfind("}") + 1
            
            if start < 0 or end <= start:
                print(f"{Fore.RED}[!] │   │       └── No valid JSON found{Style.RESET_ALL}")
                raise ValueError("No valid JSON found in response")
                
            json_str = output[start:end]
            
            # Parse JSON 
            print(f"{Fore.CYAN}[*] │   ├── Parsing JSON{Style.RESET_ALL}")
            data = json.loads(json_str)
            
            # Create and validate command
            print(f"{Fore.CYAN}[*] │   ├── Creating GCodeCommand object{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}[?] │   │   └── Converting JSON to GCodeCommand object and validating all fields.{Style.RESET_ALL}")
            command = GCodeCommand(**data)
            
            # Check if this is a completion command
            is_complete = command.command == "COMPLETE"
            
            print(f"{Fore.GREEN}[+] │   ├── Command validation successful{Style.RESET_ALL}")
            print(f"{Fore.GREEN}[+] │   │   └── Command: {command.to_gcode()}{Style.RESET_ALL}")
            
            if is_complete:
                print(f"{Fore.GREEN}[+] │   └── Reached completion command{Style.RESET_ALL}")
                print(f"{Fore.YELLOW}[?]     └── The COMPLETE command signals the end of the G-code program generation.{Style.RESET_ALL}")
            
            return ValidatedCommandEvent(
                command=command,
                prompt=ev.prompt,
                step=ev.step,
                is_complete=is_complete
            )
            
        except Exception as e:
            print(f"{Fore.RED}[!] │   ├── Command validation failed{Style.RESET_ALL}")
            print(f"{Fore.RED}[!] │   │   └── Error: {str(e)}{Style.RESET_ALL}")
            
            # More detailed error information based on retry count
            if current_retries >= max_retries:
                print(f"{Fore.RED}[!] │   └── Final attempt failed - Validation errors persist after {current_retries} attempts{Style.RESET_ALL}")
                print(f"{Fore.YELLOW}[?]     └── Moving to fallback mechanism after exhausting retry attempts.{Style.RESET_ALL}")
            else:
                print(f"{Fore.YELLOW}[!] │   └── Retrying - Attempt {current_retries}/{max_retries} failed{Style.RESET_ALL}")
                print(f"{Fore.YELLOW}[?]     └── Returning to generate_next_command with error details to help LLM correct its output.{Style.RESET_ALL}")
            
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
        
        # Get the current command list
        print(f"{Fore.CYAN}[*] │   ├── Retrieving current command list{Style.RESET_ALL}")
        commands = await ctx.get("commands", default=[])
        
        # Add command to list if it's not a COMPLETE command
        if not ev.is_complete:
            print(f"{Fore.CYAN}[*] │   ├── Adding command to program{Style.RESET_ALL}")
            commands.append(ev.command)
            await ctx.set("commands", commands)
            print(f"{Fore.GREEN}[+] │   │   └── Command added successfully{Style.RESET_ALL}")
        else:
            print(f"{Fore.CYAN}[*] │   ├── Skipping COMPLETE command{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}[?] │   │   └── COMPLETE is a control command, not part of the actual G-code program.{Style.RESET_ALL}")
        
        # Check completion conditions
        print(f"{Fore.CYAN}[*] │   ├── Checking completion conditions{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   │   └── Determining if workflow should end based on COMPLETE command or max steps limit.{Style.RESET_ALL}")
        max_steps = await ctx.get("max_steps")
        
        if ev.is_complete:
            print(f"{Fore.GREEN}[+] │   └── Program complete via COMPLETE command{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}[?]     └── Moving to finalize_program step to process results.{Style.RESET_ALL}")
            return ProgramCompleteEvent(
                prompt=ev.prompt,
                commands=commands,
                step_count=ev.step
            )
        elif ev.step >= max_steps:
            print(f"{Fore.YELLOW}[!] │   └── Program complete via max steps limit ({max_steps}){Style.RESET_ALL}")
            print(f"{Fore.YELLOW}[?]     └── Reached maximum allowed steps, moving to finalize_program to prevent infinite loops.{Style.RESET_ALL}")
            return ProgramCompleteEvent(
                prompt=ev.prompt,
                commands=commands,
                step_count=ev.step
            )
        else:
            # Continue to next step
            next_step = ev.step + 1
            print(f"{Fore.GREEN}[+] │   └── Continuing to step {next_step}{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}[?]     └── Moving to continue_generation step to prepare for next command.{Style.RESET_ALL}")
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
        print(f"{Fore.CYAN}[*] │   ├── Checking current program state{Style.RESET_ALL}")
        commands = await ctx.get("commands", default=[])
        print(f"{Fore.CYAN}[*] │   │   └── Current program has {len(commands)} commands{Style.RESET_ALL}")
        
        # Generate next command
        print(f"{Fore.CYAN}[*] │   └── Preparing for next command generation{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?]     └── Looping back to generate_next_command step with incremented step counter.{Style.RESET_ALL}")
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
        
        print(f"{Fore.GREEN}[+] │   ├── Drawing prompt: {ev.prompt}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}[+] │   ├── Commands generated: {len(ev.commands)}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}[+] │   └── Steps taken: {ev.step_count}{Style.RESET_ALL}")
        
        # Create final program
        print(f"{Fore.CYAN}[*] ├── Creating final G-code program{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   └── Converting command objects to formatted G-code text.{Style.RESET_ALL}")
        program = GCodeProgram(commands=ev.commands)
        gcode_text = program.to_gcode()
        
        # Show some of the G-code
        print(f"{Fore.CYAN}[*] ├── Generating program preview{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   └── Showing a sample of the generated G-code to verify output quality.{Style.RESET_ALL}")
        preview_lines = min(10, len(ev.commands))
        for i in range(preview_lines):
            cmd = ev.commands[i]
            print(f"{Fore.BLUE}    {cmd.to_gcode()}{Style.RESET_ALL}")
            
        if len(ev.commands) > preview_lines:
            print(f"{Fore.BLUE}    ... ({len(ev.commands) - preview_lines} more lines) ...{Style.RESET_ALL}")
        
        # Save to file
        print(f"{Fore.CYAN}[*] ├── Saving G-code to file{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   └── Writing complete G-code program to a timestamped file for later use.{Style.RESET_ALL}")
        filename = f"sequential_gcode_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(filename, 'w') as f:
            f.write(gcode_text)
        print(f"{Fore.GREEN}[+] │   └── G-code saved to {filename}{Style.RESET_ALL}")
        
        # Return final result
        print(f"{Fore.CYAN}[*] └── Preparing final result{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?]     └── Creating a comprehensive result object with all program details before ending workflow.{Style.RESET_ALL}")
        result = {
            "prompt": ev.prompt,
            "commands_count": len(ev.commands),
            "gcode": gcode_text,
            "step_count": ev.step_count,
            "program": program.model_dump(),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        print(f"{Fore.GREEN}[+] └── Workflow execution complete{Style.RESET_ALL}")
        return StopEvent(result=result)

async def main():
    print(f"{Fore.CYAN}[*] ├── Starting G-code generation workflow{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}[?] │   └── This is the main entry point that initializes the LLM and runs the workflow.{Style.RESET_ALL}")
    
    # Create LLM instance
    print(f"{Fore.CYAN}[*] ├── Initializing language model{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}[?] │   └── Setting up the LLM that will generate G-code commands based on prompts.{Style.RESET_ALL}")
    
    llm = Ollama(model="llama3.2:3b", request_timeout=10000)

    print(f"{Fore.CYAN}[*] ├── Configuring Azure OpenAI{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}[?] │   └── Switching to Azure OpenAI for more advanced capabilities.{Style.RESET_ALL}")

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
        print(f"{Fore.CYAN}[*] ├── Creating workflow instance{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   └── Instantiating the SequentialGCodeWorkflow with configured LLM.{Style.RESET_ALL}")
        workflow = SequentialGCodeWorkflow(llm=llm, verbose=True, timeout=10000)
        
        # Generate workflow visualization
        print(f"{Fore.CYAN}[*] ├── Generating workflow visualization{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   └── Creating a visual representation of the workflow to aid understanding.{Style.RESET_ALL}")
        from llama_index.utils.workflow import draw_all_possible_flows
        
        draw_all_possible_flows(
            SequentialGCodeWorkflow, filename="gcode_workflow_sequential.html"
        )
        
        print(f"{Fore.GREEN}[+] │   └── Workflow visualization saved to gcode_workflow_sequential.html{Style.RESET_ALL}")
        
        # Test with a prompt
        print(f"{Fore.CYAN}[*] ├── Preparing test prompt{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   └── Setting up a sample prompt to test the G-code generation workflow.{Style.RESET_ALL}")
        prompt = "draw a small house with a door and windows"
        
        # Run workflow
        print(f"{Fore.CYAN}[*] ├── Executing workflow{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   └── Running the workflow with the test prompt and maximum 50 steps.{Style.RESET_ALL}")
        #start_event = StartEvent(prompt=prompt, max_steps=50)
        result = await workflow.run(prompt=prompt, max_steps=50)
        
        # Display summary
        if result:
            print(f"\n{Fore.GREEN}[+] ├── Workflow completed successfully{Style.RESET_ALL}")
            print(f"{Fore.GREEN}[+] └── Generated {result.get('commands_count', 0)} commands{Style.RESET_ALL}")
    
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}[!] └── Operation interrupted by user{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?]     └── Workflow execution was manually stopped before completion.{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}[!] └── Error: {str(e)}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?]     └── An unexpected error occurred during workflow execution.{Style.RESET_ALL}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())