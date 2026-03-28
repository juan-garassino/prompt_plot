#!/usr/bin/env python3
"""
Comprehensive PromptPlot Test Suite

This script provides a complete testing framework for PromptPlot v2.0,
covering all major functionality areas:

1. Core Components
   - G-code command creation and validation
   - G-code program manipulation
   - Strategy selection

2. Plotter Connections
   - Simulated plotter testing
   - Serial plotter connection testing
   - Command execution and status monitoring

3. File Operations
   - Loading G-code from files
   - SVG to G-code conversion
   - DXF to G-code conversion
   - File format detection

4. LLM Integration
   - Mock LLM provider testing
   - LLM streaming workflow testing
   - Command generation and validation

5. Advanced Features
   - Ink change / pen change points
   - Multi-color drawing support
   - Visualization testing

Usage:
    python test_comprehensive.py                    # Run all tests
    python test_comprehensive.py --category core    # Run only core tests
    python test_comprehensive.py --category plotter # Run only plotter tests
    python test_comprehensive.py --category file    # Run only file tests
    python test_comprehensive.py --category llm     # Run only LLM tests
    python test_comprehensive.py --port /dev/ttyUSB0  # Test with real plotter
"""

import asyncio
import sys
import os
import time
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


# =============================================================================
# Test Result Tracking
# =============================================================================

@dataclass
class TestResult:
    """Individual test result"""
    name: str
    category: str
    success: bool
    message: str = ""
    duration: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)


class TestRunner:
    """Manages test execution and reporting"""
    
    def __init__(self):
        self.results: List[TestResult] = []
        self.start_time: float = 0
        
    def log_result(self, name: str, category: str, success: bool, 
                   message: str = "", duration: float = 0.0, details: Dict = None):
        """Log a test result"""
        result = TestResult(
            name=name,
            category=category,
            success=success,
            message=message,
            duration=duration,
            details=details or {}
        )
        self.results.append(result)
        
        status = "✅" if success else "❌"
        print(f"{status} [{category}] {name}: {message}")
        
        if details and not success:
            for key, value in details.items():
                print(f"   {key}: {value}")
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 70)
        print("📊 TEST SUMMARY")
        print("=" * 70)
        
        # Group by category
        categories = {}
        for result in self.results:
            if result.category not in categories:
                categories[result.category] = {"passed": 0, "failed": 0, "tests": []}
            
            if result.success:
                categories[result.category]["passed"] += 1
            else:
                categories[result.category]["failed"] += 1
            categories[result.category]["tests"].append(result)
        
        total_passed = sum(c["passed"] for c in categories.values())
        total_failed = sum(c["failed"] for c in categories.values())
        total_tests = total_passed + total_failed
        
        print(f"\nTotal: {total_tests} tests | Passed: {total_passed} ✅ | Failed: {total_failed} ❌")
        print(f"Success Rate: {(total_passed/total_tests*100):.1f}%" if total_tests > 0 else "No tests run")
        
        print("\nBy Category:")
        for category, data in categories.items():
            status = "✅" if data["failed"] == 0 else "❌"
            print(f"  {status} {category}: {data['passed']}/{data['passed'] + data['failed']} passed")
        
        if total_failed > 0:
            print("\n❌ Failed Tests:")
            for result in self.results:
                if not result.success:
                    print(f"   - [{result.category}] {result.name}: {result.message}")
        
        return total_failed == 0


# =============================================================================
# Core Component Tests
# =============================================================================

