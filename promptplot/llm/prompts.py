"""Config-aware prompt builders, few-shot examples, and creative-mode routing.

Split out of the former monolithic llm.py during the v3.1 reorg.
"""

import json as _json
from pathlib import Path as _Path
from typing import Any, Optional, Dict, List

from ..config import PaperConfig, PenConfig
from ..primitives import format_schemas_for_prompt

# Auto-generated primitive documentation from function signatures
_PRIMITIVES_PROMPT_BLOCK = format_schemas_for_prompt()


# ===== sliced body (FEW_SHOT_EXAMPLES, prompt builders, presets) below =====
# ---------------------------------------------------------------------------
# Few-shot examples (Phase D)
# ---------------------------------------------------------------------------

FEW_SHOT_EXAMPLES = {
    "geometric": {
        "description": "A square with cross-hatching",
        "commands": [
            {"command": "M5"},
            {"command": "G0", "x": 40, "y": 40},
            {"command": "M3", "s": 1000},
            {"command": "G1", "x": 160, "y": 40, "f": 2000},
            {"command": "G1", "x": 160, "y": 160, "f": 2000},
            {"command": "G1", "x": 40, "y": 160, "f": 2000},
            {"command": "G1", "x": 40, "y": 40, "f": 2000},
            {"command": "M5"},
            {"command": "G0", "x": 60, "y": 40},
            {"command": "M3", "s": 1000},
            {"command": "G1", "x": 60, "y": 160, "f": 2000},
            {"command": "M5"},
            {"command": "G0", "x": 100, "y": 40},
            {"command": "M3", "s": 1000},
            {"command": "G1", "x": 100, "y": 160, "f": 2000},
            {"command": "M5"},
            {"command": "G0", "x": 140, "y": 40},
            {"command": "M3", "s": 1000},
            {"command": "G1", "x": 140, "y": 160, "f": 2000},
            {"command": "M5"},
            {"command": "G0", "x": 0, "y": 0},
        ],
    },
    "organic": {
        "description": "A flower with curved petals using short G1 segments",
        "commands": [
            {"command": "M5"},
            {"command": "G0", "x": 100, "y": 120},
            {"command": "M3", "s": 1000},
            {"command": "G1", "x": 105, "y": 135, "f": 2000},
            {"command": "G1", "x": 108, "y": 150, "f": 2000},
            {"command": "G1", "x": 105, "y": 165, "f": 2000},
            {"command": "G1", "x": 100, "y": 175, "f": 2000},
            {"command": "G1", "x": 95, "y": 165, "f": 2000},
            {"command": "G1", "x": 92, "y": 150, "f": 2000},
            {"command": "G1", "x": 95, "y": 135, "f": 2000},
            {"command": "G1", "x": 100, "y": 120, "f": 2000},
            {"command": "M5"},
            {"command": "G0", "x": 100, "y": 175},
            {"command": "M3", "s": 1000},
            {"command": "G1", "x": 100, "y": 250, "f": 2000},
            {"command": "M5"},
            {"command": "G0", "x": 0, "y": 0},
        ],
    },
}

# ---------------------------------------------------------------------------
# JSON-based few-shot examples (Phase 2)
# ---------------------------------------------------------------------------


def _load_examples_json() -> list:
    """Load curated examples from examples.json."""
    examples_path = _Path(__file__).parent.parent / "examples.json"
    if not examples_path.exists():
        return []
    try:
        with open(examples_path, "r") as f:
            return _json.load(f)
    except Exception:
        return []


_CACHED_EXAMPLES: Optional[list] = None


def _get_examples() -> list:
    global _CACHED_EXAMPLES
    if _CACHED_EXAMPLES is None:
        _CACHED_EXAMPLES = _load_examples_json()
    return _CACHED_EXAMPLES


# Keywords that select geometric vs organic examples (fallback)
_GEOMETRIC_KEYWORDS = {
    "square",
    "rectangle",
    "triangle",
    "grid",
    "line",
    "hexagon",
    "polygon",
    "geometric",
    "pattern",
    "maze",
    "box",
    "diamond",
}
_ORGANIC_KEYWORDS = {
    "flower",
    "tree",
    "leaf",
    "face",
    "animal",
    "cat",
    "dog",
    "bird",
    "fish",
    "wave",
    "cloud",
    "mountain",
    "organic",
    "sketch",
    "portrait",
}


