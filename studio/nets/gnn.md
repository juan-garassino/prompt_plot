# GNN — MESSAGE PASSING
**Essence:** learning on non-Euclidean structure — nodes aggregate features from
their neighbours across an irregular graph. **Status:** to build.

## The idea
Unlike the rigid grids of CNNs, a GNN lives on an organic constellation. Each node
updates by aggregating messages from its neighbourhood; repeated hops spread
information. Show the graph + radial aggregation ripples + directional message flow.

## Pen-plotter visual (our engine)
- A **non-Euclidean constellation** of nodes joined by straight black edges
  (bespoke: seeded node positions + a proximity/knn graph via `_poly` edges).
- Select central nodes ringed by tight **red concentric rings** = neighbourhood
  aggregation; **red arrows** trace messages along edges toward those centers.
- Variable line weight (thin distant edges, heavy central nodes).

## Palette
black = graph web + nodes; red = aggregation rings + message arrows; cream paper.

## Annotations
`h_v^(k) = UPDATE(h_v^(k-1), AGG({h_u : u∈N(v)}))`, `MESSAGE PASSING`,
`NEIGHBORHOOD HOPS`.

## Reference prompt
Mechanical pen plotter, warm cream paper. A beautifully chaotic non-Euclidean
constellation of geometric nodes joined by straight high-tension black ink edges
(like a stellar/molecular web). Select central nodes surrounded by tight concentric
red rings (radial feature aggregation); fine red arrows trace message-passing flow
along edges toward the aggregated centers. Weights 0.1–0.5mm; ink pooling at
vertices. Annotations `h_v^(k)=UPDATE(...,AGGREGATE)`, `MESSAGE PASSING`. No
shading/gradients.

## Build notes
Bespoke: seeded 2D node cloud (`rng`), edges by distance threshold; `circle`/
`dotted_circle` for aggregation rings; red arrow heads via `_poly`. No terrain
engine needed — this is the graph counterpoint to the grid pieces.
