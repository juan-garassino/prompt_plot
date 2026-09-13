"""Plate layout — bands, panel grids, gutter rules, number chips.

Pure geometry over ``Bounds = (x0, y0, x1, y1)`` in paper mm.
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

from ..models import GCodeCommand
from ..generative.kit import Bounds, _poly, _stroke_text, circle


def reserve_bands(
    bounds: Bounds, title_h: float = 0.0, footer_h: float = 0.0
) -> Tuple[Optional[Bounds], Bounds, Optional[Bounds]]:
    """Split the drawable area into (title_band, content, footer_band).

    The title band sits at the TOP (highest y), the footer at the bottom.
    Bands are ``None`` when their height is 0.
    """
    x0, y0, x1, y1 = bounds
    title = (x0, y1 - title_h, x1, y1) if title_h > 0 else None
    footer = (x0, y0, x1, y0 + footer_h) if footer_h > 0 else None
    content = (x0, y0 + footer_h, x1, y1 - title_h)
    return title, content, footer


def split_panels(content: Bounds, n: int, rows: Optional[int] = None, gutter: float = 8.0) -> List[Bounds]:
    """Split the content area into ``n`` panel bounds on a rows×cols grid.

    Panels are ordered left→right, top→bottom. Exact math: no overlap, gutters
    exactly ``gutter`` mm, panels flush with the content edges.
    """
    if n < 1:
        raise ValueError("n must be >= 1")
    x0, y0, x1, y1 = content
    r = rows if rows is not None else 1
    if r < 1 or r > n:
        raise ValueError("rows must be in [1, n]")
    cols = math.ceil(n / r)
    pw = (x1 - x0 - gutter * (cols - 1)) / cols
    ph = (y1 - y0 - gutter * (r - 1)) / r
    if pw <= 0 or ph <= 0:
        raise ValueError("content too small for that many panels/gutter")
    panels: List[Bounds] = []
    for k in range(n):
        ri, ci = divmod(k, cols)
        px0 = x0 + ci * (pw + gutter)
        # first row at the TOP of the content area
        py1 = y1 - ri * (ph + gutter)
        panels.append((px0, py1 - ph, px0 + pw, py1))
    return panels


def gutter_rules(panels: List[Bounds], gutter: float, pen, passes: int = 1, f: int = 2200) -> List[GCodeCommand]:
    """Hairline rules centered in the vertical gutters between adjacent panels."""
    out: List[GCodeCommand] = []
    # vertical rules between horizontally adjacent panels (same row)
    for a in panels:
        for b in panels:
            if abs(a[3] - b[3]) < 1e-6 and abs(b[0] - a[2] - gutter) < 1e-6:
                x = (a[2] + b[0]) / 2
                for p in range(passes):
                    off = (p - (passes - 1) / 2) * 0.3
                    out += _poly([(x + off, a[1] + 1.0), (x + off, a[3] - 1.0)], color=pen, f=f)
    return out


def number_chips(panels: List[Bounds], pen, f: int = 2200) -> List[GCodeCommand]:
    """A small "01"-style chip at each panel's top-left corner."""
    out: List[GCodeCommand] = []
    for i, (x0, _y0, _x1, y1) in enumerate(panels):
        cx, cy = x0 + 4.5, y1 - 4.5
        out += circle(cx, cy, 3.4, pen=pen, f=f)
        out += _stroke_text(f"{i + 1:02d}", cx - 2.4, cy - 1.1, 2.0, color=pen, f=f)
    return out
