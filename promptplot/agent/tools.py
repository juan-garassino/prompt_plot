"""The agent toolbox — one registry, used by the loop, the REPL and (later) MCP.

Tools wrap EXISTING PromptPlot machinery; this module adds no drawing logic.
``tier`` gates execution: "safe" runs freely, "confirm" requires an approval
callback (interactive y/N, or --yes-plot headless).
"""

from __future__ import annotations

import asyncio
import inspect
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ..config import PaperConfig, PromptPlotConfig
from ..generative import registry as gen_registry
from ..memory import DrawingMemory
from ..models import GCodeCommand, GCodeProgram
from ..orchestrate import merge_chunks
from ..scoring import score_gcode


@dataclass
class Tool:
    name: str
    description: str
    params: Dict[str, Any]  # JSON-schema "properties" style
    handler: Callable[..., Any]
    tier: str = "safe"  # safe | confirm


@dataclass
class ToolContext:
    config: PromptPlotConfig
    session: Any  # AgentSession
    provider: Any = None  # LLMProvider, needed by vision tools (Phase B)
    yes_plot: bool = False
    approve: Optional[Callable[[str], bool]] = None  # interactive confirm


def _summary(report) -> Dict[str, Any]:
    return {
        "grade": report.grade,
        "canvas_utilization": round(report.canvas_utilization, 3),
        "draw_travel_ratio": round(report.draw_travel_ratio, 2),
        "stroke_count": report.stroke_count,
        "command_count": report.command_count,
        "dominant_issue": report.dominant_issue,
    }


def _render_program(
    ctx: ToolContext,
    commands: List[GCodeCommand],
    stem: str,
    paper: str,
    orientation: str,
    palette: Optional[List[str]],
) -> Dict[str, Any]:
    cfg = ctx.config
    cfg.paper = PaperConfig.from_size(paper, orientation=orientation, margin=cfg.paper.margin_x)
    if palette:
        cfg.color.enabled = True
        cfg.color.palette = list(palette)
    program = merge_chunks([commands], cfg)
    gcode_path = ctx.session.render_path(stem, "gcode")
    gcode_path.write_text("\n".join(c.to_gcode() for c in program.commands))
    png_path = ctx.session.render_path(stem, "png")
    from ..visualizer import GCodeVisualizer  # matplotlib import stays lazy

    GCodeVisualizer(cfg).preview(program, str(png_path))
    report = score_gcode(program, cfg.paper)
    return {
        "png_path": str(png_path),
        "gcode_path": str(gcode_path),
        "commands": len(program.commands),
        "score": _summary(report),
    }


# ---------------------------------------------------------------------------
# handlers
# ---------------------------------------------------------------------------


def _t_list_generators(ctx: ToolContext) -> Dict[str, Any]:
    return {"generators": gen_registry.list_generators()}


def _t_generator_schema(ctx: ToolContext, name: str) -> Dict[str, Any]:
    return gen_registry.get_generator_schema(name)


def _t_render_generator(
    ctx: ToolContext,
    name: str,
    seed: int = 42,
    colors: int = 1,
    params: Optional[Dict[str, Any]] = None,
    paper: str = "a4",
    orientation: str = "landscape",
    palette: Optional[List[str]] = None,
) -> Dict[str, Any]:
    cfg = ctx.config
    cfg.paper = PaperConfig.from_size(paper, orientation=orientation, margin=cfg.paper.margin_x)
    bounds = cfg.paper.get_drawable_area()
    commands = gen_registry.run_generator(name, bounds, seed, colors=colors, params=params or {})
    return _render_program(ctx, commands, f"{name}_seed{seed}", paper, orientation, palette)


def _t_render_draw_program(
    ctx: ToolContext,
    blocks: List[Dict[str, Any]],
    paper: str = "a4",
    orientation: str = "landscape",
    palette: Optional[List[str]] = None,
) -> Dict[str, Any]:
    from ..models import DrawCommand, DrawProgram
    from ..primitives import expand_primitives

    program = DrawProgram(commands=[DrawCommand(**b) for b in blocks])
    cfg = ctx.config
    cfg.paper = PaperConfig.from_size(paper, orientation=orientation, margin=cfg.paper.margin_x)
    gprog = expand_primitives(program, cfg.pen)
    return _render_program(ctx, list(gprog.commands), "draw_program", paper, orientation, palette)


