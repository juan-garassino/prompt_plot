#!/usr/bin/env python3
"""
LLM to Plotter Demo - Simple version with frame-based animation

This demo:
1. Uses an LLM (OpenAI/Gemini) to generate G-code from a prompt OR loads from file
2. Sends the generated G-code to a real pen plotter
3. Saves PNG frames during plotting (one per line drawn)
4. Creates animated GIF at the end showing progressive drawing
5. Generates JSON report with statistics

Usage Examples:

    # Generate G-code with LLM and plot with frames/GIF
    python examples/demo_llm_to_plotter_simple.py /dev/cu.usbserial-14220 --prompt "draw a triangle"

    # Plot from existing G-code file
    python examples/demo_llm_to_plotter_simple.py /dev/cu.usbserial-14220 --file my_drawing.gcode

    # Dry run (no plotter, just generate G-code and preview)
    python examples/demo_llm_to_plotter_simple.py /dev/cu.usbserial-14220 --dry-run --prompt "draw a star"

    # With JSON report
    python examples/demo_llm_to_plotter_simple.py /dev/cu.usbserial-14220 --report --prompt "draw a circle"

    # Different LLM provider
    python examples/demo_llm_to_plotter_simple.py /dev/cu.usbserial-14220 --provider gemini --prompt "draw a house"
    
    # Skip frame saving (faster, no animation)
    python examples/demo_llm_to_plotter_simple.py /dev/cu.usbserial-14220 --no-frames --prompt "draw a square"
"""

import asyncio
import sys
import os
import argparse
import time
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from promptplot import SimpleGCodeWorkflow, get_config
from promptplot.plotter import SerialPlotter
from promptplot.llm.providers import OpenAIProvider, GeminiProvider
from promptplot.core.models import GCodeCommand, GCodeProgram
from promptplot.plotter.visualizer import PlotterVisualizer


async def generate_gcode(prompt: str, provider: str = "openai"):
    """Generate G-code using LLM."""
    print(f"\n🤖 Generating G-code with {provider}...")
    print(f"   Prompt: '{prompt}'")
    
    # Create LLM provider
    if provider == "openai":
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            print("❌ OPENAI_API_KEY not set")
            return None
        llm_provider = OpenAIProvider(model='gpt-4o-mini', timeout=120)
    elif provider == "gemini":
        api_key = os.environ.get('GOOGLE_API_KEY')
        if not api_key:
            print("❌ GOOGLE_API_KEY not set")
            return None
        llm_provider = GeminiProvider(model='models/gemini-1.5-flash', timeout=120)
    else:
        print(f"❌ Unknown provider: {provider}")
        return None
    
    # Create workflow and generate
    workflow = SimpleGCodeWorkflow(
        llm=llm_provider.llm,
        max_retries=3,
        max_steps=10
    )
    
    result = await workflow.run(prompt=prompt)
    
    if result and result.get('commands_count', 0) > 0:
        print(f"✅ Generated {result['commands_count']} G-code commands")
        return result
    else:
        print("❌ Failed to generate G-code")
        return None


def load_gcode_from_file(file_path: str) -> dict:
    """Load G-code from a file."""
    print(f"\n📂 Loading G-code from file: {file_path}")
    
    try:
        path = Path(file_path)
        if not path.exists():
            print(f"❌ File not found: {file_path}")
            return None
        
        with open(path, 'r') as f:
            gcode = f.read()
        
        # Count non-empty, non-comment lines
        lines = [l.strip() for l in gcode.split('\n') if l.strip() and not l.strip().startswith(';')]
        
        print(f"✅ Loaded {len(lines)} G-code commands from {path.name}")
        
        return {
            'gcode': gcode,
            'commands_count': len(lines),
            'source': 'file',
            'file_path': str(path)
        }
        
    except Exception as e:
        print(f"❌ Failed to load file: {str(e)}")
        return None