def _select_example(user_prompt: str) -> Optional[str]:
    """Select a relevant few-shot example based on keywords in the prompt."""
    words = set(user_prompt.lower().split())
    # Try JSON examples first
    examples = _get_examples()
    if examples:
        best_match = None
        best_score = 0
        for ex in examples:
            kw_set = set(ex.get("keywords", []))
            overlap = len(words & kw_set)
            if overlap > best_score:
                best_score = overlap
                best_match = ex["name"]
        if best_match:
            return best_match

    # Fallback to original keyword sets
    if words & _ORGANIC_KEYWORDS:
        return "organic"
    if words & _GEOMETRIC_KEYWORDS:
        return "geometric"
    return None


# ---------------------------------------------------------------------------
# Complexity estimation (Phase 2)
# ---------------------------------------------------------------------------

_COMPLEX_KEYWORDS = {
    "detailed",
    "complex",
    "intricate",
    "cityscape",
    "landscape",
    "portrait",
    "realistic",
    "elaborate",
    "dense",
    "fine",
    "scene",
    "scenery",
    "panorama",
    "forest",
    "village",
    "city",
    "garden",
    "underwater",
    "battlefield",
    "mountains",
    "valley",
}
_SIMPLE_KEYWORDS = {"simple", "basic", "single", "minimal", "one", "just"}
_ABSTRACT_KEYWORDS = {
    "abstract",
    "pattern",
    "moire",
    "generative",
    "op-art",
    "opart",
    "flow",
    "field",
    "tiling",
    "spiral",
    "concentric",
    "interference",
    "texture",
    "rhythm",
    "grid",
    "hatch",
    "stipple",
    "radial",
    "geometric",
    "wave",
}
_FIGURATIVE_KEYWORDS = {
    "landscape",
    "portrait",
    "animal",
    "cat",
    "dog",
    "bird",
    "tree",
    "mountain",
    "face",
    "house",
    "person",
    "figure",
    "figurative",
    "scene",
    "flower",
    "river",
    "cloud",
    "forest",
    "village",
    "cityscape",
    "boat",
}


def estimate_complexity(prompt: str) -> str:
    """Estimate prompt complexity from keywords, word count, and element count."""
    words = prompt.lower().split()
    word_set = set(words)
    # Count distinct elements mentioned (commas and "and" suggest multiple subjects)
    element_separators = (
        prompt.lower().count(",") + prompt.lower().count(" and ") + prompt.lower().count(" with ")
    )
    if word_set & _COMPLEX_KEYWORDS or len(words) > 15 or element_separators >= 2:
        return "complex"
    if word_set & _SIMPLE_KEYWORDS or len(words) <= 4:
        return "simple"
    return "moderate"


def classify_creative_mode(prompt: str) -> str:
    """Classify a prompt into figurative, abstract, or hybrid."""
    words = set(prompt.lower().replace("-", " ").split())
    abstract_score = len(words & _ABSTRACT_KEYWORDS)
    figurative_score = len(words & _FIGURATIVE_KEYWORDS)
    if abstract_score > 0 and figurative_score > 0:
        return "hybrid"
    if abstract_score > figurative_score:
        return "abstract"
    return "figurative"


# ---------------------------------------------------------------------------
# Style presets (Phase D)
# ---------------------------------------------------------------------------

