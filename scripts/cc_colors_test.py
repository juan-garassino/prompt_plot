"""Multi-color pen test — draw all strokes of one color, pause for a pen swap, repeat.

Builds a 3-color drawing (concentric squares in black, a diagonal grid in red, a
circle of dots in blue), groups strokes by color, and streams color-by-color with
a park + keypress pause between each pen change.

Usage:
  python scripts/cc_colors_test.py --simulate          # dry run, auto-continue between colors
  python scripts/cc_colors_test.py --simulate --preview color.png
  python scripts/cc_colors_test.py                     # sends to Leo, pauses for real swaps
"""

import asyncio
import argparse
import math
import sys

from promptplot.config import PromptPlotConfig, PaperConfig
from promptplot.plotter import SerialPlotter, SimulatedPlotter
from promptplot.models import GCodeCommand
from promptplot.orchestrate import merge_chunks, stream_pen_layers

# ── palette (pen index -> name/color) ───────────────────────────────────────────
PALETTE = ["black", "red", "blue"]
# ─────────────────────────────────────────────────────────────────────────────

PAPER = PaperConfig.from_size("a5")
DX0, DY0, DX1, DY1 = PAPER.get_drawable_area()
CX, CY = (DX0 + DX1) / 2, (DY0 + DY1) / 2


def _stroke(points, color, f=1500):
    """One stroke (G0 to start, M3, G1s, M5) tagged with a color index."""
    cmds = [
        GCodeCommand(command="G0", x=round(points[0][0], 2), y=round(points[0][1], 2)),
        GCodeCommand(command="M3", s=1000, color=color),
    ]
    for x, y in points[1:]:
        cmds.append(GCodeCommand(command="G1", x=round(x, 2), y=round(y, 2), f=f, color=color))
    cmds.append(GCodeCommand(command="M5"))
    return cmds


def build_drawing():
    cmds = []

    # color 0 (black): concentric squares
    for half in (15, 25, 35):
        cmds += _stroke(
            [
                (CX - half, CY - half),
                (CX + half, CY - half),
                (CX + half, CY + half),
                (CX - half, CY + half),
                (CX - half, CY - half),
            ],
            color=0,
        )

    # color 1 (red): diagonal grid across the middle band
    for i in range(-4, 5):
        off = i * 8
        cmds += _stroke([(CX - 40 + off, CY - 40), (CX + 40 + off, CY + 40)], color=1)

    # color 2 (blue): ring of short radial dashes
    for k in range(24):
        a = 2 * math.pi * k / 24
        r0, r1 = 40, 46
        cmds += _stroke(
            [
                (CX + r0 * math.cos(a), CY + r0 * math.sin(a)),
                (CX + r1 * math.cos(a), CY + r1 * math.sin(a)),
            ],
            color=2,
        )

    return cmds


async def run(simulate: bool, port: str, baud: int, preview: str | None):
    cfg = PromptPlotConfig()
    cfg.paper = PAPER
    cfg.color.enabled = True
    cfg.color.palette = PALETTE
    cfg.color.park_position = (0.0, 0.0)
    cfg.color.pause_for_swap = not simulate  # in simulate mode, auto-continue

    raw = build_drawing()
    program = merge_chunks([raw], cfg)  # groups by color, optimizes within each

    seq = program.metadata.get("color_sequence", [])
    print(f"Paper     : A5 drawable X[{DX0},{DX1}] Y[{DY0},{DY1}] mm")
    print(f"Palette   : {', '.join(f'{i}:{c}' for i, c in enumerate(PALETTE))}")
    print(f"Colors    : {len(seq)} layers, order {seq}")
    print(f"Commands  : {len(program.commands)}")
    print(f"Mode      : {'SIMULATE' if simulate else 'LIVE → Leo'}")
    print()

    if preview:
        from promptplot.visualizer import GCodeVisualizer

        GCodeVisualizer(cfg).preview(program, preview)
        print(f"Preview saved to {preview}")

    if simulate:
        plotter = SimulatedPlotter()
        await plotter.connect()
    else:
        plotter = SerialPlotter(port=port, baud_rate=baud)
        if not await plotter.connect():
            print(f"ERROR: could not connect to {port}")
            sys.exit(1)

    ok, err = await stream_pen_layers(program, plotter, cfg, verbose=True)
    if not simulate:
        await plotter.disconnect()
    print(f"\nDone: {ok} ok  {err} errors  total={len(program.commands)}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--port", default="/dev/cu.usbserial-14120")
    p.add_argument("--baud", type=int, default=115200)
    p.add_argument("--simulate", action="store_true", default=False)
    p.add_argument("--preview", default=None, help="Save a color-coded preview PNG")
    args = p.parse_args()
    asyncio.run(run(args.simulate, args.port, args.baud, args.preview))
