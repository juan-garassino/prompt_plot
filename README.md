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

**Draw something (simulated, no hardware needed):**

```bash
promptplot draw "a spiral galaxy" --simulate
```

**Draw with real-time streaming (pen moves while LLM thinks):**

```bash
promptplot draw "a cat" --live --simulate
```

**Draw on a real plotter:**

```bash
promptplot draw "a mountain range" --port /dev/cu.usbserial-1420
```

**Draw with composition planning (LLM plans layout before generating):**

```bash
promptplot draw "a house with garden and sun" --plan --simulate
```

**Draw with quality gate (reject bad output):**

```bash
promptplot draw "a flower" --port /dev/cu.usbserial-1420 --min-grade B
```

**Resume an interrupted drawing:**

```bash
promptplot draw "a spiral galaxy" --port /dev/cu.usbserial-1420 --resume
```

**Generate GCode without plotting:**

```bash
promptplot generate "draw a house with a tree" --visualize --score
```

**Preview an existing GCode file:**

```bash
promptplot preview drawing.gcode --stats --score
```

**Plot an existing GCode file:**

```bash
promptplot plot drawing.gcode --port /dev/cu.usbserial-10
```

Generated files go to `output/` by default.

## CLI reference

### `draw` — prompt to paper in one shot

The main command. Generates GCode from a text prompt, scores it, and streams
it to the plotter.

```
promptplot draw <prompt>
  --port <port>                  Serial port
  --baud <rate>                  Baud rate (default: 115200)
  --simulate                     Simulated plotter (no hardware)
  --provider <name>              LLM provider (ollama|openai|azure|gemini)
  --model <name>                 Model name
  --style <preset>               Drawing style: artistic|precise|sketch|minimal
  --multipass                    Two-pass generation (outline + detail)
  --live                         Real-time mode: LLM → validate → plotter, one command at a time
  --max-steps <n>                Max LLM steps in live mode (default: 80)
  -o, --save <path>              Save GCode to file
  --preview                      Save preview PNG
  --min-grade <A|B|C|D|F>       Minimum quality grade to send to plotter (default: D)
  --plan                         Enable LLM composition planning phase
  --resume                       Resume from last checkpoint
```

**Batch mode (default):** LLM generates the full drawing, quality is scored,
and if it meets `--min-grade` the whole program streams to the plotter.
Global stroke optimization reduces pen lifts and travel.

**Live mode (`--live`):** LLM generates one command at a time. Each command is
validated (bounds clamped, pen safety enforced) and sent to the plotter
immediately. The pen moves while the LLM is still thinking about the next
command. No global optimization, but maximum real-time feel.

### `generate` — generate GCode without plotting

```
promptplot generate <prompt>
  --provider <name>              LLM provider (ollama|openai|azure|gemini)
  --model <name>                 Model name
  -o, --output <path>            Output file (default: output/<slug>_<ts>.gcode)
  --visualize                    Save preview PNG after generation
  --simulate                     Use simulated plotter
  --reference <path>             Reference image for visual guidance (enables multimodal)
  --style <preset>               Drawing style: artistic|precise|sketch|minimal
  --score                        Show quality score
  --multipass                    Two-pass generation (outline + detail)
  --style-from <path>            Reference GCode file for style transfer
```

### `plot` — plot an existing GCode file

```
promptplot plot <file>
  --port <port>                  Serial port
  --baud <rate>                  Baud rate (default: 115200)
  --simulate                     Simulation mode
  --brush                        Enable brush/ink mode (paint recharging)
  --preview-only                 Preview without plotting
  -o, --output <path>            Preview output path
```

### `score` — score a GCode file

```
promptplot score <file>
```

Shows quality metrics: canvas utilization, stroke count, draw/travel ratio,
pen lifts, estimated time, and a letter grade (A through F).

### `preview` — visualize a GCode file

```
promptplot preview <file>
  -o, --output <path>            Output PNG path
  --stats                        Show statistics
  --score                        Show quality score
```

### Other commands

```
promptplot config show           Display current configuration
promptplot plotter connect       Test plotter connection
promptplot plotter list-ports    List available serial ports
promptplot interactive           Interactive REPL mode
```

## Architecture

15 flat modules under `promptplot/`:

```
promptplot/
├── __init__.py       Public API exports
├── checkpoint.py     Resumable drawing checkpoints (~/.promptplot/checkpoints/)
├── cli.py            Click CLI (draw, generate, plot, preview, score, interactive, ui)
├── config.py         Dataclass config: LLM, paper, pen, brush, bounds, vision, serial, viz, workflow
├── engine.py         Workflow engine, PenState, Phase transitions, DrawingSession
├── llm.py            LLM provider abstraction + prompt builders + composition planning
├── logger.py         Rich-based workflow logger
├── memory.py         Drawing memory (JSONL) for few-shot learning
├── models.py         GCodeCommand, GCodeProgram, WorkflowResult, CompositionPlan (Pydantic)
├── pipeline.py       File-based async pipeline: load → postprocess → stream
├── plotter.py        Connection state machine, serial/simulated plotter, ALARM recovery
├── postprocess.py    Bounds → arcs → pen safety → stroke optimization → paint dips → dwells
├── scoring.py        Quality scorer (A–F grades) + style profile extraction
├── tui.py            Rich-based TUI with live status display
├── visualizer.py     Matplotlib-based GCode preview with bounds overlay
└── workflow.py       Batch (with planning), streaming, and live draw workflows
```

**Data flow:**

```
prompt → llm.py (plan?) → workflow.py → postprocess.py → plotter.py
                                                        → visualizer.py
file.gcode → pipeline.py → postprocess.py → plotter.py
                                           → visualizer.py
```

## State management

PromptPlot uses proper state machines throughout:

**PenState** — tracks pen up/down and validates commands. G0 requires pen UP,
G1 requires pen DOWN. Used in postprocessing, live workflows, and the simulated
plotter. The postprocessor uses `set_up()`/`set_down()` to fix violations; the
validator uses `process()` to detect them.

**Phase transitions** — the drawing lifecycle follows validated phases:

```
IDLE → PLANNING → GENERATING → STREAMING ↔ PAUSED → DONE → IDLE
```

Invalid transitions (e.g. IDLE → DONE) raise `IllegalTransitionError`.
Use `force=True` to bypass in exceptional cases.

**Plotter connection** — a state machine manages the serial connection:

```
DISCONNECTED → CONNECTING → IDLE → STREAMING ↔ PAUSED → IDLE → DISCONNECTED
                                  ↘ ALARM → RECOVERY ↗
```

ALARM is detected automatically from firmware responses. Recovery sends `$X`
(soft reset) and `$H` (home). Pause/resume use GRBL feed hold (`!`/`~`).

**Checkpoints** — interrupted drawings are saved to `~/.promptplot/checkpoints/`.
Resume with `--resume` to skip already-sent commands.

## Composition planning

The `--plan` flag enables an LLM-driven planning phase before GCode generation.
The LLM first creates a `CompositionPlan` that specifies subjects, positions,
sizes, and density. This plan is then injected as structured guidance into the
GCode generation prompt.

```bash
promptplot draw "a house with a garden and sun" --plan --simulate
```

The planning phase adds PLANNING to the lifecycle: IDLE → PLANNING → GENERATING → DONE.

## Configuration

Configuration is a hierarchy of dataclasses. Set via YAML/JSON file or code:

```bash
promptplot --config my_config.yaml draw "draw a cat" --simulate
```

```yaml
llm:
  default_provider: ollama
  ollama_model: llama3.2:3b
  temperature: 0.1

paper:
  width: 297.0          # mm (A3)
  height: 420.0
  margin_x: 10.0
  margin_y: 10.0

pen:
  up_position: 5.0
  down_position: 0.0
  pen_up_delay: 0.2     # seconds — G4 dwell after pen up
  pen_down_delay: 0.2   # seconds — G4 dwell after pen down
  pen_down_s_value: 1000 # S parameter for M3 (pen down force)
  feed_rate: 2000        # F parameter for G1 (draw speed mm/min)

bounds:
  enforce: true
  mode: clamp            # clamp | reject | warn

vision:
  enabled: false
  reference_image: null
  preview_feedback: false
  max_feedback_iterations: 1

brush:
  enabled: false
  charge_position: [10.0, 10.0]  # where the paint/ink is (X, Y in mm)
  dip_height: 0.0                # Z height to dip into ink
  dip_duration: 0.5              # seconds holding in ink
  drip_duration: 1.0             # seconds dripping after lift
  strokes_before_reload: 10      # dip every N strokes
  pause_after_move: 0.1          # seconds between brush moves

serial:
  port: /dev/ttyUSB0
  baud_rate: 115200

workflow:
  output_directory: output
  planning_enabled: false         # --plan flag enables this
  multipass:
    enabled: false
    outline_style: precise
    detail_style: artistic

visualization:
  drawing_color: blue
  line_width: 1.0
```

## LLM providers

| Provider | Model default | Env vars |
|----------|--------------|----------|
| `ollama` | `llama3.2:3b` | — |
| `openai` | `gpt-4o-mini` | `OPENAI_API_KEY` |
| `azure`  | `gpt-4o` | `GPT4_API_KEY`, `GPT4_ENDPOINT`, `GPT4_API_VERSION` |
| `gemini` | `gemini-1.5-flash` | `GOOGLE_API_KEY` |

