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
- Python (>=3.9), `uv`-managed. `click` CLI, `rich` output, `pydantic` v2 models.
- `pyserial` / `pyserial-asyncio` — for talking to the plotter over USB
- LLM SDKs are optional extras (`openai`, `anthropic`, `google-generativeai`); `matplotlib`+`numpy` are the `viz` extra; `svgpathtools`+`ezdxf` are the `io` extra (SVG/DXF import — stdlib fallback parsers ship built-in)
- GCode as the intermediate format

## Commands
- `make dev` — install editable with dev+viz extras (`uv pip install -e ".[dev,viz]"`). Optional extras: `uv pip install -e ".[openai,anthropic,gemini,vision,io]"` (`io` = svgpathtools+ezdxf for full-fidelity SVG/DXF import).
- `make test` — runs the full suite (~385 tests). Note: pytest `addopts` **always** runs coverage (`--cov`, html+xml reports) and treats warnings as errors (`filterwarnings = ["error", ...]`) — a new `DeprecationWarning` will fail CI unless whitelisted. One pre-existing failure (`test_refinement.py::test_batch_refinement_prefers_improved_result`, a stub-queue exhaustion) predates the v3.1 work; `make test-ci` deselects it.
- Single test: `python3 -m pytest tests/test_primitives.py::test_name -v`. By marker: `-m "not requires_hardware and not requires_llm"` to skip hardware/LLM-gated tests.
- `make lint` (ruff) / `make format` (black + isort). Line length 100.
- Run the tool: `python3 -m promptplot ...` or the `promptplot` entry point (`cli:main`).

## Skills available

### Runtime skills (for when you're actually drawing)
- `pp-stream` — sends GCode to the plotter, handles errors if it jams
- `pp-validate` — checks GCode won't crash or go off the paper before sending
- `pp-simulate` — shows you what the drawing will look like before running it

### Dev skills (for improving the code)
- `pp-optimize` — improves the path ordering so the pen lifts less
- `pp-prompt` — improves the instructions given to the LLM to get better GCode
- `pp-improve` — autonomous agent that runs the full improvement loop

### Controller skills (drive PromptPlot from Claude Code)
- `pp-orchestrate` — supervisor-worker loop for dense (10k+) drawings: plan
  regions → generate per region → validate → score → retry weak → stream →
  checkpoint. Uses the public `promptplot.orchestrate` API.

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
v3.1 — organized into subpackages (`llm/`, `workflow/`, `cli/`, `generative/`, `importers/`) plus
core flat modules, 7 LLM providers (OpenAI, Azure OpenAI, Gemini, Ollama, Anthropic, OpenRouter, NVIDIA NIM),
a PRIMITIVE/FREEFORM drawing DSL with self-describing prompt schemas (see "Drawing DSL"),
figurative/abstract/hybrid creative-mode routing,
config-aware prompts, bounds validation, multimodal vision feedback, style presets
(artistic/precise/sketch/minimal), 6-stage postprocessing pipeline
(arcs → bounds → pen safety → stroke optimization → paint dips → pen dwells),
**multi-color pen layers** (group by color → park + keypress swap → next color, with color-coded preview),
**seeded generative art** (deterministic-from-seed `art` command: tiled_field, ripple_field, flow_field,
maze, truchet, wave_bands, stipple, waves_with_circles, crosshatch_weave, turning_weave, wave_gradient,
interference_field, frequency_lens, hitomezashi, harmonograph, vortex_field, moire_layers,
strange_attractor (11 systems), domain_warp, contour_field, superformula_bloom, lissajous_carpet,
scribble_halftone (shape-aware), comic_panels, line_halftone, scribble_portrait, sparkle_grid,
iso_city, rounded_circuits, lissajous_swarm, black_hole,
pe_carpet, attention_arcs, residual_river — 37 total;
plus effects applicable to any generator: `--anaglyph`/`--glitch` red-cyan offset, and `--max-ink N` ink-density cap — no spot gets more than N pen passes),
**SVG + DXF import** (split by stroke color / DXF layer → color layers),
selectable paper size (A3/A4/A5/A6 via `--paper`),
quality scoring with letter grades (A–F), drawing memory for few-shot learning,
multi-pass generation, diagnostic retry, style transfer, brush/paint mode,
first-class pen state tracking (PenState), validated phase transitions
(IDLE → PLANNING → GENERATING → STREAMING → PAUSED → DONE),
plotter connection state machine (DISCONNECTED → CONNECTING → IDLE → STREAMING → ALARM → RECOVERY),
resumable drawing checkpoints, and LLM-driven composition planning.

