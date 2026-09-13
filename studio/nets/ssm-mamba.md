# SSM / MAMBA — CONTINUOUS TO DISCRETE
**Essence:** a continuous-time linear dynamical system, selectively scanned and
discretised. **Status:** to build.

## The idea
The latent state is a continuous flow (a helix/ribbon) sampled at discrete steps.
`h'(t) = A h(t) + B x(t)`, discretised into a selective scan. Contrast the smooth
analog wave with the discrete sampling planes.

## Pen-plotter visual (our engine)
- A sweeping **analog helix / spiral ribbon** in dense black contour lines (the
  continuous latent state).
- Sliced at regular intervals by flat **red** isometric planes (discretisation);
  red vector lines drop from the slices onto a lower grid = discrete outputs.

## Palette
black = continuous helix; red = discretisation planes + sampled outputs; cream.

## Annotations
`h'(t) = A h(t) + B x(t)`, `DISCRETIZATION`, `SELECTIVE SCAN`.

## Reference prompt
Mechanical pen plotter, warm cream paper. Central: a continuous sweeping analog
helix (spiral ribbon) in dense black contour lines (continuous-time latent state),
cleanly sliced at regular intervals by flat isometric red wireframe planes
(discrete time-step sampling, A/B matrices). Red vector lines project from the
intersections onto a lower flat grid mapping the continuous wave to discrete token
outputs. 0.3mm helix, 0.1mm red planes; ink soaking texture. Annotations
`h'(t)=Ah(t)+Bx(t)`, `SELECTIVE SCAN`. Zero gradients/fills.

## Build notes
Bespoke: helix = `_poly` of a 3D spiral through the iso `proj`; slice planes =
red iso quads at intervals; drop lines = red `_poly`. Reuse `bauhaus_memory`'s
spiral instinct. Pairs with Flow Matching (both continuous-dynamics pieces).
