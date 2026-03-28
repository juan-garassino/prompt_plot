# Configuration

All configuration lives in `promptplot/config.py` as nested dataclasses.

## Loading config

```python
from promptplot import load_config, get_config

# Load defaults
config = get_config()

# Load from YAML or JSON file
config = load_config("my_config.yaml")
```

From the CLI:

```bash
promptplot --config my_config.yaml generate "draw a cat"
```

## Top-level: `PromptPlotConfig`

| Field | Type | Default |
|-------|------|---------|
| `mode` | `PlotterMode` | `normal` |
| `llm` | `LLMConfig` | see below |
| `paper` | `PaperConfig` | see below |
| `pen` | `PenConfig` | see below |
| `brush` | `BrushConfig` | see below |
| `bounds` | `BoundsConfig` | see below |
| `vision` | `VisionConfig` | see below |
| `serial` | `SerialConfig` | see below |
| `visualization` | `VisualizationConfig` | see below |
| `workflow` | `WorkflowConfig` | see below |
| `debug` | `bool` | `False` |
| `log_level` | `str` | `INFO` |

## LLMConfig

| Field | Default | Notes |
|-------|---------|-------|
| `default_provider` | `ollama` | `ollama`, `openai`, `azure_openai`, `gemini` |
| `ollama_model` | `llama3.2:3b` | |
| `ollama_vision_model` | `llama3.2-vision:11b` | Used for multimodal with Ollama |
| `openai_model` | `gpt-4o-mini` | Needs `OPENAI_API_KEY` |
| `azure_model` | `gpt-4o` | Needs `GPT4_API_KEY`, `GPT4_ENDPOINT`, `GPT4_API_VERSION` |
| `gemini_model` | `models/gemini-1.5-flash` | Needs `GOOGLE_API_KEY` |
| `temperature` | `0.1` | Passed to all LLM provider constructors |
| `max_retries` | `3` | |

## PaperConfig

| Field | Default | Notes |
|-------|---------|-------|
| `width` | `210.0` | mm (A4 width) |
| `height` | `297.0` | mm (A4 height) |
| `margin_x` | `10.0` | mm |
| `margin_y` | `10.0` | mm |

Methods:
- `get_drawable_area()` → `(margin_x, margin_y, width - margin_x, height - margin_y)`
- `get_drawable_dimensions()` → `(width - 2*margin_x, height - 2*margin_y)`

## PenConfig

| Field | Default | Notes |
|-------|---------|-------|
| `up_position` | `5.0` | Z height when pen is up |
| `down_position` | `0.0` | Z height when pen is down |
| `up_speed` | `500.0` | |
| `down_speed` | `200.0` | |
| `pen_up_delay` | `0.2` | Seconds — injected as G4 dwell |
| `pen_down_delay` | `0.2` | Seconds — injected as G4 dwell |
| `pen_down_s_value` | `1000` | S parameter for M3 command |
| `feed_rate` | `2000` | F parameter for G1 draw commands |

## BrushConfig

| Field | Default | Notes |
|-------|---------|-------|
| `enabled` | `false` | Enable brush/ink mode |
| `charge_position` | `(10.0, 10.0)` | Ink station coordinates |
| `dip_height` | `0.0` | Z for dipping |
| `dip_duration` | `0.5` | Seconds in ink |
| `drip_duration` | `1.0` | Seconds dripping |
| `strokes_before_reload` | `10` | Strokes between reloads |

## BoundsConfig

| Field | Default | Notes |
|-------|---------|-------|
| `enforce` | `true` | Enable bounds validation in post-processing |
| `mode` | `clamp` | `clamp` (fix coords), `reject` (remove commands), `warn` (log only) |

Bounds validation runs as Stage 0 in the post-processing pipeline, before pen safety. It checks all X/Y coordinates against the paper dimensions:
- **clamp**: Coordinates outside `[0, paper.width]` / `[0, paper.height]` are clamped to the nearest valid value
- **reject**: Out-of-bounds commands are removed entirely
- **warn**: Commands are kept but violations are logged

## VisionConfig

| Field | Default | Notes |
|-------|---------|-------|
| `enabled` | `false` | Enable multimodal vision features |
| `reference_image` | `null` | Path to a reference image for guided generation |
| `preview_feedback` | `false` | Render preview and feed back to LLM for refinement |
| `max_feedback_iterations` | `1` | Number of vision refinement passes |

Requires optional vision packages: `uv pip install -e ".[vision]"`

When `reference_image` is set and `enabled` is true, the LLM receives the image alongside the prompt for visually-guided GCode generation. When `preview_feedback` is also enabled, the workflow renders the generated drawing and asks the LLM to improve it.

## SerialConfig

| Field | Default |
|-------|---------|
| `port` | `/dev/ttyUSB0` |
| `baud_rate` | `115200` |
| `timeout` | `5.0` |

## VisualizationConfig

| Field | Default |
|-------|---------|
| `figure_width` | `10.0` |
| `figure_height` | `10.0` |
| `figure_dpi` | `100` |
| `drawing_color` | `blue` |
| `travel_color` | `lightgray` |
| `line_width` | `1.0` |

## WorkflowConfig

| Field | Default |
|-------|---------|
| `max_retries` | `3` |
| `max_steps` | `50` |
| `step_timeout` | `30.0` |
| `output_directory` | `output` |

## Example YAML

```yaml
mode: normal
llm:
  default_provider: openai
  openai_model: gpt-4o-mini
  temperature: 0.1
paper:
  width: 297.0
  height: 420.0
pen:
  pen_up_delay: 0.3
  pen_down_delay: 0.3
  pen_down_s_value: 1000
  feed_rate: 2000
bounds:
  enforce: true
  mode: clamp
vision:
  enabled: false
  preview_feedback: false
serial:
  port: /dev/cu.usbserial-10
  baud_rate: 115200
workflow:
  output_directory: output
```
