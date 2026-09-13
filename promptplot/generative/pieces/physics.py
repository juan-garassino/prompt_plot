"""Studio COMPOSITIONS — designed science pieces (see STUDIO.md / ARCHITECTURE.md).

Each function here is a single data-linked artwork, not a parametric family:
the seed only fine-tunes. Built to a translator's encoding spec against a field
expert's dossier; judged by the critic panel. Real data / exact math only.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import List, Optional, Tuple

from ...models import GCodeCommand
from ..generators import _catmull_subdivide, _poly, _stroke_text, _text_width
from ..rng import SeededRNG

Bounds = Tuple[float, float, float, float]

_ASTRO_DATA = Path(__file__).resolve().parents[3] / "studio" / "astro-01" / "data"


def _spaced(t: str) -> str:
    return " ".join(t)


def _read_strain(path: Path) -> List[Tuple[float, float]]:
    """Two-column '# time  strain*1e21' file -> [(t, col)]."""
    out = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            out.append((float(parts[0]), float(parts[1])))
    return out


def _analytic_chirp(n: int = 3441, t0: float = 0.25, t1: float = 0.46):
    """Newtonian post-Newtonian chirp fallback (NOT LIGO data — caption must say so)."""
    tm = 0.4225  # merger instant in-window
    out = []
    for i in range(n):
        t = t0 + (t1 - t0) * i / (n - 1)
        tau = max(1e-4, tm - t)
        f = min(250.0, 35.0 * (tau / (tm - t0)) ** -0.375)
        amp = 0.0
        if t < tm:
            amp = 0.25 * (f / 35.0) ** (2.0 / 3.0)
        else:  # ringdown: two dying cycles
            amp = 1.0 * math.exp(-(t - tm) / 0.004)
            f = 250.0
        env = amp if t < tm else amp
        out.append((t, env * math.sin(2 * math.pi * f * (t - t0))))
    return out


def gw150914(
    rng: SeededRNG, bounds: Bounds, colors: int = 3, data_dir: str = "", feed: int = 2000
) -> List[GCodeCommand]:
    """GW150914 — the first gravitational-wave chirp (LIGO Hanford, 2015-09-14).

    Art Deco. The real bandpassed strain trace is the dominant mass (black =
    measurement); the numerical-relativity template runs gold underneath (gold =
    prediction — where they disagree, gold shows: the residual draws itself); a
    zero-crossing colonnade whose spacing ramp IS the chirp clock; a subordinate
    medallion where two horizons at true 106:86 scale touch at the merger
    instant (crimson = contact). Data: GWOSC / PRL 116, 061102.
    """
    x0, y0, x1, y1 = bounds
    BLACK = (colors - 1) if colors > 1 else None
    GOLD = 1 % colors if colors > 1 else None
    CRIMSON = 2 % colors if colors > 1 else None
    out: List[GCodeCommand] = []

    ddir = Path(data_dir) if data_dir else _ASTRO_DATA
    obs_f, nr_f = ddir / "fig1-observed-H.txt", ddir / "fig1-waveform-H.txt"
    real = obs_f.exists() and nr_f.exists()
    observed = _read_strain(obs_f) if real else _analytic_chirp()
    template = _read_strain(nr_f) if real else _analytic_chirp()

    # --- coordinate mapping (encoding §4): A4-landscape drawable assumed
    T0, T1 = 0.25, 0.46
    BASE_Y = y0 + 0.44 * (y1 - y0)  # strain baseline (~y=95 on A4)
    MERGE_X = x0 + (0.4225 - T0) / (T1 - T0) * (x1 - x0)
    XS = (x1 - x0 - 0) / (T1 - T0)
    YS = 0.135 * (y1 - y0)  # ~27mm per 1e-21 unit

    def tx(t):
        return x0 + (t - T0) / (T1 - T0) * (x1 - x0)

    def sy(v):
        return max(y0 + 1, min(y1 - 1, BASE_Y + v * YS))

    def trace_pts(series):
        return [(tx(t), sy(v)) for t, v in series if T0 <= t <= T1]

    obs_pts = trace_pts(observed)
    nr_pts = trace_pts(template)

    # merger-region trace y(x) for colonnade relief clipping
    band_top = y0 + 0.35 * (y1 - y0)
    band_bot = y0 + 0.10 * (y1 - y0)

    def trace_y_near(xq):
        best, bd = None, 9e9
        for px, py in obs_pts:
            d = abs(px - xq)
            if d < bd:
                bd, best = d, py
        return best

    # --- GOLD first: NR template under the data
    out += _poly(nr_pts, color=GOLD, f=feed)

    # --- GOLD colonnade: vertical hairlines at template zero-crossings
    #     (theory-derived GW half-period; spacing ramp = the chirp clock)
    zc = []
    for i in range(1, len(template)):
        (ta, va), (tb, vb) = template[i - 1], template[i]
        if va == 0 or (va < 0) != (vb < 0):
            if abs(va) + abs(vb) > 0.12:  # coherent region only
                zc.append(tx(ta + (tb - ta) * abs(va) / (abs(va) + abs(vb) + 1e-9)))
    last = -1e9
    for xh in zc:
        if xh - last < 2.4 or not (x0 + 20 < xh < x0 + 0.9 * (x1 - x0)):
            continue
        last = xh
        top = band_top
        ty = trace_y_near(xh)
        if ty is not None and ty < band_top + 1.5:
            top = min(band_top, ty - 1.3)
        if top - band_bot > 3:
            out += _poly([(xh, band_bot), (xh, top)], color=GOLD, f=feed)

    # --- GOLD rule pointing across the void to the medallion
    rule_y = y0 + 0.72 * (y1 - y0)
    out += _poly([(x0, rule_y), (x0 + 0.36 * (x1 - x0), rule_y)], color=GOLD, f=feed)

    # --- GOLD medallion: two dying-orbit spiral arms, ~4 turns, r 15.5->8.5mm
    mcx, mcy = MERGE_X, rule_y
    R_HI, R_LO, TURNS = 0.072 * (x1 - x0), 0.040 * (x1 - x0), 4.0
    for arm in (0.0, math.pi):
        sp = []
        n = 200
        for k in range(n + 1):
            u = k / n
            r = R_HI + (R_LO - R_HI) * u
            a = arm + 2 * math.pi * TURNS * u
            sp.append((mcx + r * math.cos(a), mcy + r * math.sin(a)))
        out += _poly(sp, color=GOLD, f=feed)

    # --- GOLD dotted plumb line from medallion underside toward the peak
    py = mcy - R_HI - 2
    while py > BASE_Y + 0.135 * (y1 - y0) + 2:
        out += _poly([(mcx, py), (mcx, py - 1.2)], color=GOLD, f=feed)
        py -= 3.0

    # --- BLACK: the measurement, one unbroken polyline (zero lifts)
    out += _poly(obs_pts, color=BLACK, f=feed)

    # --- BLACK type (spaced caps, Deco tracking)
    tt = y1 - 0.14 * (y1 - y0)
    out += _stroke_text(_spaced("GW150914"), x0, tt, 9.0, color=BLACK, f=feed)
    out += _stroke_text(_spaced("GW150914"), x0 + 0.15, tt, 9.0, color=BLACK, f=feed)  # 2nd pass
    out += _stroke_text(
        _spaced("THE FIRST GRAVITATIONAL-WAVE CHIRP"), x0, tt - 8.5, 2.6, color=BLACK, f=feed
    )
    out += _stroke_text(
        _spaced("LIGO HANFORD  35-350 HZ  0.21 S"), x0, tt - 14.0, 2.4, color=BLACK, f=feed
    )
    out += _stroke_text(
        _spaced("INSPIRAL"),
        x0 + 0.15 * (x1 - x0),
        BASE_Y + 0.09 * (y1 - y0),
        2.4,
        color=BLACK,
        f=feed,
    )
    out += _stroke_text(
        _spaced("MERGER"), MERGE_X - 22, BASE_Y + 0.17 * (y1 - y0), 2.4, color=BLACK, f=feed
    )
    out += _stroke_text(
        _spaced("RINGDOWN"), MERGE_X + 10, BASE_Y + 0.09 * (y1 - y0), 2.4, color=BLACK, f=feed
    )
    foot = "GWOSC / PRL 116 061102" if real else "ANALYTIC CHIRP (NOT LIGO DATA)"
    out += _stroke_text(_spaced(foot), x0, y0 + 2, 2.4, color=BLACK, f=feed)
    fr = _spaced("FULL HEIGHT = STRAIN 1E-21")
    out += _stroke_text(fr, x1 - _text_width(fr, 2.4), y0 + 2, 2.4, color=BLACK, f=feed)

    # --- CRIMSON: the two touching horizons (true 106:86 scale), 2 passes + dots
    r1, r2 = 0.044 * (x1 - x0), 0.036 * (x1 - x0)
    c1, c2 = (mcx - r1 * 0.92, mcy), (mcx + r2 * 0.92, mcy)
    for cxh, cyh, rr in ((c1[0], c1[1], r1), (c2[0], c2[1], r2)):
        ring = [
            (cxh + rr * math.cos(2 * math.pi * k / 48), cyh + rr * math.sin(2 * math.pi * k / 48))
            for k in range(49)
        ]
        out += _poly(ring, color=CRIMSON, f=feed)
        out += _poly([(x + 0.15, y) for x, y in ring], color=CRIMSON, f=feed)  # 2nd pass
        out += _poly([(cxh - 0.2, cyh), (cxh + 0.2, cyh)], color=CRIMSON, f=feed)  # center dot
    return out
