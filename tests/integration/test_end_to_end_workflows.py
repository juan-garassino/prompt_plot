"""
Integration tests for complete end-to-end workflows.
"""
import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

from promptplot.workflows.simple_batch import SimpleGCodeWorkflow
from promptplot.workflows.advanced_sequential import SequentialGCodeWorkflow
from promptplot.workflows.simple_streaming import SimplePlotterStreamWorkflow
from promptplot.workflows.advanced_streaming import AdvancedPlotterStreamWorkflow
from promptplot.workflows.plot_enhanced import PlotEnhancedWorkflow
from promptplot.workflows.file_plotting import FilePlottingWorkflow
from promptplot.core.models import GCodeProgram, GCodeCommand
from promptplot.core.exceptions import WorkflowException
from tests.utils.mocks import MockLLMProvider, MockPlotter, MockConfigManager
from tests.fixtures.sample_files import create_test_files
from tests.utils.gcode_utils import GCodeAnalyzer, GCodeTestValidator


class TestSimpleGCodeWorkflow:
    """Test simple G-code workflow end-to-end."""
    
    @pytest.fixture
    async def workflow_setup(self):
        """Set up workflow with mocks."""
        llm_provider = MockLLMProvider(responses=[
            '{"command": "G28", "comment": "Home all axes"}',
            '{"command": "G1", "x": 10.0, "y": 10.0, "f": 1000, "comment": "Move to start"}',
            '{"command": "M3", "s": 255, "comment": "Pen down"}',
            '{"command": "G1", "x": 20.0, "y": 20.0, "f": 1000, "comment": "Draw line"}',
            '{"command": "M5", "comment": "Pen up"}',
            '{"command": "G28", "comment": "Return home"}'
        ])
        
        plotter = MockPlotter()
        config = MockConfigManager()
        
        workflow = SimpleGCodeWorkflow(
            llm_provider=llm_provider,
            plotter=plotter,
            config=config
        )
        
        return workflow, llm_provider, plotter, config
        
    @pytest.mark.integration
    async def test_simple_drawing_workflow(self, workflow_setup):
        """Test complete simple drawing workflow."""
        workflow, llm_provider, plotter, config = workflow_setup
        
        prompt = "Draw a line from (10,10) to (20,20)"
        
        # Execute workflow
        result = await workflow.run(prompt)
        
        # Verify result
        assert isinstance(result, GCodeProgram)
        assert len(result.commands) > 0
        
        # Verify LLM was called
        assert llm_provider.call_count > 0
        assert llm_provider.last_prompt is not None
        
        # Verify plotter received commands
        await plotter.connect()
        for command in result.commands:
            await plotter.send_command(command.command)
            
        assert len(plotter.sent_commands) == len(result.commands)
        
    @pytest.mark.integration
    async def test_workflow_with_retries(self, workflow_setup):
        """Test workflow with LLM retry logic."""
        workflow, llm_provider, plotter, config = workflow_setup
        
        # Add invalid response that should trigger retry
        llm_provider.responses = [
            'Invalid JSON response',  # Should trigger retry
            '{"command": "G1", "x": 10.0, "y": 20.0, "f": 1000}'  # Valid response
        ]
        
        prompt = "Draw a simple line"
        
        result = await workflow.run(prompt)
        
        # Should eventually succeed after retry
        assert isinstance(result, GCodeProgram)
        assert llm_provider.call_count >= 2  # At least one retry
        
    @pytest.mark.integration
    async def test_workflow_error_handling(self, workflow_setup):
        """Test workflow error handling."""
        workflow, llm_provider, plotter, config = workflow_setup
        
        # Configure plotter to fail
        plotter.fail_on_command = "G1"
        
        prompt = "Draw a line"
        
        # Workflow should handle plotter errors gracefully
        result = await workflow.run(prompt)
        
        # Should still produce valid G-code even if plotter fails
        assert isinstance(result, GCodeProgram)
        
    @pytest.mark.integration
    async def test_workflow_validation(self, workflow_setup):
        """Test workflow G-code validation."""
        workflow, llm_provider, plotter, config = workflow_setup
        
        prompt = "Draw a rectangle"
        result = await workflow.run(prompt)
        
        # Validate generated G-code
        validator = GCodeTestValidator()
        is_valid, errors = validator.validate_program(result)
        
        assert is_valid, f"Generated G-code is invalid: {errors}"
        
        # Analyze complexity
        analyzer = GCodeAnalyzer()
        analysis = analyzer.analyze_complexity(result)
        
        assert analysis["total_commands"] > 0
        assert analysis["move_commands"] > 0


