#!/usr/bin/env python3
"""
SVG to G-code Conversion Example

This example demonstrates converting SVG files to G-code:
- Loading and parsing SVG files
- Configuring conversion settings
- Converting paths to G-code
- Plotting the converted G-code
- Saving results
"""

import asyncio
import sys
import os
import argparse

# Add the parent directory to the path so we can import promptplot
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from promptplot.workflows import FilePlottingWorkflow
from promptplot.plotter import SimulatedPlotter
from promptplot.converters import SVGConverter, SVGSettings
from promptplot.converters.file_detector import FileDetector


def create_sample_svg(filename):
    """Create a sample SVG file for testing."""
    svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100">
    <!-- Simple logo design -->
    <rect x="10" y="10" width="80" height="80" fill="none" stroke="black" stroke-width="2"/>
    <circle cx="50" cy="50" r="25" fill="none" stroke="black" stroke-width="2"/>
    <path d="M 30 30 L 70 30 L 70 70 L 30 70 Z" fill="none" stroke="black" stroke-width="1"/>
    <text x="50" y="55" text-anchor="middle" font-family="Arial" font-size="12">LOGO</text>
</svg>'''
    
    with open(filename, 'w') as f:
        f.write(svg_content)
    
    print(f"Created sample SVG file: {filename}")


async def convert_and_plot_svg(svg_file, settings=None):
    """Convert SVG file and plot the result."""
    print(f"\nConverting SVG file: {svg_file}")
    
    # Check if file exists
    if not os.path.exists(svg_file):
        print(f"Error: File {svg_file} not found")
        return False
    
    # Detect file format
    detector = FileDetector()
    file_type = detector.detect_format(svg_file)
    print(f"Detected file type: {file_type}")
    
    if file_type != "svg":
        print(f"Error: Expected SVG file, got {file_type}")
        return False
    
    # Set up plotter
    plotter = SimulatedPlotter(
        visualize=True,
        canvas_size=(200, 200),
        save_images=True
    )
    
    # Method 1: Direct file plotting (automatic conversion)
    print("\n--- Method 1: Direct File Plotting ---")
    
    workflow = FilePlottingWorkflow(plotter=plotter)
    
    try:
        result = await workflow.plot_file(svg_file)
        
        if result.success:
            print(f"✓ Direct plotting successful:")
            print(f"  Commands generated: {len(result.commands)}")
            print(f"  Execution time: {result.execution_time:.2f}s")
        else:
            print(f"✗ Direct plotting failed: {result.error_message}")
            
    except Exception as e:
        print(f"✗ Direct plotting error: {e}")
    
    # Method 2: Manual conversion with custom settings
    print("\n--- Method 2: Manual Conversion ---")
    
    # Use provided settings or create default ones
    if settings is None:
        settings = SVGSettings(
            resolution=0.1,           # 0.1mm resolution
            scale_factor=2.0,         # Scale up 2x
            optimize_order=True,      # Optimize drawing order
            pen_up_height=5,         # 5mm pen up
            pen_down_height=0,       # 0mm pen down
            travel_speed=3000,       # 3000 mm/min travel
            draw_speed=1000,         # 1000 mm/min drawing
            simplify_paths=True,     # Simplify complex paths
            offset_x=0,              # No X offset
            offset_y=0               # No Y offset
        )
    
    print("Conversion settings:")
    print(f"  Resolution: {settings.resolution}mm")
    print(f"  Scale factor: {settings.scale_factor}x")
    print(f"  Travel speed: {settings.travel_speed} mm/min")
    print(f"  Draw speed: {settings.draw_speed} mm/min")
    
    try:
        # Create converter with settings
        converter = SVGConverter(settings)
        
        # Convert SVG to G-code program
        gcode_program = converter.convert(svg_file)
        
        print(f"✓ Conversion successful:")
        print(f"  Original SVG elements: {converter.stats.original_elements if hasattr(converter, 'stats') else 'N/A'}")
        print(f"  Generated commands: {len(gcode_program.commands)}")
        
        # Plot the converted G-code
        result = await workflow.plot_gcode_program(gcode_program)
        
        if result.success:
            print(f"✓ Manual plotting successful:")
            print(f"  Execution time: {result.execution_time:.2f}s")
        else:
            print(f"✗ Manual plotting failed: {result.error_message}")
        
        # Save G-code to file
        output_file = svg_file.replace('.svg', '_converted.gcode')
        with open(output_file, 'w') as f:
            for command in gcode_program.commands:
                f.write(f"{command.to_gcode()}\n")
        
        print(f"✓ G-code saved to: {output_file}")
        
        return True
        
    except Exception as e:
        print(f"✗ Manual conversion error: {e}")
        return False


async def main():
    """Main example function."""
    parser = argparse.ArgumentParser(description='SVG to G-code conversion example')
    parser.add_argument('svg_file', nargs='?', help='SVG file to convert')
    parser.add_argument('--create-sample', action='store_true', help='Create a sample SVG file')
    parser.add_argument('--scale', type=float, default=1.0, help='Scale factor (default: 1.0)')
    parser.add_argument('--resolution', type=float, default=0.1, help='Resolution in mm (default: 0.1)')
    parser.add_argument('--speed', type=int, default=1000, help='Drawing speed in mm/min (default: 1000)')
    
    args = parser.parse_args()
    
    print("PromptPlot SVG to G-code Conversion Example")
    print("=" * 50)
    
    # Create sample file if requested
    if args.create_sample:
        sample_file = "sample_logo.svg"
        create_sample_svg(sample_file)
        if not args.svg_file:
            args.svg_file = sample_file
    
    # Check if we have a file to process
    if not args.svg_file:
        print("Error: No SVG file specified")
        print("Usage: python svg_to_gcode.py <svg_file>")
        print("   or: python svg_to_gcode.py --create-sample")
        return
    
    # Create custom settings from command line arguments
    settings = SVGSettings(
        resolution=args.resolution,
        scale_factor=args.scale,
        draw_speed=args.speed,
        travel_speed=args.speed * 3,  # Travel 3x faster than drawing
        optimize_order=True,
        simplify_paths=True,
        pen_up_height=5,
        pen_down_height=0
    )
    
    # Convert and plot the SVG
    success = await convert_and_plot_svg(args.svg_file, settings)
    
    if success:
        print(f"\n✓ SVG conversion example completed successfully!")
        print("  Check the visualization window for the plotted result.")
        print("  Generated G-code file has been saved.")
        
        # Keep visualization open
        input("\nPress Enter to exit...")
    else:
        print(f"\n✗ SVG conversion example failed!")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExample interrupted by user")
    except Exception as e:
        print(f"\nExample failed: {e}")
        sys.exit(1)