#!/usr/bin/env python3
"""
Visual Reporting System Demo

Demonstrates comprehensive visual reporting capabilities including
before/after comparison, accuracy analysis, and export in multiple formats.
"""

import time
import json
from pathlib import Path
import sys

# Add promptplot to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from promptplot.core.models import GCodeCommand, GCodeProgram
from promptplot.visualization.visual_reporter import VisualReporter, ReportData, ReportFormat
from promptplot.visualization.progress_monitor import ProgressSnapshot, ProgressPhase, ProgressMetric, MetricType


def create_sample_programs():
    """Create sample programs for comparison reporting"""
    
    # Original program (simple)
    original_commands = [
        GCodeCommand(command="G28"),
        GCodeCommand(command="G1", x=10.0, y=10.0, f=1000),
        GCodeCommand(command="M3", s=255),
        GCodeCommand(command="G1", x=50.0, y=10.0, f=1000),
        GCodeCommand(command="G1", x=50.0, y=50.0, f=1000),
        GCodeCommand(command="G1", x=10.0, y=50.0, f=1000),
        GCodeCommand(command="G1", x=10.0, y=10.0, f=1000),
        GCodeCommand(command="M5"),
        GCodeCommand(command="G28")
    ]
    
    original_program = GCodeProgram(
        commands=original_commands,
        metadata={
            "title": "Original Drawing",
            "description": "Simple rectangle",
            "source": "manual"
        }
    )
    
    # Optimized program (enhanced)
    optimized_commands = [
        GCodeCommand(command="G28"),
        GCodeCommand(command="G90"),  # Added absolute positioning
        GCodeCommand(command="G1", x=10.0, y=10.0, f=1500),  # Faster feed rate
        GCodeCommand(command="M3", s=255),
        # Optimized path with rounded corners
        GCodeCommand(command="G1", x=48.0, y=10.0, f=1500),
        GCodeCommand(command="G2", x=50.0, y=12.0, i=0.0, j=2.0, f=1500),  # Arc
        GCodeCommand(command="G1", x=50.0, y=48.0, f=1500),
        GCodeCommand(command="G2", x=48.0, y=50.0, i=-2.0, j=0.0, f=1500),  # Arc
        GCodeCommand(command="G1", x=12.0, y=50.0, f=1500),
        GCodeCommand(command="G2", x=10.0, y=48.0, i=0.0, j=-2.0, f=1500),  # Arc
        GCodeCommand(command="G1", x=10.0, y=12.0, f=1500),
        GCodeCommand(command="G2", x=10.0, y=10.0, i=2.0, j=0.0, f=1500),  # Arc
        GCodeCommand(command="M5"),
        GCodeCommand(command="G28")
    ]
    
    optimized_program = GCodeProgram(
        commands=optimized_commands,
        metadata={
            "title": "Optimized Drawing",
            "description": "Rectangle with rounded corners and optimized paths",
            "source": "automated_optimization"
        }
    )
    
    return original_program, optimized_program


def create_mock_progress_history():
    """Create mock progress history for reporting"""
    history = []
    start_time = time.time() - 300  # 5 minutes ago
    
    for i in range(20):
        timestamp = start_time + (i * 15)  # Every 15 seconds
        
        # Create metrics
        metrics = {
            MetricType.COMMANDS: ProgressMetric(
                MetricType.COMMANDS, i * 5, 100, "commands", timestamp
            ),
            MetricType.DISTANCE: ProgressMetric(
                MetricType.DISTANCE, i * 12.5, 250.0, "mm", timestamp
            ),
            MetricType.TIME: ProgressMetric(
                MetricType.TIME, i * 15, 300, "seconds", timestamp
            )
        }
        
        # Determine phase
        if i < 2:
            phase = ProgressPhase.HOMING
        elif i < 18:
            phase = ProgressPhase.DRAWING if i % 2 == 0 else ProgressPhase.MOVING
        else:
            phase = ProgressPhase.COMPLETED
        
        snapshot = ProgressSnapshot(
            timestamp=timestamp,
            phase=phase,
            metrics=metrics,
            current_position=(10.0 + i * 2, 10.0 + i * 1.5, 0.0),
            pen_down=(i % 3 != 0)
        )
        
        history.append(snapshot)
    
    return history