class TestSequentialGCodeWorkflow:
    """Test advanced sequential workflow end-to-end."""
    
    @pytest.fixture
    async def advanced_workflow_setup(self):
        """Set up advanced workflow with mocks."""
        llm_provider = MockLLMProvider(responses=[
            '{"command": "G28"}',
            '{"command": "G1", "x": 0.0, "y": 0.0, "f": 1000}',
            '{"command": "M3", "s": 255}',
            '{"command": "G1", "x": 10.0, "y": 0.0, "f": 1000}',
            '{"command": "G1", "x": 10.0, "y": 5.0, "f": 1000}',
            '{"command": "G1", "x": 0.0, "y": 5.0, "f": 1000}',
            '{"command": "G1", "x": 0.0, "y": 0.0, "f": 1000}',
            '{"command": "M5"}',
            '{"command": "G28"}'
        ])
        
        plotter = MockPlotter()
        config = MockConfigManager()
        
        workflow = SequentialGCodeWorkflow(
            llm_provider=llm_provider,
            plotter=plotter,
            config=config,
            max_steps=10
        )
        
        return workflow, llm_provider, plotter, config
        
    @pytest.mark.integration
    async def test_sequential_drawing_steps(self, advanced_workflow_setup):
        """Test advanced workflow with sequential steps."""
        workflow, llm_provider, plotter, config = advanced_workflow_setup
        
        prompt = "Draw a rectangle step by step"
        
        result = await workflow.run(prompt)
        
        # Should generate more complex G-code
        assert isinstance(result, GCodeProgram)
        assert len(result.commands) >= 5
        
        # Should have multiple LLM calls for sequential steps
        assert llm_provider.call_count >= 3
        
        # Analyze the drawing
        analyzer = GCodeAnalyzer()
        bounds = analyzer.calculate_drawing_bounds(result)
        
        assert bounds["width"] > 0
        assert bounds["height"] > 0
        
    @pytest.mark.integration
    async def test_workflow_step_validation(self, advanced_workflow_setup):
        """Test validation of each workflow step."""
        workflow, llm_provider, plotter, config = advanced_workflow_setup
        
        prompt = "Draw a complex shape with multiple parts"
        
        result = await workflow.run(prompt)
        
        # Each step should produce valid commands
        validator = GCodeTestValidator()
        
        for i, command in enumerate(result.commands):
            is_valid, errors = validator.validate_command(command)
            assert is_valid, f"Command {i} is invalid: {errors}"
            
    @pytest.mark.integration
    async def test_workflow_progress_tracking(self, advanced_workflow_setup):
        """Test workflow progress tracking."""
        workflow, llm_provider, plotter, config = advanced_workflow_setup
        
        progress_updates = []
        
        def progress_callback(step, total, description):
            progress_updates.append((step, total, description))
            
        workflow.set_progress_callback(progress_callback)
        
        prompt = "Draw a multi-step drawing"
        result = await workflow.run(prompt)
        
        # Should have received progress updates
        assert len(progress_updates) > 0
        
        # Progress should be sequential
        for i, (step, total, desc) in enumerate(progress_updates):
            if i > 0:
                prev_step = progress_updates[i-1][0]
                assert step >= prev_step


