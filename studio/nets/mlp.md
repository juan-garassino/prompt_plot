# MLP — NONLINEAR TRANSFORMATION
**Essence:** a network sculpts the coordinate space its data lives in — linear
transforms stretch/shear/rotate (they cannot bend), the **nonlinear activation
FOLDS** the space so distant points are brought together and tangled points torn
apart. **Status:** built as `bauhaus_manifold` (3D engine).

## The idea (the true thing)
Input plane (top, rigid grid) → matrix multiply projects/stretches it → activation
**folds** the high-dimensional sheet (origami of space; different input points map
to the same output cardinal) → linear projection resolves it back to a flat output
plane, permanently reorganised by the fold. "Same tokens, different geometry."

## Pen-plotter visual (our engine)
- A parametric **petal-saddle / folded manifold** in the middle, rendered with
  `_zbuf_terrain` (hidden-line so near petals hide far ones → a solid fold).
- **INPUT plane** (top) and **OUTPUT plane** (bottom): isometric dot-lattices +
  frame + vertical droplines through the ambient volume.
- **Streamlines** falling from the input plane, twisting through the central fold,
  opening onto the output plane; a few in **red** to trace specific trajectories.
- Right brackets: `LINEAR TRANSFORM / NONLINEAR ACTIVATION / LINEAR TRANSFORM`.

## Palette
black = surface/streamlines/planes; red = traced particle trajectories + fold
ridge. (Optional: one red cluster followed through the fold.) Cream paper.

## Annotations
`NONLINEAR TRANSFORMATION`, `SAME TOKENS · DIFFERENT GEOMETRY · A RICHER SPACE`,
`INPUT SPACE x∈Rⁿ`, `OUTPUT SPACE y∈Rᵐ`.

## Build notes
`bauhaus_manifold`: isometric `proj` + `dep`; height `wy = petal-saddle(r,θ)`;
z-buffer occlusion; streamlines funnel to a ring (not a point) then out. Honest
scope: strong 3D fold, not a 1:1 clone of a rendered-surface illustration.
Alt spec on file (studio origami-fold): a literal ReLU crease reflecting one
half-space onto the other (`F(p)=p−2·max(0,−d)·n`).
