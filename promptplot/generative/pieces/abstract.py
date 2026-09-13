"""Abstract/physics-adjacent pieces — chaos, resonance, curved spacetime."""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

from ...models import GCodeCommand
from ..rng import SeededRNG
from ..engine3d import _fit_out, _zbuf_terrain  # noqa: F401
from ..kit import (  # noqa: F401
    Bounds,
    BAUHAUS_PALETTE,
    BLUE,
    PINK,
    BLACK,
    _pen,
    fill_rect,
    fill_disc,
    fill_quarter,
    fill_ring,
    _runs_from_cmds,
    _cut,
    _clip_runs,
    _rect_keep,
    _fit_runs_cover,
    _emit_runs,
    circle,
    dotted_circle,
    plus_mark,
    crosshair_rules,
    swatch_bar,
    _spaced,
    type_block,
    scale_footer,
    _attention_matrix,
    _catmull_subdivide,
    _chain_segments,
    _dot,
    _limit_overdraw,
    _marching_squares,
    _poly,
    _stroke_text,
    _text_width,
)

from ..generators import harmonograph, strange_attractor  # noqa: F401



# ---------------------------------------------------------------------------
# piece 02 — SENSITIVE DEPENDENCE (lorenz)
# ---------------------------------------------------------------------------


def bauhaus_attractor(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 3,
    system: str = "lorenz",
    steps: int = 16000,
    feed: int = 2200,
) -> List[GCodeCommand]:
    """A full-bleed black column at the quarter line; one huge chaotic
    trajectory bursts out of it, cropped at the frame on three sides; solid
    blue/pink discs plug the true empty eyes of the two lobes."""
    x0, y0, x1, y1 = bounds
    W, H = x1 - x0, y1 - y0
    out: List[GCodeCommand] = []
    blue, pink, black = _pen(BLUE, colors), _pen(PINK, colors), _pen(BLACK, colors)

    # the column: full-bleed top and bottom, right edge on the 0.30 line
    xA = x0 + 0.30 * W
    out += fill_rect(xA - 0.09 * W, y0, xA, y1, spacing=0.6, pen=black, f=feed)

    # chaos field: everything right of the column, cropped at the frame
    field = (xA, y0, x1, y1)
    keep = _rect_keep(field)
    target = (xA - 0.04 * W, y0 - 0.09 * H, x1 + 0.08 * W, y1 + 0.09 * H)

    def kmeans2(samp, seed_pts):
        c_a, c_b = seed_pts
        for _ in range(12):
            ga, gb = [], []
            for px, py in samp:
                da = (px - c_a[0]) ** 2 + (py - c_a[1]) ** 2
                db = (px - c_b[0]) ** 2 + (py - c_b[1]) ** 2
                (ga if da < db else gb).append((px, py))
            if ga:
                c_a = (sum(p_[0] for p_ in ga) / len(ga), sum(p_[1] for p_ in ga) / len(ga))
            if gb:
                c_b = (sum(p_[0] for p_ in gb) / len(gb), sum(p_[1] for p_ in gb) / len(gb))
        return c_a, c_b

    def eye(c, samp):
        # largest empty circle near c: the disc must sit IN the lobe eye
        best, bestd = c, 0.0
        step = 0.017 * min(W, H)
        for gi in range(-5, 6):
            for gj in range(-5, 6):
                q = (c[0] + gi * step, c[1] + gj * step)
                if not keep(q):
                    continue
                d = min(math.hypot(q[0] - p[0], q[1] - p[1]) for p in samp)
                if d > bestd:
                    bestd, best = d, q
        return best, bestd

    # try 3 seeded projections of the same chaos; PCA-align the lobe axis to a
    # slight diagonal, then keep the projection with the deepest eyes + best
    # coverage of the field
    best_pick = None
    tilt = math.radians(9.0)
    for _cand in range(3):
        traj = strange_attractor(rng, bounds, colors=1, system=system, steps=steps)
        runs0 = _runs_from_cmds(traj)
        raw = [p for r in runs0 for p in r]
        if not raw:
            continue
        rs = raw[:: max(1, len(raw) // 1500)]
        mx = sum(p[0] for p in rs) / len(rs)
        my = sum(p[1] for p in rs) / len(rs)
        sxx = sum((p[0] - mx) ** 2 for p in rs)
        syy = sum((p[1] - my) ** 2 for p in rs)
        sxy = sum((p[0] - mx) * (p[1] - my) for p in rs)
        ang = 0.5 * math.atan2(2 * sxy, sxx - syy)
        ca_, sa_ = math.cos(tilt - ang), math.sin(tilt - ang)
        rot = [
            [
                (mx + (px - mx) * ca_ - (py - my) * sa_, my + (px - mx) * sa_ + (py - my) * ca_)
                for px, py in r
            ]
            for r in runs0
        ]
        runs = _clip_runs(_fit_runs_cover(rot, target), keep)
        pts = [p for r in runs for p in r]
        if not pts:
            continue
        samp = pts[:: max(1, len(pts) // 1000)]
        c_a, c_b = kmeans2(samp, (pts[len(pts) // 4], pts[3 * len(pts) // 4]))
        (ea, da_), (eb, db_) = eye(c_a, samp), eye(c_b, samp)
        sep = math.hypot(ea[0] - eb[0], ea[1] - eb[1])
        gx, gy = 10, 7
        cells = set()
        for px, py in samp:
            cells.add(
                (
                    min(gx - 1, int((px - xA) / max(1e-9, x1 - xA) * gx)),
                    min(gy - 1, int((py - y0) / max(1e-9, y1 - y0) * gy)),
                )
            )
        coverage = len(cells) / float(gx * gy)
        score = min(da_, db_) + 0.10 * sep + 30.0 * coverage
        if best_pick is None or score > best_pick[0]:
            best_pick = (score, runs, (ea, da_), (eb, db_))

    if best_pick is not None:
        _, runs, eye_a, eye_b = best_pick
        left, right = sorted((eye_a, eye_b), key=lambda t: t[0][0])
        for (ec, ed), pen, shrink in ((left, blue, 1.0), (right, pink, 0.72)):
            r = max(3.5, min(ed + 1.5, 15.0)) * shrink
            r = min(r, ec[0] - xA - 0.6, x1 - ec[0] - 0.6, ec[1] - y0 - 0.6, y1 - ec[1] - 0.6)
            if r > 2.0:
                out += fill_disc(ec[0], ec[1], r, spacing=0.5, pen=pen, f=feed)
        out += _emit_runs(runs, black, f=feed)

    # left margin column: one axis for type, swatches, footer
    xT = x0 + 0.015 * W
    out += type_block(["SENSITIVE", "DEPENDENCE"], xT, y1 - 7.0, height=3.0, pen=black, f=feed)
    out += swatch_bar(xT, y1 - 23.0, [black, blue, pink], size=3.2, f=feed)
    out += _stroke_text(_spaced("M 1:80"), xT, y0 + 2.0, 2.2, color=black, f=feed)
    return out




# ---------------------------------------------------------------------------
# piece 07 — RESONANCE (harmonograph)
# ---------------------------------------------------------------------------


def bauhaus_resonance(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 3,
    feed: int = 2200,
) -> List[GCodeCommand]:
    """One harmonograph curve in black over a solid pink disc, blue quarter
    stack, orbit circle — the damped pendulum as poster geometry."""
    x0, y0, x1, y1 = bounds
    W, H = x1 - x0, y1 - y0
    out: List[GCodeCommand] = []
    blue, pink, black = _pen(BLUE, colors), _pen(PINK, colors), _pen(BLACK, colors)

    sub = (x0 + 0.20 * W, y0 + 0.10 * H, x1 - 0.06 * W, y1 - 0.10 * H)
    curve = harmonograph(rng, sub, colors=1)
    pts = [(c.x, c.y) for c in curve if c.command == "G1" and c.x is not None]
    ccx = sum(p_[0] for p_ in pts) / len(pts)
    ccy = sum(p_[1] for p_ in pts) / len(pts)

    out += fill_disc(ccx, ccy, 0.16 * H, spacing=0.55, pen=pink, f=feed)
    out += dotted_circle(ccx, ccy, 0.40 * H, pen=black, bounds=bounds, f=feed)
    for c in curve:
        if c.command in ("M3", "G1", "G0"):
            c.color = black
    out += curve

    qx, qy = x0 + 0.09 * W, y0 + 0.24 * H
    out += fill_quarter(qx, qy, 5.0, math.pi / 2, pen=blue, f=feed)
    out += fill_quarter(qx, qy, 5.0, 3 * math.pi / 2, pen=black, f=feed)
    out += type_block(["RESONANCE"], x0 + 5.0, y1 - 6.0, pen=black, f=feed)
    out += swatch_bar(x0 + 5.0, y1 - 16.0, [black, blue, pink], f=feed)
    out += plus_mark(x1 - 9.0, y0 + 12.0, pen=black, f=feed)
    out += scale_footer(bounds, pen=black, f=feed)
    return out




# ---------------------------------------------------------------------------
# piece 09 — WARPED FRAME (gravity is the grid; a fresh, disk-less black hole)
# ---------------------------------------------------------------------------


def bauhaus_warped_frame(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 3,
    n_rulings: int = 34,
    void_frac: float = 0.34,
    mass_scale: float = 5.19615242,
    samples: int = 200,
    blue_inner: int = 8,
    ring_passes: int = 3,
    ring_offset: float = 0.34,
    echo: bool = True,
    guard_mm: float = 1.5,
    feed: int = 2200,
) -> List[GCodeCommand]:
    """WARPED FRAME — GRAVITY IS THE GRID. A straight Bauhaus lattice bent by an
    exact closed-form Schwarzschild point-lens around an off-center void. The
    outer-image map θ=½(β+√(β²+4θ_E²)) guarantees θ≥θ_E, so the shadow interior
    is provably never inked — the event horizon is bare paper. One loud pink
    photon ring sits at the critical impact parameter b=3√3·M; the innermost,
    most-deflected rulings turn blue where space bends hardest."""
    x0, y0, x1, y1 = bounds
    W, H = x1 - x0, y1 - y0
    blue, pink, black = _pen(BLUE, colors), _pen(PINK, colors), _pen(BLACK, colors)
    out: List[GCodeCommand] = []

    frame_keep = _rect_keep(bounds, inset=0.5)
    furn = lambda p: not (p[0] < x0 + 0.34 * W and p[1] < y0 + 26)  # bottom-left type band
    lat_keep = lambda p: frame_keep(p) and furn(p)

    # the void, off-center on the lower-left third (tension)
    vcx, vcy = x0 + void_frac * W, y0 + 0.38 * H
    theta_E = mass_scale  # = b_crit = 3√3 M, in M-units
    shadow_r = 0.15 * H  # photon ring radius on paper
    sc = shadow_r / theta_E  # mm per M-unit

    def warp(px, py):
        dx, dy = px - vcx, py - vcy
        beta_mm = math.hypot(dx, dy)
        if beta_mm < 1e-6:
            return None, 1.0
        beta = beta_mm / sc
        theta = 0.5 * (beta + math.sqrt(beta * beta + 4 * theta_E * theta_E))
        s = theta / beta
        return (vcx + dx * s, vcy + dy * s), s

    # straight background lattice over an over-sized (bleeding) source rect
    bleed = 0.14
    lx0, ly0, lx1, ly1 = x0 - bleed * W, y0 - bleed * H, x1 + bleed * W, y1 + bleed * H
    rulings = []
    for k in range(n_rulings):
        yy = ly0 + (ly1 - ly0) * k / (n_rulings - 1)
        yy += rng.uniform(-0.15, 0.15) * ((ly1 - ly0) / (n_rulings - 1))
        rulings.append([(lx0 + (lx1 - lx0) * t / (samples - 1), yy) for t in range(samples)])
    for k in range(n_rulings):
        xx = lx0 + (lx1 - lx0) * k / (n_rulings - 1)
        xx += rng.uniform(-0.15, 0.15) * ((lx1 - lx0) / (n_rulings - 1))
        rulings.append([(xx, ly0 + (ly1 - ly0) * t / (samples - 1)) for t in range(samples)])

    # warp each ruling; drop points inside the shadow+guard (the pile-up smear)
    warped = []  # (points-with-None-gaps, max_deflection)
    for line in rulings:
        w = []
        maxs = 1.0
        for px, py in line:
            q, s = warp(px, py)
            maxs = max(maxs, s)
            if q is None:
                w.append(None)
                continue
            if math.hypot(q[0] - vcx, q[1] - vcy) < shadow_r + guard_mm:
                w.append(None)
            else:
                w.append(q)
        warped.append((w, maxs))

    # the innermost / most-deflected rulings glow blue (curvature magnitude)
    order = sorted(range(len(warped)), key=lambda i: -warped[i][1])
    blue_set = set(order[:blue_inner])

    def emit(w, pen):
        seg = []
        for p in w:
            if p is None:
                if len(seg) >= 2:
                    for r in _clip_runs([seg], lat_keep):
                        out.append(("_", r, pen))
                seg = []
            else:
                seg.append(p)
        if len(seg) >= 2:
            for r in _clip_runs([seg], lat_keep):
                out.append(("_", r, pen))

    lattice: List = []
    _bak = out
    out = lattice  # collect lattice runs, then emit in pen order (black then blue)
    for i, (w, _m) in enumerate(warped):
        emit(w, blue if i in blue_set else black)
    out = _bak
    for _, r, pen in [x for x in lattice if x[2] == black]:
        out += _poly(r, color=black, f=feed)
    for _, r, pen in [x for x in lattice if x[2] == blue]:
        out += _poly(r, color=blue, f=feed)

    # the loud pink photon ring at b_crit (3 tight passes = one bold ring)
    for kp in range(ring_passes):
        out += circle(vcx, vcy, shadow_r + (kp - (ring_passes - 1) / 2) * ring_offset, pen=pink, f=feed)
    if echo:  # one plottable self-similar echo (e^-π out); e^-2π is sub-0.8mm, dropped
        out += circle(vcx, vcy, shadow_r * (1 + math.exp(-math.pi)), pen=pink, f=feed)

    out += plus_mark(vcx, vcy, s=1.2, pen=black, f=feed)  # the singularity

    xT = x0 + 0.02 * W
    out += type_block(["WARPED", "FRAME"], xT, y0 + 22.0, height=3.2, pen=black, f=feed)
    out += _stroke_text(_spaced("GRAVITY IS THE GRID"), xT, y0 + 7.0, 2.0, color=black, f=feed)
    out += swatch_bar(x1 - 9.0, y0 + 22.0, [black, blue, pink], size=2.6, f=feed)
    out += scale_footer(bounds, text="B = 3 SQRT3 M", pen=black, height=2.4, f=feed)
    return out

