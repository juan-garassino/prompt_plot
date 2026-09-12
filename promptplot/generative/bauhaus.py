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
    """One continuous chaotic trajectory in black; solid blue/pink discs sit in
    the empty eyes of the two lobes; a solid bar holds the left edge."""
    x0, y0, x1, y1 = bounds
    W, H = x1 - x0, y1 - y0
    out: List[GCodeCommand] = []
    blue, pink, black = _pen(BLUE, colors), _pen(PINK, colors), _pen(BLACK, colors)

    bar_x0 = x0 + 0.03 * W
    bar_x1 = bar_x0 + 0.085 * W
    out += fill_rect(bar_x0, y0 + 0.5, bar_x1, y1 - 0.5, spacing=0.6, pen=black, f=feed)

    sub = (x0 + 0.24 * W, y0 + 0.12 * H, x1 - 0.02 * W, y1 - 0.12 * H)
    traj = strange_attractor(rng, sub, colors=1, system=system, steps=steps)
    for c in traj:
        if c.command in ("M3", "G1", "G0"):
            c.color = black
    scx, scy = (sub[0] + sub[2]) / 2, (sub[1] + sub[3]) / 2
    out += dotted_circle(scx, scy, 0.46 * H, pen=black, bounds=bounds, f=feed)

    pts = [(c.x, c.y) for c in traj if c.command == "G1" and c.x is not None]
    if pts:
        # 2-means on the trajectory: centers land in the two lobe eyes
        xs_ = sorted(px for px, _ in pts)
        c_a = pts[len(pts) // 4]
        c_b = pts[3 * len(pts) // 4]
        for _ in range(12):
            ga, gb = [], []
            for px, py in pts[:: max(1, len(pts) // 3000)]:
                da = (px - c_a[0]) ** 2 + (py - c_a[1]) ** 2
                db = (px - c_b[0]) ** 2 + (py - c_b[1]) ** 2
                (ga if da < db else gb).append((px, py))
            if ga:
                c_a = (sum(p_[0] for p_ in ga) / len(ga), sum(p_[1] for p_ in ga) / len(ga))
            if gb:
                c_b = (sum(p_[0] for p_ in gb) / len(gb), sum(p_[1] for p_ in gb) / len(gb))
        left, right = sorted((c_a, c_b), key=lambda c_: c_[0])
        out += fill_disc(left[0], left[1], 5.5, spacing=0.5, pen=blue, f=feed)
        out += fill_disc(right[0], right[1], 5.5, spacing=0.5, pen=pink, f=feed)
    out += traj

    out += type_block(["SENSITIVE", "DEPENDENCE"], bar_x1 + 6.0, y1 - 6.0, pen=black, f=feed)
    out += swatch_bar(bar_x1 + 6.0, y1 - 22.0, [black, blue, pink], f=feed)
    out += plus_mark(x1 - 10.0, y1 - 10.0, pen=black, f=feed)
    out += plus_mark(bar_x1 + 8.0, y0 + 12.0, pen=black, f=feed)
    out += scale_footer(bounds, pen=black, f=feed)
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
    """Token circle with straight attention chords; every chord into the sink
    token is bold pink; the sink itself is a solid blue disc."""
    x0, y0, x1, y1 = bounds
    W, H = x1 - x0, y1 - y0
    out: List[GCodeCommand] = []
    blue, pink, black = _pen(BLUE, colors), _pen(PINK, colors), _pen(BLACK, colors)

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

    ccx, ccy = x0 + 0.56 * W, y0 + 0.52 * H
    R = min(0.40 * H, 0.34 * W, x1 - ccx - 6.0, ccx - x0 - 6.0)
    pos = [
        (
            ccx + R * math.cos(2 * math.pi * t / tokens - math.pi / 2),
            ccy + R * math.sin(2 * math.pi * t / tokens - math.pi / 2),
        )
        for t in range(tokens)
    ]
    col_mass = [sum(float(A[q][k]) for q in range(tokens)) for k in range(tokens)]
    sink = max(range(tokens), key=lambda k: col_mass[k])

    out += dotted_circle(ccx, ccy, R + 7.0, pen=black, bounds=bounds, f=feed)
    for q in range(tokens):
        row = sorted(range(tokens), key=lambda k: -float(A[q][k]))[:topk]
        for k in row:
            if k == q or float(A[q][k]) < 0.03:
                continue
            (xa, ya), (xb, yb) = pos[k], pos[q]
            if k == sink:
                dx, dy = xb - xa, yb - ya
                n = math.hypot(dx, dy) or 1.0
                oxp, oyp = -dy / n * 0.28, dx / n * 0.28
                for pp in (-1, 0, 1):
                    out += _poly(
                        [(xa + oxp * pp, ya + oyp * pp), (xb + oxp * pp, yb + oyp * pp)],
                        color=pink,
                        f=feed,
                    )
            else:
                out += _poly([(xa, ya), (xb, yb)], color=black, f=feed)
    for t in range(tokens):
        if t == sink:
            out += fill_disc(pos[t][0], pos[t][1], 4.0, spacing=0.5, pen=blue, f=feed)
        else:
            out += fill_disc(pos[t][0], pos[t][1], 1.1, spacing=0.45, pen=black, f=feed)

    qx, qy = x0 + 0.10 * W, y0 + 0.22 * H
    out += fill_quarter(qx, qy, 5.0, math.pi, pen=black, f=feed)
    out += fill_quarter(qx, qy, 5.0, 0.0, pen=pink, f=feed)
    out += type_block(["ATTENTION"], x0 + 5.0, y1 - 6.0, pen=black, f=feed)
    out += swatch_bar(x0 + 5.0, y1 - 16.0, [black, blue, pink], f=feed)
    out += plus_mark(x1 - 9.0, y0 + 12.0, pen=black, f=feed)
    out += scale_footer(bounds, pen=black, f=feed)
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
