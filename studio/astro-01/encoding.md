# astro-01 — GW150914 — encoding spec

**Visual translator** · input: `dossier.md` v1 · output for: DESIGNER · **Status:** encoding v1

---

## 1. STYLE assignment

**ART DECO** (confirming the curator's hunch, for a data-driven reason, not the hunch's):
Deco's canonical parallel-line gradient — a geometric spacing ramp — *is* this signal's
zero-crossing clock, so the style's signature ornament can be built entirely from measured
quantities; the chirp is a machine-age crescendo and Deco is the only canon whose ornament
vocabulary encodes it without adding a single untrue mark.

(Why not Swiss, the runner-up: its 2-pen cap would force dropping either the NR-template
underlay or the accent, and the theory-under-measurement duet is the discovery itself.)

One caution the designer must hold: **the ray fan is reassigned.** No sunburst radiates from
the merger — that is an explosion cliché and a lie (nothing flashed). Deco's radiating-line
energy lives in one place only: the vertical zero-crossing colonnade (§4), whose spacing ramp
is real data.

---

## 2. The one-glance statement

**A runaway, measured by a flexing ruler: one unbroken line swells and quickens to a single
catastrophic peak, rings twice, and goes silent.**

At 3 m the viewer sees a calm line gathering itself into one violent swell near the right and
dying instantly. At 1 m they see the cause — two nearly-equal circles touching — hanging over
the exact instant of the peak. At 30 cm they find gold peeking from under black (prediction
under measurement, agreeing to a pen-width) and the footer's proton-width fact.

---

## 3. Composition of truths (a) + (b) — one subject, not two

- **Truth (a) — the real Hanford strain trace — carries the piece.** It is the dominant mass,
  the full drawable width, the only element allowed to touch both side margins.
