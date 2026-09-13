# quantum-01 — encoding (VISUAL TRANSLATOR)

Source of truth: `studio/quantum-01/dossier.md` (Tonomura, Am. J. Phys. **57**, 117 (1989)).
Visual truth built: **VT-1** — accumulation: the same dots that look random ARE the fringes.

---

## 1. STYLE assignment

**SWISS / INTERNATIONAL TYPOGRAPHIC STYLE.**

Why (one line): the phenomenon's drama is *extreme scale contrast in N* (10 → 3 000 → 70 000),
and Swiss is the only canon whose signature move — one HUGE element on a strict module with
radical negative space — maps the N-axis directly onto composition; the canon's own words,
"grid-locked photography-substitute = the data drawing itself," literally describe a Tonomura frame.

Why not Pop (the curator's hunch, addressed): Pop's dot grammar is the Ben-Day lattice —
"perfectly regular; wobble reads as error" — and regularity is **exactly the lie this dossier
forbids** (no de-clumping, no blue-noise, Poisson or nothing). Pop's repetition panels fit, but
its core dot canon contradicts the physics; the art critic would be forced to fail either the
style or the science. Swiss celebrates the grid *around* the dots while leaving the dots wild.

---

## 2. The one-glance statement

> **Randomness, accumulated, is a wave.**

Sub-reading (30 cm): every mark is one whole electron that flew through the machine alone;
the ten red dots never move — they just get outvoted.

---

## 3. Channel mapping (Tufte: nothing drawn that encodes nothing)

| Ink on paper | Encodes | Rule |
|---|---|---|
| One pen tap (dot) | **One real detection** — one whole electron landing | Identical mark for every electron, every panel (~0.4 mm tap). Never decorative, never tone-fill, never a half-dot or smear. Dot size is constant across panels: the *field* is magnified, the *event* is not. |
| Dot position (x, y) | Draw from P(x) = e^(−x²/2σ²)·cos²(πx/s), y uniform (dossier E2) | The cos² law is expressed **only** through seeded sampled dots. No drawn curve, ever. Ratios fixed: crop = 5 fringe periods across panel width, σ = 2s, identical in all panels. |
| Panel | **Time / N** — a cumulative frame of ONE run | Panels are nested prefixes of one SeededRNG sequence (seed **1989**, fixed blind, no seed-shopping). Panel k = first N_k accepted points. Same crop, same s:σ:field ratios, only uniform magnification differs. |
| Panel scale (small → huge) | The growth of the sample; the story axis | 30×20 → 60×40 → 180×120 mm (1 : 2 : 6 linear). Down the page = later = more. |
| Red pen | **Arrival index ≤ 10** — the first ten electrons, in every panel | A real measured quantity (detection order). Same ten positions recur at three magnifications: visible, falsifiable proof that the panels are one experiment, not redraws. Scarce (30 taps total) and loud. |
| Overprint saturation (`--max-ink 2`, 0.8 mm cell) | Detector/monitor saturation | Rendering limit, not statistics: drawn dots remain honest i.i.d. samples; collisions overprint, never thin. |
| Panel frame (hairline, 1 pass) | The detector's field of view (the paper's own Fig. 5 crop) | Same crop at three magnifications. Only non-data ink besides the caption. |
| White space | The signal not yet arrived | The quiet zone is the experiment before it happened. |

Plotting order = arrival order within each panel (black: arrivals 11…N_k; red: 1…10). The pen
re-performs the experiment on the desk: random taps that condense into fringes. Stroke
optimizer MUST NOT reorder dots (declared exception; see §8 escape hatch).

---

## 4. Composition — A4 portrait (210 × 297 mm)

**Module:** 10 mm grid, origin at margin corner (15, 15). Drawable x ∈ [15, 195] (18 columns),
y ∈ [15, 275] (26 rows); bottom margin deepened to 22 mm (Swiss). 5 mm sub-baseline for type.
Every panel edge sits on the module. Crop aspect **3:2** (W:H), fringes = 5 vertical bands
across each panel's width.

| Element | x (mm) | y (mm) | Size | Content |
|---|---|---|---|---|
| Panel A | [15, 45] | [15, 35] | 30 × 20 | N = 10 — all ten dots RED. Noise. Defeats the eye's pattern search. |
| Panel B | [15, 75] | [35, 75] | 60 × 40 | N = 100 — 90 black + the same 10 red. Still noise (E5: emergence needs ~500+). Shares its top edge with A: the two early moments fused. |
| — the leap — | | [75, 115] | 40 mm void | 4 empty modules between 100 and 3 000: the 29× jump in N is a silence, not a mark. |
| Panel C (DOMINANT) | [15, 195] | [115, 235] | **180 × 120** | N = 3 000 — 2 900 black + the same 10 red. Fringes undeniable (paper frame c: "begin to emerge"). Fringe period s = 36 mm, σ = 72 mm, crop ±2.5s. |
| Caption block | flush-left 15 | [245, 275] | 3 lines | See §8 for exact text. |
| QUIET ZONE | [75, 195] | [15, 115] | 120 × 100 | Shaped emptiness, top-right. Makes C read louder. |