def demo_comprehensive_reports():
    """Demonstrate comprehensive report generation"""
    print("📊 Comprehensive Report Generation Demo")
    print("=" * 50)
    
    # Create sample data
    original_program, optimized_program = create_sample_programs()
    progress_history = create_mock_progress_history()
    
    # Create execution stats
    execution_stats = {
        'total_time': 285.6,
        'total_distance': 248.3,
        'drawing_distance': 160.8,
        'movement_distance': 87.5,
        'efficiency': 92.3,
        'command_count': len(optimized_program.commands),
        'average_command_time': 0.18,
        'pen_up_count': 1,
        'pen_down_count': 1
    }
    
    # Create visualizer data
    visualizer_data = {
        'lines': [
            {'start_x': 10, 'start_y': 10, 'end_x': 48, 'end_y': 10, 'is_drawing': True, 'timestamp': time.time()},
            {'start_x': 48, 'start_y': 10, 'end_x': 50, 'end_y': 12, 'is_drawing': True, 'timestamp': time.time()},
            {'start_x': 50, 'start_y': 12, 'end_x': 50, 'end_y': 48, 'is_drawing': True, 'timestamp': time.time()},
            {'start_x': 50, 'start_y': 48, 'end_x': 48, 'end_y': 50, 'is_drawing': True, 'timestamp': time.time()},
            {'start_x': 48, 'start_y': 50, 'end_x': 12, 'end_y': 50, 'is_drawing': True, 'timestamp': time.time()},
            {'start_x': 12, 'start_y': 50, 'end_x': 10, 'end_y': 48, 'is_drawing': True, 'timestamp': time.time()},
            {'start_x': 10, 'start_y': 48, 'end_x': 10, 'end_y': 12, 'is_drawing': True, 'timestamp': time.time()},
            {'start_x': 10, 'start_y': 12, 'end_x': 10, 'end_y': 10, 'is_drawing': True, 'timestamp': time.time()},
        ],
        'statistics': execution_stats,
        'drawing_area': (100.0, 80.0)
    }
    
    # Create report data
    report_data = ReportData(
        program=optimized_program,
        progress_history=progress_history,
        visualizer_data=visualizer_data,
        execution_stats=execution_stats,
        title="PromptPlot v2.0 Comprehensive Drawing Report",
        description="Complete analysis of optimized rectangle drawing with rounded corners"
    )
    
    # Create reporter
    reporter = VisualReporter(output_dir="results/demo_reports")
    
    # Generate reports in all formats
    formats = [
        (ReportFormat.PDF, "PDF"),
        (ReportFormat.HTML, "HTML"),
        (ReportFormat.PNG, "PNG"),
        (ReportFormat.JSON, "JSON")
    ]
    
    generated_reports = []
    
    for format_type, format_name in formats:
        print(f"\nGenerating {format_name} report...")
        try:
            report_path = reporter.generate_comprehensive_report(
                report_data, 
                format=format_type
            )
            generated_reports.append((format_name, report_path))
            print(f"✅ {format_name} report: {report_path}")
        except Exception as e:
            print(f"❌ {format_name} report failed: {str(e)}")
    
    return generated_reports, reporter


