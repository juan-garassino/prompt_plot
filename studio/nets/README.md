# ABSTRACT NEURAL REPRESENTATIONS FOR PENPLOTTERS

A series of pen-plotter infographics, one per neural-network architecture / learning
mechanism. Each maps the *phenomenon* of the architecture (not its box-and-wire
diagram) to line-native geometry a mechanical arm can draw. One `.md` brief per net
lives here; drop reference images beside them (e.g. `references/<net>/`).

## Shared conventions (read before building any piece)

**Medium.** Real pen plotter → **lines only**. No gradients, no fills, no shading.
"Solid" = line-fill (hatching / serpentine / spiral / dense wireframe). Tone comes
from **line density** and **hidden-line occlusion**, never from grey.

**Palette (colour = meaning, never decoration).**
- `black` — structure, the surface/terrain itself, type, furniture.
- `red` (crimson) — the active/query/trace element (the thing being followed).
- `blue` (dodgerblue) — the second perspective (keys, K).
- `green` (forest) — content / values (V).
- The paper is the "fourth colour": warm cream, left bare for voids.
Most pieces are black+red; transformer uses 4 pens. Best plotted multi-pen.

**Format.** Vertical or flow composition; spaced-caps title top-left; monospaced
math annotations floating in negative space; numbered stages; one HUGE focal form;
asymmetry + shaped negative space (see `../DESIGN_RUBRIC.md`, `../STYLES.md`).

**The 3D pen-plotter engine (in `../bauhaus.py`).** These pieces share a from-scratch
mini-renderer — do not re-invent it:
- `_zbuf_terrain(out, SX, SY, DEP, feed, PENV=..., pen=...)` — draws a 3D wireframe
  surface with a numpy **z-buffer for true hidden-line occlusion** (near ridges hide
  far mesh → the surface reads solid, not transparent). `SX/SY/DEP` are `(R+1,C+1)`
  numpy arrays of screen coords + view-depth (larger = nearer); `PENV` = optional
  per-vertex pen index for colour.
- Build `SX/SY/DEP` with an **isometric `proj(wx, wy, wz)`** and a `dep()` (front =
  nearer). Height field `wy = f(wx, wz)` is where each architecture differs.
- `_marching_squares` + `_chain_segments` → contour isohypses (softmax, probability).
- `_catmull_subdivide` → smooth wireframes; `_poly`, `_dot`, `type_block`,
  `_stroke_text`, `fill_disc`, `circle` → marks, nodes, type.

**Determinism.** Every piece is a seeded **composition** (registered in
`../registry.py` `GENERATOR_REGISTRY` + `COMPOSITIONS`): all randomness flows through
the passed `SeededRNG`; the seed only fine-tunes. `promptplot art <name> --seed N`.

## The series

| Net | Piece | Essence | Status |
|---|---|---|---|
| MLP | `bauhaus_manifold` | activation folds space (points identified through a fold) | built (3D engine) |
| CNN | `bauhaus_locality` | from pixels to meaning: stacked feature terrains | built (3D engine) |
| LSTM | `bauhaus_memory` | memory in time: precessing figure-8 helix | built |
| Transformer | `bauhaus_relevance` | attention as topography (QKᵀ→softmax→V→O) | built (3D engine) |
| GAN | — | adversarial minimax duel of two surfaces | to build → `gan.md` |
| Diffusion | — | entropy forward / score-based reversal | to build → `diffusion.md` |
| VAE | — | probabilistic bottleneck (hourglass funnel) | to build → `vae.md` |
| GNN | — | message passing over a constellation | to build → `gnn.md` |
| MoE | — | sparse routing / branching sluice | to build → `moe.md` |
| SSM / Mamba | — | continuous helix, discretely sliced | to build → `ssm-mamba.md` |
| Flow Matching | — | phase-space vector field warp | to build → `flow-matching.md` |
| ViT | — | patch partitioning → token sequence | to build → `vit.md` |
| DINO | — | teacher–student distillation, anti-collapse | to build → `dino.md` |
| RL (Actor-Critic) | — | policy field over a value landscape | to build → `rl-actor-critic.md` |

Each brief: **essence → pen-plotter visual (engine) → palette → annotations →
reference prompt → build notes**. The reference prompt is for generating a reference
plate (AI image) to aim at; the build notes are for the deterministic generator.