Hierarchy: C dominates at 3 m (a striped field); B is the clear second at 1 m; the red
constellation and caption reward 30 cm. Linear ratios C:B = 3:1, C:A = 6:1.
Asymmetry: all masses hang on one flush-left axis (x = 15, shared by A, B, C, caption);
mass falls to the bottom, emptiness holds the top-right. Time reads straight down the page in
one scan, exactly as the dossier demands. Nothing bleeds off the frame — the crop is physics
and must stay whole.

Detector→paper magnification (colophon-grade fact): ×4.3 / ×8.6 / ×25.7 on top of the
experiment's own ×2000 — the plotter is the third magnification stage (dossier §3: exact,
not an approximation).

---

## 5. Pen budget (≤3; uses 2 + white)

| Pen | Physical | Meaning |
|---|---|---|
| 1 — BLACK 0.4 mm fineliner | dots (arrivals 11…N_k), panel frames (1-pass hairline), caption strokes | **Fact.** One tap = one electron. Frames = field of view. Caption = record. |
| 2 — RED 0.4 mm fineliner | ONLY arrivals 1–10, overprinted in all three panels (30 taps total) | **The witnesses.** The first ten electrons, drawn once each per panel, never black-duplicated. They prove the nesting and quietly correct "electrons interfere with each other": these ten landed alone, at random, and ended up part of a wave. |
| (3) — white paper | the third color, per Swiss canon | Not-yet-arrived probability. |

Is red honest? Yes: arrival index is a real recorded quantity; positions are untouched i.i.d.
draws. It is the dossier's own sanctioned second pen ("an increment, a real quantity") chosen
as the *first* increment so it stays scarce — a newest-arrivals pen would flood panels B and C
and fail Swiss scarcity. **One pen swap total** (all black, park, swap, all red).

---

## 6. Expressive levers (rubric, played consciously)

- **Proportion:** 6:1 linear cascade; dominant mass ≥3:1 over the second. The huge Swiss
  element is the data panel itself, not type.
- **Fill vs. void:** the 120×100 quiet zone; the 40 mm "leap" gap that IS the 100→3000 jump;
  deep bottom margin.
- **Density gradients:** the piece's only gradient IS dot density, and both of its ramps are
  physics: cos² fringe modulation across each panel, Gaussian envelope falloff toward the
  crop edges (~45% at the edge fringes). No cosmetic ramp is permitted on top.
- **Color play:** red as scarce accent (30 taps against ~3 000 black) — compositional weight,
  and also the piece's proof of honesty.
- **Texture direction:** none chosen, and that IS the choice — i.i.d. dots have no direction;
  any texture anisotropy would be fabricated information.
- **Depth & dimensionality (rubric dim 7) — FLATNESS DECLARED:** this piece is consciously
  flat, doubly justified: (a) Swiss-ITS is flat by canon; (b) the detector is a plane — the
  data has two spatial dimensions plus *time*, and the composition spends its entire depth
  budget on the time axis via the 1:2:6 scale cascade and the nested red constellation
  recurring at three magnifications. Occlusion, perspective, or tone-as-volume would assert a
  third spatial dimension the phenomenon does not have. Statistical depth, not spatial depth.

---

## 7. Forbidden list

Inherited from the dossier (science critic fails the piece on any):
1. **No trajectories** — no lines source→slit→dot, no paths, no arrows through slits; do not
   connect the red dots (a constellation line is a trajectory in disguise).
2. No drawn wave — no ripples through slits, no splash "becoming" particles.
3. No cleaning of low-N panels — no de-clumping, stratifying, blue-noise, hand-placing.
   Clumpy unfairness at N = 10 and 100 is the message.
4. No early fringe hints — no dot placed on maxima by hand, no tuning N = 100 to whisper
   stripes. **Seed fixed at 1989 before first render; re-rolling the seed to get a
   "better-looking" panel is forbidden** (it is de-clumping by other means).
5. No per-panel redraws — nested prefixes of ONE stream, or the caption is false.
6. No changing s, σ, or the field crop between panels; no sinc² envelope.

