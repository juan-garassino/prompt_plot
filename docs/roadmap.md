# PromptPlot Roadmap

## Current State (v3.0)

The core pipeline works end-to-end: prompt → LLM → GCode → postprocess → plotter. 11 flat modules, 4 LLM providers with multimodal support, config-aware prompts, bounds validation, style presets, 5-stage post-processing.

### What's solid
- Full pipeline wired and functional
- Clean flat architecture (no nested packages)
- Config-aware prompts use real canvas dimensions, pen values, coordinate ranges
- Bounds validation prevents hardware damage (clamp/reject/warn)
- 4 LLM providers (Ollama, OpenAI, Azure, Gemini) with temperature wiring
- Multimodal vision support with graceful fallback
- Post-processing: bounds → pen safety → stroke optimization → paint dips → dwells
- Serial plotter with backpressure, heartbeat, async streaming
- Rich CLI with generate, plot, preview, interactive modes

### Known issues
- 10 test files from v2 import deleted module paths — can't run
- 239 uncommitted changes from v3 restructuring sitting unstaged
- No tests for pipeline.py, plotter.py, visualizer.py, logger.py
- CLAUDE.md has unfilled placeholder sections
- GCodeVisualizer not exported from __init__.py

---

## Phase 1: Stabilize

**Priority: critical. Do before anything else.**

- [ ] Commit the remaining v3 restructuring (deleted v2 files, new modules)
- [ ] Delete the 10 broken v2 test files (they test code that no longer exists)
- [ ] Add tests for `pipeline.py` (file loading, postprocess integration)
- [ ] Add tests for `plotter.py` (SimulatedPlotter at minimum)
- [ ] Fill in CLAUDE.md placeholders (current status, file structure, serial port)
- [ ] Export `GCodeVisualizer` from `__init__.py`
- [ ] Get `pytest` to run clean: 0 errors, all tests pass

---

## Phase 2: Drawing Quality

**Priority: high. Biggest impact on actual output quality.**

- [ ] **Curve approximation** — the LLM struggles with circles/arcs because it only has G1 (straight lines). Either add a postprocess step that converts G2/G3 arcs into short G1 segments, or improve the prompt to explicitly request many small segments for curves (8-12+ points per curve).
- [ ] **Better few-shot examples** — the current two (geometric/organic) are minimal. Curate 4-5 real plotter-tested examples with known-good output. Store as JSON fixtures alongside the code.
- [ ] **GCode quality scorer** — a function that traces a program and reports: canvas utilization %, stroke count, draw/travel ratio, longest travel move, estimated draw time. Use for automated quality evaluation.
- [ ] **Adaptive detail prompting** — detect when a prompt is complex ("draw a detailed cityscape") and adjust the prompt to request more commands, more detail, wider canvas usage.

---

## Phase 3: Generation Intelligence

**Priority: medium. Makes the system smarter over time.**

- [ ] **Multi-pass generation** — for complex drawings: generate outline first, then fill/detail/texture in a second LLM call. Merge the two programs. Outline pass uses `style=precise`, detail pass uses `style=artistic`.
- [ ] **Drawing memory** — save successful prompt→GCode pairs. When a new prompt is similar to a past success, include the past GCode as a few-shot example. The system gets better with use.
- [ ] **Style transfer from examples** — given a reference GCode file (not image), extract its characteristics (stroke density, canvas usage, line length distribution) and inject those as constraints into the prompt.
- [ ] **Automatic retry with diagnosis** — when validation fails, instead of just retrying, analyze *why* (too few commands? out of bounds? missing pen lifts?) and add targeted instructions to the reflection prompt.

---

## Phase 4: File Format Support

**Priority: medium. Bypasses LLM for known shapes.**

- [ ] **SVG-to-GCode converter** — load SVG, extract paths, convert to optimized GCode. No LLM needed. Was in v2 but removed in the restructure.
- [ ] **DXF import** — common format from CAD software. Parse polylines and arcs, convert to GCode.
- [ ] **Image tracing** — bitmap image → edge detection → vectorize → GCode. Useful for photos and raster art.
- [ ] **GCode import/export** — load existing .gcode files from other tools, run through the postprocess pipeline, re-export.

---

## Phase 5: Hardware & UX

**Priority: lower. Polish and accessibility.**

- [ ] **Live preview during streaming** — update the matplotlib preview as commands stream to the plotter. See the drawing progress in real time.
- [ ] **Pause/resume/cancel** — plotter streaming with ability to stop mid-drawing and resume from where it left off.
- [ ] **Web UI** — simple Flask/FastAPI frontend: type prompt, see preview, click "plot". More accessible than CLI for demos and workshops.
- [ ] **Job queue** — queue multiple prompts, generate and plot them sequentially. Useful for batch production.
- [ ] **Progress estimation** — estimate remaining time based on GCode length and feed rate. Show in CLI and web UI.

---

## Phase 6: Close the Physical Loop

**Priority: future. The most ambitious feature.**

- [ ] **Photo feedback** — after plotting, take a photo of the physical drawing (webcam or phone), feed it back to the LLM with the original prompt, ask "what needs to change?", generate corrections. True closed-loop physical drawing.
- [ ] **Calibration** — generate a test pattern, photograph it, detect distortion/offset, apply corrections to future GCode. Auto-calibrate pen position and paper alignment.
- [ ] **Multi-pen support** — switch between pens (colors, widths) mid-drawing. Requires tool change GCode sequences and color-aware prompt generation.

---

## Implementation Order

```
Phase 1 (stabilize)          ← DO NOW, prerequisite for everything
  │
  ├── Phase 2 (quality)      ← highest ROI, do next
  │     │
  │     └── Phase 3 (intelligence)  ← builds on quality scoring
  │
  ├── Phase 4 (file formats) ← independent, do when needed
  │
  └── Phase 5 (hardware/UX)  ← polish
        │
        └── Phase 6 (physical loop) ← long-term vision
```