STYLE_PRESETS = {
    "artistic": """ARTISTIC GUIDELINES:
- Use the FULL canvas. Fill 60-80% of the drawable area. Spread elements across all regions.
- For organic shapes, use many short G1 segments (3-8mm each, at least 20-40 points per curve).
- Vary stroke density: denser lines for detail/shadows (2-3mm spacing), sparser for highlights (8-10mm).
- Connect strokes where possible -- continuous lines look better on paper.
- Compose with visual balance -- distribute elements across left, center, and right; top, middle, bottom.
- Add DETAIL: texture lines for ground/water, hatching for shadows, small decorative elements.
- Each major element should use 25-60 G1 commands. A full scene should have 10-20 distinct strokes.
- Think like a pen artist: build up detail through layered strokes, not single sparse lines.
- Add secondary details: texture strokes, fill patterns, hatching, decorative borders, repeated motifs.
- NEVER draw a shape with fewer than 10 G1 segments. Simple shapes look unfinished on paper.
- Build drawings in layers: silhouette first, contour second, texture/fill last.
- Use clean silhouettes for major forms, shorter marks for interior texture, and intentional empty areas for contrast.""",
    "precise": """STYLE: PRECISE
- Use clean, exact geometry with sharp corners.
- Straight lines should be perfectly straight (single G1 per segment).
- Maintain consistent spacing between parallel lines.
- Symmetry matters -- mirror coordinates accurately.""",
    "sketch": """STYLE: SKETCH
- Use overlapping, slightly offset strokes for a hand-drawn feel.
- Lines don't need to connect perfectly -- small gaps add character.
- Draw outlines with 2-3 slightly varied passes for a loose, expressive look.
- Vary line weight by drawing some strokes twice.""",
    "minimal": """STYLE: MINIMAL
- Use as few strokes as possible to convey the subject.
- Embrace negative space -- leave large areas of the canvas empty.
- Every line should be intentional and essential.
- Prefer continuous single-stroke drawings where possible.""",
}


# ---------------------------------------------------------------------------
# Config-aware prompt builders (Phase A)
# ---------------------------------------------------------------------------


