"""
Prompt Template Management System

This module provides centralized management of prompt templates
extracted from existing workflow files, with validation and parameter substitution.
"""

import re
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass
from enum import Enum


class TemplateType(Enum):
    """Types of prompt templates"""
    GCODE_PROGRAM = "gcode_program"
    NEXT_COMMAND = "next_command" 
    REFLECTION = "reflection"
    STREAMING = "streaming"


@dataclass
class TemplateValidationResult:
    """Result of template validation"""
    is_valid: bool
    missing_parameters: List[str]
    extra_parameters: List[str]
    errors: List[str]


class PromptTemplate:
    """
    A prompt template with parameter validation and substitution.
    
    Extracted from existing workflow patterns in boilerplate files.
    """
    
    def __init__(
        self,
        name: str,
        template: str,
        required_parameters: Optional[Set[str]] = None,
        optional_parameters: Optional[Set[str]] = None,
        description: Optional[str] = None
    ):
        """
        Initialize a prompt template.
        
        Args:
            name: Template name/identifier
            template: Template string with {parameter} placeholders
            required_parameters: Set of required parameter names
            optional_parameters: Set of optional parameter names
            description: Template description
        """
        self.name = name
        self.template = template
        self.required_parameters = required_parameters or set()
        self.optional_parameters = optional_parameters or set()
        self.description = description
        
        # Extract parameters from template
        self._template_parameters = self._extract_parameters()
        
        # Validate template consistency
        self._validate_template_consistency()
    
    def _extract_parameters(self) -> Set[str]:
        """Extract parameter names from template string"""
        # Find all {parameter} patterns, but ignore escaped braces {{}}
        # This regex looks for single braces that are not part of double braces
        pattern = r'(?<!\{)\{([^{}]+)\}(?!\})'
        matches = re.findall(pattern, self.template)
        return set(matches)
    
    def _validate_template_consistency(self) -> None:
        """Validate that template parameters match declared parameters"""
        declared_params = self.required_parameters | self.optional_parameters
        
        # Check for undeclared parameters in template
        undeclared = self._template_parameters - declared_params
        if undeclared:
            raise ValueError(
                f"Template '{self.name}' contains undeclared parameters: {undeclared}"
            )
        
        # Check for declared parameters not in template
        unused = declared_params - self._template_parameters
        if unused:
            raise ValueError(
                f"Template '{self.name}' declares unused parameters: {unused}"
            )
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> TemplateValidationResult:
        """
        Validate provided parameters against template requirements.
        
        Args:
            parameters: Dictionary of parameter values
            
        Returns:
            Validation result with details
        """
        provided_params = set(parameters.keys())
        
        # Check for missing required parameters
        missing_required = self.required_parameters - provided_params
        
        # Check for extra parameters
        all_valid_params = self.required_parameters | self.optional_parameters
        extra_params = provided_params - all_valid_params
        
        errors = []
        if missing_required:
            errors.append(f"Missing required parameters: {missing_required}")
        if extra_params:
            errors.append(f"Unknown parameters: {extra_params}")
        
        return TemplateValidationResult(
            is_valid=len(errors) == 0,
            missing_parameters=list(missing_required),
            extra_parameters=list(extra_params),
            errors=errors
        )
    
    def format(self, **parameters) -> str:
        """
        Format the template with provided parameters.
        
        Args:
            **parameters: Parameter values
            
        Returns:
            Formatted template string
            
        Raises:
            ValueError: If required parameters are missing or validation fails
        """
        validation = self.validate_parameters(parameters)
        
        if not validation.is_valid:
            raise ValueError(
                f"Template '{self.name}' validation failed: {'; '.join(validation.errors)}"
            )
        
        try:
            return self.template.format(**parameters)
        except KeyError as e:
            raise ValueError(f"Missing parameter for template '{self.name}': {e}")
        except Exception as e:
            raise ValueError(f"Error formatting template '{self.name}': {e}")