Main commands:
- `promptplot draw "prompt" --simulate` (batch) / `--live` (real-time) / `--colors N` (multi-color) / `--paper a4`.
- `promptplot art <generator> --seed N --colors K --simulate --preview` (seeded generative, no LLM).
- `promptplot import file.svg|file.dxf --simulate --preview` (vector file → color layers).

New flags on `draw`: `--plan` (LLM plans composition first), `--resume` (resume interrupted drawing),
`--orchestrate --regions N` (supervisor-worker fan-out), `--colors N` (LLM assigns colors, plotter pauses
for swaps), `--paper a3|a4|a5|a6 --orientation portrait|landscape`.

### Four controllers
PromptPlot can be driven three ways, sharing the same postprocess/scoring/plotter primitives:
- **File** — replay curated .gcode from `~/.promptplot/library/` (`promptplot library list|play <name>`).
- **LLM** — `SupervisorWorkerWorkflow` runs the plan→workers→merge→critique→retry loop in one
  Python process. Drive via `promptplot draw "..." --orchestrate --regions N`.
- **PromptPlot Agent** — the built-in agentic controller (`promptplot agent`, package
  `promptplot/agent/`): an LLM-agnostic chat loop (any of the 7 providers via a strict JSON
  tool-call envelope in `agent/protocol.py`) over a typed toolbox (`agent/tools.py`:
  list/render generators, render DSL blocks, score, validate, import, memory search).
  Sessions persist to `~/.promptplot/agent_sessions/<id>/` (transcript.json + trace.jsonl +
  renders/ + report.md); resume with `--session <id>`. Headless: `promptplot agent -p "..."`.
  Tools are tiered safe/confirm: `critique_render` sends a png to the provider's vision model
  (`acomplete_multimodal`; NVIDIA default vision model llama-3.2-11b-vision), and the confirm
  tier (`stream_to_plotter`, `save_to_library`) always traces the pen-up frame first and needs
  an interactive y/N or `--yes-plot`. OpenAI/NVIDIA use native function calling
  (`acomplete_tools` on the provider base, `_openai_native_tools` helper); every other provider
  falls back to the JSON envelope automatically. Tests: `tests/test_agent.py` (stub providers,
  no keys/hardware). Proven live: the agent on NVIDIA rendered, vision-critiqued its own png,
  adjusted a param and re-rendered autonomously.
  MCP surface: `promptplot mcp` serves the same toolbox over stdio (`agent/mcp_server.py`,
  FastMCP; optional extra `pip install -e ".[agent]"`): 12 tools with ToolAnnotations
  (readOnlyHint / destructiveHint), error envelope with `remediation`, inline `Image`
  previews via `preview_image`, `plot://renders` + `plot://render/{file}` resources, and
  hardware gated behind an explicit `confirm=true` argument — any MCP client can drive
  the plotter.
- **Claude Code** — external orchestrator using the public `promptplot.orchestrate` API
  (`plan_regions`, `generate_region`, `validate_chunk`, `score_chunk`, `merge_chunks`,
  `stream_chunk`, `load_and_continue`). The `pp-orchestrate` skill teaches the loop.