def build_gcode_prompt(
    user_prompt: str,
    paper: PaperConfig,
    pen: PenConfig,
    style: str = "artistic",
    style_profile: Optional[Any] = None,
    memory_entry: Optional[Any] = None,
    creative_mode: str = "figurative",
    candidate_index: int = 0,
    palette: Optional[List[str]] = None,
) -> str:
    """Build a GCode generation prompt using actual config values."""
    x0, y0, x1, y1 = paper.get_drawable_area()
    w, h = paper.get_drawable_dimensions()
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    s_val = pen.pen_down_s_value
    f_val = pen.feed_rate

    # Scale example coordinates to ~20% and ~80% of drawable area
    ex_lo_x = round(x0 + w * 0.2, 1)
    ex_lo_y = round(y0 + h * 0.2, 1)
    ex_hi_x = round(x0 + w * 0.8, 1)
    ex_hi_y = round(y0 + h * 0.8, 1)

    orientation = getattr(paper, "orientation", None) or (
        "landscape" if paper.x_extent > paper.y_extent else "portrait"
    )
    orientation_tip = (
        "The canvas is wider than tall -- compose horizontally."
        if orientation == "landscape"
        else "The canvas is taller than wide -- compose vertically or use the height."
    )

    style_block = STYLE_PRESETS.get(style, STYLE_PRESETS["artistic"])

    # Adaptive detail based on complexity
    complexity = estimate_complexity(user_prompt)
    complexity_block = ""
    if complexity == "complex":
        complexity_block = f"""
COMPLEXITY: This is a DETAILED prompt. You MUST generate at least 200 GCode commands (aim for 250-400).
Use 80%+ of the canvas ({w:.0f}mm x {h:.0f}mm). Fill the composition with rich detail:
- Break every shape into many short G1 segments (3-8mm each) for smooth lines.
- Curves and arcs: 20-40 short segments each. More segments = smoother result.
- Straight edges: single G1 per side, but add detail nearby (hatching, texture, patterns).
- Repeated elements: use consistent spacing with many instances across the canvas.
- Add secondary detail: texture lines, fill patterns, decorative elements, borders.
- Layer the composition: large structural shapes first, then medium elements, then fine details.
- Use the FULL canvas height and width. Place elements across all four quadrants.
- Each distinct element should use 20-60 G1 commands depending on complexity.
DO NOT generate fewer than 200 commands. A detailed composition requires density and variety.
"""
    elif complexity == "simple":
        complexity_block = """
COMPLEXITY: Keep it simple. 20-40 GCode commands should suffice.
"""

    # Curve guidance
    curve_block = f"""
DRAWING TECHNIQUE — CRITICAL:
- Do NOT use G2/G3 arc commands. Approximate ALL curves with short G1 segments.
- For circles: use 16+ segments. For any curved shape: use 20-40 segments.
- Keep individual G1 segments SHORT (3-10mm) for smooth curves. Long segments look angular and robotic.
- For organic or irregular shapes, use MANY short segments with small variations in position.

Example: a curved line across the canvas (note the many small steps):
M5
G0 X{x0+w*0.1:.1f} Y{y0+h*0.6:.1f}
M3 S{s_val}
G1 X{x0+w*0.15:.1f} Y{y0+h*0.58:.1f} F{f_val}
G1 X{x0+w*0.22:.1f} Y{y0+h*0.62:.1f} F{f_val}
G1 X{x0+w*0.30:.1f} Y{y0+h*0.57:.1f} F{f_val}
G1 X{x0+w*0.38:.1f} Y{y0+h*0.61:.1f} F{f_val}
G1 X{x0+w*0.45:.1f} Y{y0+h*0.55:.1f} F{f_val}
G1 X{x0+w*0.52:.1f} Y{y0+h*0.59:.1f} F{f_val}
G1 X{x0+w*0.60:.1f} Y{y0+h*0.54:.1f} F{f_val}
G1 X{x0+w*0.68:.1f} Y{y0+h*0.58:.1f} F{f_val}
G1 X{x0+w*0.75:.1f} Y{y0+h*0.53:.1f} F{f_val}
G1 X{x0+w*0.85:.1f} Y{y0+h*0.56:.1f} F{f_val}
M5
(That is just ONE element — a full scene needs 5-10 such elements with this level of detail.)

SCENE COMPOSITION RULES:
- Divide the canvas into zones: top third = sky/background, middle = main subjects, bottom = foreground.
- Place elements at DIFFERENT positions across the full X range ({x0:.0f} to {x1:.0f}) and Y range ({y0:.0f} to {y1:.0f}).
- Each distinct element (mountain, tree, river, bird) should be a separate stroke (M5 -> G0 -> M3 -> G1s -> M5).
- Draw multiple instances: 3-5 trees, 2-3 mountain ridges, several birds at different heights.
- Add ground texture, ripples, or shading lines between major elements.
"""

    # Optionally include a few-shot example (try JSON examples first, then inline)
    example_key = _select_example(user_prompt)
    few_shot_block = ""
    json_examples = _get_examples()
    json_match = None
    if example_key and json_examples:
        json_match = next((ex for ex in json_examples if ex["name"] == example_key), None)

    if json_match:
        few_shot_block = f"""
REFERENCE EXAMPLE ({json_match['prompt']}):
{json_match['gcode'][:500]}

Use a similar structure but adapt to the actual prompt and canvas dimensions below.
"""
    elif example_key and example_key in FEW_SHOT_EXAMPLES:
        import json

        ex = FEW_SHOT_EXAMPLES[example_key]
        few_shot_block = f"""
REFERENCE EXAMPLE ({ex['description']}):
{json.dumps({"commands": ex["commands"]}, indent=2)}

Use a similar structure but adapt to the actual prompt and canvas dimensions below.
"""

    # Memory-based few-shot (from past successful drawings)
    memory_block = ""
    if memory_entry is not None:
        gcode_preview = memory_entry.gcode[:600]
        memory_block = f"""
SUCCESSFUL PREVIOUS DRAWING (similar request: "{memory_entry.prompt}"):
{gcode_preview}

Use a similar approach adapted to the current prompt.
"""

    # Style profile constraints
    style_profile_block = ""
    if style_profile is not None:
        hints = style_profile.to_prompt_hints()
        if hints:
            style_profile_block = f"\nSTYLE CONSTRAINTS (from reference): {hints}\n"

    # Primitives guidance — auto-generated from function signatures
    primitives_block = _PRIMITIVES_PROMPT_BLOCK
    freeform_block = f"""
FREEFORM DRAWING DSL (prefer this over raw G0/G1 for organic or expressive marks):
- Emit FREEFORM commands when the drawing needs contour, texture, or accents.
- FREEFORM contour_path / silhouette_outline:
  Use for major organic outlines and confident long contours.
  Example:
  {{"command":"FREEFORM","type":"silhouette_outline","params":{{"points":[[{ex_lo_x},{ex_lo_y}],[{cx:.1f},{cy:.1f}],[{ex_hi_x},{ex_hi_y}]],"closed":false}}}}
- FREEFORM texture_strokes:
  Use for foliage, fur, clouds, bark, terrain, water ripples, and shading clusters.
  Example:
  {{"command":"FREEFORM","type":"texture_strokes","params":{{"centers":[[{x0+w*0.3:.1f},{y0+h*0.6:.1f}],[{x0+w*0.35:.1f},{y0+h*0.58:.1f}]],"stroke_length":7,"angle":35,"jitter":25}}}}
- FREEFORM accent_marks:
  Use for sparse high-contrast finishing marks or small details.
- FREEFORM hatch_region:
  Use for shaded freeform regions when a simple rectangle hatch is enough.
- FREEFORM negative_space_region:
  Use to reserve important empty paper areas; this affects planning and critique even though it draws nothing.

REPRESENTATION RULES:
- Use PRIMITIVE for precise geometry, repeated fields, circles, polygons, structured hatch, spirals.
- Use FREEFORM for organic silhouettes, expressive contours, and local texture clusters.
- Use raw G0/G1 only as a fallback for unique one-off machine-specific motion.
- A strong result usually mixes: major structure in PRIMITIVE/FREEFORM silhouette objects, then texture in FREEFORM marks.
"""
    if creative_mode == "abstract":
        mode_block = """
CREATIVE MODE: ABSTRACT
- Build the page as a system of regions, not as one uniform texture.
- Create one focal event, one quiet/void area, and supporting fields around them.
- Prefer FREEFORM field_stack, moire_grid, radial_field, ring_field, tiling_field, gradient_hatch_region, noise_warped_flow, border_system.
- Vary rhythm, angle families, and density between regions.
- Avoid filling the entire page with one repeated motif unless explicitly requested.
"""
    elif creative_mode == "hybrid":
        mode_block = """
CREATIVE MODE: HYBRID
- Keep the figurative subject readable first.
- Use abstract systems to support atmosphere, framing, or texture around the subject.
- Reserve the main subject silhouette clearly against surrounding fields.
- Mix figurative FREEFORM commands with abstract field commands intentionally.
"""
    else:
        mode_block = """
CREATIVE MODE: FIGURATIVE
- Lead with silhouette and readable composition.
- Use FREEFORM silhouette_outline, contour_bundle, shading_region, texture_cluster, detail_pass_region, reserve_region.
- Place the subject before texture and keep at least one quiet region of paper.
"""
    candidate_block = ""
    if candidate_index > 0:
        candidate_block = f"""
CANDIDATE VARIATION:
- This is candidate {candidate_index + 1}. Deliberately vary the composition from other candidates.
- Change focal placement, density distribution, and support regions while keeping the prompt intent.
"""

    color_block = ""
    if palette and len(palette) > 1:
        color_list = ", ".join(f"{i}={name}" for i, name in enumerate(palette))
        color_block = f"""
COLOR LAYERS (this drawing uses {len(palette)} pens):
  Colors by index: {color_list}
  Add "color": <index> to each PRIMITIVE, FREEFORM, and G1 command to pick its pen.
  Assign colors meaningfully (e.g. sky=blue, foliage=green) and reuse them consistently.
  Example: {{"command": "G1", "x": {ex_hi_x}, "y": {ex_lo_y}, "f": {f_val}, "color": 1}}
"""

    prompt = f"""Create G-code for a pen plotter. Prompt: {user_prompt}

CANVAS: The drawable area is {w:.0f}mm x {h:.0f}mm.
  Minimum coordinates: X={x0:.1f}, Y={y0:.1f}
  Maximum coordinates: X={x1:.1f}, Y={y1:.1f}
  Center: X={cx:.1f}, Y={cy:.1f}
All X coordinates MUST be between {x0:.1f} and {x1:.1f}.
All Y coordinates MUST be between {y0:.1f} and {y1:.1f}.
{orientation_tip}

COMMANDS (only these are allowed):
  G0 Xnn Ynn   - Rapid move (pen must be UP). Used to reposition without drawing.
  G1 Xnn Ynn Fnnnn - Draw a line to (X,Y) at feed rate F (use F{f_val}). Pen must be DOWN.
  M3 S{s_val}      - Put pen DOWN (start drawing).
  M5           - Lift pen UP (stop drawing).

PEN CONTROL RULES (critical):
  1. ALWAYS start with M5 (pen up).
  2. Before every G0 rapid move, ensure pen is UP (M5).
  3. Before drawing with G1, ensure pen is DOWN (M3 S{s_val}).
  4. The sequence for each stroke is: M5 -> G0 (move to start) -> M3 S{s_val} -> G1 ... G1 (draw) -> M5
  5. ALWAYS end with: M5 then G0 X0 Y0 (pen up, return home).
{color_block}{few_shot_block}{memory_block}{style_profile_block}{complexity_block}
{curve_block}
{primitives_block}
{freeform_block}
{mode_block}
{candidate_block}
{style_block}

Return a JSON with "commands" list. Example:
{{
    "commands": [
        {{"command": "M5"}},
        {{"command": "G0", "x": {ex_lo_x}, "y": {ex_lo_y}}},
        {{"command": "M3", "s": {s_val}}},
        {{"command": "G1", "x": {ex_hi_x}, "y": {ex_lo_y}, "f": {f_val}}},
        {{"command": "G1", "x": {ex_hi_x}, "y": {ex_hi_y}, "f": {f_val}}},
        {{"command": "G1", "x": {ex_lo_x}, "y": {ex_hi_y}, "f": {f_val}}},
        {{"command": "G1", "x": {ex_lo_x}, "y": {ex_lo_y}, "f": {f_val}}},
        {{"command": "M5"}},
        {{"command": "G0", "x": 0, "y": 0}}
    ]
}}

Write just the JSON, no other text.
"""
    return prompt


