"""
Comprehensive CLI integration tests.
Tests all CLI commands with various file formats and configurations.
"""
import pytest
import asyncio
import tempfile
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, Mock

from promptplot.cli import PromptPlotCLI
from promptplot.config import get_config, save_config
from tests.fixtures.sample_files import create_test_files
from tests.utils.mocks import MockLLMProvider, MockPlotter


class TestCLIWorkflowCommands:
    """Test CLI workflow execution commands."""
    
    @pytest.fixture
    def cli(self):
        """Create CLI instance for testing."""
        return PromptPlotCLI()
    
    @pytest.mark.integration
    async def test_simple_workflow_command(self, cli, temp_dir):
        """Test simple workflow CLI command."""
        output_file = temp_dir / "simple_output.gcode"
        
        # Mock the workflow execution
        with patch('promptplot.workflows.simple_batch.SimpleGCodeWorkflow') as mock_workflow_class:
            mock_workflow = Mock()
            mock_workflow.run.return_value = Mock(commands=[])
            mock_workflow_class.return_value = mock_workflow
            
            result = await cli.run([
                "workflow", "simple", "Draw a test line",
                "--output", str(output_file),
                "--simulate"
            ])
            
            assert result == 0
            mock_workflow.run.assert_called_once()
    
    @pytest.mark.integration
    async def test_advanced_workflow_command(self, cli):
        """Test advanced workflow CLI command."""
        with patch('promptplot.workflows.advanced_sequential.SequentialGCodeWorkflow') as mock_workflow_class:
            mock_workflow = Mock()
            mock_workflow.run.return_value = Mock(commands=[])
            mock_workflow_class.return_value = mock_workflow
            
            result = await cli.run([
                "workflow", "advanced", "Draw a complex shape",
                "--steps", "10",
                "--simulate"
            ])
            
            assert result == 0
            mock_workflow.run.assert_called_once()
    
    @pytest.mark.integration
    async def test_streaming_workflow_command(self, cli):
        """Test streaming workflow CLI command."""
        with patch('promptplot.workflows.simple_streaming.SimpleStreamingWorkflow') as mock_workflow_class:
            mock_workflow = Mock()
            mock_workflow.run.return_value = Mock()
            mock_workflow_class.return_value = mock_workflow
            
            result = await cli.run([
                "workflow", "streaming", "Draw in real-time",
                "--simulate"
            ])
            
            assert result == 0
            mock_workflow.run.assert_called_once()
    
    @pytest.mark.integration
    async def test_enhanced_workflow_command(self, cli):
        """Test enhanced workflow with vision CLI command."""
        with patch('promptplot.workflows.plot_enhanced.PlotEnhancedWorkflow') as mock_workflow_class:
            mock_workflow = Mock()
            mock_workflow.run.return_value = Mock()
            mock_workflow_class.return_value = mock_workflow
            
            result = await cli.run([
                "workflow", "enhanced", "Draw with vision feedback",
                "--simulate",
                "--vision"
            ])
            
            assert result == 0
            mock_workflow.run.assert_called_once()


