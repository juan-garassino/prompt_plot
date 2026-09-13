# STYLE CANONS — the studio's four movements (ALWAYS with lines)

Every piece is assigned ONE style by the curator/translator. The ART CRITIC
judges against that style's canon below, not against generic taste. Hard house
constraint across all four: everything is LINES — line work, hatching, dot
lattices, multi-pass weights. "Solid" only ever means serpentine/spiral/
concentric line fills. No element that a pen cannot draw as strokes.

## 1. BAUHAUS (1920s) — kit exists: `bauhaus.py`

Geometry as ideology. Circles/bars/quarter-discs, one accent color used
scarcely, spaced-caps type, swatch bar, M 1:80 footer.
Palette: blue | pink | black. Line moves: spiral/serpentine fills, dotted
orbits, crosshair rules. Critic notes: asymmetric balance required; furniture
must sit on a shared grid.

## 2. ART DECO (1920–30s)

Machine-age luxury: sunburst ray fans, stepped ziggurat outlines, chevrons,
nested arcs, fan shells, frame ornaments, symmetric monumentality (symmetry is
ALLOWED and often right here). Thin/thick alternation via 1–3 passes.
Palette: gold | black (+ one jewel tone: emerald or crimson) on cream.
Line moves: radiating line fans with geometric spacing, concentric stepped
borders, parallel-line gradients (spacing ramps), zigzag bands.
Critic notes: demands craft precision — ray spacing must be exact; ornament is
welcome but must be rhythmic, never noisy. Type: spaced caps, wide tracking,
centered allowed.

## 3. SWISS / INTERNATIONAL TYPOGRAPHIC STYLE (1950s)

The grid is the artwork. Strict modular grid (document the module in the
code), flush-left type, extreme scale contrast (one HUGE element), radical
negative space, diagonal energy, zero ornament.
Palette: red | black on white (max 2 pens + white space as third color).
Line moves: hairline rules, line-screen tone (parallel-line halftone), massive
type set with the stroke font (letters 20–60mm tall as graphic mass),
grid-locked photography-substitute = the data drawing itself.
Critic notes: symmetric or centered = automatic fail; any element off the
module grid = fail; if nothing is huge, fail.

## 4. POP ART (1960s)

Mechanical reproduction as art: Ben-Day dot lattices (regular dot grids at
2–4 sizes = tone), fat contour outlines (3–4 passes), repetition panels (the
same motif ×4/×6 with pen-role swaps per panel), comic energy marks
(speed lines, starbursts).
Palette: primary red | blue | yellow + black outlines (4 pens).
Line moves: benday dot fills (dot = 2 tiny strokes, strict lattice), bold
multi-pass contours, panel grids with thin gutters, halftone size ramps.
Critic notes: repetition must vary MEANINGFULLY (data changes per panel, not
just color); outlines must dominate; dot lattices must be perfectly regular —
wobble reads as error, not charm.

## Kit obligations (build as needed in the style's first piece)

- deco kit: `ray_fan()`, `stepped_border()`, `chevron_band()`, `line_gradient()`
- swiss kit: `modular_grid()`, `giant_type()` (stroke font at display sizes),
  `line_screen_tone()`
- pop kit: `benday_fill()` (dot lattice with size classes), `fat_outline()`
  (multi-pass contour), `panel_grid()`

Placement: shared helpers grow in `bauhaus.py` only if style-neutral; style
kits live with their first piece in `promptplot/generative/physics.py` or a
`styles_<name>.py` module once ≥2 pieces use them.
