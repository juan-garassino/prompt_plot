"""DXF → ImportResult, grouped by DXF layer.

Uses a stdlib ASCII-DXF parser for the common entities (LINE, LWPOLYLINE,
CIRCLE, ARC). Install the ``io`` extra (``ezdxf``) for full entity support
(POLYLINE/SPLINE/INSERT, true layer colors, binary DXF).
"""

from __future__ import annotations

import math
from typing import List, Optional

from .layers import ImportedPath, ImportResult


def _arc_points(cx, cy, r, a0deg, a1deg, n=32):
    a0, a1 = math.radians(a0deg), math.radians(a1deg)
    if a1 <= a0:
        a1 += 2 * math.pi
    return [
        (cx + r * math.cos(a0 + (a1 - a0) * k / n), cy + r * math.sin(a0 + (a1 - a0) * k / n))
        for k in range(n + 1)
    ]


def _circle_points(cx, cy, r, n=48):
    return [
        (cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n))
        for k in range(n + 1)
    ]


def _parse_stdlib(path: str) -> List[ImportedPath]:
    text = open(path, "r", errors="ignore").read().splitlines()
    pairs = []
    for i in range(0, len(text) - 1, 2):
        pairs.append((text[i].strip(), text[i + 1].strip()))

    out: List[ImportedPath] = []
    etype = None
    layer = "0"
    xs: List[float] = []
    ys: List[float] = []
    x2 = y2 = None
    radius = None
    a0 = a1 = None

    def flush():
        nonlocal etype, layer, xs, ys, x2, y2, radius, a0, a1
        if etype == "LINE" and xs and x2 is not None:
            out.append(ImportedPath(points=[(xs[0], ys[0]), (x2, y2)], color=layer, layer=layer))
        elif etype == "LWPOLYLINE" and len(xs) >= 2:
            out.append(ImportedPath(points=list(zip(xs, ys)), color=layer, layer=layer))
        elif etype == "CIRCLE" and xs and radius is not None:
            out.append(
                ImportedPath(points=_circle_points(xs[0], ys[0], radius), color=layer, layer=layer)
            )
        elif etype == "ARC" and xs and radius is not None and a0 is not None:
            out.append(
                ImportedPath(
                    points=_arc_points(xs[0], ys[0], radius, a0, a1 or a0 + 360),
                    color=layer,
                    layer=layer,
                )
            )
        etype, xs, ys, x2, y2, radius, a0, a1 = None, [], [], None, None, None, None, None

    in_entities = False
    for code, val in pairs:
        if code == "2" and val == "ENTITIES":
            in_entities = True
            continue
        if not in_entities:
            continue
        if code == "0":
            flush()
            if val == "ENDSEC":
                in_entities = False
                continue
            etype = val
            layer = "0"
        elif code == "8":
            layer = val
        elif code == "10":
            xs.append(float(val))
        elif code == "20":
            ys.append(float(val))
        elif code == "11":
            x2 = float(val)
        elif code == "21":
            y2 = float(val)
        elif code == "40":
            radius = float(val)
        elif code == "50":
            a0 = float(val)
        elif code == "51":
            a1 = float(val)
    flush()
    return out


def _parse_ezdxf(path: str) -> Optional[List[ImportedPath]]:
    try:
        import ezdxf
    except ImportError:
        return None
    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    out: List[ImportedPath] = []
    for e in msp:
        layer = e.dxf.layer
        t = e.dxftype()
        if t == "LINE":
            out.append(
                ImportedPath(
                    [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)],
                    color=layer,
                    layer=layer,
                )
            )
        elif t == "LWPOLYLINE":
            pts = [(p[0], p[1]) for p in e.get_points()]
            if e.closed and pts:
                pts.append(pts[0])
            if len(pts) >= 2:
                out.append(ImportedPath(pts, color=layer, layer=layer))
        elif t == "POLYLINE":
            pts = [(v.dxf.location.x, v.dxf.location.y) for v in e.vertices]
            if len(pts) >= 2:
                out.append(ImportedPath(pts, color=layer, layer=layer))
        elif t == "CIRCLE":
            out.append(
                ImportedPath(
                    _circle_points(e.dxf.center.x, e.dxf.center.y, e.dxf.radius),
                    color=layer,
                    layer=layer,
                )
            )
        elif t == "ARC":
            out.append(
                ImportedPath(
                    _arc_points(
                        e.dxf.center.x,
                        e.dxf.center.y,
                        e.dxf.radius,
                        e.dxf.start_angle,
                        e.dxf.end_angle,
                    ),
                    color=layer,
                    layer=layer,
                )
            )
    return out


def parse_dxf(path: str, prefer_lib: bool = True) -> ImportResult:
    """Parse a DXF file into an ImportResult (paths grouped by layer)."""
    paths = None
    if prefer_lib:
        paths = _parse_ezdxf(path)
    if not paths:
        paths = _parse_stdlib(path)
    return ImportResult(paths=paths, y_down=False, source=path)