def demo_comparison_reports():
    """Demonstrate before/after comparison reports"""
    print("\n🔄 Before/After Comparison Reports Demo")
    print("=" * 50)
    
    # Create sample programs
    original_program, optimized_program = create_sample_programs()
    
    # Create report data for both versions
    original_stats = {
        'total_time': 320.4,
        'total_distance': 280.0,
        'drawing_distance': 160.0,
        'movement_distance': 120.0,
        'efficiency': 78.5,
        'command_count': len(original_program.commands),
        'average_command_time': 0.25
    }
    
    optimized_stats = {
        'total_time': 285.6,
        'total_distance': 248.3,
        'drawing_distance': 160.8,
        'movement_distance': 87.5,
        'efficiency': 92.3,
        'command_count': len(optimized_program.commands),
        'average_command_time': 0.18
    }
    
    # Create visualizer data for original
    original_visualizer_data = {
        'lines': [
            {'start_x': 10, 'start_y': 10, 'end_x': 50, 'end_y': 10, 'is_drawing': True},
            {'start_x': 50, 'start_y': 10, 'end_x': 50, 'end_y': 50, 'is_drawing': True},
            {'start_x': 50, 'start_y': 50, 'end_x': 10, 'end_y': 50, 'is_drawing': True},
            {'start_x': 10, 'start_y': 50, 'end_x': 10, 'end_y': 10, 'is_drawing': True},
        ],
        'statistics': original_stats,
        'drawing_area': (100.0, 80.0)
    }
    
    # Create visualizer data for optimized (from previous demo)
    optimized_visualizer_data = {
        'lines': [
            {'start_x': 10, 'start_y': 10, 'end_x': 48, 'end_y': 10, 'is_drawing': True},
            {'start_x': 48, 'start_y': 10, 'end_x': 50, 'end_y': 12, 'is_drawing': True},
            {'start_x': 50, 'start_y': 12, 'end_x': 50, 'end_y': 48, 'is_drawing': True},
            {'start_x': 50, 'start_y': 48, 'end_x': 48, 'end_y': 50, 'is_drawing': True},
            {'start_x': 48, 'start_y': 50, 'end_x': 12, 'end_y': 50, 'is_drawing': True},
            {'start_x': 12, 'start_y': 50, 'end_x': 10, 'end_y': 48, 'is_drawing': True},
            {'start_x': 10, 'start_y': 48, 'end_x': 10, 'end_y': 12, 'is_drawing': True},
            {'start_x': 10, 'start_y': 12, 'end_x': 10, 'end_y': 10, 'is_drawing': True},
        ],
        'statistics': optimized_stats,
        'drawing_area': (100.0, 80.0)
    }
    
    # Create report data objects
    original_data = ReportData(
        program=original_program,
        progress_history=[],
        visualizer_data=original_visualizer_data,
        execution_stats=original_stats,
        title="Original Rectangle Drawing",
        description="Basic rectangle with sharp corners"
    )
    
    optimized_data = ReportData(
        program=optimized_program,
        progress_history=[],
        visualizer_data=optimized_visualizer_data,
        execution_stats=optimized_stats,
        title="Optimized Rectangle Drawing",
        description="Rectangle with rounded corners and optimized paths"
    )
    
    # Create reporter
    reporter = VisualReporter(output_dir="results/demo_reports")
    
    # Generate comparison reports
    comparison_reports = []
    
    print("Generating PDF comparison report...")
    try:
        pdf_path = reporter.generate_comparison_report(
            original_data, optimized_data, 
            format=ReportFormat.PDF
        )
        comparison_reports.append(("PDF Comparison", pdf_path))
        print(f"✅ PDF comparison report: {pdf_path}")
    except Exception as e:
        print(f"❌ PDF comparison report failed: {str(e)}")
    
    print("Generating HTML comparison report...")
    try:
        html_path = reporter.generate_comparison_report(
            original_data, optimized_data,
            format=ReportFormat.HTML
        )
        comparison_reports.append(("HTML Comparison", html_path))
        print(f"✅ HTML comparison report: {html_path}")
    except Exception as e:
        print(f"❌ HTML comparison report failed: {str(e)}")
    
    # Show improvement metrics
    print(f"\n📈 Optimization Results:")
    print(f"Time improvement: {((original_stats['total_time'] - optimized_stats['total_time']) / original_stats['total_time'] * 100):.1f}%")
    print(f"Distance reduction: {((original_stats['total_distance'] - optimized_stats['total_distance']) / original_stats['total_distance'] * 100):.1f}%")
    print(f"Efficiency improvement: {(optimized_stats['efficiency'] - original_stats['efficiency']):.1f} percentage points")
    
    return comparison_reports, reporter


