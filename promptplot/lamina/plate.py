"""Plate composition — a lamina is a finished plottable sheet.

``compose_plate(spec)`` turns a :class:`PlateSpec` (one or more panels of
registry pieces + a style preset + paper) into a postprocessed
:class:`~promptplot.models.GCodeProgram` plus a pen-layer plan, ready for
preview, saving, or streaming pen-by-pen to the plotter.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..config import PaperConfig, PromptPlotConfig
from ..generative import run_generator
from ..generative.kit import (
    _spaced,
    _stroke_text,
    _text_width,
    scale_footer,
    swatch_bar,
    type_block,
)
from ..models import GCodeCommand, GCodeProgram
from ..orchestrate import merge_chunks, split_color_layers
from .layout import gutter_rules, number_chips, reserve_bands, split_panels
from .styles import StylePreset, get_style


@dataclass
class Panel:
    generator: str
    seed: int = 7
    params: Dict[str, Any] = field(default_factory=dict)
    label: Optional[str] = None  # caption under the panel, spaced caps


@dataclass
class PlateSpec:
    panels: List[Panel]
    style: str = "bauhaus"
    title: Optional[str] = None
    subtitle: Optional[str] = None
    paper: str = "a4"
    orientation: str = "portrait"
    margin: float = 12.0
    gutter: float = 8.0
    rows: Optional[int] = None


def spec_to_json(spec: PlateSpec) -> str:
    return json.dumps(asdict(spec), indent=2)


def spec_from_json(text: str) -> PlateSpec:
    d = json.loads(text)
    d["panels"] = [Panel(**p) for p in d.get("panels", [])]
    return PlateSpec(**d)


def _furniture(
    spec: PlateSpec,
    preset: StylePreset,
    bounds,
    title_band,
    panels,
) -> List[GCodeCommand]:
    x0, y0, x1, y1 = bounds
    W = x1 - x0
    black = len(preset.pens) - 1  # last pen = structure/type by convention
    out: List[GCodeCommand] = []
    if "title" in preset.furniture and spec.title and title_band is not None:
        tx0, _ty0, tx1, ty1 = title_band
        if preset.type_align == "center":
            tw = _text_width(_spaced(spec.title), 3.6)
            tx = (tx0 + tx1) / 2 - tw / 2
        else:
            tx = tx0 + 0.02 * W
        out += type_block([spec.title], tx, ty1 - 2.0, height=3.6, pen=black, underline=False)
        if spec.subtitle:
            out += _stroke_text(_spaced(spec.subtitle), tx, ty1 - 11.0, 2.0, color=black)
    for i, p in enumerate(spec.panels):
        if p.label:
            px0, py0, px1, _py1 = panels[i]
            out += _stroke_text(_spaced(p.label), px0 + 1.0, py0 + 1.5, 1.8, color=black)
    if "gutter_rules" in preset.furniture and len(panels) > 1:
        out += gutter_rules(panels, spec.gutter, pen=black, passes=preset.rule_passes)
    if "number_chips" in preset.furniture and len(panels) > 1:
        out += number_chips(panels, pen=black)
    if "swatch_bar" in preset.furniture:
        out += swatch_bar(x1 - 8.0, y1 - 3.0, list(range(len(preset.pens))), size=2.2)
    if "scale_footer" in preset.furniture:
        out += scale_footer(bounds, pen=black)
    return out


def compose_plate(
    spec: PlateSpec, config: Optional[PromptPlotConfig] = None
) -> Tuple[GCodeProgram, List[Dict[str, Any]]]:
    """Compose a plate: panels → style pens → furniture → postprocess → pen plan."""
    if not spec.panels:
        raise ValueError("PlateSpec has no panels")
    preset = get_style(spec.style)
    config = config or PromptPlotConfig()
    config.paper = PaperConfig.from_size(spec.paper, orientation=spec.orientation, margin=spec.margin)
    config.color.enabled = True
    config.color.palette = list(preset.pens)

    bounds = config.paper.get_drawable_area()
    title_h = 16.0 if (spec.title and "title" in preset.furniture) else 0.0
    footer_h = 8.0 if "scale_footer" in preset.furniture else 0.0
    title_band, content, _footer_band = reserve_bands(bounds, title_h, footer_h)
    panels = split_panels(content, len(spec.panels), rows=spec.rows, gutter=spec.gutter)

    npens = len(preset.pens)
    chunks: List[List[GCodeCommand]] = []
    for p, pb in zip(spec.panels, panels):
        cmds = run_generator(p.generator, pb, p.seed, colors=npens, params=p.params)
        # clamp semantic pens beyond the style's palette to the last (structure)
        # pen so a 4-pen piece still plots cleanly in a 2/3-pen style.
        for c in cmds:
            if c.color is not None and c.color >= npens:
                c.color = npens - 1
        chunks.append(cmds)
    chunks.append(_furniture(spec, preset, bounds, title_band, panels))

    program = merge_chunks(chunks, config)
    pen_plan = [
        {"pen": color_idx, "name": (preset.pens[color_idx] if color_idx is not None and color_idx < len(preset.pens) else "default"), "strokes": len(cmds)}
        for color_idx, cmds in split_color_layers(program)
    ]
    return program, pen_plan
