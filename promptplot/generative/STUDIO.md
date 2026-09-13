# THE STUDIO — agent team & pipeline for plotted science infographics

Goal: map what is hard to visualize (astrophysics, quantum mechanics, ML) into
simple, artistic, TRUE pen-plotter pieces. Every piece runs this pipeline; every
artifact is written to `studio/<piece-slug>/` so rounds are reviewable.

## Roles

1. **CURATOR (main loop)** — owns the series, writes the one-line brief, chains
   the agents, resolves deadlocks, final gate before Juan's vote. Series
   coherence: the collection must feel like one hand.

2. **FIELD EXPERT** (astrophysicist / quantum physicist / ML researcher — one
   agent per domain). Input: topic. Output `dossier.md`:
   - the phenomenon in ≤5 lines, the governing quantities/equations
   - three candidate **visual truths** — quantitative relationships that could
     carry a drawing (ranked; each with "why it's visually potent")
   - REAL data sources or exact formulas to use (never fake data — house rule:
     real GPT-2 attention, real Luminet solutions, real LIGO strain, …)
   - honest simplifications allowed vs. distortions that would make it a lie
   - what laypeople commonly get wrong (the piece should quietly correct it)

3. **VISUAL TRANSLATOR (information designer)**. Input: dossier. Output
   `encoding.md`:
   - the STYLE assignment for the piece — one of the four canons in STYLES.md
     (Bauhaus / Art Deco / Swiss-ITS / Pop Art), with one line on why this
     movement fits this phenomenon; all styles are line-native by house rule
   - the one-glance statement the drawing must make
   - channel mapping: which quantity → position / length / density / angle /
     pen; Tufte discipline — nothing drawn that encodes nothing
   - composition sketch in words+coordinates (A4, margins, where masses sit)
   - pen budget (≤3–4) and what each pen MEANS
   - forbidden list for this piece (e.g. "no decorative orbits")

4. **DESIGNER (builder)**. Input: encoding.md + DESIGN_RUBRIC.md. Builds the
   generator (new pieces in `promptplot/generative/physics.py` on the bauhaus
   kit; never two designers on one file concurrently), renders to ~/Downloads
   root, ≤3 self-scored iterations, tests green, uncommitted.

5. **CRITIC PANEL** — two independent agents, both see the png cold:
   - **ART CRITIC**: DESIGN_RUBRIC six dimensions (avg ≥8, none <7) JUDGED
     AGAINST the piece's assigned style canon in STYLES.md (Deco may be
     symmetric; Swiss must not be; Pop must repeat meaningfully), 3 mandatory
     changes on fail → `critique-art-N.md`.
   - **SCIENCE CRITIC** (same domain as the expert, different instance; gets
     dossier + png, NOT the code): truth (is the physics right?), encoding
     fidelity (does the visual quantitatively match, no lying areas/scales?),
     insight legibility (does the phenomenon land?). Each ≥8. 3 mandatory
     changes on fail → `critique-science-N.md`.

6. **FABRICATION GATE** (no LLM): pytest green, validate_gcode clean, stroke
   spacing ≥0.8mm, pen swaps ≤4, draw time sane. Automated, non-negotiable.

## The loop

brief → EXPERT dossier → TRANSLATOR encoding → DESIGNER build/render
→ CRITIC PANEL (parallel) → fail: back to DESIGNER with both critics' mandates
→ 2 consecutive fails on the same mandate: back to TRANSLATOR (encoding is the
problem) → encoding declared unworkable: back to EXPERT for the next visual
truth → both critics pass → FABRICATION GATE → Juan votes → winner moves to
leo/, then commit.

## House rules

- Real data or exact math only; the dossier names the source.
- Previews always to ~/Downloads root; leo/ only after Juan promotes.
- Every piece: seeded, deterministic, bounded, registered, tested.
- Critics never see code or the designer's notes. Designers never grade
  themselves as final. The curator never overrides a double-fail silently.
