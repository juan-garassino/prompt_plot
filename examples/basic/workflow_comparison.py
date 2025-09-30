#!/usr/bin/env python3
"""
Workflow Comparison Example

This example demonstrates the differences between workflow types:
- Simple Batch Workflow
- Advanced Sequential Workflow
- Performance comparison
- Feature comparison
- Use case recommendations
"""

import asyncio
import sys
import os
import time

# Add the parent directory to the path so we can import promptplot
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from promptplot.workflows import SimpleBatchWorkflow, AdvancedSequentialWorkflow
from promptplot.plotter import SimulatedPlotter


async def test_workflow(workflow_name, workflow, prompt, test_number):
    """Test a workflow with a given prompt."""
    print(f"\n   Test {test_number}: {workflow_name}")
    print(f"   Prompt: {prompt}")
    
    start_time = time.time()
    
    try:
        result = await workflow.execute(prompt)
        end_time = time.time()
        
        if result.success:
            execution_time = end_time - start_time
            commands = len(result.commands)
            
            print(f"   ✓ Success:")
            print(f"     Commands: {commands}")
            print(f"     Time: {execution_time:.2f}s")
            
            # Additional metrics for advanced workflow
            if hasattr(result, 'validation_passes'):
                print(f"     Validation passes: {result.validation_passes}")
            if hasattr(result, 'retry_count'):
                print(f"     Retries: {result.retry_count}")
            
            return {
                'success': True,
                'commands': commands,
                'time': execution_time,
                'validation_passes': getattr(result, 'validation_passes', 0),
                'retries': getattr(result, 'retry_count', 0)
            }
        else:
            print(f"   ✗ Failed: {result.error_message}")
            return {'success': False, 'time': end_time - start_time}
            
    except Exception as e:
        end_time = time.time()
        print(f"   ✗ Error: {e}")
        return {'success': False, 'time': end_time - start_time, 'error': str(e)}