def demo_file_conversion_reports():
    """Demonstrate file conversion reports"""
    print("\n📁 File Conversion Reports Demo")
    print("=" * 50)
    
    # Simulate file conversion scenario
    original_file = "examples/sample_drawing.svg"
    
    # Create converted program (simulating SVG to G-code conversion)
    converted_commands = [
        GCodeCommand(command="G28"),
        GCodeCommand(command="G90"),
        # Simulated SVG path conversion
        GCodeCommand(command="G1", x=15.0, y=15.0, f=1000),
        GCodeCommand(command="M3", s=255),
        # SVG rectangle path
        GCodeCommand(command="G1", x=45.0, y=15.0, f=1000),
        GCodeCommand(command="G1", x=45.0, y=35.0, f=1000),
        GCodeCommand(command="G1", x=15.0, y=35.0, f=1000),
        GCodeCommand(command="G1", x=15.0, y=15.0, f=1000),
        # SVG circle path (approximated)
        GCodeCommand(command="G1", x=65.0, y=25.0, f=1000),
        GCodeCommand(command="G1", x=68.0, y=27.0, f=1000),
        GCodeCommand(command="G1", x=70.0, y=30.0, f=1000),
        GCodeCommand(command="G1", x=68.0, y=33.0, f=1000),
        GCodeCommand(command="G1", x=65.0, y=35.0, f=1000),
        GCodeCommand(command="G1", x=62.0, y=33.0, f=1000),
        GCodeCommand(command="G1", x=60.0, y=30.0, f=1000),
        GCodeCommand(command="G1", x=62.0, y=27.0, f=1000),
        GCodeCommand(command="G1", x=65.0, y=25.0, f=1000),
        GCodeCommand(command="M5"),
        GCodeCommand(command="G28")
    ]
    
    converted_program = GCodeProgram(
        commands=converted_commands,
        metadata={
            "title": "SVG Conversion Result",
            "description": "Converted from sample_drawing.svg",
            "source_file": original_file,
            "conversion_method": "svg_to_gcode"
        }
    )
    
    # Create conversion statistics
    conversion_stats = {
        'source_file': original_file,
        'source_format': 'SVG',
        'target_format': 'G-code',
        'conversion_time': 2.3,
        'original_elements': 2,  # Rectangle and circle
        'converted_commands': len(converted_commands),
        'accuracy_score': 94.5,
        'fidelity_score': 91.2,
        'optimization_level': 'standard',
        'total_distance': 156.8,
        'drawing_distance': 98.4
    }
    
    # Create reporter
    reporter = VisualReporter(output_dir="results/demo_reports")
    
    print("Generating file conversion report...")
    try:
        conversion_path = reporter.generate_file_conversion_report(
            original_file,
            converted_program,
            conversion_stats,
            format=ReportFormat.PDF
        )
        print(f"✅ File conversion report: {conversion_path}")
        
        # Also generate JSON version for data analysis
        json_path = reporter.generate_file_conversion_report(
            original_file,
            converted_program,
            conversion_stats,
            format=ReportFormat.JSON
        )
        print(f"✅ JSON conversion data: {json_path}")
        
        return [(conversion_path, json_path)], reporter
        
    except Exception as e:
        print(f"❌ File conversion report failed: {str(e)}")
        return [], reporter


