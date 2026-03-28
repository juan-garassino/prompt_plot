# PromptPlot

Text → GCode → pen plotter drawing.

Describe what you want drawn. An LLM generates GCode movement instructions.
The GCode gets post-processed (bounds validation, pen safety, stroke optimization,
dwells) and streamed to a pen plotter over USB serial.

## Install

```bash
# With uv (recommended)
uv pip install -e .

# With pip
pip install -e .

# With visualization support
uv pip install -e ".[viz]"

# With multimodal vision support
uv pip install -e ".[vision]"

# With OpenAI / Azure / Gemini LLM providers
uv pip install -e ".[openai]"
uv pip install -e ".[azure]"
uv pip install -e ".[gemini]"
```

## Quick start

**Generate GCode from a prompt:**

```bash
promptplot generate "draw a spiral"
```

**Generate and preview:**

```bash
promptplot generate "draw a house with a tree" --visualize
```

**Generate with a style preset:**

```bash
promptplot generate "draw a cat" --style sketch --visualize
```

**Generate from a reference image:**

```bash
promptplot generate "draw this scene" --reference photo.jpg --visualize
```

**Plot a GCode file to the plotter:**

```bash
promptplot plot drawing.gcode --port /dev/cu.usbserial-10
```

**Preview a GCode file without plotting:**

```bash
promptplot preview drawing.gcode --stats
```

Generated files go to `output/` by default.

## CLI reference

```
promptplot generate <prompt>     Generate GCode from text prompt
  --provider <name>              LLM provider (ollama|openai|azure|gemini)
  --model <name>                 Model name
  -o, --output <path>            Output file (default: output/<slug>_<ts>.gcode)
  --visualize                    Show preview after generation
  --simulate                     Use simulated plotter
  --reference <path>             Reference image for visual guidance (enables multimodal)
  --style <preset>               Drawing style: artistic|precise|sketch|minimal

promptplot plot <file>           Plot a GCode file
  --port <port>                  Serial port
  --baud <rate>                  Baud rate (default: 115200)
  --simulate                     Simulation mode
  --brush                        Enable brush/ink mode
  --preview-only                 Preview without plotting
  -o, --output <path>            Preview output path

promptplot preview <file>        Preview/visualize a GCode file
  -o, --output <path>            Output PNG path
  --stats                        Show statistics

promptplot config show           Display current configuration
promptplot plotter connect       Test plotter connection
promptplot plotter list-ports    List available serial ports
promptplot interactive           Interactive REPL mode
```

## Architecture

11 flat modules under `promptplot/`:

```
promptplot/
├── __init__.py       Public API exports
├── cli.py            Click-based CLI (generate, plot, preview, interactive)
├── config.py         Dataclass config: LLM, paper, pen, brush, bounds, vision, serial, viz
├── llm.py            LLM provider abstraction + config-aware prompt builders + multimodal
├── logger.py         Rich-based workflow logger
├── models.py         GCodeCommand, GCodeProgram, WorkflowResult
├── pipeline.py       File-based async pipeline: load → postprocess → stream
├── plotter.py        Serial and simulated plotter implementations
├── postprocess.py    Bounds → pen safety → stroke optimization → paint dips → dwells
├── visualizer.py     Matplotlib-based GCode preview with bounds overlay
└── workflow.py       Batch and streaming GCode generation workflows + vision refinement
```

**Data flow:**

```
prompt → llm.py → workflow.py → postprocess.py → plotter.py
                                                → visualizer.py
file.gcode → pipeline.py → postprocess.py → plotter.py
                                           → visualizer.py
```

## Configuration

Configuration is a hierarchy of dataclasses. Set via YAML/JSON file or code:

```bash
promptplot --config my_config.yaml generate "draw a cat"
```

```yaml
llm:
  default_provider: ollama
  ollama_model: llama3.2:3b
  temperature: 0.1
paper:
  width: 297.0
  height: 420.0
  margin_x: 10.0
  margin_y: 10.0
pen:
  up_position: 5.0
  down_position: 0.0
  pen_up_delay: 0.2
  pen_down_delay: 0.2
  pen_down_s_value: 1000
  feed_rate: 2000
bounds:
  enforce: true
  mode: clamp           # clamp | reject | warn
vision:
  enabled: false
  reference_image: null
  preview_feedback: false
  max_feedback_iterations: 1
brush:
  enabled: false
  charge_position: [10.0, 10.0]
  strokes_before_reload: 10
serial:
  port: /dev/ttyUSB0
  baud_rate: 115200
workflow:
  output_directory: output
visualization:
  drawing_color: blue
  line_width: 1.0
```

See [docs/configuration.md](docs/configuration.md) for all options.

## LLM providers

| Provider | Model default | Env vars |
|----------|--------------|----------|
| `ollama` | `llama3.2:3b` | — |
| `openai` | `gpt-4o-mini` | `OPENAI_API_KEY` |
| `azure`  | `gpt-4o` | `GPT4_API_KEY`, `GPT4_ENDPOINT`, `GPT4_API_VERSION` |
| `gemini` | `gemini-1.5-flash` | `GOOGLE_API_KEY` |

All providers support multimodal (vision) with optional packages. See [docs/llm-providers.md](docs/llm-providers.md) for setup details.

## Hardware setup

- Pen plotter connected via USB (serial port)
- Firmware: GRBL or compatible (responds "ok" after each command)
- Paper size: A3 (297 x 420mm) or A4 (210 x 297mm)

```bash
# Find your port
promptplot plotter list-ports

# Test connection
promptplot plotter connect --port /dev/cu.usbserial-10

# Plot
promptplot plot drawing.gcode --port /dev/cu.usbserial-10
```

See [docs/hardware.md](docs/hardware.md) for detailed setup.

## Post-processing pipeline

Every GCode program passes through five stages (in order):

0. **Bounds validation** — clamp, reject, or warn on out-of-bounds coordinates
1. **Pen safety** — enforce M5 before G0 moves, M3 before G1, return home
2. **Stroke optimization** — nearest-neighbor reorder to minimize pen lifts
3. **Paint dips** — ink reload sequences every N strokes (brush mode)
4. **Pen dwells** — G4 delays after M3/M5 for pen settle time

See [docs/postprocessing.md](docs/postprocessing.md) for details.

## Style presets

Control the artistic character of generated drawings:

| Style | Description |
|-------|-------------|
| `artistic` | Full canvas, varied density, hatching, organic detail (default) |
| `precise` | Clean geometry, sharp corners, consistent spacing |
| `sketch` | Overlapping strokes, hand-drawn feel, loose lines |
| `minimal` | Few strokes, negative space, essential lines only |

```bash
promptplot generate "draw a portrait" --style sketch
```

## Python API

```python
import asyncio
from promptplot import (
    PromptPlotConfig, get_config, BatchGCodeWorkflow,
    FilePipeline, SimulatedPlotter, get_llm_provider,
)

async def main():
    config = get_config()
    llm = get_llm_provider(config.llm)
    wf = BatchGCodeWorkflow(llm=llm, config=config)
    result = await wf.run(prompt="draw a triangle")
    print(result["gcode"])

asyncio.run(main())
```

## License

MIT — see [LICENSE](LICENSE).
