#!/usr/bin/env python3
"""
Simple Drawing Example

This example demonstrates the most basic usage of PromptPlot:
- Setting up a simulated plotter
- Creating a simple workflow
- Executing a drawing prompt
- Handling results

This is the recommended starting point for new users.
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
    print("PromptPlot Basic Drawing Example")
    print("=" * 40)
    
    # Step 1: Set up a simulated plotter
    print("1. Setting up simulated plotter...")
    plotter = SimulatedPlotter(
        visualize=True,          # Show real-time visualization
        canvas_size=(200, 200),  # 200x200mm canvas
        save_images=True         # Save visualization images
    )
    print("   ✓ Simulated plotter ready")
    
    # Step 2: Create a simple workflow
    print("2. Creating workflow...")
    workflow = SimpleBatchWorkflow(plotter=plotter)
    print("   ✓ Simple batch workflow created")
    
    # Step 3: Define drawing prompts
    prompts = [
        "Draw a 50mm square centered at origin",
        "Draw a circle with 25mm radius at position (60, 60)",
        "Draw a triangle with 40mm sides at position (-60, -60)"
    ]
    
    # Step 4: Execute each drawing
    print("3. Executing drawings...")
    
    for i, prompt in enumerate(prompts, 1):
        print(f"   Drawing {i}: {prompt}")
        
        try:
            # Execute the drawing
            result = await workflow.execute(prompt)
            
            if result.success:
                print(f"   ✓ Success: {len(result.commands)} G-code commands generated")
                print(f"     Execution time: {result.execution_time:.2f} seconds")
            else:
                print(f"   ✗ Failed: {result.error_message}")
                
        except Exception as e:
            print(f"   ✗ Error: {e}")
        
        # Small delay between drawings for visualization
        await asyncio.sleep(1)
    
    print("\n4. Example completed!")
    print("   Check the visualization window for the drawings.")
    print("   Generated images are saved in the results directory.")
    
    # Keep the visualization window open
    input("\nPress Enter to exit...")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExample interrupted by user")
    except Exception as e:
        print(f"\nExample failed: {e}")
        sys.exit(1)