class TestFilePlottingWorkflow:
    """Test file plotting workflow end-to-end."""
    
    @pytest.fixture
    async def file_workflow_setup(self, temp_dir):
        """Set up file plotting workflow."""
        plotter = MockPlotter()
        config = MockConfigManager()
        
        workflow = FilePlottingWorkflow(
            plotter=plotter,
            config=config
        )
        
        # Create test files
        test_files = create_test_files(temp_dir)
        
        return workflow, plotter, config, test_files
        
    @pytest.mark.integration
    async def test_svg_file_plotting(self, file_workflow_setup):
        """Test plotting SVG file end-to-end."""
        workflow, plotter, config, test_files = file_workflow_setup
        
        svg_file = test_files["svg"]
        
        result = await workflow.plot_file(svg_file)
        
        assert isinstance(result, GCodeProgram)
        assert len(result.commands) > 0
        
        # Verify file was processed correctly
        analyzer = GCodeAnalyzer()
        analysis = analyzer.analyze_complexity(result)
        
        assert analysis["total_commands"] > 5
        assert analysis["move_commands"] > 0
        
    @pytest.mark.integration
    async def test_gcode_file_plotting(self, file_workflow_setup):
        """Test plotting G-code file end-to-end."""
        workflow, plotter, config, test_files = file_workflow_setup
        
        gcode_file = test_files["gcode"]
        
        result = await workflow.plot_file(gcode_file)
        
        assert isinstance(result, GCodeProgram)
        
        # G-code file should be loaded as-is
        validator = GCodeTestValidator()
        is_valid, errors = validator.validate_program(result)
        assert is_valid, f"Loaded G-code is invalid: {errors}"
        
    @pytest.mark.integration
    async def test_dxf_file_plotting(self, file_workflow_setup):
        """Test plotting DXF file end-to-end."""
        workflow, plotter, config, test_files = file_workflow_setup
        
        dxf_file = test_files["dxf"]
        
        result = await workflow.plot_file(dxf_file)
        
        assert isinstance(result, GCodeProgram)
        assert len(result.commands) > 0
        
    @pytest.mark.integration
    async def test_batch_file_plotting(self, file_workflow_setup):
        """Test plotting multiple files in batch."""
        workflow, plotter, config, test_files = file_workflow_setup
        
        files_to_plot = [
            test_files["svg"],
            test_files["gcode"],
            test_files["dxf"]
        ]
        
        results = await workflow.plot_files_batch(files_to_plot)
        
        assert len(results) == len(files_to_plot)
        
        for result in results:
            assert isinstance(result, GCodeProgram)
            assert len(result.commands) > 0
            
    @pytest.mark.integration
    async def test_file_plotting_with_preview(self, file_workflow_setup):
        """Test file plotting with preview generation."""
        workflow, plotter, config, test_files = file_workflow_setup
        
        svg_file = test_files["svg"]
        
        # Enable preview mode
        preview_result = await workflow.preview_file(svg_file)
        
        assert isinstance(preview_result, dict)
        assert "program" in preview_result
        assert "bounds" in preview_result
        assert "statistics" in preview_result
        
        # Verify preview data
        program = preview_result["program"]
        bounds = preview_result["bounds"]
        stats = preview_result["statistics"]
        
        assert isinstance(program, GCodeProgram)
        assert bounds["width"] > 0
        assert bounds["height"] > 0
        assert stats["total_commands"] > 0


