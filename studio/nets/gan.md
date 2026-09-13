# GAN — THE ADVERSARIAL MINIMAX DUEL
**Essence:** two networks in tension — a Generator sculpting fakes upward and a
Discriminator judging them downward, meeting at a decision boundary.
**Status:** to build.

## The idea
`min_G max_D V(D,G)`. Generator turns latent noise into a synthesised terrain;
Discriminator is an inverted surface testing output against real data. They meet
at a central zero-plane (the decision boundary); gradients arc back as tension.

## Pen-plotter visual (our engine)
- Two opposing `_zbuf_terrain` surfaces: bottom = Generator terrain extruding
  UPWARD from a stippled latent grid; top = Discriminator surface hanging DOWN,
  a rigid grid vs a `REAL DATA` reference plane.
- They meet at a horizontal `DECISION BOUNDARY` zero-plane.
- **Red** tensioned vector lines/arrows arc vertically between them = gradient
  backprop / minimax equilibrium.

## Palette
black = both surfaces + reference plane; red = the adversarial gradient tension.

## Annotations
`min_G max_D V(D,G)`, `LATENT z∼p_z`, `REAL x∼p_data`, `EQUILIBRIUM PLANE`.

## Reference prompt (for a reference plate)
Two-color mechanical pen plotter, warm cream drafting paper. Strict vertical
isometric, two opposing forces. Bottom "LATENT NOISE → SYNTHESIS (GENERATOR)": a
flat grid of stippled points collapsing/extruding up into an emerging 3D wireframe
terrain of black isolines. Top "EVALUATION MANIFOLD (DISCRIMINATOR)": an inverted
concave wireframe grid testing output against a REAL DATA plane. Center: the two
surfaces meet at a horizontal zero-plane "DECISION BOUNDARY"; fine red vector lines
+ arrows arc between them (gradient backprop, minimax tension). Variable weights
0.1–0.5mm, no gradients/fills. Annotations `min_G max_D V(D,G)`, `LATENT z∼p_z`,
`REAL x∼p_data`, `EQUILIBRIUM PLANE`.

## Build notes
Reuse `_zbuf_terrain` twice (one flipped in depth). Latent = `_dot` stipple grid.
Tension arcs = red `_poly` splines between matched surface points.
