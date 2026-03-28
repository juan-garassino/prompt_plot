# Architecture

PromptPlot v3.0 uses a flat module structure — 11 Python files, no nested packages.

## Modules

| Module | Purpose |
|--------|---------|
| `models.py` | Data classes: `GCodeCommand`, `GCodeProgram`, `WorkflowResult` |
| `config.py` | Dataclass-based config: LLM, paper, pen, brush, bounds, vision, serial, visualization |
| `llm.py` | LLM provider abstraction (Ollama, OpenAI, Azure, Gemini) + config-aware prompt builders + multimodal |
| `workflow.py` | `BatchGCodeWorkflow` and `StreamingGCodeWorkflow` with vision refinement |
| `postprocess.py` | Five-stage pipeline: bounds → pen safety → optimization → paint dips → dwells |
| `pipeline.py` | File-based pipeline: load .gcode → postprocess → preview → stream |
| `plotter.py` | `SerialPlotter` (pyserial) and `SimulatedPlotter` |
| `visualizer.py` | Matplotlib preview with drawable area overlay, out-of-bounds highlighting, statistics |
| `logger.py` | Rich-based workflow logger |
| `cli.py` | Click CLI: generate, plot, preview, config, plotter, interactive |
| `__init__.py` | Public API re-exports |

## Data flow

### Prompt-based generation

```
User prompt (+ optional reference image)
  → llm.py (build config-aware prompt, call LLM, optionally multimodal)
  → workflow.py (orchestrates generation + validation + retries + vision refinement)
  → postprocess.py (bounds → pen safety → optimize → dwells)
  → plotter.py (stream to hardware)
  → visualizer.py (optional preview with bounds overlay)
```

### File-based plotting

```
file.gcode
  → pipeline.py (load + parse)
  → postprocess.py (bounds → pen safety → optimize → dwells)
  → plotter.py (stream to hardware)
  → visualizer.py (optional preview)
```

## Post-processing pipeline order

The five stages must run in this order:

0. **Bounds validation** — clamp/reject/warn out-of-bounds coordinates (safety)
1. **Pen safety** — enforce M5 before G0, M3 before G1, return home
2. **Stroke optimization** — nearest-neighbor reorder to minimize pen lifts
3. **Paint dips** — ink reload sequences (brush mode only)
4. **Pen dwells** — G4 delays after M3/M5 (must be last)

## Prompt system

The LLM prompt is built dynamically from config values, not hardcoded:

- Canvas dimensions come from `PaperConfig.get_drawable_area()`
- Pen S-value from `PenConfig.pen_down_s_value`
- Feed rate from `PenConfig.feed_rate`
- Style guidelines from the selected preset (artistic, precise, sketch, minimal)
- Few-shot examples selected by keyword matching against the user prompt
- Reflection prompts include valid coordinate ranges

## Multimodal vision

When vision is enabled, the workflow supports:

1. **Reference images** — user provides an image, LLM sees it alongside the prompt
2. **Preview feedback** — workflow renders the GCode to a PNG, feeds it back to the LLM for refinement

Each provider implements `acomplete_multimodal()` with graceful fallback to text-only if multimodal packages aren't installed.

## Key design decisions

- **Flat modules** — no nested packages, every import is `from promptplot.X import Y`
- **Dataclass config** — no YAML/JSON schema files, config is Python dataclasses
- **Config-aware prompts** — LLM sees the real canvas, pen values, and coordinate ranges
- **Bounds before hardware** — out-of-bounds coordinates never reach the plotter
- **Async plotter** — serial communication is async for non-blocking streaming
- **Post-processing is separate** — LLM output is never sent raw to hardware
- **Graceful degradation** — multimodal falls back to text, optional deps are try/except'd
