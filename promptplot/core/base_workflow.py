"""
Base workflow class for PromptPlot v2.0

This module contains the base workflow class that extracts common patterns
from all existing workflow implementations, providing shared retry logic,
validation, and error handling.
"""

import json
import asyncio
from typing import Any, Dict, Optional, Union, List
from abc import ABCMeta, abstractmethod
from datetime import datetime

from llama_index.core.workflow import Workflow, Context
from pydantic import ValidationError as PydanticValidationError

from .models import GCodeCommand, GCodeProgram, ValidationError, WorkflowResult
from .exceptions import WorkflowException, ValidationException, LLMException


class WorkflowABCMeta(ABCMeta, type(Workflow)):
    """Metaclass that combines ABC and Workflow metaclasses"""
    pass


class BasePromptPlotWorkflow(Workflow, metaclass=WorkflowABCMeta):
    """
    Base class for all PromptPlot workflows
    
    Extracts common patterns from existing workflow implementations:
    - Common initialization patterns
    - Shared retry and validation logic  
    - Common error handling and reflection prompt patterns
    - Standardized result formatting
    """
    
    # Default configuration extracted from existing workflows
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_MAX_STEPS = 50
    DEFAULT_TIMEOUT = 10000
    
    # Common prompt templates extracted from existing files
    REFLECTION_PROMPT_TEMPLATE = """
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

    def __init__(self, llm: Any, max_retries: int = None, max_steps: int = None, 
                 timeout: int = None, *args, **kwargs):
        """
        Initialize the base workflow with common parameters
        
        Extracted common initialization pattern from all current workflow classes.
        
        Args:
            llm: The language model to use for generation
            max_retries: Maximum number of retry attempts (default: 3)
            max_steps: Maximum total steps to prevent infinite loops (default: 50)
            timeout: Workflow timeout in milliseconds (default: 10000)
            *args: Additional arguments
            **kwargs: Additional keyword arguments
        """
        super().__init__(timeout=timeout or self.DEFAULT_TIMEOUT, *args, **kwargs)
        self.llm = llm
        self.max_retries = max_retries or self.DEFAULT_MAX_RETRIES
        self.max_steps = max_steps or self.DEFAULT_MAX_STEPS

    async def initialize_context(self, ctx: Context, prompt: str, **kwargs) -> None:
        """
        Initialize workflow context with common variables
        
        Extracted common context initialization from existing workflows.
        
        Args:
            ctx: The workflow context
            prompt: The drawing prompt
            **kwargs: Additional context variables
        """
        # Store workflow parameters
        await ctx.set("max_retries", self.max_retries)
        await ctx.set("max_steps", self.max_steps)
        await ctx.set("prompt", prompt)
        
        # Initialize command storage and statistics
        await ctx.set("commands", [])
        await ctx.set("commands_executed", 0)
        await ctx.set("success_count", 0)
        await ctx.set("failed_count", 0)
        
        # Store additional context variables
        for key, value in kwargs.items():
            await ctx.set(key, value)

    async def validate_gcode_command(self, output: str) -> Union[GCodeCommand, GCodeProgram, Exception]:
        """
        Validate G-code command or program output from LLM
        
        Common validation logic extracted from all existing workflows with
        enhanced error handling and structured error reporting.
        
        Args:
            output: Raw output from LLM
            
        Returns:
            GCodeCommand, GCodeProgram if valid, Exception if invalid
        """
        try:
            # Clean the output - extracted pattern from existing workflows
            cleaned_output = self._clean_llm_output(output)
            
            # Extract JSON object
            json_str = self._extract_json_from_output(cleaned_output)
            
            # Parse JSON
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError as e:
                return ValidationException(f"Invalid JSON format: {str(e)}")
            
            # Check if this is a single command or a program
            if "commands" in data:
                # This is a program (batch mode)
                try:
                    program = GCodeProgram(**data)
                    return program
                except PydanticValidationError as e:
                    return ValidationException(f"Program validation failed: {str(e)}")
            else:
                # This is a single command (sequential mode)
                try:
                    command = GCodeCommand(**data)
                    return command
                except PydanticValidationError as e:
                    return ValidationException(f"Command validation failed: {str(e)}")
                
        except Exception as e:
            return ValidationException(f"Unexpected validation error: {str(e)}")

    def _clean_llm_output(self, output: str) -> str:
        """
        Clean LLM output by removing code blocks and extra text
        
        Extracted common cleaning logic from existing workflows.
        """
        output = output.strip()
        
        # Remove JSON code blocks
        if "```json" in output:
            start = output.find("```json") + 7
            end = output.rfind("```")
            output = output[start:end].strip()
        elif "```" in output:
            start = output.find("```") + 3
            end = output.rfind("```")
            output = output[start:end].strip()
            
        return output

    def _extract_json_from_output(self, output: str) -> str:
        """
        Extract JSON object from cleaned output
        
        Extracted common JSON extraction logic from existing workflows.
        """
        # Find JSON object boundaries
        start = output.find("{")
        end = output.rfind("}") + 1
        
        if start < 0 or end <= start:
            raise ValueError("No valid JSON object found in output")
            
        return output[start:end]

    async def handle_retry_with_reflection(self, error: str, wrong_answer: str, 
                                         original_prompt: str) -> str:
        """
        Handle retry with reflection prompt
        
        Common retry pattern with reflection prompts extracted from existing files.
        
        Args:
            error: Error message from validation
            wrong_answer: The incorrect LLM output
            original_prompt: The original prompt (for context)
            
        Returns:
            New LLM response after reflection
        """
        reflection_prompt = self.REFLECTION_PROMPT_TEMPLATE.format(
            wrong_answer=wrong_answer,
            error=error
        )
        
        try:
            if hasattr(self.llm, 'acomplete'):
                response = await self.llm.acomplete(reflection_prompt)
                return response.text
            else:
                response = self.llm.complete(reflection_prompt)
                return response.text
        except Exception as e:
            raise LLMException(f"Failed to get reflection response: {str(e)}")

    async def check_retry_limits(self, ctx: Context, step: int, task_key: str) -> bool:
        """
        Check if retry limits have been exceeded
        
        Common retry limit checking extracted from existing workflows.
        
        Args:
            ctx: Workflow context
            step: Current step number
            task_key: Key for tracking retries for this task
            
        Returns:
            True if retries are available, False if limit exceeded
        """
        current_retries = await ctx.get(task_key, default=0)
        max_retries = await ctx.get("max_retries")
        
        if current_retries >= max_retries:
            return False
            
        # Increment retry counter
        await ctx.set(task_key, current_retries + 1)
        return True

    async def check_step_limits(self, ctx: Context, current_step: int) -> bool:
        """
        Check if step limits have been exceeded
        
        Common step limit checking extracted from existing workflows.
        
        Args:
            ctx: Workflow context
            current_step: Current step number
            
        Returns:
            True if steps are available, False if limit exceeded
        """
        max_steps = await ctx.get("max_steps")
        return current_step < max_steps

    async def get_command_history(self, ctx: Context) -> str:
        """
        Get formatted command history for LLM context
        
        Common history formatting extracted from existing workflows.
        
        Args:
            ctx: Workflow context
            
        Returns:
            Formatted command history string
        """
        commands = await ctx.get("commands", default=[])
        if not commands:
            return "No previous commands"
            
        return "\n".join([
            f"Step {i+1}: {cmd.to_gcode()}" 
            for i, cmd in enumerate(commands)
        ])

    async def add_command_to_history(self, ctx: Context, command: GCodeCommand) -> None:
        """
        Add a command to the execution history
        
        Common command tracking extracted from existing workflows.
        
        Args:
            ctx: Workflow context
            command: Command to add to history
        """
        commands = await ctx.get("commands", default=[])
        commands.append(command)
        await ctx.set("commands", commands)

    async def update_statistics(self, ctx: Context, success: bool) -> None:
        """
        Update execution statistics
        
        Common statistics tracking extracted from existing workflows.
        
        Args:
            ctx: Workflow context
            success: Whether the operation was successful
        """
        commands_executed = await ctx.get("commands_executed", default=0)
        await ctx.set("commands_executed", commands_executed + 1)
        
        if success:
            success_count = await ctx.get("success_count", default=0)
            await ctx.set("success_count", success_count + 1)
        else:
            failed_count = await ctx.get("failed_count", default=0)
            await ctx.set("failed_count", failed_count + 1)

    def create_fallback_command(self) -> GCodeCommand:
        """
        Create a fallback COMPLETE command for error recovery
        
        Common fallback pattern extracted from existing workflows.
        
        Returns:
            A COMPLETE command to gracefully terminate workflow
        """
        return GCodeCommand(command="COMPLETE")

    async def create_workflow_result(self, ctx: Context, success: bool = True, 
                                   error_message: str = None) -> WorkflowResult:
        """
        Create standardized workflow result
        
        Common result formatting extracted from existing workflows.
        
        Args:
            ctx: Workflow context
            success: Whether workflow completed successfully
            error_message: Error message if workflow failed
            
        Returns:
            Standardized WorkflowResult object
        """
        # Get data from context
        prompt = await ctx.get("prompt", default="")
        commands = await ctx.get("commands", default=[])
        commands_executed = await ctx.get("commands_executed", default=0)
        step_count = await ctx.get("step_count", default=len(commands))
        
        # Create program and G-code text
        program = GCodeProgram(commands=commands) if commands else None
        gcode_text = program.to_gcode() if program else ""
        
        # Create result
        return WorkflowResult(
            success=success,
            prompt=prompt,
            commands_count=len(commands),
            gcode=gcode_text,
            program=program,
            step_count=step_count,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            error_message=error_message,
            metadata={
                "commands_executed": commands_executed,
                "max_retries": self.max_retries,
                "max_steps": self.max_steps
            }
        )

    @abstractmethod
    async def generate_gcode(self, prompt: str, **kwargs) -> WorkflowResult:
        """
        Abstract method for G-code generation
        
        Each workflow implementation must define how it generates G-code.
        
        Args:
            prompt: Drawing prompt
            **kwargs: Additional parameters
            
        Returns:
            WorkflowResult with generated G-code
        """
        pass

    def __str__(self) -> str:
        """String representation of the workflow"""
        return f"{self.__class__.__name__}(max_retries={self.max_retries}, max_steps={self.max_steps})"

    def __repr__(self) -> str:
        """Detailed string representation of the workflow"""
        return (f"{self.__class__.__name__}("
                f"llm={type(self.llm).__name__}, "
                f"max_retries={self.max_retries}, "
                f"max_steps={self.max_steps})")