def convert_gcode_for_grbl(gcode: str) -> list:
    """Convert standard G-code to GRBL servo-compatible commands."""
    lines = [line.strip() for line in gcode.split('\n') if line.strip()]
    converted = []
    pen_down = False
    
    for line in lines:
        # Skip comments
        if line.startswith(';'):
            continue
            
        # Convert pen commands
        if line == "M3" or line.startswith("M3 ") and "S" not in line:
            converted.append(("M3 S1000", True))  # Pen down
            pen_down = True
        elif line == "M5":
            converted.append(("M3 S0", True))     # Pen up
            pen_down = False
        elif line.startswith("G1"):
            # Add S value to keep servo engaged during moves
            if pen_down and "S" not in line:
                # Add S1000 to keep pen down during move
                if "F" in line:
                    # Insert S before F
                    parts = line.split("F")
                    cmd = parts[0].strip() + " S1000 F" + parts[1]
                else:
                    cmd = line + " S1000"
                converted.append((cmd, False))
            else:
                converted.append((line, False))
        elif line.startswith("G0"):
            # Rapid moves - pen should be up
            converted.append((line, False))
        elif line.startswith("G28"):
            # Home command
            converted.append((line, False))
        else:
            # Other commands pass through
            converted.append((line, False))
    
    return converted


def update_execution_stats(cmd, current_position, pen_down, stats):
    """Update execution statistics based on G-code command."""
    # Parse coordinates from command
    if cmd.startswith("G1") or cmd.startswith("G0"):
        # Extract X, Y coordinates
        parts = cmd.split()
        new_x, new_y = current_position[0], current_position[1]
        
        for part in parts:
            if part.startswith("X"):
                try:
                    new_x = float(part[1:])
                except ValueError:
                    pass
            elif part.startswith("Y"):
                try:
                    new_y = float(part[1:])
                except ValueError:
                    pass
        
        # Calculate distance moved
        distance = ((new_x - current_position[0])**2 + (new_y - current_position[1])**2)**0.5
        stats['total_distance'] += distance
        
        if pen_down:
            stats['drawing_distance'] += distance
        else:
            stats['movement_distance'] += distance
        
        # Update position
        current_position[0] = new_x
        current_position[1] = new_y


