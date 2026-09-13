"""engine3d — the from-scratch 3D pen-plotter engine.

A numpy z-buffer hidden-line renderer for line-native 3D on a plotter: surface
quads are rasterized into a depth buffer, then only the VISIBLE parts of each
mesh line are drawn, so near ridges/folds occlude far mesh and surfaces read as
solid form. Pieces build (SX, SY, DEP) screen/depth arrays with their own
isometric ``proj``/``dep`` closures and call :func:`_zbuf_terrain`.
"""

from __future__ import annotations

import math
from typing import List, Optional

from ..models import GCodeCommand
from .generators import _poly



def _zbuf_terrain(out, SX, SY, DEP, feed=2200, PENV=None, pen=None, PXW=210, PXH=160):
    """Shared 3D hidden-line terrain engine. Rasterize the surface quads into a
    numpy z-buffer, then draw only the visible parts of each grid line so near
    folds occlude far ones (a solid surface, not a transparent wireframe).
    SX/SY/DEP are (R+1,C+1) arrays of screen coords + view-depth (larger=nearer);
    PENV optional per-vertex pen index, else the single `pen`. Appends to `out`."""
    import numpy as np

    R, C = SX.shape[0] - 1, SX.shape[1] - 1
    sxmin, sxmax = float(SX.min()) - 3, float(SX.max()) + 3
    symin, symax = float(SY.min()) - 3, float(SY.max()) + 3
    zb = np.full((PXH, PXW), -1e18)
    PX = (SX - sxmin) / (sxmax - sxmin) * (PXW - 1)
    PY = (SY - symin) / (symax - symin) * (PXH - 1)
    dspan = float(DEP.max() - DEP.min()) or 1.0
    bias = 0.02 * dspan

    def tri(p0, p1, p2, d0, d1, d2):
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
        ins = (aa >= -1e-4) & (bb >= -1e-4) & (cc >= -1e-4)
        d = aa * d0 + bb * d1 + cc * d2
        sub = zb[miny : maxy + 1, minx : maxx + 1]
        m = ins & (d > sub)
        sub[m] = d[m]

    for i in range(R):
        for j in range(C):
            tri((PX[i, j], PY[i, j]), (PX[i + 1, j], PY[i + 1, j]), (PX[i + 1, j + 1], PY[i + 1, j + 1]), DEP[i, j], DEP[i + 1, j], DEP[i + 1, j + 1])
            tri((PX[i, j], PY[i, j]), (PX[i + 1, j + 1], PY[i + 1, j + 1]), (PX[i, j + 1], PY[i, j + 1]), DEP[i, j], DEP[i + 1, j + 1], DEP[i, j + 1])

    def vis(sx, sy, d):
        px = int((sx - sxmin) / (sxmax - sxmin) * (PXW - 1))
        py = int((sy - symin) / (symax - symin) * (PXH - 1))
        if px < 0 or px >= PXW or py < 0 or py >= PXH:
            return True
        return d >= zb[py, px] - bias

    def draw(idx):
        run, cur = [], None
        for (i, j) in idx:
            if vis(SX[i, j], SY[i, j], DEP[i, j]):
                pp = int(PENV[i, j]) if PENV is not None else pen
                if cur is None or pp == cur:
                    run.append((SX[i, j], SY[i, j]))
                    cur = pp
                else:
                    if len(run) >= 2:
                        out.extend(_poly(run, color=cur, f=feed))
                    run, cur = [(SX[i, j], SY[i, j])], pp
            else:
                if len(run) >= 2:
                    out.extend(_poly(run, color=cur, f=feed))
                run, cur = [], None
        if len(run) >= 2:
            out.extend(_poly(run, color=cur, f=feed))

    for i in range(R + 1):
        draw([(i, j) for j in range(C + 1)])
    for j in range(C + 1):
        draw([(i, j) for i in range(R + 1)])



def _fit_out(out, bounds, inset=4.0):
    """Safety net: if the emitted geometry spills the drawable, uniformly
    shrink + centre ALL commands so the whole composition lands on paper."""
    xs = [c.x for c in out if c.x is not None]
    ys = [c.y for c in out if c.y is not None]
    if not xs:
        return out
    x0, y0, x1, y1 = bounds
    bx0, bx1, by0, by1 = min(xs), max(xs), min(ys), max(ys)
    if bx0 >= x0 and bx1 <= x1 and by0 >= y0 and by1 <= y1:
        return out
    tw, th = (x1 - x0 - 2 * inset), (y1 - y0 - 2 * inset)
    s = min(tw / max(1e-6, bx1 - bx0), th / max(1e-6, by1 - by0), 1.0)
    cxs, cys = (bx0 + bx1) / 2, (by0 + by1) / 2
    tcx, tcy = (x0 + x1) / 2, (y0 + y1) / 2
    fitted = []
    for c in out:
        nx = tcx + (c.x - cxs) * s if c.x is not None else None
        ny = tcy + (c.y - cys) * s if c.y is not None else None
        fitted.append(c.model_copy(update={"x": (round(nx, 3) if nx is not None else None),
                                           "y": (round(ny, 3) if ny is not None else None)}))
    return fitted

