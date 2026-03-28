#!/usr/bin/env python3
"""
Multiple Shapes Example

This example demonstrates drawing multiple shapes in sequence:
- Positioning shapes at different coordinates
- Managing drawing order
- Combining different geometric shapes
- Optimizing pen movements
"""

import asyncio
import sys
import os

# Add the parent directory to the path so we can import promptplot
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from promptplot.workflows import SimpleBatchWorkflow
from promptplot.plotter import SimulatedPlotter


async def main():
    """Main example function."""
    print("PromptPlot Multiple Shapes Example")
    print("=" * 42)
    
    # Set up plotter with larger canvas for multiple shapes
    print("1. Setting up plotter...")
    plotter = SimulatedPlotter(
        visualize=True,
        canvas_size=(300, 300),  # Larger canvas
        save_images=True,
        pen_color='blue'
    )
    
    workflow = SimpleBatchWorkflow(plotter=plotter)
    print("   ✓ Plotter and workflow ready")
    
    # Define a collection of shapes with positions
    shapes = [
        {
            'name': 'Center Square',
            'prompt': 'Draw a 40mm square centered at origin (0, 0)',
            'description': 'Main central square'
        },
        {
            'name': 'Top Circle',
            'prompt': 'Draw a circle with 20mm radius centered at (0, 60)',
            'description': 'Circle above the square'
        },
        {
            'name': 'Bottom Triangle',
            'prompt': 'Draw an equilateral triangle with 30mm sides centered at (0, -60)',
            'description': 'Triangle below the square'
        },
        {
            'name': 'Left Diamond',
            'prompt': 'Draw a diamond (rotated square) with 25mm diagonal at (-60, 0)',
            'description': 'Diamond to the left'
        },
        {
            'name': 'Right Hexagon',
            'prompt': 'Draw a regular hexagon with 15mm radius at (60, 0)',
            'description': 'Hexagon to the right'
        },
        {
            'name': 'Corner Decorations',
            'prompt': 'Draw small 8mm circles at corners: (80, 80), (-80, 80), (-80, -80), (80, -80)',
            'description': 'Corner decorative elements'
        }
    ]
    
    print(f"\n2. Drawing {len(shapes)} shapes...")
    
    total_commands = 0
    total_time = 0
    
    for i, shape in enumerate(shapes, 1):
        print(f"\n   Shape {i}/{len(shapes)}: {shape['name']}")
        print(f"   Description: {shape['description']}")
        print(f"   Prompt: {shape['prompt']}")
        
        try:
            result = await workflow.execute(shape['prompt'])
            
            if result.success:
                commands = len(result.commands)
                time_taken = result.execution_time
                total_commands += commands
                total_time += time_taken
                
                print(f"   ✓ Success: {commands} commands, {time_taken:.2f}s")
            else:
                print(f"   ✗ Failed: {result.error_message}")
                
        except Exception as e:
            print(f"   ✗ Error: {e}")
        
        # Small delay for visualization
        await asyncio.sleep(0.5)
    
    # Draw connecting lines between shapes
    print(f"\n3. Adding connecting elements...")
    
    connecting_elements = [
        'Draw a line from (0, 20) to (0, 40) connecting square to circle',
        'Draw a line from (0, -20) to (0, -40) connecting square to triangle',
        'Draw a line from (-20, 0) to (-40, 0) connecting square to diamond',
        'Draw a line from (20, 0) to (40, 0) connecting square to hexagon'
    ]
    
    for element in connecting_elements:
        try:
            result = await workflow.execute(element)
            if result.success:
                total_commands += len(result.commands)
                total_time += result.execution_time
                print(f"   ✓ Connection added")
            else:
                print(f"   ✗ Connection failed")
        except Exception as e:
            print(f"   ✗ Connection error: {e}")
        
        await asyncio.sleep(0.3)
    
    # Summary
    print(f"\n4. Drawing Summary:")
    print(f"   Total shapes drawn: {len(shapes)}")
    print(f"   Total G-code commands: {total_commands}")
    print(f"   Total execution time: {total_time:.2f} seconds")
    print(f"   Average time per shape: {total_time/len(shapes):.2f} seconds")
    
    # Optional: Create a border around everything
    print(f"\n5. Adding decorative border...")
    
    try:
        border_prompt = "Draw a decorative rectangular border with rounded corners, 280mm wide and 280mm tall, centered at origin"
        result = await workflow.execute(border_prompt)
        
        if result.success:
            print(f"   ✓ Border added: {len(result.commands)} commands")
            total_commands += len(result.commands)
        else:
            print(f"   ✗ Border failed: {result.error_message}")
            
    except Exception as e:
        print(f"   ✗ Border error: {e}")
    
    print(f"\n6. Multiple shapes example completed!")
    print(f"   Final total: {total_commands} G-code commands")
    print(f"   Check the visualization for the complete drawing.")
    
    # Keep visualization open
    input("\nPress Enter to exit...")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExample interrupted by user")
    except Exception as e:
        print(f"\nExample failed: {e}")
        sys.exit(1)