def build_preview_reflection_prompt(
    user_prompt: str,
    critique: Dict[str, Any],
    paper: PaperConfig,
    style: str = "artistic",
    creative_mode: str = "figurative",
) -> str:
    """Build a refinement prompt from a structured preview critique."""
    x0, y0, x1, y1 = paper.get_drawable_area()
    w, h = paper.get_drawable_dimensions()
    reasons = critique.get("failure_reasons", [])
    dominant = critique.get("dominant_issue", "detail")
    critique_lines = [
        f"- dominant_issue: {dominant}",
        f"- silhouette_clarity: {critique.get('silhouette_clarity', 0):.2f}",
        f"- canvas_balance: {critique.get('canvas_balance', 0):.2f}",
        f"- density_variation: {critique.get('density_variation', 0):.2f}",
        f"- geometry_strength: {critique.get('geometry_strength', 0):.2f}",
        f"- freeform_quality: {critique.get('freeform_quality', 0):.2f}",
    ]
    if reasons:
        critique_lines.append("- failure_reasons: " + ", ".join(reasons))
    critique_text = "\n".join(critique_lines)
    if creative_mode == "abstract":
        mode_guidance = (
            "- strengthen focal vs void contrast\n"
            "- vary field rhythm between regions\n"
            "- reduce over-uniform texture and preserve one quiet region\n"
            "- prefer abstract field commands such as moire_grid, field_stack, radial_field, tiling_field\n"
        )
    elif creative_mode == "hybrid":
        mode_guidance = (
            "- keep the main subject readable before enriching the surrounding abstract fields\n"
            "- preserve a clean silhouette boundary around the subject\n"
            "- use abstract systems to support atmosphere, not to overwhelm the figure\n"
        )
    else:
        mode_guidance = (
            "- strengthen the main silhouette before adding more texture\n"
            "- keep the subject readable at a glance\n"
            "- use figurative commands such as silhouette_outline, contour_bundle, shading_region, texture_cluster\n"
        )
    return (
        f"Refine the drawing for this prompt: {user_prompt}\n"
        f"Style: {style}\n"
        f"Creative mode: {creative_mode}\n"
        f"Canvas: {w:.0f}mm x {h:.0f}mm with X={x0:.1f}-{x1:.1f}, Y={y0:.1f}-{y1:.1f}\n\n"
        "A preview critique found these issues:\n"
        f"{critique_text}\n\n"
        "Improve the composition intentionally:\n"
        "- distribute detail across the page instead of clustering near center\n"
        "- preserve negative space where it helps readability\n"
        "- use PRIMITIVE for geometry/fields and FREEFORM for organic contours/textures\n"
        f"{mode_guidance}"
        "- if the dominant issue is structural, revise silhouettes and layout\n"
        "- if the dominant issue is detail, keep the composition and enrich texture/fill\n\n"
        "Return ONLY valid JSON with a commands array using PRIMITIVE, FREEFORM, and/or raw GCode commands."
    )


