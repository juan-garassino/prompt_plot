"""
Unit tests for plotter interfaces and implementations.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import asyncio

from promptplot.plotter.base import BasePlotter
from promptplot.plotter.serial_plotter import SerialPlotter
from promptplot.plotter.simulated import SimulatedPlotter
from promptplot.core.exceptions import PlotterException
from tests.utils.mocks import MockPlotter


class TestBasePlotter:
    """Test base plotter interface."""
    
    @pytest.mark.unit
    def test_base_plotter_is_abstract(self):
        """Test that BasePlotter cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BasePlotter()
            
    @pytest.mark.unit
    async def test_mock_plotter_basic_operations(self):
        """Test basic mock plotter operations."""
        plotter = MockPlotter()
        
        # Test connection
        assert not plotter.is_connected
        result = await plotter.connect()
        assert result is True
        assert plotter.is_connected
        
        # Test command sending
        success = await plotter.send_command("G28")
        assert success is True
        assert "G28" in plotter.sent_commands
        
        # Test disconnection
        await plotter.disconnect()
        assert not plotter.is_connected
        
    @pytest.mark.unit
    async def test_mock_plotter_context_manager(self):
        """Test mock plotter as context manager."""
        plotter = MockPlotter()
        
        async with plotter as p:
            assert p.is_connected
            await p.send_command("G1 X10 Y20 F1000")
            
        assert not plotter.is_connected
        assert len(plotter.sent_commands) == 1
        
    @pytest.mark.unit
    async def test_mock_plotter_command_failure(self):
        """Test mock plotter command failure simulation."""
        plotter = MockPlotter(fail_on_command="G1")
        
        await plotter.connect()
        
        # This command should succeed
        success = await plotter.send_command("G28")
        assert success is True
        
        # This command should fail
        success = await plotter.send_command("G1 X10 Y20")
        assert success is False
        
    @pytest.mark.unit
    async def test_mock_plotter_disconnected_error(self):
        """Test mock plotter error when not connected."""
        plotter = MockPlotter()
        
        # Should raise error when sending command while disconnected
        with pytest.raises(ConnectionError):
            await plotter.send_command("G28")


class TestSerialPlotter:
    """Test serial plotter implementation."""
    
    @pytest.fixture
    def serial_config(self):
        """Serial plotter configuration."""
        return {
            "port": "/dev/ttyUSB0",
            "baud_rate": 115200,
            "timeout": 5.0
        }
        
    @pytest.mark.unit
    def test_serial_plotter_initialization(self, serial_config):
        """Test serial plotter initialization."""
        plotter = SerialPlotter(**serial_config)
        
        assert plotter.port == serial_config["port"]
        assert plotter.baud_rate == serial_config["baud_rate"]
        assert plotter.timeout == serial_config["timeout"]
        assert not plotter.is_connected
        
    @pytest.mark.unit
    def test_serial_plotter_default_config(self):
        """Test serial plotter with default configuration."""
        plotter = SerialPlotter(port="/dev/ttyUSB0")
        
        assert plotter.port == "/dev/ttyUSB0"
        assert plotter.baud_rate == 115200  # Default
        assert plotter.timeout == 5.0  # Default
        
    @pytest.mark.unit
    @patch('promptplot.plotter.serial_plotter.serial_asyncio.open_serial_connection')
    async def test_serial_plotter_connect_success(self, mock_open_connection, serial_config):
        """Test successful serial connection."""
        # Mock successful connection
        mock_reader = AsyncMock()
        mock_writer = Mock()
        mock_open_connection.return_value = (mock_reader, mock_writer)
        
        plotter = SerialPlotter(**serial_config)
        result = await plotter.connect()
        
        assert result is True
        assert plotter.is_connected
        mock_open_connection.assert_called_once_with(
            url=serial_config["port"],
            baudrate=serial_config["baud_rate"]
        )
        
    @pytest.mark.unit
    @patch('promptplot.plotter.serial_plotter.serial_asyncio.open_serial_connection')
    async def test_serial_plotter_connect_failure(self, mock_open_connection, serial_config):
        """Test failed serial connection."""
        # Mock connection failure
        mock_open_connection.side_effect = Exception("Port not found")
        
        plotter = SerialPlotter(**serial_config)
        
        with pytest.raises(PlotterException):
            await plotter.connect()
            
        assert not plotter.is_connected
        
    @pytest.mark.unit
    @patch('promptplot.plotter.serial_plotter.serial_asyncio.open_serial_connection')
    async def test_serial_plotter_send_command(self, mock_open_connection, serial_config):
        """Test sending commands via serial."""
        # Mock connection
        mock_reader = AsyncMock()
        mock_writer = Mock()
        mock_writer.write = Mock()
        mock_writer.drain = AsyncMock()
        mock_open_connection.return_value = (mock_reader, mock_writer)
        
        # Mock response
        mock_reader.readline.return_value = b"ok\n"
        
        plotter = SerialPlotter(**serial_config)
        await plotter.connect()
        
        result = await plotter.send_command("G28")
        
        assert result is True
        mock_writer.write.assert_called()
        mock_writer.drain.assert_called()
        
    @pytest.mark.unit
    @patch('promptplot.plotter.serial_plotter.serial_asyncio.open_serial_connection')
    async def test_serial_plotter_command_timeout(self, mock_open_connection, serial_config):
        """Test command timeout handling."""
        # Mock connection
        mock_reader = AsyncMock()
        mock_writer = Mock()
        mock_writer.write = Mock()
        mock_writer.drain = AsyncMock()
        mock_open_connection.return_value = (mock_reader, mock_writer)
        
        # Mock timeout
        mock_reader.readline.side_effect = asyncio.TimeoutError()
        
        plotter = SerialPlotter(**serial_config)
        await plotter.connect()
        
        with pytest.raises(PlotterException):
            await plotter.send_command("G28")
            
    @pytest.mark.unit
    @patch('promptplot.plotter.serial_plotter.serial_asyncio.open_serial_connection')
    async def test_serial_plotter_disconnect(self, mock_open_connection, serial_config):
        """Test serial disconnection."""
        # Mock connection
        mock_reader = AsyncMock()
        mock_writer = Mock()
        mock_writer.close = Mock()
        mock_writer.wait_closed = AsyncMock()
        mock_open_connection.return_value = (mock_reader, mock_writer)
        
        plotter = SerialPlotter(**serial_config)
        await plotter.connect()
        
        await plotter.disconnect()
        
        assert not plotter.is_connected
        mock_writer.close.assert_called_once()
        mock_writer.wait_closed.assert_called_once()