class TestCLIFileCommands:
    """Test CLI file plotting commands."""
    
    @pytest.fixture
    def cli(self):
        """Create CLI instance for testing."""
        return PromptPlotCLI()
    
    @pytest.fixture
    def test_files(self, temp_dir):
        """Create test files for CLI testing."""
        return create_test_files(temp_dir)
    
    @pytest.mark.integration
    async def test_file_plot_command_svg(self, cli, test_files):
        """Test plotting SVG file via CLI."""
        svg_file = test_files["svg"]
        
        with patch('promptplot.workflows.file_plotting.FilePlottingWorkflow') as mock_workflow_class:
            mock_workflow = Mock()
            mock_workflow.plot_file.return_value = Mock(commands=[])
            mock_workflow_class.return_value = mock_workflow
            
            result = await cli.run([
                "file", "plot", str(svg_file),
                "--simulate",
                "--preview"
            ])
            
            assert result == 0
            mock_workflow.plot_file.assert_called_once_with(svg_file)
    
    @pytest.mark.integration
    async def test_file_plot_command_gcode(self, cli, test_files):
        """Test plotting G-code file via CLI."""
        gcode_file = test_files["gcode"]
        
        with patch('promptplot.workflows.file_plotting.FilePlottingWorkflow') as mock_workflow_class:
            mock_workflow = Mock()
            mock_workflow.plot_file.return_value = Mock(commands=[])
            mock_workflow_class.return_value = mock_workflow
            
            result = await cli.run([
                "file", "plot", str(gcode_file),
                "--simulate"
            ])
            
            assert result == 0
            mock_workflow.plot_file.assert_called_once()
    
    @pytest.mark.integration
    async def test_file_plot_command_dxf(self, cli, test_files):
        """Test plotting DXF file via CLI."""
        dxf_file = test_files["dxf"]
        
        with patch('promptplot.workflows.file_plotting.FilePlottingWorkflow') as mock_workflow_class:
            mock_workflow = Mock()
            mock_workflow.plot_file.return_value = Mock(commands=[])
            mock_workflow_class.return_value = mock_workflow
            
            result = await cli.run([
                "file", "plot", str(dxf_file),
                "--simulate",
                "--scale", "2.0", "2.0", "1.0"
            ])
            
            assert result == 0
            mock_workflow.plot_file.assert_called_once()
    
    @pytest.mark.integration
    async def test_file_convert_command(self, cli, test_files, temp_dir):
        """Test file conversion via CLI."""
        svg_file = test_files["svg"]
        output_file = temp_dir / "converted.gcode"
        
        with patch('promptplot.converters.svg_converter.SVGConverter') as mock_converter_class:
            mock_converter = Mock()
            mock_converter.convert.return_value = Mock(commands=[])
            mock_converter_class.return_value = mock_converter
            
            result = await cli.run([
                "file", "convert", str(svg_file), str(output_file)
            ])
            
            assert result == 0
    
    @pytest.mark.integration
    async def test_file_validate_command(self, cli, test_files):
        """Test file validation via CLI."""
        gcode_file = test_files["gcode"]
        
        with patch('promptplot.converters.gcode_loader.GCodeLoader') as mock_loader_class:
            mock_loader = Mock()
            mock_loader.validate_file.return_value = (True, [])
            mock_loader_class.return_value = mock_loader
            
            result = await cli.run([
                "file", "validate", str(gcode_file)
            ])
            
            assert result == 0
    
    @pytest.mark.integration
    async def test_file_batch_command(self, cli, test_files):
        """Test batch file plotting via CLI."""
        files_to_plot = [
            str(test_files["svg"]),
            str(test_files["gcode"]),
            str(test_files["dxf"])
        ]
        
        with patch('promptplot.workflows.file_plotting.FilePlottingWorkflow') as mock_workflow_class:
            mock_workflow = Mock()
            mock_workflow.plot_files_batch.return_value = [Mock(commands=[]) for _ in files_to_plot]
            mock_workflow_class.return_value = mock_workflow
            
            result = await cli.run([
                "file", "batch", *files_to_plot,
                "--simulate",
                "--delay", "1.0"
            ])
            
            assert result == 0
            mock_workflow.plot_files_batch.assert_called_once()


