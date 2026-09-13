# TRANSFORMER — ATTENTION AS TOPOGRAPHY
**Essence:** attention is a topographical mapping — Queries and Keys collide to
raise a similarity landscape, softmax turns it into a probability distribution,
and Values are reshaped by the gravity of that context. **Status:** built as
`bauhaus_relevance` (3D engine); studio agents pushing the ultimate version.

## The idea (the true thing)
- **Q** (red) flows in from the LEFT ("what do I need?"); **K** (blue) cascades
  from the TOP ("what do I hold?"). Where their paths intersect, the dot product
  raises a **QKᵀ peak** — high mountain = strong resonance, flat plain = unrelated.
  Q and K MERGE into one landscape (red + blue).
- **Softmax** smooths/sharpens the raw terrain into a probability distribution,
  drawn as concentric **contour rings** (density = probability).
- **V** (green) is a separate semantic terrain (the content to retrieve).
- **O = AV**: the attention peaks act as a topographical mask, pulling V's terrain
  upward at high-probability locations — content reshaped by context.

## Pen-plotter visual (our engine)
- Vertical stack (or #98 flow): canvas grid → QKᵀ cones → softmax contours → V
  (green) → O. Each terrain via `_zbuf_terrain`; contours via `_marching_squares`.
- **Arrows parallel to the isometric grid axes** (Q along +X, K along −Y).
- Droplines tie the query·key anchors through every stage.

## Palette
black = grids/structure/contours; **red = Q**; **blue = K**; **green = V**; O tints
its pulled-up peaks. Best plotted with 4 pens on cream.

## Annotations
`ATTENTION AS TOPOGRAPHY`, `S = QKᵀ/√d`, `A = softmax(S)`, `O = AV`,
`Q QUERIES / K KEYS / VALUES V`.

## Build notes
`bauhaus_relevance`: shared `proj/dep`; QKᵀ = sharp cones at 3 query·key anchors
(fine jagged floor) with `PENV` red/blue merge; softmax = contour isohypses of a
smoothed field; V green terrain; O = V + attention peaks. Consider the #98 flow
layout (K top / Q left / merge centre / V green / O) as the next iteration.
