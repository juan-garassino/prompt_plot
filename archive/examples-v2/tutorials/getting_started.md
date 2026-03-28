# Getting Started with PromptPlot

This tutorial will guide you through your first steps with PromptPlot v2.0, from installation to creating your first drawing.

## Learning Objectives

By the end of this tutorial, you will:
- Have PromptPlot installed and working
- Understand basic PromptPlot concepts
- Create your first drawing from a prompt
- Know how to use different workflow types
- Be able to troubleshoot common issues

## Prerequisites

- Python 3.8 or higher
- Basic command line knowledge
- Text editor or IDE

## Step 1: Installation

### Basic Installation

Install PromptPlot using pip:

```bash
pip install promptplot
```

### Development Installation

For the latest features, install from source:

```bash
git clone <repository-url>
cd promptplot
pip install -e .
```

### Verify Installation

Test that PromptPlot is installed correctly:

```bash
python -c "import promptplot; print(promptplot.__version__)"
```

You should see the version number (e.g., "2.0.0").

## Step 2: Understanding Key Concepts

### Workflows
Workflows are the main entry points for using PromptPlot. They handle the process of converting prompts to G-code and executing them.

**Types:**
- **SimpleBatchWorkflow**: Basic prompt-to-G-code conversion
- **AdvancedSequentialWorkflow**: Enhanced with validation and error recovery
- **SimpleStreamingWorkflow**: Real-time streaming to plotter
- **AdvancedStreamingWorkflow**: Enhanced streaming with monitoring
- **FilePlottingWorkflow**: Direct file conversion and plotting

### Plotters
Plotters are interfaces to drawing hardware (real or simulated).

**Types:**
- **SimulatedPlotter**: Virtual plotter with visualization
- **SerialPlotter**: Real hardware via serial connection

### Strategies
Strategies determine how drawings are optimized.

**Types:**
- **Orthogonal**: Optimized for straight lines and geometric shapes
- **Non-orthogonal**: Handles curves and complex paths

## Step 3: Your First Drawing

Create a new file called `first_drawing.py`:

```python
import asyncio
from promptplot.workflows import SimpleBatchWorkflow
from promptplot.plotter import SimulatedPlotter

async def main():
    # Set up a simulated plotter
    plotter = SimulatedPlotter(visualize=True)
    
    # Create a workflow
    workflow = SimpleBatchWorkflow(plotter=plotter)
    
    # Execute a drawing
    result = await workflow.execute("Draw a 50mm square")
    
    if result.success:
        print(f"Success! Generated {len(result.commands)} commands")
    else:
        print(f"Failed: {result.error_message}")

if __name__ == "__main__":
    asyncio.run(main())
```

Run the script:

```bash
python first_drawing.py
```

**Expected Output:**
- A visualization window showing a square
- Console output showing success and command count
- The visualization window stays open until you close it

## Step 4: Exploring Different Prompts

Try different prompts to see what PromptPlot can do:

```python
prompts = [
    "Draw a circle with 30mm radius",
    "Draw a triangle with 40mm sides",
    "Draw a star with 5 points",
    "Draw a spiral with 3 turns",
    "Draw the word HELLO in block letters"
]

for prompt in prompts:
    print(f"Drawing: {prompt}")
    result = await workflow.execute(prompt)
    if result.success:
        print(f"  ✓ Success: {len(result.commands)} commands")
    else:
        print(f"  ✗ Failed: {result.error_message}")
    
    # Wait a moment between drawings
    await asyncio.sleep(2)
```

## Step 5: Using Different Workflows

### Advanced Sequential Workflow

For more complex drawings with validation:

```python
from promptplot.workflows import AdvancedSequentialWorkflow

# Create advanced workflow
advanced_workflow = AdvancedSequentialWorkflow(
    plotter=plotter,
    max_steps=100,
    validation_enabled=True,
    max_retries=3
)

# Try a complex prompt
complex_prompt = "Draw a mandala with a central circle, 8 petals, and decorative border"
result = await advanced_workflow.execute(complex_prompt)

if result.success:
    print(f"Advanced drawing completed:")
    print(f"  Commands: {len(result.commands)}")
    print(f"  Validation passes: {result.validation_passes}")
    print(f"  Retries: {result.retry_count}")
```

