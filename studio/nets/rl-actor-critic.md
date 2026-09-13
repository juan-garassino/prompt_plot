# RL (ACTOR-CRITIC) — THE FEEDBACK LOOP
**Essence:** an agent improves a policy against a value estimate, navigating a
reward landscape via exploration/exploitation. **Status:** to build.

## The idea
A closed dynamical loop over a reward landscape: the **Critic** is an elevation map
of expected value; the **Actor** is a vector field of directional streamlines
curving up toward optima; a reward feedback line loops back from the environment.

## Pen-plotter visual (our engine)
- Base: a 3D topographical **value terrain** (`_zbuf_terrain`) = the Critic V(s).
- Hovering above: a field of curved **red** directional arrows (the Actor's policy)
  flowing up the steepest gradients toward the peaks.
- A single heavy black **feedback loop** from the output peaks back to the start.

## Palette
black = value terrain + feedback loop; red = policy vector field; cream paper.

## Annotations
`π_θ(a|s) POLICY`, `V_π(s) VALUE`, `ADVANTAGE FUNCTION`.

## Reference prompt
Mechanical pen plotter, warm cream paper. Base: a complex 3D topographical
wireframe mountain range in black ink (the `CRITIC` value function). Hovering just
above like a magnetic field: a dense layer of curved red directional vector arrows
(the `ACTOR` policy) flowing up the steepest gradients toward the highest peaks. A
single heavy black line loops from the output peaks back to the base plane
(environment feedback loop). Contours not shading; red arrows razor 0.1mm.
Annotations `π_θ(a|s)`, `V_π(s)`, `ADVANTAGE`. No fills/gradients.

## Build notes
Bespoke: value terrain via `_zbuf_terrain`; policy arrows = red `_poly` along the
gradient of the height field (ascent streamlines); feedback = one black spline loop.
Relates to `005-products/018/019` RL projects.