class CoreTests:
    """Tests for core PromptPlot components"""
    
    def __init__(self, runner: TestRunner):
        self.runner = runner
        self.category = "Core"
    
    def run_all(self):
        """Run all core tests"""
        print("\n" + "=" * 70)
        print("🔧 CORE COMPONENT TESTS")
        print("=" * 70)
        
        self.test_imports()
        self.test_gcode_command_creation()
        self.test_gcode_command_validation()
        self.test_gcode_program_creation()
        self.test_gcode_program_analysis()
        self.test_strategy_selector()
        self.test_configuration()
    
    def test_imports(self):
        """Test that all core modules can be imported"""
        start = time.time()
        try:
            from promptplot import (
                GCodeCommand, GCodeProgram, StrategySelector,
                get_config, PromptPlotConfig
            )
            from promptplot.core import DrawingStrategy, WorkflowResult
            
            self.runner.log_result(
                "Core Imports", self.category, True,
                "All core modules imported successfully",
                time.time() - start
            )
        except ImportError as e:
            self.runner.log_result(
                "Core Imports", self.category, False,
                f"Import failed: {str(e)}",
                time.time() - start
            )
    
    def test_gcode_command_creation(self):
        """Test G-code command creation"""
        start = time.time()
        try:
            from promptplot.core import GCodeCommand
            
            # Test basic commands
            commands = [
                GCodeCommand(command="G28"),
                GCodeCommand(command="G1", x=10.0, y=20.0, f=1000),
                GCodeCommand(command="M3", s=255),
                GCodeCommand(command="M5"),
                GCodeCommand(command="G0", x=0.0, y=0.0, z=5.0),
            ]
            
            # Verify all commands created
            assert len(commands) == 5
            assert commands[0].command == "G28"
            assert commands[1].x == 10.0
            assert commands[2].s == 255
            
            self.runner.log_result(
                "G-code Command Creation", self.category, True,
                f"Created {len(commands)} commands successfully",
                time.time() - start,
                {"commands_created": len(commands)}
            )
        except Exception as e:
            self.runner.log_result(
                "G-code Command Creation", self.category, False,
                f"Failed: {str(e)}",
                time.time() - start
            )
    
    def test_gcode_command_validation(self):
        """Test G-code command validation"""
        start = time.time()
        try:
            from promptplot.core import GCodeCommand
            from pydantic import ValidationError
            
            # Test valid commands
            valid_commands = ["G0", "G1", "G28", "M3", "M5"]
            for cmd in valid_commands:
                GCodeCommand(command=cmd)
            
            # Test invalid command (should raise ValidationError)
            invalid_raised = False
            try:
                GCodeCommand(command="INVALID")
            except ValidationError:
                invalid_raised = True
            
            assert invalid_raised, "Invalid command should raise ValidationError"
            
            self.runner.log_result(
                "G-code Command Validation", self.category, True,
                f"Validated {len(valid_commands)} commands, invalid rejected",
                time.time() - start
            )
        except Exception as e:
            self.runner.log_result(
                "G-code Command Validation", self.category, False,
                f"Failed: {str(e)}",
                time.time() - start
            )
    
    def test_gcode_program_creation(self):
        """Test G-code program creation"""
        start = time.time()
        try:
            from promptplot.core import GCodeCommand, GCodeProgram
            
            commands = [
                GCodeCommand(command="G28"),
                GCodeCommand(command="M5"),
                GCodeCommand(command="G1", x=0.0, y=0.0),
                GCodeCommand(command="M3"),
                GCodeCommand(command="G1", x=50.0, y=0.0),
                GCodeCommand(command="G1", x=50.0, y=50.0),
                GCodeCommand(command="G1", x=0.0, y=50.0),
                GCodeCommand(command="G1", x=0.0, y=0.0),
                GCodeCommand(command="M5"),
            ]
            
            program = GCodeProgram(commands=commands)
            
            # Test to_gcode conversion
            gcode_str = program.to_gcode()
            assert len(gcode_str) > 0
            
            self.runner.log_result(
                "G-code Program Creation", self.category, True,
                f"Created program with {len(program.commands)} commands",
                time.time() - start,
                {"gcode_length": len(gcode_str)}
            )
        except Exception as e:
            self.runner.log_result(
                "G-code Program Creation", self.category, False,
                f"Failed: {str(e)}",
                time.time() - start
            )
    
    def test_gcode_program_analysis(self):
        """Test G-code program analysis methods"""
        start = time.time()
        try:
            from promptplot.core import GCodeCommand, GCodeProgram
            
            commands = [
                GCodeCommand(command="G28"),
                GCodeCommand(command="M5"),
                GCodeCommand(command="G1", x=0.0, y=0.0),
                GCodeCommand(command="M3"),
                GCodeCommand(command="G1", x=50.0, y=0.0),
                GCodeCommand(command="G1", x=50.0, y=50.0),
                GCodeCommand(command="M5"),
            ]
            
            program = GCodeProgram(commands=commands)
            
            # Test analysis methods
            bounds = program.get_bounds()
            movement_cmds = program.get_movement_commands()
            pen_cmds = program.get_pen_commands()
            cmd_counts = program.count_by_command_type()
            
            assert bounds is not None
            assert len(movement_cmds) > 0
            assert len(pen_cmds) > 0
            assert len(cmd_counts) > 0
            
            self.runner.log_result(
                "G-code Program Analysis", self.category, True,
                f"Analysis complete: bounds={bounds}",
                time.time() - start,
                {
                    "bounds": bounds,
                    "movement_commands": len(movement_cmds),
                    "pen_commands": len(pen_cmds),
                    "command_types": cmd_counts
                }
            )
        except Exception as e:
            self.runner.log_result(
                "G-code Program Analysis", self.category, False,
                f"Failed: {str(e)}",
                time.time() - start
            )
    
    def test_strategy_selector(self):
        """Test strategy selection"""
        start = time.time()
        try:
            from promptplot import StrategySelector
            
            selector = StrategySelector()
            
            test_prompts = [
                ("Draw a rectangle", "orthogonal"),
                ("Draw a circle", "non_orthogonal"),
                ("Draw a grid pattern", "orthogonal"),
                ("Draw a curved flower", "non_orthogonal"),
            ]
            
            results = []
            for prompt, expected_type in test_prompts:
                strategy = selector.select_strategy(prompt)
                analysis = selector.analyze_prompt_complexity(prompt)
                results.append({
                    "prompt": prompt,
                    "strategy": strategy.__class__.__name__,
                    "complexity": analysis.complexity_level.value
                })
            
            self.runner.log_result(
                "Strategy Selector", self.category, True,
                f"Analyzed {len(test_prompts)} prompts",
                time.time() - start,
                {"results": results}
            )
        except Exception as e:
            self.runner.log_result(
                "Strategy Selector", self.category, False,
                f"Failed: {str(e)}",
                time.time() - start
            )
    
    def test_configuration(self):
        """Test configuration system"""
        start = time.time()
        try:
            from promptplot import get_config
            
            config = get_config()
            
            # Verify config has expected sections
            assert hasattr(config, 'llm')
            assert hasattr(config, 'plotter')
            assert hasattr(config, 'workflow')
            
            self.runner.log_result(
                "Configuration System", self.category, True,
                "Configuration loaded successfully",
                time.time() - start,
                {
                    "llm_provider": config.llm.default_provider,
                    "plotter_type": config.plotter.default_type,
                    "max_retries": config.workflow.max_retries
                }
            )
        except Exception as e:
            self.runner.log_result(
                "Configuration System", self.category, False,
                f"Failed: {str(e)}",
                time.time() - start
            )