```bash
# Use a specific provider
promptplot draw "a cat" --provider openai --model gpt-4o --simulate

# Ollama is the default (no API key needed, runs locally)
promptplot draw "a spiral" --simulate
```

All providers support multimodal (vision) with optional packages.

## Quality scoring

Every generated drawing can be scored on quality:

```bash
# Score during generation
promptplot draw "a flower" --simulate --min-grade B

# Score an existing file
promptplot score drawing.gcode

# Score with preview
promptplot preview drawing.gcode --score --stats
```

Metrics:
- **Canvas utilization** — % of drawable area used
- **Draw/travel ratio** — drawing distance vs wasted pen-up travel
- **Stroke count** — number of continuous draw sequences
- **Pen lift count** — number of M5 commands
- **Estimated time** — based on total distance and feed rate
- **Grade** — A through F based on utilization and efficiency

The `--min-grade` flag on `draw` rejects output below the threshold and
won't send it to the plotter.

## Drawing memory

PromptPlot remembers successful drawings. When you generate a new drawing,
it checks memory for similar past prompts and uses them as few-shot examples
to improve quality.

Memory is stored at `~/.promptplot/memory/drawings.jsonl`. Only drawings
graded A or B are saved automatically.

## Multi-pass generation

For complex prompts, `--multipass` generates in two passes:

1. **Outline pass** — clean structure and main shapes (precise style)
2. **Detail pass** — texture, fill, and fine detail (artistic style)

The two passes are merged and post-processed together.

```bash
promptplot draw "a detailed cityscape" --multipass --simulate
```

## Style transfer

Use an existing GCode file as a style reference. The system extracts stroke
characteristics (length, density, direction variance) and instructs the LLM
to match that style:

```bash
promptplot generate "draw a tree" --style-from reference.gcode --visualize
```

## Brush / paint mode

For plotters with a brush instead of a pen, enable brush mode to automatically
insert paint recharging sequences:

```bash
promptplot plot drawing.gcode --brush --port /dev/cu.usbserial-10
```

Or configure in YAML:

```yaml
brush:
  enabled: true
  charge_position: [10.0, 10.0]  # where the paint is
  strokes_before_reload: 10       # dip every 10 strokes
  dip_duration: 0.5               # hold in paint for 0.5s
  drip_duration: 1.0              # drip for 1s after lifting
```

The postprocessor inserts a sequence every N strokes:
pen up → travel to paint station → dip → hold → lift → drip pause → return to drawing.

## Post-processing pipeline

Every GCode program passes through six stages (in order):

0. **Arc approximation** — convert G2/G3 arcs to short G1 line segments
1. **Bounds validation** — clamp, reject, or warn on out-of-bounds coordinates
2. **Pen safety** — enforce M5 before G0 travel, M3 before G1 draw, return home
3. **Stroke optimization** — nearest-neighbor reorder to minimize pen lifts and travel
4. **Paint dips** — ink reload sequences every N strokes (brush mode only)
5. **Pen dwells** — G4 delays after M3/M5 for pen settle time

In live mode (`--live`), per-command validation applies bounds clamping and
pen safety in real time as each command is generated and sent.

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
promptplot draw "a spiral" --port /dev/cu.usbserial-10
```

Serial ports by platform:
- macOS: `/dev/cu.usbserial-*` (e.g. `/dev/cu.usbserial-1420`)
- Linux: `/dev/ttyUSB0`
- Windows: `COM3`

## Python API

```python
import asyncio
from promptplot import (
    PromptPlotConfig, get_config, BatchGCodeWorkflow,
    LiveDrawWorkflow, SimulatedPlotter, get_llm_provider,
    score_gcode, PenState, ConnectionState, CheckpointManager,
)

async def main():
    config = get_config()
    llm = get_llm_provider(config.llm)

    # Batch generation
    wf = BatchGCodeWorkflow(llm=llm, config=config)
    result = await wf.run(prompt="draw a triangle")
    print(result["gcode"])

    # Batch generation with composition planning
    config.workflow.planning_enabled = True
    wf = BatchGCodeWorkflow(llm=llm, config=config)
    result = await wf.run(prompt="a house with garden")

    # PenState tracking
    pen = PenState()
    pen.process("M3 S1000")   # pen down
    assert pen.is_down
    pen.process("M5")          # pen up
    assert pen.is_up

    # Live drawing to simulated plotter
    plotter = SimulatedPlotter()
    await plotter.connect()
    assert plotter.connection_state == ConnectionState.IDLE
    live = LiveDrawWorkflow(llm=llm, config=config, plotter=plotter)
    result = await live.run("draw a spiral")
    await plotter.disconnect()

asyncio.run(main())
```

## License

MIT — see [LICENSE](LICENSE).
