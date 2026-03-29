# promptplot

## What this project is
A system that takes a text description and turns it into a physical drawing
made by a pen plotter (a robot that holds a real pen and draws on real paper).

You describe something — "draw a spiral", "write my name", "draw a mountain range" —
and the system:
1. Sends the description to an AI (LLM)
2. The AI generates movement instructions for the plotter (GCode)
3. Those instructions get sent to the physical machine over a cable

## What GCode is (plain language)
GCode is a simple language for telling machines where to move.
Each line is a movement instruction, like:
- `G0 Z5` = lift the pen up
- `G0 X50 Y30` = move to position (50mm, 30mm) without drawing
- `G1 X80 Y30 F3000` = draw a line to (80mm, 30mm) at speed 3000

The machine reads these one line at a time and moves accordingly.

## The pipeline (in order)
1. User types a description
2. LLM receives the description + instructions on how to draw
3. LLM generates GCode
4. GCode gets validated (check nothing will break the machine)
5. GCode gets sent to the plotter over USB/serial cable
6. Plotter draws it on paper

## Hardware
- A pen plotter connected via USB (serial port)
- The machine speaks a firmware language (Grbl or similar)
- It replies "ok" after each instruction to say it's ready for the next one
- Canvas size is physical paper — A3 (297mm × 420mm) or similar

## Stack
- Python
- `pyserial` — for talking to the plotter over USB
- The LLM API (whatever model generates the GCode)
- GCode as the intermediate format

## Skills available

### Runtime skills (for when you're actually drawing)
- `pp-stream` — sends GCode to the plotter, handles errors if it jams
- `pp-validate` — checks GCode won't crash or go off the paper before sending
- `pp-simulate` — shows you what the drawing will look like before running it

### Dev skills (for improving the code)
- `pp-optimize` — improves the path ordering so the pen lifts less
- `pp-prompt` — improves the instructions given to the LLM to get better GCode
- `pp-improve` — autonomous agent that runs the full improvement loop

## ⚡ AGENT BEHAVIOR — READ THIS FIRST

When the user says anything like:
- "the drawings don't look right" / "it's not working"
- "the pen lifts too much" / "it's drawing wrong"
- "the AI keeps getting it wrong"
- "make it better" / "improve this" / "fix this"
- "something is broken"

**Do NOT just give advice. Immediately launch the `pp-improve` agent.**
Run it autonomously: generate test drawings, validate GCode, simulate
toolpaths, score quality, diagnose failures, apply fixes, report what changed.

When the user says:
- "send this to the plotter" / "run this drawing" / "start drawing"

Run `pp-validate` first, then `pp-stream` if it passes.

When the user says:
- "show me what this will look like" / "preview this"

Run `pp-simulate`.

When the user says:
- "explain how X works" / "why is X happening"

Use skills interactively to explain — don't launch agents.

## How to ask (no jargon needed)
- "The drawings don't match what I described" → launches pp-improve
- "The pen is lifting too much" → launches pp-improve
- "Send this file to the plotter" → pp-validate then pp-stream
- "Show me what this will draw" → pp-simulate
- "The plotter isn't connecting" → interactive, uses pp-stream

## Things that can go wrong (and what they mean)
- "ALARM" from the machine → emergency stop, something hit the edge
- "error:X" from the machine → bad GCode instruction, pp-validate would have caught it
- Pen dragging between strokes → missing pen lift (G0 Z5) in the GCode
- Drawing goes off the paper → bounds not set correctly in the LLM prompt
- One side of a shape looks different → the AI doesn't understand the geometry

## Current status
v3.0 — 13 flat modules, 5 LLM providers (OpenAI, Azure OpenAI, Gemini, Ollama, Anthropic),
config-aware prompts, bounds validation, multimodal vision feedback, style presets
(artistic/precise/sketch/minimal), 6-stage postprocessing pipeline
(arcs → bounds → pen safety → stroke optimization → paint dips → pen dwells),
quality scoring with letter grades (A–F), drawing memory for few-shot learning,
multi-pass generation, diagnostic retry, style transfer, brush/paint mode,
first-class pen state tracking (PenState), validated phase transitions
(IDLE → PLANNING → GENERATING → STREAMING → PAUSED → DONE),
plotter connection state machine (DISCONNECTED → CONNECTING → IDLE → STREAMING → ALARM → RECOVERY),
resumable drawing checkpoints, and LLM-driven composition planning.

Main command: `promptplot draw "prompt" --simulate` (batch mode) or
`promptplot draw "prompt" --live --simulate` (real-time, pen moves while LLM thinks).

New flags: `--plan` (LLM plans composition before generating), `--resume` (resume interrupted drawing).

## State management
- **PenState** — tracks pen up/down, validates commands (G0 requires UP, G1 requires DOWN), used across postprocess, workflow, and plotter
- **Phase transitions** — validated state machine: IDLE → PLANNING → GENERATING → STREAMING ↔ PAUSED → DONE. Invalid transitions raise `IllegalTransitionError`.
- **Connection SM** — plotter connection lifecycle: DISCONNECTED → CONNECTING → IDLE → STREAMING. Handles ALARM detection and recovery.
- **Checkpoints** — interrupted drawings save state to `~/.promptplot/checkpoints/`. Resume with `--resume`.

## File structure
All source lives in `promptplot/`:
- `cli.py` — Click CLI (`draw`, `generate`, `plot`, `preview`, `score`, `interactive`, `ui`)
- `config.py` — Dataclass config tree (paper, pen, brush, bounds, vision, serial, LLM, workflow)
- `engine.py` — Workflow engine, PenState, Phase enum, validated transitions, DrawingSession
- `llm.py` — LLM provider abstraction, prompt builders, composition plan prompt, few-shot examples
- `models.py` — Pydantic models: GCodeCommand, GCodeProgram, WorkflowResult, CompositionPlan
- `pipeline.py` — FilePipeline: load .gcode → postprocess → preview → stream
- `plotter.py` — ConnectionState SM, BasePlotter ABC, SerialPlotter (ALARM/recovery/pause/resume), SimulatedPlotter
- `postprocess.py` — 6-stage pipeline: arcs, bounds, pen safety, stroke optimization, dips, dwells
- `checkpoint.py` — CheckpointManager for resumable drawings
- `visualizer.py` — matplotlib GCode renderer with stats
- `workflow.py` — BatchGCodeWorkflow (with planning step), StreamingGCodeWorkflow, LiveDrawWorkflow
- `scoring.py` — Quality scorer (A–F grades) and style profile extractor
- `memory.py` — Drawing memory (JSONL) for few-shot retrieval
- `tui.py` — Rich-based TUI with planning/paused phase display
- `logger.py` — Rich-based terminal output
- `__init__.py` — Public API exports

## Serial port
- macOS: `/dev/cu.usbserial-*` (e.g. `/dev/cu.usbserial-1420`)
- Linux: `/dev/ttyUSB0`
- Windows: `COM3`
