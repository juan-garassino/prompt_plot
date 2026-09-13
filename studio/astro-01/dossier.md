# astro-01 — GW150914: the first gravitational-wave chirp

**Field expert:** astrophysics · **Date:** 2026-09-13 · **Status:** dossier v1

**Topic selection.** Curator's candidate (1) accepted: the GW150914 chirp. It is
complementary to the existing Luminet piece (a static portrait of one black hole vs.
the dynamic death-spiral of two), and it is the only candidate with authoritative,
directly downloadable numerical data (GWOSC). Runner-up PSR B1919+21 was rejected for
now: the famous CP1919 stacked-pulse data is a *digitization* of a figure from Harold
Craft's 1970 Cornell thesis — no clean primary numerical file exists at an
authoritative archive, which strains the house rule "real data, cite source."

---

## 1. The phenomenon (≤5 lines)

Two black holes of ~36 and ~29 solar masses, orbiting each other, lose energy to
gravitational radiation; the orbit shrinks, so they circle faster, so they radiate
harder — a runaway. On 2015-09-14 the last 0.2 s of this runaway swept through LIGO's
band (35 → 250 Hz), the holes merged into one 62 M☉ black hole at roughly half the
speed of light, radiating 3.0 M☉c² — and the merged hole "rang down" to silence in
milliseconds. Detected by both LIGO detectors 6.9 ms apart; peak strain 1.0×10⁻²¹.

### Governing relations

- **Chirp mass** sets everything:
  ℳ = (m₁m₂)^(3/5) / (m₁+m₂)^(1/5) ≈ 28 M☉ source-frame ≈ 30 M☉ detector-frame
  (Gℳ/c³ ≈ 1.48×10⁻⁴ s for ℳ = 30 M☉).
- **Frequency evolution** (Newtonian-order inspiral):
  df/dt = (96/5) π^(8/3) (Gℳ/c³)^(5/3) f^(11/3), which integrates to the closed form
  **f_GW(t) = (1/π) · [5 / (256 (t_c − t))]^(3/8) · (Gℳ/c³)^(−5/8)**
  (t_c = coalescence time). Checked against the data: this gives f = 33 Hz at
  t_c − t = 0.2 s, 100 Hz at 10 ms, 240 Hz at 1 ms — the observed sweep exactly.
- **Amplitude evolution**: h ∝ (Gℳ/c³)^(5/3) (πf)^(2/3) / D — amplitude grows as
  f^(2/3) while f itself runs away. Both rise together: that is the chirp.
- **Orbital separation** (Kepler; orbital angular frequency Ω = π·f_GW):
  a(t) = [G·M_tot / (π f_GW(t))²]^(1/3), M_tot ≈ 65 M☉.
  At f_GW = 150 Hz: a ≈ 350 km. At 250 Hz: a ≈ 240 km ≈ the sum of the two
  Schwarzschild radii (106 km + 86 km) — they are touching. That is the merger.
- **Ringdown** (dominant ℓ=m=2 quasinormal mode of the 62 M☉, a≈0.67 remnant):
  h(t) = A·e^(−t/τ)·cos(2π f_qnm t + φ), with f_qnm ≈ 250 Hz, τ ≈ 4 ms (Q ≈ 3):
  about two visible cycles, then nothing.

**GW150914 numbers (LIGO PRL 116, 061102):** m₁ = 36 (+5/−4) M☉, m₂ = 29 (±4) M☉,
remnant 62 (±4) M☉, E_rad = 3.0 (±0.5) M☉c², peak strain 1.0×10⁻²¹, band sweep
35 → 250 Hz in ~0.2 s (~8 GW cycles → ~4 orbits in band), distance ~410 Mpc (z≈0.09),
detector arrival gap 6.9 ms (Livingston first), SNR 24.

---

## 2. Three candidate visual truths (ranked)

### (a) The strain trace itself — inspiral → merger → ringdown, anatomy labeled  ★ RANK 1

