"""BAUHAUS UNIVERSUM — shared design kit + collection pieces.

Flat constructivist language on three pens (blue / pink / black): solid
serpentine and spiral fills, bars, quarter-discs, dotted orbits, swatch bars,
crosshair rules and spaced-caps single-stroke type. Every piece is a seeded
generator `(rng, bounds, colors=3, ...) -> List[GCodeCommand]` laid out
directly in paper mm. Renders use ``BAUHAUS_PALETTE``.
"""

from __future__ import annotations

import io
import math
import zipfile
from typing import List, Optional, Sequence, Tuple

from ..models import GCodeCommand
from .generators import (
    _attention_matrix,
    _catmull_subdivide,
    _chain_segments,
    _dot,
    _marching_squares,
    _poly,
    _stroke_text,
    _text_width,
    strange_attractor,
)
from .rng import SeededRNG

Bounds = Tuple[float, float, float, float]

BAUHAUS_PALETTE = ["dodgerblue", "deeppink", "black"]
BLUE, PINK, BLACK = 0, 1, 2


def _pen(idx: int, colors: int) -> Optional[int]:
    return idx % colors if colors > 1 else None


# ---------------------------------------------------------------------------
# fills
# ---------------------------------------------------------------------------


def fill_rect(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    spacing: float = 0.55,
    pen: Optional[int] = None,
    f: int = 2200,
) -> List[GCodeCommand]:
    """Solid rectangle as one serpentine polyline."""
    pts = []
    y = y0
    flip = False
    while y <= y1 + 1e-9:
        row = [(x0, y), (x1, y)]
        pts.extend(reversed(row) if flip else row)
        flip = not flip
        y += spacing
    return _poly(pts, color=pen, f=f)


def fill_disc(
    cx: float, cy: float, r: float, spacing: float = 0.5, pen: Optional[int] = None, f: int = 2200
) -> List[GCodeCommand]:
    """Solid disc as one Archimedean spiral."""
    turns = max(2, int(r / spacing))
    n = turns * 30
    pts = []
    for k in range(n + 1):
        t = k / n
        rr = r * t
        a = 2 * math.pi * turns * t
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return _poly(pts, color=pen, f=f)


def fill_quarter(
    cx: float,
    cy: float,
    r: float,
    a_start: float,
    spacing: float = 0.55,
    pen: Optional[int] = None,
    f: int = 2200,
) -> List[GCodeCommand]:
    """Solid quarter-disc as concentric arcs."""
    out: List[GCodeCommand] = []
    rr = r
    while rr > 0.3:
        arc = []
        a = a_start
        while a <= a_start + math.pi / 2 + 1e-6:
            arc.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
            a += 0.08
        out += _poly(arc, color=pen, f=f)
        rr -= spacing
    return out


def fill_ring(
    cx: float,
    cy: float,
    r0: float,
    r1: float,
    spacing: float = 0.55,
    pen: Optional[int] = None,
    f: int = 2200,
) -> List[GCodeCommand]:
    out: List[GCodeCommand] = []
    rr = r0
    while rr <= r1 + 1e-9:
        ring = [
            (cx + rr * math.cos(2 * math.pi * k / 72), cy + rr * math.sin(2 * math.pi * k / 72))
            for k in range(73)
        ]
        out += _poly(ring, color=pen, f=f)
        rr += spacing
    return out


# ---------------------------------------------------------------------------
# geometry: runs, clipping (crop-at-frame + knockouts), cover-fit
# ---------------------------------------------------------------------------


def _runs_from_cmds(cmds: Sequence[GCodeCommand]) -> List[List[Tuple[float, float]]]:
    """Extract pen-down polylines from a command list."""
    runs: List[List[Tuple[float, float]]] = []
    cur: List[Tuple[float, float]] = []
    for c in cmds:
        if c.command == "G0":
            if len(cur) >= 2:
                runs.append(cur)
            cur = [(c.x, c.y)] if c.x is not None else []
        elif c.command == "G1" and c.x is not None:
            cur.append((c.x, c.y))
    if len(cur) >= 2:
        runs.append(cur)
    return runs


def _cut(inside, outside, keep, iters=14):
    """Bisect the crossing point between an inside and an outside point."""
    a, b = inside, outside
    for _ in range(iters):
        m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        if keep(m):
            a = m
        else:
            b = m
    return a


def _clip_runs(runs, keep) -> List[List[Tuple[float, float]]]:
    """Clip polylines to a boolean keep-region, cutting segments at the edge."""
    out: List[List[Tuple[float, float]]] = []
    for pts in runs:
        cur: List[Tuple[float, float]] = []
        for i, p in enumerate(pts):
            if i == 0:
                if keep(p):
                    cur.append(p)
                continue
            a = pts[i - 1]
            ka, kb = keep(a), keep(p)
            if ka and kb:
                if not cur:
                    cur = [a]
                cur.append(p)
            elif ka and not kb:
                if not cur:
                    cur = [a]
                cur.append(_cut(a, p, keep))
                if len(cur) >= 2:
                    out.append(cur)
                cur = []
            elif kb and not ka:
                cur = [_cut(p, a, keep), p]
        if len(cur) >= 2:
            out.append(cur)
    return out


def _rect_keep(region: Bounds, inset: float = 0.0):
    rx0, ry0, rx1, ry1 = region
    return lambda p: rx0 + inset <= p[0] <= rx1 - inset and ry0 + inset <= p[1] <= ry1 - inset


def _fit_runs_cover(runs, target: Bounds) -> List[List[Tuple[float, float]]]:
    """Uniform-scale + recenter runs so their bbox COVERS the target rect
    (overshoots on one axis — made for cropping at the frame)."""
    xs = [p[0] for r in runs for p in r]
    ys = [p[1] for r in runs for p in r]
    if not xs:
        return runs
    bx0, bx1, by0, by1 = min(xs), max(xs), min(ys), max(ys)
    tx0, ty0, tx1, ty1 = target
    s = max((tx1 - tx0) / max(1e-9, bx1 - bx0), (ty1 - ty0) / max(1e-9, by1 - by0))
    bcx, bcy = (bx0 + bx1) / 2, (by0 + by1) / 2
    tcx, tcy = (tx0 + tx1) / 2, (ty0 + ty1) / 2
    return [[(tcx + (px - bcx) * s, tcy + (py - bcy) * s) for px, py in r] for r in runs]


def _emit_runs(runs, pen: Optional[int], f: int = 2200) -> List[GCodeCommand]:
    out: List[GCodeCommand] = []
    for r in runs:
        out += _poly(r, color=pen, f=f)
    return out


# ---------------------------------------------------------------------------
# furniture
# ---------------------------------------------------------------------------


def circle(
    cx: float, cy: float, r: float, pen: Optional[int] = None, f: int = 2200, n: int = 96
) -> List[GCodeCommand]:
    ring = [
        (cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n))
        for k in range(n + 1)
    ]
    return _poly(ring, color=pen, f=f)


def dotted_circle(
    cx: float,
    cy: float,
    r: float,
    pen: Optional[int] = None,
    bounds: Optional[Bounds] = None,
    f: int = 2200,
) -> List[GCodeCommand]:
    out: List[GCodeCommand] = []
    seg: List[Tuple[float, float]] = []
    for k in range(241):
        a = 2 * math.pi * k / 240
        px, py = cx + r * math.cos(a), cy + r * math.sin(a)
        ok = (k % 6) < 2
        if ok and bounds is not None:
            ok = bounds[0] + 0.5 < px < bounds[2] - 0.5 and bounds[1] + 0.5 < py < bounds[3] - 0.5
        if ok:
            seg.append((px, py))
        else:
            if len(seg) >= 2:
                out += _poly(seg, color=pen, f=f)
            seg = []
    if len(seg) >= 2:
        out += _poly(seg, color=pen, f=f)
    return out


def plus_mark(
    x: float, y: float, s: float = 1.0, pen: Optional[int] = None, f: int = 2200
) -> List[GCodeCommand]:
    return _poly([(x - s, y), (x + s, y)], color=pen, f=f) + _poly(
        [(x, y - s), (x, y + s)], color=pen, f=f
    )


def crosshair_rules(
    bounds: Bounds,
    xs: Sequence[float] = (),
    ys: Sequence[float] = (),
    pen: Optional[int] = None,
    f: int = 2200,
) -> List[GCodeCommand]:
    x0, y0, x1, y1 = bounds
    out: List[GCodeCommand] = []
    for x in xs:
        out += _poly([(x, y0 + 0.5), (x, y1 - 0.5)], color=pen, f=f)
    for y in ys:
        out += _poly([(x0 + 0.5, y), (x1 - 0.5, y)], color=pen, f=f)
    return out


def swatch_bar(
    x: float,
    y_top: float,
    pens: Sequence[Optional[int]],
    size: float = 2.2,
    spacing: float = 0.5,
    f: int = 2200,
) -> List[GCodeCommand]:
    out: List[GCodeCommand] = []
    y = y_top
    for pen in pens:
        out += fill_rect(x, y - size, x + size * 0.82, y, spacing=spacing, pen=pen, f=f)
        y -= size + 0.7
    return out


# ---------------------------------------------------------------------------
# type
# ---------------------------------------------------------------------------


def _spaced(text: str) -> str:
    return " ".join(text)


def type_block(
    lines: Sequence[str],
    x: float,
    y_top: float,
    height: float = 2.6,
    pen: Optional[int] = None,
    underline: bool = True,
    f: int = 2200,
) -> List[GCodeCommand]:
    out: List[GCodeCommand] = []
    y = y_top
    for ln in lines:
        out += _stroke_text(_spaced(ln), x, y, height, color=pen, f=f)
        y -= height * 2.0
    if underline:
        out += _poly(
            [(x, y + height * 2.0 - 2.0), (x + 6.0, y + height * 2.0 - 2.0)], color=pen, f=f
        )
    return out


def scale_footer(
    bounds: Bounds,
    text: str = "M 1:80",
    pen: Optional[int] = None,
    height: float = 2.6,
    f: int = 2200,
) -> List[GCodeCommand]:
    x0, y0, x1, _y1 = bounds
    tw = _text_width(_spaced(text), height)
    return _stroke_text(_spaced(text), x1 - tw - 3.0, y0 + 3.0, height, color=pen, f=f)


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
# piece 03 — ATTENTION
# ---------------------------------------------------------------------------