## Drawing DSL: how LLM output becomes GCode
The LLM does **not** emit raw GCode for shapes. It emits a `DrawProgram` (`models.py`) whose
commands are one of three kinds, expanded deterministically by `primitives.py`:
- **PRIMITIVE** — parametric shapes expanded to exact `G1` segments. Registry: `circle`,
  `ellipse`, `polygon`, `hatch`, `crosshatch`, `filled_polygon`, `stipple`, `spiral`, `flow_field`.
- **FREEFORM** — organic/expressive marks: `contour_path`/`silhouette_outline`, `texture_strokes`,
  `accent_marks`, `hatch_region`, `negative_space_region`, and abstract fields (`field_stack`,
  `moire_grid`, `radial_field`, etc.).
- Raw `G0`/`G1` GCode dicts for anything the DSL doesn't cover.

`expand_primitives(draw_program, pen_config)` turns a DrawProgram into a `GCodeProgram`.
Primitive/freeform **schemas are introspected from function signatures** and injected into the
prompt (`get_all_primitive_schemas`, `format_schemas_for_prompt` in `primitives.py`) — adding a
new primitive means writing an `expand_*` function and registering it; the prompt updates itself.
`llm.classify_creative_mode(prompt)` routes to **figurative / abstract / hybrid** prompt variants.

**Claude-Code-as-LLM path**: hand-build `blocks` of PRIMITIVE/FREEFORM dicts and call
`orchestrate.compose_and_stream(blocks, plotter, config)` — expand → merge → postprocess → stream,
with no intermediate `.gcode` file. See `scripts/cc_draw_*.py` for working examples.

## BAUHAUS UNIVERSUM (collection)
`generative/bauhaus.py` — a design-language kit (serpentine/spiral/quarter fills, dotted
orbits, plus marks, swatch bars, crosshair rules, spaced-caps `type_block`/`scale_footer`,
`BAUHAUS_PALETTE` blue|pink|black) plus poster pieces built on it: `bauhaus_attractor`
(SENSITIVE DEPENDENCE — one Lorenz line, solid discs in the lobe eyes), `bauhaus_attention`
(GPT-2 sink chords in bold pink), `bauhaus_weights` (PARAMETER FIELD — Q|K|V Hinton discs
from the trained checkpoint), `bauhaus_gradient`
(GRADIENT DESCENT — contour bowls + descent path), `bauhaus_resonance` (harmonograph),
`bauhaus_loom` (FORWARD PASS — the perceptron rethought as an Anni-Albers weaving: a real
weight matrix woven warp/weft, over/under by sign, float by magnitude; APPROVED),
`bauhaus_decision` (DECISION SURFACE — the network drawn as its FUNCTION not its wiring: the
exact iso-0 marching-squares knife through input space, ±margin shoulders opening a corridor,
support-vector discs on the shoulders, point clouds coloured by the true sign of f; trained
query directions from the checkpoint drive the readout when `weights=` is given; APPROVED).
Retired: `bauhaus_perceptron` (kept in-file for version history, deregistered — superseded by
the loom + decision pieces).
Related one-off: `black_hole_bauhaus`. Renders go to ~/Downloads for voting; winners move
to `leo/bauhaus/`.

## Multi-color pen layers
Every drawing source (LLM, manual scripts, generative, imported files) can tag commands with a
`color` index. When `config.color.enabled`, `postprocess.reorder_by_color` groups strokes by pen and
optimizes **within** each color (never reordering across a color). `orchestrate.stream_pen_layers`
then streams color-by-color: after each layer it lifts, parks at `config.color.park_position`, and
(if `pause_for_swap`) blocks for a keypress before the next pen. `visualizer` renders each pen in its
palette color with a legend. Color sources: `draw --colors N` (LLM assigns), `art --colors K`,
`import` (SVG stroke / DXF layer), or hand-tagged `GCodeCommand(color=…)` in a script (see
`scripts/cc_colors_test.py`). Color survives a save→reload round-trip as a `; color=N` comment.