The real Hanford strain (bandpassed 35–350 Hz as published), one continuous line,
time → x, strain → y, with three quiet annotations marking the anatomy: *inspiral*
(cycles tightening, amplitude swelling), *merger* (the single tallest cycle, peak
strain 1.0×10⁻²¹, the loudest moment ever recorded by our species), *ringdown*
(two dying wiggles, τ ≈ 4 ms, then flat noise).

**Why visually potent:** the entire physics — energy loss, runaway, collision,
settling — is legible in ONE unbroken line with no encoding tricks. Both amplitude
and wavelength change in exactly the coupled way the equations demand; the eye reads
acceleration-toward-catastrophe without being told. It is real measured data of the
most violent event ever observed, drawn at 1:10²¹ vertical scale. A second pen can
carry the numerical-relativity template (also downloadable, below) as the "prediction
under the measurement" — theory and data agreeing to within the pen's line width is
itself the discovery.

### (b) The dying orbit — separation shrinking as a two-armed spiral  ★ RANK 2

Two interleaved spiral arms (one per black hole, orbiting their common center),
radius r(t) = a(t)/2 taken from Kepler + the measured f(t); terminate where a equals
the sum of the Schwarzschild radii, drawing the two horizons as touching circles at
true relative scale (106 km vs 86 km). Honest turn count: only ~4 orbits happen in
band — the spiral is shockingly few-turned, which is itself the truth (this is a
plunge, not a gentle coil).

**Why visually potent:** it converts the waveform into the *cause* — two bodies
falling forever and finally hitting. The near-1:1 size ratio of the circles and the
tiny number of turns violate every decorative-spiral instinct, which is exactly the
corrective punch. Weakness: the radial dynamic range in band is small (~350 km →
~190 km, under 2:1), so the spiral gap shrinks subtly rather than dramatically.

### (c) Frequency climbing the staff — the chirp as musical score  ★ RANK 3

Extract instantaneous frequency from zero-crossing intervals of the real strain;
plot each half-cycle as a mark whose x = time, y = log-frequency (a staff). The marks
start sparse and low, then climb and crowd into the merger like an accelerando,
ending on one high sustained-then-cut note (the ringdown).

**Why visually potent:** it literalizes the "chirp" metaphor honestly — 35→250 Hz is
genuinely inside human hearing, so the musical-notation reading is *physically
grounded*, not whimsy. Weakness: it needs the viewer to accept a derived quantity
(frequency) rather than the raw measurement, and it flirts with the very "GWs are
sound" misconception this piece should correct — usable only with a disciplined
caption.

---

## 3. Real data — verified

All URLs below returned **HTTP 200 with no authentication** via `curl` on
2026-09-13. Primary source: LIGO/Virgo Gravitational Wave Open Science Center
(GWOSC), data release for LIGO PRL 116, 061102 (2016).

**Primary file (the published Fig. 1 observed trace, Hanford):**

```
https://gwosc.org/GW150914data/P150914/fig1-observed-H.txt
```

Plain two-column ASCII, header `# time (seconds)  strain * 1.e21`; 3441 samples at
16384 Hz covering a 0.21 s window (t = 0.25–0.46 s relative to GPS 1126259446); the
strain column is already multiplied by 10²¹ (peak ≈ ±1.0) and bandpassed 35–350 Hz
as published. This file IS the famous plot.

**Companion files (same directory, same format, all verified 200):**

| File | Content |
|---|---|
| `fig1-observed-L.txt` | Livingston strain, time-shifted (+6.9 ms) and sign-flipped as published, for the two-detector overlay |
| `fig1-waveform-H.txt` | Numerical-relativity template projected onto H1 — the "theory" line |
| `fig1-residual-H.txt` | data − template residual (noise) |
| `fig2-unfiltered-waveform-H.txt` | Unfiltered NR waveform — clean anatomy without bandpass ringing |

**Full raw strain (if higher fidelity ever wanted):**
`https://gwosc.org/s/events/GW150914/H-H1_LOSC_4_V2-1126259446-32.txt.gz`
(32 s @ 4096 Hz, gzipped ASCII; verified 200). Event API metadata:
`https://gwosc.org/eventapi/json/GWTC-1-confident/GW150914/v3/` (verified 200).

