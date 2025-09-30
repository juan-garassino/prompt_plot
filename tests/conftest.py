"""
Pytest configuration and shared fixtures for PromptPlot v2.0 tests.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock
from typing import Dict, Any, List
import tempfile
import os
from pathlib import Path

# Import core components for testing
from promptplot.core.models import GCodeCommand, GCodeProgram
from promptplot.core.exceptions import PromptPlotException
from promptplot.llm.providers import LLMProvider
from promptplot.plotter.base import BasePlotter


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_gcode_commands():
    """Sample G-code commands for testing."""
    return [
        GCodeCommand(command="G28", comment="Home all axes"),
        GCodeCommand(command="G1", x=10.0, y=20.0, f=1000, comment="Move to position"),
        GCodeCommand(command="M3", s=255, comment="Pen down"),
        GCodeCommand(command="G1", x=30.0, y=40.0, f=1000, comment="Draw line"),
        GCodeCommand(command="M5", comment="Pen up"),
    ]


@pytest.fixture
def sample_gcode_program(sample_gcode_commands):
    """Sample G-code program for testing."""
    return GCodeProgram(
        commands=sample_gcode_commands,
        metadata={
            "title": "Test Drawing",
            "description": "A simple test drawing",
            "created_by": "test_suite"
        }
    )


@pytest.fixture
def mock_llm_provider():
    """Mock LLM provider for testing."""
    mock = Mock(spec=LLMProvider)
    mock.acomplete = AsyncMock(return_value='{"command": "G1", "x": 10.0, "y": 20.0, "f": 1000}')
    mock.complete = Mock(return_value='{"command": "G1", "x": 10.0, "y": 20.0, "f": 1000}')
    mock.model_name = "test-model"
    return mock


@pytest.fixture
def mock_plotter():
    """Mock plotter for testing."""
    mock = Mock(spec=BasePlotter)
    mock.connect = AsyncMock(return_value=True)
    mock.disconnect = AsyncMock()
    mock.send_command = AsyncMock(return_value=True)
    mock.is_connected = True
    mock.port = "TEST_PORT"
    
    # Context manager support
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=None)
    
    return mock


@pytest.fixture
def mock_image():
    """Mock image object for vision testing."""
    mock = MagicMock()
    mock.size = (640, 480)
    mock.mode = "RGB"
    mock.format = "PNG"
    return mock


@pytest.fixture
def sample_prompts():
    """Sample prompts for testing different drawing scenarios."""
    return {
        "simple_line": "Draw a straight line from (0,0) to (10,10)",
        "rectangle": "Draw a rectangle with corners at (0,0), (10,0), (10,5), (0,5)",
        "circle": "Draw a circle with center at (5,5) and radius 3",
        "complex": "Draw a house with a triangular roof, rectangular base, and a door",
        "orthogonal": "Draw a grid pattern 5x5 with 1 unit spacing",
        "non_orthogonal": "Draw a smooth sine wave from x=0 to x=10"
    }


@pytest.fixture
def sample_svg_content():
    """Sample SVG content for file conversion testing."""
    return '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
  <rect x="10" y="10" width="30" height="30" fill="none" stroke="black"/>
  <circle cx="70" cy="30" r="15" fill="none" stroke="black"/>
  <line x1="10" y1="60" x2="90" y2="60" stroke="black"/>
</svg>'''


@pytest.fixture
def sample_gcode_file_content():
    """Sample G-code file content for testing."""
    return """G28 ; Home all axes
G1 X10 Y20 F1000 ; Move to start
M3 S255 ; Pen down
G1 X30 Y40 F1000 ; Draw line
G1 X50 Y20 F1000 ; Continue drawing
M5 ; Pen up
G28 ; Return home"""


@pytest.fixture
def sample_dxf_content():
    """Sample DXF content for testing."""
    return """0
SECTION
2
ENTITIES
0
LINE
8
0
10
0.0
20
0.0
11
10.0
21
10.0
0
CIRCLE
8
0
10
5.0
20
5.0
40
2.5
0
ENDSEC
0
EOF"""


@pytest.fixture
def test_files(temp_dir, sample_svg_content, sample_gcode_file_content, sample_dxf_content):
    """Create test files in temporary directory."""
    files = {}
    
    # SVG file
    svg_file = temp_dir / "test.svg"
    svg_file.write_text(sample_svg_content)
    files["svg"] = svg_file
    
    # G-code file
    gcode_file = temp_dir / "test.gcode"
    gcode_file.write_text(sample_gcode_file_content)
    files["gcode"] = gcode_file
    
    # DXF file
    dxf_file = temp_dir / "test.dxf"
    dxf_file.write_text(sample_dxf_content)
    files["dxf"] = dxf_file
    
    # JSON file
    json_file = temp_dir / "test.json"
    json_file.write_text('{"commands": [{"command": "G1", "x": 10, "y": 20}]}')
    files["json"] = json_file
    
    return files


@pytest.fixture
def mock_config():
    """Mock configuration for testing."""
    return {
        "llm": {
            "provider": "test",
            "model": "test-model",
            "timeout": 30
        },
        "plotter": {
            "port": "TEST_PORT",
            "baud_rate": 115200,
            "timeout": 5
        },
        "vision": {
            "enabled": False,
            "capture_interval": 1.0
        },
        "strategies": {
            "default": "orthogonal",
            "complexity_threshold": 0.5
        }
    }


@pytest.fixture
def mock_workflow_context():
    """Mock workflow context for testing."""
    return {
        "prompt": "Draw a test shape",
        "max_retries": 3,
        "max_steps": 10,
        "strategy": "orthogonal"
    }


class MockLLMResponse:
    """Mock LLM response for testing."""
    def __init__(self, content: str):
        self.content = content
        self.message = MagicMock()
        self.message.content = content


@pytest.fixture
def mock_llm_response():
    """Factory for creating mock LLM responses."""
    def _create_response(content: str):
        return MockLLMResponse(content)
    return _create_response


# Utility functions for tests
def assert_valid_gcode_command(command: GCodeCommand):
    """Assert that a G-code command is valid."""
    assert isinstance(command, GCodeCommand)
    assert command.command is not None
    assert len(command.command) > 0


def assert_valid_gcode_program(program: GCodeProgram):
    """Assert that a G-code program is valid."""
    assert isinstance(program, GCodeProgram)
    assert len(program.commands) > 0
    for command in program.commands:
        assert_valid_gcode_command(command)


# Export utility functions
__all__ = [
    "assert_valid_gcode_command",
    "assert_valid_gcode_program",
    "MockLLMResponse"
]