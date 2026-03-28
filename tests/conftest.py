"""
Pytest configuration and shared fixtures for PromptPlot v3.0 tests.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock
from typing import Dict, Any, List
import tempfile
from pathlib import Path

from promptplot.models import GCodeCommand, GCodeProgram
from promptplot.llm import LLMProvider
from promptplot.plotter import BasePlotter


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
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=None)
    return mock


@pytest.fixture
def sample_prompts():
    """Sample prompts for testing different drawing scenarios."""
    return {
        "simple_line": "Draw a straight line from (0,0) to (10,10)",
        "rectangle": "Draw a rectangle with corners at (0,0), (10,0), (10,5), (0,5)",
        "circle": "Draw a circle with center at (5,5) and radius 3",
        "complex": "Draw a house with a triangular roof, rectangular base, and a door",
    }


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
def test_files(temp_dir, sample_gcode_file_content):
    """Create test files in temporary directory."""
    files = {}
    gcode_file = temp_dir / "test.gcode"
    gcode_file.write_text(sample_gcode_file_content)
    files["gcode"] = gcode_file
    return files


@pytest.fixture
def mock_config():
    """Mock configuration dict for testing."""
    return {
        "llm": {
            "provider": "test",
            "model": "test-model",
            "timeout": 30
        },
        "serial": {
            "port": "TEST_PORT",
            "baud_rate": 115200,
            "timeout": 5
        },
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


__all__ = [
    "assert_valid_gcode_command",
    "assert_valid_gcode_program",
    "MockLLMResponse",
]
