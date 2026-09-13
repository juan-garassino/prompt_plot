# MoE — SPARSE ROUTING (MIXTURE OF EXPERTS)
**Essence:** conditional computation — a gating network sparsely routes each token
to a few specialised experts. **Status:** to build.

## The idea
A dense token stream hits a routing gate and SHATTERS into a few sparse paths that
activate only selected expert sub-networks; the rest stay dark. `Σ G(x)_i E_i(x)`.

## Pen-plotter visual (our engine)
- A dense column of vertical **black** lines (input tokens) cascading down onto a
  rigid angled `ROUTING GATE` plane.
- On impact the stream **shatters** into a few sparse **red** trajectories dropping
  into isolated wireframe cubes (`EXPERTS`) — some densely inked, some empty.

## Palette
black = input stream + expert cubes; red = the sparse routed paths; cream paper.

## Annotations
`Σ G(x)_i E_i(x)`, `SPARSE ACTIVATION`, `GATE ROUTING`.

## Reference prompt
Mechanical pen plotter, warm cream paper, vertical, kinetic fracture. A dense
uniform stream of vertical black lines (Input Tokens) cascades down and strikes a
rigid angled geometric `ROUTING GATE` plane; on impact it shatters into sparse
distinct red trajectories dropping into four isolated isometric wireframe cubes
`EXPERTS` — some receive dense flow, others stay empty. Heavy 0.5mm input vs
razor 0.1mm red routes; plotter jitter at the gate. Annotations `Σ G(x)_i E_i(x)`,
`SPARSE ACTIVATION`. No fills/gradients.

## Build notes
Bespoke: token lines as `_poly`; gate plane as an oblique quad; routed paths as
red `_poly` from gate to expert cubes (small `_zbuf` wireframe cubes or plain
iso boxes). Sparsity = only k of N experts inked.
