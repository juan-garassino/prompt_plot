# DIFFUSION (DDPM) — ENTROPY & SCORE-BASED REVERSAL
**Essence:** forward process destroys structure into Gaussian noise; the learned
reverse process (the score function) pulls noise back into data.
**Status:** to build.

## The idea
A stack of aligned planes over time t=0…T. Bottom (t=0) = a sharp data-manifold
terrain; upward it fractures → dissolves → a flat plane of uniform noise dots
(Gaussian prior). Red streamlines (the score `∇_x log p_t(x)`) flow DOWNWARD,
reversing entropy to reconstruct the terrain.

## Pen-plotter visual (our engine)
- 4–5 stacked isometric planes (like the CNN/transformer stack) via `_zbuf_terrain`
  for the terrain planes; upper planes drawn as dashes/broken contours dissolving
  to a `_dot` noise field at the top.
- **Red** curved streamlines threading top→bottom with arrowheads = reverse drift.

## Palette
black = terrain/contours/noise dots; red = score-function streamlines.

## Annotations
`q(x_t|x_{t-1}) FORWARD NOISE`, `p_θ(x_{t-1}|x_t) REVERSE DRIFT`,
`∇_x log p_t(x)`, `DATA MANIFOLD … GAUSSIAN PRIOR`.

## Reference prompt
Mechanical pen plotter, warm cream paper. Vertical: five stacked aligned isometric
grid planes, t=0→T. Bottom (t=0 "DATA MANIFOLD"): intricate sharp 3D wireframe
mountains in dense black contours. Next: peaks fracture, lines become dashes.
Next: terrain disintegrates into a high-entropy cloud of points/broken contours.
Top (t=T "GAUSSIAN PRIOR"): flat grid of evenly stippled noise dots. Threading the
stack: red vector streamlines "SCORE ∇_x log p_t(x)" with arrows pulling noise
downward to reconstruct the terrain. Stippling + line art, no gradients.
Annotations `q(x_t|x_{t-1}) FORWARD`, `p_θ(x_{t-1}|x_t) REVERSE`.

## Build notes
Same stack machinery as `bauhaus_relevance`; per-plane "dissolve" = drop mesh
segments by a t-dependent probability + convert to dashes; noise via `_dot`.
Score streamlines = red `_poly` curves through the planes. Pairs conceptually with
Flow Matching. (Juan flagged diffusion as a likely next piece.)
