# Two kinds of art (+ one file store) — the classification

Juan's observation: the project has two parts — the **generative** pieces and the
**custom-designed** pieces "that need to go to a library, unless they are also
script-formed". Correct. Here is the sharpened architecture.

## The distinguishing question: is the SEED a creative axis or a nuisance?

### A. GENERATORS — parametric families (seed = creative axis)
`promptplot/generative/generators.py` + `registry.py`. Driven by `promptplot art
<name> --seed N`. Many seeds are ALL wanted; the family IS the product
(truchet, vortex_field, flow_field, the attractors, black_hole …).
Contract: seed materially changes output; schema introspected from the
signature; tests include **seed-differs** + deterministic + in-bounds.

### B. COMPOSITIONS — designed singletons (seed = fine-tune, often data-linked)
`promptplot/generative/bauhaus.py`, `physics.py` (studio output), and the future
astro/quantum/ml pieces. ONE artwork per function; the composition is the value,
not a parametric family. Seed only jitters detail (a Lorenz path, a dot cloud) —
there is no "gw150914 seed 12" anyone wants; the data is the data.
Contract: deterministic + in-bounds, but **NOT seed-differs** (already how the
bauhaus/big_bang entries are excluded). Each carries its studio trail
(`studio/<slug>/dossier.md` + `encoding.md`) and a canonical render in `leo/`.

### C. FILE LIBRARY — frozen `.gcode` (last resort or pinned snapshot)
`~/.promptplot/library/` via `promptplot library list|play`. For pieces that
genuinely can't be scripted (hand-edited gcode, a specific imported SVG) OR a
pinned render of a script piece at one exact size you never want to drift.

## The rule: PREFER SCRIPT ALWAYS

A frozen `.gcode` is dead — it replays only at its baked paper size and palette.
A script piece (A or B) re-renders at any paper/pen/margin, is diffable,
improvable (the whole studio critic-loop depends on this), and stays data-live
(gw150914 re-reads the real LIGO file — change the event with one param).
Freeze to the file library (C) only when a piece cannot be a script, or when you
want a guaranteed-immutable snapshot.

## Decision tree for any new piece
1. Do you want many seeds, all valid? → **A. generator** (generators.py).
2. Is it ONE designed/ data-linked artwork? → **B. composition** (its own
   module, studio trail, seed = fine-tune). ← the studio produces these.
3. Can it not be scripted at all? → **C. file library** (.gcode).

## Practical consequences (not done yet — the roadmap this implies)
- Registry stays single (shared schema introspection, `art` can run both), but
  each entry should be **tagged** `kind="generator"|"composition"` so
  `art --list` groups them and the seed-differs test auto-applies to generators
  only (today it's a hand-maintained list).
- A `promptplot compose <name>` alias (or `art --gallery`) could list only
  compositions with their one canonical seed + studio link.
- `bauhaus.py` + `physics.py` ARE the compositions home already; they just need
  the label and the tag.

## The four-layer framework (2026-09-13)

The system is now one pipeline — science illustration as art, natively:

```
ENGINE   promptplot/generative/engine3d.py + kit.py
         the from-scratch 3D pen-plotter renderer (z-buffer hidden-line
         terrains/ribbons) + the 2D design kit (fills, type, furniture).
   ↓
PIECES   promptplot/generative/pieces/{ml,abstract,physics}.py
         seeded compositions by science domain (neural nets today; quantum,
         astro, relativity to come). Style-NEUTRAL: `bauhaus_*` names are
         legacy compat (shimmed via bauhaus.py); new pieces get subject-based
         names. Registered in registry.py like any generator.
   ↓
LAMINA   promptplot/lamina/  →  `promptplot plate`
         a finished plottable sheet: one piece as a poster or several as
         panels, style preset (bauhaus/swiss/deco/pop/radial_viz/
         science_poster) mapping semantic pens → physical pens + furniture,
         postprocessed, split into pen layers, previewed, streamed to Leo.
   ↓
STUDIO   promptplot/studio/  →  `promptplot studio`
         briefs (studio/<domain>/*.md) + the native designer → render →
         vision-critic → synth loop on any LLM provider. The near-mandatory
         path for NEW pieces; code-mode candidates live under
         studio/<slug>/rounds/ until a human promotes them into pieces/.
```

Agents reach every layer: the built-in agent + MCP expose `studio_list_briefs`,
`studio_get_brief`, `studio_design`, `compose_plate`, and hardware always goes
through `stream_to_plotter` (pen-up limits trace + confirm).