## Generative art (seeded)
`promptplot art <generator> --seed N|now --colors K --paper a4 --simulate --preview`. Fully
**deterministic**: same seed + params + version → identical GCode (all randomness flows through one
`SeededRNG`; no global random). `--seed now` uses a timestamp seed that is printed and embedded in the
output filename for later reproduction. Generators live in `generative/generators.py` and are registered
in `generative/registry.py` (`GENERATOR_REGISTRY`); param schemas are introspected from signatures, so
adding a generator + registering it updates `art --list` automatically — mirrors the primitives pattern.
Generators: `tiled_field` (dense directional-tile grid), `ripple_field` (concentric ripples → noise
peaks), `flow_field` (evenly-spaced non-overlapping streamlines, Jobard–Lefebvre), `maze`, `truchet`,
`wave_bands`, `stipple`, `waves_with_circles`, `crosshatch_weave` (±45° woven plaid, black-dominant),
`turning_weave` (grid-aligned diagonal L-paths that enter an edge, turn at lattice nodes, exit another edge),
`wave_gradient` (rows of waves, calm at top → tall spiky peaks at bottom),
`interference_field` (scanlines displaced by interfering circular ripples from N seeded 'drops' — ripple-tank/moiré; frequency varies within each wave),
`frequency_lens` (rows of sine with circular 'lenses' where the local frequency drops — phase-integrated so waves stay continuous across the edge),
`hitomezashi` (Japanese stitch grid — emergent staircase mazes from seeded binary offsets),
`harmonograph` (one continuous damped double-pendulum curve),
`vortex_field` (scanlines swirled around seeded whirlpool centers),
`moire_layers` (same line grid per pen at tiny rotations — physical moiré on paper),
`strange_attractor` (lorenz/rossler/halvorsen/aizawa, RK4, ported from `008-formCollapse` — 'controlled chaos'),
`domain_warp` (scanlines through warped fbm — liquid marble),
`contour_field` (marching-squares topographic isolines of noise/blobs/ridge fields),
`superformula_bloom` (nested rotating superformula shells — botanical mandala),
`lissajous_carpet` (the classic Lissajous frequency table as a grid of curve cells),
`scribble_halftone` / `line_halftone` / `scribble_portrait` (image-driven: photo tones → dashes / line-screen / continuous scribble; `--param image=path`, Pillow via the `vision` extra; procedural fbm fallback without an image).
Image fit rule: pictures **cover-fit** the drawable area — auto-rotated 90° to match the paper's orientation, filling everything inside the margins, center-cropping overflow (`_image_tone_grid`).
`scribble_halftone` is **shape-aware** by default: dash direction follows the image's contour tangents (Sobel + structure tensor), blends into a noise field in flat tone, cross-hatches darks. `line_halftone` plays with effective pen width (dark runs drawn as doubled/tripled parallel passes). `scribble_portrait` leaves highlights as blank paper (steep capacity curve).
`comic_panels` (seeded comic-page layout, max 3 panels, default pool vortex+contours; `subs` overrides),
`sparkle_grid` (mid-century atomic stars on a STRICT grid; tight shells (`shell_gap`), slim arms (`slim` exponent), per-gridline interval registry keeps spur arms from overlapping ink; tip relief avoids pooling),
`iso_city` (voxel city, unit-gridded faces, hidden lines removed via front-to-back occupancy-mask claiming; `projection=2pt|1pt|iso` — real vanishing-point perspective by default, `persp` controls strength),
`rounded_circuits` (guillotine regions filled with serpentine conveyor-belt bands — parallel lines snaking through rounded U-turns, pink/blue interlock),
`lissajous_swarm` (phase-swept Lissajous family — sheared 3D tube/butterfly moiré; near-camera curves double-pass for depth thickness),
`black_hole` (Luminet 1979 — EXACT elliptic-integral solver verified against bgmeulem/luminet at machine precision: direct + n=1 ghost images, near-side ellipse fallback, flux-binned pens in lines mode, photographic-plate `mode=dots` with hot/inferno pen palettes, `mode=flow` — flux-duty dashes riding the lensed isoradials with screen-space stroke spacing (`flow_spacing` mm) and variable dash lengths, photon ring double-passed in every mode),
`pe_carpet` (sinusoidal positional-encoding matrix as a waveform carpet),
`attention_arcs` (attention as a score of arcs: pen per head, ink passes ∝ weight; `weights=ckpt.keras` uses trained Q/K via h5py, `attn_npz=...` uses real GPT-2 attention — extract with `scripts/extract_gpt2_attention.py`),
`residual_river` (transformer residual stream: channel lines weave at attention stations, band expands through FFN lenses, skip arcs per block).
Picture generators accept ANY photo: `--param channels=cmyk` splits a color image into cyan/magenta/yellow/black pen passes (Golden-Gate-style multicolor portraits).
`rounded_circuits` is ONE closed self-crossing belt with concentric constant-offset lines and big round turns. `iso_city` defaults to terraced plateau masses (fill/void space) with window details, cover-fit immersion (`zoom`, `height`, `lod`).
The `--anaglyph` glitch defaults to 4 pens (cyan/red/yellow/black); `--max-ink N --max-ink-cell MM` caps pen passes per spot on any generator.
`strange_attractor` systems (formCollapse catalog; divergent variants replaced with classical dynamics): lorenz, rossler, halvorsen, aizawa, rabinovich_fabrikant, chen, newton_leipnik, burke_shaw, finance, three_scroll, qi.
Effects (`generative/effects.py`): `--anaglyph [--anaglyph-offset MM] [--glitch N]` duplicates ANY generator into offset red/cyan pen layers with seeded glitch bands.
Paper safety: `harmonograph`/`strange_attractor` have an `overdraw` cap (default 6 hits per 0.8mm cell) so converging lines can't chew through the paper.
`art --port …` streams Leo-ready: heartbeat off + mandatory pen-up limits trace before inking.