class PromptTemplateManager:
    """
    Centralized manager for prompt templates.
    
    Provides access to all templates extracted from existing workflow files.
    """
    
    def __init__(self):
        """Initialize the template manager with default templates"""
        self._templates: Dict[str, PromptTemplate] = {}
        self._load_default_templates()
    
    def _load_default_templates(self) -> None:
        """Load default templates extracted from boilerplate files"""
        
        # G-code Program Template (from generate_llm_simple.py)
        gcode_program_template = '''
Create G-code for a pen plotter. Prompt: {prompt}

Return a JSON with "commands" list containing G-code commands.
Format:
{{{{
    "commands": [
        {{{{"command": "G0", "x": 0, "y": 0}}}},
        {{{{"command": "G1", "x": 10, "y": 10, "f": 1000}}}}
    ]
}}}}

Include pen up/down movements with M3/M5 commands.
Use realistic coordinates and values.
Ensure the drawing is complete and the pen returns to the starting position.
write just the JSON, no other text.
'''
        
        self.register_template(PromptTemplate(
            name="gcode_program",
            template=gcode_program_template.strip(),
            required_parameters={"prompt"},
            description="Generate complete G-code program from prompt"
        ))
        
        # Next Command Template (from generate_llm_advanced.py and streaming files)
        next_command_template = '''
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
{{{{"command": "G0", "x": 10.0, "y": 20.0, "z": 0.0}}}}

If the drawing is complete, return:
{{{{"command": "COMPLETE"}}}}

Do not include any explanations, just the JSON object.
'''
        
        self.register_template(PromptTemplate(
            name="next_command",
            template=next_command_template.strip(),
            required_parameters={"prompt", "history"},
            description="Generate next single G-code command with history context"
        ))
        
        # Reflection Template (from all boilerplate files)
        reflection_template = '''
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
'''
        
        self.register_template(PromptTemplate(
            name="reflection",
            template=reflection_template.strip(),
            required_parameters={"wrong_answer", "error"},
            description="Reflection prompt for error correction"
        ))
        
        # Streaming Template (from llm_stream_advanced.py)
        streaming_template = '''
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
{{{{"command": "G0", "x": 0.0, "y": 0.0, "z": 5.0}}}}

When the drawing is complete, output:
{{{{"command": "COMPLETE"}}}}

Return only the JSON objects, no additional text.
'''
        
        self.register_template(PromptTemplate(
            name="streaming",
            template=streaming_template.strip(),
            required_parameters={"prompt", "history"},
            description="Streaming G-code generation template"
        ))
        
        # Enhanced Next Command Template (with coordinate bounds from llm_stream_simple.py)
        enhanced_next_command_template = '''
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
{{{{"command": "G0", "x": 10.0, "y": 20.0, "z": 0.0}}}}

If the drawing is complete, return:
{{{{"command": "COMPLETE"}}}}

Do not include any explanations, just the JSON object.
'''
        
        self.register_template(PromptTemplate(
            name="next_command_enhanced",
            template=enhanced_next_command_template.strip(),
            required_parameters={"prompt", "history"},
            description="Enhanced next command template with coordinate bounds and recommendations"
        ))
    
    def register_template(self, template: PromptTemplate) -> None:
        """
        Register a new template.
        
        Args:
            template: Template to register
            
        Raises:
            ValueError: If template name already exists
        """
        if template.name in self._templates:
            raise ValueError(f"Template '{template.name}' already exists")
        
        self._templates[template.name] = template
    
    def get_template(self, name: str) -> PromptTemplate:
        """
        Get a template by name.
        
        Args:
            name: Template name
            
        Returns:
            The requested template
            
        Raises:
            KeyError: If template doesn't exist
        """
        if name not in self._templates:
            raise KeyError(f"Template '{name}' not found. Available: {list(self._templates.keys())}")
        
        return self._templates[name]
    
    def list_templates(self) -> List[str]:
        """
        List all available template names.
        
        Returns:
            List of template names
        """
        return list(self._templates.keys())
    
    def format_template(self, name: str, **parameters) -> str:
        """
        Format a template with parameters.
        
        Args:
            name: Template name
            **parameters: Template parameters
            
        Returns:
            Formatted template string
            
        Raises:
            KeyError: If template doesn't exist
            ValueError: If parameters are invalid
        """
        template = self.get_template(name)
        return template.format(**parameters)
    
    def validate_template_parameters(self, name: str, parameters: Dict[str, Any]) -> TemplateValidationResult:
        """
        Validate parameters for a template.
        
        Args:
            name: Template name
            parameters: Parameters to validate
            
        Returns:
            Validation result
            
        Raises:
            KeyError: If template doesn't exist
        """
        template = self.get_template(name)
        return template.validate_parameters(parameters)
    
    def get_template_info(self, name: str) -> Dict[str, Any]:
        """
        Get information about a template.
        
        Args:
            name: Template name
            
        Returns:
            Dictionary with template information
            
        Raises:
            KeyError: If template doesn't exist
        """
        template = self.get_template(name)
        
        return {
            "name": template.name,
            "description": template.description,
            "required_parameters": list(template.required_parameters),
            "optional_parameters": list(template.optional_parameters),
            "template_parameters": list(template._template_parameters)
        }


# Global template manager instance
_template_manager = None


def get_template_manager() -> PromptTemplateManager:
    """
    Get the global template manager instance.
    
    Returns:
        Global template manager
    """
    global _template_manager
    if _template_manager is None:
        _template_manager = PromptTemplateManager()
    return _template_manager


def format_template(name: str, **parameters) -> str:
    """
    Convenience function to format a template.
    
    Args:
        name: Template name
        **parameters: Template parameters
        
    Returns:
        Formatted template string
    """
    return get_template_manager().format_template(name, **parameters)


def list_templates() -> List[str]:
    """
    Convenience function to list available templates.
    
    Returns:
        List of template names
    """
    return get_template_manager().list_templates()