def _t_score_gcode(ctx: ToolContext, gcode_path: str) -> Dict[str, Any]:
    program = _load_gcode(gcode_path)
    return _summary(score_gcode(program, ctx.config.paper))


def _t_memory_search(ctx: ToolContext, prompt: str, top_k: int = 3) -> Dict[str, Any]:
    mem = DrawingMemory()
    hits = mem.find_similar(prompt, top_k=top_k)
    return {
        "matches": [
            {"prompt": h.prompt, "grade": h.grade, "creative_mode": h.creative_mode} for h in hits
        ]
    }


def _t_validate_gcode(ctx: ToolContext, gcode_path: str) -> Dict[str, Any]:
    from ..engine import PenState
    from ..orchestrate import validate_chunk

    program = _load_gcode(gcode_path)
    commands = list(program.commands)
    _fixed, warnings, _pen = validate_chunk(commands, PenState(), ctx.config.paper)
    return {"commands": len(commands), "warnings": warnings[:20], "ok": not warnings}


def _t_import_file(
    ctx: ToolContext, path: str, paper: str = "a4", orientation: str = "landscape"
) -> Dict[str, Any]:
    from ..importers import import_file

    cfg = ctx.config
    cfg.paper = PaperConfig.from_size(paper, orientation=orientation, margin=cfg.paper.margin_x)
    commands = import_file(path, cfg)
    stem = Path(path).stem
    return _render_program(ctx, list(commands), f"import_{stem}", paper, orientation, None)


def _t_list_session_renders(ctx: ToolContext) -> Dict[str, Any]:
    return {"renders": ctx.session.list_renders()}


CRITIC_PROMPT = """You are a strict art director for pen-plotter drawings.
Judge this preview like a curator: composition, page fill (margins must stay
clear), line rhythm/spacing (no solid pooling that damages paper), and whether
the piece has one clear visual idea. Reply with:
VERDICT: keep | tweak | reject
ISSUES: <up to 3 bullets>
SUGGESTION: <one concrete parameter-level change>
{brief}"""


async def _t_critique_render(ctx: ToolContext, png_path: str, brief: str = "") -> Dict[str, Any]:
    if ctx.provider is None:
        return {"error": "no LLM provider attached to this session"}
    extra = f"\nClient brief: {brief}" if brief else ""
    text = await ctx.provider.acomplete_multimodal(
        CRITIC_PROMPT.format(brief=extra), image_paths=[Path(png_path)]
    )
    return {"critique": text}


def _load_gcode(path: str) -> GCodeProgram:
    from ..pipeline import FilePipeline

    return FilePipeline(PromptPlotConfig()).load_gcode_file(path)


async def _t_stream_to_plotter(
    ctx: ToolContext, gcode_path: str, port: str = "simulate"
) -> Dict[str, Any]:
    from ..orchestrate import stream_pen_layers, trace_frame
    from ..plotter import SerialPlotter, SimulatedPlotter

    program = _load_gcode(gcode_path)
    if port == "simulate":
        plotter = SimulatedPlotter()
        await plotter.connect()
    else:
        # heartbeat off: single-reader discipline during long streams
        plotter = SerialPlotter(
            port=port, baud_rate=ctx.config.serial.baud_rate, enable_heartbeat=False
        )
        if not await plotter.connect():
            return {"error": f"could not connect to {port}"}
    # mandatory guardrail: pen-up tour of the drawable limits first
    await trace_frame(plotter, ctx.config.paper, laps=1)
    ok, err = await stream_pen_layers(program, plotter, ctx.config, verbose=False)
    if port != "simulate":
        await plotter.send_command("M5")
        await plotter.send_command("G0 X0 Y0")
        await plotter.disconnect()
    return {"streamed_ok": ok, "errors": err, "port": port}


def _t_save_to_library(ctx: ToolContext, gcode_path: str, name: str) -> Dict[str, Any]:
    lib = Path.home() / ".promptplot" / "library"
    lib.mkdir(parents=True, exist_ok=True)
    dest = lib / f"{name}.gcode"
    dest.write_text(Path(gcode_path).read_text())
    return {"saved": str(dest)}