class TestCLIConfigCommands:
    """Test CLI configuration commands."""
    
    @pytest.fixture
    def cli(self):
        """Create CLI instance for testing."""
        return PromptPlotCLI()
    
    @pytest.mark.integration
    async def test_config_show_command(self, cli):
        """Test config show command."""
        result = await cli.run(["config", "show"])
        assert result == 0
    
    @pytest.mark.integration
    async def test_config_show_json_format(self, cli):
        """Test config show with JSON format."""
        result = await cli.run(["config", "show", "--format", "json"])
        assert result == 0
    
    @pytest.mark.integration
    async def test_config_show_section(self, cli):
        """Test config show specific section."""
        result = await cli.run(["config", "show", "--section", "llm"])
        assert result == 0
    
    @pytest.mark.integration
    async def test_config_set_command(self, cli):
        """Test config set command."""
        with patch('promptplot.config.save_config') as mock_save:
            mock_save.return_value = True
            
            result = await cli.run([
                "config", "set", "workflow.max_retries", "5"
            ])
            
            assert result == 0
            mock_save.assert_called_once()
    
    @pytest.mark.integration
    async def test_config_reset_command(self, cli):
        """Test config reset command."""
        with patch('promptplot.config.reset_config') as mock_reset:
            result = await cli.run([
                "config", "reset", "--confirm"
            ])
            
            assert result == 0
            mock_reset.assert_called_once()
    
    @pytest.mark.integration
    async def test_config_profile_list(self, cli):
        """Test config profile list command."""
        with patch('promptplot.config.list_profiles') as mock_list:
            mock_list.return_value = ["default", "test"]
            
            result = await cli.run([
                "config", "profile", "list"
            ])
            
            assert result == 0
            mock_list.assert_called_once()
    
    @pytest.mark.integration
    async def test_config_profile_switch(self, cli):
        """Test config profile switch command."""
        with patch('promptplot.config.switch_profile') as mock_switch:
            mock_switch.return_value = True
            
            result = await cli.run([
                "config", "profile", "switch", "test"
            ])
            
            assert result == 0
            mock_switch.assert_called_once_with("test")


class TestCLIPlotterCommands:
    """Test CLI plotter commands."""
    
    @pytest.fixture
    def cli(self):
        """Create CLI instance for testing."""
        return PromptPlotCLI()
    
    @pytest.mark.integration
    async def test_plotter_connect_command(self, cli):
        """Test plotter connect command."""
        with patch('promptplot.plotter.serial_plotter.SerialPlotter') as mock_plotter_class:
            mock_plotter = Mock()
            mock_plotter.connect.return_value = True
            mock_plotter_class.return_value = mock_plotter
            
            result = await cli.run([
                "plotter", "connect", "--port", "/dev/ttyUSB0"
            ])
            
            assert result == 0
    
    @pytest.mark.integration
    async def test_plotter_test_command(self, cli):
        """Test plotter test command."""
        with patch('promptplot.plotter.simulated.SimulatedPlotter') as mock_plotter_class:
            mock_plotter = Mock()
            mock_plotter.send_command.return_value = True
            mock_plotter_class.return_value = mock_plotter
            
            result = await cli.run([
                "plotter", "test", "--simulate",
                "--commands", "G28", "G1 X10 Y10"
            ])
            
            assert result == 0
    
    @pytest.mark.integration
    async def test_plotter_status_command(self, cli):
        """Test plotter status command."""
        with patch('promptplot.plotter.serial_plotter.SerialPlotter') as mock_plotter_class:
            mock_plotter = Mock()
            mock_plotter.get_status.return_value = {"connected": True, "port": "/dev/ttyUSB0"}
            mock_plotter_class.return_value = mock_plotter
            
            result = await cli.run([
                "plotter", "status", "--port", "/dev/ttyUSB0"
            ])
            
            assert result == 0
    
    @pytest.mark.integration
    async def test_plotter_list_ports_command(self, cli):
        """Test plotter list-ports command."""
        with patch('serial.tools.list_ports.comports') as mock_list_ports:
            mock_list_ports.return_value = [
                Mock(device="/dev/ttyUSB0", description="USB Serial"),
                Mock(device="/dev/ttyUSB1", description="Arduino")
            ]
            
            result = await cli.run([
                "plotter", "list-ports"
            ])
            
            assert result == 0


