"""
Performance benchmark tests for PromptPlot workflows.
"""
import pytest
import asyncio
import time
from pathlib import Path
import statistics
from typing import List, Dict, Any

from promptplot.workflows.simple_batch import SimpleBatchWorkflow
from promptplot.workflows.advanced_sequential import AdvancedSequentialWorkflow
from promptplot.workflows.file_plotting import FilePlottingWorkflow
from promptplot.core.models import GCodeProgram
from tests.utils.mocks import MockLLMProvider, MockPlotter, MockConfigManager
from tests.fixtures.sample_files import create_test_files
from tests.utils.gcode_utils import GCodeAnalyzer


class PerformanceMetrics:
    """Helper class for collecting performance metrics."""
    
    def __init__(self):
        self.metrics = {}
        
    def start_timer(self, name: str):
        """Start timing an operation."""
        self.metrics[f"{name}_start"] = time.perf_counter()
        
    def end_timer(self, name: str):
        """End timing an operation."""
        start_time = self.metrics.get(f"{name}_start")
        if start_time:
            self.metrics[f"{name}_duration"] = time.perf_counter() - start_time
            
    def get_duration(self, name: str) -> float:
        """Get duration of an operation."""
        return self.metrics.get(f"{name}_duration", 0.0)
        
    def add_metric(self, name: str, value: Any):
        """Add a custom metric."""
        self.metrics[name] = value
        
    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all collected metrics."""
        return self.metrics.copy()


@pytest.mark.benchmark
class TestWorkflowPerformance:
    """Test workflow performance benchmarks."""
    
    @pytest.fixture
    def performance_setup(self):
        """Set up performance testing environment."""
        # Use fast mock responses for consistent timing
        fast_responses = [
            '{"command": "G28"}',
            '{"command": "G1", "x": 10, "y": 10, "f": 1000}',
            '{"command": "M3", "s": 255}',
            '{"command": "G1", "x": 20, "y": 20, "f": 1000}',
            '{"command": "M5"}',
            '{"command": "G28"}'
        ]
        
        llm_provider = MockLLMProvider(responses=fast_responses)
        plotter = MockPlotter()
        config = MockConfigManager()
        
        return llm_provider, plotter, config
        
    @pytest.mark.benchmark
    async def test_simple_workflow_performance(self, performance_setup, benchmark):
        """Benchmark simple workflow performance."""
        llm_provider, plotter, config = performance_setup
        
        workflow = SimpleBatchWorkflow(llm_provider, plotter, config)
        
        def run_workflow():
            return asyncio.run(workflow.run("Draw a simple line"))
            
        # Benchmark the workflow
        result = benchmark(run_workflow)
        
        assert isinstance(result, GCodeProgram)
        assert len(result.commands) > 0
        
    @pytest.mark.benchmark
    async def test_advanced_workflow_performance(self, performance_setup, benchmark):
        """Benchmark advanced workflow performance."""
        llm_provider, plotter, config = performance_setup
        
        workflow = AdvancedSequentialWorkflow(
            llm_provider, plotter, config,
            max_steps=10
        )
        
        def run_workflow():
            return asyncio.run(workflow.run("Draw a complex shape"))
            
        result = benchmark(run_workflow)
        
        assert isinstance(result, GCodeProgram)
        
    @pytest.mark.benchmark
    async def test_concurrent_workflow_performance(self, performance_setup):
        """Benchmark concurrent workflow execution."""
        llm_provider, plotter, config = performance_setup
        
        metrics = PerformanceMetrics()
        
        # Create multiple workflows
        workflows = []
        for i in range(5):
            workflow = SimpleBatchWorkflow(
                MockLLMProvider(responses=llm_provider.responses.copy()),
                MockPlotter(port=f"PORT_{i}"),
                MockConfigManager()
            )
            workflows.append(workflow)
            
        # Benchmark concurrent execution
        metrics.start_timer("concurrent_execution")
        
        tasks = [
            workflow.run(f"Draw shape {i}")
            for i, workflow in enumerate(workflows)
        ]
        
        results = await asyncio.gather(*tasks)
        
        metrics.end_timer("concurrent_execution")
        
        # Verify all completed successfully
        assert len(results) == 5
        for result in results:
            assert isinstance(result, GCodeProgram)
            
        # Performance should be better than sequential
        concurrent_time = metrics.get_duration("concurrent_execution")
        assert concurrent_time < 5.0  # Should complete within 5 seconds
        
    @pytest.mark.benchmark
    async def test_large_gcode_generation_performance(self, performance_setup):
        """Benchmark performance with large G-code generation."""
        llm_provider, plotter, config = performance_setup
        
        # Create many responses for large drawing
        large_responses = []
        for i in range(100):
            large_responses.append(f'{{"command": "G1", "x": {i}, "y": {i%20}, "f": 1000}}')
            
        llm_provider.responses = large_responses
        
        workflow = AdvancedSequentialWorkflow(
            llm_provider, plotter, config,
            max_steps=100
        )
        
        metrics = PerformanceMetrics()
        metrics.start_timer("large_generation")
        
        result = await workflow.run("Draw a large complex pattern")
        
        metrics.end_timer("large_generation")
        
        # Verify result
        assert isinstance(result, GCodeProgram)
        assert len(result.commands) >= 50
        
        # Performance metrics
        generation_time = metrics.get_duration("large_generation")
        commands_per_second = len(result.commands) / generation_time
        
        # Should generate at least 10 commands per second
        assert commands_per_second >= 10
        
        # Memory usage should be reasonable
        analyzer = GCodeAnalyzer()
        analysis = analyzer.analyze_complexity(result)
        
        metrics.add_metric("total_commands", analysis["total_commands"])
        metrics.add_metric("commands_per_second", commands_per_second)
        metrics.add_metric("total_distance", analysis["total_distance"])
        
        print(f"Performance metrics: {metrics.get_all_metrics()}")


@pytest.mark.benchmark
class TestFileConversionPerformance:
    """Test file conversion performance benchmarks."""
    
    @pytest.fixture
    def file_performance_setup(self, temp_dir):
        """Set up file conversion performance testing."""
        plotter = MockPlotter()
        config = MockConfigManager()
        
        workflow = FilePlottingWorkflow(plotter, config)
        test_files = create_test_files(temp_dir)
        
        return workflow, test_files
        
    @pytest.mark.benchmark
    async def test_svg_conversion_performance(self, file_performance_setup, benchmark):
        """Benchmark SVG file conversion performance."""
        workflow, test_files = file_performance_setup
        
        svg_file = test_files["svg"]
        
        def convert_svg():
            return asyncio.run(workflow.plot_file(svg_file))
            
        result = benchmark(convert_svg)
        
        assert isinstance(result, GCodeProgram)
        assert len(result.commands) > 0
        
    @pytest.mark.benchmark
    async def test_batch_file_conversion_performance(self, file_performance_setup):
        """Benchmark batch file conversion performance."""
        workflow, test_files = file_performance_setup
        
        files_to_convert = [
            test_files["svg"],
            test_files["gcode"], 
            test_files["dxf"],
            test_files["json"]
        ]
        
        metrics = PerformanceMetrics()
        metrics.start_timer("batch_conversion")
        
        results = await workflow.plot_files_batch(files_to_convert)
        
        metrics.end_timer("batch_conversion")
        
        # Verify results
        assert len(results) == len(files_to_convert)
        for result in results:
            assert isinstance(result, GCodeProgram)
            
        # Performance metrics
        conversion_time = metrics.get_duration("batch_conversion")
        files_per_second = len(files_to_convert) / conversion_time
        
        metrics.add_metric("files_converted", len(files_to_convert))
        metrics.add_metric("files_per_second", files_per_second)
        
        # Should convert at least 1 file per second
        assert files_per_second >= 1.0
        
    @pytest.mark.benchmark
    async def test_large_svg_conversion_performance(self, temp_dir):
        """Benchmark large SVG file conversion performance."""
        # Create large SVG file
        large_svg = temp_dir / "large.svg"
        svg_content = '<?xml version="1.0"?><svg width="1000" height="1000">'
        
        # Add many elements (but not too many for reasonable test time)
        for i in range(100):
            x, y = i * 10, (i % 10) * 100
            svg_content += f'<rect x="{x}" y="{y}" width="5" height="5"/>'
            svg_content += f'<circle cx="{x+50}" cy="{y+50}" r="3"/>'
            
        svg_content += '</svg>'
        large_svg.write_text(svg_content)
        
        plotter = MockPlotter()
        config = MockConfigManager()
        workflow = FilePlottingWorkflow(plotter, config)
        
        metrics = PerformanceMetrics()
        metrics.start_timer("large_svg_conversion")
        
        result = await workflow.plot_file(large_svg)
        
        metrics.end_timer("large_svg_conversion")
        
        # Verify result
        assert isinstance(result, GCodeProgram)
        assert len(result.commands) > 100
        
        # Performance should be reasonable for large files
        conversion_time = metrics.get_duration("large_svg_conversion")
        assert conversion_time < 10.0  # Should complete within 10 seconds


@pytest.mark.benchmark
class TestMemoryPerformance:
    """Test memory usage and performance."""
    
    @pytest.mark.benchmark
    async def test_memory_usage_large_workflow(self):
        """Test memory usage with large workflows."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Create large workflow
        large_responses = []
        for i in range(500):
            large_responses.append(f'{{"command": "G1", "x": {i}, "y": {i%50}, "f": 1000}}')
            
        llm_provider = MockLLMProvider(responses=large_responses)
        plotter = MockPlotter()
        config = MockConfigManager()
        
        workflow = AdvancedSequentialWorkflow(
            llm_provider, plotter, config,
            max_steps=500
        )
        
        # Execute workflow
        result = await workflow.run("Draw very large pattern")
        
        # Check memory usage
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (less than 100MB)
        assert memory_increase < 100 * 1024 * 1024
        
        # Verify result
        assert isinstance(result, GCodeProgram)
        assert len(result.commands) >= 100
        
    @pytest.mark.benchmark
    async def test_memory_cleanup_after_workflow(self):
        """Test that memory is properly cleaned up after workflows."""
        import gc
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        
        # Run multiple workflows and check memory doesn't grow indefinitely
        memory_samples = []
        
        for i in range(10):
            llm_provider = MockLLMProvider()
            plotter = MockPlotter()
            config = MockConfigManager()
            
            workflow = SimpleBatchWorkflow(llm_provider, plotter, config)
            
            result = await workflow.run(f"Draw pattern {i}")
            
            # Force garbage collection
            gc.collect()
            
            # Sample memory usage
            memory_samples.append(process.memory_info().rss)
            
            # Clean up references
            del workflow, llm_provider, plotter, config, result
            
        # Memory usage should not grow significantly
        memory_growth = memory_samples[-1] - memory_samples[0]
        
        # Allow some growth but not excessive (less than 50MB)
        assert memory_growth < 50 * 1024 * 1024