TOOLBOX: List[Tool] = [
    Tool("list_generators", "List all seeded art generator names.", {}, _t_list_generators),
    Tool(
        "generator_schema",
        "Get a generator's docstring and parameters.",
        {"name": {"type": "string"}},
        _t_generator_schema,
    ),
    Tool(
        "render_generator",
        "Run a seeded generator, save gcode + png preview, return paths and an A-F quality score.",
        {
            "name": {"type": "string"},
            "seed": {"type": "integer"},
            "colors": {"type": "integer"},
            "params": {"type": "object"},
            "paper": {"type": "string", "enum": ["a3", "a4", "a5", "a6"]},
            "orientation": {"type": "string", "enum": ["portrait", "landscape"]},
            "palette": {"type": "array", "items": {"type": "string"}},
        },
        _t_render_generator,
    ),
    Tool(
        "render_draw_program",
        "Render a list of PRIMITIVE/FREEFORM DSL blocks (dicts) to gcode + png.",
        {
            "blocks": {"type": "array"},
            "paper": {"type": "string"},
            "orientation": {"type": "string"},
            "palette": {"type": "array", "items": {"type": "string"}},
        },
        _t_render_draw_program,
    ),
    Tool(
        "score_gcode",
        "Score an existing .gcode file (A-F grade + metrics).",
        {"gcode_path": {"type": "string"}},
        _t_score_gcode,
    ),
    Tool(
        "validate_gcode",
        "Validate a .gcode file for safety/bounds issues.",
        {"gcode_path": {"type": "string"}},
        _t_validate_gcode,
    ),
    Tool(
        "import_file",
        "Import an SVG or DXF file and render it to gcode + png.",
        {
            "path": {"type": "string"},
            "paper": {"type": "string"},
            "orientation": {"type": "string"},
        },
        _t_import_file,
    ),
    Tool(
        "memory_search",
        "Search past drawings for similar prompts (few-shot recall).",
        {"prompt": {"type": "string"}, "top_k": {"type": "integer"}},
        _t_memory_search,
    ),
    Tool(
        "list_session_renders",
        "List artifacts produced in this session.",
        {},
        _t_list_session_renders,
    ),
    Tool(
        "critique_render",
        "Look at a rendered png with the vision model and return an art-director critique.",
        {"png_path": {"type": "string"}, "brief": {"type": "string"}},
        _t_critique_render,
    ),
    Tool(
        "stream_to_plotter",
        "Send a .gcode file to the plotter (traces the pen-up frame first; "
        "port 'simulate' for a dry run). REQUIRES USER CONFIRMATION.",
        {"gcode_path": {"type": "string"}, "port": {"type": "string"}},
        _t_stream_to_plotter,
        tier="confirm",
    ),
    Tool(
        "save_to_library",
        "Save a .gcode file into the curated library. REQUIRES USER CONFIRMATION.",
        {"gcode_path": {"type": "string"}, "name": {"type": "string"}},
        _t_save_to_library,
        tier="confirm",
    ),
]


def get_tool(name: str) -> Optional[Tool]:
    for t in TOOLBOX:
        if t.name == name:
            return t
    return None


async def dispatch(ctx: ToolContext, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Run a tool with permission gating; returns a JSON-safe result dict."""
    tool = get_tool(name)
    if tool is None:
        return {"error": f"unknown tool {name!r}; call one of " f"{[t.name for t in TOOLBOX]}"}
    if tool.tier == "confirm":
        allowed = ctx.yes_plot or (ctx.approve is not None and ctx.approve(name))
        if not allowed:
            return {"error": f"tool {name!r} requires user confirmation and none was given"}
    t0 = time.time()
    try:
        result = tool.handler(ctx, **args)
        if inspect.isawaitable(result):
            result = await result
    except TypeError as e:
        return {"error": f"bad arguments for {name}: {e}"}
    except Exception as e:  # tool errors go back to the model, not up the stack
        return {"error": f"{type(e).__name__}: {e}"}
    ctx.session.trace(name, args, json.dumps(result)[:400], time.time() - t0)
    return result