def build_reflection_prompt(
    wrong_answer: str,
    error: str,
    paper: PaperConfig,
) -> str:
    """Build a reflection prompt that includes valid coordinate ranges."""
    x0, y0, x1, y1 = paper.get_drawable_area()
    return f"""Your previous response had validation errors and could not be processed correctly.

Previous response: {wrong_answer}

Error details: {error}

VALID COORDINATE RANGES:
  X must be between {x0:.1f} and {x1:.1f}
  Y must be between {y0:.1f} and {y1:.1f}

Please reflect on these errors and produce a valid response that strictly follows the required JSON format.
Make sure to:
1. Use proper JSON syntax with correct quotes, commas, and brackets
2. Include all required fields
3. Follow the schema definition precisely
4. Use valid commands (starting with G or M)
5. Use the right data types (numbers for coordinates, strings for command names)
6. Keep ALL coordinates within the valid ranges above

Return ONLY the corrected JSON with no additional text, code blocks, or explanations.
"""


def build_next_command_prompt(
    user_prompt: str,
    history: str,
    paper: PaperConfig,
    pen: PenConfig,
) -> str:
    """Build the streaming next-command prompt with real config values."""
    x0, y0, x1, y1 = paper.get_drawable_area()
    w, h = paper.get_drawable_dimensions()
    s_val = pen.pen_down_s_value
    f_val = pen.feed_rate

    return f"""Generate the NEXT single G-code command for a pen plotter based on this prompt: {user_prompt}

Previous commands:
{history}

CANVAS: {w:.0f}mm x {h:.0f}mm. All X coordinates MUST be between {x0:.1f} and {x1:.1f}. All Y coordinates MUST be between {y0:.1f} and {y1:.1f}.

Rules:
1. Use G0 for rapid movements (pen must be UP first via M5)
2. Use G1 for drawing lines with feed rate f={f_val} (pen must be DOWN first via M3 S{s_val})
3. M3 S{s_val} = pen DOWN, M5 = pen UP
4. Use only commands: G0, G1, M3, M5
5. All coordinates (x, y) should be float numbers within the canvas bounds
6. Stroke sequence: M5 -> G0 (reposition) -> M3 S{s_val} -> G1 (draw) -> M5
7. Always end with M5 then G0 X0 Y0

Return ONLY ONE command as JSON: {{"command": "G1", "x": 10.0, "y": 20.0, "f": {f_val}}}
If the drawing is complete, return: {{"command": "COMPLETE"}}
"""