async def main():
    """Main comparison function."""
    print("PromptPlot Workflow Comparison")
    print("=" * 40)
    
    # Set up plotters (separate for each workflow to avoid interference)
    print("1. Setting up plotters and workflows...")
    
    plotter1 = SimulatedPlotter(visualize=False)  # Disable visualization for speed
    plotter2 = SimulatedPlotter(visualize=False)
    
    # Create workflows
    simple_workflow = SimpleBatchWorkflow(plotter=plotter1)
    advanced_workflow = AdvancedSequentialWorkflow(
        plotter=plotter2,
        max_steps=50,
        max_retries=3,
        validation_enabled=True
    )
    
    print("   ✓ Simple Batch Workflow ready")
    print("   ✓ Advanced Sequential Workflow ready")
    
    # Test prompts of varying complexity
    test_prompts = [
        {
            'name': 'Simple Shape',
            'prompt': 'Draw a 30mm square',
            'complexity': 'Low'
        },
        {
            'name': 'Medium Complexity',
            'prompt': 'Draw a circle with 25mm radius and add 4 small dots at cardinal points',
            'complexity': 'Medium'
        },
        {
            'name': 'Complex Pattern',
            'prompt': 'Draw a mandala with central circle, 6 petals, and decorative border',
            'complexity': 'High'
        },
        {
            'name': 'Geometric Design',
            'prompt': 'Draw overlapping triangles forming a star pattern with connecting lines',
            'complexity': 'Medium-High'
        }
    ]
    
    print(f"\n2. Running comparison tests ({len(test_prompts)} prompts)...")
    
    results = {
        'Simple Batch': [],
        'Advanced Sequential': []
    }
    
    for i, test in enumerate(test_prompts, 1):
        print(f"\n--- Test Case {i}: {test['name']} (Complexity: {test['complexity']}) ---")
        
        # Test Simple Batch Workflow
        simple_result = await test_workflow(
            "Simple Batch", simple_workflow, test['prompt'], f"{i}a"
        )
        results['Simple Batch'].append(simple_result)
        
        # Small delay between tests
        await asyncio.sleep(0.5)
        
        # Test Advanced Sequential Workflow
        advanced_result = await test_workflow(
            "Advanced Sequential", advanced_workflow, test['prompt'], f"{i}b"
        )
        results['Advanced Sequential'].append(advanced_result)
        
        # Compare results for this test
        if simple_result['success'] and advanced_result['success']:
            time_diff = advanced_result['time'] - simple_result['time']
            command_diff = advanced_result['commands'] - simple_result['commands']
            
            print(f"\n   Comparison:")
            print(f"     Time difference: {time_diff:+.2f}s")
            print(f"     Command difference: {command_diff:+d}")
            
            if advanced_result['time'] < simple_result['time']:
                print(f"     ⚡ Advanced workflow was faster")
            else:
                print(f"     🐌 Simple workflow was faster")
        
        await asyncio.sleep(1)
    
    # Overall analysis
    print(f"\n3. Overall Analysis:")
    print("=" * 30)
    
    # Calculate success rates
    simple_successes = sum(1 for r in results['Simple Batch'] if r['success'])
    advanced_successes = sum(1 for r in results['Advanced Sequential'] if r['success'])
    
    print(f"\nSuccess Rates:")
    print(f"   Simple Batch: {simple_successes}/{len(test_prompts)} ({simple_successes/len(test_prompts)*100:.1f}%)")
    print(f"   Advanced Sequential: {advanced_successes}/{len(test_prompts)} ({advanced_successes/len(test_prompts)*100:.1f}%)")
    
    # Calculate average times (only for successful runs)
    simple_times = [r['time'] for r in results['Simple Batch'] if r['success']]
    advanced_times = [r['time'] for r in results['Advanced Sequential'] if r['success']]
    
    if simple_times and advanced_times:
        avg_simple = sum(simple_times) / len(simple_times)
        avg_advanced = sum(advanced_times) / len(advanced_times)
        
        print(f"\nAverage Execution Times:")
        print(f"   Simple Batch: {avg_simple:.2f}s")
        print(f"   Advanced Sequential: {avg_advanced:.2f}s")
        print(f"   Difference: {avg_advanced - avg_simple:+.2f}s")
    
    # Calculate average commands
    simple_commands = [r['commands'] for r in results['Simple Batch'] if r['success']]
    advanced_commands = [r['commands'] for r in results['Advanced Sequential'] if r['success']]
    
    if simple_commands and advanced_commands:
        avg_simple_cmd = sum(simple_commands) / len(simple_commands)
        avg_advanced_cmd = sum(advanced_commands) / len(advanced_commands)
        
        print(f"\nAverage Command Count:")
        print(f"   Simple Batch: {avg_simple_cmd:.1f}")
        print(f"   Advanced Sequential: {avg_advanced_cmd:.1f}")
        print(f"   Difference: {avg_advanced_cmd - avg_simple_cmd:+.1f}")
    
    # Advanced workflow specific metrics
    total_validations = sum(r.get('validation_passes', 0) for r in results['Advanced Sequential'])
    total_retries = sum(r.get('retries', 0) for r in results['Advanced Sequential'])
    
    print(f"\nAdvanced Workflow Metrics:")
    print(f"   Total validation passes: {total_validations}")
    print(f"   Total retries needed: {total_retries}")
    print(f"   Average validations per prompt: {total_validations/len(test_prompts):.1f}")
    
    # Recommendations
    print(f"\n4. Recommendations:")
    print("=" * 20)
    print("\nUse Simple Batch Workflow when:")
    print("   • Speed is priority")
    print("   • Drawing simple geometric shapes")
    print("   • Prototyping and testing")
    print("   • Resource constraints exist")
    
    print("\nUse Advanced Sequential Workflow when:")
    print("   • Quality is priority")
    print("   • Drawing complex patterns")
    print("   • Production use")
    print("   • Error recovery is important")
    
    print(f"\n5. Workflow comparison completed!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nComparison interrupted by user")
    except Exception as e:
        print(f"\nComparison failed: {e}")
        sys.exit(1)