@pytest.mark.benchmark
class TestScalabilityPerformance:
    """Test scalability performance characteristics."""
    
    @pytest.mark.benchmark
    async def test_workflow_scaling_with_complexity(self):
        """Test how workflow performance scales with complexity."""
        complexity_levels = [10, 50, 100, 200]
        performance_results = []
        
        for complexity in complexity_levels:
            # Create responses for this complexity level
            responses = []
            for i in range(complexity):
                responses.append(f'{{"command": "G1", "x": {i}, "y": {i%10}, "f": 1000}}')
                
            llm_provider = MockLLMProvider(responses=responses)
            plotter = MockPlotter()
            config = MockConfigManager()
            
            workflow = AdvancedSequentialWorkflow(
                llm_provider, plotter, config,
                max_steps=complexity
            )
            
            # Measure performance
            start_time = time.perf_counter()
            result = await workflow.run(f"Draw pattern with {complexity} commands")
            end_time = time.perf_counter()
            
            execution_time = end_time - start_time
            commands_per_second = len(result.commands) / execution_time
            
            performance_results.append({
                "complexity": complexity,
                "execution_time": execution_time,
                "commands_per_second": commands_per_second,
                "total_commands": len(result.commands)
            })
            
        # Analyze scaling characteristics
        # Performance should not degrade linearly with complexity
        for i in range(1, len(performance_results)):
            prev_result = performance_results[i-1]
            curr_result = performance_results[i]
            
            complexity_ratio = curr_result["complexity"] / prev_result["complexity"]
            time_ratio = curr_result["execution_time"] / prev_result["execution_time"]
            
            # Time should not increase more than 2x for 2x complexity
            assert time_ratio < complexity_ratio * 2
            
        print("Scalability results:", performance_results)
        
    @pytest.mark.benchmark
    async def test_concurrent_workflow_scaling(self):
        """Test how performance scales with concurrent workflows."""
        concurrency_levels = [1, 2, 5, 10]
        performance_results = []
        
        for concurrency in concurrency_levels:
            workflows = []
            
            # Create workflows for this concurrency level
            for i in range(concurrency):
                llm_provider = MockLLMProvider()
                plotter = MockPlotter(port=f"PORT_{i}")
                config = MockConfigManager()
                
                workflow = SimpleBatchWorkflow(llm_provider, plotter, config)
                workflows.append(workflow)
                
            # Measure concurrent execution
            start_time = time.perf_counter()
            
            tasks = [
                workflow.run(f"Draw concurrent pattern {i}")
                for i, workflow in enumerate(workflows)
            ]
            
            results = await asyncio.gather(*tasks)
            
            end_time = time.perf_counter()
            
            execution_time = end_time - start_time
            workflows_per_second = concurrency / execution_time
            
            performance_results.append({
                "concurrency": concurrency,
                "execution_time": execution_time,
                "workflows_per_second": workflows_per_second
            })
            
            # Verify all completed
            assert len(results) == concurrency
            
        # Analyze concurrent scaling
        # Higher concurrency should not significantly increase total time
        max_time = max(result["execution_time"] for result in performance_results)
        min_time = min(result["execution_time"] for result in performance_results)
        
        # Total time should not increase more than 3x even with 10x concurrency
        assert max_time / min_time < 3.0
        
        print("Concurrency scaling results:", performance_results)


