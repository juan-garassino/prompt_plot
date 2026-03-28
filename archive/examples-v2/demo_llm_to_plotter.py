#!/usr/bin/env python3
"""
LLM to Plotter Demo - Generate G-code, send to real plotter, save frames, create animation

This demo:
1. Uses an LLM (OpenAI/Gemini) to generate G-code from a prompt
2. Sends the generated G-code to a real pen plotter
3. Saves PNG frames during plotting (one per command)
4. Creates animated GIF at the end
5. Generates JSON report with statistics

Usage Examples:

    # Visualization demo (no plotter required)
    uv run python examples/demo_llm_to_plotter.py --demo

    # Basic plotting with PNG + GIF animation
    uv run python examples/demo_llm_to_plotter.py /dev/cu.usbserial-14220 --prompt "draw a square"

    # With JSON report
    uv run python examples/demo_llm_to_plotter.py /dev/cu.usbserial-14220 --report --prompt "draw a circle"

    # Dry run (no plotter, just generate G-code and preview)
    uv run python examples/demo_llm_to_plotter.py /dev/cu.usbserial-14220 --dry-run --prompt "draw a star"

    # Different LLM provider
    uv run python examples/demo_llm_to_plotter.py /dev/cu.usbserial-14220 --provider gemini --prompt "draw a house"
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


def convert_gcode_for_grbl(gcode: str) -> list:
    """
    Convert standard G-code to GRBL servo-compatible commands.
    
    GRBL pen plotters need:
    - M3 S1000 for pen down (not just M3)
    - M3 S0 for pen up (not M5)
    - S value on G1 commands to keep servo engaged in laser mode
    """
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


class FrameRecorder:
    """Simple frame recorder that saves PNG frames during plotting."""
    
    def __init__(self, output_dir: str = "results/plotter_frames"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.drawing_lines = []  # Lines drawn with pen down
        self.movement_lines = []  # Lines with pen up
        self.current_position = [0.0, 0.0]
        self.frame_count = 0
        self.session_id = time.strftime('%Y%m%d_%H%M%S')
        
    def add_line(self, start_x, start_y, end_x, end_y, pen_down):
        """Add a line segment."""
        line = {'start': [start_x, start_y], 'end': [end_x, end_y]}
        if pen_down:
            self.drawing_lines.append(line)
        else:
            self.movement_lines.append(line)
        self.current_position = [end_x, end_y]
    
    def save_frame(self, command: str = ""):
        """Save current state as a PNG frame."""
        try:
            import matplotlib.pyplot as plt
            
            fig, ax = plt.subplots(1, 1, figsize=(10, 8))
            
            # Plot movement lines (pen up) in light gray
            for line in self.movement_lines:
                ax.plot([line['start'][0], line['end'][0]], 
                       [line['start'][1], line['end'][1]], 
                       '--', color='lightgray', linewidth=1, alpha=0.5)
            
            # Plot drawing lines (pen down) in blue
            for line in self.drawing_lines:
                ax.plot([line['start'][0], line['end'][0]], 
                       [line['start'][1], line['end'][1]], 
                       'b-', linewidth=2)
            
            # Plot current position
            ax.plot(self.current_position[0], self.current_position[1], 
                   'ro', markersize=8, label='Current')
            
            # Plot start marker
            ax.plot(0, 0, 'go', markersize=6, label='Start')
            
            ax.set_aspect('equal')
            ax.grid(True, alpha=0.3)
            ax.legend(loc='upper right')
            ax.set_xlabel('X (mm)')
            ax.set_ylabel('Y (mm)')
            ax.set_title(f'Frame {self.frame_count}: {command[:50]}...' if len(command) > 50 else f'Frame {self.frame_count}: {command}')
            
            # Save frame
            frame_path = self.output_dir / f"{self.session_id}_frame_{self.frame_count:04d}.png"
            plt.savefig(frame_path, dpi=100, bbox_inches='tight')
            plt.close()
            
            self.frame_count += 1
            return str(frame_path)
            
        except Exception as e:
            print(f"⚠️  Frame save failed: {e}")
            return None
    
    def create_gif(self, output_path: str = None, duration: int = 200) -> str:
        """Create animated GIF from saved frames."""
        try:
            from PIL import Image
            import glob
            
            # Find all frames
            frame_pattern = str(self.output_dir / f"{self.session_id}_frame_*.png")
            frame_files = sorted(glob.glob(frame_pattern))
            
            if not frame_files:
                print("⚠️  No frames found for GIF creation")
                return None
            
            # Load frames
            frames = [Image.open(f) for f in frame_files]
            
            # Create GIF
            if output_path is None:
                output_path = str(self.output_dir / f"{self.session_id}_animation.gif")
            
            frames[0].save(
                output_path,
                save_all=True,
                append_images=frames[1:],
                duration=duration,
                loop=0
            )
            
            print(f"✅ GIF created: {output_path} ({len(frames)} frames)")
            return output_path
            
        except ImportError:
            print("⚠️  PIL not available for GIF creation. Install with: pip install Pillow")
            return None
        except Exception as e:
            print(f"❌ GIF creation failed: {e}")
            return None
    
    def save_final_png(self, execution_stats: dict = None) -> str:
        """Save final PNG with statistics."""
        try:
            import matplotlib.pyplot as plt
            
            fig, ax = plt.subplots(1, 1, figsize=(10, 8))
            
            # Plot movement lines
            for line in self.movement_lines:
                ax.plot([line['start'][0], line['end'][0]], 
                       [line['start'][1], line['end'][1]], 
                       '--', color='lightgray', linewidth=1, alpha=0.5)
            
            # Plot drawing lines
            for line in self.drawing_lines:
                ax.plot([line['start'][0], line['end'][0]], 
                       [line['start'][1], line['end'][1]], 
                       'b-', linewidth=2)
            
            # Markers
            if self.drawing_lines:
                start = self.drawing_lines[0]['start']
                end = self.drawing_lines[-1]['end']
                ax.plot(start[0], start[1], 'go', markersize=8, label='Start')
                ax.plot(end[0], end[1], 'ro', markersize=8, label='End')
            
            ax.set_aspect('equal')
            ax.grid(True, alpha=0.3)
            ax.legend()
            ax.set_xlabel('X (mm)')
            ax.set_ylabel('Y (mm)')
            
            # Title with stats
            title = "LLM-Generated Drawing"
            if execution_stats:
                title += f"\nTime: {execution_stats.get('total_time', 0):.1f}s"
                title += f", Distance: {execution_stats.get('drawing_distance', 0):.1f}mm"
            ax.set_title(title, fontsize=12)
            
            # Save
            png_path = str(self.output_dir / f"{self.session_id}_final.png")
            plt.savefig(png_path, dpi=150, bbox_inches='tight')
            plt.close()
            
            return png_path
            
        except Exception as e:
            print(f"❌ Final PNG save failed: {e}")
            return None


async def send_to_plotter_with_frames(port: str, gcode: str, pen_delay: float = 1.0, 
                                     save_frames: bool = True, frame_interval: int = 1):
    """Send G-code to plotter and save PNG frames during execution."""
    print(f"\n🖊️  Sending to plotter on {port}...")
    
    # Convert G-code for GRBL servo compatibility
    commands = convert_gcode_for_grbl(gcode)
    print(f"   Total commands: {len(commands)}")
            enable_interactive=enable_interactive,
            enable_progress_monitoring=enable_progress,
            enable_reporting=True
        )
        
        # Create a dummy program for session initialization
        from promptplot.core.models import GCodeProgram
        dummy_commands = [GCodeCommand(command="G28")]  # Just for initialization
        dummy_program = GCodeProgram(commands=dummy_commands)
        
        # Start visualization session
        session_id = viz_manager.start_session(dummy_program, "llm_to_plotter_session")
        
        if enable_interactive:
            viz_manager.set_view_mode(ViewMode.STANDARD)
            print(f"✅ Interactive visualization ready")
        
        if enable_progress:
            print(f"✅ Progress monitoring started")
    
    # Initialize progress tracking
    progress_history = []
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
        
        # Show interactive visualization if enabled
        if viz_manager and enable_interactive:
            viz_manager.show_interactive_visualization(block=False)
            print(f"🖼️  Interactive window opened - you can zoom, pan, and monitor progress!")
        
        # Home first
        print("   [0] G28 (homing)")
        await plotter.send_command_safe("G28")
        await asyncio.sleep(2.0)
        
        if viz_manager:
            # Update execution progress for homing
            home_cmd = GCodeCommand(command="G28")
            viz_manager.update_execution_progress(0, home_cmd, 2.0, tuple(current_position), pen_down)
        
        # Pen up to start
        print("   [0] M3 S0 (pen up)")
        await plotter.send_command_safe("M3 S0")
        await asyncio.sleep(pen_delay)
        
        # Send each command with real-time visualization
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
                    
                    # Update visualization in real-time
                    if viz_manager:
                        # Create GCodeCommand object for progress tracking
                        cmd_obj = GCodeCommand(command=cmd.split()[0] if cmd.split() else "G1")
                        
                        # Parse coordinates from command if available
                        if "X" in cmd or "Y" in cmd:
                            parts = cmd.split()
                            for part in parts:
                                if part.startswith("X"):
                                    try:
                                        cmd_obj.x = float(part[1:])
                                    except ValueError:
                                        pass
                                elif part.startswith("Y"):
                                    try:
                                        cmd_obj.y = float(part[1:])
                                    except ValueError:
                                        pass
                        
                        # Update execution progress
                        viz_manager.update_execution_progress(
                            i, cmd_obj, 0.05, tuple(current_position), pen_down
                        )
                        
                        # Add line to visualization if position changed and pen is down
                        if enable_interactive and (old_position != current_position) and pen_down:
                            if viz_manager.visualizer:
                                viz_manager.visualizer.add_line(
                                    old_position[0], old_position[1],
                                    current_position[0], current_position[1],
                                    is_drawing=True, command=cmd
                                )
                        
                        # Create progress snapshot for history
                        if i % 5 == 0 or is_pen_cmd:
                            phase = ProgressPhase.DRAWING if pen_down else ProgressPhase.MOVING
                            snapshot = create_progress_snapshot(
                                phase, current_position, pen_down,
                                i + 1, len(commands), execution_stats['total_distance'],
                                execution_stats['start_time']
                            )
                            progress_history.append(snapshot)
                else:
                    execution_stats['failed_commands'] += 1
                
                # Wait after pen commands to let servo settle
                if is_pen_cmd:
                    await asyncio.sleep(pen_delay)
                else:
                    await asyncio.sleep(0.05)  # Small delay between moves
                    
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
        
        # Generate PNG visualization at the end if requested
        if args.png or args.full_viz:
            try:
                print(f"\n🖼️  Generating PNG visualization...")
                png_path = await generate_png_visualization(gcode, execution_stats, progress_history)
                if png_path:
                    print(f"✅ PNG saved: {png_path}")
                else:
                    print(f"⚠️  PNG generation failed")
            except Exception as e:
                print(f"❌ PNG generation error: {str(e)}")
        
        # Final updates
        if viz_manager:
            # End the visualization session
            viz_manager.end_session(generate_report=False)
        
        # Final progress snapshot
        execution_stats['end_time'] = time.time()
        execution_stats['total_time'] = execution_stats['end_time'] - execution_stats['start_time']
        execution_stats['efficiency'] = (execution_stats['successful_commands'] / max(execution_stats['total_commands'], 1)) * 100
        execution_stats['average_command_time'] = execution_stats['total_time'] / max(execution_stats['successful_commands'], 1)
        
        final_snapshot = create_progress_snapshot(
            ProgressPhase.COMPLETED, current_position, False,
            len(commands), len(commands), execution_stats['total_distance'],
            execution_stats['start_time']
        )
        progress_history.append(final_snapshot)
        
        print(f"\n✅ Sent {execution_stats['successful_commands']}/{len(commands)} commands successfully")
        
        # Show final visualization summary
        if viz_manager and enable_progress:
            progress_summary = viz_manager.get_progress_summary()
            print(f"\n📊 Progress Summary:")
            print(f"   • Total time: {progress_summary.get('total_time', 0):.1f}s")
            print(f"   • Drawing time: {progress_summary.get('drawing_time', 0):.1f}s")
            print(f"   • Average speed: {progress_summary.get('average_speed', 0):.1f} mm/s")
        
        return execution_stats, progress_history, viz_manager
        
    except Exception as e:
        print(f"❌ Plotter error: {e}")
        return None, [], viz_manager
    finally:
        await plotter.disconnect()
        print("🔌 Disconnected from plotter")


def create_progress_snapshot(phase, position, pen_down, current_cmd, total_cmds, distance, start_time):
    """Create a progress snapshot for reporting."""
    current_time = time.time()
    elapsed = current_time - start_time
    
    metrics = {
        MetricType.COMMANDS: ProgressMetric(
            MetricType.COMMANDS, current_cmd, total_cmds, "commands", current_time
        ),
        MetricType.DISTANCE: ProgressMetric(
            MetricType.DISTANCE, distance, distance * 1.2, "mm", current_time  # Estimate total
        ),
        MetricType.TIME: ProgressMetric(
            MetricType.TIME, elapsed, elapsed * 1.2, "seconds", current_time  # Estimate total
        )
    }
    
    return ProgressSnapshot(
        timestamp=current_time,
        phase=phase,
        metrics=metrics,
        current_position=tuple(position),
        pen_down=pen_down
    )


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


async def create_animated_plotter_visualization(gcode: str, port: str, pen_delay: float = 1.0):
    """Create real-time animated visualization that updates as the plotter draws."""
    try:
        import matplotlib.pyplot as plt
        import matplotlib.patches as patches
        from matplotlib.animation import FuncAnimation
        import threading
        import queue
        
        # Parse G-code commands
        commands = convert_gcode_for_grbl(gcode)
        
        # Setup the plot
        fig, ax = plt.subplots(1, 1, figsize=(12, 9))
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.3)
        ax.set_title('Real-Time Plotter Visualization', fontsize=14, pad=20)
        ax.set_xlabel('X (mm)')
        ax.set_ylabel('Y (mm)')
        
        # Initialize drawing data
        drawing_lines = []
        movement_lines = []
        current_pos_marker = ax.plot(0, 0, 'ro', markersize=8, label='Current Position')[0]
        pen_status_text = ax.text(0.02, 0.98, 'Pen: UP', transform=ax.transAxes, 
                                 fontsize=12, verticalalignment='top',
                                 bbox=dict(boxstyle='round', facecolor='lightgray'))
        command_text = ax.text(0.02, 0.92, 'Command: Initializing...', transform=ax.transAxes,
                              fontsize=10, verticalalignment='top')
        
        ax.legend()
        
        # Queue for communication between plotter thread and animation
        update_queue = queue.Queue()
        plotter_finished = threading.Event()
        
        # Animation function
        def animate(frame):
            try:
                while not update_queue.empty():
                    update_data = update_queue.get_nowait()
                    
                    if update_data['type'] == 'line':
                        line_data = update_data['data']
                        if line_data['pen_down']:
                            line = ax.plot([line_data['start'][0], line_data['end'][0]], 
                                         [line_data['start'][1], line_data['end'][1]], 
                                         'b-', linewidth=2)[0]
                            drawing_lines.append(line)
                        else:
                            line = ax.plot([line_data['start'][0], line_data['end'][0]], 
                                         [line_data['start'][1], line_data['end'][1]], 
                                         '--', color='lightgray', linewidth=1, alpha=0.5)[0]
                            movement_lines.append(line)
                    
                    elif update_data['type'] == 'position':
                        pos_data = update_data['data']
                        current_pos_marker.set_data([pos_data['x']], [pos_data['y']])
                        
                        # Update pen status
                        pen_color = 'green' if pos_data['pen_down'] else 'red'
                        pen_text = 'DOWN' if pos_data['pen_down'] else 'UP'
                        pen_status_text.set_text(f'Pen: {pen_text}')
                        pen_status_text.set_bbox(dict(boxstyle='round', facecolor=pen_color, alpha=0.3))
                        
                        # Update command text
                        command_text.set_text(f"Command: {pos_data.get('command', 'N/A')}")
                    
                    elif update_data['type'] == 'bounds':
                        bounds = update_data['data']
                        ax.set_xlim(bounds['x_min'] - 5, bounds['x_max'] + 5)
                        ax.set_ylim(bounds['y_min'] - 5, bounds['y_max'] + 5)
                
                # Redraw the plot
                fig.canvas.draw_idle()
                
            except queue.Empty:
                pass
            
            return [current_pos_marker, pen_status_text, command_text] + drawing_lines + movement_lines
        
        # Plotter execution in separate thread
        async def run_plotter():
            from promptplot.plotter import SerialPlotter
            
            current_position = [0.0, 0.0, 0.0]
            pen_down = False
            
            # Calculate bounds for auto-scaling
            all_x, all_y = [], []
            temp_pos = [0.0, 0.0]
            for cmd, _ in commands:
                if cmd.startswith("G1") or cmd.startswith("G0"):
                    parts = cmd.split()
                    for part in parts:
                        if part.startswith("X"):
                            try:
                                temp_pos[0] = float(part[1:])
                                all_x.append(temp_pos[0])
                            except ValueError:
                                pass
                        elif part.startswith("Y"):
                            try:
                                temp_pos[1] = float(part[1:])
                                all_y.append(temp_pos[1])
                            except ValueError:
                                pass
            
            if all_x and all_y:
                bounds = {
                    'x_min': min(all_x), 'x_max': max(all_x),
                    'y_min': min(all_y), 'y_max': max(all_y)
                }
                update_queue.put({'type': 'bounds', 'data': bounds})
            
            # Connect to plotter
            plotter = SerialPlotter(port=port, timeout=10.0)
            try:
                await plotter.connect_with_retry()
                print(f"✅ Connected to plotter for animated visualization")
                
                # Home and setup
                await plotter.send_command_safe("G28")
                update_queue.put({'type': 'position', 'data': {
                    'x': 0, 'y': 0, 'pen_down': False, 'command': 'G28 (Homing)'
                }})
                await asyncio.sleep(2.0)
                
                await plotter.send_command_safe("M3 S0")
                await asyncio.sleep(pen_delay)
                
                # Execute commands with real-time updates
                for i, (cmd, is_pen_cmd) in enumerate(commands):
                    print(f"   [{i+1}/{len(commands)}] {cmd}")
                    
                    # Update position tracking
                    old_position = current_position.copy()
                    update_execution_stats(cmd, current_position, pen_down, {})
                    
                    # Update pen state
                    if "M3 S1000" in cmd:
                        pen_down = True
                    elif "M3 S0" in cmd:
                        pen_down = False
                    
                    # Send command to plotter
                    success = await plotter.send_command_safe(cmd)
                    
                    # Update visualization
                    if old_position != current_position:
                        # Add line to visualization
                        update_queue.put({'type': 'line', 'data': {
                            'start': old_position[:2],
                            'end': current_position[:2],
                            'pen_down': pen_down
                        }})
                    
                    # Update current position marker
                    update_queue.put({'type': 'position', 'data': {
                        'x': current_position[0],
                        'y': current_position[1],
                        'pen_down': pen_down,
                        'command': cmd
                    }})
                    
                    # Wait appropriately
                    if is_pen_cmd:
                        await asyncio.sleep(pen_delay)
                    else:
                        await asyncio.sleep(0.1)  # Slightly longer for animation visibility
                
                # Final cleanup
                await plotter.send_command_safe("M3 S0")
                await plotter.send_command_safe("G28")
                
                # Final position update
                update_queue.put({'type': 'position', 'data': {
                    'x': 0, 'y': 0, 'pen_down': False, 'command': 'Completed!'
                }})
                
                print(f"✅ Animated plotting completed")
                
            except Exception as e:
                print(f"❌ Animated plotter error: {e}")
            finally:
                await plotter.disconnect()
                plotter_finished.set()
        
        # Start the plotter in a separate thread
        def plotter_thread():
            asyncio.run(run_plotter())
        
        thread = threading.Thread(target=plotter_thread)
        thread.daemon = True
        thread.start()
        
        # Start animation
        anim = FuncAnimation(fig, animate, interval=100, blit=False, cache_frame_data=False)
        
        # Show the plot
        plt.show()
        
        # Wait for plotter to finish
        thread.join()
        
        return True
        
    except ImportError:
        print("❌ matplotlib not available for animated visualization")
        return False
    except Exception as e:
        print(f"❌ Animated visualization failed: {str(e)}")
        return False


async def generate_png_visualization(gcode: str, execution_stats: dict, progress_history: list, 
                                   output_dir: str = "results/llm_plotter_pngs") -> str:
    """Generate a simple PNG visualization of the drawing path."""
    try:
        import matplotlib.pyplot as plt
        import matplotlib.patches as patches
        from pathlib import Path
        import time
        
        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Parse G-code to extract drawing path
        lines = [line.strip() for line in gcode.split('\n') if line.strip() and not line.startswith(';')]
        
        drawing_lines = []
        movement_lines = []
        current_pos = [0.0, 0.0]
        pen_down = False
        
        for line in lines:
            # Check pen state
            if "M3 S1000" in line or (line.startswith("M3") and "S1000" in line):
                pen_down = True
                continue
            elif "M3 S0" in line or line == "M5":
                pen_down = False
                continue
            
            # Parse movement commands
            if line.startswith("G1") or line.startswith("G0"):
                parts = line.split()
                new_x, new_y = current_pos[0], current_pos[1]
                
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
                
                # Add line to appropriate list
                if current_pos != [new_x, new_y]:
                    line_data = {
                        'start': current_pos.copy(),
                        'end': [new_x, new_y],
                        'pen_down': pen_down
                    }
                    
                    if pen_down:
                        drawing_lines.append(line_data)
                    else:
                        movement_lines.append(line_data)
                
                current_pos = [new_x, new_y]
        
        # Create the plot
        fig, ax = plt.subplots(1, 1, figsize=(10, 8))
        
        # Plot movement lines (pen up) in light gray
        for line in movement_lines:
            ax.plot([line['start'][0], line['end'][0]], 
                   [line['start'][1], line['end'][1]], 
                   color='lightgray', linewidth=1, linestyle='--', alpha=0.5)
        
        # Plot drawing lines (pen down) in blue
        for line in drawing_lines:
            ax.plot([line['start'][0], line['end'][0]], 
                   [line['start'][1], line['end'][1]], 
                   color='blue', linewidth=2)
        
        # Add start and end markers
        if drawing_lines or movement_lines:
            all_lines = drawing_lines + movement_lines
            if all_lines:
                start_pos = all_lines[0]['start']
                end_pos = all_lines[-1]['end']
                
                ax.plot(start_pos[0], start_pos[1], 'go', markersize=8, label='Start')
                ax.plot(end_pos[0], end_pos[1], 'ro', markersize=8, label='End')
        
        # Set equal aspect ratio and add grid
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.3)
        ax.legend()
        
        # Add title and stats
        title = f"LLM-Generated Drawing"
        if execution_stats:
            title += f"\nTime: {execution_stats.get('total_time', 0):.1f}s, "
            title += f"Distance: {execution_stats.get('drawing_distance', 0):.1f}mm"
        
        ax.set_title(title, fontsize=12, pad=20)
        ax.set_xlabel('X (mm)')
        ax.set_ylabel('Y (mm)')
        
        # Save PNG
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        png_filename = f"llm_plotter_drawing_{timestamp}.png"
        png_path = output_path / png_filename
        
        plt.tight_layout()
        plt.savefig(png_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        return str(png_path)
        
    except ImportError:
        print("❌ matplotlib not available for PNG generation")
        return None
    except Exception as e:
        print(f"❌ PNG generation failed: {str(e)}")
        return None


async def generate_comprehensive_report(prompt, provider, gcode, execution_stats, progress_history, 
                                      viz_manager=None, output_dir="results/llm_plotter_reports"):
    """Generate comprehensive visual report with interactive visualization data."""
    print(f"\n📊 Generating comprehensive visual report...")
    
    # Create G-code program object
    gcode_lines = [line.strip() for line in gcode.split('\n') if line.strip() and not line.startswith(';')]
    commands = []
    
    for line in gcode_lines:
        # Parse basic G-code commands
        parts = line.split()
        if not parts:
            continue
            
        cmd_type = parts[0]
        cmd = GCodeCommand(command=cmd_type)
        
        # Parse coordinates and parameters
        for part in parts[1:]:
            if part.startswith('X'):
                try:
                    cmd.x = float(part[1:])
                except ValueError:
                    pass
            elif part.startswith('Y'):
                try:
                    cmd.y = float(part[1:])
                except ValueError:
                    pass
            elif part.startswith('F'):
                try:
                    cmd.f = float(part[1:])
                except ValueError:
                    pass
            elif part.startswith('S'):
                try:
                    cmd.s = int(part[1:])
                except ValueError:
                    pass
        
        commands.append(cmd)
    
    program = GCodeProgram(
        commands=commands,
        metadata={
            "title": f"LLM Generated Drawing: {prompt}",
            "description": f"Generated using {provider} LLM provider",
            "source": f"llm_{provider}",
            "prompt": prompt,
            "generation_time": time.time()
        }
    )
    
    # Create visualizer data from execution stats and viz_manager
    visualizer_data = {
        'lines': [],
        'statistics': execution_stats,
        'drawing_area': (100.0, 100.0)
    }
    
    # Get visualization data from viz_manager if available
    if viz_manager and hasattr(viz_manager, 'visualizer') and viz_manager.visualizer:
        try:
            # Extract drawing lines from interactive visualizer
            if hasattr(viz_manager.visualizer, 'drawing_lines'):
                for line in viz_manager.visualizer.drawing_lines:
                    visualizer_data['lines'].append({
                        'start_x': line.get('start_x', 0),
                        'start_y': line.get('start_y', 0),
                        'end_x': line.get('end_x', 0),
                        'end_y': line.get('end_y', 0),
                        'is_drawing': line.get('is_drawing', True),
                        'timestamp': line.get('timestamp', time.time())
                    })
            
            # Get drawing area from visualizer
            if hasattr(viz_manager.visualizer, 'drawing_area'):
                visualizer_data['drawing_area'] = viz_manager.visualizer.drawing_area
                
        except Exception as e:
            print(f"⚠️  Could not extract visualization data: {e}")
    
    # Fallback: Estimate drawing lines from G-code if no viz data
    if not visualizer_data['lines']:
        current_pos = [0.0, 0.0]
        pen_down = False
        
        for cmd in commands:
            s_value = getattr(cmd, 's', None)
            if cmd.command == "M3" and s_value is not None and s_value > 0:
                pen_down = True
            elif cmd.command == "M3" and (s_value is None or s_value == 0):
                pen_down = False
            elif cmd.command == "M5":
                pen_down = False
            elif cmd.command in ["G1", "G0"] and cmd.x is not None and cmd.y is not None:
                if pen_down:
                    visualizer_data['lines'].append({
                        'start_x': current_pos[0],
                        'start_y': current_pos[1],
                        'end_x': cmd.x,
                        'end_y': cmd.y,
                        'is_drawing': True,
                        'timestamp': time.time()
                    })
                current_pos = [cmd.x, cmd.y]
    
    # Create report data
    report_data = ReportData(
        program=program,
        progress_history=progress_history,
        visualizer_data=visualizer_data,
        execution_stats=execution_stats,
        title=f"LLM-to-Plotter Session Report",
        description=f"Complete analysis of '{prompt}' drawing generated by {provider} and executed on plotter"
    )
    
    # Use viz_manager's reporter if available, otherwise create new one
    if viz_manager and hasattr(viz_manager, 'reporter') and viz_manager.reporter:
        reporter = viz_manager.reporter
    else:
        reporter = VisualReporter(output_dir=output_dir)
    
    generated_reports = []
    
    # Generate multiple format reports
    formats = [
        (ReportFormat.HTML, "HTML"),
        (ReportFormat.PDF, "PDF"),
        (ReportFormat.JSON, "JSON")
    ]
    
    for format_type, format_name in formats:
        try:
            report_path = reporter.generate_comprehensive_report(
                report_data, 
                format=format_type
            )
            generated_reports.append((format_name, report_path))
            print(f"✅ {format_name} report: {report_path}")
        except Exception as e:
            print(f"❌ {format_name} report failed: {str(e)}")
    
    # Generate interactive visualization export if available
    if viz_manager and hasattr(viz_manager, 'visualizer') and viz_manager.visualizer:
        try:
            viz_export_path = f"{output_dir}/interactive_visualization.png"
            viz_manager.save_visualization_snapshot(viz_export_path)
            generated_reports.append(("Interactive Snapshot", viz_export_path))
            print(f"✅ Interactive visualization snapshot: {viz_export_path}")
        except Exception as e:
            print(f"⚠️  Could not save visualization snapshot: {e}")
    
    # Generate summary insights
    if execution_stats:
        print(f"\n📈 Session Summary:")
        print(f"• Total execution time: {execution_stats.get('total_time', 0):.1f} seconds")
        print(f"• Commands executed: {execution_stats.get('successful_commands', 0)}/{execution_stats.get('total_commands', 0)}")
        print(f"• Success rate: {execution_stats.get('efficiency', 0):.1f}%")
        print(f"• Total distance: {execution_stats.get('total_distance', 0):.1f} mm")
        print(f"• Drawing distance: {execution_stats.get('drawing_distance', 0):.1f} mm")
        
        if execution_stats.get('total_distance', 0) > 0:
            drawing_ratio = execution_stats.get('drawing_distance', 0) / execution_stats['total_distance']
            print(f"• Drawing efficiency: {drawing_ratio * 100:.1f}%")
    
    # Show progress monitoring insights if available
    if viz_manager and hasattr(viz_manager, 'progress_monitor') and viz_manager.progress_monitor:
        try:
            progress_summary = viz_manager.get_progress_summary()
            print(f"\n📊 Progress Monitoring Insights:")
            print(f"• Drawing phases detected: {progress_summary.get('phase_count', 0)}")
            print(f"• Average drawing speed: {progress_summary.get('average_speed', 0):.1f} mm/s")
            print(f"• Peak drawing speed: {progress_summary.get('peak_speed', 0):.1f} mm/s")
            print(f"• Idle time: {progress_summary.get('idle_time', 0):.1f}s")
        except Exception as e:
            print(f"⚠️  Could not get progress insights: {e}")
    
    return generated_reports, reporter


async def main():
    parser = argparse.ArgumentParser(description="Generate G-code with LLM, send to plotter with interactive visualization and reporting")
    parser.add_argument("port", help="Serial port (e.g., /dev/cu.usbserial-14220)")
    parser.add_argument("--prompt", default="draw a small square", help="Drawing prompt")
    parser.add_argument("--provider", choices=["openai", "gemini"], default="openai", help="LLM provider")
    parser.add_argument("--pen-delay", type=float, default=1.0, help="Delay after pen up/down (seconds)")
    parser.add_argument("--dry-run", action="store_true", help="Generate G-code but don't send to plotter")
    parser.add_argument("--report", action="store_true", help="Generate visual reports after plotting")
    parser.add_argument("--interactive", action="store_true", help="Enable real-time interactive visualization")
    parser.add_argument("--animated", action="store_true", help="Enable real-time animated visualization (recommended)")
    parser.add_argument("--progress", action="store_true", help="Enable progress monitoring")
    parser.add_argument("--png", action="store_true", help="Generate PNG visualization at the end")
    parser.add_argument("--full-viz", action="store_true", help="Enable all visualization features (interactive + progress + reports + PNG)")
    
    args = parser.parse_args()
    
    # Enable all visualization features if --full-viz is used
    if args.full_viz:
        args.interactive = True
        args.animated = True
        args.progress = True
        args.report = True
        args.png = True
    
    print("🎨 PromptPlot - LLM to Plotter Demo with Advanced Visualization")
    print("=" * 60)
    
    if args.interactive:
        print("🖼️  Interactive visualization: ENABLED")
    if args.animated:
        print("🎬 Animated visualization: ENABLED")
    if args.progress:
        print("📊 Progress monitoring: ENABLED")
    if args.report:
        print("📋 Report generation: ENABLED")
    if args.png:
        print("🖼️  PNG generation: ENABLED")
    
    # Step 1: Generate G-code
    result = await generate_gcode(args.prompt, args.provider)
    
    if not result:
        print("\n❌ Failed to generate G-code")
        return 1
    
    # Show generated G-code
    gcode = result.get('gcode', '')
    print("\n📋 Generated G-code:")
    for i, line in enumerate(gcode.split('\n')[:10], 1):
        print(f"   {i:2d}. {line}")
    gcode_lines = gcode.split('\n')
    if len(gcode_lines) > 10:
        remaining = len(gcode_lines) - 10
        print(f"   ... and {remaining} more lines")
    
    execution_stats = None
    progress_history = []
    viz_manager = None
    
    if args.dry_run:
        print("\n🔍 Dry run - not sending to plotter")
        # Create mock stats for dry run reporting
        if args.report:
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
            
            # Create mock progress history
            for i in range(5):
                snapshot = create_progress_snapshot(
                    ProgressPhase.DRAWING if i % 2 == 0 else ProgressPhase.MOVING,
                    [i * 10, i * 5, 0], i % 2 == 0,
                    i * 5, 25, i * 30, time.time() - 60
                )
                progress_history.append(snapshot)
    else:
        # Step 2: Send to plotter with visualization
        if args.animated:
            # Use the new animated visualization
            print(f"\n🎬 Starting animated real-time visualization...")
            success = await create_animated_plotter_visualization(gcode, args.port, args.pen_delay)
            if success:
                print(f"✅ Animated visualization completed successfully")
            else:
                print(f"❌ Animated visualization failed")
            
            # Create mock stats for PNG/report generation
            execution_stats = {
                'start_time': time.time() - 60,
                'end_time': time.time(),
                'total_time': 60.0,
                'successful_commands': len([l for l in gcode.split('\n') if l.strip()]),
                'total_commands': len([l for l in gcode.split('\n') if l.strip()]),
                'failed_commands': 0,
                'total_distance': 150.0,
                'drawing_distance': 100.0,
                'movement_distance': 50.0,
                'efficiency': 100.0,
                'average_command_time': 0.15,
                'pen_up_count': 1,
                'pen_down_count': 1
            }
            progress_history = []
            viz_manager = None
            
        elif args.interactive or args.progress:
            execution_stats, progress_history, viz_manager = await send_to_plotter_with_visualization(
                args.port, gcode, args.pen_delay, 
                enable_interactive=args.interactive,
                enable_progress=args.progress
            )
        else:
            # Simple plotter execution without complex visualization
            from promptplot.plotter import SerialPlotter
            
            print(f"\n🖊️  Sending to plotter on {args.port}...")
            commands = convert_gcode_for_grbl(gcode)
            print(f"   Total commands: {len(commands)}")
            
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
            
            plotter = SerialPlotter(port=args.port, timeout=10.0)
            try:
                await plotter.connect_with_retry()
                print(f"✅ Connected to plotter")
                
                # Home and setup
                await plotter.send_command_safe("G28")
                await asyncio.sleep(2.0)
                await plotter.send_command_safe("M3 S0")
                await asyncio.sleep(args.pen_delay)
                
                # Send commands
                for i, (cmd, is_pen_cmd) in enumerate(commands):
                    print(f"   [{i+1}/{len(commands)}] {cmd}")
                    success = await plotter.send_command_safe(cmd)
                    if success:
                        execution_stats['successful_commands'] += 1
                    else:
                        execution_stats['failed_commands'] += 1
                    
                    if is_pen_cmd:
                        await asyncio.sleep(args.pen_delay)
                    else:
                        await asyncio.sleep(0.05)
                
                # End sequence
                await plotter.send_command_safe("M3 S0")
                await asyncio.sleep(args.pen_delay)
                await plotter.send_command_safe("G28")
                
                execution_stats['end_time'] = time.time()
                execution_stats['total_time'] = execution_stats['end_time'] - execution_stats['start_time']
                execution_stats['efficiency'] = (execution_stats['successful_commands'] / max(execution_stats['total_commands'], 1)) * 100
                
                print(f"\n✅ Sent {execution_stats['successful_commands']}/{len(commands)} commands successfully")
                
            except Exception as e:
                print(f"❌ Plotter error: {e}")
                execution_stats = None
            finally:
                await plotter.disconnect()
                print("🔌 Disconnected from plotter")
            
            progress_history = []
            viz_manager = None
    
    # Step 3: Generate comprehensive reports if requested
    if args.report and execution_stats:
        try:
            reports, reporter = await generate_comprehensive_report(
                args.prompt, args.provider, gcode, 
                execution_stats, progress_history, viz_manager
            )
            
            print(f"\n📋 Generated {len(reports)} reports:")
            for report_type, report_path in reports:
                print(f"  • {report_type}: {report_path}")
            
            print(f"\n💡 Tips:")
            print(f"  • Open the HTML report in your browser for interactive viewing")
            print(f"  • The JSON report contains raw data for further analysis")
            if args.interactive:
                print(f"  • The interactive visualization window shows real-time drawing progress")
            if args.progress:
                print(f"  • Progress monitoring data is included in all reports")
            
        except Exception as e:
            print(f"\n❌ Report generation failed: {str(e)}")
            import traceback
            traceback.print_exc()
    
    # Keep interactive visualization open if requested
    if viz_manager and args.interactive and not args.dry_run:
        print(f"\n🖼️  Interactive visualization is still open.")
        print(f"   Close the matplotlib window to exit, or press Ctrl+C here.")
        try:
            # Keep the visualization window open
            input("Press Enter to close visualization and exit...")
        except KeyboardInterrupt:
            pass
        finally:
            if viz_manager:
                viz_manager.close()
    
    print("\n🎉 Done!")
    return 0


async def demo_visualization_only():
    """Demo the visualization features without requiring a physical plotter."""
    print("🎨 PromptPlot - Visualization Demo (No Plotter Required)")
    print("=" * 60)
    
    # Generate sample G-code
    sample_gcode = """