async def send_to_plotter_with_frames(port: str, gcode: str, pen_delay: float = 1.0, 
                                     save_frames: bool = True, create_gif: bool = True):
    """Send G-code to plotter and save frames for animation."""
    print(f"\n🖊️  Sending to plotter on {port}...")
    
    # Convert G-code for GRBL servo compatibility
    commands = convert_gcode_for_grbl(gcode)
    print(f"   Total commands: {len(commands)}")
    
    # Initialize visualizer for frame saving
    visualizer = None
    frames_dir = ""
    if save_frames:
        visualizer = PlotterVisualizer(drawing_area=(100.0, 100.0))
        visualizer.setup_figure("LLM-to-Plotter Live Drawing")
        frames_dir = f"results/frames_{time.strftime('%Y%m%d_%H%M%S')}"
        print(f"🎬 Saving frames to: {frames_dir}")
    
    # Initialize progress tracking
    execution_stats = {
        'start_time': time.time(),
        'total_commands': len(commands),
        'successful_commands': 0,
        'failed_commands': 0,
        'total_distance': 0.0,
        'drawing_distance': 0.0,
        'movement_distance': 0.0,
        'pen_up_count': 0,
        'pen_down_count': 0
    }
    
    current_position = [0.0, 0.0, 0.0]
    pen_down = False
    
    # Connect to plotter
    plotter = SerialPlotter(port=port, timeout=10.0)
    
    try:
        await plotter.connect_with_retry()
        print(f"✅ Connected to plotter")
        
        # Home first
        print("   [0] G28 (homing)")
        await plotter.send_command_safe("G28")
        await asyncio.sleep(2.0)
        
        # Save initial frame
        if visualizer:
            visualizer.save_frame(0, frames_dir)
        
        # Pen up to start
        print("   [0] M3 S0 (pen up)")
        await plotter.send_command_safe("M3 S0")
        await asyncio.sleep(pen_delay)
        
        # Send each command and save frames
        for i, (cmd, is_pen_cmd) in enumerate(commands):
            print(f"   [{i+1}/{len(commands)}] {cmd}")
            
            try:
                success = await plotter.send_command_safe(cmd)
                if success:
                    execution_stats['successful_commands'] += 1
                    
                    # Update position and stats based on command
                    old_position = current_position.copy()
                    update_execution_stats(cmd, current_position, pen_down, execution_stats)
                    
                    # Update pen state
                    if "M3 S1000" in cmd:
                        pen_down = True
                        execution_stats['pen_down_count'] += 1
                    elif "M3 S0" in cmd:
                        pen_down = False
                        execution_stats['pen_up_count'] += 1
                    
                    # Add line to visualizer if position changed
                    if visualizer and old_position != current_position:
                        visualizer.add_line(
                            old_position[0], old_position[1],
                            current_position[0], current_position[1],
                            is_drawing=pen_down, command=cmd
                        )
                        # Update current position marker
                        visualizer.update_position(current_position[0], current_position[1], 
                                                 current_position[2], pen_down)
                    
                    # Save frame after every command (to show pen state changes and movements)
                    if visualizer:
                        visualizer.save_frame(i + 1, frames_dir)
                else:
                    execution_stats['failed_commands'] += 1
                
                # Wait after pen commands to let servo settle
                if is_pen_cmd:
                    await asyncio.sleep(pen_delay)
                else:
                    await asyncio.sleep(0.1)  # Slightly longer for better frame spacing
                    
            except Exception as e:
                print(f"      ⚠️  Command failed: {e}")
                execution_stats['failed_commands'] += 1
        
        # Pen up at end
        print("   [end] M3 S0 (pen up)")
        await plotter.send_command_safe("M3 S0")
        pen_down = False
        await asyncio.sleep(pen_delay)
        
        # Home at end
        print("   [end] G28 (homing)")
        await plotter.send_command_safe("G28")
        current_position = [0.0, 0.0, 0.0]
        
        # Save final frame
        if visualizer:
            visualizer.update_position(0, 0, 0, False)
            visualizer.save_frame(len(commands) + 1, frames_dir)
        
        # Final progress snapshot
        execution_stats['end_time'] = time.time()
        execution_stats['total_time'] = execution_stats['end_time'] - execution_stats['start_time']
        execution_stats['efficiency'] = (execution_stats['successful_commands'] / max(execution_stats['total_commands'], 1)) * 100
        execution_stats['average_command_time'] = execution_stats['total_time'] / max(execution_stats['successful_commands'], 1)
        
        print(f"\n✅ Sent {execution_stats['successful_commands']}/{len(commands)} commands successfully")
        
        # Create GIF animation from frames
        if visualizer and create_gif and frames_dir:
            print(f"\n🎬 Creating animated GIF...")
            gif_path = f"results/animation_{time.strftime('%Y%m%d_%H%M%S')}.gif"
            success = visualizer.create_animation_from_frames(frames_dir, gif_path, duration=0.8)
            if success:
                print(f"✅ GIF created: {gif_path}")
            else:
                print(f"❌ GIF creation failed")
        
        # Generate final PNG
        if visualizer:
            png_path = f"results/final_drawing_{time.strftime('%Y%m%d_%H%M%S')}.png"
            success = visualizer.generate_final_png(png_path, "LLM Generated Drawing", execution_stats)
            if success:
                print(f"✅ Final PNG: {png_path}")
        
        return execution_stats, frames_dir
        
    except Exception as e:
        print(f"❌ Plotter error: {e}")
        return None, ""
    finally:
        await plotter.disconnect()
        print("🔌 Disconnected from plotter")
        if visualizer:
            visualizer.close()


