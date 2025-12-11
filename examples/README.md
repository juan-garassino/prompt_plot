# PromptPlot Examples & Demos

This directory contains comprehensive examples and demos for using PromptPlot v2.0.

## Demo Files

| File | Description | Requirements |
|------|-------------|--------------|
| `demo_quick_start.py` | Basic introduction to PromptPlot components | None |
| `demo_plotter_connection.py` | Test plotter connections (simulated & serial) | Optional: serial plotter |
| `demo_llm_generation.py` | Generate G-code using LLM (no plotter) | OpenAI, Gemini, Azure, or Ollama |
| `demo_llm_to_plotter.py` | **Generate G-code AND send to real plotter with interactive visualization** | LLM + serial plotter + matplotlib |
| `demo_llm_streaming.py` | Real-time streaming G-code generation | OpenAI, Gemini, Azure, or Ollama |
| `demo_visualization.py` | Visual reporting and progress monitoring | matplotlib |
| `demo_cli.py` | Command-line interface demonstration | None |
| `demo_comprehensive.py` | Complete test suite for all features | None |

---

## Pen Plotter Hardware Guide

### How GRBL Pen Plotters Work

Most pen plotters use GRBL firmware, which interprets G-code commands sent over serial (USB). The plotter has:

- **X/Y stepper motors** - Move the pen carriage across the drawing surface
- **Servo motor** - Lifts and lowers the pen (controlled via spindle commands)
- **Serial connection** - Typically 115200 baud rate

### G-code Commands Reference

#### Movement Commands

| Command | Description | Example |
|---------|-------------|---------|
| `G0` | Rapid move (pen up travel) | `G0 X10 Y20` |
| `G1` | Linear move (drawing) | `G1 X50 Y50 F1000` |
| `G28` | Home all axes | `G28` |

#### Pen Control (Servo-based plotters)

GRBL uses spindle commands (`M3`) to control the servo. The `S` parameter sets the servo position:

| Command | Description | Notes |
|---------|-------------|-------|
| `M3 S0` | Pen UP | Servo at 0 position |
| `M3 S1000` | Pen DOWN | Servo at max position |
| `M5` | Spindle off | May also lift pen |

**Important:** In GRBL's laser mode, you must include `S` value with each `G1` move to keep the servo engaged:

```gcode
M3 S1000          ; Pen down
G1 X10 Y10 S1000  ; Move WITH S value to keep pen down
G1 X20 Y20 S1000  ; Continue drawing
M3 S0             ; Pen up
```

#### Feed Rate

| Parameter | Description |
|-----------|-------------|
| `F` | Speed in mm/min (e.g., `F1000` = 1000 mm/min) |

### Timing Considerations

Servos need time to physically move. Always add delays after pen commands:

- **Pen up/down:** Wait ~1 second after `M3 S0` or `M3 S1000`
- **Movement:** Small delay (0.1s) between moves is usually sufficient

### Common Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| `error:22` | Invalid G-code | Use `M3 S1000` instead of bare `M3` |
| Pen doesn't stay down | GRBL laser mode | Add `S1000` to each `G1` command |
| Pen moves during travel | Missing pen up | Send `M3 S0` before travel moves |
| Scratchy lines | Pen moves before servo settles | Add 1s delay after pen commands |

### Serial Port Detection

| OS | Common Ports |
|----|--------------|
| macOS | `/dev/cu.usbserial-*`, `/dev/tty.usbmodem*` |
| Linux | `/dev/ttyUSB0`, `/dev/ttyACM0` |
| Windows | `COM3`, `COM4`, etc. |

### Example: Drawing a Square

```gcode
G28                      ; Home
M3 S0                    ; Pen up
G1 X0 Y0 S0 F1000        ; Move to origin
M3 S1000                 ; Pen down (wait 1s)
G1 X30 Y0 S1000 F1000    ; Draw bottom
G1 X30 Y30 S1000 F1000   ; Draw right
G1 X0 Y30 S1000 F1000    ; Draw top
G1 X0 Y0 S1000 F1000     ; Draw left
M3 S0                    ; Pen up
```