Visual additions (translator's):
7. **No drawn cos² curve, no envelope line, no axes, ticks, plots, or graph furniture**
   (rubric NO-SCHEMATICS: the subject is the phenomenon, never the apparatus). No biprism
   diagram, no slit icon, no labeled arrows.
8. No dot-size variation, no halftone conversion, no lattice-snapping (no Ben-Day
   regularization), no smoothing of the dense panel.
9. No furniture that encodes nothing: the only non-data ink is the three panel frames and
   the caption. No swatch bars, no plus marks, no ornament.
10. No centering, no symmetric layout, nothing off the 10 mm module (Swiss canon: automatic
    fail).
11. Panel frames must not bleed off the sheet — cropping the frame would silently change the
    field of view.

---

## 8. Fabrication

**Density gate** (dossier §6): peak ≈ 2N/(W·H) ≤ 1 dot/mm².

| Panel | N | Area (mm²) | 2N/A (dots/mm²) | Gate |
|---|---|---|---|---|
| A | 10 | 600 | 0.033 | ✓ |
| B | 100 | 2 400 | 0.083 | ✓ |
| C | 3 000 | 21 600 | 0.278 | ✓ (3.6× headroom) |

**The honest cap — decided:** the plotted sequence is the paper's own frames (a)–(c):
**10 / 100 / 3 000**. Frame (d), 20 000, at the gate needs ≥ 40 000 mm² — 79% of A4's
drawable area — which annihilates the quiet zone, pushes draw time past 6 h, and saturates
dots into tone, dissolving the piece's core claim that one mark = one indivisible electron.
Frame (e), 70 000, needs ≥ 140 000 mm² ≈ 2.8 sheets: physically unplottable at A4. At 3 000
the fringes are, by the paper's own caption and by E5, already undeniable — and uniquely at
this N the viewer sees the wave and the individual particles *simultaneously*. We plot the
moment order is born, and the caption carries the full truth of the record:

**Caption (flush-left x = 15, spaced caps, stroke font, black, 1 pass):**
- Line 1 (5 mm caps): `ONE ELECTRON AT A TIME`
- Line 2 (2.5 mm caps): `10 · 100 · 3 000 DETECTIONS — THE FIRST FRAMES OF TONOMURA'S
  70 000. EACH DOT: ONE WHOLE ELECTRON, ALONE IN THE MACHINE. RED: THE FIRST TEN, IN EVERY
  FRAME.`
- Line 3 (2 mm caps, colophon): `A. TONOMURA ET AL., AM. J. PHYS. 57, 117 (1989). ELECTRON
  BIPRISM — ONE WAVEFRONT SPLIT INTO TWO CONVERGING HALVES: THE TWO-SLIT EXPERIMENT MADE
  REAL. P(X) ∝ e^(−X²/2σ²)·COS²(πX/S), S = 1.4 MM AT THE DETECTOR; σ RECONSTRUCTED FROM THE
  PUBLISHED FRAMES. FRAMES 20 000 AND 70 000 EXCEED THIS SHEET'S INK. SEED 1989.`

The caption confirms; it never explains. It names 70 000 without claiming it, declares the
reconstructed σ (dossier requirement), and carries the biprism credit that licenses the
double-slit framing.

**Sampling:** rejection from P(x) = e^(−x²/2σ²)·cos²(πx/s), x over ±2.5s, y uniform, ONE
SeededRNG stream, seed 1989, i.i.d. — no stratification, no minimum-distance rejection.
Work in detector units (s = 1.4, σ = 2.8, crop 7 wide), scale uniformly per panel (exact,
per dossier §3).

**Marks & order:** dot = single pen tap (down–up, no stroke), ~0.4 mm, identical everywhere.
Plot furniture first (frames, caption — registration check), then black dots in arrival
order (B: 11–100, C: 11–3 000), one park+swap, then red dots 1–10 per panel A→B→C in arrival
order. `--max-ink 2` per 0.8 mm cell; collisions overprint (detector saturation), never thin.
**Escape hatch:** arrival order is the default (the plot performs the experiment); if the
draw-time gate fails, the designer may fall back to optimized ordering with curator sign-off —
the finished artifact is identical.

**Budget:** ~3 120 taps + 3 frames + caption ≈ 60–90 min with arrival-order travel. Pen
swaps: 1 (gate ≤ 4 ✓). Stroke spacing satisfied by panel sizing, not statistics ✓.

**Leo note (A5 landscape, /dev/cu.usbserial-14120):** rotate the composition 90° (time then
reads left→right, the dossier's own scan direction) and scale ×0.707; all densities double —
C peaks at 0.56 dots/mm², still under the gate ✓. House rule stands: mandatory pen-up limits
trace before any ink.
