# CNN — FROM PIXELS TO MEANING
**Essence:** hierarchical feature extraction — a network distils raw pixels into
meaning by stacking increasingly abstract feature maps. **Status:** built as
`bauhaus_locality` (3D engine); being pushed further by the studio agents.

## The idea (the true thing)
Each layer is a *feature-map terrain*. Low layers hold fine, busy detail (points,
gradients); higher layers hold fewer, taller, smoother forms (edges → textures →
objects). Spatial resolution DECREASES as abstraction INCREASES. A single input
patch's influence widens up the stack (the growing receptive field) — a "data
trace" of compression + abstraction.

## Pen-plotter visual (our engine)
- A vertical stack of 4–5 **isometric wireframe terrains**, each rendered with
  `_zbuf_terrain` (hidden-line occlusion → solid surfaces, not transparent mesh).
- Height field per layer varies: bottom ≈ flat fine grid (PIXELS), then small
  bumps (LOW), rounded hills (MID), few big peaks (HIGH); the tallest HIGH peak
  drawn in **red**.
- A **red receptive-field window** on each layer, connected up a dashed red column
  (the patch widening/abstracting through depth).
- Left double-arrow: `MORE ABSTRACTION` ↑ / `SPATIAL RESOLUTION` ↓. Right labels
  `PIXELS / LOW-LEVEL / MID-LEVEL / HIGH-LEVEL`. Top: `FROM PIXELS TO MEANING`.
- Bottom mini-diagram: receptive field shrinking grid → window → single cell.

## Palette
black = terrain/mesh; red = the tallest peak + the receptive-field trace. Cream paper.

## Annotations
`FROM PIXELS TO MEANING`, `MORE ABSTRACTION`, `DECREASING RESOLUTION`, layer names.

## Build notes
`bauhaus_locality`: `freqs`/`amps` per layer set the abstraction gradient; `proj`
oblique + `dep = -v + 0.2*z`; `PENV` reddens the top peak; window via `_poly`
squares; a shared `_zbuf_terrain` call per layer. Keep it seeded + in-bounds.
