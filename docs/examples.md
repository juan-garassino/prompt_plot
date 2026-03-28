# Examples

## CLI usage

### Generate GCode from a prompt

```bash
# Basic generation (saves to output/)
promptplot generate "draw a spiral"

# Specify output file
promptplot generate "draw a house" -o house.gcode

# Generate and preview
promptplot generate "draw a mountain range" --visualize

# Use a specific provider and model
promptplot generate "draw a cat" --provider openai --model gpt-4o
```

### Style presets

```bash
# Artistic (default) — full canvas, varied density, hatching
promptplot generate "draw a forest" --style artistic --visualize

# Precise — clean geometry, sharp corners
promptplot generate "draw a grid pattern" --style precise --visualize

# Sketch — overlapping strokes, hand-drawn feel
promptplot generate "draw a portrait" --style sketch --visualize

# Minimal — few strokes, negative space
promptplot generate "draw a bird" --style minimal --visualize
```

### Reference images (multimodal)

```bash
# Generate from a reference image
promptplot generate "draw this scene" --reference photo.jpg --visualize

# Combine with style
promptplot generate "sketch this" --reference portrait.jpg --style sketch
```

Requires vision packages: `uv pip install -e ".[vision]"`

### Plot a GCode file

```bash
# Plot to hardware
promptplot plot drawing.gcode --port /dev/cu.usbserial-10

# Preview only (no hardware needed)
promptplot plot drawing.gcode --preview-only

# Simulation mode
promptplot plot drawing.gcode --simulate

# Brush/ink mode
promptplot plot drawing.gcode --port /dev/cu.usbserial-10 --brush
```

### Preview and analyze

```bash
# Preview a GCode file
promptplot preview drawing.gcode

# Preview with statistics
promptplot preview drawing.gcode --stats

# Save preview to specific path
promptplot preview drawing.gcode -o my_preview.png
```

The preview shows:
- Gray dashed line: paper boundary
- Green dotted line: drawable area (margins)
- Blue lines: drawing strokes
- Red lines: out-of-bounds segments (if any)

### Configuration

```bash
# Show current config
promptplot config show

# Use a custom config file
promptplot --config my_config.yaml generate "draw a star"
```

### Interactive mode

```bash
promptplot interactive
# Type prompts, see GCode, optionally save
```

## Python API

### Generate GCode

```python
import asyncio
from promptplot import get_config, BatchGCodeWorkflow, get_llm_provider

async def main():
    config = get_config()
    llm = get_llm_provider(config.llm)
    wf = BatchGCodeWorkflow(llm=llm, config=config)
    result = await wf.run(prompt="draw a triangle")
    print(result["gcode"])

asyncio.run(main())
```

### Generate with a style preset

```python
import asyncio
from promptplot import get_config, BatchGCodeWorkflow, get_llm_provider

async def main():
    config = get_config()
    llm = get_llm_provider(config.llm)
    wf = BatchGCodeWorkflow(llm=llm, config=config, style="sketch")
    result = await wf.run(prompt="draw a face")
    print(result["gcode"])

asyncio.run(main())
```

### Generate with a reference image

```python
import asyncio
from promptplot import get_config, BatchGCodeWorkflow, get_llm_provider

async def main():
    config = get_config()
    config.vision.enabled = True
    config.vision.reference_image = "photo.jpg"

    llm = get_llm_provider(config.llm)
    wf = BatchGCodeWorkflow(llm=llm, config=config)
    result = await wf.run(prompt="draw this scene")
    print(result["gcode"])

asyncio.run(main())
```

### Process a GCode file

```python
import asyncio
from promptplot import FilePipeline, SimulatedPlotter, get_config

async def main():
    config = get_config()
    pipeline = FilePipeline(config)

    # Preview only
    processed, ok, err = await pipeline.process_file(
        "drawing.gcode", preview_only=True
    )

    # Send to simulated plotter
    plotter = SimulatedPlotter()
    processed, ok, err = await pipeline.process_file(
        "drawing.gcode", plotter=plotter
    )

asyncio.run(main())
```

### Post-process GCode

```python
from promptplot.postprocess import run_pipeline
from promptplot import get_config, GCodeCommand, GCodeProgram

config = get_config()
program = GCodeProgram(commands=[
    GCodeCommand(command="G1", x=10.0, y=10.0, f=3000),
    GCodeCommand(command="G0", x=50.0, y=50.0),
    GCodeCommand(command="G1", x=80.0, y=30.0, f=3000),
])

processed = run_pipeline(program, config)
print(processed.to_gcode())
```

### Bounds validation standalone

```python
from promptplot.postprocess import validate_bounds
from promptplot.config import PaperConfig
from promptplot.models import GCodeCommand, GCodeProgram

paper = PaperConfig(width=210, height=297)
program = GCodeProgram(commands=[
    GCodeCommand(command="G1", x=500, y=50, f=2000),  # out of bounds!
])

fixed, violations = validate_bounds(program, paper, mode="clamp")
print(f"{len(violations)} violations fixed")
print(fixed.to_gcode())
```

### Custom configuration

```python
from promptplot.config import PromptPlotConfig, LLMConfig, PaperConfig, PenConfig, BoundsConfig

config = PromptPlotConfig(
    llm=LLMConfig(
        default_provider="openai",
        openai_model="gpt-4o",
        temperature=0.2,
    ),
    paper=PaperConfig(
        width=297.0,
        height=420.0,
    ),
    pen=PenConfig(
        pen_down_s_value=500,
        feed_rate=3000,
    ),
    bounds=BoundsConfig(
        enforce=True,
        mode="clamp",
    ),
)
```

### Config-aware prompt builder

```python
from promptplot.llm import build_gcode_prompt
from promptplot.config import PaperConfig, PenConfig

prompt = build_gcode_prompt(
    "draw a cat",
    PaperConfig(width=297, height=420),
    PenConfig(pen_down_s_value=500, feed_rate=3000),
    style="sketch",
)
print(prompt)  # Shows actual canvas dimensions, pen values, style guidelines
```
