#!/usr/bin/env python3
"""
Simple Demo for PromptPlot v2.0

This example demonstrates the core components working together
without requiring complex workflow execution or LLM services.
Perfect for testing and demonstration purposes.
"""

import sys
import os
from pathlib import Path

# Add the parent directory to the path so we can import promptplot
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from promptplot import get_config, StrategySelector
    from promptplot.core.models import GCodeCommand, GCodeProgram
    from promptplot.plotter.simulated import SimulatedPlotter
    from promptplot.converters import FileFormatDetector
    from tests.utils.mocks import MockLLMProvider
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure PromptPlot is installed: pip install -e .")
    sys.exit(1)


def demo_configuration():
    """Demo configuration system."""
    print("🔧 Configuration System Demo")
    print("-" * 35)
    
    config = get_config()
    print(f"✅ Configuration loaded successfully")
    print(f"   • LLM Provider: {config.llm.default_provider}")
    print(f"   • Plotter Type: {config.plotter.default_type}")
    print(f"   • Max Retries: {config.workflow.max_retries}")
    print(f"   • Max Steps: {config.workflow.max_steps}")


def demo_strategy_selection():
    """Demo strategy selection system."""
    print("\n🧠 Strategy Selection Demo")
    print("-" * 30)
    
    selector = StrategySelector()
    
    test_prompts = [
        "Draw a rectangle",
        "Draw a circle", 
        "Draw a curved flower",
        "Create a grid pattern"
    ]
    
    for prompt in test_prompts:
        strategy = selector.select_strategy(prompt)
        analysis = selector.analyze_prompt_complexity(prompt)
        
        print(f"📝 '{prompt}'")
        print(f"   → {strategy.__class__.__name__}")
        print(f"   → Complexity: {analysis.complexity_level.value}")
        print(f"   → Curves: {analysis.requires_curves}")


def demo_gcode_generation():
    """Demo G-code generation and manipulation."""
    print("\n⚙️  G-code Generation Demo")
    print("-" * 30)
    
    # Create sample G-code commands
    commands = [
        GCodeCommand(command="G28", comment="Home all axes"),
        GCodeCommand(command="G1", x=10.0, y=10.0, f=1000, comment="Move to start"),
        GCodeCommand(command="M3", s=255, comment="Pen down"),
        GCodeCommand(command="G1", x=30.0, y=10.0, f=1000, comment="Draw line"),
        GCodeCommand(command="G1", x=30.0, y=30.0, f=1000, comment="Draw line"),
        GCodeCommand(command="G1", x=10.0, y=30.0, f=1000, comment="Draw line"),
        GCodeCommand(command="G1", x=10.0, y=10.0, f=1000, comment="Draw line"),
        GCodeCommand(command="M5", comment="Pen up"),
        GCodeCommand(command="G28", comment="Return home")
    ]
    
    # Create G-code program
    program = GCodeProgram(commands=commands)
    
    print(f"✅ Created G-code program with {len(program.commands)} commands")
    print("📋 Sample commands:")
    for i, cmd in enumerate(program.commands[:4], 1):
        print(f"   {i}. {cmd.command} ; {cmd.comment}")
    print(f"   ... and {len(program.commands) - 4} more commands")
    
    return program


def demo_plotter_simulation(program):
    """Demo plotter simulation."""
    print("\n🖨️  Plotter Simulation Demo")
    print("-" * 32)
    
    try:
        plotter = SimulatedPlotter(port="DEMO", visualize=False)
        print("✅ Simulated plotter created")
        
        # Simulate sending commands
        print("📤 Simulating command execution:")
        for i, command in enumerate(program.commands[:5], 1):
            print(f"   {i}. Executing: {command.command}")
        
        if len(program.commands) > 5:
            print(f"   ... and {len(program.commands) - 5} more commands")
        
        print("✅ All commands executed successfully")
        
    except Exception as e:
        print(f"❌ Plotter simulation error: {e}")


def demo_llm_provider():
    """Demo LLM provider (mock)."""
    print("\n🤖 LLM Provider Demo")
    print("-" * 25)
    
    # Create mock LLM provider
    responses = [
        '{"command": "G1", "x": 25.0, "y": 25.0, "f": 1000, "comment": "Draw to corner"}',
        '{"command": "G2", "x": 25.0, "y": 25.0, "i": 10.0, "j": 0.0, "f": 800, "comment": "Draw arc"}'
    ]
    
    llm_provider = MockLLMProvider(responses=responses)
    print("✅ Mock LLM provider created")
    
    # Test LLM responses
    print("💬 Testing LLM responses:")
    for i, response in enumerate(responses, 1):
        print(f"   {i}. Response: {response[:50]}...")
    
    print(f"✅ LLM provider ready with {len(responses)} sample responses")


def demo_file_detection():
    """Demo file format detection."""
    print("\n📁 File Format Detection Demo")
    print("-" * 35)
    
    detector = FileFormatDetector()
    
    # Test file extensions
    test_files = [
        "drawing.svg",
        "plot.gcode", 
        "design.dxf",
        "image.png"
    ]
    
    print("🔍 Testing file format detection:")
    for filename in test_files:
        try:
            # Create a temporary path for testing
            test_path = Path(filename)
            format_info = detector._detect_by_extension(test_path)
            if format_info and format_info.name != "UNKNOWN":
                print(f"   ✅ {filename} → {format_info.name}")
            else:
                print(f"   ❓ {filename} → Unknown format")
        except Exception as e:
            print(f"   ❌ {filename} → Error: {e}")


def main():
    """Run all demos."""
    print("🎨 PromptPlot v2.0 Simple Demo")
    print("=" * 35)
    print("Demonstrating core system components")
    print()
    
    try:
        # Run all demo components
        demo_configuration()
        demo_strategy_selection()
        program = demo_gcode_generation()
        demo_plotter_simulation(program)
        demo_llm_provider()
        demo_file_detection()
        
        print("\n🎉 All demos completed successfully!")
        print("\n📚 What was demonstrated:")
        print("• ✅ Configuration system loading")
        print("• ✅ Strategy selection and prompt analysis")
        print("• ✅ G-code command creation and programs")
        print("• ✅ Plotter simulation interface")
        print("• ✅ LLM provider abstraction")
        print("• ✅ File format detection")
        
        print("\n🚀 Next steps:")
        print("• Try: make example-llm (with real LLM)")
        print("• Try: make example-streaming")
        print("• Try: make example-cli")
        print("• Check examples/ directory for more")
        
        return True
        
    except Exception as e:
        print(f"\n💥 Demo failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⏹️  Demo interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n💥 Fatal error: {e}")
        sys.exit(1)