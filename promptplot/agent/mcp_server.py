"""PromptPlot MCP server — the toolbox over stdio for any MCP client.

Patterns follow the workspace chassis (029-mcp-boilerplate) and the
marketing_agent error envelope: ToolAnnotations hints on every tool, a typed
error envelope with a `remediation` field the client LLM can act on, inline
`Image` previews, `plot://` resources for artifacts, and the hardware tool
gated behind an explicit ``confirm=true`` argument + destructive hint.

Run: ``promptplot mcp`` (or ``python -m promptplot mcp-serve``).
"""

from __future__ import annotations

import asyncio
import json
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP, Image
from mcp.types import ToolAnnotations

from ..config import get_config
from .session import AgentSession
from .tools import ToolContext, dispatch

READ_ONLY = ToolAnnotations(readOnlyHint=True)
RENDERS = ToolAnnotations(readOnlyHint=False, destructiveHint=False)
HARDWARE = ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=True)


class ErrorCode(str, Enum):
    UNKNOWN_TOOL = "unknown_tool"
    BAD_ARGS = "bad_args"
    NOT_CONFIRMED = "not_confirmed"
    TOOL_FAILED = "tool_failed"


def _envelope(code: ErrorCode, message: str, remediation: str) -> Dict[str, Any]:
    return {"error": {"code": code.value, "message": message, "remediation": remediation}}


def _wrap(result: Dict[str, Any]) -> Dict[str, Any]:
    """Translate agent-tool errors into the MCP error envelope."""
    if "error" not in result:
        return result
    msg = result["error"]
    if "unknown tool" in msg:
        return _envelope(ErrorCode.UNKNOWN_TOOL, msg, "call list_generators or read the tool list")
    if "confirmation" in msg:
        return _envelope(
            ErrorCode.NOT_CONFIRMED, msg, "retry with confirm=true after asking the user"
        )
    if "bad arguments" in msg:
        return _envelope(
            ErrorCode.BAD_ARGS, msg, "check the tool schema and fix the argument names"
        )
    return _envelope(ErrorCode.TOOL_FAILED, msg, "inspect the message; adjust parameters and retry")


mcp = FastMCP("promptplot")
_ctx: Optional[ToolContext] = None


def _context() -> ToolContext:
    global _ctx
    if _ctx is None:
        _ctx = ToolContext(config=get_config(), session=AgentSession("mcp"))
    return _ctx


