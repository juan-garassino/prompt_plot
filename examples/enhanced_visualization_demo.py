#!/usr/bin/env python3
"""
Enhanced Visualization System Demo

Demonstrates the new interactive visualization, progress monitoring,
and reporting capabilities of PromptPlot v2.0.
"""

import asyncio
import time
from pathlib import Path
import sys

# Add promptplot to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from promptplot.core.models import GCodeCommand, GCodeProgram
from promptplot.visualization import InteractiveVisualizer, ProgressMonitor, VisualReporter
from promptplot.visualization.visualization_manager import VisualizationManager
from promptplot.plotter.visualizer import GridConfiguration, GridType


def create_sample_program() -> GCodeProgram:
    """Create a sample G-code program for demonstration"""
    commands = [
        # Home and setup
        GCodeCommand(command="G28", comment="Home all axes"),
        GCodeCommand(command="G90", comment="Absolute positioning"),
        
        # Draw a rectangle
        GCodeCommand(command="G1", x=10.0, y=10.0, f=1000, comment="Move to start"),
        GCodeCommand(command="M3", s=255, comment="Pen down"),
        GCodeCommand(command="G1", x=40.0, y=10.0, f=1000, comment="Bottom edge"),
        GCodeCommand(command="G1", x=40.0, y=30.0, f=1000, comment="Right edge"),
        GCodeCommand(command="G1", x=10.0, y=30.0, f=1000, comment="Top edge"),
        GCodeCommand(command="G1", x=10.0, y=10.0, f=1000, comment="Left edge"),
        GCodeCommand(command="M5", comment="Pen up"),
        
        # Move to circle position
        GCodeCommand(command="G1", x=70.0, y=20.0, f=1000, comment="Move to circle"),
        GCodeCommand(command="M3", s=255, comment="Pen down"),
        
        # Draw a circle (approximated with segments)
        GCodeCommand(command="G1", x=75.0, y=22.0, f=1000),
        GCodeCommand(command="G1", x=78.0, y=26.0, f=1000),
        GCodeCommand(command="G1", x=80.0, y=30.0, f=1000),
        GCodeCommand(command="G1", x=78.0, y=34.0, f=1000),
        GCodeCommand(command="G1", x=75.0, y=38.0, f=1000),
        GCodeCommand(command="G1", x=70.0, y=40.0, f=1000),
        GCodeCommand(command="G1", x=65.0, y=38.0, f=1000),
        GCodeCommand(command="G1", x=62.0, y=34.0, f=1000),
        GCodeCommand(command="G1", x=60.0, y=30.0, f=1000),
        GCodeCommand(command="G1", x=62.0, y=26.0, f=1000),
        GCodeCommand(command="G1", x=65.0, y=22.0, f=1000),
        GCodeCommand(command="G1", x=70.0, y=20.0, f=1000),
        
        GCodeCommand(command="M5", comment="Pen up"),
        GCodeCommand(command="G28", comment="Return home")
    ]
    
    return GCodeProgram(
        commands=commands,
        metadata={
            "title": "Demo Drawing",
            "description": "Rectangle and circle demonstration",
            "created_by": "enhanced_visualization_demo"
        }
    )


def demo_interactive_visualizer():
    """Demonstrate interactive visualizer features"""
    print("🎨 Interactive Visualizer Demo")
    print("=" * 50)
    
    # Create sample program
    program = create_sample_program()
    
    # Setup grid configuration
    grid_config = GridConfiguration(
        grid_type=GridType.BOTH,
        major_grid_spacing=(10.0, 10.0),
        minor_grid_spacing=(2.0, 2.0),
        show_coordinates=True
    )
    
    # Create interactive visualizer
    visualizer = InteractiveVisualizer(
        drawing_area=(100.0, 80.0),
        enable_interaction=True,
        grid_config=grid_config
    )
    
    # Simulate drawing execution
    print("Simulating drawing execution...")
    current_pos = (0.0, 0.0, 5.0)
    pen_down = False
    
    for i, command in enumerate(program.commands):
        # Simulate command execution time
        time.sleep(0.1)
        
        # Update position based on command
        if command.is_movement_command():
            new_pos = (
                command.x if command.x is not None else current_pos[0],
                command.y if command.y is not None else current_pos[1],
                command.z if command.z is not None else current_pos[2]
            )
            
            # Add line to visualizer
            visualizer.add_line(
                current_pos[0], current_pos[1],
                new_pos[0], new_pos[1],
                pen_down, command.command
            )
            
            current_pos = new_pos
        
        # Update pen state
        if command.is_pen_down():
            pen_down = True
        elif command.is_pen_up():
            pen_down = False
        
        # Update visualizer position
        visualizer.update_position(current_pos[0], current_pos[1], current_pos[2], pen_down)
    
    # Setup and show interactive visualization
    visualizer.setup_interactive_figure("Enhanced Visualization Demo")
    
    print("Interactive features available:")
    print("- Mouse wheel: Zoom in/out")
    print("- Right-click drag: Pan")
    print("- 'r' key: Fit to drawing")
    print("- 'g' key: Toggle grid")
    print("- 's' key: Save current view")
    print("- Select mode: Click and drag to select areas")
    
    # Enable real-time tracking
    visualizer.enable_real_time_tracking(update_interval=0.5)
    
    # Show visualization (non-blocking for demo)
    visualizer.show_interactive(block=False)
    
    # Save visualization
    saved_path = visualizer.save_current_view()
    print(f"Visualization saved to: {saved_path}")
    
    return visualizer