def bauhaus_attention(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 3,
    tokens: int = 24,
    topk: int = 2,
    temp: float = 1.0,
    attn_npz: str = "",
    block: int = 5,
    feed: int = 2200,
) -> List[GCodeCommand]:
    """A huge token ring cropped at three frame edges; the ring is rotated so
    the sink token lands on the left axis as one big solid blue disc, and the
    strongest chords into it run pink — a directional wedge of attention."""
    x0, y0, x1, y1 = bounds
    W, H = x1 - x0, y1 - y0
    out: List[GCodeCommand] = []
    blue, pink, black = _pen(BLUE, colors), _pen(PINK, colors), _pen(BLACK, colors)
    frame_keep = _rect_keep(bounds)

    A = None
    if attn_npz:
        try:
            import numpy as np

            A = np.load(attn_npz)["attn"][block][0]
            tokens = A.shape[-1]
        except Exception:
            A = None
    if A is None:
        A = _attention_matrix(rng, tokens, 0, temp, True, "", 0)

    col_mass = [sum(float(A[q][k]) for q in range(tokens)) for k in range(tokens)]
    sink = max(range(tokens), key=lambda k: col_mass[k])

    # ring center right of middle; radius huge so the ring crops at the frame;
    # phase rotated so the sink token sits on the left axis at mid-height
    ccx, ccy = x0 + 0.62 * W, y0 + 0.46 * H
    R = min(0.66 * H, 0.60 * W)
    phase = math.pi - 2 * math.pi * sink / tokens
    pos = [
        (
            ccx + R * math.cos(2 * math.pi * t / tokens + phase),
            ccy + R * math.sin(2 * math.pi * t / tokens + phase),
        )
        for t in range(tokens)
    ]
    sk = pos[sink]
    r_sink = min(10.0, sk[0] - x0 - 0.8, x1 - sk[0] - 0.8, sk[1] - y0 - 0.8, y1 - sk[1] - 0.8)
    r_sink = max(1.5, r_sink)

    out += dotted_circle(ccx, ccy, R, pen=black, bounds=bounds, f=feed)

    # chords into the sink, ranked: top 12 pink (top 3 of those triple-pass),
    # the next 12 thin black, the rest dropped — no fan flood
    into_sink = []
    plain = []
    for q in range(tokens):
        row = sorted(range(tokens), key=lambda k: -float(A[q][k]))[:topk]
        for k in row:
            if k == q or float(A[q][k]) < 0.03:
                continue
            if k == sink:
                into_sink.append((float(A[q][k]), q))
            else:
                plain.append((k, q))
    into_sink.sort(reverse=True)

    for k, q in plain:
        if q == sink:
            continue
        for seg in _clip_runs([[pos[k], pos[q]]], frame_keep):
            out += _poly(seg, color=black, f=feed)

    for rank, (_w, q) in enumerate(into_sink[:24]):
        xb, yb = pos[q]
        dx, dy = xb - sk[0], yb - sk[1]
        n = math.hypot(dx, dy) or 1.0
        ax_, ay_ = sk[0] + dx / n * (r_sink + 1.0), sk[1] + dy / n * (r_sink + 1.0)
        if rank < 12:
            passes = 3 if rank < 3 else 1
            for pp in range(passes):
                o = (pp - (passes - 1) / 2) * 0.32
                oxp, oyp = -dy / n * o, dx / n * o
                for seg in _clip_runs([[(ax_ + oxp, ay_ + oyp), (xb + oxp, yb + oyp)]], frame_keep):
                    out += _poly(seg, color=pink, f=feed)
        else:
            for seg in _clip_runs([[(ax_, ay_), (xb, yb)]], frame_keep):
                out += _poly(seg, color=black, f=feed)

    for t in range(tokens):
        if t == sink:
            continue
        px, py = pos[t]
        if x0 + 2.2 < px < x1 - 2.2 and y0 + 2.2 < py < y1 - 2.2:
            out += fill_disc(px, py, 1.4, spacing=0.45, pen=black, f=feed)
    out += fill_disc(sk[0], sk[1], r_sink, spacing=0.5, pen=blue, f=feed)

    # left axis: type over the sink, swatches, footer
    xT = x0 + 0.015 * W
    out += type_block(["ATTENTION"], xT, y1 - 7.0, height=2.8, pen=black, f=feed)
    out += swatch_bar(xT, y1 - 17.0, [black, blue, pink], size=3.2, f=feed)
    out += _stroke_text(_spaced("M 1:80"), xT, y0 + 2.0, 2.2, color=black, f=feed)
    return out


# ---------------------------------------------------------------------------
# piece 04 — PARAMETER FIELD (Hinton diagram)
# ---------------------------------------------------------------------------


def _load_qkv(weights: str, block: int):
    import numpy as np

    buf = io.BytesIO(zipfile.ZipFile(weights).read("model.weights.h5"))
    import h5py

    f5 = h5py.File(buf, "r")
    base = "layers/transformer_encoder_block" + ("" if block == 0 else f"_{block}")

    def att(nm):
        Wm = np.array(f5[f"{base}/att/{nm}/vars/0"])
        return Wm.reshape(Wm.shape[0], -1)

    return [att("query_dense"), att("key_dense"), att("value_dense")]


def bauhaus_weights(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 3,
    weights: str = "",
    block: int = 0,
    rows: int = 22,
    cols: int = 16,
    feed: int = 2200,
) -> List[GCodeCommand]:
    """A true Hinton diagram in the Bauhaus language: Q | K | V panels on a
    strict grid, every weight a solid circle — radius by magnitude, blue
    positive, pink negative. Trained weights when a checkpoint is given."""
    import numpy as np

    x0, y0, x1, y1 = bounds
    W, H = x1 - x0, y1 - y0
    out: List[GCodeCommand] = []
    blue, pink, black = _pen(BLUE, colors), _pen(PINK, colors), _pen(BLACK, colors)

    panels = None
    if weights:
        try:
            panels = _load_qkv(weights, block)
        except Exception:
            panels = None
    if panels is None:
        panels = [
            np.array([[rng.random() * 2 - 1 for _ in range(48)] for _ in range(72)])
            for _ in range(3)
        ]

    gap = 0.045 * W
    pw = (W - 4 * gap) / 3.0
    pitch = min(pw / cols, (H * 0.62) / rows)
    ph = pitch * rows
    py_top = y1 - 0.14 * H
    labels = ["Q", "K", "V"]
    for pi, Wm in enumerate(panels):
        # block-mean downsample to rows x cols, signed
        R0, C0 = Wm.shape
        br, bc = max(1, R0 // rows), max(1, C0 // cols)
        M = np.zeros((rows, cols))
        for i in range(rows):
            for j in range(cols):
                blk = Wm[i * br : (i + 1) * br, j * bc : (j + 1) * bc]
                if blk.size:
                    # magnitude by |w| mean (doesn't cancel), sign by mean
                    M[i, j] = math.copysign(float(np.abs(blk).mean()), float(blk.mean()))
        norm = float(np.percentile(np.abs(M), 90)) or 1.0
        rx = x0 + gap + pi * (pw + gap) + (pw - pitch * cols) / 2.0
        for i in range(rows):
            cy_ = py_top - pitch * (i + 0.5)
            for j in range(cols):
                w = float(M[i, j])
                rr = min(1.0, abs(w) / norm) * pitch * 0.38
                if rr < 0.22:
                    continue
                cx_ = rx + pitch * (j + 0.5)
                pen = blue if w >= 0 else pink
                if rr < 0.55:
                    out += _poly([(cx_ - rr, cy_), (cx_ + rr, cy_)], color=pen, f=feed)
                else:
                    out += fill_disc(cx_, cy_, rr, spacing=0.42, pen=pen, f=feed)
        cap = labels[pi]
        out += _stroke_text(
            _spaced(cap), rx + pitch * cols / 2 - 2.0, py_top - ph - 6.5, 3.0, color=black, f=feed
        )
        if pi < 2:
            bx = x0 + gap + (pi + 1) * (pw + gap) - gap / 2
            out += _poly([(bx, py_top - ph), (bx, py_top)], color=black, f=feed)

    out += type_block(["PARAMETER", "FIELD"], x0 + 5.0, y0 + 16.5, pen=black, f=feed)
    out += swatch_bar(x1 - 8.0, y1 - 4.0, [black, blue, pink], f=feed)
    out += plus_mark(x1 - 9.0, y0 + 20.0, pen=black, f=feed)
    out += scale_footer(bounds, pen=black, f=feed)
    return out


# ---------------------------------------------------------------------------
# piece 05 — FORWARD PASS (perceptron)
# ---------------------------------------------------------------------------


# RETIRED (curation, no-schematics rule): a wiring diagram cannot be art. The
# 'forward pass' concept is superseded by the ml-01 space-warping piece. Kept
# for version history; deregistered from GENERATOR_REGISTRY.
def bauhaus_perceptron(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 3,
    layers: Sequence[int] = (6, 8, 8, 3),
    weights: str = "",
    feed: int = 2200,
) -> List[GCodeCommand]:
    """An MLP as constructivist art: neurons are solid discs, connections carry
    1-3 parallel passes by |w|, the winning forward path runs bold pink."""
    x0, y0, x1, y1 = bounds
    W, H = x1 - x0, y1 - y0
    out: List[GCodeCommand] = []
    blue, pink, black = _pen(BLUE, colors), _pen(PINK, colors), _pen(BLACK, colors)

    # weight matrices: slices of the real checkpoint when given, else seeded
    mats = []
    try:
        if weights:
            qkv = _load_qkv(weights, 0)
            src = qkv[0]
            for a, b in zip(layers, layers[1:]):
                mats.append(
                    [
                        [float(src[i % src.shape[0]][j % src.shape[1]]) for j in range(b)]
                        for i in range(a)
                    ]
                )
    except Exception:
        mats = []
    if not mats:
        for a, b in zip(layers, layers[1:]):
            mats.append([[rng.random() * 2 - 1 for _ in range(b)] for _ in range(a)])

    n_l = len(layers)
    lx = [x0 + W * (0.14 + 0.72 * i / (n_l - 1)) for i in range(n_l)]

    def ys(n):
        span = H * 0.62
        return [y0 + H * 0.52 - span / 2 + span * (j + 0.5) / n for j in range(n)]

    pos = [[(lx[i], y) for y in ys(n)] for i, n in enumerate(layers)]

    # bar behind the second hidden layer
    bx = lx[min(2, n_l - 1)]
    out += fill_rect(bx - 5.0, y0 + 0.5, bx + 5.0, y1 - 0.5, spacing=0.6, pen=black, f=feed)

    # winning path: greedy argmax |w| from a seeded input neuron
    path = [rng.randint(0, layers[0] - 1)]
    for li, M in enumerate(mats):
        row = M[path[-1]]
        path.append(max(range(len(row)), key=lambda j: abs(row[j])))

    for li, M in enumerate(mats):
        norm = max(abs(v) for row in M for v in row) or 1.0
        for i, row in enumerate(M):
            for j, w in enumerate(row):
                t = abs(w) / norm
                if t < 0.45:
                    continue
                (xa, ya), (xb, yb) = pos[li][i], pos[li + 1][j]
                on_path = path[li] == i and path[li + 1] == j
                pen = pink if on_path else black
                passes = 3 if on_path else (2 if t > 0.75 else 1)
                dx, dy = xb - xa, yb - ya
                n = math.hypot(dx, dy) or 1.0
                oxp, oyp = -dy / n * 0.3, dx / n * 0.3
                for pp in range(passes):
                    o = pp - (passes - 1) / 2
                    out += _poly(
                        [(xa + oxp * o, ya + oyp * o), (xb + oxp * o, yb + oyp * o)],
                        color=pen,
                        f=feed,
                    )

    for li, col in enumerate(pos):
        for j, (px, py) in enumerate(col):
            r = 2.0 + 1.6 * rng.random()
            if li == 0:
                out += fill_disc(px, py, r, spacing=0.5, pen=blue, f=feed)
            elif li == n_l - 1:
                out += fill_disc(px, py, r, spacing=0.5, pen=pink, f=feed)
            elif path[li] == j:
                out += fill_disc(px, py, r * 0.9, spacing=0.5, pen=black, f=feed)
            else:
                out += circle(px, py, r * 0.9, pen=black, f=feed)

    out += type_block(["FORWARD", "PASS"], x0 + 5.0, y1 - 6.0, pen=black, f=feed)
    out += swatch_bar(x0 + 5.0, y1 - 22.0, [black, blue, pink], f=feed)
    out += plus_mark(x1 - 9.0, y1 - 9.0, pen=black, f=feed)
    out += scale_footer(bounds, pen=black, f=feed)
    return out


# ---------------------------------------------------------------------------
# piece 06 — GRADIENT DESCENT  → reworked as WATERSHED (basin of attraction)
# ---------------------------------------------------------------------------


def bauhaus_gradient(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 3,
    n_seeds: int = 220,
    min_sep: float = 2.4,
    rk4_dt: float = 0.9,
    max_steps: int = 420,
    deep_depth: float = 1.0,
    shallow_depth: float = 0.55,
    settle_eps: float = 0.006,
    momentum: float = 0.9,
    feed: int = 2200,
) -> List[GCodeCommand]:
    """WATERSHED — gradient descent as a BASIN OF ATTRACTION. The whole
    parameter plane rains downhill (exact RK4 on an analytic 2-Gaussian loss)
    into two sinks; the separatrix is left as a knife of blank paper. Each
    streamline is black on the plateau and inks its last stretch in its
    destination's hue (blue = deep global well, pink = shallow local trap). One
    blue heavy-ball-momentum channel visibly OVERSHOOTS the deep sink and rings
    back — the optimizer, not decorative flow."""
    x0, y0, x1, y1 = bounds
    W, H = x1 - x0, y1 - y0
    blue, pink, black = _pen(BLUE, colors), _pen(PINK, colors), _pen(BLACK, colors)
    out: List[GCodeCommand] = []

    fx0, fy0, fx1, fy1 = x0 + 6, y0 + 12, x1 - 6, y1 - 22
    fw, fh = fx1 - fx0, fy1 - fy0
    rect_keep = _rect_keep((fx0, fy0, fx1, fy1))
    typebox = lambda p: p[0] < fx0 + 0.34 * W and p[1] > fy1 - 0.16 * H
    keep = lambda p: rect_keep(p) and not typebox(p)

    def u2px(u):
        return fx0 + (u + 1) / 2 * fw

    def v2py(v):
        return fy0 + (v + 1) / 2 * fh

    # exact analytic loss: two negative Gaussians + a mild draining bowl
    gux, guy, sd = -0.34, -0.30, 0.42  # deep global well (lower-left)
    sux, svy, ss = 0.40, 0.34, 0.55  # shallow local trap (upper-right)

    def gradL(u, v):
        e1 = deep_depth * math.exp(-((u - gux) ** 2 + (v - guy) ** 2) / (2 * sd * sd))
        e2 = shallow_depth * math.exp(-((u - sux) ** 2 + (v - svy) ** 2) / (2 * ss * ss))
        gx = 0.24 * u + e1 * (u - gux) / (sd * sd) + e2 * (u - sux) / (ss * ss)
        gy = 0.24 * v + e1 * (v - guy) / (sd * sd) + e2 * (v - svy) / (ss * ss)
        return gx, gy

    def rhs(u, v):
        gx, gy = gradL(u, v)
        n = math.hypot(gx, gy) or 1e-9
        return -gx / n, -gy / n

    # locate the TWO true sinks by descent from a coarse lattice
    def descend(u, v):
        for _ in range(800):
            gx, gy = gradL(u, v)
            n = math.hypot(gx, gy)
            if n < settle_eps:
                break
            u -= 0.02 * gx
            v -= 0.02 * gy
        return u, v

    ends = [descend(-1 + 2 * i / 5, -1 + 2 * j / 5) for i in range(6) for j in range(6)]
    gc = [e for e in ends if (e[0] - gux) ** 2 + (e[1] - guy) ** 2 <= (e[0] - sux) ** 2 + (e[1] - svy) ** 2]
    sc = [e for e in ends if e not in gc]
    gsink = (sum(p[0] for p in gc) / len(gc), sum(p[1] for p in gc) / len(gc)) if gc else (gux, guy)
    ssink = (sum(p[0] for p in sc) / len(sc), sum(p[1] for p in sc) / len(sc)) if sc else (sux, svy)
    gpx, spx = (u2px(gsink[0]), v2py(gsink[1])), (u2px(ssink[0]), v2py(ssink[1]))
    rscale = max(0.6, min(1.0, min(fw, fh) / 160))
    deep_r, shallow_r = 13.0 * rscale, 5.0 * rscale

    # evenly-spaced streamlines (Jobard–Lefebvre, seed-based)
    cell = max(min_sep, 0.5)
    occ: dict = {}

    def gkey(px, py):
        return (int((px - fx0) / cell), int((py - fy0) / cell))

    def too_close(px, py):
        # exempt a capture radius near each sink so tributaries reach the rim
        if math.hypot(px - gpx[0], py - gpx[1]) < deep_r + 1.2 * min_sep:
            return False
        if math.hypot(px - spx[0], py - spx[1]) < shallow_r + 1.2 * min_sep:
            return False
        gk = gkey(px, py)
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                for qx, qy in occ.get((gk[0] + di, gk[1] + dj), []):
                    if (px - qx) ** 2 + (py - qy) ** 2 < min_sep * min_sep:
                        return True
        return False

    def register(pts):
        for px, py in pts:
            occ.setdefault(gkey(px, py), []).append((px, py))

    h = 0.02 * rk4_dt

    def trace(u, v):
        pts = [(u2px(u), v2py(v))]
        skey = None
        for _ in range(max_steps):
            gx, gy = gradL(u, v)
            if math.hypot(gx, gy) < settle_eps:
                break
            k1 = rhs(u, v)
            k2 = rhs(u + 0.5 * h * k1[0], v + 0.5 * h * k1[1])
            k3 = rhs(u + 0.5 * h * k2[0], v + 0.5 * h * k2[1])
            k4 = rhs(u + h * k3[0], v + h * k3[1])
            u += h / 6 * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0])
            v += h / 6 * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1])
            px, py = u2px(u), v2py(v)
            if math.hypot(px - gpx[0], py - gpx[1]) < deep_r + 0.6:
                skey = "b"
                break
            if math.hypot(px - spx[0], py - spx[1]) < shallow_r + 0.6:
                skey = "p"
                break
            if not keep((px, py)) or too_close(px, py):
                break
            pts.append((px, py))
        if skey is None:
            db = (pts[-1][0] - gpx[0]) ** 2 + (pts[-1][1] - gpx[1]) ** 2
            dp = (pts[-1][0] - spx[0]) ** 2 + (pts[-1][1] - spx[1]) ** 2
            skey = "b" if db <= dp else "p"
        return pts, skey

    grid_n = max(6, int(math.sqrt(n_seeds)))
    starts = []
    for i in range(grid_n):
        for j in range(grid_n):
            su = -1.05 + 2.1 * (i + 0.5) / grid_n + rng.uniform(-0.3, 0.3) * (2.1 / grid_n)
            sv = -1.05 + 2.1 * (j + 0.5) / grid_n + rng.uniform(-0.3, 0.3) * (2.1 / grid_n)
            starts.append((su, sv))
    rng.shuffle(starts)

    streams = []  # (pts, skey, start_uv)
    for su, sv in starts:
        p0 = (u2px(su), v2py(sv))
        if not keep(p0) or too_close(*p0):
            continue
        pts, skey = trace(su, sv)
        if len(pts) < 4:
            continue
        register(pts)
        streams.append((pts, skey, (su, sv)))

    # the hero: the blue-basin tributary starting farthest up-plateau
    hero_idx = -1
    best_d = -1.0
    for i, (pts, skey, st) in enumerate(streams):
        if skey == "b":
            d = (st[0] - gsink[0]) ** 2 + (st[1] - gsink[1]) ** 2
            if d > best_d:
                best_d, hero_idx = d, i

    # draw the field: black plateau, destination-hued last stretch
    for i, (pts, skey, _st) in enumerate(streams):
        if i == hero_idx:
            continue
        ncut = max(1, int(len(pts) * 0.85))
        out += _poly(pts[: ncut + 1], color=black, f=feed)
        tail = pts[ncut:]
        if len(tail) >= 2:
            out += _poly(tail, color=(blue if skey == "b" else pink), f=feed)

    # the OVERSHOOT braid — heavy-ball momentum into the deep sink
    def offset_poly(pts, d):
        n = len(pts)
        res = []
        for i, (px, py) in enumerate(pts):
            ax, ay = pts[max(0, i - 1)]
            bx, by = pts[min(n - 1, i + 1)]
            tx, ty = bx - ax, by - ay
            L = math.hypot(tx, ty) or 1.0
            res.append((px - ty / L * d, py + tx / L * d))
        return res

    if hero_idx >= 0:
        u, v = streams[hero_idx][2]
        vel = [0.0, 0.0]
        path = [(u2px(u), v2py(v))]
        spd = [0.0]
        left = False
        for _ in range(max_steps):
            gx, gy = gradL(u, v)
            vel[0] = momentum * vel[0] - 0.03 * gx
            vel[1] = momentum * vel[1] - 0.03 * gy
            u += vel[0]
            v += vel[1]
            px, py = u2px(u), v2py(v)
            if not keep((px, py)):
                break
            path.append((px, py))
            spd.append(math.hypot(vel[0], vel[1]))
            near = (u - gsink[0]) ** 2 + (v - gsink[1]) ** 2
            if near > 0.09:
                left = True
            if left and near < 0.02 and math.hypot(vel[0], vel[1]) < 0.006:
                break
        smax = max(spd) or 1.0
        out += _poly(path, color=blue, f=feed)  # center pass always
        for d in (-0.38, 0.38):  # outer passes only on the fast opening reach
            seg = []
            for i, p in enumerate(path):
                if spd[i] > 0.4 * smax:
                    seg.append(p)
                elif len(seg) >= 2:
                    out += _poly(offset_poly(seg, d), color=blue, f=feed)
                    seg = []
                else:
                    seg = []
            if len(seg) >= 2:
                out += _poly(offset_poly(seg, d), color=blue, f=feed)

    # the sinks: hierarchy at 3m
    out += circle(gpx[0], gpx[1], deep_r + 2.5, pen=black, f=feed)  # one seating ring = a well
    out += fill_disc(gpx[0], gpx[1], deep_r, spacing=0.5, pen=blue, f=feed)
    out += fill_disc(spx[0], spx[1], shallow_r, spacing=0.5, pen=pink, f=feed)
    out += dotted_circle(spx[0], spx[1], shallow_r + 4, pen=pink, bounds=bounds, f=feed)

    # furniture on a shared left axis
    xT = x0 + 0.02 * W
    out += type_block(["WATER", "SHED"], xT, y1 - 6.0, height=3.2, pen=black, f=feed)
    out += _stroke_text(
        _spaced("EVERY START FINDS THE VALLEY"), xT, y1 - 20.0, 2.0, color=black, f=feed
    )
    out += swatch_bar(x1 - 9.0, y1 - 4.0, [black, blue, pink], size=2.6, f=feed)
    sad = (u2px((gsink[0] + ssink[0]) / 2), v2py((gsink[1] + ssink[1]) / 2))
    out += plus_mark(sad[0], sad[1], s=1.4, pen=black, f=feed)
    out += scale_footer(bounds, text="DTH = -GRAD L . DT", pen=black, height=2.4, f=feed)
    return out