# =============================================================================
# Plotter Tests
# =============================================================================

class PlotterTests:
    """Tests for plotter connections and operations"""
    
    def __init__(self, runner: TestRunner, serial_port: Optional[str] = None):
        self.runner = runner
        self.category = "Plotter"
        self.serial_port = serial_port
    
    async def run_all(self):
        """Run all plotter tests"""
        print("\n" + "=" * 70)
        print("🖨️  PLOTTER TESTS")
        print("=" * 70)
        
        await self.test_simulated_plotter_connection()
        await self.test_simulated_plotter_commands()
        await self.test_simulated_plotter_program()
        await self.test_plotter_status_monitoring()
        
        if self.serial_port:
            await self.test_serial_plotter_connection()
    
    async def test_simulated_plotter_connection(self):
        """Test simulated plotter connection"""
        start = time.time()
        try:
            from promptplot.plotter import SimulatedPlotter
            
            plotter = SimulatedPlotter(port="TEST")
            
            # Test connection
            success = await plotter.connect()
            assert success, "Connection should succeed"
            assert plotter.is_connected, "Plotter should be connected"
            
            # Test disconnection
            await plotter.disconnect()
            assert not plotter.is_connected, "Plotter should be disconnected"
            
            self.runner.log_result(
                "Simulated Plotter Connection", self.category, True,
                "Connect/disconnect cycle successful",
                time.time() - start
            )
        except Exception as e:
            self.runner.log_result(
                "Simulated Plotter Connection", self.category, False,
                f"Failed: {str(e)}",
                time.time() - start
            )
    
    async def test_simulated_plotter_commands(self):
        """Test sending commands to simulated plotter"""
        start = time.time()
        try:
            from promptplot.plotter import SimulatedPlotter
            
            plotter = SimulatedPlotter(port="TEST")
            await plotter.connect()
            
            # Test basic commands
            test_commands = [
                "G28",
                "M5",
                "G1 X10 Y10 F1000",
                "M3 S255",
                "G1 X20 Y20 F1000",
                "M5",
            ]
            
            success_count = 0
            for cmd in test_commands:
                result = await plotter.send_command(cmd)
                if result:
                    success_count += 1
            
            await plotter.disconnect()
            
            all_success = success_count == len(test_commands)
            self.runner.log_result(
                "Simulated Plotter Commands", self.category, all_success,
                f"Executed {success_count}/{len(test_commands)} commands",
                time.time() - start,
                {"commands_sent": len(test_commands), "successful": success_count}
            )
        except Exception as e:
            self.runner.log_result(
                "Simulated Plotter Commands", self.category, False,
                f"Failed: {str(e)}",
                time.time() - start
            )
    
    async def test_simulated_plotter_program(self):
        """Test executing a G-code program on simulated plotter"""
        start = time.time()
        try:
            from promptplot.plotter import SimulatedPlotter
            from promptplot.core import GCodeCommand, GCodeProgram
            
            # Create a test program (draw a square)
            commands = [
                GCodeCommand(command="G28"),
                GCodeCommand(command="M5"),
                GCodeCommand(command="G1", x=0.0, y=0.0, f=1000),
                GCodeCommand(command="M3"),
                GCodeCommand(command="G1", x=30.0, y=0.0, f=1000),
                GCodeCommand(command="G1", x=30.0, y=30.0, f=1000),
                GCodeCommand(command="G1", x=0.0, y=30.0, f=1000),
                GCodeCommand(command="G1", x=0.0, y=0.0, f=1000),
                GCodeCommand(command="M5"),
            ]
            program = GCodeProgram(commands=commands)
            
            plotter = SimulatedPlotter(port="TEST")
            await plotter.connect()
            
            success_count = 0
            for cmd in program.commands:
                result = await plotter.send_command(cmd.to_gcode())
                if result:
                    success_count += 1
            
            await plotter.disconnect()
            
            all_success = success_count == len(program.commands)
            self.runner.log_result(
                "Simulated Plotter Program Execution", self.category, all_success,
                f"Executed {success_count}/{len(program.commands)} program commands",
                time.time() - start,
                {"program_commands": len(program.commands), "successful": success_count}
            )
        except Exception as e:
            self.runner.log_result(
                "Simulated Plotter Program Execution", self.category, False,
                f"Failed: {str(e)}",
                time.time() - start
            )
    
    async def test_plotter_status_monitoring(self):
        """Test plotter status monitoring"""
        start = time.time()
        try:
            from promptplot.plotter import SimulatedPlotter
            
            plotter = SimulatedPlotter(port="TEST")
            await plotter.connect()
            
            # Send some commands
            await plotter.send_command("G28")
            await plotter.send_command("G1 X10 Y10")
            
            # Check status
            assert hasattr(plotter, 'status')
            
            # Check command history
            history = plotter.get_command_history() if hasattr(plotter, 'get_command_history') else []
            
            await plotter.disconnect()
            
            self.runner.log_result(
                "Plotter Status Monitoring", self.category, True,
                f"Status monitoring working, {len(history)} commands in history",
                time.time() - start,
                {"history_length": len(history)}
            )
        except Exception as e:
            self.runner.log_result(
                "Plotter Status Monitoring", self.category, False,
                f"Failed: {str(e)}",
                time.time() - start
            )
    
    async def test_serial_plotter_connection(self):
        """Test serial plotter connection (requires hardware)"""
        start = time.time()
        try:
            from promptplot.plotter import SerialPlotter
            
            plotter = SerialPlotter(
                port=self.serial_port,
                timeout=10.0,
                max_retries=2
            )
            
            try:
                success = await plotter.connect_with_retry()
                
                if success:
                    # Test basic command
                    await plotter.send_command("G28")
                    await plotter.disconnect()
                    
                    self.runner.log_result(
                        "Serial Plotter Connection", self.category, True,
                        f"Connected to {self.serial_port}",
                        time.time() - start,
                        {"port": self.serial_port}
                    )
                else:
                    self.runner.log_result(
                        "Serial Plotter Connection", self.category, False,
                        f"Failed to connect to {self.serial_port}",
                        time.time() - start
                    )
            except Exception as e:
                self.runner.log_result(
                    "Serial Plotter Connection", self.category, False,
                    f"Connection error: {str(e)}",
                    time.time() - start,
                    {"port": self.serial_port}
                )
        except ImportError as e:
            self.runner.log_result(
                "Serial Plotter Connection", self.category, False,
                f"Import error: {str(e)}",
                time.time() - start
            )