def demo_progress_monitor():
    """Demonstrate progress monitoring features"""
    print("\n📊 Progress Monitor Demo")
    print("=" * 50)
    
    # Create sample program
    program = create_sample_program()
    
    # Create progress monitor
    monitor = ProgressMonitor(
        enable_visualization=True,
        update_interval=0.5
    )
    
    # Add progress callback
    def progress_callback(snapshot):
        print(f"Progress: {snapshot.overall_percentage:.1f}% - Phase: {snapshot.phase.value}")
    
    monitor.add_progress_callback(progress_callback)
    
    # Start monitoring
    monitor.start_monitoring(program, estimated_duration=len(program.commands) * 0.2)
    
    print("Simulating command execution with progress monitoring...")
    
    # Simulate command execution
    current_pos = (0.0, 0.0, 0.0)
    pen_down = False
    
    for i, command in enumerate(program.commands):
        # Simulate variable execution times
        execution_time = 0.1 + (i % 3) * 0.05
        time.sleep(execution_time)
        
        # Update position
        if command.is_movement_command():
            new_pos = (
                command.x if command.x is not None else current_pos[0],
                command.y if command.y is not None else current_pos[1],
                command.z if command.z is not None else current_pos[2]
            )
            current_pos = new_pos
        
        # Update pen state
        if command.is_pen_down():
            pen_down = True
        elif command.is_pen_up():
            pen_down = False
        
        # Update progress monitor
        monitor.update_command_progress(i, command, execution_time)
        monitor.update_position(current_pos, pen_down)
    
    # Get final progress summary
    summary = monitor.get_progress_summary()
    print(f"\nFinal Progress Summary:")
    print(f"Overall Progress: {summary['overall_progress']:.1f}%")
    print(f"Total Time: {summary['elapsed_time']:.1f}s")
    print(f"Commands: {summary['command_progress']['current']}/{summary['command_progress']['total']}")
    
    # Save progress report
    report_path = monitor.save_progress_report()
    print(f"Progress report saved to: {report_path}")
    
    # Stop monitoring
    monitor.stop_monitoring()
    
    return monitor


def demo_visual_reporter():
    """Demonstrate visual reporting features"""
    print("\n📋 Visual Reporter Demo")
    print("=" * 50)
    
    # Create sample data
    program = create_sample_program()
    
    # Create mock execution stats
    execution_stats = {
        'total_time': 5.2,
        'total_distance': 156.8,
        'drawing_distance': 98.4,
        'movement_distance': 58.4,
        'efficiency': 87.5,
        'command_count': len(program.commands)
    }
    
    # Create mock visualizer data
    visualizer_data = {
        'lines': [
            {'start_x': 10, 'start_y': 10, 'end_x': 40, 'end_y': 10, 'is_drawing': True},
            {'start_x': 40, 'start_y': 10, 'end_x': 40, 'end_y': 30, 'is_drawing': True},
            {'start_x': 40, 'start_y': 30, 'end_x': 10, 'end_y': 30, 'is_drawing': True},
            {'start_x': 10, 'start_y': 30, 'end_x': 10, 'end_y': 10, 'is_drawing': True},
        ],
        'statistics': execution_stats,
        'drawing_area': (100.0, 80.0)
    }
    
    # Create report data
    from promptplot.visualization.visual_reporter import ReportData
    report_data = ReportData(
        program=program,
        progress_history=[],
        visualizer_data=visualizer_data,
        execution_stats=execution_stats,
        title="Enhanced Visualization Demo Report",
        description="Demonstration of PromptPlot v2.0 enhanced visualization capabilities"
    )
    
    # Create reporter
    reporter = VisualReporter()
    
    # Generate comprehensive report
    print("Generating comprehensive PDF report...")
    pdf_path = reporter.generate_comprehensive_report(
        report_data, 
        format=ReportFormat.PDF
    )
    print(f"PDF report generated: {pdf_path}")
    
    # Generate HTML report
    print("Generating HTML report...")
    html_path = reporter.generate_comprehensive_report(
        report_data,
        format=ReportFormat.HTML
    )
    print(f"HTML report generated: {html_path}")
    
    # Generate JSON report
    print("Generating JSON report...")
    json_path = reporter.generate_comprehensive_report(
        report_data,
        format=ReportFormat.JSON
    )
    print(f"JSON report generated: {json_path}")
    
    return reporter