def bauhaus_gradient_v1(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 3,
    levels: int = 14,
    steps: int = 70,
    lr: float = 0.22,
    feed: int = 2200,
) -> List[GCodeCommand]:
    """RETIRED (kept for version history, deregistered). The original GRADIENT
    DESCENT: a two-bowl loss landscape as thin contour ellipses with a bold pink
    descent path + step dots. Superseded by the WATERSHED rework of
    ``bauhaus_gradient`` — flagged as textbook/schematic by the studio critics."""
    x0, y0, x1, y1 = bounds
    W, H = x1 - x0, y1 - y0
    out: List[GCodeCommand] = []
    blue, pink, black = _pen(BLUE, colors), _pen(PINK, colors), _pen(BLACK, colors)
    cx_, cy_ = x0 + 0.54 * W, y0 + 0.5 * H

    m1 = (cx_ - 0.16 * W, cy_ - 0.07 * H)  # global minimum
    m2 = (cx_ + 0.22 * W, cy_ + 0.13 * H)  # shallow second bowl

    def loss(px, py):
        d1 = ((px - m1[0]) / (0.30 * W)) ** 2 + ((py - m1[1]) / (0.26 * H)) ** 2
        d2 = ((px - m2[0]) / (0.20 * W)) ** 2 + ((py - m2[1]) / (0.18 * H)) ** 2
        return min(d1, 0.35 + 0.8 * d2)

    # marching-squares-lite: sample a grid, draw iso segments per cell
    nxg, nyg = 90, 62
    gx = [x0 + 4 + (W - 8) * i / (nxg - 1) for i in range(nxg)]
    gy = [y0 + 8 + (H - 16) * j / (nyg - 1) for j in range(nyg)]
    field = [[loss(px, py) for py in gy] for px in gx]
    vmax = 1.15
    for lv in range(1, levels + 1):
        iso = vmax * (lv / levels) ** 1.4
        for i in range(nxg - 1):
            for j in range(nyg - 1):
                quad = (field[i][j], field[i + 1][j], field[i + 1][j + 1], field[i][j + 1])
                pts_c = []
                corners = [
                    (gx[i], gy[j]),
                    (gx[i + 1], gy[j]),
                    (gx[i + 1], gy[j + 1]),
                    (gx[i], gy[j + 1]),
                ]
                for k in range(4):
                    a_, b_ = quad[k], quad[(k + 1) % 4]
                    if (a_ < iso) != (b_ < iso):
                        t = (iso - a_) / (b_ - a_)
                        pa, pb = corners[k], corners[(k + 1) % 4]
                        pts_c.append((pa[0] + (pb[0] - pa[0]) * t, pa[1] + (pb[1] - pa[1]) * t))
                if len(pts_c) >= 2:
                    out += _poly(pts_c[:2], color=black, f=feed)

    # descent path from a seeded start, bold pink with step dots
    px, py = x0 + W * rng.uniform(0.20, 0.30), y0 + H * rng.uniform(0.78, 0.88)
    path = [(px, py)]
    for _ in range(steps):
        e = 1.5
        gx_ = (loss(px + e, py) - loss(px - e, py)) / (2 * e)
        gy_ = (loss(px, py + e) - loss(px, py - e)) / (2 * e)
        px -= lr * W * gx_
        py -= lr * H * gy_
        path.append((px, py))
    for o in (-0.35, 0.0, 0.35):
        out += _poly([(p_[0], p_[1] + o) for p_ in path], color=pink, f=feed)
    for k, (sx, sy) in enumerate(path[:: max(1, steps // 14)]):
        out += fill_disc(sx, sy, 1.0, spacing=0.45, pen=pink, f=feed)
    out += fill_disc(m1[0], m1[1], 3.2, spacing=0.5, pen=blue, f=feed)
    out += dotted_circle(m2[0], m2[1], 6.0, pen=black, bounds=bounds, f=feed)

    out += type_block(["GRADIENT", "DESCENT"], x0 + 5.0, y1 - 6.0, pen=black, f=feed)
    out += swatch_bar(x0 + 5.0, y1 - 22.0, [black, blue, pink], f=feed)
    out += plus_mark(x1 - 9.0, y1 - 9.0, pen=black, f=feed)
    out += scale_footer(bounds, pen=black, f=feed)
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
    from .generators import harmonograph

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
# FORWARD PASS, rethought — the weight matrix as an Anni-Albers weave draft.
# A network layer IS a grid of connections = a loom. Warp (blue) = inputs,
# weft (pink) = outputs; at each crossing the thread on TOP is set by the real
# weight's SIGN, its FLOAT length by magnitude. Not a wiring diagram — a textile
# that happens to be the exact matrix.
# ---------------------------------------------------------------------------


def bauhaus_loom(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 3,
    weights: str = "",
    block: int = 0,
    n_warp: int = 52,
    n_weft: int = 34,
    feed: int = 2200,
) -> List[GCodeCommand]:
    """FORWARD PASS as weaving: a real weight matrix woven as warp/weft threads,
    over/under by sign, float by magnitude. Bauhaus by lineage (the weaving
    workshop), true by construction (it is the matrix), lines by nature."""
    import numpy as np

    x0, y0, x1, y1 = bounds
    W, H = x1 - x0, y1 - y0
    blue, pink, black = _pen(BLUE, colors), _pen(PINK, colors), _pen(BLACK, colors)
    out: List[GCodeCommand] = []

    Wm = None
    if weights:
        try:
            Wm = _load_qkv(weights, block)[0]  # query matrix
        except Exception:
            Wm = None
    if Wm is None:
        Wm = np.array([[rng.random() * 2 - 1 for _ in range(96)] for _ in range(96)])

    # block-mean downsample to n_warp x n_weft, keep sign + magnitude
    R0, C0 = Wm.shape
    br, bc = max(1, R0 // n_warp), max(1, C0 // n_weft)
    M = np.zeros((n_warp, n_weft))
    for i in range(n_warp):
        for j in range(n_weft):
            blk = Wm[i * br : (i + 1) * br, j * bc : (j + 1) * bc]
            if blk.size:
                M[i, j] = math.copysign(float(np.abs(blk).mean()), float(blk.mean()))
    # sort warp rows + weft cols by mean weight so same-sign regions CLUSTER —
    # a legitimate neuron reorder (permutation-invariant), revealing the block/
    # diagonal structure a trained matrix hides in arbitrary index order.
    ri = sorted(range(n_warp), key=lambda i: float(M[i].mean()))
    ci = sorted(range(n_weft), key=lambda j: float(M[:, j].mean()))
    M = M[np.ix_(ri, ci)]
    norm = float(np.percentile(np.abs(M), 92)) or 1.0

    # the tapestry fills the page (dominant mass); title band above, footer below
    mx0, mx1 = x0 + 6, x1 - 6
    my0, my1 = y0 + 16, y1 - 20
    dx = (mx1 - mx0) / (n_warp - 1)
    dy = (my1 - my0) / (n_weft - 1)
    gap = min(dx, dy) * 0.34  # the interlace gap: the under-thread ducks here

    def strong(w):
        return abs(w) / norm > 0.85  # heaviest floats get a second pass (sheen)

    # WARP threads (vertical, blue) — broken where the warp dips UNDER (w < 0)
    for i in range(n_warp):
        xi = mx0 + i * dx
        cuts = []
        for j in range(n_weft):
            if M[i, j] < 0:  # weft on top here -> warp ducks under
                yj = my0 + j * dy
                cuts.append((yj - gap, yj + gap))
        yptr = my0
        segs = []
        for a, b in cuts:
            if a > yptr:
                segs.append((yptr, a))
            yptr = max(yptr, b)
        if yptr < my1:
            segs.append((yptr, my1))
        for a, b in segs:
            out += _poly([(xi, a), (xi, b)], color=blue, f=feed)

    # WEFT threads (horizontal, pink) — broken where the weft dips UNDER (w >= 0)
    for j in range(n_weft):
        yj = my0 + j * dy
        cuts = []
        for i in range(n_warp):
            if M[i, j] >= 0:  # warp on top -> weft ducks under
                xi = mx0 + i * dx
                cuts.append((xi - gap, xi + gap))
        xptr = mx0
        segs = []
        for a, b in cuts:
            if a > xptr:
                segs.append((xptr, a))
            xptr = max(xptr, b)
        if xptr < mx1:
            segs.append((xptr, mx1))
        for a, b in segs:
            out += _poly([(a, yj), (b, yj)], color=pink, f=feed)
            if b - a > dx * 2.4:  # a long float catches the light -> doubled
                out += _poly([(a, yj + 0.25), (b, yj + 0.25)], color=pink, f=feed)

    # black selvage: the woven edge, framing the cloth (the only closed rects)
    out += _poly(
        [
            (mx0 - 2, my0 - 2),
            (mx1 + 2, my0 - 2),
            (mx1 + 2, my1 + 2),
            (mx0 - 2, my1 + 2),
            (mx0 - 2, my0 - 2),
        ],
        color=black,
        f=feed,
    )

    # type: title top-left over the cloth's head, spec footer
    out += type_block(["FORWARD PASS"], x0 + 4, y1 - 4, height=3.0, pen=black, f=feed)
    out += _stroke_text(_spaced("THE WEIGHTS, WOVEN"), x0 + 4, y1 - 11, 2.2, color=black, f=feed)
    out += swatch_bar(x1 - 8, y1 - 4, [black, blue, pink], size=1.8, f=feed)
    out += scale_footer(
        bounds, text="LAYER Q  52x34  WARP=IN WEFT=OUT", pen=black, height=2.2, f=feed
    )
    return out


# ---------------------------------------------------------------------------
# piece 08 — DECISION SURFACE (the network as its function, not its wiring)
# ---------------------------------------------------------------------------


def bauhaus_decision(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 3,
    weights: str = "",
    block: int = 0,
    hidden: int = 6,
    n_points: int = 120,
    margin: float = 0.22,
    boundary_passes: int = 3,
    grid: int = 140,
    feed: int = 2200,
) -> List[GCodeCommand]:
    """DECISION SURFACE — a neural network drawn as its decision FUNCTION, not
    its wiring. A small readout f(u,v)=Σ aᵢ·tanh(Wᵢ·[u,v]+bᵢ) scores the input
    plane; the bold black knife is the EXACT iso-0 contour (marching squares),
    flanked by ±margin shoulders and the hidden-unit hyperplane creases the cut
    visibly kinks on (the fingerprint of composition — no neuron drawn). Every
    dot is coloured by the TRUE sign of f: blue = class +1, pink = class −1.
    Trained query directions drive the readout when a checkpoint is given."""
    import numpy as np

    x0, y0, x1, y1 = bounds
    W, H = x1 - x0, y1 - y0
    blue, pink, black = _pen(BLUE, colors), _pen(PINK, colors), _pen(BLACK, colors)
    out: List[GCodeCommand] = []

    # bands: title on top, field in the middle, footer below → the corner→corner
    # cut lives in the field and never fights the type.
    title_h, foot_h = 24.0, 12.0
    fx0, fx1 = x0 + 6.0, x1 - 6.0
    fy0, fy1 = y0 + foot_h, y1 - title_h
    fw, fh = fx1 - fx0, fy1 - fy0
    keep = _rect_keep((fx0, fy0, fx1, fy1))

    def px2u(px: float) -> float:
        return (px - fx0) / fw * 2.0 - 1.0

    def py2v(py: float) -> float:
        return (py - fy0) / fh * 2.0 - 1.0

    def u2px(u: float) -> float:
        return fx0 + (u + 1.0) / 2.0 * fw

    def v2py(v: float) -> float:
        return fy0 + (v + 1.0) / 2.0 * fh

    # ---- the readout f(u,v) = Σ aᵢ tanh(Wᵢ·[u,v] + bᵢ) --------------------
    Wq = None
    if weights:
        try:
            Wq = _load_qkv(weights, block)[0]  # trained query matrix (~96×96)
        except Exception:
            Wq = None

    def build_field(attempt: int):
        """Return (W1, b1, a). Real path rotates which trained columns feed the
        2D readout; fallback re-draws seeded gaussians at a shrinking scale."""
        if Wq is not None:
            C = Wq.shape[1]
            c = (attempt * 2) % max(1, C - 3)
            W1 = np.array(Wq[:hidden, c : c + 2], dtype=float)
            b1 = np.array([float(Wq[i, (c + 2) % C]) for i in range(hidden)])
            a = np.array(
                [
                    float(np.linalg.norm(Wq[i, :hidden]))
                    * (1.0 if float(Wq[i].mean()) >= 0 else -1.0)
                    for i in range(hidden)
                ]
            )
        else:
            sc = 1.6 * (0.82**attempt)
            W1 = np.array([[rng.gauss(0, sc) for _ in range(2)] for _ in range(hidden)])
            b1 = np.array([rng.gauss(0, 0.55) for _ in range(hidden)])
            a = np.array([rng.gauss(0, 1.0) for _ in range(hidden)])
        # normalise input scale so tanh isn't saturated flat
        s = float(np.abs(W1).mean()) or 1.0
        W1 = W1 / s * 1.7
        return W1, b1, a

    def eval_grid(W1, b1, a, us, vs):
        U, V = np.meshgrid(us, vs)  # (ny, nx) → F[j][i], j indexes vs/ys
        F = np.zeros_like(U)
        for i in range(hidden):
            F += a[i] * np.tanh(W1[i, 0] * U + W1[i, 1] * V + b1[i])
        return F

    def chains_at(F_list, xs, ys, iso, minlen=6):
        segs = _marching_squares(F_list, xs, ys, iso)
        return [c for c in _chain_segments(segs) if len(c) >= minlen]

    def span(ch):
        xs_ = [p[0] for p in ch]
        ys_ = [p[1] for p in ch]
        return math.hypot(max(xs_) - min(xs_), max(ys_) - min(ys_))

    # ---- boundary-quality gate: pick the cleanest single folded knife -------
    cxs = [fx0 + i * (fw / 44) for i in range(45)]
    cys = [fy0 + j * (fh / 44) for j in range(45)]
    cus = np.array([px2u(x) for x in cxs])
    cvs = np.array([py2v(y) for y in cys])
    best = None
    for attempt in range(8):
        W1, b1, a = build_field(attempt)
        Fc = eval_grid(W1, b1, a, cus, cvs).tolist()
        chs = chains_at(Fc, cxs, cys, 0.0)
        if not chs:
            continue
        dom = max(chs, key=span)

        def diag_score(ch):
            xs_ = [p[0] for p in ch]
            ys_ = [p[1] for p in ch]
            dx, dy = max(xs_) - min(xs_), max(ys_) - min(ys_)
            aspect = min(dx, dy) / (max(dx, dy) + 1e-9)  # 1 → true diagonal
            return span(ch) * (0.35 + 0.65 * aspect)

        # fewest components, then the longest chain that best spans the diagonal
        score = (len(chs), -diag_score(dom))
        if best is None or score < best[0]:
            best = (score, (W1, b1, a))
    if best is None:
        W1, b1, a = build_field(0)
    else:
        W1, b1, a = best[1]

    # ---- fine field, reused for boundary + both margins --------------------
    xs = [fx0 + i * (fw / grid) for i in range(grid + 1)]
    ys = [fy0 + j * (fh / grid) for j in range(grid + 1)]
    us = np.array([px2u(x) for x in xs])
    vs = np.array([py2v(y) for y in ys])
    Fnp = eval_grid(W1, b1, a, us, vs)
    # normalise field magnitude so `margin` is a consistent fraction of the
    # range whatever the weight source (the iso-0 cut is scale-invariant, so
    # only the shoulders + point classification depend on this).
    fscale = float(np.percentile(np.abs(Fnp), 88)) or 1.0
    a = a / fscale
    F_list = (Fnp / fscale).tolist()

    def offset_poly(pts, d):
        n = len(pts)
        res = []
        for i, (px, py) in enumerate(pts):
            ax, ay = pts[max(0, i - 1)]
            bx, by = pts[min(n - 1, i + 1)]
            tx, ty = bx - ax, by - ay
            L = math.hypot(tx, ty) or 1.0
            res.append((px - ty / L * d, py + tx / L * d))
        return res

    # ---- MARGIN SHOULDERS first (thin, so the knife overprints them) -------
    for iso in (margin, -margin):
        for ch in chains_at(F_list, xs, ys, iso):
            for r in _clip_runs([ch], keep):
                out += _poly(r, color=black, f=feed)

    # ---- THE DECISION CUT: iso-0, the hero. The curve is already piecewise-
    # bent (a NETWORK's boundary, not one perceptron's straight line); drawn as
    # a solid multi-line knife. Secondary components stay a single quiet stroke.
    b_chains = sorted(chains_at(F_list, xs, ys, 0.0), key=span, reverse=True)
    for ci, ch in enumerate(b_chains):
        for r in _clip_runs([ch], keep):
            if len(r) < 2:
                continue
            offs = [-0.5, -0.25, 0.0, 0.25, 0.5] if ci == 0 else [0.0]
            for d in offs:
                out += _poly(offset_poly(r, d) if d else r, color=black, f=feed)

    # ---- POINT CLOUDS labelled by the true sign of f ----------------------
    def fval(u, v):
        return sum(
            float(a[i]) * math.tanh(float(W1[i, 0]) * u + float(W1[i, 1]) * v + float(b1[i]))
            for i in range(hidden)
        )

    def dot(cx, cy, r, pen):
        turns = max(1, int(r / 0.55))
        n = max(10, int(r * 16))
        pts = []
        for k in range(n + 1):
            t = k / n
            ang = 2 * math.pi * turns * t
            pts.append((cx + r * t * math.cos(ang), cy + r * t * math.sin(ang)))
        return _poly(pts, color=pen, f=feed)

    # 1:2 blue:pink mass — pink is the dense, loud field. A CLEAR corridor
    # (|f|<0.7·margin) hugs the cut; a few big "support vector" discs sit on the
    # shoulders (0.7·margin ≤ |f| < 1.5·margin); the rest is the small field.
    n_blue = n_points // 3
    n_pink = n_points - n_blue
    want = {"b": n_blue, "p": n_pink}
    got = {"b": [], "p": []}
    sup = {"b": 0, "p": 0}
    SUPMAX = 5
    typebox = lambda px, py: px < fx0 + 0.30 * fw and py > fy1 - 0.14 * fh
    tries = 0
    while (len(got["b"]) < n_blue or len(got["p"]) < n_pink) and tries < 12000:
        tries += 1
        px = rng.uniform(fx0 + 2, fx1 - 2)
        py = rng.uniform(fy0 + 2, fy1 - 2)
        if typebox(px, py):
            continue
        val = fval(px2u(px), py2v(py))
        key = "b" if val >= 0 else "p"
        if len(got[key]) >= want[key]:
            continue
        av = abs(val)
        if av < 0.7 * margin:  # the spine corridor stays a clean void
            continue
        if av < 1.5 * margin:  # support shoulder — a few big discs only
            if sup[key] >= SUPMAX:
                continue
            sup[key] += 1
            got[key].append((px, py, True))
        else:
            got[key].append((px, py, False))
    for px, py, is_sup in got["b"]:
        out += dot(px, py, 2.1 if is_sup else 1.0, blue)
    for px, py, is_sup in got["p"]:
        out += dot(px, py, 2.1 if is_sup else 1.0, pink)

    # ---- FURNITURE on a shared left axis ----------------------------------
    xT = x0 + 0.02 * W
    out += type_block(["DECISION", "SURFACE"], xT, y1 - 5.0, height=3.2, pen=black, f=feed)
    out += _stroke_text(
        _spaced("THE CUT THROUGH INPUT SPACE"), xT, y1 - 19.0, 2.0, color=black, f=feed
    )
    out += swatch_bar(x1 - 9.0, y1 - 4.0, [black, blue, pink], size=2.6, f=feed)
    out += plus_mark(fx1 - 0.16 * fw, fy0 + 0.12 * fh, s=1.4, pen=black, f=feed)
    out += scale_footer(bounds, text="F(X)=SIGN(W.X+B)", pen=black, height=2.4, f=feed)
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


# ---------------------------------------------------------------------------
# piece 10 — THE LONG NOW (LSTM cell state as one modulated memory band)
# ---------------------------------------------------------------------------


def bauhaus_conveyor(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 3,
    weights: str = "",
    block: int = 0,
    steps: int = 64,
    forget_events: int = 2,
    write_events: int = 4,
    band_max_frac: float = 0.20,
    full_pitch: float = 0.9,
    void_pitch: float = 5.0,
    feed: int = 2200,
) -> List[GCodeCommand]:
    """THE LONG NOW — an LSTM's memory carried through time. The exact cell
    update cₜ = fₜ·cₜ₋₁ + iₜ·gₜ runs across `steps`; the black conveyor band's
    thickness AND ink density are |cₜ| (dense = strong memory, near-void where it
    decays). Forget gates pinch the band to a thread; pink write-stitches inject
    new information into one selvage; a thin blue ghost shows the prior value
    being overwritten. Time is the horizontal axis."""
    x0, y0, x1, y1 = bounds
    W, H = x1 - x0, y1 - y0
    blue, pink, black = _pen(BLUE, colors), _pen(PINK, colors), _pen(BLACK, colors)
    out: List[GCodeCommand] = []

    dt = (0.78 * W) / steps
    A = band_max_frac * H
    yb = y0 + 0.46 * H
    xL = x0 + 0.20 * W

    # gate schedule — the fallback runs the SAME true recurrence as a real ckpt
    f = [0.80 + 0.19 * rng.fbm(t * 0.11, 7.3) for t in range(steps)]
    ig = [(0.15 + 0.10 * rng.fbm(t * 0.09, 2.1)) * (2.0 * rng.fbm(t * 0.07, 9.9) - 1.0) for t in range(steps)]

    def scatter(nev):
        idx = []
        for k in range(nev):
            base = (k + 1) / (nev + 1)
            idx.append(int(min(steps - 2, max(1, (base + rng.uniform(-0.05, 0.05)) * steps))))
        return sorted(set(idx))

    forgets = scatter(forget_events)
    writes = scatter(write_events)
    for t in forgets:
        f[t] = 0.06  # a scripted pinch-to-thread
    deepest = forgets[len(forgets) // 2] if forgets else 0
    for w in writes:
        ig[w] = rng.choice([-1, 1]) * 0.9  # a strong signed injection
    # the write just after the deepest forget is the loudest (cause & effect)
    after = min([w for w in writes if w > deepest], default=None)
    if after is not None:
        ig[after] = math.copysign(1.15, ig[after])

    c = 0.0
    c_now, c_prev = [], []
    for t in range(steps):
        c_prev.append(c)
        c = f[t] * c + ig[t]
        c_now.append(c)
    cmax = max(1e-6, max(abs(v) for v in c_now))
    h = [max(0.6, A * abs(v) / cmax) for v in c_now]

    xc = [xL + (t + 0.5) * dt for t in range(steps)]

    # body — aligned horizontal striations clipped to the tube envelope: the
    # number of lines at each column IS |cₜ|, so the ribbon swells with memory
    # and collapses toward the baseline through a forget (density = tone).
    nlev = int(A / full_pitch) + 1
    for k in range(nlev + 1):
        off = k * full_pitch
        if off > A + 1e-6:
            break
        for sgn in ((1, -1) if k > 0 else (1,)):
            run: List[Tuple[float, float]] = []
            for t in range(steps):
                if h[t] >= off:
                    run.append((xc[t], yb + sgn * off))
                elif len(run) >= 2:
                    out += _poly(run, color=black, f=feed)
                    run = []
                else:
                    run = []
            if len(run) >= 2:
                out += _poly(run, color=black, f=feed)

    # smooth tube selvages (the rounded memory ribbon) + through-baseline
    out += _poly([(xc[t], yb + h[t]) for t in range(steps)], color=black, f=feed)
    out += _poly([(xc[t], yb - h[t]) for t in range(steps)], color=black, f=feed)
    out += _poly([(xL, yb), (xc[-1], yb)], color=black, f=feed)

    # blue prior-memory ghost in a clear lane below the band
    yg = yb - A - 4.0
    out += _poly([(xc[t], yg - A * 0.35 * abs(c_prev[t]) / cmax) for t in range(steps)], color=blue, f=feed)

    # pink write-stitches into one selvage (sign of c picks top/bottom)
    for w in writes:
        top = c_now[w] >= 0
        y_from = yb + h[w] if top else yb - h[w]
        length = min(0.9 * h[w], A * abs(ig[w]) / cmax * 1.4)
        length *= 1.3 if w == after else 1.0
        y_to = y_from - length if top else y_from + length
        out += _poly([(xc[w], y_from), (xc[w], y_to)], color=pink, f=feed)

    # forget anchor — the singularity of forgetting, on the baseline
    out += plus_mark(xc[deepest], yb, s=1.4, pen=black, f=feed)

    xT = x0 + 0.02 * W
    out += type_block(["THE LONG", "NOW"], xT, yb + 0.24 * H, height=3.2, pen=black, f=feed)
    out += _stroke_text(_spaced("FORGET . WRITE . CARRY"), xT, yb + 0.10 * H, 2.0, color=black, f=feed)
    out += swatch_bar(xT, yb - 0.02 * H, [black, blue, pink], size=2.6, f=feed)
    real = bool(weights)
    out += scale_footer(
        bounds,
        text=("GATES REAL RECURRENCE EXACT" if real else "GATES SYNTHETIC RECURRENCE EXACT"),
        pen=black,
        height=2.2,
        f=feed,
    )
    return out


# ---------------------------------------------------------------------------
# piece 11 — SETTLING (the perceptron boundary as a rotating sweep of errors)
# ---------------------------------------------------------------------------


def bauhaus_settling(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 3,
    weights: str = "",
    block: int = 0,
    n_points: int = 90,
    margin_gap: float = 0.14,
    eta: float = 1.0,
    max_epochs: int = 40,
    ghost_lines: int = 16,
    final_passes: int = 3,
    feed: int = 2200,
) -> List[GCodeCommand]:
    """SETTLING — a perceptron's decision boundary drawn as MOTION: the line
    that its own errors pushed into place. Real online Rosenblatt updates on a
    seeded separable cloud leave a fan of successive boundary positions (black,
    ghosting from wild to settled); the converged cut is the loud pink knife; the
    2-3 misclassified points that rotated the boundary most are the scarce large
    discs — the CAUSE of the cut. Time here is the learning."""
    x0, y0, x1, y1 = bounds
    W, H = x1 - x0, y1 - y0
    blue, pink, black = _pen(BLUE, colors), _pen(PINK, colors), _pen(BLACK, colors)
    out: List[GCodeCommand] = []

    fx0, fy0, fx1, fy1 = x0 + 0.24 * W, y0 + 8, x1 - 6, y1 - 8
    fw, fh = fx1 - fx0, fy1 - fy0
    fieldkeep = _rect_keep((fx0, fy0, fx1, fy1))

    def dx2px(x):
        return fx0 + (x + 1) / 2 * fw

    def dy2py(y):
        return fy0 + (y + 1) / 2 * fh

    def make_data(phi, theta):
        ws = (math.cos(phi), math.sin(phi))
        pts, lab = [], []
        tries = 0
        while len(pts) < n_points and tries < n_points * 25:
            tries += 1
            x = (rng.uniform(-1, 1), rng.uniform(-1, 1))
            s = ws[0] * x[0] + ws[1] * x[1] - theta
            if abs(s) < margin_gap:
                continue
            pts.append(x)
            lab.append(1 if s > 0 else -1)
        return pts, lab

    def train(pts, lab):
        w = [0.0, 0.0]
        b = 0.0
        hist = []
        for _ in range(max_epochs):
            updated = False
            for x, y in zip(pts, lab):
                if (1 if (w[0] * x[0] + w[1] * x[1] + b) > 0 else -1) != y:
                    w[0] += eta * y * x[0]
                    w[1] += eta * y * x[1]
                    b += eta * y
                    hist.append((w[0], w[1], b, x, y))
                    updated = True
            if not updated:
                break
        return w, b, hist

    # resample until the trajectory is long enough to read as a sweep
    best = None
    for _ in range(20):
        phi = rng.uniform(0.35, 0.75) * math.pi
        theta = rng.uniform(-0.15, 0.15)
        pts, lab = make_data(phi, theta)
        w, b, hist = train(pts, lab)
        if best is None or len(hist) > len(best[4]):
            best = (pts, lab, w, b, hist)
        if len(hist) >= ghost_lines:
            break
    pts, lab, wf, bf, hist = best

    def boundary_seg(wx, wy, bb):
        n2 = wx * wx + wy * wy
        if n2 < 1e-9:
            return [(fx0, fy0), (fx0, fy0)]
        ox, oy = -bb * wx / n2, -bb * wy / n2
        dx, dy = -wy, wx
        dl = math.hypot(dx, dy) or 1.0
        dx, dy = dx / dl, dy / dl
        L, N = 4.0, 48  # densify so _clip_runs keeps the in-rect portion
        p0 = (ox - L * dx, oy - L * dy)
        p1 = (ox + L * dx, oy + L * dy)
        return [
            (dx2px(p0[0] + (p1[0] - p0[0]) * t / N), dy2py(p0[1] + (p1[1] - p0[1]) * t / N))
            for t in range(N + 1)
        ]

    def offset_poly(p, d):
        n = len(p)
        res = []
        for i, (px, py) in enumerate(p):
            ax, ay = p[max(0, i - 1)]
            bx, by = p[min(n - 1, i + 1)]
            tx, ty = bx - ax, by - ay
            ln = math.hypot(tx, ty) or 1.0
            res.append((px - ty / ln * d, py + tx / ln * d))
        return res

    # thinned scatter — quiet context so the sweep dominates
    keepn = max(10, int(0.6 * len(pts)))
    for (x, y) in list(zip(pts, lab))[:keepn]:
        px, py = dx2px(x[0]), dy2py(x[1])
        if y > 0:
            out += fill_disc(px, py, 0.8, spacing=0.5, pen=blue, f=feed)
        else:
            out += circle(px, py, 0.9, pen=pink, f=feed)

    # the fan of past-guess boundaries — subsample by EVEN ANGLE of the normal
    # so it reads as one clean rotating sweep (a fan closing), not random sticks.
    ang_all = [math.atan2(h[1], h[0]) for h in hist]
    order = sorted(range(len(hist)), key=lambda i: ang_all[i])
    if len(order) <= ghost_lines:
        sel = order
    else:
        sel = [order[int(round(k * (len(order) - 1) / (ghost_lines - 1)))] for k in range(ghost_lines)]
    final_ang = math.atan2(wf[1], wf[0])
    for si in sel:
        wx, wy, bb, _, _ = hist[si]
        near = abs(math.atan2(math.sin(ang_all[si] - final_ang), math.cos(ang_all[si] - final_ang)))
        for r in _clip_runs([boundary_seg(wx, wy, bb)], fieldkeep):
            out += _poly(r, color=black, f=feed)
            if near < 0.12:  # the ghosts nearest the settled angle gain weight
                out += _poly(offset_poly(r, 0.3), color=black, f=feed)

    # the hero: the converged cut, a bold pink knife that dominates at 3m
    for r in _clip_runs([boundary_seg(wf[0], wf[1], bf)], fieldkeep):
        for d in (-0.7, -0.42, -0.14, 0.14, 0.42, 0.7):
            out += _poly(offset_poly(r, d), color=pink, f=feed)

    # the scarce accent — the culprit points that rotated the boundary most
    def angdiff(a, b):
        return math.atan2(math.sin(a - b), math.cos(a - b))

    angs = [math.atan2(h[1], h[0]) for h in hist]
    rot = [0.0] + [abs(angdiff(angs[i], angs[i - 1])) for i in range(1, len(hist))]
    top = sorted(range(len(hist)), key=lambda i: -rot[i])[:3]
    for i in top:
        _, _, _, cx, cy = hist[i]
        px, py = dx2px(cx[0]), dy2py(cx[1])
        _, _, _, _, yv = hist[i]
        out += fill_disc(px, py, 2.2, spacing=0.5, pen=(blue if yv > 0 else pink), f=feed)
        out += circle(px, py, 3.0, pen=black, f=feed)
    if top:
        _, _, _, c0, _ = hist[top[0]]
        out += plus_mark(dx2px(c0[0]), dy2py(c0[1]), s=1.2, pen=black, f=feed)

    xT = x0 + 0.02 * W
    out += type_block(["SETTLING"], xT, y1 - 6.0, height=3.2, pen=black, f=feed)
    out += _stroke_text(_spaced("THE LINE THAT ERRORS BUILT"), xT, y1 - 20.0, 2.0, color=black, f=feed)
    out += swatch_bar(xT, y1 - 26.0, [black, blue, pink], size=3.0, f=feed)
    out += scale_footer(bounds, text=f"W += Y X   {len(hist)} UPDATES", pen=black, height=2.4, f=feed)
    return out


# ---------------------------------------------------------------------------
# piece 12 — RELEVANCE TERRAIN (transformer Q·K score field as a sheared relief)
# ---------------------------------------------------------------------------


def bauhaus_relevance(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 3,
    weights: str = "",
    block: int = 0,
    head: int = 0,
    tokens: int = 40,
    temp: float = 1.0,
    levels: int = 16,
    level_floor: float = 0.45,
    grid: int = 110,
    shear_deg: float = 33.0,
    causal: bool = True,
    min_chain: int = 8,
    feed: int = 2200,
) -> List[GCodeCommand]:
    """RELEVANCE TERRAIN — a transformer's attention drawn as the LANDSCAPE of
    who-is-relevant-to-whom. The raw pre-softmax compatibility field S=Q·Kᵀ/√d is
    a relief; its marching-squares isolines (black), sheared so no framing axis
    survives, are the terrain. A blue ridgeline of summit discs marks each query's
    argmax key (the softmax verdict); the single global-max relevance is the one
    scarce pink peak. Real trained Q/K when a checkpoint is given."""
    import numpy as np

    x0, y0, x1, y1 = bounds
    W, H = x1 - x0, y1 - y0
    blue, pink, black = _pen(BLUE, colors), _pen(PINK, colors), _pen(BLACK, colors)
    out: List[GCodeCommand] = []

    fx0, fy0, fx1, fy1 = x0 + 0.20 * W, y0 + 8, x1 - 6, y1 - 8
    fw, fh = fx1 - fx0, fy1 - fy0
    frame_keep = _rect_keep((fx0, fy0, fx1, fy1))

    S = _attention_matrix(rng, tokens, head, temp, causal, weights, block, return_scores=True)
    A = _attention_matrix(rng, tokens, head, temp, causal, weights, block)  # softmax, for disc size
    S = np.asarray(S, dtype=float)

    # causal floor: the un-attendable upper triangle is a flat low plain, NOT a
    # −1e9 cliff (which would spawn a spurious inked boundary).
    if causal:
        low = float(S[np.tril_indices(tokens)].min())
        for q in range(tokens):
            for k in range(q + 1, tokens):
                S[q, k] = low - 0.05

    # bilinear upsample S(q,k) → F[j][i] over index coords (i≡key, j≡query)
    xs = [i * (tokens - 1) / grid for i in range(grid + 1)]
    ys = [j * (tokens - 1) / grid for j in range(grid + 1)]

    def bil(qf, kf):
        q0, k0 = int(qf), int(kf)
        q1, k1 = min(tokens - 1, q0 + 1), min(tokens - 1, k0 + 1)
        tq, tk = qf - q0, kf - k0
        return (
            S[q0, k0] * (1 - tq) * (1 - tk)
            + S[q0, k1] * (1 - tq) * tk
            + S[q1, k0] * tq * (1 - tk)
            + S[q1, k1] * tq * tk
        )

    F = [[bil(ys[j], xs[i]) for i in range(grid + 1)] for j in range(grid + 1)]

    # shear+rotate map from (k,q) index space to a normalized frame so the causal
    # diagonal becomes a mountain SPINE and no horizontal/vertical axis survives.
    sh = math.tan(math.radians(shear_deg))
    rot = math.radians(20.0)
    cs, sn = math.cos(rot), math.sin(rot)

    def raw(ki, qi):
        a, c = ki / (tokens - 1) - 0.5, qi / (tokens - 1) - 0.5
        a = a + sh * c
        return a * cs - c * sn, a * sn + c * cs

    corners = [raw(0, 0), raw(tokens - 1, 0), raw(0, tokens - 1), raw(tokens - 1, tokens - 1)]
    rxs = [p[0] for p in corners]
    rys = [p[1] for p in corners]
    bcx, bcy = (min(rxs) + max(rxs)) / 2, (min(rys) + max(rys)) / 2
    scale = 1.04 * max(fw / (max(rxs) - min(rxs)), fh / (max(rys) - min(rys)))
    fcx, fcy = (fx0 + fx1) / 2, (fy0 + fy1) / 2

    def to_paper(ki, qi):
        rx, ry = raw(ki, qi)
        return (fcx + (rx - bcx) * scale, fcy + (ry - bcy) * scale)

    # isolevels in percentile space of the VALID (lower-tri) scores; drop the
    # bottom ~level_floor so the low plain stays bare paper.
    valid = np.array([S[q, k] for q in range(tokens) for k in range(q + 1)])
    lo, hi = np.percentile(valid, 100 * level_floor), np.percentile(valid, 99)
    isos = [lo + (hi - lo) * (t + 0.5) / levels for t in range(levels)]

    for iso in isos:
        segs = _marching_squares(F, xs, ys, iso)
        for ch in _chain_segments(segs):
            if len(ch) < min_chain:
                continue
            # causal clip in index space, then shear to paper
            run = []
            for (kv, qv) in ch:
                if qv >= kv - 0.5:
                    run.append(to_paper(kv, qv))
                elif len(run) >= 2:
                    for r in _clip_runs([run], frame_keep):
                        out += _poly(r, color=black, f=feed)
                    run = []
                else:
                    run = []
            if len(run) >= 2:
                for r in _clip_runs([run], frame_keep):
                    out += _poly(r, color=black, f=feed)

    # blue argmax summit ridgeline — each query's chosen key (the softmax verdict)
    A = np.asarray(A, dtype=float)
    summits = []
    for q in range(tokens):
        ks = A[q, : q + 1] if causal else A[q]
        kstar = int(np.argmax(ks))
        summits.append((q, kstar, float(A[q, kstar])))
    rr = 0.02 * min(W, H)
    order = sorted(range(tokens), key=lambda q: -summits[q][2])
    big3 = set(order[:3])
    gq, gk, gp = max(summits, key=lambda s: s[2])  # the single global max
    for (q, kstar, p) in summits:
        if (q, kstar) == (gq, gk):
            continue
        px, py = to_paper(kstar, q)
        if not frame_keep((px, py)):
            continue
        r = max(1.4, rr * (0.4 + p) * 2.2)
        out += fill_disc(px, py, r, spacing=0.5, pen=blue, f=feed)
        if q in big3:
            out += fill_disc(px, py, max(0.8, r - 0.6), spacing=0.5, pen=blue, f=feed)

    # the one scarce pink peak — the single loudest relevance on the page
    px, py = to_paper(gk, gq)
    if frame_keep((px, py)):
        out += fill_disc(px, py, max(2.2, rr * (0.4 + gp) * 2.6), spacing=0.5, pen=pink, f=feed)
        out += circle(px, py, max(3.4, rr * (0.4 + gp) * 2.6 + 1.4), pen=pink, f=feed)

    xT = x0 + 0.02 * W
    out += type_block(["RELEVANCE", "TERRAIN"], xT, y1 - 7.0, height=3.2, pen=black, f=feed)
    out += _stroke_text(_spaced("WHO IS RELEVANT TO WHOM"), xT, y1 - 21.0, 2.0, color=black, f=feed)
    out += swatch_bar(x1 - 9.0, y1 - 4.0, [black, blue, pink], size=2.6, f=feed)
    p0 = to_paper(0, 0)
    out += plus_mark(p0[0], p0[1], s=1.4, pen=black, f=feed)
    out += scale_footer(bounds, text="S = Q.KT / SQRT D", pen=black, height=2.4, f=feed)
    return out


# ---------------------------------------------------------------------------
# piece 13 — MEMORY IN TIME (LSTM as a vertical figure-8 of information loops)
# ---------------------------------------------------------------------------


def bauhaus_memory(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 3,
    loops: int = 40,
    half: int = 130,
    precess: float = 0.5,
    grow: float = 1.0,
    feed: int = 2200,
) -> List[GCodeCommand]:
    """MEMORY IN TIME — an LSTM as a figure-8 of PRECESSING loops. The recurrence
    loops back every step (REMEMBER c_t above, FORGET c_{t-1} below, meeting at the
    hollow carried-state waist), but each iteration lands slightly ROTATED by the
    transformation it underwent — a helix / logarithmic spiral of nested loops,
    not one static 8. Gate leaders mark the input/forget/output gates. Black + red."""
    x0, y0, x1, y1 = bounds
    W, H = x1 - x0, y1 - y0
    accent, black = _pen(PINK, colors), _pen(BLACK, colors)  # PINK slot rendered crimson
    out: List[GCodeCommand] = []

    cx, cyw = x0 + 0.48 * W, y0 + 0.50 * H
    ru, rl, wx = 0.135 * H, 0.175 * H, 1.55  # top REMEMBER lobe, bigger FORGET lobe

    def rot(px, py, ph):
        c, s = math.cos(ph), math.sin(ph)
        return (px * c - py * s, px * s + py * c)

    # faint background orbits (the iterations echoing) + a light starfield
    for e in range(3):
        ea, eb = (0.34 + 0.05 * e) * W, (0.40 + 0.05 * e) * H
        erot = rng.uniform(-0.3, 0.3)
        seg = []
        for k in range(241):
            a = 2 * math.pi * k / 240
            ox, oy = rot(ea * 0.5 * math.cos(a), eb * 0.5 * math.sin(a), erot)
            if k % 6 < 3:
                seg.append((cx + ox, cyw + oy))
            elif len(seg) >= 2:
                out += _poly(seg, color=black, f=feed)
                seg = []
            else:
                seg = []
        if len(seg) >= 2:
            out += _poly(seg, color=black, f=feed)
    for _ in range(26):
        sxp, syp = rng.uniform(x0 + 4, x1 - 4), rng.uniform(y0 + 4, y1 - 4)
        out += _dot(sxp, syp, rng.uniform(0.3, 0.9), color=black, f=feed)

    # the precessing figure-8 family — each loop a rounded double-circle, rotated
    for i in range(loops):
        t = i / (loops - 1)
        sc = (0.26 + 0.74 * t) * (grow ** i)
        ph = precess * t  # monotonic precession: the swept helix of iterations
        jr = 1.0 + 0.04 * rng.gauss(0, 1)  # subtle per-iteration transformation
        pts = []
        for k in range(half + 1):  # upper lobe — REMEMBER
            a = 2 * math.pi * k / half
            ox, oy = rot(wx * ru * sc * jr * math.sin(a), ru * sc * (1 - math.cos(a)), ph)
            pts.append((cx + ox, cyw + oy))
        for k in range(half + 1):  # lower lobe — FORGET (bigger)
            a = 2 * math.pi * k / half
            ox, oy = rot(wx * rl * sc * jr * math.sin(a), -rl * sc * (1 - math.cos(a)), ph)
            pts.append((cx + ox, cyw + oy))
        pen = accent if (i % 3 == 0 or i >= loops - 2) else black
        out += _poly(pts, color=pen, f=feed)

    # the central line carries THREE points the helix connects: INPUT → LATENT → OUTPUT
    top_node, bot_node = cyw + 1.98 * ru, cyw - 1.98 * rl
    aT, aB = top_node + 11, bot_node - 11
    out += _poly([(cx, aB), (cx, aT)], color=black, f=feed)
    out += _poly([(cx - 1.6, aT - 4), (cx, aT), (cx + 1.6, aT - 4)], color=black, f=feed)
    out += _poly([(cx - 1.6, aB + 4), (cx, aB), (cx + 1.6, aB + 4)], color=black, f=feed)
    out += fill_disc(cx, top_node, 1.9, spacing=0.5, pen=black, f=feed)  # OUTPUT point
    out += fill_disc(cx, bot_node, 1.9, spacing=0.5, pen=black, f=feed)  # INPUT point
    out += circle(cx, cyw, 2.6, pen=accent, f=feed)  # LATENT — the carried state
    out += _stroke_text(_spaced("OUTPUT"), cx + 6, aT - 1.2, 2.3, color=black, f=feed)
    out += _stroke_text(_spaced("INPUT"), cx + 6, aB - 1.2, 2.3, color=black, f=feed)
    out += _stroke_text(_spaced("LATENT"), cx + 6, cyw - 1.2, 2.2, color=accent, f=feed)

    # lobe descriptions
    out += _stroke_text(_spaced("REMEMBER"), cx - 13, cyw + ru * 0.95, 2.2, color=black, f=feed)
    out += _stroke_text(_spaced("C T"), cx - 4, cyw + ru * 0.95 - 5.2, 1.9, color=black, f=feed)
    out += _stroke_text(_spaced("FORGET"), cx - 11, cyw - rl * 0.98, 2.2, color=black, f=feed)
    out += _stroke_text(_spaced("C T-1"), cx - 6, cyw - rl * 0.98 - 5.2, 1.9, color=black, f=feed)

    # gate leaders (dot on an outer loop → dashed leader → label)
    def leader(px, py, lx, ly, l1, l2):
        out.extend(_dot(px, py, 1.4, color=black, f=feed))
        n = 7
        for s in range(0, n, 2):
            a = (px + (lx - px) * s / n, py + (ly - py) * s / n)
            b = (px + (lx - px) * (s + 1) / n, py + (ly - py) * (s + 1) / n)
            out.extend(_poly([a, b], color=black, f=feed))
        out.extend(_stroke_text(_spaced(l1), lx - 0.14 * W, ly + 2.2, 2.0, color=black, f=feed))
        out.extend(_stroke_text(_spaced(l2), lx - 0.14 * W, ly - 2.4, 1.8, color=black, f=feed))

    og = rot(-wx * ru, ru, precess * 0.5)
    ig = rot(wx * ru, ru * 0.4, precess * 0.5)
    fg = rot(-wx * rl, -rl, precess * 0.5)
    leader(cx + og[0], cyw + og[1], x0 + 0.14 * W, cyw + 0.22 * H, "OUTPUT GATE", "O T")
    leader(cx + ig[0], cyw + ig[1], x1 - 0.05 * W, cyw + 0.02 * H, "INPUT GATE", "I T")
    leader(cx + fg[0], cyw + fg[1], x0 + 0.13 * W, cyw - 0.18 * H, "FORGET GATE", "F T")

    # small series label
    out += _stroke_text(_spaced("LSTM   MEMORY IN TIME"), x0 + 0.03 * W, y0 + 8.0, 2.0, color=black, f=feed)
    return out


# ---------------------------------------------------------------------------
# piece 14 — LOCALITY IN SPACE (CNN as stacked wireframe feature-map terrains)
# ---------------------------------------------------------------------------


def bauhaus_locality(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 3,
    layers: int = 4,
    nx: int = 26,
    ny: int = 26,
    feed: int = 2200,
) -> List[GCodeCommand]:
    """LOCALITY IN SPACE — a CNN as a stack of feature-map TERRAINS, from PIXELS
    to MEANING. Each layer varies in character: a nearly-flat fine PIXEL grid,
    then small-bump LOW-level, rounded-hill MID-level, up to a few big smooth
    HIGH-level peaks (the tallest in red). Smooth Catmull wireframes in oblique
    projection; a red receptive-field window is tracked up the growing stack."""
    x0, y0, x1, y1 = bounds
    W, H = x1 - x0, y1 - y0
    accent, black = _pen(PINK, colors), _pen(BLACK, colors)  # PINK slot rendered crimson
    out: List[GCodeCommand] = []

    LW, DX, DY = 0.52 * W, 0.27 * W, 0.075 * H
    base_x = x0 + 0.11 * W
    base_y0 = y0 + 0.15 * H
    gap = 0.185 * H
    freqs = [9.0, 6.0, 3.6, 2.2, 1.8]  # fine pixels → few big features
    amps = [0.004, 0.030, 0.078, 0.150, 0.170]  # flat → tall

    def layer_z(i):
        fr = freqs[min(i, len(freqs) - 1)]
        Z = [[rng.fbm(u / (nx - 1) * fr + i * 11.3, v / (ny - 1) * fr + i * 5.7) for u in range(nx)] for v in range(ny)]
        lo = min(min(r) for r in Z)
        hi = max(max(r) for r in Z)
        rr = (hi - lo) or 1.0
        return [[(Z[v][u] - lo) / rr for u in range(nx)] for v in range(ny)]

    def proj(i, u, v, z):
        zh = amps[min(i, len(amps) - 1)] * H
        return (base_x + u * LW + v * DX, base_y0 + i * gap + v * DY + z * zh)

    def emit_by_pen(sm, smp):
        segs, run, cur = [], [sm[0]], smp[0]
        for p, pen in zip(sm[1:], smp[1:]):
            run.append(p)
            if pen != cur:
                segs.append((run, cur))
                run, cur = [p], pen
        segs.append((run, cur))
        res: List[GCodeCommand] = []
        for r, pen in segs:
            if len(r) >= 2:
                res += _poly(r, color=pen, f=feed)
        return res

    centers = []
    for i in range(layers):
        Z = layer_z(i)
        top = i == layers - 1
        pun = pvn = 0.5
        if top:  # the tallest peak → drawn red
            pv = max(range(ny), key=lambda v: max(Z[v]))
            pu = max(range(nx), key=lambda u: Z[pv][u])
            pun, pvn = pu / (nx - 1), pv / (ny - 1)

        def penf(u, v):
            if top and math.hypot(u - pun, v - pvn) < 0.20:
                return accent
            return black

        for jv in range(ny):
            v = jv / (ny - 1)
            pts = [proj(i, iu / (nx - 1), v, Z[jv][iu]) for iu in range(nx)]
            pens = [penf(iu / (nx - 1), v) for iu in range(nx)]
            sm, smp = _catmull_subdivide(pts, pens, subdiv=2)
            out += emit_by_pen(sm, smp)
        for iu in range(nx):
            u = iu / (nx - 1)
            pts = [proj(i, u, jv / (ny - 1), Z[jv][iu]) for jv in range(ny)]
            pens = [penf(u, jv / (ny - 1)) for jv in range(ny)]
            sm, smp = _catmull_subdivide(pts, pens, subdiv=2)
            out += emit_by_pen(sm, smp)

        # receptive-field window (red), larger toward the input (bottom)
        uc, vc = 0.52, 0.46
        hw = 0.13 - i * 0.02
        zc = Z[int(vc * (ny - 1))][int(uc * (nx - 1))]
        sq = [
            proj(i, uc - hw, vc - hw, zc),
            proj(i, uc + hw, vc - hw, zc),
            proj(i, uc + hw, vc + hw, zc),
            proj(i, uc - hw, vc + hw, zc),
            proj(i, uc - hw, vc - hw, zc),
        ]
        out += _poly(sq, color=accent, f=feed)
        centers.append(proj(i, uc, vc, zc))

    # right-edge layer labels
    lbls = ["PIXELS", "LOW-LEVEL", "MID-LEVEL", "HIGH-LEVEL"]
    for i in range(layers):
        p = proj(i, 1.0, 0.5, 0.5)
        out += _stroke_text(_spaced(lbls[min(i, 3)]), p[0] + 5, p[1], 1.6, color=black, f=feed)

    # dashed red connectors up the receptive-field column
    for i in range(layers - 1):
        a, b = centers[i], centers[i + 1]
        n = 9
        for s in range(0, n, 2):
            p0 = (a[0] + (b[0] - a[0]) * s / n, a[1] + (b[1] - a[1]) * s / n)
            p1 = (a[0] + (b[0] - a[0]) * (s + 1) / n, a[1] + (b[1] - a[1]) * (s + 1) / n)
            out += _poly([p0, p1], color=accent, f=feed)

    # left depth arrow: PIXELS (bottom) ↔ HIGH-ORDER FEATURES (top)
    ax = x0 + 0.05 * W
    ay0, ay1 = base_y0, base_y0 + (layers - 1) * gap + 0.10 * H
    out += _poly([(ax, ay0), (ax, ay1)], color=black, f=feed)
    out += _poly([(ax - 1.4, ay1 - 3), (ax, ay1), (ax + 1.4, ay1 - 3)], color=black, f=feed)
    out += _poly([(ax - 1.4, ay0 + 3), (ax, ay0), (ax + 1.4, ay0 + 3)], color=black, f=feed)
    out += _stroke_text(_spaced("PIXELS"), ax - 2, ay0 - 5, 1.9, color=black, f=feed)
    out += _stroke_text(_spaced("HIGH-ORDER"), ax - 2, ay1 + 6.5, 1.9, color=black, f=feed)
    out += _stroke_text(_spaced("FEATURES"), ax - 2, ay1 + 2.0, 1.9, color=black, f=feed)

    # title + caption
    xT = x0 + 0.03 * W
    out += type_block(["CNN"], xT, y1 - 6.0, height=4.2, pen=black, underline=False, f=feed)
    out += _stroke_text(_spaced("LOCALITY IN SPACE"), xT, y1 - 16.0, 2.4, color=black, f=feed)
    cxp = x0 + 0.58 * W
    out += _stroke_text(_spaced("SMALL WINDOWS"), cxp, y0 + 20.0, 1.9, color=black, f=feed)
    out += _stroke_text(_spaced("DEEPER PATTERNS"), cxp, y0 + 15.0, 1.9, color=black, f=feed)
    out += _stroke_text(_spaced("A LARGER PICTURE"), cxp, y0 + 10.0, 1.9, color=black, f=feed)

    # bottom mini-diagram: the receptive field shrinking grid → window → cell
    mgx, mgy, celln, cs = x0 + 0.10 * W, y0 + 10.0, 6, 2.2
    stages = [(celln, 3), (celln, 2), (celln, 1)]
    sx = mgx
    for si, (gn, winr) in enumerate(stages):
        for r in range(gn + 1):
            out += _poly([(sx, mgy + r * cs), (sx + gn * cs, mgy + r * cs)], color=black, f=feed)
        for c in range(gn + 1):
            out += _poly([(sx + c * cs, mgy), (sx + c * cs, mgy + gn * cs)], color=black, f=feed)
        cc = gn / 2.0
        out += _poly(
            [
                (sx + (cc - winr) * cs, mgy + (cc - winr) * cs),
                (sx + (cc + winr) * cs, mgy + (cc - winr) * cs),
                (sx + (cc + winr) * cs, mgy + (cc + winr) * cs),
                (sx + (cc - winr) * cs, mgy + (cc + winr) * cs),
                (sx + (cc - winr) * cs, mgy + (cc - winr) * cs),
            ],
            color=accent,
            f=feed,
        )
        nxt = sx + gn * cs + 5
        if si < len(stages) - 1:
            out += _poly([(sx + gn * cs + 1, mgy + gn * cs / 2), (nxt - 1, mgy + gn * cs / 2)], color=black, f=feed)
        sx = nxt + 4
    return out


# ---------------------------------------------------------------------------
# piece 15 — NONLINEAR TRANSFORMATION (MLP as a warped hourglass manifold)
# ---------------------------------------------------------------------------


def bauhaus_manifold(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 3,
    nu: int = 34,
    nv: int = 84,
    petals: int = 3,
    fold: float = 1.05,
    twist: float = 1.2,
    nstream: int = 52,
    feed: int = 2200,
) -> List[GCodeCommand]:
    """NONLINEAR TRANSFORMATION — an MLP rendered by a from-scratch 3D pen-plotter
    engine. A parametric petal-saddle (the nonlinear activation FOLDING space so
    far-apart points meet) is projected isometrically and hidden-line removed via
    a z-buffer, so near folds occlude far ones and it reads as a solid form.
    Streamlines funnel from the INPUT plane through the fold to the OUTPUT plane.
    All output is lines. Black surface, red fold-ridges + flow accents."""
    import numpy as np

    x0, y0, x1, y1 = bounds
    W, H = x1 - x0, y1 - y0
    accent, black = _pen(PINK, colors), _pen(BLACK, colors)  # PINK slot → crimson
    out: List[GCodeCommand] = []

    # ---- 3D world → isometric screen -------------------------------------
    cx0, cy0 = x0 + 0.50 * W, y0 + 0.50 * H
    a, cd, bwy = 0.29 * W, 0.070 * H, 0.195 * H  # lower camera: taller wy, shallower iso
    Hy = 1.30  # plane height (INPUT +Hy top, OUTPUT −Hy bottom)

    def proj(wx, wy, wz):
        return (cx0 + (wx - wz) * a, cy0 + wy * bwy - (wx + wz) * cd)

    def depth(wx, wy, wz):
        return (wx + wz) + 0.12 * wy  # larger = nearer (front)

    def surf(r, th):
        return fold * ((r ** 1.1) * math.cos(petals * th) + 0.20 * (r ** 2) * math.cos(2 * petals * th))

    # ---- surface vertex grid --------------------------------------------
    SX = np.zeros((nu + 1, nv + 1))
    SY = np.zeros((nu + 1, nv + 1))
    DEP = np.zeros((nu + 1, nv + 1))
    for i in range(nu + 1):
        r = i / nu
        for j in range(nv + 1):
            th = 2 * math.pi * j / nv
            wx, wz = r * math.cos(th), r * math.sin(th)
            wy = surf(r, th)
            sx, sy = proj(wx, wy, wz)
            SX[i, j], SY[i, j], DEP[i, j] = sx, sy, depth(wx, wy, wz)

    # ---- z-buffer (hidden-line): rasterize the surface quads -------------
    PXW, PXH = 240, 320
    pad = 4.0
    sxmin, sxmax = float(SX.min()) - pad, float(SX.max()) + pad
    symin, symax = float(SY.min()) - pad, float(SY.max()) + pad
    zbuf = np.full((PXH, PXW), -1e18)
    PX = (SX - sxmin) / (sxmax - sxmin) * (PXW - 1)
    PY = (SY - symin) / (symax - symin) * (PXH - 1)
    dspan = float(DEP.max() - DEP.min()) or 1.0
    bias = 0.02 * dspan

    def fill_tri(p0, p1, p2, d0, d1, d2):
        minx = int(max(0, math.floor(min(p0[0], p1[0], p2[0]))))
        maxx = int(min(PXW - 1, math.ceil(max(p0[0], p1[0], p2[0]))))
        miny = int(max(0, math.floor(min(p0[1], p1[1], p2[1]))))
        maxy = int(min(PXH - 1, math.ceil(max(p0[1], p1[1], p2[1]))))
        if maxx < minx or maxy < miny:
            return
        den = (p1[1] - p2[1]) * (p0[0] - p2[0]) + (p2[0] - p1[0]) * (p0[1] - p2[1])
        if abs(den) < 1e-9:
            return
        X, Y = np.meshgrid(np.arange(minx, maxx + 1), np.arange(miny, maxy + 1))
        aa = ((p1[1] - p2[1]) * (X - p2[0]) + (p2[0] - p1[0]) * (Y - p2[1])) / den
        bb = ((p2[1] - p0[1]) * (X - p2[0]) + (p0[0] - p2[0]) * (Y - p2[1])) / den
        cc = 1 - aa - bb
        inside = (aa >= -1e-4) & (bb >= -1e-4) & (cc >= -1e-4)
        d = aa * d0 + bb * d1 + cc * d2
        sub = zbuf[miny : maxy + 1, minx : maxx + 1]
        m = inside & (d > sub)
        sub[m] = d[m]

    for i in range(nu):
        for j in range(nv):
            p00 = (PX[i, j], PY[i, j])
            p10 = (PX[i + 1, j], PY[i + 1, j])
            p11 = (PX[i + 1, j + 1], PY[i + 1, j + 1])
            p01 = (PX[i, j + 1], PY[i, j + 1])
            fill_tri(p00, p10, p11, DEP[i, j], DEP[i + 1, j], DEP[i + 1, j + 1])
            fill_tri(p00, p11, p01, DEP[i, j], DEP[i + 1, j + 1], DEP[i, j + 1])

    def visible(sx, sy, dep):
        px = int((sx - sxmin) / (sxmax - sxmin) * (PXW - 1))
        py = int((sy - symin) / (symax - symin) * (PXH - 1))
        if px < 0 or px >= PXW or py < 0 or py >= PXH:
            return True  # off-surface → nothing to occlude
        return dep >= zbuf[py, px] - bias

    def emit_visible(samples):
        # samples: list of (sx, sy, dep, pen); draw only visible runs
        run, runpen = [], None
        for sx, sy, dep, pen in samples:
            if visible(sx, sy, dep):
                if runpen is None or pen == runpen:
                    run.append((sx, sy))
                    runpen = pen
                else:
                    if len(run) >= 2:
                        out.extend(_poly(run, color=runpen, f=feed))
                    run, runpen = [(sx, sy)], pen
            else:
                if len(run) >= 2:
                    out.extend(_poly(run, color=runpen, f=feed))
                run, runpen = [], None
        if len(run) >= 2:
            out.extend(_poly(run, color=runpen, f=feed))

    # ---- draw the visible surface mesh (the fold, hidden-line removed) ----
    ridge = {0, nv // (2 * petals)}  # crease columns → red fold-ridges
    for j in range(nv + 1):  # radial lines
        red = (j % (nv // petals)) < 1 or ((j - nv // (2 * petals)) % (nv // petals)) < 1
        emit_visible([(SX[i, j], SY[i, j], DEP[i, j], accent if red else black) for i in range(nu + 1)])
    for i in range(2, nu + 1):  # rings (skip the tiny center rings)
        emit_visible([(SX[i, j], SY[i, j], DEP[i, j], black) for j in range(nv + 1)])

    # ---- streamlines: INPUT plane → through the fold → OUTPUT plane -------
    for s_i in range(nstream):
        th0 = 2 * math.pi * s_i / nstream
        r0 = 0.6 + 0.4 * rng.random()
        samples = []
        pen = accent if s_i % 4 == 0 else black
        STEPS = 74
        for k in range(STEPS + 1):
            s = k / STEPS
            wy_lin = Hy - 2 * Hy * s
            rr = r0 * (0.42 + 0.58 * abs(2 * s - 1))  # funnel to a ring, not a point
            th = th0 + twist * s
            blend = math.exp(-((s - 0.5) / 0.22) ** 2)
            wy = wy_lin * (1 - blend) + surf(min(1.0, rr), th) * blend
            wx, wz = rr * math.cos(th), rr * math.sin(th)
            sx, sy = proj(wx, wy, wz)
            samples.append((sx, sy, depth(wx, wy, wz), pen))
        emit_visible(samples)

    # ---- INPUT / OUTPUT planes: dot lattice + frame + droplines ----------
    def plane(wy, label, above):
        g = 11
        for ia in range(g):
            for ib in range(g):
                gu, gv = -1.15 + 2.3 * ia / (g - 1), -1.15 + 2.3 * ib / (g - 1)
                sx, sy = proj(gu, wy, gv)
                out.extend(_dot(sx, sy, 0.45, color=black, f=feed))
        corners = [(-1.15, -1.15), (1.15, -1.15), (1.15, 1.15), (-1.15, 1.15), (-1.15, -1.15)]
        out.extend(_poly([proj(gu, wy, gv) for gu, gv in corners], color=black, f=feed))
        c = proj(0, wy, 0)
        ly = c[1] + (14 if above else -8)
        out.extend(_stroke_text(_spaced(label), c[0] - 0.10 * W, ly, 2.3, color=black, f=feed))

    plane(Hy, "INPUT SPACE", True)
    plane(-Hy, "OUTPUT SPACE", False)
    for dl in range(10):  # a few vertical droplines through the ambient volume
        gu = -1.0 + 2.0 * rng.random()
        gv = -1.0 + 2.0 * rng.random()
        seg = []
        for k in range(0, 21, 2):
            wy = Hy - 2 * Hy * k / 20
            p = proj(gu, wy, gv)
            seg.append(p)
        for k in range(0, len(seg) - 1, 2):
            out += _poly([seg[k], seg[k + 1]], color=black, f=feed)

    # ---- furniture -------------------------------------------------------
    xT = x0 + 0.02 * W
    out += type_block(["MLP"], xT, y1 - 6.0, height=3.6, pen=black, underline=False, f=feed)
    out += _stroke_text(_spaced("NONLINEAR TRANSFORMATION"), xT, y1 - 15.0, 2.0, color=black, f=feed)
    rx = x1 - 0.20 * W
    out += _stroke_text(_spaced("LINEAR TRANSFORM"), rx, cy0 + 0.30 * H, 1.7, color=black, f=feed)
    out += _stroke_text(_spaced("NONLINEAR"), rx, cy0 + 0.02 * H, 1.7, color=accent, f=feed)
    out += _stroke_text(_spaced("ACTIVATION"), rx, cy0 - 0.03 * H, 1.7, color=accent, f=feed)
    out += _stroke_text(_spaced("LINEAR TRANSFORM"), rx, cy0 - 0.30 * H, 1.7, color=black, f=feed)
    return out