async def _run(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    return _wrap(await dispatch(_context(), name, args))


# -- catalog ------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
async def list_generators() -> dict:
    """List all seeded art generator names."""
    return await _run("list_generators", {})


@mcp.tool(annotations=READ_ONLY)
async def generator_schema(name: str) -> dict:
    """Get a generator's docstring and parameters."""
    return await _run("generator_schema", {"name": name})


# -- rendering ------------------------------------------------------------------


@mcp.tool(annotations=RENDERS)
async def render_generator(
    name: str,
    seed: int = 42,
    colors: int = 1,
    params: Optional[dict] = None,
    paper: str = "a4",
    orientation: str = "landscape",
    palette: Optional[List[str]] = None,
) -> dict:
    """Run a seeded generator; saves gcode + png and returns paths plus an A-F score."""
    return await _run(
        "render_generator",
        {
            "name": name,
            "seed": seed,
            "colors": colors,
            "params": params or {},
            "paper": paper,
            "orientation": orientation,
            "palette": palette,
        },
    )


@mcp.tool(annotations=RENDERS)
async def render_draw_program(
    blocks: List[dict], paper: str = "a4", orientation: str = "landscape"
) -> dict:
    """Render PRIMITIVE/FREEFORM DSL blocks to gcode + png."""
    return await _run(
        "render_draw_program", {"blocks": blocks, "paper": paper, "orientation": orientation}
    )


@mcp.tool(annotations=RENDERS)
async def import_file(path: str, paper: str = "a4", orientation: str = "landscape") -> dict:
    """Import an SVG or DXF file and render it."""
    return await _run("import_file", {"path": path, "paper": paper, "orientation": orientation})


@mcp.tool(annotations=READ_ONLY)
async def preview_image(png_path: str) -> Image:
    """Return a rendered png inline so the client can look at it."""
    return Image(path=png_path)


# -- analysis -------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
async def score_gcode(gcode_path: str) -> dict:
    """Score an existing .gcode file (A-F grade + metrics)."""
    return await _run("score_gcode", {"gcode_path": gcode_path})


@mcp.tool(annotations=READ_ONLY)
async def validate_gcode(gcode_path: str) -> dict:
    """Validate a .gcode file for safety/bounds issues."""
    return await _run("validate_gcode", {"gcode_path": gcode_path})


@mcp.tool(annotations=READ_ONLY)
async def memory_search(prompt: str, top_k: int = 3) -> dict:
    """Search past drawings for similar prompts."""
    return await _run("memory_search", {"prompt": prompt, "top_k": top_k})


@mcp.tool(annotations=READ_ONLY)
async def list_session_renders() -> dict:
    """List artifacts produced in this MCP session."""
    return await _run("list_session_renders", {})


# -- hardware (gated) -----------------------------------------------------------


@mcp.tool(annotations=HARDWARE)
async def stream_to_plotter(gcode_path: str, port: str = "simulate", confirm: bool = False) -> dict:
    """Send gcode to the physical plotter. ALWAYS traces the pen-up frame first.
    Requires confirm=true — ask the human before setting it. port='simulate' dry-runs."""
    ctx = _context()
    ctx.yes_plot = bool(confirm)
    try:
        return _wrap(
            await dispatch(ctx, "stream_to_plotter", {"gcode_path": gcode_path, "port": port})
        )
    finally:
        ctx.yes_plot = False


@mcp.tool(annotations=HARDWARE)
async def save_to_library(gcode_path: str, name: str, confirm: bool = False) -> dict:
    """Save a gcode file into the curated library. Requires confirm=true."""
    ctx = _context()
    ctx.yes_plot = bool(confirm)
    try:
        return _wrap(
            await dispatch(ctx, "save_to_library", {"gcode_path": gcode_path, "name": name})
        )
    finally:
        ctx.yes_plot = False


# -- framework layer: studio briefs + lamina plates -----------------------------


@mcp.tool(annotations=READ_ONLY)
async def studio_list_briefs(domain: Optional[str] = None) -> dict:
    """List the science-illustration design briefs (studio/<domain>/*.md)."""
    return await _run("studio_list_briefs", {"domain": domain})


@mcp.tool(annotations=READ_ONLY)
async def studio_get_brief(slug: str, domain: Optional[str] = None) -> dict:
    """Get one design brief (essence, status, sections) as markdown."""
    return await _run("studio_get_brief", {"slug": slug, "domain": domain})


@mcp.tool(annotations=RENDERS)
async def compose_plate(spec_json: dict) -> dict:
    """Compose a lamina (finished plottable sheet): panels of registry pieces +
    a style preset -> gcode + png + pen-layer plan. Plot via stream_to_plotter."""
    return await _run("compose_plate", {"spec_json": spec_json})


# -- resources ------------------------------------------------------------------


@mcp.resource("plot://renders", mime_type="application/json")
def renders_index() -> str:
    """Index of every artifact in the MCP session."""
    return json.dumps({"renders": _context().session.list_renders()})


@mcp.resource("plot://render/{filename}", mime_type="image/png")
def render_file(filename: str) -> bytes:
    """Fetch one artifact (png/gcode) from the MCP session by filename."""
    path = _context().session.renders_dir / filename
    return path.read_bytes()


@mcp.resource("plot://about", mime_type="text/markdown")
def about() -> str:
    return (
        "# PromptPlot MCP\n"
        "Seeded generative pen-plotter art. Typical flow: `list_generators` → "
        "`render_generator` → `preview_image` → iterate params → ask the human → "
        "`stream_to_plotter(confirm=true)`. Never plot without human confirmation."
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