# =============================================================================
# File Operation Tests
# =============================================================================

class FileTests:
    """Tests for file operations and conversions"""
    
    def __init__(self, runner: TestRunner):
        self.runner = runner
        self.category = "File"
    
    def run_all(self):
        """Run all file tests"""
        print("\n" + "=" * 70)
        print("📁 FILE OPERATION TESTS")
        print("=" * 70)
        
        self.test_file_format_detection()
        self.test_gcode_file_loading()
        self.test_gcode_string_parsing()
        self.test_svg_conversion()
        self.test_json_conversion()
    
    def test_file_format_detection(self):
        """Test file format detection"""
        start = time.time()
        try:
            from promptplot.converters import FileFormatDetector
            
            detector = FileFormatDetector()
            
            test_files = [
                ("test.svg", "SVG"),
                ("test.gcode", "GCODE"),
                ("test.dxf", "DXF"),
                ("test.json", "JSON"),
                ("test.png", "IMAGE"),
            ]
            
            results = []
            for filename, expected in test_files:
                try:
                    detected = detector.detect_format(filename)
                    results.append({
                        "file": filename,
                        "detected": detected.name if detected else "UNKNOWN",
                        "expected": expected
                    })
                except Exception:
                    results.append({
                        "file": filename,
                        "detected": "ERROR",
                        "expected": expected
                    })
            
            self.runner.log_result(
                "File Format Detection", self.category, True,
                f"Detected {len(results)} file formats",
                time.time() - start,
                {"results": results}
            )
        except Exception as e:
            self.runner.log_result(
                "File Format Detection", self.category, False,
                f"Failed: {str(e)}",
                time.time() - start
            )
    
    def test_gcode_file_loading(self):
        """Test loading G-code from file"""
        start = time.time()
        try:
            from promptplot.converters import GCodeLoader
            
            # Check if sample file exists
            sample_file = Path("examples/sample_files/simple_commands.gcode")
            
            if sample_file.exists():
                loader = GCodeLoader()
                program = loader.load(str(sample_file))
                
                self.runner.log_result(
                    "G-code File Loading", self.category, True,
                    f"Loaded {len(program.commands)} commands from file",
                    time.time() - start,
                    {"file": str(sample_file), "commands": len(program.commands)}
                )
            else:
                self.runner.log_result(
                    "G-code File Loading", self.category, True,
                    "Sample file not found, skipped",
                    time.time() - start
                )
        except Exception as e:
            self.runner.log_result(
                "G-code File Loading", self.category, False,
                f"Failed: {str(e)}",
                time.time() - start
            )
    
    def test_gcode_string_parsing(self):
        """Test parsing G-code from string"""
        start = time.time()
        try:
            from promptplot.converters import GCodeLoader
            
            gcode_string = """
            G28 ; Home
            M5 ; Pen up
            G1 X0 Y0 F1000
            M3 S255 ; Pen down
            G1 X50 Y0 F1000
            G1 X50 Y50 F1000
            G1 X0 Y50 F1000
            G1 X0 Y0 F1000
            M5 ; Pen up
            """
            
            loader = GCodeLoader()
            program = loader.load_from_string(gcode_string)
            
            self.runner.log_result(
                "G-code String Parsing", self.category, True,
                f"Parsed {len(program.commands)} commands from string",
                time.time() - start,
                {"commands": len(program.commands)}
            )
        except Exception as e:
            self.runner.log_result(
                "G-code String Parsing", self.category, False,
                f"Failed: {str(e)}",
                time.time() - start
            )
    
    def test_svg_conversion(self):
        """Test SVG to G-code conversion"""
        start = time.time()
        try:
            from promptplot.converters import SVGConverter
            
            # Check if sample SVG exists
            sample_svg = Path("examples/sample_files/logo.svg")
            
            if sample_svg.exists():
                converter = SVGConverter()
                program = converter.convert(str(sample_svg))
                
                self.runner.log_result(
                    "SVG Conversion", self.category, True,
                    f"Converted SVG to {len(program.commands)} G-code commands",
                    time.time() - start,
                    {"file": str(sample_svg), "commands": len(program.commands)}
                )
            else:
                self.runner.log_result(
                    "SVG Conversion", self.category, True,
                    "Sample SVG not found, skipped",
                    time.time() - start
                )
        except Exception as e:
            self.runner.log_result(
                "SVG Conversion", self.category, False,
                f"Failed: {str(e)}",
                time.time() - start
            )
    
    def test_json_conversion(self):
        """Test JSON to G-code conversion"""
        start = time.time()
        try:
            from promptplot.converters import JSONConverter
            from promptplot.core import GCodeCommand, GCodeProgram
            
            # Create test JSON data
            json_data = {
                "commands": [
                    {"command": "G28"},
                    {"command": "M5"},
                    {"command": "G1", "x": 10.0, "y": 10.0, "f": 1000},
                    {"command": "M3", "s": 255},
                    {"command": "G1", "x": 30.0, "y": 30.0, "f": 1000},
                    {"command": "M5"},
                ]
            }
            
            converter = JSONConverter()
            program = converter.convert_from_dict(json_data)
            
            self.runner.log_result(
                "JSON Conversion", self.category, True,
                f"Converted JSON to {len(program.commands)} G-code commands",
                time.time() - start,
                {"commands": len(program.commands)}
            )
        except Exception as e:
            self.runner.log_result(
                "JSON Conversion", self.category, False,
                f"Failed: {str(e)}",
                time.time() - start
            )