class TestCLIInteractiveMode:
    """Test CLI interactive mode."""
    
    @pytest.fixture
    def cli(self):
        """Create CLI instance for testing."""
        return PromptPlotCLI()
    
    @pytest.mark.integration
    async def test_interactive_mode_startup(self, cli):
        """Test interactive mode startup."""
        # Mock input to exit immediately
        with patch('builtins.input', side_effect=['quit']):
            result = await cli.run(["interactive"])
            assert result == 0


class TestCLIErrorHandling:
    """Test CLI error handling scenarios."""
    
    @pytest.fixture
    def cli(self):
        """Create CLI instance for testing."""
        return PromptPlotCLI()
    
    @pytest.mark.integration
    async def test_invalid_command(self, cli):
        """Test handling of invalid commands."""
        result = await cli.run(["invalid_command"])
        assert result == 1
    
    @pytest.mark.integration
    async def test_missing_arguments(self, cli):
        """Test handling of missing arguments."""
        result = await cli.run(["workflow"])
        assert result == 1
    
    @pytest.mark.integration
    async def test_invalid_file_path(self, cli):
        """Test handling of invalid file paths."""
        result = await cli.run([
            "file", "plot", "/nonexistent/file.svg"
        ])
        assert result == 1
    
    @pytest.mark.integration
    async def test_invalid_config_key(self, cli):
        """Test handling of invalid configuration keys."""
        result = await cli.run([
            "config", "set", "invalid.key", "value"
        ])
        assert result == 1
    
    @pytest.mark.integration
    async def test_plotter_connection_failure(self, cli):
        """Test handling of plotter connection failures."""
        with patch('promptplot.plotter.serial_plotter.SerialPlotter') as mock_plotter_class:
            mock_plotter = Mock()
            mock_plotter.connect.side_effect = Exception("Connection failed")
            mock_plotter_class.return_value = mock_plotter
            
            result = await cli.run([
                "plotter", "connect", "--port", "/dev/invalid"
            ])
            
            assert result == 1


class TestCLIIntegrationWithRealFiles:
    """Test CLI integration with real file operations."""
    
    @pytest.fixture
    def cli(self):
        """Create CLI instance for testing."""
        return PromptPlotCLI()
    
    @pytest.mark.integration
    async def test_cli_with_real_gcode_file(self, cli, temp_dir):
        """Test CLI with real G-code file."""
        # Create a real G-code file
        gcode_content = """
G28 ; Home all axes
G1 X10 Y10 F1000 ; Move to start
M3 S255 ; Pen down
G1 X20 Y20 F1000 ; Draw line
G1 X20 Y10 F1000 ; Draw line
G1 X10 Y10 F1000 ; Draw line
M5 ; Pen up
G28 ; Return home
"""
        gcode_file = temp_dir / "test.gcode"
        gcode_file.write_text(gcode_content.strip())
        
        # Test validation
        result = await cli.run([
            "file", "validate", str(gcode_file)
        ])
        assert result == 0
        
        # Test plotting with simulation
        result = await cli.run([
            "file", "plot", str(gcode_file), "--simulate", "--preview"
        ])
        assert result == 0
    
    @pytest.mark.integration
    async def test_cli_with_real_svg_file(self, cli, temp_dir):
        """Test CLI with real SVG file."""
        # Create a simple SVG file
        svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
  <rect x="10" y="10" width="30" height="30" fill="none" stroke="black"/>
  <circle cx="70" cy="30" r="15" fill="none" stroke="black"/>
