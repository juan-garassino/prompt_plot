# DINO — TEACHER–STUDENT DISTILLATION
**Essence:** self-supervised learning — a Student chases an EMA Teacher, stabilised
by centering to avoid representation collapse. **Status:** to build.

## The idea
Twin parallel manifolds with a dynamic shadow: a rigid Teacher plane projects an
evolving target boundary DOWN onto a flexible Student surface; a central centering
sphere pushes outward to stop the Student collapsing to a point. EMA + stop-grad.

## Pen-plotter visual (our engine)
- Two parallel wireframe planes: **TEACHER** (top, thick rigid black lines) casting
  red projection lines down onto a finer, slightly warped **STUDENT** plane.
- A central geometric **centering sphere** (stipple/crosshatch) with red outward
  force vectors = anti-collapse.
- Line-weight = power: 0.8mm teacher, 0.2mm student.

## Palette
black = both planes + sphere; red = teacher→student projection + centering force.

## Annotations
`EXPONENTIAL MOVING AVERAGE (EMA)`, `STOP-GRADIENT`, `AVOID COLLAPSE`.

## Reference prompt
Two-color mechanical pen plotter, warm cream paper, vertical. Twin parallel
wireframe planes: top `TEACHER` in thick rigid black lines casts downward red
projection lines onto a slightly morphed adaptive bottom `STUDENT` plane in finer
black lines. A central geometric sphere `CENTERING` between them pushes outward with
red vector force lines to prevent the bottom plane collapsing to a point. Weights
0.8mm teacher / 0.2mm student; sphere in dense crosshatch. Annotations `EMA`,
`STOP-GRADIENT`, `REPRESENTATION COLLAPSE AVOIDANCE`. No gradients.

## Build notes
Bespoke: two `_zbuf_terrain` planes (teacher flat/rigid, student gently warped);
sphere = `fill_disc`/crosshatch; projection + force lines red `_poly`. Relates to
`005-products/024-dino`.