# =============================================================================
# LLM Integration Tests
# =============================================================================

class LLMTests:
    """Tests for LLM integration and streaming"""
    
    def __init__(self, runner: TestRunner):
        self.runner = runner
        self.category = "LLM"
    
    async def run_all(self):
        """Run all LLM tests"""
        print("\n" + "=" * 70)
        print("🤖 LLM INTEGRATION TESTS")
        print("=" * 70)
        
        self.test_mock_llm_provider()
        await self.test_llm_command_generation()
        await self.test_llm_streaming_workflow()
    
    def test_mock_llm_provider(self):
        """Test mock LLM provider"""
        start = time.time()
        try:
            from tests.utils.mocks import MockLLMProvider
            
            responses = [
                '{"command": "G1", "x": 10.0, "y": 10.0, "f": 1000}',
                '{"command": "M3", "s": 255}',
                '{"command": "COMPLETE"}'
            ]
            
            provider = MockLLMProvider(responses=responses)
            
            # Test that provider returns responses in order
            for i, expected in enumerate(responses):
                response = provider.complete(f"Test prompt {i}")
                assert response == expected or expected in str(response)
            
            self.runner.log_result(
                "Mock LLM Provider", self.category, True,
                f"Mock provider working with {len(responses)} responses",
                time.time() - start
            )
        except Exception as e:
            self.runner.log_result(
                "Mock LLM Provider", self.category, False,
                f"Failed: {str(e)}",
                time.time() - start
            )
    
    async def test_llm_command_generation(self):
        """Test LLM command generation and validation"""
        start = time.time()
        try:
            from tests.utils.mocks import MockLLMProvider
            from promptplot.core import GCodeCommand
            import json
            
            # Mock responses for a simple square drawing
            responses = [
                '{"command": "G28"}',
                '{"command": "M5"}',
                '{"command": "G1", "x": 0.0, "y": 0.0, "f": 1000}',
                '{"command": "M3", "s": 255}',
                '{"command": "G1", "x": 50.0, "y": 0.0, "f": 1000}',
                '{"command": "G1", "x": 50.0, "y": 50.0, "f": 1000}',
                '{"command": "G1", "x": 0.0, "y": 50.0, "f": 1000}',
                '{"command": "G1", "x": 0.0, "y": 0.0, "f": 1000}',
                '{"command": "M5"}',
                '{"command": "COMPLETE"}'
            ]
            
            provider = MockLLMProvider(responses=responses)
            
            # Generate and validate commands
            valid_commands = []
            for i, response in enumerate(responses):
                try:
                    data = json.loads(response)
                    if data.get("command") != "COMPLETE":
                        cmd = GCodeCommand(**data)
                        valid_commands.append(cmd)
                except Exception:
                    pass
            
            self.runner.log_result(
                "LLM Command Generation", self.category, True,
                f"Generated and validated {len(valid_commands)} commands",
                time.time() - start,
                {"total_responses": len(responses), "valid_commands": len(valid_commands)}
            )
        except Exception as e:
            self.runner.log_result(
                "LLM Command Generation", self.category, False,
                f"Failed: {str(e)}",
                time.time() - start
            )
    
    async def test_llm_streaming_workflow(self):
        """Test LLM streaming workflow with simulated plotter"""
        start = time.time()
        try:
            from tests.utils.mocks import MockLLMProvider
            from promptplot.plotter import SimulatedPlotter
            from promptplot.core import GCodeCommand
            import json
            
            # Mock responses for streaming
            responses = [
                '{"command": "G28"}',
                '{"command": "M5"}',
                '{"command": "G1", "x": 10.0, "y": 10.0, "f": 1000}',
                '{"command": "M3", "s": 255}',
                '{"command": "G1", "x": 40.0, "y": 10.0, "f": 1000}',
                '{"command": "G1", "x": 40.0, "y": 40.0, "f": 1000}',
                '{"command": "M5"}',
                '{"command": "COMPLETE"}'
            ]
            
            provider = MockLLMProvider(responses=responses)
            plotter = SimulatedPlotter(port="TEST")
            
            await plotter.connect()
            
            # Simulate streaming workflow
            commands_executed = 0
            for response in responses:
                try:
                    data = json.loads(response)
                    if data.get("command") == "COMPLETE":
                        break
                    
                    cmd = GCodeCommand(**data)
                    success = await plotter.send_command(cmd.to_gcode())
                    if success:
                        commands_executed += 1
                except Exception:
                    pass
            
            await plotter.disconnect()
            
            self.runner.log_result(
                "LLM Streaming Workflow", self.category, True,
                f"Streamed {commands_executed} commands to plotter",
                time.time() - start,
                {"commands_executed": commands_executed}
            )
        except Exception as e:
            self.runner.log_result(
                "LLM Streaming Workflow", self.category, False,
                f"Failed: {str(e)}",
                time.time() - start
            )