class TestSimulatedPlotter:
    """Test simulated plotter implementation."""
    
    @pytest.mark.unit
    def test_simulated_plotter_initialization(self):
        """Test simulated plotter initialization."""
        plotter = SimulatedPlotter()
        
        assert plotter.port == "SIMULATED"
        assert not plotter.is_connected
        
    @pytest.mark.unit
    def test_simulated_plotter_custom_port(self):
        """Test simulated plotter with custom port name."""
        plotter = SimulatedPlotter(port="SIM_TEST")
        
        assert plotter.port == "SIM_TEST"
        
    @pytest.mark.unit
    async def test_simulated_plotter_connect(self):
        """Test simulated plotter connection."""
        plotter = SimulatedPlotter()
        
        result = await plotter.connect()
        
        assert result is True
        assert plotter.is_connected
        
    @pytest.mark.unit
    async def test_simulated_plotter_send_command(self):
        """Test sending commands to simulated plotter."""
        plotter = SimulatedPlotter()
        await plotter.connect()
        
        commands = ["G28", "G1 X10 Y20 F1000", "M3 S255", "M5"]
        
        for command in commands:
            result = await plotter.send_command(command)
            assert result is True
            
        # Check command history
        assert len(plotter.command_history) == len(commands)
        for i, command in enumerate(commands):
            assert plotter.command_history[i]["command"] == command
            
    @pytest.mark.unit
    async def test_simulated_plotter_position_tracking(self):
        """Test position tracking in simulated plotter."""
        plotter = SimulatedPlotter()
        await plotter.connect()
        
        # Send movement commands
        await plotter.send_command("G1 X10 Y20 F1000")
        assert plotter.current_position == (10.0, 20.0, 0.0)
        
        await plotter.send_command("G1 X30 Y40 Z5 F1000")
        assert plotter.current_position == (30.0, 40.0, 5.0)
        
    @pytest.mark.unit
    async def test_simulated_plotter_pen_state(self):
        """Test pen state tracking in simulated plotter."""
        plotter = SimulatedPlotter()
        await plotter.connect()
        
        # Initially pen should be up
        assert not plotter.pen_down
        
        # Pen down command
        await plotter.send_command("M3 S255")
        assert plotter.pen_down
        
        # Pen up command
        await plotter.send_command("M5")
        assert not plotter.pen_down
        
    @pytest.mark.unit
    async def test_simulated_plotter_drawing_path(self):
        """Test drawing path recording."""
        plotter = SimulatedPlotter()
        await plotter.connect()
        
        # Move to start position
        await plotter.send_command("G1 X0 Y0 F1000")
        
        # Start drawing
        await plotter.send_command("M3 S255")
        await plotter.send_command("G1 X10 Y10 F1000")
        await plotter.send_command("G1 X20 Y0 F1000")
        
        # Stop drawing
        await plotter.send_command("M5")
        
        # Check drawing path
        drawing_segments = [seg for seg in plotter.drawing_path if seg["pen_down"]]
        assert len(drawing_segments) == 2  # Two line segments while pen was down
        
    @pytest.mark.unit
    async def test_simulated_plotter_statistics(self):
        """Test statistics collection in simulated plotter."""
        plotter = SimulatedPlotter()
        await plotter.connect()
        
        # Execute various commands
        commands = [
            "G28",  # Home
            "G1 X10 Y10 F1000",  # Move
            "M3 S255",  # Pen down
            "G1 X20 Y20 F1000",  # Draw
            "M5",  # Pen up
        ]
        
        for command in commands:
            await plotter.send_command(command)
            
        stats = plotter.get_statistics()
        
        assert stats["total_commands"] == len(commands)
        assert stats["move_commands"] == 2
        assert stats["pen_down_commands"] == 1
        assert stats["pen_up_commands"] == 1
        assert stats["total_distance"] > 0
        
    @pytest.mark.unit
    async def test_simulated_plotter_reset(self):
        """Test resetting simulated plotter state."""
        plotter = SimulatedPlotter()
        await plotter.connect()
        
        # Execute some commands
        await plotter.send_command("G1 X10 Y10 F1000")
        await plotter.send_command("M3 S255")
        
        # Reset state
        plotter.reset()
        
        assert plotter.current_position == (0.0, 0.0, 0.0)
        assert not plotter.pen_down
        assert len(plotter.command_history) == 0
        assert len(plotter.drawing_path) == 0
        
    @pytest.mark.unit
    async def test_simulated_plotter_context_manager(self):
        """Test simulated plotter as context manager."""
        async with SimulatedPlotter() as plotter:
            assert plotter.is_connected
            
            await plotter.send_command("G28")
            assert len(plotter.command_history) == 1
            
        # Should be disconnected after context
        assert not plotter.is_connected