def demo_report_analysis():
    """Demonstrate report analysis and insights"""
    print("\n🔍 Report Analysis and Insights Demo")
    print("=" * 50)
    
    # Load and analyze a generated JSON report
    json_reports = list(Path("results/demo_reports").glob("*.json"))
    
    if json_reports:
        latest_report = max(json_reports, key=lambda p: p.stat().st_mtime)
        print(f"Analyzing report: {latest_report.name}")
        
        try:
            with open(latest_report, 'r') as f:
                report_data = json.load(f)
            
            # Extract key insights
            print("\n📊 Key Insights:")
            
            if 'execution_stats' in report_data:
                stats = report_data['execution_stats']
                print(f"• Total execution time: {stats.get('total_time', 0):.1f} seconds")
                print(f"• Drawing efficiency: {stats.get('efficiency', 0):.1f}%")
                print(f"• Average command time: {stats.get('average_command_time', 0):.3f} seconds")
                
                # Calculate derived metrics
                if 'total_distance' in stats and 'total_time' in stats:
                    speed = stats['total_distance'] / max(stats['total_time'], 1)
                    print(f"• Average drawing speed: {speed:.1f} mm/s")
                
                if 'drawing_distance' in stats and 'total_distance' in stats:
                    efficiency = (stats['drawing_distance'] / stats['total_distance']) * 100
                    print(f"• Path efficiency: {efficiency:.1f}% (drawing vs total movement)")
            
            if 'program_info' in report_data:
                prog_info = report_data['program_info']
                print(f"• Total commands: {prog_info.get('total_commands', 0)}")
                
                if 'command_types' in prog_info:
                    cmd_types = prog_info['command_types']
                    print(f"• Command breakdown: {dict(list(cmd_types.items())[:3])}")
            
            # Performance recommendations
            print("\n💡 Performance Recommendations:")
            
            if 'execution_stats' in report_data:
                stats = report_data['execution_stats']
                
                if stats.get('efficiency', 100) < 85:
                    print("• Consider path optimization to improve efficiency")
                
                if stats.get('average_command_time', 0) > 0.2:
                    print("• Command execution time is high - check plotter communication")
                
                drawing_ratio = stats.get('drawing_distance', 0) / max(stats.get('total_distance', 1), 1)
                if drawing_ratio < 0.6:
                    print("• High movement-to-drawing ratio - optimize pen positioning")
                
                if stats.get('total_time', 0) > 300:  # 5 minutes
                    print("• Long execution time - consider breaking into smaller segments")
            
            print("\n✅ Report analysis completed")
            
        except Exception as e:
            print(f"❌ Report analysis failed: {str(e)}")
    else:
        print("No JSON reports found for analysis")


def main():
    """Run all visual reporting demos"""
    print("📋 PromptPlot v2.0 Visual Reporting System Demo")
    print("=" * 60)
    
    try:
        # Demo 1: Comprehensive Reports
        comprehensive_reports, reporter1 = demo_comprehensive_reports()
        
        # Demo 2: Comparison Reports
        comparison_reports, reporter2 = demo_comparison_reports()
        
        # Demo 3: File Conversion Reports
        conversion_reports, reporter3 = demo_file_conversion_reports()
        
        # Demo 4: Report Analysis
        demo_report_analysis()
        
        # Summary
        print(f"\n✨ Visual Reporting Demo Completed!")
        print(f"=" * 60)
        
        all_reports = comprehensive_reports + comparison_reports + conversion_reports
        
        print(f"Generated {len(all_reports)} reports:")
        for report_type, report_path in all_reports:
            print(f"  • {report_type}: {report_path}")
        
        print(f"\nReport features demonstrated:")
        print(f"  ✅ Comprehensive session reports (PDF, HTML, PNG, JSON)")
        print(f"  ✅ Before/after comparison analysis")
        print(f"  ✅ File conversion quality reports")
        print(f"  ✅ Performance metrics and recommendations")
        print(f"  ✅ Visual progress tracking and statistics")
        print(f"  ✅ Automated report generation and analysis")
        
        print(f"\nReports saved to: results/demo_reports/")
        print(f"Open the HTML reports in a browser for interactive viewing!")
        
        # Cleanup
        if reporter1:
            reporter1.close()
        if reporter2:
            reporter2.close()
        if reporter3:
            reporter3.close()
            
    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
    except Exception as e:
        print(f"\nDemo error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()