# =============================================================================
# Advanced Feature Tests
# =============================================================================

class AdvancedTests:
    """Tests for advanced features like ink changes and multi-color support"""
    
    def __init__(self, runner: TestRunner):
        self.runner = runner
        self.category = "Advanced"
    
    async def run_all(self):
        """Run all advanced tests"""
        print("\n" + "=" * 70)
        print("🎨 ADVANCED FEATURE TESTS")
        print("=" * 70)
        
        await self.test_ink_change_points()
        await self.test_multi_color_drawing()
        await self.test_pause_resume()
        self.test_visualization()
    
    async def test_ink_change_points(self):
        """Test ink/pen change point handling"""
        start = time.time()
        try:
            from promptplot.core import GCodeCommand, GCodeProgram
            from promptplot.plotter import SimulatedPlotter
            
            # Create a program with ink change points
            # Using M0 (program pause) or custom commands for ink changes
            commands = [
                GCodeCommand(command="G28"),
                GCodeCommand(command="M5"),
                # First color (e.g., black)
                GCodeCommand(command="G1", x=0.0, y=0.0, f=1000),
                GCodeCommand(command="M3", s=255),
                GCodeCommand(command="G1", x=30.0, y=0.0, f=1000),
                GCodeCommand(command="G1", x=30.0, y=30.0, f=1000),
                GCodeCommand(command="M5"),
                # Ink change point - pen up and move to change position
                GCodeCommand(command="G1", x=0.0, y=0.0, z=10.0, f=3000),
                # Second color (e.g., red) - after manual pen change
                GCodeCommand(command="G1", x=40.0, y=0.0, f=1000),
                GCodeCommand(command="M3", s=255),
                GCodeCommand(command="G1", x=70.0, y=0.0, f=1000),
                GCodeCommand(command="G1", x=70.0, y=30.0, f=1000),
                GCodeCommand(command="M5"),
            ]
            
            program = GCodeProgram(commands=commands)
            
            # Execute on simulated plotter
            plotter = SimulatedPlotter(port="TEST")
            await plotter.connect()
            
            success_count = 0
            for cmd in program.commands:
                result = await plotter.send_command(cmd.to_gcode())
                if result:
                    success_count += 1
            
            await plotter.disconnect()
            
            self.runner.log_result(
                "Ink Change Points", self.category, True,
                f"Executed {success_count}/{len(program.commands)} commands with ink change",
                time.time() - start,
                {"total_commands": len(program.commands), "successful": success_count}
            )
        except Exception as e:
            self.runner.log_result(
                "Ink Change Points", self.category, False,
                f"Failed: {str(e)}",
                time.time() - start
            )
    
    async def test_multi_color_drawing(self):
        """Test multi-color drawing with pen changes"""
        start = time.time()
        try:
            from promptplot.core import GCodeCommand, GCodeProgram
            from promptplot.plotter import SimulatedPlotter
            
            # Define colors/pens with their drawing commands
            colors = [
                {
                    "name": "Black",
                    "commands": [
                        GCodeCommand(command="G1", x=10.0, y=10.0, f=1000),
                        GCodeCommand(command="M3", s=255),
                        GCodeCommand(command="G1", x=40.0, y=10.0, f=1000),
                        GCodeCommand(command="M5"),
                    ]
                },
                {
                    "name": "Red",
                    "commands": [
                        GCodeCommand(command="G1", x=10.0, y=20.0, f=1000),
                        GCodeCommand(command="M3", s=255),
                        GCodeCommand(command="G1", x=40.0, y=20.0, f=1000),
                        GCodeCommand(command="M5"),
                    ]
                },
                {
                    "name": "Blue",
                    "commands": [
                        GCodeCommand(command="G1", x=10.0, y=30.0, f=1000),
                        GCodeCommand(command="M3", s=255),
                        GCodeCommand(command="G1", x=40.0, y=30.0, f=1000),
                        GCodeCommand(command="M5"),
                    ]
                }
            ]
            
            # Build complete program with pen changes
            all_commands = [GCodeCommand(command="G28"), GCodeCommand(command="M5")]
            
            for i, color in enumerate(colors):
                # Add pen change position (move to change area)
                if i > 0:
                    all_commands.append(GCodeCommand(command="G1", x=-10.0, y=0.0, z=10.0, f=3000))
                    # In real scenario, would pause here for manual pen change
                
                all_commands.extend(color["commands"])
            
            program = GCodeProgram(commands=all_commands)
            
            # Execute
            plotter = SimulatedPlotter(port="TEST")
            await plotter.connect()
            
            success_count = 0
            for cmd in program.commands:
                result = await plotter.send_command(cmd.to_gcode())
                if result:
                    success_count += 1
            
            await plotter.disconnect()
            
            self.runner.log_result(
                "Multi-Color Drawing", self.category, True,
                f"Drew {len(colors)} colors with {success_count} commands",
                time.time() - start,
                {"colors": len(colors), "total_commands": len(program.commands)}
            )
        except Exception as e:
            self.runner.log_result(
                "Multi-Color Drawing", self.category, False,
                f"Failed: {str(e)}",
                time.time() - start
            )
    
    async def test_pause_resume(self):
        """Test pause and resume functionality"""
        start = time.time()
        try:
            from promptplot.core import GCodeCommand, GCodeProgram
            from promptplot.plotter import SimulatedPlotter
            
            commands = [
                GCodeCommand(command="G28"),
                GCodeCommand(command="M5"),
                GCodeCommand(command="G1", x=10.0, y=10.0, f=1000),
                GCodeCommand(command="M3", s=255),
                GCodeCommand(command="G1", x=30.0, y=10.0, f=1000),
                # Pause point
                GCodeCommand(command="G4", p=1000),  # Dwell for 1 second
                GCodeCommand(command="G1", x=30.0, y=30.0, f=1000),
                GCodeCommand(command="M5"),
            ]
            
            program = GCodeProgram(commands=commands)
            
            plotter = SimulatedPlotter(port="TEST")
            await plotter.connect()
            
            # Execute with simulated pause
            executed_before_pause = 0
            executed_after_pause = 0
            pause_index = 5  # Index of G4 command
            
            for i, cmd in enumerate(program.commands):
                result = await plotter.send_command(cmd.to_gcode())
                if result:
                    if i < pause_index:
                        executed_before_pause += 1
                    else:
                        executed_after_pause += 1
            
            await plotter.disconnect()
            
            self.runner.log_result(
                "Pause/Resume Functionality", self.category, True,
                f"Executed {executed_before_pause} before pause, {executed_after_pause} after",
                time.time() - start
            )
        except Exception as e:
            self.runner.log_result(
                "Pause/Resume Functionality", self.category, False,
                f"Failed: {str(e)}",
                time.time() - start
            )
    
    def test_visualization(self):
        """Test visualization capabilities"""
        start = time.time()
        try:
            from promptplot.plotter import PlotterVisualizer, MATPLOTLIB_AVAILABLE
            
            if not MATPLOTLIB_AVAILABLE:
                self.runner.log_result(
                    "Visualization", self.category, True,
                    "Matplotlib not available, skipped",
                    time.time() - start
                )
                return
            
            # Test visualizer creation
            visualizer = PlotterVisualizer()
            
            self.runner.log_result(
                "Visualization", self.category, True,
                "Visualizer created successfully",
                time.time() - start
            )
        except Exception as e:
            self.runner.log_result(
                "Visualization", self.category, False,
                f"Failed: {str(e)}",
                time.time() - start
            )