@pytest.mark.benchmark
class TestRealWorldPerformance:
    """Test performance with realistic scenarios."""
    
    @pytest.mark.benchmark
    async def test_typical_drawing_session_performance(self):
        """Test performance of a typical drawing session."""
        # Simulate a typical session with multiple drawings
        drawing_prompts = [
            "Draw a simple line",
            "Draw a rectangle", 
            "Draw a circle",
            "Draw a house with triangular roof",
            "Draw a flower with petals"
        ]
        
        llm_provider = MockLLMProvider()
        plotter = MockPlotter()
        config = MockConfigManager()
        
        workflow = SimpleBatchWorkflow(llm_provider, plotter, config)
        
        session_metrics = PerformanceMetrics()
        session_metrics.start_timer("full_session")
        
        results = []
        for i, prompt in enumerate(drawing_prompts):
            session_metrics.start_timer(f"drawing_{i}")
            result = await workflow.run(prompt)
            session_metrics.end_timer(f"drawing_{i}")
            
            results.append(result)
            
        session_metrics.end_timer("full_session")
        
        # Verify all drawings completed
        assert len(results) == len(drawing_prompts)
        
        # Session should complete in reasonable time
        total_time = session_metrics.get_duration("full_session")
        assert total_time < 30.0  # Should complete within 30 seconds
        
        # Individual drawings should be fast
        for i in range(len(drawing_prompts)):
            drawing_time = session_metrics.get_duration(f"drawing_{i}")
            assert drawing_time < 10.0  # Each drawing within 10 seconds
            
        # Calculate session statistics
        total_commands = sum(len(result.commands) for result in results)
        commands_per_second = total_commands / total_time
        
        session_metrics.add_metric("total_drawings", len(results))
        session_metrics.add_metric("total_commands", total_commands)
        session_metrics.add_metric("commands_per_second", commands_per_second)
        
        print(f"Session performance: {session_metrics.get_all_metrics()}")
        
        # Should maintain good throughput
        assert commands_per_second >= 5.0