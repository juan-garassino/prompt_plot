"""File import pillar — SVG/DXF → color-layered GCode.

Parse a vector file, split it by color (SVG stroke) or layer (DXF), fit it onto
the paper, and emit color-tagged strokes for the normal color-layer pipeline.
"""

from __future__ import annotations

import os
from typing import List, Tuple

from ..models import GCodeCommand
from .layers import ImportedPath, ImportResult, build_program_commands
from .svg_import import parse_svg
from .dxf_import import parse_dxf


def parse_file(path: str) -> ImportResult:
    """Parse an SVG or DXF file into an ImportResult (dispatch by extension)."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".svg":
        return parse_svg(path)
    if ext in (".dxf",):
        return parse_dxf(path)
    raise ValueError(f"Unsupported import format {ext!r}. Supported: .svg, .dxf")


def import_file(
    path: str, config, group_by: str = "auto", fit: bool = True
) -> Tuple[List[GCodeCommand], List[str], ImportResult]:
    """Import a file into color-tagged GCode.

    ``group_by`` = ``color`` (SVG default) | ``layer`` (DXF default) | ``auto``.
    Returns ``(commands, palette, result)``.
    """
    result = parse_file(path)
    if group_by == "auto":
        group_by = "layer" if result.source.lower().endswith(".dxf") else "color"
    commands, palette = build_program_commands(result, config, fit=fit, group_by=group_by)
    return commands, palette, result


__all__ = [
    "ImportedPath",
    "ImportResult",
    "parse_file",
    "parse_svg",
    "parse_dxf",
    "import_file",
    "build_program_commands",
]