def demo_visualization_manager():
    """Demonstrate unified visualization manager"""
    print("\n🎛️  Visualization Manager Demo")
    print("=" * 50)
    
    # Create sample program
    program = create_sample_program()
    
    # Create visualization manager
    with VisualizationManager(
        drawing_area=(100.0, 80.0),
        enable_interactive=True,
        enable_progress_monitoring=True,
        enable_reporting=True
    ) as viz_manager:
        
        # Start session
        session_id = viz_manager.start_session(program, "demo_session")
        print(f"Started session: {session_id}")
        
        # Show interactive visualization (non-blocking)
        viz_manager.show_interactive_visualization(block=False)
        
        # Simulate execution
        print("Simulating coordinated execution...")
        current_pos = (0.0, 0.0, 0.0)
        pen_down = False
        
        for i, command in enumerate(program.commands):
            execution_time = 0.15 + (i % 4) * 0.05
            time.sleep(execution_time)
            
            # Update position
            if command.is_movement_command():
                new_pos = (
                    command.x if command.x is not None else current_pos[0],
                    command.y if command.y is not None else current_pos[1],
                    command.z if command.z is not None else current_pos[2]
                )
                current_pos = new_pos
            
            # Update pen state
            if command.is_pen_down():
                pen_down = True
            elif command.is_pen_up():
                pen_down = False
            
            # Update all components through manager
            viz_manager.update_execution_progress(
                i, command, execution_time, current_pos, pen_down
            )
            
            # Show progress every 5 commands
            if i % 5 == 0:
                summary = viz_manager.get_progress_summary()
                if 'progress' in summary:
                    progress = summary['progress']['overall_progress']
                    print(f"Progress: {progress:.1f}%")
        
        # Get final summary
        final_summary = viz_manager.get_progress_summary()
        print(f"\nSession completed!")
        print(f"Commands executed: {final_summary['session_data']['commands_executed']}")
        print(f"Total time: {final_summary['session_data']['execution_stats']['total_time']:.1f}s")
        
        # Save current view
        view_path = viz_manager.save_current_view()
        print(f"Final view saved: {view_path}")
        
        # Generate comprehensive report
        print("Generating final session report...")
        report_path = viz_manager.end_session(generate_report=True)
        print(f"Session report generated: {report_path}")


def main():
    """Run all visualization demos"""
    print("🚀 PromptPlot v2.0 Enhanced Visualization System Demo")
    print("=" * 60)
    
    try:
        # Demo 1: Interactive Visualizer
        visualizer = demo_interactive_visualizer()
        
        # Demo 2: Progress Monitor
        monitor = demo_progress_monitor()
        
        # Demo 3: Visual Reporter
        reporter = demo_visual_reporter()
        
        # Demo 4: Visualization Manager (Unified)
        demo_visualization_manager()
        
        print("\n✨ All demos completed successfully!")
        print("\nKey features demonstrated:")
        print("- Interactive visualization with zoom, pan, and selection")
        print("- Real-time progress monitoring with visual dashboard")
        print("- Comprehensive report generation (PDF, HTML, JSON)")
        print("- Unified visualization management")
        print("- Grid overlay system with coordinate display")
        print("- File plotting preview capabilities")
        print("- Performance monitoring and bottleneck detection")
        
        # Keep visualizations open for inspection
        input("\nPress Enter to close all visualizations and exit...")
        
        # Cleanup
        if visualizer:
            visualizer.close()
        if monitor:
            monitor.close()
        if reporter:
            reporter.close()
            
    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
    except Exception as e:
        print(f"\nDemo error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()