## File import (SVG/DXF)
`promptplot import file.svg|file.dxf --group-by color|layer|auto --paper a4 --simulate --preview`.
`importers/svg_import.py` groups by SVG stroke color; `importers/dxf_import.py` groups by DXF layer.
Both ship **stdlib parsers** (work with no extra deps) and use `svgpathtools`/`ezdxf` for full
curve/entity fidelity when the `io` extra is installed (`pip install -e ".[io]"`). `importers/layers.py`
fits paths into the drawable area (uniform scale, centered, SVG Y flipped) and emits color-tagged strokes
that flow through the same color-layer pipeline.

## State management
- **PenState** — tracks pen up/down, validates commands (G0 requires UP, G1 requires DOWN), used across postprocess, workflow, and plotter
- **Phase transitions** — validated state machine: IDLE → PLANNING → GENERATING → STREAMING ↔ PAUSED → DONE. Invalid transitions raise `IllegalTransitionError`.
- **Connection SM** — plotter connection lifecycle: DISCONNECTED → CONNECTING → IDLE → STREAMING. Handles ALARM detection and recovery.
- **Checkpoints** — interrupted drawings save state to `~/.promptplot/checkpoints/`. Resume with `--resume`.

## File structure
All source lives in `promptplot/`. Three formerly-monolithic modules are now **subpackages** whose
`__init__.py` re-exports the same public names (so `from promptplot.llm import X` etc. are unchanged):
- `llm/` — `base.py` (LLMProvider ABC, errors), `providers.py` (7 providers + `create_llm_provider`/`get_llm_provider`), `prompts.py` (all `build_*_prompt`, `classify_creative_mode`, presets, few-shot, palette color block).
- `workflow/` — `events.py`, `_shared.py` (helpers + `diagnose_failure` + console/logger), `batch.py`, `supervisor.py`, `streaming.py`, `livedraw.py`.
- `cli/` — `_group.py` (the `cli` click group + `main` + `_get_config`/`_print_score`), `draw.py`, `generate.py`, `art.py`, `import_cmd.py`, `manage.py` (config/plotter/interactive/ui/library). `__main__.py` enables `python -m promptplot`.
- `generative/` — **NEW.** `rng.py` (`SeededRNG`: seeded Random + numpy + value/fbm noise), `generators.py` (8 generators), `registry.py` (`GENERATOR_REGISTRY` + signature-introspected schemas + `run_generator`). See "Generative art".
- `importers/` — **NEW.** `svg_import.py`, `dxf_import.py`, `layers.py` (fit-to-paper + color/layer grouping), `__init__.py` (`import_file`, `parse_file`). See "File import".