</svg>'''
        svg_file = temp_dir / "test.svg"
        svg_file.write_text(svg_content)
        
        # Test conversion
        output_file = temp_dir / "converted.gcode"
        result = await cli.run([
            "file", "convert", str(svg_file), str(output_file)
        ])
        assert result == 0
        
        # Test plotting
        result = await cli.run([
            "file", "plot", str(svg_file), "--simulate", "--preview"
        ])
        assert result == 0
    
    @pytest.mark.integration
    async def test_cli_configuration_persistence(self, cli, temp_dir):
        """Test CLI configuration persistence."""
        # Set a configuration value
        result = await cli.run([
            "config", "set", "workflow.max_retries", "7"
        ])
        assert result == 0
        
        # Verify the value was set
        result = await cli.run([
            "config", "show", "--section", "workflow", "--format", "json"
        ])
        assert result == 0
        
        # Reset configuration
        result = await cli.run([
            "config", "reset", "--confirm"
        ])
        assert result == 0


class TestCLIPerformance:
    """Test CLI performance characteristics."""
    
    @pytest.fixture
    def cli(self):
        """Create CLI instance for testing."""
        return PromptPlotCLI()
    
    @pytest.mark.integration
    @pytest.mark.slow
    async def test_cli_startup_performance(self, cli):
        """Test CLI startup performance."""
        import time
        
        start_time = time.time()
        result = await cli.run(["--help"])
        end_time = time.time()
        
        startup_time = end_time - start_time
        assert startup_time < 2.0, f"CLI startup too slow: {startup_time}s"
        assert result == 0
    
    @pytest.mark.integration
    async def test_cli_command_response_time(self, cli):
        """Test CLI command response times."""
        import time
        
        commands_to_test = [
            ["config", "show"],
            ["plotter", "list-ports"],
            ["--version"]
        ]
        
        for command in commands_to_test:
            start_time = time.time()
            result = await cli.run(command)
            end_time = time.time()
            
            response_time = end_time - start_time
            assert response_time < 5.0, f"Command {command} too slow: {response_time}s"
            assert result == 0


class TestCLISubprocessIntegration:
    """Test CLI as subprocess (real CLI execution)."""
    
    @pytest.mark.integration
    def test_cli_help_subprocess(self):
        """Test CLI help via subprocess."""
        result = subprocess.run([
            sys.executable, "-m", "promptplot.cli", "--help"
        ], capture_output=True, text=True, timeout=10)
        
        assert result.returncode == 0
        assert "PromptPlot v2.0" in result.stdout
        assert "workflow" in result.stdout
        assert "config" in result.stdout
    
    @pytest.mark.integration
    def test_cli_version_subprocess(self):
        """Test CLI version via subprocess."""
        result = subprocess.run([
            sys.executable, "-m", "promptplot.cli", "--version"
        ], capture_output=True, text=True, timeout=10)
        
        assert result.returncode == 0
        assert "PromptPlot v2.0" in result.stdout
    
    @pytest.mark.integration
    def test_cli_config_show_subprocess(self):
        """Test CLI config show via subprocess."""
        result = subprocess.run([
            sys.executable, "-m", "promptplot.cli", "config", "show", "--format", "json"
        ], capture_output=True, text=True, timeout=10)
        
        assert result.returncode == 0
        
        # Should be valid JSON
        try:
            config_data = json.loads(result.stdout)
            assert isinstance(config_data, dict)
            assert "llm" in config_data
            assert "workflow" in config_data
        except json.JSONDecodeError:
            pytest.fail("CLI config show did not return valid JSON")
    
    @pytest.mark.integration
    def test_cli_plotter_list_ports_subprocess(self):
        """Test CLI plotter list-ports via subprocess."""
        result = subprocess.run([
            sys.executable, "-m", "promptplot.cli", "plotter", "list-ports"
        ], capture_output=True, text=True, timeout=10)
        
        # Should succeed even if no ports found
        assert result.returncode == 0
    
    @pytest.mark.integration
    def test_cli_invalid_command_subprocess(self):
        """Test CLI invalid command via subprocess."""
        result = subprocess.run([
            sys.executable, "-m", "promptplot.cli", "invalid_command"
        ], capture_output=True, text=True, timeout=10)
        
        assert result.returncode == 1
        assert "Unknown command" in result.stderr or "error" in result.stderr.lower()