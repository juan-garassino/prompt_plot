#!/usr/bin/env python3
"""
Quick Start Example for PromptPlot v2.0

This is the fastest way to get started with PromptPlot.
Run this example to see basic G-code generation and plotter simulation.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the parent directory to the path so we can import promptplot
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from promptplot.core.models import GCodeCommand, GCodeProgram
    from promptplot.plotter.simulated import SimulatedPlotter
    from promptplot.strategies import StrategySelector
    from tests.utils.mocks import MockLLMProvider
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure PromptPlot is installed: pip install -e .")
    sys.exit(1)


async def quick_demo():
    """Quick demonstration of PromptPlot capabilities."""
    print("🎨 PromptPlot v2.0 Quick Start Demo")
    print("=" * 40)
    
    # 1. Strategy Selection Demo
    print("1. Testing strategy selection...")
    selector = StrategySelector()
    
    prompts = [
        "Draw a square",
        "Draw a circle", 
        "Draw a curved flower"
    ]
    
    for prompt in prompts:
        strategy = selector.select_strategy(prompt)
        print(f"   '{prompt}' → {strategy.__class__.__name__}")
    
    # 2. G-code Generation Demo
    print("\n2. Generating sample G-code...")
    
    # Create sample G-code commands
    commands = [
        GCodeCommand(command="G28", comment="Home all axes"),
        GCodeCommand(command="G1", x=10.0, y=10.0, f=1000, comment="Move to start"),
        GCodeCommand(command="M3", s=255, comment="Pen down"),
        GCodeCommand(command="G1", x=30.0, y=10.0, f=1000, comment="Draw line 1"),
        GCodeCommand(command="G1", x=30.0, y=30.0, f=1000, comment="Draw line 2"),
        GCodeCommand(command="G1", x=10.0, y=30.0, f=1000, comment="Draw line 3"),
        GCodeCommand(command="G1", x=10.0, y=10.0, f=1000, comment="Draw line 4"),
        GCodeCommand(command="M5", comment="Pen up"),
        GCodeCommand(command="G28", comment="Return home")
    ]
    
    program = GCodeProgram(commands=commands)
    print(f"   ✅ Created G-code program with {len(program.commands)} commands")
    
    # 3. Plotter Simulation Demo
    print("\n3. Testing plotter simulation...")
    
    plotter = SimulatedPlotter(port="DEMO", visualize=True)
    
    try:
        async with plotter:
            print("   🔗 Connected to simulated plotter")
            
            # Send commands to plotter
            for i, command in enumerate(commands, 1):
                success = await plotter.send_command(command.command)
                if success:
                    print(f"   {i:2d}. ✅ {command.command} ; {command.comment}")
                else:
                    print(f"   {i:2d}. ❌ Failed: {command.command}")
                
                # Small delay for visualization
                await asyncio.sleep(0.2)
            
            print("   📊 Drawing completed!")
            
    except Exception as e:
        print(f"   ❌ Plotter error: {e}")
        return False
    
    # 4. Mock LLM Demo
    print("\n4. Testing mock LLM provider...")
    
    mock_llm = MockLLMProvider(responses=[
        '{"command": "G1", "x": 50.0, "y": 50.0, "f": 1000, "comment": "Test command"}'
    ])
    
    try:
        response = await mock_llm.acomplete("Generate a G-code command")
        print(f"   📝 LLM Response: {response}")
        
        # Parse the response
        import json
        parsed = json.loads(response)
        test_cmd = GCodeCommand(**parsed)
        print(f"   ✅ Parsed command: {test_cmd.command}")
        
    except Exception as e:
        print(f"   ❌ LLM error: {e}")
        return False
    
    print("\n🎉 Demo completed successfully!")
    print("\nNext steps:")
    print("• Try: make example-llm (with real LLM)")
    print("• Try: make example-streaming")
    print("• Try: make example-cli")
    print("• Check examples/ directory for more demos")
    
    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(quick_demo())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⏹️  Demo interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n💥 Demo failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)