---

## Interactive Visualization Features

The enhanced `demo_llm_to_plotter.py` now includes comprehensive visualization capabilities:

### Real-Time Interactive Visualization
- **Live drawing preview** - Watch your plotter draw in real-time
- **Zoom and pan** - Explore the drawing area interactively
- **Pen state indicators** - See when the pen is up/down
- **Progress tracking** - Visual progress bar and statistics

### Progress Monitoring
- **Phase detection** - Homing, moving, drawing, completed
- **Performance metrics** - Speed, distance, efficiency
- **Time tracking** - Total time, drawing time, idle time
- **Command statistics** - Success rate, error tracking

### Comprehensive Reporting
- **Multiple formats** - HTML (interactive), PDF, PNG, JSON
- **Visual summaries** - Before/after comparisons, accuracy analysis
- **Performance insights** - Optimization recommendations
- **Export capabilities** - Save visualizations and data

### Usage Examples

```bash
# Visualization demo (no plotter required)
uv run python examples/demo_llm_to_plotter.py --demo

# Interactive visualization during plotting
uv run python examples/demo_llm_to_plotter.py /dev/cu.usbserial-14220 --interactive --prompt "draw a star"

# Full visualization suite (interactive + progress + reports)
uv run python examples/demo_llm_to_plotter.py /dev/cu.usbserial-14220 --full-viz --prompt "draw a house"

# Progress monitoring only
uv run python examples/demo_llm_to_plotter.py /dev/cu.usbserial-14220 --progress --prompt "draw a circle"

# Generate reports without plotting
uv run python examples/demo_llm_to_plotter.py /dev/cu.usbserial-14220 --dry-run --report --prompt "complex drawing"
```

### Visualization Features
- **Interactive matplotlib window** with zoom, pan, and selection
- **Real-time path visualization** showing planned vs actual drawing
- **Progress metrics dashboard** with live statistics
- **Multi-format report generation** for analysis and sharing
- **Drawing session recording** for playback and analysis

---

## Quick Start

### 1. Basic Demo (No Dependencies)
```bash
uv run python examples/demo_quick_start.py
```

### 2. Test Plotter Connection
```bash
# Simulated plotter (always works)
uv run python examples/demo_plotter_connection.py

# Real plotter on specific port
uv run python examples/demo_plotter_connection.py /dev/ttyUSB0
```

### 3. LLM-Powered Drawing (Generate Only)
```bash
# With OpenAI (generates G-code but doesn't send to plotter)
uv run python examples/demo_llm_generation.py --provider openai

# With Gemini
uv run python examples/demo_llm_generation.py --provider gemini

# Custom prompt
uv run python examples/demo_llm_generation.py --prompt "Draw a star"
```

### 4. LLM to Real Plotter (Generate + Execute)
```bash
# Generate G-code with OpenAI and send to plotter
uv run python examples/demo_llm_to_plotter.py /dev/cu.usbserial-14220 --prompt "draw a square"

# Use Gemini instead
uv run python examples/demo_llm_to_plotter.py /dev/cu.usbserial-14220 --provider gemini --prompt "draw a triangle"

# Dry run (generate but don't send)
uv run python examples/demo_llm_to_plotter.py /dev/cu.usbserial-14220 --prompt "draw a house" --dry-run

# Adjust pen delay (default 1 second)
uv run python examples/demo_llm_to_plotter.py /dev/cu.usbserial-14220 --pen-delay 1.5
```

### 5. Streaming Demo
```bash
uv run python examples/demo_llm_streaming.py --provider openai --interactive
```

### 5. Run Comprehensive Tests
```bash
# All tests
uv run python examples/demo_comprehensive.py

# Specific category
uv run python examples/demo_comprehensive.py --category core
uv run python examples/demo_comprehensive.py --category plotter
uv run python examples/demo_comprehensive.py --category file
uv run python examples/demo_comprehensive.py --category llm
uv run python examples/demo_comprehensive.py --category advanced
```

