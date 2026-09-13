# VAE — THE PROBABILISTIC BOTTLENECK
**Essence:** encode inputs into a continuous Gaussian latent, then decode back —
an hourglass funnel through a probabilistic core. **Status:** to build.

## The idea
Encoder funnel collapses a high-dim wireframe inward to a dense elliptical latent
point-cloud (μ,σ); the reparameterization trick samples `z=μ+σ⊙ε`; the decoder
funnel expands back out to a reconstructed terrain.

## Pen-plotter visual (our engine)
- Two opposing wireframe **funnels** (encoder left/top, decoder right/bottom) via
  `_zbuf_terrain` or ruled cones (see `bauhaus_manifold`'s hyperboloid rulings).
- A central **elliptical latent point-cloud** (`_dot` stipple in an ellipse).
- **Red** vector lines darting through the bottleneck = reparameterization.

## Palette
black = funnels/reconstruction; red = reparameterization vectors; cream paper.

## Annotations
`z = μ + σ⊙ε`, `N(0,I)`, `LATENT BOTTLENECK`.

## Reference prompt
Two-color mechanical pen plotter, textured cream paper. Horizontal: two opposing
3D wireframe funnels (Encoder left, Decoder right). Left grid collapses inward,
compressing into a central dense elliptical point-cloud (latent bottleneck). From
that noise core the right grid expands outward, reconstructing topography. Red
vector lines denote the reparameterization trick mapping from the central cloud
into the expanding decoder grid. Variable weights 0.1–0.5mm, crisp contour
hatching, pure line art. Annotations `z=μ+σ⊙ε`, `N(0,I)`, `LATENT BOTTLENECK`.
No gradients/fills.

## Build notes
The hourglass rulings already exist in the old `bauhaus_manifold` history (ruled
hyperboloid) — reuse as the funnels; latent = ellipse `_dot` cloud; reparam =
red `_poly` darts. Horizontal composition.
