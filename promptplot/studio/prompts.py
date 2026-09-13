"""Prompt templates for the native studio loop (designer → critic → synth).

Each template inlines the governance canon — the chosen style's section from
``promptplot/generative/STYLES.md`` and the full ``DESIGN_RUBRIC.md`` — so the
loop enforces the same bar as the human-run studio. Replies must be a single
JSON object (parsed with the agent protocol's tolerant extractor).
"""

from __future__ import annotations

import re
from pathlib import Path

_GEN_DIR = Path(__file__).resolve().parents[1] / "generative"


def _read_doc(name: str) -> str:
    p = _GEN_DIR / name
    return p.read_text(encoding="utf-8") if p.exists() else ""


def style_canon(style: str) -> str:
    """The one style's section from STYLES.md (falls back to the whole doc)."""
    text = _read_doc("STYLES.md")
    if not text:
        return ""
    pattern = rf"^##\s+\d+\.\s+.*{re.escape(style)}.*?$\n(.*?)(?=^##\s|\Z)"
    m = re.search(pattern, text, flags=re.MULTILINE | re.DOTALL | re.IGNORECASE)
    return m.group(0) if m else text


def rubric() -> str:
    return _read_doc("DESIGN_RUBRIC.md")


DESIGNER_PROMPT = """You are a DESIGNER in the PromptPlot studio, designing for a REAL pen
plotter (lines only — no gradients, no fills except line-fills; tone = line density).

THE BRIEF:
{brief}

STYLE CANON (obey it):
{style_canon}

DESIGN RUBRIC (you will be scored against this; pass = avg>=8, no dimension <7;
the no-schematics rule is absolute — draw the phenomenon, not the apparatus):
{rubric}

{mode_instructions}

{feedback}

Reply with EXACTLY ONE JSON object, nothing else:
{{"concept": "<one-paragraph concept>", "payload": {payload_schema}}}
"""

PARAMS_MODE_INSTRUCTIONS = """MODE: params. Propose a rendering of EXISTING registry pieces.
Available pieces and their parameter schemas:
{schemas}
Your payload selects piece(s), seeds, and parameter overrides to realize the brief."""

PARAMS_PAYLOAD_SCHEMA = (
    '{"panels": [{"generator": "<registry name>", "seed": <int>, '
    '"params": {"<param>": <value>}, "label": "<optional caption>"}], '
    '"title": "<spaced caps>", "subtitle": "<spaced caps>"}'
)

CODE_MODE_INSTRUCTIONS = """MODE: code. Write a NEW piece as one Python function
`def {fn_name}(rng, bounds, colors=3, feed=2200) -> list` following the house
conventions: all randomness via the passed SeededRNG; emit GCodeCommand lists via
the kit helpers (import from promptplot.generative.bauhaus: _poly, _pen, BLUE/PINK/BLACK,
fill_disc, circle, type_block, _stroke_text, _spaced, scale_footer, _zbuf_terrain for 3D).
Stay inside `bounds`; deterministic; black+red palette unless the brief says otherwise."""

CODE_PAYLOAD_SCHEMA = '{"function_name": "<name>", "source": "<complete python source>"}'

CRITIC_PROMPT = """You are the STUDIO CRITIC PANEL (art director + science critic) judging a
pen-plotter render against the brief and rubric. Be harsh; the render is attached.

THE BRIEF:
{brief}

DESIGN RUBRIC:
{rubric}

Score all 7 dimensions 0-10 (pass = avg>=8 AND none <7). Apply the no-schematics
rule ruthlessly. Reply with EXACTLY ONE JSON object:
{{"scores": {{"hierarchy": n, "grid_alignment": n, "tension_asymmetry": n,
"negative_space": n, "pen_craft": n, "concept_legibility": n,
"depth_dimensionality": n}}, "verdict": "pass|revise|fail",
"top_fixes": ["..."], "one_line": "..."}}
"""

SYNTH_PROMPT = """You are the STUDIO LEAD. Fold this critique into ONE concrete instruction
for the designer's next round (or declare the piece done).

CONCEPT: {concept}
CRITIQUE: {critique}

Reply with EXACTLY ONE JSON object:
{{"done": true|false, "instruction": "<the single most important change for the next round>"}}
"""
