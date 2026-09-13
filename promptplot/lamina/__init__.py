"""Lamina — finished plottable sheets: pieces + style + layout + pen plan.

A lamina is one piece as a poster or several pieces composed as panels, with
style-preset palette/furniture, postprocessed and split into pen layers ready
for the plotter. See ``promptplot plate --help``.
"""

from __future__ import annotations

from .plate import Panel, PlateSpec, compose_plate, spec_from_json, spec_to_json
from .styles import STYLE_PRESETS, StylePreset, get_style

__all__ = [
    "Panel",
    "PlateSpec",
    "compose_plate",
    "spec_from_json",
    "spec_to_json",
    "STYLE_PRESETS",
    "StylePreset",
    "get_style",
]