**Analytic fallback** (only if the network is unavailable at build time — say so in
the piece notes if used): Newtonian chirp with ℳ = 30 M☉ (detector frame):
f_GW(t) = (1/π)·[5/(256(t_c−t))]^(3/8)·(Gℳ/c³)^(−5/8), phase φ(t) = 2π∫f dt,
h(t) = h₀·f(t)^(2/3)·cos φ(t) normalized to peak 1.0×10⁻²¹; truncate the inspiral at
f_GW ≈ 200 Hz and stitch a ringdown e^(−t/τ)cos(2π·250·t), τ = 4 ms. This
reproduces the real sweep to within a few percent over the in-band window but it is
a model, not the measurement — the drawing must not be captioned "LIGO data" if built
from it.

---

## 4. Simplifications allowed vs. lies

**Allowed (honest):**
- Using the bandpassed 35–350 Hz trace rather than raw strain. The raw data is
  seismic-noise dominated and unreadable; the published discovery figure is
  bandpassed. Note "bandpassed 35–350 Hz" in the piece annotation.
- Plotting Hanford only, or Hanford + the shifted/inverted Livingston overlay
  (the shift/inversion is the published, physically justified alignment).
- Vertical exaggeration of the strain axis by any single uniform factor (the units
  are 10⁻²¹; some scale must be chosen). Uniform only.
- Light resampling/smoothing below pen resolution (<0.1 mm at final scale).
- For visual truth (b): drawing horizons as circles of Schwarzschild radius
  (106 km / 86 km) with Keplerian separation — at merger they genuinely overlap at
  scale, so *touching circles at true relative scale are fine and true*.

**Lies (forbidden):**
- Idealizing the trace — removing noise wiggles, forcing monotone amplitude growth —
  while still presenting it as data. Either plot the real file or label it a model.
- Extending the ringdown for beauty. It dies in ~2 cycles (τ = 4 ms). A long
  romantic ringing tail is false physics.
- A many-turned inspiral spiral. Only ~4 orbits occur in band; a 20-turn coil is a
  decorative lie about how sudden this plunge is.
- Non-uniform axis distortion (stretching only the merger region, log-time, etc.)
  without explicit labeling.
- The rubber-sheet cliché: concentric circular ripples on a 2D "fabric" plane. The
  wave is a quadrupolar strain propagating at c, not a splash.
- Captioning analytic-fallback output as LIGO data.

---

## 5. The misconception to quietly correct

**"Gravitational waves are sound from space"** (and its cousin: "LIGO *heard* the
black holes"). The wave is a strain of spacetime itself — a fractional change of
distance, h = ΔL/L — not a pressure wave; space is not a medium carrying audio. The
famous "chirp" sound is a *conversion*: the frequencies happen to fall in the human
audio band. The piece corrects this by making the y-axis honestly dimensionless:
annotate **strain ×10⁻²¹**, and add one devastating scale note — at peak, LIGO's 4 km
arms changed length by ~4×10⁻¹⁸ m, about 1/400 of a proton's diameter. The viewer
should leave knowing they are looking at a *ruler flexing*, not a microphone signal.

---

## 6. Pen-plotter fit

The strain trace is the plotter's dream: one continuous polyline of 3441 real points
with zero pen lifts — the machine performs the 0.2 s of the event as a single
unbroken gesture, and the physical continuity of the ink line *is* the physical
continuity of the signal. Scale check at A4 landscape (~250 mm drawable width for
the 0.21 s window): the fastest merger cycle (~4 ms) spans ~4.8 mm, comfortably
above the 0.8 mm stroke-spacing floor with a 0.3 mm pen; peak-to-peak amplitude maps
to ±25–30 mm with everything else calm around it, so ink density is naturally low
except at the one moment that matters. A second pen can underlay the NR template
(`fig1-waveform-H.txt`) — theory under measurement, agreeing to within a line width —
and a third could carry the annotations; that stays inside a ≤3-pen budget with no
swap during either trace. No fills, no hatching, no retraces: the piece is almost
pure travel-free drawing time.