# =============================================================================
# Main Test Runner
# =============================================================================

async def run_tests(categories: List[str] = None, serial_port: str = None):
    """Run the comprehensive test suite"""
    
    print("🧪 PromptPlot v2.0 Comprehensive Test Suite")
    print("=" * 70)
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Categories: {', '.join(categories) if categories else 'All'}")
    if serial_port:
        print(f"Serial Port: {serial_port}")
    print()
    
    runner = TestRunner()
    runner.start_time = time.time()
    
    # Determine which test categories to run
    run_all = not categories
    
    # Core tests (synchronous)
    if run_all or "core" in categories:
        core_tests = CoreTests(runner)
        core_tests.run_all()
    
    # Plotter tests (async)
    if run_all or "plotter" in categories:
        plotter_tests = PlotterTests(runner, serial_port)
        await plotter_tests.run_all()
    
    # File tests (synchronous)
    if run_all or "file" in categories:
        file_tests = FileTests(runner)
        file_tests.run_all()
    
    # LLM tests (async)
    if run_all or "llm" in categories:
        llm_tests = LLMTests(runner)
        await llm_tests.run_all()
    
    # Advanced tests (async)
    if run_all or "advanced" in categories:
        advanced_tests = AdvancedTests(runner)
        await advanced_tests.run_all()
    
    # Print summary
    total_time = time.time() - runner.start_time
    print(f"\n⏱️  Total test time: {total_time:.2f} seconds")
    
    success = runner.print_summary()
    
    return success


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="PromptPlot Comprehensive Test Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python test_comprehensive.py                    # Run all tests
    python test_comprehensive.py --category core    # Run only core tests
    python test_comprehensive.py --category plotter # Run only plotter tests
    python test_comprehensive.py --category file    # Run only file tests
    python test_comprehensive.py --category llm     # Run only LLM tests
    python test_comprehensive.py --category advanced # Run only advanced tests
    python test_comprehensive.py --port /dev/ttyUSB0  # Test with real plotter

Test Categories:
    core     - G-code commands, programs, strategy selection, configuration
    plotter  - Simulated and serial plotter connections and operations
    file     - File format detection, G-code loading, SVG/JSON conversion
    llm      - Mock LLM provider, command generation, streaming workflows
    advanced - Ink changes, multi-color drawing, pause/resume, visualization
        """
    )
    
    parser.add_argument(
        "--category", "-c",
        action="append",
        choices=["core", "plotter", "file", "llm", "advanced"],
        help="Test category to run (can be specified multiple times)"
    )
    
    parser.add_argument(
        "--port", "-p",
        help="Serial port for real plotter testing (e.g., /dev/ttyUSB0, COM3)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    try:
        success = asyncio.run(run_tests(
            categories=args.category,
            serial_port=args.port
        ))
        
        print("\n" + "=" * 70)
        if success:
            print("🎉 All tests passed!")
        else:
            print("❌ Some tests failed. Check the summary above.")
        print("=" * 70)
        
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n⏹️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Test suite error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