G28
G90
G1 X10 Y10 F1500
M3 S1000
G1 X50 Y10 F1500
G1 X50 Y50 F1500
G1 X10 Y50 F1500
G1 X10 Y10 F1500
M3 S0
G28
"""
    
    print("📋 Using sample G-code for visualization demo")
    
    # Setup visualization manager
    viz_manager = VisualizationManager(
        drawing_area=(100.0, 100.0),
        enable_interactive=True,
        enable_progress_monitoring=True,
        enable_reporting=True
    )
    
    # Parse and simulate G-code execution
    commands = convert_gcode_for_grbl(sample_gcode)
    
    # Create sample program for session
    sample_commands = [GCodeCommand(command=cmd.split()[0]) for cmd, _ in commands if cmd.strip()]
    sample_program = GCodeProgram(commands=sample_commands)
    
    # Start visualization session
    session_id = viz_manager.start_session(sample_program, "demo_square_session")
    viz_manager.set_view_mode(ViewMode.STANDARD)
    
    # Show interactive visualization
    viz_manager.show_interactive_visualization(block=False)
    print("🖼️  Interactive visualization opened!")
    
    # Simulate drawing process
    print("\n🎬 Simulating drawing process...")
    current_position = [0.0, 0.0, 0.0]
    pen_down = False
    
    execution_stats = {
        'start_time': time.time(),
        'total_commands': len(commands),
        'successful_commands': 0,
        'total_distance': 0.0,
        'drawing_distance': 0.0,
        'movement_distance': 0.0,
        'pen_up_count': 0,
        'pen_down_count': 0
    }
    
    progress_history = []
    
    for i, (cmd, is_pen_cmd) in enumerate(commands):
        print(f"   [{i+1}/{len(commands)}] {cmd}")
        
        # Update position and stats
        old_position = current_position.copy()
        update_execution_stats(cmd, current_position, pen_down, execution_stats)
        
        # Update pen state
        if "M3 S1000" in cmd:
            pen_down = True
            execution_stats['pen_down_count'] += 1
        elif "M3 S0" in cmd:
            pen_down = False
            execution_stats['pen_up_count'] += 1
        
        # Update visualization
        cmd_obj = GCodeCommand(command=cmd.split()[0] if cmd.split() else "G1")
        viz_manager.update_execution_progress(
            i, cmd_obj, 0.3, tuple(current_position), pen_down
        )
        
        # Add line to visualization if position changed and pen is down
        if old_position != current_position and pen_down and viz_manager.visualizer:
            viz_manager.visualizer.add_line(
                old_position[0], old_position[1],
                current_position[0], current_position[1],
                is_drawing=True, command=cmd
            )
        
        # Create progress snapshot
        if i % 3 == 0 or is_pen_cmd:
            phase = ProgressPhase.DRAWING if pen_down else ProgressPhase.MOVING
            snapshot = create_progress_snapshot(
                phase, current_position, pen_down,
                i + 1, len(commands), execution_stats['total_distance'],
                execution_stats['start_time']
            )
            progress_history.append(snapshot)
        
        execution_stats['successful_commands'] += 1
        
        # Simulate execution time
        await asyncio.sleep(0.3)
    
    # Final updates
    execution_stats['end_time'] = time.time()
    execution_stats['total_time'] = execution_stats['end_time'] - execution_stats['start_time']
    execution_stats['efficiency'] = 100.0
    execution_stats['average_command_time'] = execution_stats['total_time'] / len(commands)
    
    print("✅ Simulation completed!")
    
    # Generate PNG visualization
    print(f"\n🖼️  Generating PNG visualization...")
    try:
        png_path = await generate_png_visualization(sample_gcode, execution_stats, progress_history)
        if png_path:
            print(f"✅ PNG saved: {png_path}")
        else:
            print(f"⚠️  PNG generation failed")
    except Exception as e:
        print(f"❌ PNG generation error: {str(e)}")
    
    print(f"\n📊 Demo Summary:")
    print(f"   • Total time: {execution_stats.get('total_time', 0):.1f}s")
    print(f"   • Drawing distance: {execution_stats.get('drawing_distance', 0):.1f}mm")
    print(f"   • Total distance: {execution_stats.get('total_distance', 0):.1f}mm")
    print(f"   • Commands executed: {execution_stats.get('successful_commands', 0)}")
    
    print(f"\n🖼️  Visualization demo completed!")
    print(f"   The enhanced visualization features work with real plotter connections.")
    print(f"   Try: python examples/demo_llm_to_plotter.py /dev/cu.usbserial-14220 --full-viz")
    
    print("🎉 Demo completed!")


if __name__ == "__main__":
    try:
        # Check if this is a visualization demo (no port argument)
        if len(sys.argv) == 1 or (len(sys.argv) == 2 and sys.argv[1] in ['--demo', '--viz-demo']):
            exit_code = asyncio.run(demo_visualization_only())
        else:
            exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⏹️  Interrupted")
        sys.exit(1)
