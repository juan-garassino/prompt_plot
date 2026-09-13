"""Style presets — the movement canons applied at the LAMINA level.

The semantic-pen convention (kit slots): pieces emit pen INDICES with the kit
meaning — slot 0 = cool/secondary (BLUE), slot 1 = the scarce accent (PINK),
slot 2 = structure/type (BLACK), slot 3 = extra content pen. Preset ``pens``
are ordered BY SLOT, so a plate maps semantics to physical pens simply via
``config.color.palette = preset.pens`` before ``merge_chunks``. Two-pen styles
put structure at slot 0 (``_pen`` wraps BLACK→0 when colors=2). One piece →
many styled plates.

Presets encode the canons in ``promptplot/generative/STYLES.md``; the critic
notes there remain the judging authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class StylePreset:
    name: str
    pens: List[str]  # physical palette; index == semantic pen index
    paper: str  # "cream" | "white" (paper stock note, not rendered)
    furniture: Tuple[str, ...]  # which furniture elements the plate draws
    type_align: str  # "left" | "center"
    rule_passes: int = 1  # passes for gutter rules / hairlines
    accent_pen: int = 1  # semantic index reserved for the scarce accent
    notes: str = ""  # one-line canon reminder


STYLE_PRESETS: Dict[str, StylePreset] = {
    "bauhaus": StylePreset(
        name="bauhaus",
        pens=["dodgerblue", "deeppink", "black"],
        paper="cream",
        furniture=("title", "swatch_bar", "scale_footer", "number_chips"),
        type_align="left",
        notes="geometry as ideology; asymmetric balance; accent scarce",
    ),
    "swiss": StylePreset(
        name="swiss",
        pens=["black", "red"],
        paper="white",
        furniture=("title", "gutter_rules", "scale_footer"),
        type_align="left",
        notes="the grid is the artwork; one HUGE element; centered = fail",
    ),
    "deco": StylePreset(
        name="deco",
        pens=["goldenrod", "darkred", "black"],
        paper="cream",
        furniture=("title", "gutter_rules", "scale_footer", "number_chips"),
        type_align="center",
        rule_passes=2,
        notes="machine-age luxury; ray fans; symmetry allowed; exact spacing",
    ),
    "pop": StylePreset(
        name="pop",
        pens=["blue", "red", "black", "gold"],
        paper="white",
        furniture=("title", "gutter_rules", "number_chips"),
        type_align="left",
        rule_passes=3,
        notes="benday dots; fat outlines; repetition must vary meaningfully",
    ),
    "radial_viz": StylePreset(
        name="radial_viz",
        pens=["steelblue", "indianred", "black", "darkseagreen"],
        paper="cream",
        furniture=("title", "scale_footer", "swatch_bar"),
        type_align="left",
        notes="data as concentric arcs; annotation is the point, gridded",
    ),
    "science_poster": StylePreset(
        name="science_poster",
        pens=["dodgerblue", "crimson", "black", "forestgreen"],
        paper="cream",
        furniture=("title", "gutter_rules", "scale_footer", "number_chips"),
        type_align="left",
        notes="one dominant body; field density IS the data; data footer",
    ),
}


def get_style(name: str) -> StylePreset:
    if name not in STYLE_PRESETS:
        raise KeyError(f"Unknown style {name!r}. Available: {sorted(STYLE_PRESETS)}")
    return STYLE_PRESETS[name]
