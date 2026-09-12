"""SVG → ImportResult.

Groups paths by stroke color (or Inkscape layer). Uses a stdlib parser for the
common plotter elements (line/polyline/polygon/rect/circle/ellipse and
line-only path data). Install the ``io`` extra (``svgpathtools``) for full curve
flattening.
"""

from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from typing import List, Optional

from .layers import ImportedPath, ImportResult

_NUM = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")


def _local(tag: str) -> str:
    return tag.split("}")[-1]


def _stroke_of(el, inherited: str) -> str:
    stroke = el.get("stroke")
    style = el.get("style", "")
    if not stroke and "stroke:" in style:
        m = re.search(r"stroke:\s*([^;]+)", style)
        if m:
            stroke = m.group(1).strip()
    if not stroke or stroke.lower() == "none":
        return inherited
    return stroke.strip()


def _points_attr(s: str) -> List:
    nums = [float(n) for n in _NUM.findall(s)]
    return [(nums[i], nums[i + 1]) for i in range(0, len(nums) - 1, 2)]


def _circle(cx, cy, r, n=48):
    return [
        (cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n))
        for k in range(n + 1)
    ]


def _ellipse(cx, cy, rx, ry, n=48):
    return [
        (cx + rx * math.cos(2 * math.pi * k / n), cy + ry * math.sin(2 * math.pi * k / n))
        for k in range(n + 1)
    ]


def _parse_path_d(d: str) -> List[List]:
    """Parse an SVG path 'd' into polylines. Line commands (M/L/H/V/Z) are exact;
    curve commands (C/S/Q/T/A) are approximated by their endpoints."""
    tokens = re.findall(r"[MmLlHhVvCcSsQqTtAaZz]|[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", d)
    polylines: List[List] = []
    cur: List = []
    x = y = 0.0
    start = (0.0, 0.0)
    i = 0
    cmd = None

    def nxt():
        nonlocal i
        v = float(tokens[i])
        i += 1
        return v

    while i < len(tokens):
        t = tokens[i]
        if t.isalpha():
            cmd = t
            i += 1
        rel = cmd.islower()
        c = cmd.upper()
        if c == "M":
            if cur:
                polylines.append(cur)
            px, py = nxt(), nxt()
            x, y = (x + px, y + py) if rel else (px, py)
            start = (x, y)
            cur = [(x, y)]
            cmd = "l" if rel else "L"  # subsequent implicit lineto
        elif c == "L":
            px, py = nxt(), nxt()
            x, y = (x + px, y + py) if rel else (px, py)
            cur.append((x, y))
        elif c == "H":
            px = nxt()
            x = x + px if rel else px
            cur.append((x, y))
        elif c == "V":
            py = nxt()
            y = y + py if rel else py
            cur.append((x, y))
        elif c in ("C", "S", "Q", "T", "A"):
            # consume params, keep only the endpoint (approximation)
            counts = {"C": 6, "S": 4, "Q": 4, "T": 2, "A": 7}
            vals = [nxt() for _ in range(counts[c])]
            ex, ey = vals[-2], vals[-1]
            x, y = (x + ex, y + ey) if rel else (ex, ey)
            cur.append((x, y))
        elif c == "Z":
            if cur:
                cur.append(start)
                polylines.append(cur)
                cur = []
            x, y = start
        else:
            i += 1
    if cur:
        polylines.append(cur)
    return polylines


def _parse_stdlib(path: str) -> List[ImportedPath]:
    tree = ET.parse(path)
    root = tree.getroot()
    out: List[ImportedPath] = []

    def walk(el, layer: str, stroke: str):
        tag = _local(el.tag)
        if tag == "g":
            # Inkscape layer?
            label = None
            for k, v in el.attrib.items():
                if k.endswith("label"):
                    label = v
            if (
                el.get("{http://www.inkscape.org/namespaces/inkscape}groupmode") == "layer"
                and label
            ):
                layer = label
            stroke = _stroke_of(el, stroke)
            for child in el:
                walk(child, layer, stroke)
            return

        s = _stroke_of(el, stroke)
        polys: List[List] = []
        if tag == "line":
            polys = [
                [
                    (float(el.get("x1", 0)), float(el.get("y1", 0))),
                    (float(el.get("x2", 0)), float(el.get("y2", 0))),
                ]
            ]
        elif tag in ("polyline", "polygon"):
            pts = _points_attr(el.get("points", ""))
            if tag == "polygon" and pts:
                pts = pts + [pts[0]]
            polys = [pts]
        elif tag == "rect":
            x, y = float(el.get("x", 0)), float(el.get("y", 0))
            w, h = float(el.get("width", 0)), float(el.get("height", 0))
            polys = [[(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]]
        elif tag == "circle":
            polys = [_circle(float(el.get("cx", 0)), float(el.get("cy", 0)), float(el.get("r", 0)))]
        elif tag == "ellipse":
            polys = [
                _ellipse(
                    float(el.get("cx", 0)),
                    float(el.get("cy", 0)),
                    float(el.get("rx", 0)),
                    float(el.get("ry", 0)),
                )
            ]
        elif tag == "path":
            polys = _parse_path_d(el.get("d", ""))

        for poly in polys:
            if len(poly) >= 2:
                out.append(ImportedPath(points=poly, color=s, layer=layer))

        for child in el:
            walk(child, layer, s)

    walk(root, "default", "black")
    return out


def _parse_svgpathtools(path: str, samples: int = 24) -> Optional[List[ImportedPath]]:
    try:
        from svgpathtools import svg2paths2
    except ImportError:
        return None
    paths, attrs, _svg_attr = svg2paths2(path)
    out: List[ImportedPath] = []
    for p, attr in zip(paths, attrs):
        stroke = attr.get("stroke", "black") or "black"
        style = attr.get("style", "")
        if "stroke:" in style:
            m = re.search(r"stroke:\s*([^;]+)", style)
            if m:
                stroke = m.group(1).strip()
        for sub in p.continuous_subpaths():
            pts = [
                (sub.point(k / samples).real, sub.point(k / samples).imag)
                for k in range(samples + 1)
            ]
            out.append(ImportedPath(points=pts, color=stroke, layer="default"))
    return out


def parse_svg(path: str, prefer_lib: bool = True) -> ImportResult:
    """Parse an SVG file into an ImportResult (paths grouped by stroke color)."""
    paths = None
    if prefer_lib:
        paths = _parse_svgpathtools(path)
    if not paths:
        paths = _parse_stdlib(path)
    return ImportResult(paths=paths, y_down=True, source=path)