class TestPlotterIntegration:
    """Test plotter integration scenarios."""
    
    @pytest.mark.unit
    async def test_multiple_plotters_concurrent(self):
        """Test using multiple plotters concurrently."""
        plotter1 = MockPlotter(port="PORT1")
        plotter2 = MockPlotter(port="PORT2")
        
        # Connect both plotters
        await asyncio.gather(
            plotter1.connect(),
            plotter2.connect()
        )
        
        assert plotter1.is_connected
        assert plotter2.is_connected
        
        # Send commands concurrently
        await asyncio.gather(
            plotter1.send_command("G1 X10 Y10"),
            plotter2.send_command("G1 X20 Y20")
        )
        
        assert "G1 X10 Y10" in plotter1.sent_commands
        assert "G1 X20 Y20" in plotter2.sent_commands
        
    @pytest.mark.unit
    async def test_plotter_error_recovery(self):
        """Test plotter error recovery scenarios."""
        plotter = MockPlotter(fail_on_command="FAIL")
        await plotter.connect()
        
        # Successful command
        result = await plotter.send_command("G28")
        assert result is True
        
        # Failed command
        result = await plotter.send_command("FAIL")
        assert result is False
        
        # Recovery with successful command
        result = await plotter.send_command("G1 X10 Y10")
        assert result is True
        
    @pytest.mark.unit
    async def test_plotter_command_queue(self):
        """Test queuing multiple commands."""
        plotter = MockPlotter()
        await plotter.connect()
        
        commands = [
            "G28",
            "G1 X10 Y10 F1000",
            "M3 S255",
            "G1 X20 Y20 F1000",
            "M5"
        ]
        
        # Send all commands
        results = await asyncio.gather(*[
            plotter.send_command(cmd) for cmd in commands
        ])
        
        # All should succeed
        assert all(results)
        assert len(plotter.sent_commands) == len(commands)
        
        # Commands should be in order
        for i, command in enumerate(commands):
            assert plotter.sent_commands[i] == command