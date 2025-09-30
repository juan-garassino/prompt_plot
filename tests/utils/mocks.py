"""
Mock objects for testing PromptPlot components.
"""
from unittest.mock import Mock, AsyncMock, MagicMock
from typing import Dict, Any, List, Optional
import json
import asyncio

from promptplot.core.models import GCodeCommand, GCodeProgram
from promptplot.llm.providers import LLMProvider
from promptplot.plotter.base import BasePlotter


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing."""
    
    def __init__(self, responses: Optional[List[str]] = None):
        super().__init__(timeout=30)
        self.responses = responses or [
            '{"command": "G1", "x": 10.0, "y": 20.0, "f": 1000}',
            '{"command": "G1", "x": 30.0, "y": 40.0, "f": 1000}',
            '{"command": "M5"}'
        ]
        self.call_count = 0
        self.last_prompt = None
    
    @property
    def provider_name(self) -> str:
        return "mock"
    
    def _create_llm_instance(self):
        return Mock()  # Return a mock instance
        
    async def acomplete(self, prompt: str) -> str:
        """Mock async completion."""
        self.last_prompt = prompt
        response = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1
        # Simulate some processing time
        await asyncio.sleep(0.01)
        return response
        
    def complete(self, prompt: str) -> str:
        """Mock sync completion."""
        self.last_prompt = prompt
        response = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1
        return response


class MockPlotter(BasePlotter):
    """Mock plotter for testing."""
    
    def __init__(self, port: str = "MOCK_PORT", fail_on_command: Optional[str] = None):
        super().__init__(port)
        self.sent_commands = []
        self.fail_on_command = fail_on_command
        self.command_history = []
        
    async def connect(self) -> bool:
        """Mock connection."""
        await asyncio.sleep(0.01)  # Simulate connection time
        self._active = True
        return True
        
    async def disconnect(self) -> None:
        """Mock disconnection."""
        await asyncio.sleep(0.01)
        self._active = False
        
    async def send_command(self, command: str) -> bool:
        """Mock command sending."""
        if not self.is_connected:
            raise ConnectionError("Plotter not connected")
            
        if self.fail_on_command and self.fail_on_command in command:
            return False
            
        self.sent_commands.append(command)
        self.command_history.append(command)
        await asyncio.sleep(0.01)  # Simulate command execution time
        return True
        
    def get_sent_commands(self) -> List[str]:
        """Get list of sent commands."""
        return self.sent_commands.copy()
        
    def clear_commands(self) -> None:
        """Clear sent commands history."""
        self.sent_commands.clear()


class MockImageProcessor:
    """Mock image processor for vision testing."""
    
    def __init__(self):
        self.processed_images = []
        
    def preprocess_image(self, image):
        """Mock image preprocessing."""
        self.processed_images.append(image)
        return image
        
    def extract_drawing_features(self, image):
        """Mock feature extraction."""
        return {
            "lines": 3,
            "curves": 1,
            "complexity": 0.6,
            "bounding_box": (0, 0, 100, 100)
        }
        
    def compare_images(self, before, after):
        """Mock image comparison."""
        return {
            "difference_score": 0.15,
            "changed_regions": [(10, 10, 50, 50)],
            "new_features": 2
        }


class MockStrategySelector:
    """Mock strategy selector for testing."""
    
    def __init__(self, default_strategy: str = "orthogonal"):
        self.default_strategy = default_strategy
        self.analysis_history = []
        
    def analyze_prompt_complexity(self, prompt: str):
        """Mock prompt analysis."""
        analysis = {
            "complexity_score": 0.5,
            "requires_curves": "curve" in prompt.lower() or "circle" in prompt.lower(),
            "estimated_commands": len(prompt.split()) * 2,
            "suggested_strategy": "non_orthogonal" if "curve" in prompt.lower() else "orthogonal"
        }
        self.analysis_history.append((prompt, analysis))
        return analysis
        
    def select_workflow(self, complexity):
        """Mock workflow selection."""
        if complexity.get("requires_curves", False):
            return "non_orthogonal"
        return "orthogonal"


class MockVisualizer:
    """Mock visualizer for testing."""
    
    def __init__(self):
        self.plots = []
        self.current_plot = None
        
    def create_plot(self, title: str = "Test Plot"):
        """Mock plot creation."""
        self.current_plot = {
            "title": title,
            "commands": [],
            "pen_position": (0, 0),
            "pen_down": False
        }
        return self.current_plot
        
    def add_command(self, command: GCodeCommand):
        """Mock command visualization."""
        if self.current_plot:
            self.current_plot["commands"].append(command)
            
    def save_plot(self, filename: str):
        """Mock plot saving."""
        if self.current_plot:
            self.plots.append((filename, self.current_plot.copy()))
            
    def get_plots(self):
        """Get saved plots."""
        return self.plots.copy()


class MockWorkflow:
    """Mock workflow for testing."""
    
    def __init__(self, name: str = "test_workflow"):
        self.name = name
        self.steps_executed = []
        self.results = []
        
    async def run(self, prompt: str, **kwargs):
        """Mock workflow execution."""
        self.steps_executed.append(("start", prompt))
        
        # Simulate workflow steps
        await asyncio.sleep(0.01)
        self.steps_executed.append(("analyze", prompt))
        
        await asyncio.sleep(0.01)
        self.steps_executed.append(("generate", prompt))
        
        result = GCodeProgram(
            commands=[
                GCodeCommand(command="G28"),
                GCodeCommand(command="G1", x=10.0, y=20.0, f=1000)
            ]
        )
        
        self.results.append(result)
        self.steps_executed.append(("complete", result))
        
        return result


def create_mock_gcode_validator():
    """Create a mock G-code validator."""
    mock = Mock()
    mock.validate_command = Mock(return_value=True)
    mock.validate_program = Mock(return_value=True)
    mock.get_validation_errors = Mock(return_value=[])
    return mock


def create_mock_file_converter(file_type: str):
    """Create a mock file converter for specific file type."""
    mock = Mock()
    
    if file_type == "svg":
        mock.convert = Mock(return_value=[
            GCodeCommand(command="G1", x=10.0, y=10.0, f=1000),
            GCodeCommand(command="G1", x=20.0, y=20.0, f=1000)
        ])
    elif file_type == "gcode":
        mock.load = Mock(return_value=GCodeProgram(
            commands=[GCodeCommand(command="G28")]
        ))
    elif file_type == "dxf":
        mock.convert = Mock(return_value=[
            GCodeCommand(command="G1", x=0.0, y=0.0, f=1000),
            GCodeCommand(command="G1", x=50.0, y=50.0, f=1000)
        ])
        
    return mock


class MockConfigManager:
    """Mock configuration manager."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {
            "llm": {"provider": "test", "model": "test-model"},
            "plotter": {"port": "TEST", "baud_rate": 115200},
            "vision": {"enabled": False}
        }
        
    def get(self, key: str, default=None):
        """Get configuration value."""
        keys = key.split(".")
        value = self.config
        for k in keys:
            value = value.get(k, default)
            if value is None:
                return default
        return value
        
    def set(self, key: str, value: Any):
        """Set configuration value."""
        keys = key.split(".")
        config = self.config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
        
    def save(self):
        """Mock save configuration."""
        pass
        
    def load(self):
        """Mock load configuration."""
        pass