def build_composition_plan_prompt(
    user_prompt: str,
    paper: PaperConfig,
    style: str = "artistic",
    creative_mode: str = "figurative",
    candidate_index: int = 0,
) -> str:
    """Build a prompt asking the LLM for a JSON composition plan."""
    x0, y0, x1, y1 = paper.get_drawable_area()
    w, h = paper.get_drawable_dimensions()
    candidate_line = (
        f"\nCandidate variation index: {candidate_index + 1}\n" if candidate_index > 0 else "\n"
    )
    if creative_mode == "abstract":
        return f"""You are a composition planner for abstract pen-plot art. Plan the page as regions with different visual roles.

Drawing request: {user_prompt}
Style: {style}
Canvas: {w:.0f}mm x {h:.0f}mm (drawable area X: {x0:.1f}-{x1:.1f}, Y: {y0:.1f}-{y1:.1f}){candidate_line}

Return a JSON object with this structure:
{{
  "regions": [
    {{
      "name": "focal region",
      "role": "focal",
      "x": 30.0,
      "y": 40.0,
      "width": 80.0,
      "height": 100.0,
      "field_family": "moire_grid",
      "density": "dense",
      "rhythm": "interference",
      "layer": 1
    }},
    {{
      "name": "quiet void",
      "role": "void",
      "x": 130.0,
      "y": 30.0,
      "width": 50.0,
      "height": 80.0,
      "field_family": "mask_region",
      "density": "sparse",
      "rhythm": "parallel",
      "layer": 0
    }}
  ],
  "style": "{style}",
  "estimated_commands": 180,
  "notes": "optional abstract composition notes"
}}

Rules:
- Include at least one focal region and one void region.
- Use 3-8 regions total.
- Spread regions across the page with clear density contrast.
- field_family should be one of: moire_grid, field_stack, radial_field, ring_field, tiling_field, gradient_hatch_region, noise_warped_flow, mask_region, border_system.
- Avoid uniform full-page texture.
Return ONLY the JSON.
"""
    return f"""You are a composition planner for a pen plotter. Given a drawing request,
plan the layout by breaking it into subjects with positions and sizes plus figurative regions.

Drawing request: {user_prompt}
Style: {style}
Canvas: {w:.0f}mm x {h:.0f}mm (drawable area X: {x0:.1f}-{x1:.1f}, Y: {y0:.1f}-{y1:.1f}){candidate_line}

Return a JSON object with this structure:
{{
    "subjects": [
        {{
            "name": "main subject",
            "description": "brief description of what to draw",
            "x": 100.0,
            "y": 150.0,
            "width": 80.0,
            "height": 60.0,
            "density": "medium",
            "priority": 1
        }}
    ],
    "regions": [
        {{
            "name": "subject silhouette",
            "role": "subject",
            "x": 70.0,
            "y": 90.0,
            "width": 90.0,
            "height": 120.0,
            "line_mode": "silhouette",
            "density": "medium"
        }},
        {{
            "name": "reserved quiet area",
            "role": "void",
            "x": 150.0,
            "y": 40.0,
            "width": 40.0,
            "height": 70.0,
            "line_mode": "accent",
            "density": "sparse"
        }}
    ],
    "style": "{style}",
    "estimated_commands": 120,
    "notes": "optional composition notes"
}}

Rules:
- Include at least one subject and at least one void region.
- Use regions to separate silhouette, shading, detail, and quiet space.
- Use the full canvas with readable hierarchy.
- For hybrid prompts, allow abstract support ideas in notes but keep the subject readable.
Return ONLY the JSON.
"""


