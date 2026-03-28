from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Union
import json
from llama_index.llms.ollama import Ollama
from llama_index.llms.azure_openai import AzureOpenAI

class GCodeCommand(BaseModel):
    command: str
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None
    f: Optional[int] = None
    s: Optional[int] = None
    p: Optional[int] = None

    def to_gcode(self) -> str:
        parts = [self.command]
        for attr, value in self.__dict__.items():
            if value is not None and attr != 'command':
                parts.append(f"{attr.upper()}{value:.3f}" if isinstance(value, float) else f"{attr.upper()}{value}")
        return " ".join(parts)

class GCodeProgram(BaseModel):
    commands: List[GCodeCommand]

    def to_gcode(self) -> str:
        return "\n".join(cmd.to_gcode() for cmd in self.commands)

class WorkflowException(Exception):
    def __init__(self, message: str, details: Dict = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

class GCodePredictor:
    """Handles structured prediction of G-code sequences"""
    
    COMMAND_TEMPLATES = {
        "move": {
            "command": "G0",
            "params": ["x", "y", "z"]
        },
        "line": {
            "command": "G1",
            "params": ["x", "y", "z", "f"]
        },
        "dwell": {
            "command": "G4",
            "params": ["p"]
        },
        "speed": {
            "command": "M3",
            "params": ["s"]
        }
    }

    def __init__(self, model_name: str = "llama3.2:3b"):
        self.model_name = model_name
        self._setup_llm()

    def _setup_llm(self):
        """Initialize the language model"""
        try:
            self.llm = Ollama(model=self.model_name, request_timeout=10000)

            import os
            
            self.llm = AzureOpenAI(
                        model="gpt-4o",
                        deployment_name="gpt-4o-gs",
                        api_key=os.environ.get("GPT4_API_KEY"),
                        api_version=os.environ.get("GPT4_API_VERSION"),
                        azure_endpoint=os.environ.get("GPT4_ENDPOINT"),
                        timeout=1220,)
            
        except Exception as e:
            raise WorkflowException("Failed to initialize LLM", {"error": str(e)})

    def _parse_json_safely(self, text: str) -> dict:
        """Safely parse JSON from LLM response"""
        # Clean up common JSON issues
        text = text.strip()
        text = text.replace("```json", "").replace("```", "")
        
        # Handle potential trailing commas
        text = text.replace(",]", "]").replace(",}", "}")
        
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise WorkflowException("Invalid JSON format", {
                "error": str(e),
                "text": text
            })

    def _validate_command_sequence(self, commands: List[dict]) -> List[GCodeCommand]:
        """Validate and convert commands to GCodeCommand objects"""
        validated_commands = []
        
        for cmd in commands:
            # Ensure command is present
            if "command" not in cmd:
                raise WorkflowException("Missing command field", {"command_data": cmd})
            
            # Clean up command format
            cmd["command"] = cmd["command"].upper().strip()
            
            # Convert to GCodeCommand
            try:
                validated_commands.append(GCodeCommand(**cmd))
            except Exception as e:
                raise WorkflowException("Invalid command format", {
                    "command_data": cmd,
                    "error": str(e)
                })
        
        return validated_commands

    def generate_gcode(self, prompt: str, max_retries: int = 3) -> str:
        """Generate G-code with structured prediction and error handling"""
        template = """
        Create G-code commands for a pen plotter based on this prompt: {prompt}
        
        Expected output format (JSON):
        {{
            "commands": [
                {{"command": "G0", "x": float, "y": float, "z": float}},
                {{"command": "G1", "x": float, "y": float, "f": int}},
                {{"command": "M3", "s": int}}
            ]
        }}
        
        Rules:
        1. Use G0 for rapid movements (no drawing)
        2. Use G1 for drawing lines with feed rate (f)
        3. Use M3/M5 for pen up/down
        4. Always include feed rate (f) with G1 commands
        5. Use only commands: G0, G1, M3, M5
        6. All coordinates (x,y,z) should be float numbers
        7. Feed rate (f) and speed (s) should be integers
        
        Return only the JSON, no additional text.
        """
        
        for attempt in range(max_retries):
            try:
                # Get LLM response
                response = self.llm.complete(template.format(prompt=prompt))
                
                # Parse and validate JSON
                data = self._parse_json_safely(response.text)
                if "commands" not in data:
                    raise WorkflowException("Missing commands array in response")
                
                # Validate commands
                commands = self._validate_command_sequence(data["commands"])
                
                # Create and return program
                program = GCodeProgram(commands=commands)
                return program.to_gcode()
            
            except WorkflowException as e:
                if attempt == max_retries - 1:
                    raise e
                continue
            except Exception as e:
                if attempt == max_retries - 1:
                    raise WorkflowException("Unexpected error", {"error": str(e)})
                continue
        
        raise WorkflowException("Failed to generate valid G-code after retries")

def generate_gcode(prompt: str) -> str:
    """Simplified interface for G-code generation"""
    try:
        predictor = GCodePredictor()
        return predictor.generate_gcode(prompt)
    except WorkflowException as e:
        return f"Error: {e.message}\nDetails: {json.dumps(e.details, indent=2)}"
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == "__main__":
    # Test with different prompts
    test_prompts = [
        "draw a square 10x10 units",
        "draw a diagonal line from 0,0 to 50,50",
        "draw something crazy with decimals",
    ]
    
    for prompt in test_prompts:
        print(f"\nPrompt: {prompt}")
        print("=" * 40)
        print(generate_gcode(prompt))
        print("=" * 40)