## Directory Structure

```
examples/
├── demo_quick_start.py          # Basic introduction
├── demo_plotter_connection.py   # Plotter connection testing
├── demo_llm_generation.py       # LLM G-code generation
├── demo_llm_streaming.py        # Real-time streaming
├── demo_llm_to_plotter.py       # LLM + plotter + interactive visualization
├── demo_visualization.py        # Visual reporting
├── demo_cli.py                  # CLI demonstration
├── demo_comprehensive.py        # Complete test suite
├── basic/                       # Basic usage examples
│   ├── simple_drawing.py
│   ├── multiple_shapes.py
│   └── hardware_connection.py
├── file_conversion/             # File conversion examples
│   └── svg_to_gcode.py
├── sample_files/                # Sample files for testing
│   ├── simple_commands.gcode
│   ├── logo.svg
│   └── development.yaml
└── tutorials/                   # Step-by-step tutorials
```

## Test Categories (demo_comprehensive.py)

| Category | What It Tests |
|----------|---------------|
| `core` | G-code commands, programs, strategy selection, configuration |
| `plotter` | Simulated/serial connections, command execution, status |
| `file` | Format detection, G-code loading, SVG/JSON conversion |
| `llm` | Mock LLM provider, command generation, streaming workflows |
| `advanced` | Ink changes, multi-color drawing, pause/resume, visualization |

## Sample Files

The `sample_files/` directory contains:
- `simple_commands.gcode` - Basic G-code for testing
- `logo.svg` - SVG file for conversion testing
- `development.yaml` - Configuration example

## Requirements

Most demos work without external dependencies. For full functionality:

```bash
# Core dependencies
uv pip install -e .

# For LLM features (install the provider you want to use)
uv pip install llama-index-llms-openai      # For OpenAI
uv pip install llama-index-llms-gemini      # For Gemini
uv pip install llama-index-llms-azure-openai # For Azure OpenAI
uv pip install llama-index-llms-ollama      # For Ollama (local)
```

---

## LLM Provider Setup

### Supported Providers

| Provider | Model Examples | Environment Variable |
|----------|---------------|---------------------|
| OpenAI | `gpt-4o-mini`, `gpt-4o`, `gpt-4` | `OPENAI_API_KEY` |
| Gemini | `models/gemini-1.5-flash`, `models/gemini-1.5-pro` | `GOOGLE_API_KEY` |
| Azure OpenAI | `gpt-4o` | `GPT4_API_KEY`, `GPT4_ENDPOINT`, `GPT4_API_VERSION` |
| Ollama | `llama3.2:3b`, `mistral`, `codellama` | None (local) |

### Quick Setup

#### OpenAI (Recommended)
```bash
export OPENAI_API_KEY='sk-your-api-key'
uv run python examples/demo_llm_generation.py --provider openai
```

#### Google Gemini
```bash
export GOOGLE_API_KEY='your-google-api-key'
uv run python examples/demo_llm_generation.py --provider gemini
```

#### Azure OpenAI
```bash
export GPT4_API_KEY='your-azure-api-key'
export GPT4_ENDPOINT='https://your-resource.openai.azure.com/'
export GPT4_API_VERSION='2024-02-15-preview'
uv run python examples/demo_llm_generation.py --provider azure
```

#### Ollama (Local)
```bash
# Install Ollama: https://ollama.ai/
ollama pull llama3.2:3b
uv run python examples/demo_llm_generation.py --provider ollama
```

### Auto-Detection

If you run without `--provider`, the demo will auto-detect available providers in this order:
1. OpenAI (if `OPENAI_API_KEY` is set)
2. Gemini (if `GOOGLE_API_KEY` is set)
3. Azure OpenAI (if Azure credentials are set)
4. Ollama (if running locally)

# For visualization
pip install matplotlib
```