# ---------------------------------------------------------------------------
# Region worker prompts (supervisor-worker orchestration)
# ---------------------------------------------------------------------------


def build_region_worker_prompt(
    user_prompt: str,
    region: Any,
    config: Any,
    plan_context: Optional[str] = None,
) -> str:
    """Build a worker prompt constrained to a single region's bounds.

    Heavily biases the LLM toward primitive use (hatch, flow_field, crosshatch)
    and explicit bounds clamping for high density at low token cost.
    """
    x0, y0, x1, y1 = region.bounds
    rw = x1 - x0
    rh = y1 - y0
    s_val = config.pen.pen_down_s_value
    f_val = config.pen.feed_rate
    role = region.role
    density = region.target_density
    target_n = region.target_command_count
    name = region.name or "region"
    plan_block = f"\nGlobal composition context:\n{plan_context}\n" if plan_context else ""

    return f"""You are a region worker for a pen plotter. Generate GCode for ONE rectangular region only.

Region: {name} (role={role}, density={density})
Region bounds (HARD CLAMP — never go outside):
  X: [{x0:.1f}, {x1:.1f}]   width={rw:.1f}mm
  Y: [{y0:.1f}, {y1:.1f}]   height={rh:.1f}mm

User prompt: {user_prompt}
{plan_block}
CRITICAL RULES:
1. Every X coordinate must be in [{x0:.1f}, {x1:.1f}]. Every Y in [{y0:.1f}, {y1:.1f}]. NO EXCEPTIONS.
2. Pen safety: M5 before any G0 travel, M3 S{s_val} before any G1 draw.
3. Use feed rate F{f_val} on G1 commands.
4. Target ~{target_n} commands. Hit this density.

PRIMITIVE BIAS — STRONGLY PREFER PRIMITIVES OVER RAW G1:
- Use {{"command": "PRIMITIVE", "type": "hatch", "params": {{...}}}} for fills — one hatch expands to 50-200 G1 segments.
- Use "flow_field" for organic dense textures — expands to hundreds of segments.
- Use "crosshatch" for shading — even denser.
- Use "stipple" for dotted texture.
- Each primitive must have x, y, width, height parameters CLAMPED to the region bounds above.

For a dense region, emit 5-15 primitives. For sparse, emit 1-3 primitives plus a few G1 outlines.

{_PRIMITIVES_PROMPT_BLOCK}

Return JSON: {{"commands": [ ... ]}}
Mix PRIMITIVE commands with raw GCode (M3/M5/G0/G1) freely.
ALL coordinates within the region bounds above. Output ONLY the JSON.
"""
