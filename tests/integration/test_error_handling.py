"""
Integration tests for error handling and recovery mechanisms.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path

from promptplot.core.exceptions import (
    PromptPlotException, LLMException, PlotterException, 
    ValidationException, ConversionException
)
from promptplot.workflows.simple_batch import SimpleBatchWorkflow
from promptplot.workflows.file_plotting import FilePlottingWorkflow
from promptplot.llm.providers import LLMProvider
from promptplot.plotter.base import BasePlotter
from tests.utils.mocks import MockLLMProvider, MockPlotter, MockConfigManager


class TestLLMErrorHandling:
    """Test LLM error handling and recovery."""
    
    @pytest.mark.integration
    async def test_llm_timeout_recovery(self):
        """Test recovery from LLM timeout errors."""
        # Create provider that times out then succeeds
        llm_provider = MockLLMProvider()
        
        # Mock timeout on first call, success on second
        original_acomplete = llm_provider.acomplete
        call_count = 0
        
        async def timeout_then_success(prompt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise asyncio.TimeoutError("LLM request timeout")
            return await original_acomplete(prompt)
            
        llm_provider.acomplete = timeout_then_success
        
        plotter = MockPlotter()
        config = MockConfigManager()
        
        workflow = SimpleBatchWorkflow(
            llm_provider, plotter, config,
            max_retries=3
        )
        
        # Should recover from timeout
        result = await workflow.run("Draw a line")
        
        assert result is not None
        assert call_count == 2  # One timeout, one success
        
    @pytest.mark.integration
    async def test_llm_invalid_response_recovery(self):
        """Test recovery from invalid LLM responses."""
        invalid_responses = [
            "Not JSON at all",
            '{"incomplete": json',
            '{"command": "INVALID_COMMAND"}',
            '{"command": "G1", "x": "not_a_number"}',
            '{"command": "G1", "x": 10, "y": 20, "f": 1000}'  # Valid response
        ]
        
        llm_provider = MockLLMProvider(responses=invalid_responses)
        plotter = MockPlotter()
        config = MockConfigManager()
        
        workflow = SimpleBatchWorkflow(
            llm_provider, plotter, config,
            max_retries=5
        )
        
        # Should eventually succeed with valid response
        result = await workflow.run("Draw a line")
        
        assert result is not None
        assert llm_provider.call_count >= 4  # Multiple retries before success
        
    @pytest.mark.integration
    async def test_llm_connection_error_handling(self):
        """Test handling of LLM connection errors."""
        llm_provider = MockLLMProvider()
        
        # Mock connection error
        async def connection_error(prompt):
            raise ConnectionError("Unable to connect to LLM service")
            
        llm_provider.acomplete = connection_error
        
        plotter = MockPlotter()
        config = MockConfigManager()
        
        workflow = SimpleBatchWorkflow(llm_provider, plotter, config)
        
        # Should raise appropriate exception
        with pytest.raises(LLMException):
            await workflow.run("Draw a line")
            
    @pytest.mark.integration
    async def test_llm_rate_limit_handling(self):
        """Test handling of LLM rate limiting."""
        llm_provider = MockLLMProvider()
        
        call_count = 0
        
        async def rate_limit_then_success(prompt):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise Exception("Rate limit exceeded")
            return '{"command": "G1", "x": 10, "y": 20, "f": 1000}'
            
        llm_provider.acomplete = rate_limit_then_success
        
        plotter = MockPlotter()
        config = MockConfigManager()
        
        workflow = SimpleBatchWorkflow(
            llm_provider, plotter, config,
            max_retries=5,
            retry_delay=0.1  # Short delay for testing
        )
        
        # Should eventually succeed after rate limit clears
        result = await workflow.run("Draw a line")
        
        assert result is not None
        assert call_count == 3  # Two rate limits, then success


class TestPlotterErrorHandling:
    """Test plotter error handling and recovery."""
    
    @pytest.mark.integration
    async def test_plotter_connection_failure(self):
        """Test handling of plotter connection failures."""
        plotter = MockPlotter()
        
        # Mock connection failure
        async def connection_failure():
            raise ConnectionError("Unable to connect to plotter")
            
        plotter.connect = connection_failure
        
        llm_provider = MockLLMProvider()
        config = MockConfigManager()
        
        workflow = SimpleBatchWorkflow(llm_provider, plotter, config)
        
        # Should handle connection failure gracefully
        with pytest.raises(PlotterException):
            await workflow.run("Draw a line")
            
    @pytest.mark.integration
    async def test_plotter_command_failure_recovery(self):
        """Test recovery from individual command failures."""
        plotter = MockPlotter()
        
        # Mock intermittent command failures
        original_send = plotter.send_command
        call_count = 0
        
        async def intermittent_failure(command):
            nonlocal call_count
            call_count += 1
            # Fail every 3rd command
            if call_count % 3 == 0:
                return False
            return await original_send(command)
            
        plotter.send_command = intermittent_failure
        
        llm_provider = MockLLMProvider()
        config = MockConfigManager()
        
        workflow = SimpleBatchWorkflow(llm_provider, plotter, config)
        
        # Should handle individual command failures
        result = await workflow.run("Draw multiple lines")
        
        assert result is not None
        # Some commands may have failed, but workflow should complete
        
    @pytest.mark.integration
    async def test_plotter_disconnection_recovery(self):
        """Test recovery from plotter disconnection."""
        plotter = MockPlotter()
        
        # Mock disconnection after some commands
        command_count = 0
        
        async def disconnect_after_commands(command):
            nonlocal command_count
            command_count += 1
            if command_count == 3:
                plotter.is_connected = False
                raise ConnectionError("Plotter disconnected")
            return True
            
        plotter.send_command = disconnect_after_commands
        
        llm_provider = MockLLMProvider()
        config = MockConfigManager()
        
        workflow = SimpleBatchWorkflow(
            llm_provider, plotter, config,
            auto_reconnect=True
        )
        
        # Should attempt to reconnect and continue
        result = await workflow.run("Draw a complex shape")
        
        assert result is not None
        
    @pytest.mark.integration
    async def test_plotter_hardware_error_simulation(self):
        """Test handling of simulated hardware errors."""
        plotter = MockPlotter()
        
        # Simulate various hardware errors
        error_responses = [
            "Error: Limit switch triggered",
            "Error: Motor stall detected", 
            "Error: Temperature too high",
            "ok"  # Recovery
        ]
        
        error_index = 0
        
        async def hardware_errors(command):
            nonlocal error_index
            if error_index < len(error_responses) - 1:
                error_msg = error_responses[error_index]
                error_index += 1
                if "Error:" in error_msg:
                    raise PlotterException(error_msg)
            return True
            
        plotter.send_command = hardware_errors
        
        llm_provider = MockLLMProvider()
        config = MockConfigManager()
        
        workflow = SimpleBatchWorkflow(
            llm_provider, plotter, config,
            max_retries=5
        )
        
        # Should handle hardware errors and eventually succeed
        result = await workflow.run("Draw a test pattern")
        
        assert result is not None


class TestValidationErrorHandling:
    """Test validation error handling and recovery."""
    
    @pytest.mark.integration
    async def test_gcode_validation_errors(self):
        """Test handling of G-code validation errors."""
        # Create responses with validation issues
        invalid_responses = [
            '{"command": "", "x": 10, "y": 20}',  # Empty command
            '{"command": "G1", "x": "invalid", "y": 20}',  # Invalid coordinate
            '{"command": "G1", "f": -1000}',  # Invalid feed rate
            '{"command": "G1", "x": 10, "y": 20, "f": 1000}'  # Valid
        ]
        
        llm_provider = MockLLMProvider(responses=invalid_responses)
        plotter = MockPlotter()
        config = MockConfigManager()
        
        workflow = SimpleBatchWorkflow(
            llm_provider, plotter, config,
            max_retries=5,
            strict_validation=True
        )
        
        # Should retry until valid G-code is generated
        result = await workflow.run("Draw a line")
        
        assert result is not None
        assert llm_provider.call_count >= 3  # Multiple validation failures
        
    @pytest.mark.integration
    async def test_coordinate_bounds_validation(self):
        """Test handling of coordinate bounds validation."""
        # Create responses with out-of-bounds coordinates
        out_of_bounds_responses = [
            '{"command": "G1", "x": 1000, "y": 1000, "f": 1000}',  # Too large
            '{"command": "G1", "x": -100, "y": -100, "f": 1000}',  # Negative
            '{"command": "G1", "x": 10, "y": 20, "f": 1000}'  # Valid
        ]
        
        llm_provider = MockLLMProvider(responses=out_of_bounds_responses)
        plotter = MockPlotter()
        config = MockConfigManager({
            "plotter": {
                "max_x": 100,
                "max_y": 100,
                "min_x": 0,
                "min_y": 0
            }
        })
        
        workflow = SimpleBatchWorkflow(
            llm_provider, plotter, config,
            validate_bounds=True
        )
        
        # Should reject out-of-bounds coordinates
        result = await workflow.run("Draw within bounds")
        
        assert result is not None
        # Should have valid coordinates within bounds
        for command in result.commands:
            if command.x is not None:
                assert 0 <= command.x <= 100
            if command.y is not None:
                assert 0 <= command.y <= 100


class TestFileConversionErrorHandling:
    """Test file conversion error handling."""
    
    @pytest.mark.integration
    async def test_invalid_file_format_handling(self, temp_dir):
        """Test handling of invalid file formats."""
        # Create file with unsupported format
        invalid_file = temp_dir / "test.xyz"
        invalid_file.write_text("Invalid file content")
        
        plotter = MockPlotter()
        config = MockConfigManager()
        
        workflow = FilePlottingWorkflow(plotter, config)
        
        # Should raise appropriate exception
        with pytest.raises(ConversionException):
            await workflow.plot_file(invalid_file)
            
    @pytest.mark.integration
    async def test_corrupted_file_handling(self, temp_dir):
        """Test handling of corrupted files."""
        # Create corrupted SVG file
        corrupted_svg = temp_dir / "corrupted.svg"
        corrupted_svg.write_text("<?xml version='1.0'?><svg><rect x='10' y='10'")  # Incomplete
        
        plotter = MockPlotter()
        config = MockConfigManager()
        
        workflow = FilePlottingWorkflow(plotter, config)
        
        # Should handle corrupted file gracefully
        with pytest.raises(ConversionException):
            await workflow.plot_file(corrupted_svg)
            
    @pytest.mark.integration
    async def test_missing_file_handling(self, temp_dir):
        """Test handling of missing files."""
        missing_file = temp_dir / "nonexistent.svg"
        
        plotter = MockPlotter()
        config = MockConfigManager()
        
        workflow = FilePlottingWorkflow(plotter, config)
        
        # Should raise appropriate exception
        with pytest.raises(ConversionException):
            await workflow.plot_file(missing_file)
            
    @pytest.mark.integration
    async def test_large_file_handling(self, temp_dir):
        """Test handling of very large files."""
        # Create large SVG file
        large_svg = temp_dir / "large.svg"
        svg_content = '<?xml version="1.0"?><svg width="1000" height="1000">'
        
        # Add many elements
        for i in range(1000):
            svg_content += f'<rect x="{i}" y="{i}" width="1" height="1"/>'
            
        svg_content += '</svg>'
        large_svg.write_text(svg_content)
        
        plotter = MockPlotter()
        config = MockConfigManager()
        
        workflow = FilePlottingWorkflow(plotter, config)
        
        # Should handle large file (may be slow)
        result = await workflow.plot_file(large_svg)
        
        assert result is not None
        # Should have many commands
        assert len(result.commands) > 100


class TestConcurrentErrorHandling:
    """Test error handling in concurrent scenarios."""
    
    @pytest.mark.integration
    async def test_concurrent_workflow_errors(self):
        """Test error handling when multiple workflows fail concurrently."""
        # Create workflows that will fail
        failing_workflows = []
        
        for i in range(3):
            llm_provider = MockLLMProvider()
            
            # Make each provider fail differently
            if i == 0:
                llm_provider.acomplete = AsyncMock(side_effect=TimeoutError())
            elif i == 1:
                llm_provider.acomplete = AsyncMock(side_effect=ConnectionError())
            else:
                llm_provider.acomplete = AsyncMock(side_effect=ValueError())
                
            plotter = MockPlotter(port=f"PORT_{i}")
            config = MockConfigManager()
            
            workflow = SimpleBatchWorkflow(llm_provider, plotter, config)
            failing_workflows.append(workflow)
            
        # Run all workflows concurrently
        tasks = [
            workflow.run(f"Draw shape {i}")
            for i, workflow in enumerate(failing_workflows)
        ]
        
        # Should handle all failures gracefully
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All should be exceptions
        for result in results:
            assert isinstance(result, Exception)
            
    @pytest.mark.integration
    async def test_resource_cleanup_on_errors(self):
        """Test that resources are properly cleaned up on errors."""
        llm_provider = MockLLMProvider()
        plotter = MockPlotter()
        config = MockConfigManager()
        
        # Mock plotter to fail after connection
        async def fail_after_connect():
            await asyncio.sleep(0.01)  # Simulate connection time
            raise PlotterException("Connection lost")
            
        plotter.send_command = AsyncMock(side_effect=fail_after_connect)
        
        workflow = SimpleBatchWorkflow(llm_provider, plotter, config)
        
        # Should clean up resources even on failure
        with pytest.raises(PlotterException):
            await workflow.run("Draw something")
            
        # Plotter should be properly disconnected
        assert not plotter.is_connected
        
    @pytest.mark.integration
    async def test_error_propagation_chain(self):
        """Test error propagation through workflow chain."""
        # Create chain of workflows where errors propagate
        llm_provider1 = MockLLMProvider()
        llm_provider2 = MockLLMProvider()
        
        plotter1 = MockPlotter(port="PORT1")
        plotter2 = MockPlotter(port="PORT2")
        
        config = MockConfigManager()
        
        workflow1 = SimpleBatchWorkflow(llm_provider1, plotter1, config)
        workflow2 = SimpleBatchWorkflow(llm_provider2, plotter2, config)
        
        # Make first workflow fail
        llm_provider1.acomplete = AsyncMock(side_effect=LLMException("LLM Error"))
        
        # Chain workflows
        try:
            result1 = await workflow1.run("Draw first shape")
        except LLMException as e:
            # Second workflow should handle the error from first
            result2 = await workflow2.run(f"Handle error: {str(e)}")
            assert result2 is not None
            
    @pytest.mark.integration
    async def test_graceful_degradation(self):
        """Test graceful degradation when components fail."""
        llm_provider = MockLLMProvider()
        plotter = MockPlotter()
        config = MockConfigManager()
        
        # Configure for graceful degradation
        workflow = SimpleBatchWorkflow(
            llm_provider, plotter, config,
            fallback_mode=True,
            allow_partial_results=True
        )
        
        # Make plotter fail intermittently
        success_count = 0
        
        async def partial_failure(command):
            nonlocal success_count
            success_count += 1
            # Succeed 70% of the time
            return success_count % 10 < 7
            
        plotter.send_command = partial_failure
        
        # Should complete with partial results
        result = await workflow.run("Draw complex pattern")
        
        assert result is not None
        # Should have some commands even with failures
        assert len(result.commands) > 0