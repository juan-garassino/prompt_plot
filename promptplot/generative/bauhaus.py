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
# piece 06 — GRADIENT DESCENT
# ---------------------------------------------------------------------------


def bauhaus_gradient(
    rng: SeededRNG,
    bounds: Bounds,
    colors: int = 3,
    levels: int = 14,
    steps: int = 70,
    lr: float = 0.22,
    feed: int = 2200,
) -> List[GCodeCommand]:
    """A two-bowl loss landscape as thin contour ellipses; the descent path is a
    bold pink polyline with solid step dots, the minimum a solid blue disc."""
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