Core flat modules:
- `config.py` — **Dataclass** config tree (paper, pen, brush, **color**, bounds, vision, serial, LLM, workflow). `ColorConfig` (palette, park_position, pause_for_swap, assign_mode) and `PaperConfig.from_size("a4")`. Not pydantic-BaseSettings and not `PROMPTPLOT_`-prefixed — LLM keys read direct env vars: `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `ANTHROPIC_API_KEY`, `GPT4_API_KEY`/`GPT4_ENDPOINT`/`GPT4_API_VERSION` (Azure). Don't "modernize" to the workspace env_prefix convention without being asked.
- `engine.py` — Workflow engine, PenState, Phase enum, validated transitions, DrawingSession
- `models.py` — Pydantic models: GCodeCommand (has a `color` field, emitted as a `; color=N` comment), GCodeProgram, DrawProgram/DrawCommand, PrimitiveCommand/FreeformCommand (carry a `color`), WorkflowResult, CompositionPlan (+figurative/abstract variants), Region, ChunkMetrics
- `primitives.py` — PRIMITIVE/FREEFORM registries and `expand_primitives` (propagates a block-level `color` onto emitted strokes); schemas introspected from `expand_*` signatures and injected into prompts (see "Drawing DSL")
- `orchestrate.py` — pure-function public API: `plan_regions`, `generate_region`, `validate_chunk`, `score_chunk`, `merge_chunks`, `stream_chunk`, `stream_pen_layers`/`split_color_layers` (multi-color), `load_and_continue`, `compose_and_stream`
- `pipeline.py` — FilePipeline: load .gcode → postprocess → preview → stream
- `plotter.py` — ConnectionState SM, BasePlotter ABC, SerialPlotter (ALARM/recovery/pause/resume), SimulatedPlotter
- `postprocess.py` — pipeline: arcs, bounds, pen safety, stroke optimization (or `reorder_by_color` when multi-color → per-color optimize, never across a color), dips, dwells; plus `validate_chunk`
- `checkpoint.py` — CheckpointManager for resumable drawings
- `visualizer.py` — matplotlib GCode renderer with stats; color-coded per-pen preview when a program has color layers
- `scoring.py` — Quality scorer (A–F grades), style profile extractor, `score_chunk`
- `memory.py` — Drawing memory (JSONL) for few-shot retrieval
- `tui.py` — Rich-based TUI with planning/paused phase display
- `logger.py` — Rich-based terminal output
- `__init__.py` — Public API exports (the stable surface for the `orchestrate`/`compose_and_stream` controller path)
- `scripts/` — standalone Claude-Code controller scripts (`cc_draw_*.py`, `cc_colors_test.py`, `cc_brush_test.py`, `cc_llm_stream.py`) using the `orchestrate` API directly against hardware

## Serial port
- macOS: `/dev/cu.usbserial-*` (e.g. `/dev/cu.usbserial-1420`)
- Linux: `/dev/ttyUSB0`
- Windows: `COM3`
