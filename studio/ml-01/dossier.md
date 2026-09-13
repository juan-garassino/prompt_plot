# ml-01 — The forward pass: a network bends space

**Field expert:** ML research · **Date:** 2026-09-13 · **Status:** dossier v1
(replaces the rejected circles-and-wires MLP schematic)

**Topic selection.** Curator's hypothesis accepted, with one word sharpened. The
visually TRUE thing about a forward pass is that a network **warps its input
space**: a regular grid pushed through successive learned layers is bent and
stretched until the classes become linearly separable (Olah, "Neural Networks,
Manifolds, and Topology", colah.github.io, 2014). The sharpening: our instance
uses tanh layers with invertible weight matrices, and such layers are
**homeomorphisms** — they bend and stretch the plane but never tear, glue, or
overlap it. "Folding" (non-injective collapse) is ReLU's move, not this
network's; the caption must say *bends*, not *folds*. The circles-and-wires
picture failed DESIGN_RUBRIC dimension 6 on principle: it drew the apparatus.
This piece draws the phenomenon — what the machine does to space.

---

## 1. The phenomenon (≤5 lines)

A trained network classifies two interleaved crescents ("two moons") that no
straight line can separate. Each layer applies one learned move,
h = tanh(Wx + b): a linear stretch-and-rotate followed by a smooth squash into
the (−1,1) box. Three such moves deform the entire plane until the two
crescents sit in opposite corners — and the final layer, which is nothing but a
fixed straight line, separates them trivially. The intelligence is not in the
cut; it is in the bending that made the cut sufficient.

### Governing math

- **Layer map** (row-vector convention): h₀ = x,
  **h_k = tanh(h_{k−1} W_k + b_k)**, k = 1..3, all widths 2 — so every hidden
  space is itself a 2D plane, drawable with **zero projection**.
- **Readout**: logit(x) = h₃ · w_out + b_out; class = [logit > 0]. The decision
  boundary in the final hidden space is *exactly* the straight line
  w_out·h + b_out = 0. In input space it is the preimage — a curve.
- **Homeomorphism guarantee**: tanh is a strictly monotone bijection ℝ→(−1,1)
  applied per coordinate; if det W_k ≠ 0 the composite layer is injective and
  smooth with smooth inverse on its image. The drawn mesh can never
  self-intersect; an overlapping mesh is a rendering bug, not the math.
- **Local area change** (the drawable "gravity" of the warp): the Jacobian of
  layer k at x is J_k = W_k · diag(1 − h_k²), so
  **det J(x) = Π_k det(W_k) · Π_i (1 − h²_{k,i}(x))** — computable in closed
  form at every grid vertex. |det J| < 1 means the plane is locally crushed;
  |det J| > 1 means it is stretched. Sign flips = orientation reversal
  (mirror), which several of these layers do.

### Exact recipe (verified by running it, 2026-09-13 — all numpy, offline)

Reject the repo's Keras transformer checkpoint for this piece (§3 for why) and
**really train** a tiny MLP from scratch. Everything below is deterministic
given the seed; total compute < 1 s.

1. **Data — two moons, analytic** (the standard sklearn construction,
   reimplemented in ~6 lines so no dependency is needed): with
   t = linspace(0, π, 200): moon A = (cos t, sin t), moon B =
   (1 − cos t, 1 − sin t − 0.5). N = 400 points.
2. **RNG order matters** for reproducibility: `rng = np.random.default_rng(seed)`;
   draw (i) Gaussian noise σ = 0.08 on all 400 points in one call
   `rng.normal(0, 0.08, (400, 2))`, then (ii) weights in layer order.
   Normalize: x' = (x − 0.5)/1.5, y' = (y − 0.25)/1.5 (data then spans roughly
   [−1.1, 1.1] × [−0.55, 0.55]).
3. **Network**: 2 → 2 → 2 → 2 → 1. Hidden activation tanh, output sigmoid.
   Init: W_k ~ N(0, 1/√fan_in) via `rng.normal(0, sqrt(1/fan_in), (fan_in, fan_out))`,
   biases zero.
4. **Training**: binary cross-entropy, full-batch Adam
   (lr 0.01, β₁ = 0.9, β₂ = 0.999, ε = 1e−8), 4000 steps.
5. **Seed rule**: take the first seed ≥ 7 reaching 100% train accuracy.
   Verified: seeds 7–9 stall at 90–92%; **seed 10 is the first success**
   (acc 1.000; det W = 3.73, −13.86, 0.35, all nonzero → homeomorphism holds;
   final-space margin 1.10). Print the seed on the piece.
6. **Grid**: lines over [−1.2, 1.2] × [−0.8, 0.8] (a comfortable frame around
   the data), each line a polyline of 240 samples so curvature renders as true
   curves. Stage k mesh = the grid pushed through layers 1..k. Verified stage
   extents: stage 0 fills the frame; stages 1–3 land inside the (−1,1) tanh box
   — panels are naturally at comparable scale.
7. **Boundary**: evaluate logit on an 801×801 grid over the same frame,
   marching-squares the zero contour → one polyline in input space; push that
   polyline forward through the layers to draw it in stages 1–3. In stage 3 it
   lies exactly on the verified line **−5.243 h₁ + 4.382 h₂ + 0.001 = 0**
   (draw the pushed-forward *segment*, not the infinite line — the infinite
   line overclaims beyond the image of the drawn region).

**Verified quotables (seed 10):** class separation (min inter-class distance /
cloud span) per stage: **0.075 → 0.065 → 0.275 → 1.119** — a 15× opening, and
honestly non-monotone (layer 1 first *repositions*, slightly worsening
separation, before layers 2–3 blow it open). |det J| over the frame: median
2.5×10⁻⁸, 5th–95th percentile spanning 10⁻¹²·⁵ to 10⁻¹·⁵, max ≈ 4.0. Meaning:
the network crushes almost the entire plane into the corners; **area survives
only in a thin band along the decision boundary**, where it is stretched up to
4×. That sentence is drawable.

---

## 2. Three candidate visual truths (ranked)

### (a) The warped grid — one mesh, four stages  ★ RANK 1

The same regular grid drawn four times: input space, then after layer 1, 2, 3.
Each stage is a mesh of true curves (tanh curvature is real, not stylized),
with the two class clouds riding the mesh in two pens and the decision boundary
threading through each panel — a serpentine curve in stage 0 that is *exactly
straight* by stage 3.

**Why visually potent:** the grid makes SPACE itself the protagonist — the
viewer watches the coordinate system deform, which is precisely what a forward
pass is. The invariant (same grid) against the change (progressive warp) is the
cleanest possible visual argument, and the straightening boundary is a
narrative payoff the eye finds unaided. Every line is exact computation: mesh
vertices are forward passes, curvature is tanh, pile-up against the (−1,1) box
edges is saturation, and the mesh's refusal to ever cross itself IS Olah's
homeomorphism theorem, drawn. Nothing in the picture is decoration.

### (b) The boundary unbent — curvy cut vs. straight cut  ★ RANK 2

Two panels only, large: input space with the data and the serpentine decision
boundary weaving between the moons; final hidden space with the two clouds
crushed into opposite corners (verified: separation ratio 1.12 — clusters
tighter than the gap between them) and the boundary as one straight line.
Caption logic: *the last layer is just a ruler; the depth did the bending.*

**Why visually potent:** maximum drama per line of ink — one curve becomes
straight, two tangled crescents become two far points. Huge negative space,
gallery-simple. Weakness: without the grid, the *mechanism* (space warping) is
implied rather than shown; the viewer sees before/after, not the medium that
deformed. Best used as the hero framing if (a)'s four panels overload A4.

### (c) The migration — 400 points crossing the layers  ★ RANK 3

Every data point plotted at its position in stages 0..3 (panels side by side),
with faint **dashed correspondence lines** linking each point's successive
positions; two pens for the two classes, converging from interleaved crescents
to two opposite-corner clusters. The quantitative arc is real: separation
0.075 → 0.065 → 0.275 → 1.12, including the honest layer-1 dip.

**Why visually potent:** it reads as migration — populations disentangling —
and dot-and-dash is native plotter vocabulary. **Mandatory honesty caveat:** an
MLP has no continuous trajectory between layers; the map is discrete. The
connecting dashes are correspondence annotation, not a path the computation
travels. They must be drawn as annotation (dashed, faint, clearly subordinate)
— solid smooth "flow" trajectories would depict a dynamical system this network
is not (that drawing belongs to a Neural-ODE piece, a different dossier).

---

## 3. Real data / source — and why not the transformer checkpoint

House rule is "real data or exact math." This piece satisfies it with **exact
math plus a genuinely trained network**: the MLP above is really trained, the
full procedure is pinned (seed, RNG draw order, init, optimizer, steps), and
any critic can re-derive every line in under a second with numpy alone. Nothing
is faked, nothing is illustrative-only.

The available real checkpoint —
`/Users/juan-garassino/Code/005-products/027-ml-workspace/welllog-prediction/out/ckpt_base.keras`
(readable via zipfile+h5py, see `_load_qkv` in `promptplot/generative/bauhaus.py`)
— is **rejected for this piece**, for three reasons:

1. **No honest 2D input space.** Its inputs are windows of 1D well-log
   sequences embedded in d_model dimensions. There is no plane to grid; any 2D
   grid pushed through it would be a fiction, and any projection of the
   high-dimensional warp would mix projection artifacts with true deformation —
   the drawing could not distinguish them.
2. **Unverifiable forward pass offline.** Recomputing a transformer forward
   pass faithfully from raw h5 arrays means reimplementing attention, layer
   norm, and positional encodings exactly; a silent mismatch would be an
   undetectable lie in ink. The MLP forward pass is four lines of numpy.
3. **Series economy.** That checkpoint's Q/K/V already carry the
   `bauhaus_weights` Hinton piece; reusing it flattens the collection.

Reference for the concept (not data): C. Olah, "Neural Networks, Manifolds,
and Topology" (2014) — the tanh-layers-are-homeomorphisms argument and the
topology-of-separability framing used throughout this dossier.

---

## 4. Simplifications allowed vs. lies

**Allowed (honest, declare on the piece where noted):**

- **tanh instead of ReLU.** Not a lie: the drawn network genuinely uses tanh,
  tanh is a real, historically central activation, and the smooth curves in the
  mesh are its true geometry. It is also the honest choice for the *theorem*
  the piece embodies (homeomorphism needs invertible activations). Declare the
  architecture in the caption ("3 tanh layers, width 2").
- **Width-2 hidden layers.** The flagship honesty decision: every hidden space
  is literally 2D, so the piece needs **no projection at all**. Nothing is
  reduced, rotated, or approximated to get to paper.
- **Per-panel uniform isotropic rescale** to a common drawable frame (like the
  astro dossier's uniform strain-axis scale). Verified barely needed — stages
  1–3 already live in (−1,1)² — but if applied, it must be one scalar per
  panel. Anisotropic rescale is forbidden: the anisotropic stretching IS the
  phenomenon.
- **Log-scaling and clipping |det J|** for any density channel. The true
  dynamic range is ~10¹⁵ — unplottable; use log₁₀|det J| clipped to the
  verified 5th–95th percentile band [−12.5, −1.5]. Declare "density ∝
  log |det J|".
- **Decimating mesh lines below the 0.8 mm spacing floor** in saturated zones
  (a resolution limit, same class as resampling below pen width), *or* letting
  the pile-up print as controlled double-pass darkening — the pile-up is
  saturation itself, so denser ink where |det J| → 0 is truthful by default.
- **Seed selection by the stated first-success rule**, seed printed on the
  piece. Selection with a declared rule is reproducibility; selection without
  one is cherry-picking.

**Lies (forbidden):**

- **A smooth morph between stages presented as computation.** The forward pass
  is three discrete maps; there is no in-between space. Interpolated
  intermediate meshes, or solid flowing trajectories in truth (c), depict a
  continuous dynamics this network does not have.
- **A mesh that crosses or overlaps itself.** det W_k ≠ 0 (verified) makes
  every layer injective. Apparent fold-overs would be a bug drawn as fact —
  and would falsely depict ReLU-style folding. Symmetrically: calling the tanh
  warp "folding" in the caption. Bends, stretches, mirrors — never folds.
- **Beautifying the mesh** — smoothing curvature, regularizing cell sizes,
  taming the corner pile-up. The crush into the corners (median |det J|
  2.5×10⁻⁸) is the network's actual behavior.
- **Drawing an untrained (or different-seed) network and captioning it as the
  trained one**, or hiding the layer-1 separation dip in truth (c) by
  reordering panels.
- **Extending the final straight boundary beyond the pushed-forward segment.**
  The line −5.243 h₁ + 4.382 h₂ + 0.001 = 0 is the boundary only within the
  image of the drawn region.
- **Non-uniform panel distortion** (stretching one axis, log-warping a panel)
  without explicit labeling — same rule as the astro dossier's axis clause.
- **PCA projection, if anyone widens the network later.** Honest only if
  declared on the piece *and* with the caveat that each layer gets its own
  principal axes, so panel-to-panel motion confounds true warping with
  projection change. Width 2 was chosen precisely to delete this caveat;
  do not reintroduce it casually.

---

## 5. The misconception to quietly correct

**"A neural network computes like a flowchart"** — signals hopping between
neuron-circles along wire-arrows, the picture the rejected piece drew. That
picture shows the *apparatus* (the plumbing numbers flow through) and says
nothing about what the computation *is*. The truth: a network is a **learned
deformation of space**. Each layer bends the entire input plane a little; depth
composes small bends into a warp that makes the answer geometrically trivial.
Two quiet corollaries the piece should land: (1) *the output layer is not where
the thinking happens* — it is a fixed straight cut, dumb as a ruler; every bit
of learned intelligence is in the bending that preceded it; (2) *the network
never teleports or tears the data* — classes are steered apart by a continuous
deformation (verified homeomorphism), which is why the interleaved crescents
must swing around each other rather than simply swap sides. The viewer should
leave thinking "it bends space until a straight line is enough," not "data
flows through circles."

---

## 6. Pen-plotter fit

This phenomenon is native line work: a warped mesh is nothing but polylines,
and the plotter's one true gradient — line density — happens to be the exact
mathematical quantity the warp produces. Where |det J| → 0 the mesh lines
genuinely converge, so contraction prints itself as darkness with zero encoding
artifice (cap physical ink with the existing `--max-ink` machinery; floor
spacing at 0.8 mm per the fabrication gate). Scale check for truth (a) on A4
landscape (~267 mm drawable): four panels ≈ 60 mm wide; a 17×13-line grid gives
~3.5 mm nominal cell pitch, so even 4× contraction stays at the plottable
floor, and each line at 240 samples renders tanh curvature as smooth true
curves. Pen budget ≤ 4 with meaning: one pen = space (the mesh), two pens = the
two classes, one scarce accent pen = the decision boundary — one continuous
polyline per panel, the only element that changes character (serpentine →
straight), so the loudest pen carries the punchline. No fills; the only
double-pass ink is the truthful saturation pile-up at the (−1,1) box edges.
