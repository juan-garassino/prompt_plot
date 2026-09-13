# quantum-01 — dossier (FIELD EXPERT: quantum physics)

Topic chosen: **(1) double-slit with single-particle buildup** — the curator's first
preference, confirmed. It has the most visual truth of the four candidates AND the only
one whose canonical dataset is literally made of dots: Tonomura's electron-biprism
buildup. Orbitals (2) are static density maps (no story axis); tunneling (3) needs a
continuous wavefunction plot (not the plotter's grain); Bell correlations (4) are an
abstract statistic with no natural picture. This one is the plotter's home turf.

**Primary source (read in full, all numbers below verified against the paper itself):**
A. Tonomura, J. Endo, T. Matsuda, T. Kawasaki, H. Ezawa, *"Demonstration of
single-electron buildup of an interference pattern,"* Am. J. Phys. **57**(2), 117–120
(Feb 1989), doi:10.1119/1.16104. Secondary: Hitachi R&D double-slit page
(hitachi.com/rd/research/materials/quantum/doubleslit).

⚠ Provenance warning for the critic and designer: the widely reproduced frame counts
"11 / 200 / 6000 / 40000 / 140000" (Wikipedia's famous image) come from a **later
rendition of the video**, not this paper. The AJP paper's Fig. 5 caption reads
**10 / 100 / 3000 / 20 000 / 70 000**. We use the paper. Likewise Hitachi's web page
says "10 electrons per second"; the paper says ≈10³ electrons/s (beam current
1.6×10⁻¹⁶ A). We use the paper.

---

## 1. The phenomenon (≤5 lines)

A single electron is emitted, flies **alone** through a 1.5 m apparatus (the next
electron is ~150 km behind it), passes an electron biprism — one wavefront split into
two converging halves, optically a double slit — and lands on the detector as **one
localized dot**. Each dot's position is irreducibly random; its probability law is
|ψ₁+ψ₂|² ∝ cos². After 70 000 solo landings, interference fringes stand on the screen
that no individual electron could have known. The wave lives in the probability; the
particle lives in the detection.

### Governing equations

**(E1) de Broglie wavelength** (relativistic, as in the paper):

    λ = h / sqrt( 2 m₀ e V₀ (1 + e V₀ / (2 m₀ c²)) )
    V₀ = 50 000 V  →  λ = 5.4 pm  (0.054 Å)          [paper, Sec. III]

**(E2) Two-beam interference** — probability density of a detection at transverse
position x on the detector plane (biprism = two virtual coherent sources):

    P(x) = C · E(x) · cos²(π x / s)

    s  = fringe period at the detector = 1.4 mm       [paper: 0.7 µm at the image
                                                       plane, ×2000 magnification]
    E(x) = beam-overlap envelope ≈ exp(−x² / 2σ²),  σ ≈ 2.8 mm (reconstructed — see §4)
    C  = normalization;  y-coordinate ~ uniform over the panel height
    (fringes are straight bands ⊥ x)

For reference only, the textbook true-two-slit form is
I(x) ∝ cos²(π d x / λL) · sinc²(π a x / λL). **Do not plot the sinc² envelope** — the
biprism has no slit-width envelope; its envelope is the beam profile. Using sinc² here
would be a (subtle) lie.

**(E3) Fringe geometry** (why s = 1.4 mm): the two half-beams cross at full angle
2β = 7.7×10⁻⁶ rad, fringe period at the image plane s₀ = λ/2β = 0.7 µm = 7000 Å,
magnified ×2000 by two projector lenses → 1.4 mm on the ~12 mm-wide detector field
(≈8 periods across the whole field; the published Fig. 5 crop shows ≈5 periods —
the paper states 70 000 electrons ≙ 14 000 per fringe).

**(E4) Detection statistics**: successive electrons are independent draws from P(x,y).
Counts in any region after N electrons are Binomial(N, p) ≈ Poisson. Shot noise is not
an artifact to smooth — **it is the signal at low N**.

**(E5) Statistical emergence threshold** (when the eye can see fringes): with F fringe
periods in view and ~B bins resolving each period, modulation exceeds shot noise once
mean counts per bin μ = N/(F·B) satisfy μ ≳ √μ·3, i.e. μ ≳ 9. For F = 5, B = 10:
pattern statistically present at N ≈ 500, visually unmistakable at N ≈ 2000–3000 —
exactly consistent with the paper's frame (c): fringes "begin to emerge" at N = 3000.

---

## 2. Three visual truths (ranked)

### VT-1 (build this) — Accumulation: the same dots that look random ARE the fringes.
One probability law, growing sample. Panels of the **same run** at increasing N
(paper-true counts: 10 → 100 → 3000, optionally 20 000 rendered as saturation): at
N = 10 the dots defeat any pattern-search the viewer's eye can run; at N = 3000 the
fringes are undeniable. **Mandatory: panels are nested prefixes of ONE seeded sample
sequence** — the 10 dots of panel one are the first 10 dots of the final panel, exactly
as Tonomura's frames are cumulative snapshots of one exposure. *Why visually potent:*
the viewer re-enacts the physicist's inference in a single left-to-right scan — order
condenses out of noise, and no single dot "knew." Time/accumulation is the story axis;
each mark is a whole particle; only the ensemble is a wave. No annotation needed for
the punchline to land.

### VT-2 — The pattern does not care about the rate: electrons never cooperate.
Real result from the same paper: fringe contrast is identical **within 10%** for beam
intensities from 200 to 5000 electrons/s — and geometrically, successive electrons are
~150 km apart in a 1.5 m machine ("the next electron is not even produced from the
cathode till long after the preceding electron is detected"). *Why visually potent:*
two panels with equal N, drawn from the same law but labeled with rates 25× apart, are
statistically indistinguishable — the viewer hunts for a difference and fails; that
failed hunt is the physics. Also carries a brutal annotation: a 1.5 m apparatus vs a
150 km inter-electron gap on the same scale bar. Ranked 2 because its punch is an
*absence* of difference — subtler than VT-1. (I substitute this for the curator's
"fringe spacing vs slit separation": a d-sweep was never in Tonomura's experiment and
would be synthetic; rate-invariance is measured fact from the same dataset.)

### VT-3 — Which-path knowledge deletes the cross term: same electrons, no fringes.
Two panels, same N, same envelope E(x): left P ∝ E(x)·cos²(πx/s) (no path info),
right P ∝ E(x)·½ (paths distinguished — the interference cross term 2Re(ψ₁ψ₂*)
removed, nothing else changed). Identical dot budgets; only the stripes vanish. *Why
visually potent:* the most dramatic single contrast in quantum mechanics, drawn with
zero extra machinery. Ranked 3 because it steps outside the real dataset — Tonomura
1989 contains **no which-path variant**, so this panel would be quantum-mechanical
prediction, and must be labeled as such, not as data. Use only if the translator needs
a second movement; never let it dilute VT-1.

---

## 3. Exact numbers the designer must use (all from Am. J. Phys. 57, 117 (1989))

| Quantity | Value | Status |
|---|---|---|
| Accelerating voltage V₀ | 50 kV | measured |
| Electron wavelength λ | 5.4 pm (0.054 Å) | paper, via E1 |
| Electron speed | ~1.2×10⁸ m/s (β ≈ 0.4) | derived; matches Hitachi page |
| Beam current / rate | 1.6×10⁻¹⁶ A ≈ 10³ electrons/s (whole field) | paper |
| Source → detector | 1.5 m | paper |
| Mean gap between successive electrons | ~150 km | paper |
| Wave-packet length | ~1 µm | paper |
| Biprism filament | < 1 µm diameter, between grounded plates ~10 mm apart | paper |
| Transverse coherence length | 140 µm | paper |
| Beam crossing angle 2β | 7.7×10⁻⁶ rad | paper (Eq. 8–9) |
| Fringe period (image plane / detector) | 0.7 µm / 1.4 mm (×2000) | paper |
| Detector field | ~12 mm across; Fig. 5 shows the central ⅓ width × ½ length | paper |
| Detector | fluorescent film + Hamamatsu PIAS photon-counting chain; ~500 photons per 50-kV electron; ≈100% detection efficiency | paper |
| Buildup frame counts (Fig. 5 a–e) | **10, 100, 3000, 20 000, 70 000** | paper caption |
| Electrons per fringe at frame (e) | 14 000 (≈5 fringes in the crop) | paper |
| Buildup time scale | ~20 min order-of-magnitude ("reasonable time, say, 20 min") | paper |
| Rate-invariance of contrast | same within 10% from 200 to 5000 e/s | paper |

**Sampling recipe (deterministic, seeded):** draw (x, y) by rejection from
P(x) = exp(−x²/2σ²)·cos²(πx/s) with x over ±2.5 fringe periods (≈5 periods in view,
matching Fig. 5), y uniform; ONE SeededRNG stream; panel k renders the first N_k
accepted points. i.i.d. draws — no stratification, no blue-noise, no minimum-distance
rejection at the statistical level (see §4 for the ink-level saturation rule).

**Working in detector coordinates then scaling uniformly to paper is exact**, not an
approximation — the experiment itself already magnified the pattern ×2000; the plotter
is the third magnification stage. Keep s : field-width : σ ratios fixed
(1.4 : 12 : 2.8).

---

## 4. Allowed simplifications vs. lies

**Allowed (say so in the piece's colophon where noted):**
- Two-virtual-source model E(x)·cos²(πx/s) instead of the full Fresnel biprism
  calculation. Omits the faint filament-edge Fresnel fringes at the overlap borders —
  invisible at plotter resolution. Honest.
- Gaussian envelope with σ ≈ 2.8 mm (detector units): **reconstructed** to match the
  published frames' visible fringe falloff (edge fringes ≈ 45% of center). The paper
  does not tabulate the envelope. Must be declared as reconstructed.
- Uniform y within the panel; crop to the central field — the paper's own Fig. 5 crops.
- **Scaled-down N per panel is allowed only with true labeling.** Preferred: use the
  paper's own first frames 10 / 100 / 3000 directly — all three are plottable, and by
  E5 the fringes genuinely emerge at 3000. If a fourth, denser panel is wanted, label
  its actual plotted count; never claim 70 000.
- Overlapping detections at high N: cap repeat hits per ~0.8 mm cell (`--max-ink`)
  and let fringe cores saturate to near-solid ink. This mimics detector/monitor
  saturation and is a *rendering* limit, not a change to the statistics — the dots that
  are drawn remain honest i.i.d. samples.
- Calling the piece "double-slit" is acceptable **with a biprism credit line**
  (e.g. "realized with an electron biprism — one wavefront split into two converging
  halves; the two-slit experiment made real"). The paper itself frames it this way.

**Lies (forbidden — the science critic must fail the piece on any of these):**
- **Trajectories.** Any line from source through a slit to a dot asserts which-path
  information that would destroy the very pattern shown, and no such paths exist in the
  formalism. No connecting lines, no "electron paths," no arrows through slits.
- A literal ripple/wave drawn traveling through the slits alongside the dots, as if
  the wave were a physical splash that "breaks into" particles on the screen.
- **Cleaning up low-N panels**: de-clumping, stratifying, blue-noising, or hand-placing
  early dots so they "read better." The clumpy, unfair-looking scatter at N = 10 and
  N = 100 is the message. Poisson or nothing.
- Placing dots deterministically on fringe maxima, or letting fringe visibility appear
  earlier than E5 allows (e.g. tuning N = 100 to secretly hint stripes).
- Independent re-draws per panel. Panels must be nested prefixes of one sequence —
  otherwise the "same experiment, later" caption is false.
- Changing s, σ, or the field crop between panels of VT-1/VT-2.
- The sinc² slit-width envelope (wrong physics for a biprism), or inventing a
  slit-separation sweep and presenting it as Tonomura data.
- If VT-3 is drawn: presenting the which-path panel as measured data. It is a
  prediction; label it so.

---

## 5. The misconception this piece quietly corrects

**"The fringes form because electrons interfere with each other"** (or: the pattern is
waves splashing onto the screen). The piece corrects it structurally, without a single
word of argument: every mark on the paper is one whole, indivisible landing — never a
half-dot, never a smear — and the machine held only one electron at a time (150 km
between electrons; a 1.5 m apparatus; the next electron not yet emitted when the last
one landed). Each electron interferes **only with itself**; the wave is the probability
law, visible in nothing smaller than the ensemble. Secondary correction (VT-3 only, if
used): "measurement disturbs the electron mechanically" — no; merely making the paths
distinguishable deletes the cross term.

---

## 6. Pen-plotter fit (one paragraph)

Dots are the plotter's native grain, and this is the one canonical quantum dataset that
*is* dots — the mapping is one-to-one: one electron detection = one pen tap, no
rasterization metaphor in between. Better, the buildup story maps onto the plotter's
own temporality: if the machine draws the seeded sequence **in arrival order**, the
piece performs the experiment live on the desk — for the first minute the pen seems to
tap at random, and the fringes condense under the viewer's eyes exactly as they did on
Tonomura's monitor over 20 minutes; the nested-prefix panel structure means panel k is
literally a photograph of the plot mid-run. One black pen suffices (a second pen could
honestly encode "arrivals since the previous frame" per panel — an increment, a real
quantity — but nothing more). Fabrication reality: i.i.d. samples have arbitrarily
close pairs, so the ≥0.8 mm spacing gate must be satisfied by panel sizing, not by
thinning the statistics — expected peak density ≈ 2N/(W·H) at fringe centers, so size
panels such that 2N/(W·H) ≤ ~1 dot/mm² (e.g. N = 3000 needs ≥ 6000 mm², a 160×40 mm
panel), and let residual collisions overprint under the `--max-ink` cap as detector
saturation. Shot noise costs nothing in ink and is the content: the cheapest marks the
plotter can make carry the deepest law in the drawing.

---

*FIELD EXPERT sign-off: every number above was read from the AJP 1989 paper directly
(scanned pages rendered and verified), not from memory or web summaries. The two
public-web discrepancies (frame counts, emission rate) are flagged in the header so the
science critic does not "correct" the piece toward the wrong numbers.*