### Streaming Workflow

For real-time drawing:

```python
from promptplot.workflows import SimpleStreamingWorkflow

# Create streaming workflow
streaming_workflow = SimpleStreamingWorkflow(
    plotter=plotter,
    stream_delay=0.1  # 100ms between commands
)

# Stream a drawing
print("Starting streaming drawing...")
async for command in streaming_workflow.stream("Draw a sine wave"):
    print(f"Executing: {command}")
```

## Step 6: Configuration

### Basic Configuration

Create a configuration file `config.yaml`:

```yaml
llm:
  provider: ollama
  model: llama3.2:3b
  timeout: 30

plotter:
  type: simulated
  visualization: true
  canvas_size: [200, 200]

workflow:
  max_retries: 3
  validation_enabled: true
```

Use the configuration:

```python
from promptplot.config import load_config

config = load_config("config.yaml")
plotter = SimulatedPlotter.from_config(config)
workflow = SimpleBatchWorkflow.from_config(config, plotter=plotter)
```

### Environment Variables

Set configuration via environment variables:

```bash
export PROMPTPLOT_LLM_PROVIDER=ollama
export PROMPTPLOT_PLOTTER_TYPE=simulated
export PROMPTPLOT_VISUALIZATION_ENABLED=true
```

## Step 7: Error Handling

Handle common errors gracefully:

```python
async def safe_drawing(workflow, prompt):
    try:
        result = await workflow.execute(prompt)
        
        if result.success:
            print(f"✓ Success: {prompt}")
            return result
        else:
            print(f"✗ Failed: {prompt}")
            print(f"  Error: {result.error_message}")
            return None
            
    except Exception as e:
        print(f"✗ Exception: {prompt}")
        print(f"  Error: {e}")
        return None

# Use safe drawing
result = await safe_drawing(workflow, "Draw a complex geometric pattern")
```

## Step 8: Saving Results

Save G-code to files:

```python
def save_gcode(result, filename):
    if result and result.success:
        with open(filename, 'w') as f:
            f.write(f"; Generated by PromptPlot\n")
            f.write(f"; Commands: {len(result.commands)}\n\n")
            
            for command in result.commands:
                f.write(f"{command.to_gcode()}\n")
        
        print(f"G-code saved to {filename}")
    else:
        print("No valid result to save")

# Save your drawing
result = await workflow.execute("Draw a house with windows and door")
save_gcode(result, "house_drawing.gcode")
```

## Common Issues and Solutions

### Issue: "No module named 'promptplot'"

**Solution:** Make sure PromptPlot is installed:
```bash
pip install promptplot
```

### Issue: "Could not connect to Ollama"

**Solution:** Start Ollama service:
```bash
ollama serve
```

### Issue: Visualization window doesn't appear

**Solution:** Check your display backend:
```python
import matplotlib
matplotlib.use('TkAgg')  # or 'Qt5Agg'
```

### Issue: Drawing looks wrong

**Solutions:**
- Check your prompt clarity
- Try a simpler prompt first
- Enable validation in advanced workflows
- Check the coordinate system

## Next Steps

Now that you have the basics:

1. **Try Hardware**: Follow the hardware setup tutorial
2. **File Conversion**: Learn to convert SVG and other files
3. **Advanced Features**: Explore computer vision integration
4. **Configuration**: Set up custom configurations
5. **Integration**: Build applications with PromptPlot

## Practice Exercises

1. **Basic Shapes**: Draw squares, circles, triangles of different sizes
2. **Positioning**: Draw shapes at specific coordinates
3. **Combinations**: Combine multiple shapes in one drawing
4. **Text**: Try drawing text and letters
5. **Patterns**: Create repeating patterns and designs

## Summary

You've learned:
- ✓ How to install PromptPlot
- ✓ Basic concepts (workflows, plotters, strategies)
- ✓ Creating your first drawing
- ✓ Using different workflow types
- ✓ Basic configuration
- ✓ Error handling
- ✓ Saving results

Continue with the hardware setup tutorial to connect real plotters, or explore file conversion to work with existing designs.