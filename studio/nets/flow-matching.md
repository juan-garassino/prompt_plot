# FLOW MATCHING / CONTINUOUS NORMALIZING FLOWS — THE PHASE SPACE
**Essence:** push a simple base distribution along a learned vector-field ODE into
a complex target distribution. **Status:** to build.

## The idea
A serene base shape (a circle) on the left is swept by a dense field of curved
streamlines (the ODE flow field) that shear/stretch/warp it into a complex
multi-modal target on the right. `dz/dt = v_θ(z,t)`.

## Pen-plotter visual (our engine)
- Left: a clean wireframe **circle** (base distribution).
- A dense field of parallel, curving **black + red** streamlines (the vector field)
  progressively warping it rightward into an asymmetric multi-modal boundary.
- Red = a few outlier trajectories stretched to the extremes.

## Palette
black = flow field + base/target; red = highlighted outlier trajectories; cream.

## Annotations
`dz/dt = v_θ(z,t)`, `VECTOR FIELD`, `BASE → TARGET`, `PHASE SPACE`.

## Reference prompt
Mechanical pen plotter, warm cream paper, horizontal, kinetic. Far left: a serene
wireframe circle (Base Distribution). Flowing right: a massive dense field of
parallel curving black-and-red streamlines (ODE flow field) that shear, stretch,
warp the circle into a complex asymmetric multi-modal boundary on the right.
Thousands of non-intersecting curved lines; red highlights outlier trajectories.
Annotations `dz/dt=v_θ(z,t)`, `PHASE SPACE TRANSFORMATION`. Pure line art, high
tension curves, no gradients/fills.

## Build notes
Bespoke: seed a streamline field (reuse `flow_field` spacing ideas from
`generators.py`); integrate each streamline under an analytic warping field; base
circle + warped target via the endpoints. Horizontal composition.