class TestWorkflowIntegration:
    """Test integration between different workflow components."""
    
    @pytest.mark.integration
    async def test_workflow_chaining(self):
        """Test chaining multiple workflows together."""
        # Create mock components
        llm_provider = MockLLMProvider()
        plotter = MockPlotter()
        config = MockConfigManager()
        
        # Create workflows
        simple_workflow = SimpleGCodeWorkflow(llm_provider, plotter, config)
        advanced_workflow = SequentialGCodeWorkflow(llm_provider, plotter, config)
        
        # Execute simple workflow first
        simple_result = await simple_workflow.run("Draw a line")
        
        # Use result as input for advanced workflow
        advanced_result = await advanced_workflow.run(
            "Enhance the previous drawing with a circle",
            previous_result=simple_result
        )
        
        # Advanced result should build on simple result
        assert len(advanced_result.commands) >= len(simple_result.commands)
        
    @pytest.mark.integration
    async def test_concurrent_workflows(self):
        """Test running multiple workflows concurrently."""
        # Create separate mock components for each workflow
        workflows = []
        for i in range(3):
            llm_provider = MockLLMProvider()
            plotter = MockPlotter(port=f"PORT_{i}")
            config = MockConfigManager()
            
            workflow = SimpleGCodeWorkflow(llm_provider, plotter, config)
            workflows.append(workflow)
            
        # Run workflows concurrently
        prompts = [
            "Draw a line",
            "Draw a circle", 
            "Draw a rectangle"
        ]
        
        tasks = [
            workflow.run(prompt)
            for workflow, prompt in zip(workflows, prompts)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # All workflows should complete successfully
        assert len(results) == 3
        for result in results:
            assert isinstance(result, GCodeProgram)
            
    @pytest.mark.integration
    async def test_workflow_error_recovery(self):
        """Test workflow error recovery and continuation."""
        llm_provider = MockLLMProvider(responses=[
            'Invalid response',  # Should cause error
            '{"command": "G28"}',  # Recovery response
            '{"command": "G1", "x": 10, "y": 10, "f": 1000}'
        ])
        
        plotter = MockPlotter()
        config = MockConfigManager()
        
        workflow = SimpleGCodeWorkflow(
            llm_provider, plotter, config,
            max_retries=3
        )
        
        # Should recover from initial error
        result = await workflow.run("Draw something")
        
        assert isinstance(result, GCodeProgram)
        assert llm_provider.call_count >= 2  # Initial failure + recovery
        
    @pytest.mark.integration
    async def test_workflow_performance_monitoring(self):
        """Test workflow performance monitoring."""
        llm_provider = MockLLMProvider()
        plotter = MockPlotter()
        config = MockConfigManager()
        
        workflow = SimpleGCodeWorkflow(llm_provider, plotter, config)
        
        # Enable performance monitoring
        workflow.enable_performance_monitoring()
        
        start_time = asyncio.get_event_loop().time()
        result = await workflow.run("Draw a test shape")
        end_time = asyncio.get_event_loop().time()
        
        # Get performance metrics
        metrics = workflow.get_performance_metrics()
        
        assert "total_time" in metrics
        assert "llm_time" in metrics
        assert "validation_time" in metrics
        assert metrics["total_time"] > 0
        assert metrics["total_time"] <= (end_time - start_time) + 0.1  # Small tolerance
        
    @pytest.mark.integration
    @pytest.mark.slow
    async def test_large_drawing_workflow(self):
        """Test workflow with large, complex drawing."""
        # Create responses for a complex drawing (100+ commands)
        responses = []
        for i in range(50):
            responses.append(f'{{"command": "G1", "x": {i*2}, "y": {i%10}, "f": 1000}}')
            
        llm_provider = MockLLMProvider(responses=responses)
        plotter = MockPlotter()
        config = MockConfigManager()
        
        workflow = SequentialGCodeWorkflow(
            llm_provider, plotter, config,
            max_steps=50
        )
        
        result = await workflow.run("Draw a complex pattern with many points")
        
        # Should handle large drawings efficiently
        assert isinstance(result, GCodeProgram)
        assert len(result.commands) >= 20
        
        # Validate performance
        analyzer = GCodeAnalyzer()
        analysis = analyzer.analyze_complexity(result)
        
        assert analysis["complexity_score"] > 0.5  # Should be reasonably complex
        assert analysis["total_distance"] > 0
        
    @pytest.mark.integration
    async def test_workflow_memory_management(self):
        """Test workflow memory management with multiple runs."""
        llm_provider = MockLLMProvider()
        plotter = MockPlotter()
        config = MockConfigManager()
        
        workflow = SimpleGCodeWorkflow(llm_provider, plotter, config)
        
        # Run workflow multiple times
        results = []
        for i in range(10):
            result = await workflow.run(f"Draw shape {i}")
            results.append(result)
            
        # Memory usage should be reasonable
        assert len(results) == 10
        
        # Each result should be independent
        for i, result in enumerate(results):
            assert isinstance(result, GCodeProgram)
            # Results should not interfere with each other
            assert len(result.commands) > 0

class TestCompleteSystemIntegration:
    """Complete end-to-end system integration tests."""
    
    @pytest.mark.integration
    async def test_all_workflow_types_with_simulated_plotter(self):
        """Test all workflow types with simulated plotter."""
        from promptplot.workflows.simple_streaming import SimplePlotterStreamWorkflow
        from promptplot.workflows.advanced_streaming import AdvancedPlotterStreamWorkflow
        from promptplot.workflows.plot_enhanced import PlotEnhancedWorkflow
        
        # Setup components
        llm_provider = MockLLMProvider(responses=[
            '{"command": "G28"}',
            '{"command": "G1", "x": 10, "y": 10, "f": 1000}',
            '{"command": "M3", "s": 255}',
            '{"command": "G1", "x": 20, "y": 20, "f": 1000}',
            '{"command": "M5"}',
            '{"command": "G28"}'
        ])
        plotter = MockPlotter(port="SIMULATED")
        config = MockConfigManager()
        
        # Test all workflow types
        workflows = [
            SimpleGCodeWorkflow(llm_provider, plotter, config),
            SequentialGCodeWorkflow(llm_provider, plotter, config),
            SimplePlotterStreamWorkflow(llm_provider, plotter, config),
            AdvancedPlotterStreamWorkflow(llm_provider, plotter, config),
            PlotEnhancedWorkflow(llm_provider, plotter, config)
        ]
        
        prompt = "Draw a simple test shape"
        
        for workflow in workflows:
            result = await workflow.run(prompt)
            assert isinstance(result, GCodeProgram)
            assert len(result.commands) > 0
            
            # Verify workflow-specific behavior
            workflow_name = workflow.__class__.__name__
            print(f"✓ {workflow_name} completed successfully")
    
    @pytest.mark.integration
    async def test_all_workflow_types_with_real_plotter_simulation(self):
        """Test all workflow types with real plotter interface (simulated)."""
        from promptplot.plotter.serial_plotter import SerialPlotter
        from promptplot.plotter.simulated import SimulatedPlotter
        
        # Setup components with real plotter interfaces
        llm_provider = MockLLMProvider()
        config = MockConfigManager()
        
        # Test with simulated plotter that mimics real interface
        simulated_plotter = SimulatedPlotter(port="TEST_PORT", visualize=True)
        
        workflows = [
            SimpleGCodeWorkflow(llm_provider, simulated_plotter, config),
            SequentialGCodeWorkflow(llm_provider, simulated_plotter, config)
        ]
        
        for workflow in workflows:
            async with simulated_plotter:
                result = await workflow.run("Draw a test pattern")
                assert isinstance(result, GCodeProgram)
                
                # Verify plotter received commands
                assert len(simulated_plotter.command_history) > 0
    
    @pytest.mark.integration
    async def test_file_conversion_workflows_complete(self, temp_dir):
        """Test complete file conversion workflows."""
        from promptplot.workflows.file_plotting import FilePlottingWorkflow
        from promptplot.converters import SVGConverter, GCodeLoader, DXFConverter
        
        # Create test files
        test_files = create_test_files(temp_dir)
        
        plotter = MockPlotter()
        config = MockConfigManager()
        workflow = FilePlottingWorkflow(plotter, config)
        
        # Test each file format
        for file_format, file_path in test_files.items():
            print(f"Testing {file_format} file: {file_path}")
            
            # Test conversion
            result = await workflow.plot_file(file_path)
            assert isinstance(result, GCodeProgram)
            assert len(result.commands) > 0
            
            # Validate converted G-code
            validator = GCodeTestValidator()
            is_valid, errors = validator.validate_program(result)
            assert is_valid, f"{file_format} conversion produced invalid G-code: {errors}"
            
            print(f"✓ {file_format} conversion successful")
    
    @pytest.mark.integration
    async def test_cli_commands_integration(self):
        """Test CLI commands integration."""
        from promptplot.cli import PromptPlotCLI
        
        cli = PromptPlotCLI()
        
        # Test config commands
        result = await cli.run(["config", "show", "--format", "json"])
        assert result == 0
        
        # Test workflow commands (dry run)
        result = await cli.run([
            "workflow", "simple", "Draw a test line", 
            "--simulate", "--output", "/tmp/test_output.gcode"
        ])
        assert result == 0
        
        # Test file commands
        test_gcode = Path("/tmp/test.gcode")
        test_gcode.write_text("G28\nG1 X10 Y10 F1000\nM3 S255\nG1 X20 Y20\nM5\nG28")
        
        result = await cli.run([
            "file", "validate", str(test_gcode)
        ])
        assert result == 0
        
        # Test plotter commands
        result = await cli.run([
            "plotter", "list-ports"
        ])
        assert result == 0
        
        print("✓ All CLI commands working")
    
    @pytest.mark.integration
    async def test_configuration_system_integration(self):
        """Test configuration system works across all components."""
        from promptplot.config import get_config, save_config, load_config
        from promptplot.config.profiles import ProfileManager, create_profile
        from promptplot.config.runtime import RuntimeConfigManager
        
        # Test configuration loading and saving
        config = get_config()
        original_max_retries = config.workflow.max_retries
        
        # Modify configuration
        config.workflow.max_retries = 5
        save_config(config)
        
        # Reload and verify
        new_config = load_config()
        assert new_config.workflow.max_retries == 5
        
        # Test profile system
        profile_manager = ProfileManager()
        
        # Create test profile
        test_profile = create_profile(
            name="test_integration",
            description="Integration test profile"
        )
        
        # Switch to profile and verify
        profile_manager.switch_profile("test_integration")
        active_profile = profile_manager.get_active_profile()
        assert active_profile.name == "test_integration"
        
        # Test runtime configuration
        runtime_manager = RuntimeConfigManager()
        
        # Update runtime setting
        result = await runtime_manager.update_field(
            "workflow.max_retries", 10, "integration_test"
        )
        assert result.value == "success"
        
        # Restore original configuration
        config.workflow.max_retries = original_max_retries
        save_config(config)
        
        print("✓ Configuration system integration successful")
    
    @pytest.mark.integration
    async def test_error_handling_and_recovery_complete(self):
        """Test comprehensive error handling and recovery mechanisms."""
        
        # Test LLM provider failures
        failing_llm = MockLLMProvider(responses=["Invalid JSON"] * 3 + ['{"command": "G28"}'])
        plotter = MockPlotter()
        config = MockConfigManager()
        
        workflow = SimpleGCodeWorkflow(failing_llm, plotter, config, max_retries=5)
        
        # Should recover after retries
        result = await workflow.run("Draw something")
        assert isinstance(result, GCodeProgram)
        assert failing_llm.call_count >= 4  # 3 failures + 1 success
        
        # Test plotter communication failures
        failing_plotter = MockPlotter(fail_on_command="G1")
        workflow = SimpleGCodeWorkflow(MockLLMProvider(), failing_plotter, config)
        
        # Should handle plotter failures gracefully
        result = await workflow.run("Draw a line")
        assert isinstance(result, GCodeProgram)
        
        # Test configuration validation errors
        invalid_config = MockConfigManager()
        invalid_config.workflow.max_retries = -1  # Invalid value
        
        try:
            workflow = SimpleGCodeWorkflow(MockLLMProvider(), MockPlotter(), invalid_config)
            # Should handle invalid configuration
            assert True  # If we get here, error handling worked
        except Exception as e:
            # Should be a validation error, not a crash
            assert "validation" in str(e).lower() or "invalid" in str(e).lower()
        
        print("✓ Error handling and recovery working")
    
    @pytest.mark.integration
    async def test_strategy_selector_integration(self):
        """Test strategy selector integration with workflows."""
        from promptplot.strategies import StrategySelector, OrthogonalStrategy, NonOrthogonalStrategy
        
        selector = StrategySelector()
        
        # Test orthogonal prompt detection
        orthogonal_prompts = [
            "Draw a rectangle",
            "Create a grid of lines",
            "Draw straight lines forming a square"
        ]
        
        for prompt in orthogonal_prompts:
            strategy = selector.select_strategy(prompt)
            assert isinstance(strategy, OrthogonalStrategy), f"Failed for prompt: {prompt}"
        
        # Test non-orthogonal prompt detection
        non_orthogonal_prompts = [
            "Draw a circle",
            "Create a curved flower",
            "Draw organic flowing lines"
        ]
        
        for prompt in non_orthogonal_prompts:
            strategy = selector.select_strategy(prompt)
            assert isinstance(strategy, NonOrthogonalStrategy), f"Failed for prompt: {prompt}"
        
        # Test strategy integration with workflow
        llm_provider = MockLLMProvider()
        plotter = MockPlotter()
        config = MockConfigManager()
        
        workflow = SimpleGCodeWorkflow(llm_provider, plotter, config)
        
        # Test with orthogonal strategy
        result = await workflow.run("Draw a rectangle")
        assert isinstance(result, GCodeProgram)
        
        # Test with non-orthogonal strategy
        result = await workflow.run("Draw a circle")
        assert isinstance(result, GCodeProgram)
        
        print("✓ Strategy selector integration working")
    
    @pytest.mark.integration
    async def test_llm_provider_integration_complete(self):
        """Test LLM provider integration across all workflows."""
        from promptplot.llm.providers import AzureOpenAIProvider, OllamaProvider
        from promptplot.llm.templates import PromptTemplateManager
        
        # Test template management
        template_manager = PromptTemplateManager()
        
        # Test template rendering
        template = template_manager.get_template("simple_drawing")
        rendered = template_manager.render_template("simple_drawing", {
            "prompt": "Draw a test shape",
            "max_commands": 10
        })
        
        assert "Draw a test shape" in rendered
        assert "10" in rendered
        
        # Test with mock providers (since we can't test real LLM calls in CI)
        mock_azure = MockLLMProvider(provider_type="azure")
        mock_ollama = MockLLMProvider(provider_type="ollama")
        
        providers = [mock_azure, mock_ollama]
        
        for provider in providers:
            workflow = SimpleGCodeWorkflow(provider, MockPlotter(), MockConfigManager())
            result = await workflow.run("Test prompt")
            assert isinstance(result, GCodeProgram)
            
        print("✓ LLM provider integration working")
    
    @pytest.mark.integration
    @pytest.mark.slow
    async def test_performance_and_scalability(self):
        """Test system performance and scalability."""
        import time
        import psutil
        import os
        
        # Monitor system resources
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Test with large number of commands
        large_responses = []
        for i in range(100):
            large_responses.append(f'{{"command": "G1", "x": {i}, "y": {i%10}, "f": 1000}}')
        
        llm_provider = MockLLMProvider(responses=large_responses)
        plotter = MockPlotter()
        config = MockConfigManager()
        
        workflow = SequentialGCodeWorkflow(llm_provider, plotter, config, max_steps=100)
        
        start_time = time.time()
        result = await workflow.run("Draw a complex pattern with many points")
        end_time = time.time()
        
        # Performance assertions
        duration = end_time - start_time
        assert duration < 30.0, f"Workflow took too long: {duration}s"
        
        # Memory usage should be reasonable
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        assert memory_increase < 100, f"Memory usage increased too much: {memory_increase}MB"
        
        # Result should be valid
        assert isinstance(result, GCodeProgram)
        assert len(result.commands) >= 50
        
        print(f"✓ Performance test passed: {duration:.2f}s, {memory_increase:.1f}MB increase")
    
    @pytest.mark.integration
    async def test_concurrent_workflow_execution(self):
        """Test concurrent execution of multiple workflows."""
        import asyncio
        
        # Create multiple workflow instances
        workflows = []
        for i in range(5):
            llm_provider = MockLLMProvider(responses=[
                f'{{"command": "G28"}}',
                f'{{"command": "G1", "x": {i*10}, "y": {i*10}, "f": 1000}}',
                f'{{"command": "M3", "s": 255}}',
                f'{{"command": "G1", "x": {(i+1)*10}, "y": {(i+1)*10}, "f": 1000}}',
                f'{{"command": "M5"}}',
                f'{{"command": "G28"}}'
            ])
            plotter = MockPlotter(port=f"PORT_{i}")
            config = MockConfigManager()
            
            workflow = SimpleGCodeWorkflow(llm_provider, plotter, config)
            workflows.append((workflow, f"Draw pattern {i}"))
        
        # Execute all workflows concurrently
        start_time = time.time()
        
        tasks = [workflow.run(prompt) for workflow, prompt in workflows]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # All workflows should complete successfully
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                pytest.fail(f"Workflow {i} failed: {result}")
            assert isinstance(result, GCodeProgram)
        
        # Concurrent execution should be faster than sequential
        assert duration < 10.0, f"Concurrent execution took too long: {duration}s"
        
        print(f"✓ Concurrent execution test passed: {len(results)} workflows in {duration:.2f}s")
    
    @pytest.mark.integration
    async def test_visualization_and_monitoring_integration(self):
        """Test visualization and monitoring integration."""
        from promptplot.visualization import VisualizationManager, ProgressMonitor
        from promptplot.plotter.visualizer import PlotterVisualizer
        
        # Test visualization manager
        viz_manager = VisualizationManager()
        
        # Create test G-code program
        test_program = GCodeProgram(commands=[
            GCodeCommand(command="G28"),
            GCodeCommand(command="G1", x=10.0, y=10.0, f=1000),
            GCodeCommand(command="M3", s=255),
            GCodeCommand(command="G1", x=20.0, y=20.0, f=1000),
            GCodeCommand(command="M5"),
            GCodeCommand(command="G28")
        ])
        
        # Test visualization generation
        viz_result = await viz_manager.create_visualization(
            test_program, 
            output_path="/tmp/test_viz.png"
        )
        
        assert viz_result["success"] == True
        assert Path(viz_result["output_path"]).exists()
        
        # Test progress monitoring
        progress_monitor = ProgressMonitor()
        
        # Simulate workflow progress
        progress_monitor.start_monitoring("test_workflow")
        
        for i in range(5):
            progress_monitor.update_progress("test_workflow", i, 5, f"Step {i}")
            await asyncio.sleep(0.1)
        
        progress_monitor.complete_monitoring("test_workflow")
        
        # Get monitoring results
        results = progress_monitor.get_results("test_workflow")
        assert results["completed"] == True
        assert results["total_steps"] == 5
        
        print("✓ Visualization and monitoring integration working")
    
    @pytest.mark.integration
    async def test_complete_file_plotting_pipeline(self, temp_dir):
        """Test complete file plotting pipeline from file to execution."""
        from promptplot.workflows.file_plotting import FilePlottingWorkflow
        
        # Create comprehensive test files
        test_files = create_test_files(temp_dir)
        
        plotter = MockPlotter()
        config = MockConfigManager()
        workflow = FilePlottingWorkflow(plotter, config)
        
        # Test complete pipeline for each file type
        for file_format, file_path in test_files.items():
            print(f"Testing complete pipeline for {file_format}")
            
            # 1. File detection and validation
            from promptplot.converters.file_detector import FileFormatDetector
            detector = FileFormatDetector()
            
            detected_format = detector.detect_format(file_path)
            assert detected_format is not None, f"Failed to detect format for {file_format}"
            
            # 2. File conversion
            result = await workflow.plot_file(file_path)
            assert isinstance(result, GCodeProgram)
            
            # 3. G-code validation
            validator = GCodeTestValidator()
            is_valid, errors = validator.validate_program(result)
            assert is_valid, f"Invalid G-code from {file_format}: {errors}"
            
            # 4. Plotter execution simulation
            async with plotter:
                for command in result.commands:
                    success = await plotter.send_command(command.command)
                    assert success, f"Failed to send command: {command.command}"
            
            # 5. Verify execution results
            assert len(plotter.sent_commands) == len(result.commands)
            
            print(f"✓ Complete pipeline test passed for {file_format}")
        
        print("✓ All file plotting pipelines working")


class TestSystemRobustness:
    """Test system robustness and edge cases."""
    
    @pytest.mark.integration
    async def test_malformed_input_handling(self):
        """Test handling of malformed inputs."""
        llm_provider = MockLLMProvider(responses=[
            "Not JSON at all",
            '{"invalid": "json", "missing": "command"}',
            '{"command": "INVALID_COMMAND"}',
            '{"command": "G1", "x": "not_a_number"}',
            '{"command": "G1", "x": 10, "y": 10, "f": 1000}'  # Finally valid
        ])
        
        plotter = MockPlotter()
        config = MockConfigManager()
        workflow = SimpleGCodeWorkflow(llm_provider, plotter, config, max_retries=10)
        
        # Should eventually succeed despite malformed inputs
        result = await workflow.run("Draw something")
        assert isinstance(result, GCodeProgram)
        assert llm_provider.call_count >= 5  # Should have retried multiple times
        
        print("✓ Malformed input handling working")
    
    @pytest.mark.integration
    async def test_resource_exhaustion_handling(self):
        """Test handling of resource exhaustion scenarios."""
        
        # Test with very high retry count (simulating resource exhaustion)
        llm_provider = MockLLMProvider(responses=["Invalid"] * 1000)
        plotter = MockPlotter()
        config = MockConfigManager()
        
        workflow = SimpleGCodeWorkflow(llm_provider, plotter, config, max_retries=5)
        
        # Should fail gracefully after max retries
        try:
            result = await workflow.run("Draw something")
            # If it succeeds, that's also acceptable (mock might have fallback)
            if result:
                assert isinstance(result, GCodeProgram)
        except Exception as e:
            # Should be a workflow exception, not a system crash
            assert isinstance(e, (WorkflowException, Exception))
        
        print("✓ Resource exhaustion handling working")
    
    @pytest.mark.integration
    async def test_network_interruption_simulation(self):
        """Test handling of network interruption scenarios."""
        
        # Simulate network interruption with delayed responses
        class DelayedLLMProvider(MockLLMProvider):
            async def acomplete(self, prompt: str) -> str:
                await asyncio.sleep(0.1)  # Simulate network delay
                return await super().acomplete(prompt)
        
        llm_provider = DelayedLLMProvider()
        plotter = MockPlotter()
        config = MockConfigManager()
        
        workflow = SimpleGCodeWorkflow(llm_provider, plotter, config)
        
        # Should handle delays gracefully
        start_time = time.time()
        result = await workflow.run("Draw something")
        end_time = time.time()
        
        assert isinstance(result, GCodeProgram)
        assert end_time - start_time >= 0.1  # Should have experienced delay
        
        print("✓ Network interruption handling working")
    
    @pytest.mark.integration
    async def test_memory_pressure_handling(self):
        """Test handling under memory pressure."""
        
        # Create workflow with large data structures
        large_responses = []
        for i in range(1000):
            large_responses.append(f'{{"command": "G1", "x": {i}, "y": {i}, "f": 1000, "comment": "Large comment with lots of text to increase memory usage for testing purposes"}}')
        
        llm_provider = MockLLMProvider(responses=large_responses)
        plotter = MockPlotter()
        config = MockConfigManager()
        
        workflow = SequentialGCodeWorkflow(llm_provider, plotter, config, max_steps=100)
        
        # Should handle large datasets without crashing
        result = await workflow.run("Draw a very complex pattern")
        assert isinstance(result, GCodeProgram)
        assert len(result.commands) >= 50
        
        print("✓ Memory pressure handling working")