def generate_json_report(source: str, source_info: str, gcode: str, execution_stats: dict, 
                        frames_dir: str, output_dir: str = "results/reports") -> str:
    """Generate JSON report with session data.
    
    Args:
        source: "llm" or "file"
        source_info: prompt text or file path
        gcode: The G-code content
        execution_stats: Execution statistics
        frames_dir: Directory containing frames
        output_dir: Output directory for report
    """
    try:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        session_info = {
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "source": source,
            "session_id": time.strftime('%Y%m%d_%H%M%S')
        }
        
        if source == "llm":
            session_info["prompt"] = source_info
        else:
            session_info["file_path"] = source_info
        
        report_data = {
            "session_info": session_info,
            "gcode_info": {
                "total_lines": len([l for l in gcode.split('\n') if l.strip()]),
                "gcode_preview": [l for l in gcode.split('\n')[:10] if l.strip()]
            },
            "execution_stats": execution_stats,
            "output_files": {
                "frames_directory": frames_dir,
                "gif_animation": f"results/animation_{time.strftime('%Y%m%d_%H%M%S')}.gif",
                "final_png": f"results/final_drawing_{time.strftime('%Y%m%d_%H%M%S')}.png"
            }
        }
        
        report_filename = f"session_report_{time.strftime('%Y%m%d_%H%M%S')}.json"
        report_path = output_path / report_filename
        
        with open(report_path, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        print(f"✅ JSON report: {report_path}")
        return str(report_path)
        
    except Exception as e:
        print(f"❌ Report generation failed: {str(e)}")
        return ""


async def main():
    parser = argparse.ArgumentParser(description="Generate G-code with LLM or load from file, send to plotter, create frames and animation")
    parser.add_argument("port", help="Serial port (e.g., /dev/cu.usbserial-14220)")
    parser.add_argument("--prompt", default=None, help="Drawing prompt for LLM generation")
    parser.add_argument("--file", default=None, help="G-code file to plot (alternative to --prompt)")
    parser.add_argument("--provider", choices=["openai", "gemini"], default="openai", help="LLM provider")
    parser.add_argument("--pen-delay", type=float, default=1.0, help="Delay after pen up/down (seconds)")
    parser.add_argument("--dry-run", action="store_true", help="Generate/load G-code but don't send to plotter")
    parser.add_argument("--report", action="store_true", help="Generate JSON report")
    parser.add_argument("--no-frames", action="store_true", help="Don't save frames or create GIF")
    
    args = parser.parse_args()
    
    # Validate arguments - need either prompt or file
    if not args.prompt and not args.file:
        args.prompt = "draw a triangle"  # Default prompt
    
    print("🎨 PromptPlot - LLM to Plotter with Frame-Based Animation")
    print("=" * 60)
    
    # Step 1: Get G-code (from LLM or file)
    if args.file:
        # Load from file
        result = load_gcode_from_file(args.file)
        source = "file"
    else:
        # Generate with LLM
        result = await generate_gcode(args.prompt, args.provider)
        source = "llm"
    
    if not result:
        print(f"\n❌ Failed to {'load' if args.file else 'generate'} G-code")
        return 1
    
    # Show G-code
    gcode = result.get('gcode', '')
    source_label = f"from {args.file}" if args.file else "Generated"
    print(f"\n📋 {source_label} G-code:")
    for i, line in enumerate(gcode.split('\n')[:10], 1):
        if line.strip():
            print(f"   {i:2d}. {line}")
    gcode_lines = [l for l in gcode.split('\n') if l.strip()]
    if len(gcode_lines) > 10:
        remaining = len(gcode_lines) - 10
        print(f"   ... and {remaining} more lines")
    
    execution_stats = None
    frames_dir = ""
    
    if args.dry_run:
        print("\n🔍 Dry run - not sending to plotter")
        # Create mock stats for dry run
        execution_stats = {
            'start_time': time.time() - 60,
            'end_time': time.time(),
            'total_time': 60.0,
            'total_commands': len([l for l in gcode.split('\n') if l.strip()]),
            'successful_commands': len([l for l in gcode.split('\n') if l.strip()]),
            'failed_commands': 0,
            'total_distance': 150.0,
            'drawing_distance': 100.0,
            'movement_distance': 50.0,
            'efficiency': 100.0,
            'average_command_time': 0.15,
            'pen_up_count': 1,
            'pen_down_count': 1
        }
    else:
        # Step 2: Send to plotter with frame saving
        execution_stats, frames_dir = await send_to_plotter_with_frames(
            args.port, gcode, args.pen_delay, 
            save_frames=not args.no_frames,
            create_gif=not args.no_frames
        )
    
    # Step 3: Generate JSON report if requested
    if args.report and execution_stats:
        if args.file:
            generate_json_report("file", args.file, gcode, execution_stats, frames_dir)
        else:
            generate_json_report("llm", args.prompt, gcode, execution_stats, frames_dir)
    
    print("\n🎉 Done!")
    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⏹️  Interrupted")
        sys.exit(1)