- **Truth (b) — the dying orbit — is demoted to a medallion (a colophon, a seal).** Ø ≈ 34 mm
  (~1/7 the trace's visual mass), locked to the merger's time coordinate by a plumb line, with
  no independent position of its own: it exists *only where the trace peaks*. Cause above,
  effect below, joined at the catastrophe instant. It is subordinate by scale, by placement,
  and by dependency — it can never compete because it cannot move.
- Truth (c) is not drawn. Its content (frequency evolution) is carried honestly by the
  colonnade (§4), which is derived from the same zero crossings without pretending to be a
  musical score.

---

## 4. Channel mapping (Tufte discipline — every mark encodes)

| Quantity (source) | Channel | Scale |
|---|---|---|
| Time (`fig1-observed-H.txt`, 0.25–0.46 s window) | x-position | uniform, 267 mm / 0.21 s = **1.271 mm/ms** |
| Strain h(t), the measurement (same file, verbatim) | y-displacement from baseline | uniform, **27 mm per 1.0×10⁻²¹** |
| NR prediction (`fig1-waveform-H.txt`) | same x/y mapping, gold, drawn *under* the black data | identical scales — non-negotiable |
| Theory–data residual | **emergent**: gold visible beyond the black line edge | no separate residual trace |
| Instantaneous GW half-period (measured zero crossings of the plotted file) | spacing of vertical gold hairlines — the **colonnade** | 14.3 ms→18.2 mm at 35 Hz ramping to 2 ms→2.5 mm at 250 Hz |
| Orbital separation a(t) (Kepler + measured f(t), dossier §1) | radius of the two medallion spiral arms | 1 km = 0.0885 mm; r: 175 km→15.5 mm down to 96 km→8.5 mm; **exactly ~4 turns per arm** |
| The two horizons (Schwarzschild 106 km / 86 km) | crimson touching circles, true relative scale | radii 9.4 mm / 7.6 mm, centers 17 mm apart — they genuinely touch |
| Merger instant | shared x = 235 mm: peak, plumb line, medallion center | alignment = simultaneity |
| Epistemic status | **pen color** (§6): black=measured, gold=predicted/derived, crimson=contact | — |

Not encoded, deliberately: no axis, no ticks, no scale bar. The scales are attested in the
footer as text (§5 type). Amplitude needs no redundant channel — the swell is the swell.

---

## 5. Composition sketch — A4 landscape, margins 15 mm

Canvas 297×210 mm; drawable x ∈ [15, 282], y ∈ [15, 195] (origin bottom-left, mm, y up).

**Shared axes (the grid):** x=15 (title left, footer left, trace entry) · x=235 (the merger
plumb: peak, plumb line, medallion center) · x=282 (trace exit, right footer) · y=160 (title
rule and medallion center) · y=95 (strain baseline) · y=18 (footer baselines).

- **The trace (dominant mass).** Baseline y=95. Enters the LEFT margin mid-noise at x=15 and
  exits the RIGHT margin mid-noise at x=282 — the frame crops an ongoing quiet on both sides:
  the event is bracketed by ordinary noise and the window slices into it. Early inspiral
  ripples ±5–11 mm; merger swell peaks at (≈235, 122) and troughs to y=68; ringdown's two
  wiggles die by x≈250; residual noise ±2 mm to the edge.
- **The colonnade (secondary mass).** Vertical gold hairlines, one per zero crossing of the
  plotted file, from the first coherent in-band cycle (x≈40) to the end of ringdown (x≈250)
  — then absence: silence is shown by the colonnade stopping. ≈20–24 lines, band y ∈ [34, 78],
  spacing ramping 18 mm → 2.5 mm left to right. The merger troughs (y→68) plunge 10 mm into
  the band top — the only overlap in the piece, at the only moment that matters (§7 depth).
- **The medallion (tertiary).** Center (235, 160), overall Ø ≈ 34 mm: two gold spiral arms of
  ~4 tight turns each (r 15.5→8.5 mm — a plunge, not a coil; the arms are a thin annulus),
  terminating at two crimson touching circles, radii 9.4/7.6 mm, centers at (226.5, 160) and
  (243.5, 160). At true scale the horizons dominate the orbit — that IS the corrective punch.
  A dotted gold plumb line drops from the medallion's underside (235, 144) to just above the
  peak (235, 124).
- **Type.** Spaced caps throughout (Deco tracking), stroke font:
  - Title block, flush-left x=15: `GW150914` cap-height 9 mm, baseline y=180 (2 passes
    allowed for display weight). Under it, 3.5 mm caps baseline y=172:
    `THE FIRST GRAVITATIONAL-WAVE CHIRP · 14 SEPTEMBER 2015`. Then 2.5 mm caps baseline
    y=166: `LIGO HANFORD · BANDPASSED 35–350 HZ · 0.21 S OF DATA`.
  - Gold hairline rule at y=160, x 15→110 — it shares the medallion's center axis and points
    across the void to it.
  - Anatomy labels, black 2.5 mm caps, naked (no leaders, no arrows): `INSPIRAL` baseline
    y=112, left-aligned x=55 · `MERGER` baseline y=130, right-aligned to x=231 · `RINGDOWN`
    baseline y=112, left-aligned x=240.
  - Footers, 2.5 mm caps, baseline y=18: flush-left x=15:
    `AT PEAK, EACH 4 KM ARM CHANGED BY 4×10⁻¹⁸ M — 1/400 OF A PROTON · A RULER FLEXING, NOT A SOUND`
    flush-right x=282: `FULL HEIGHT = STRAIN 1.0×10⁻²¹ · GOLD: PREDICTION · BLACK: MEASUREMENT · GWOSC / PRL 116, 061102`.
- **Quiet zones (shaped, not leftover).** (1) Upper-middle: x 110–217, y 125–195 — pure cream
  between title rule and medallion; the rule's dead-end makes the emptiness read as a span
  being crossed. (2) Lower-left below the colonnade band (y < 34, x < 240) down to the footer.
  The dense zone (merger swell + tightest colonnade, x 200–250) reads louder against both.
- **What crops at the frame:** the trace, both sides, mid-noise. Nothing else touches a margin.

---

## 6. Pen budget — 3 pens (≤4 ✓), each with a meaning

| Pen | Tool | MEANING | Carries |
|---|---|---|---|
| 1 **BLACK** 0.3 mm fineliner | **The measurement / the record** | strain trace (single pass, one unbroken polyline, zero lifts), all type |
| 2 **GOLD** 0.5 mm gel | **The theory / the derived** | NR template (drawn first, under the data), colonnade, medallion spiral arms, rule + dotted plumb |
| 3 **CRIMSON** 0.3 mm | **The contact** | the two touching horizons (2 passes) + two terminal center dots — nothing else |

Ground: cream paper (Deco canon). Crimson total ink < 150 mm of stroke in a piece with
several meters of line: scarce and loud.

---

## 7. Expressive levers, played consciously

- **Density gradient (required — used twice, both true):** the colonnade's 18 → 2.5 mm spacing
  ramp is the measured chirp clock; the trace's own cycle-crowding is the second, free
  gradient. Nothing decorative generates density anywhere.
- **Depth decision — declared LOW-RELIEF:** Deco is a bas-relief tradition (elevator doors,
  not perspective), and the subject is a 1-D strain — faking 3-D on the data would lie. Depth
  is delivered by **occlusion only**: the black trace occludes the gold colonnade where the
  merger plunges into it (hairlines clipped with 1.2–1.5 mm relief gaps against the data
  polyline), and the crimson horizons occlude the gold arm ends. Occlusion appears exactly
  once in the field — at the catastrophe — so depth itself is an accent.
- **Scarce accent:** crimson exists only as the two touching circles + dots — the only closed
  shapes and the only double-passed marks in the piece.
- **Proportion:** trace (267 mm wide, 54 mm tall at climax) : medallion (34 mm) : type —
  a clear 3-level hierarchy; the 3 m read is the swell, not the seal.
- **Fill vs void:** packed (merger + tight colonnade) against two shaped silences (§5);
  the colonnade's *stop* after ringdown makes silence a drawn element.
- **Texture direction — chosen, not defaulted:** colonnade verticals run cross-grain to the
  horizontal flow of time (the clock ticks against the flow); medallion arms follow form.

---

## 8. Forbidden list for this piece

From the dossier's hard lies:
1. **No extended ringdown** — exactly the ~2 cycles in the file; no romantic tail.
2. **No many-turn spirals** — medallion arms: ~4 turns from the measured f(t), period.
3. **No rubber-sheet ripples** — no concentric circles radiating from anything, anywhere.
4. **No de-noised data presented as data** — plot `fig1-observed-H.txt` verbatim; resampling
   only below 0.1 mm at final scale; noise flanks and residual tail stay, untrimmed.
5. **No non-uniform axis distortion** — one uniform time scale, one uniform strain scale.
6. **If the analytic fallback is ever used, the caption changes** — it may not say LIGO data.

Visual additions:
7. **No schematic furniture** — no drawn axes, ticks, frame boxes, arrows, leader lines, or
   legend boxes. Annotations are naked type on the grid. (Pen meanings live in the footer text.)
8. **No sunburst/ray fan at the merger** — no explosion iconography; the event emitted no light
   here and the piece must not decorate the peak.
9. **No retracing or thickening of the data line** — the measurement is one pass, always; line
   weight games are for title and horizons only.
10. **No filled shapes** — horizons are outlines (multi-pass ring, optionally one inner
    concentric ring); house rule: everything is lines.
11. **Crimson nowhere except the horizons and their two dots.**
12. **No Livingston overlay** in v1 — one detector, one unbroken line; purity is the point.

---

## 9. Fabrication notes

- **Scale floor confirmed by dossier §6:** fastest merger cycle ≈ 4 ms ≈ 4.8 mm at this time
  scale → adjacent near-vertical strokes of the trace sit ≈ 2.4 mm apart at the worst point —
  comfortably above the **0.8 mm minimum spacing** with 0.3 mm pens. Colonnade minimum spacing
  2.5 mm ✓. Nothing in this piece may be drawn closer than 0.8 mm; if a design tweak violates
  this, the tweak loses.
- **Multi-pass weight allowed ONLY:** crimson horizon circles ×2; title `GW150914` ×2.
  Everything else — especially the data trace and the NR template — is strictly single-pass.
- **Draw order / swaps (2 swaps):** GOLD first (template → colonnade → arms → rule → plumb),
  swap; BLACK (trace in one unbroken zero-lift polyline → type), swap; CRIMSON (horizons →
  dots). Gold under black is deliberate: where prediction and measurement agree, black wins;
  where they differ, gold shows — the residual draws itself.
- **Relief gaps:** clip gold colonnade hairlines 1.2–1.5 mm short of the black trace path
  (computed against the data polyline), only where they would collide (merger region).
- **Data:** fetch `https://gwosc.org/GW150914data/P150914/fig1-observed-H.txt` and
  `fig1-waveform-H.txt`; cache locally in the piece's data dir; cite GWOSC / PRL 116, 061102
  in the footer. Seeded, deterministic, bounded, registered, tested — house rule.
- **Draw-time sanity:** ~3.4 k-point trace + ~24 hairlines + medallion + type; almost pure
  travel-free drawing; well within gate limits. Pen lifts: 0 within the trace; ~1 per
  colonnade line; type as usual.
