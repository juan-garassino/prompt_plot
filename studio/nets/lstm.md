# LSTM — MEMORY IN TIME
**Essence:** recursive memory — the cell state loops every step but takes a
*different path each iteration* because of the transformation it underwent (a
helix / logarithmic spiral). **Status:** built as `bauhaus_memory`; studio agents
pushing the ultimate version.

## The idea (the true thing)
The recurrence is a loop, not a chain. Draw time as slightly offset, precessing
curves forming a figure-8: each pass is one time step, landing rotated/rescaled —
a log-spiral of iterations. Two rounded lobes meet at a hollow **LATENT** waist:
**REMEMBER** (c_t) above, **FORGET** (c_{t-1}) below. The central line carries
three connected points: **INPUT** (bottom) → **LATENT** (waist) → **OUTPUT** (top).
Forget/input/output **gates** are red lateral attractors that warp the pathways
(gates multiplicatively scale the flow).

## Pen-plotter visual (our engine)
- ~40 continuous **precessing figure-8 loops** (each lobe a rounded circle through
  the waist), scale + phase drifting per loop → the helix/spiral read.
- Vertical axis INPUT→OUTPUT with arrowheads; three nodes (INPUT solid, LATENT
  hollow-red, OUTPUT solid); REMEMBER / FORGET lobe labels.
- **Gate leaders** (dashed) to red dots labelled OUTPUT/INPUT/FORGET GATE, the
  loops bending toward them.
- Faint background **orbit ellipses** + scattered **starfield** dots.

## Palette
black = cell-state loops/structure; red = gates + the one traced iteration + the
hollow latent node. Cream paper.

## Annotations
`MEMORY IN TIME`, `INFORMATION LOOPS`, gate names, `C T` / `C T-1`.

## Build notes
`bauhaus_memory`: two-circle figure-8 per loop, monotonic `precess` (swept helix),
slight `grow` (log-spiral); nodes at lobe apexes + waist; gate leaders via `_dot`
+ dashed `_poly`. Not a rolled-cell σ/tanh box diagram. Seeded jitter only.
