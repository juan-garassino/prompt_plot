"""
Brush/paint mode test — draws a spiral with automatic ink reloads.

Set INK_WELL_X, INK_WELL_Y to wherever your ink well sits on the paper.
Set STROKES_PER_DIP to how many strokes before each reload.

Usage:
  python scripts/cc_brush_test.py --simulate     # dry run, shows dip sequence
  python scripts/cc_brush_test.py                # sends to Leo
"""

import asyncio
import argparse
import math
import sys

from promptplot.config import PromptPlotConfig, PaperConfig, BrushConfig
from promptplot.plotter import SerialPlotter, SimulatedPlotter
from promptplot.models import GCodeCommand
from promptplot.orchestrate import merge_chunks

# ── adjust these ──────────────────────────────────────────────────────────────
INK_WELL_X       = 10.0    # mm from origin — left edge
INK_WELL_Y       = 10.0    # mm from origin — bottom edge
STROKES_PER_DIP  = 3       # pen-downs between ink reloads (low = frequent dips)
DIP_DURATION     = 0.6     # seconds brush sits in ink
DRIP_DURATION    = 1.2     # seconds after lifting (let it drip)
# ─────────────────────────────────────────────────────────────────────────────

PAPER = PaperConfig(width=148.0, height=210.0, margin_x=10.0, margin_y=10.0)
DX0, DY0, DX1, DY1 = PAPER.get_drawable_area()
CX, CY = (DX0 + DX1) / 2, (DY0 + DY1) / 2


def spiral_cmds(cx, cy, r_start=5.0, r_end=35.0, turns=4, points=200, f=1500):
    """Outward Archimedean spiral — one continuous stroke."""
    cmds = []
    for i in range(points + 1):
        t = turns * 2 * math.pi * i / points
        r = r_start + (r_end - r_start) * i / points
        x = round(cx + r * math.cos(t), 2)
        y = round(cy + r * math.sin(t), 2)
        if i == 0:
            cmds.append(GCodeCommand(command="G0", x=x, y=y))
        else:
            cmds.append(GCodeCommand(command="G1", x=x, y=y, f=f))
    cmds.append(GCodeCommand(command="M5"))
    return cmds


def concentric_circles(cx, cy, radii=(15, 25, 35), n=48, f=1800):
    """Several concentric circles — each is a separate stroke (triggers dips)."""
    cmds = []
    for r in radii:
        for i in range(n + 1):
            a = 2 * math.pi * i / n
            x = round(cx + r * math.cos(a), 2)
            y = round(cy + r * math.sin(a), 2)
            cmds.append(GCodeCommand(command="G0" if i == 0 else "G1",
                                     x=x, y=y, f=f if i > 0 else None))
        cmds.append(GCodeCommand(command="M5"))
    return cmds


def build_drawing():
    cmds = []
    # Spiral in center
    cmds += spiral_cmds(CX, CY)
    # Concentric circles offset slightly
    cmds += concentric_circles(CX, CY, radii=(18, 28, 38))
    # A few radial lines for texture
    for angle in range(0, 360, 45):
        a = math.radians(angle)
        x1 = round(CX + 10 * math.cos(a), 2)
        y1 = round(CY + 10 * math.sin(a), 2)
        x2 = round(CX + 38 * math.cos(a), 2)
        y2 = round(CY + 38 * math.sin(a), 2)
        cmds += [
            GCodeCommand(command="G0", x=x1, y=y1),
            GCodeCommand(command="G1", x=x2, y=y2, f=1600),
            GCodeCommand(command="M5"),
        ]
    return cmds


async def run(simulate: bool, port: str, baud: int):
    cfg = PromptPlotConfig()
    cfg.paper = PAPER

    # ── brush config ──────────────────────────────────────────────────────────
    cfg.brush.enabled             = True
    cfg.brush.charge_position     = (INK_WELL_X, INK_WELL_Y)
    cfg.brush.dip_duration        = DIP_DURATION
    cfg.brush.drip_duration       = DRIP_DURATION
    cfg.brush.strokes_before_reload = STROKES_PER_DIP
    # ─────────────────────────────────────────────────────────────────────────

    raw = build_drawing()
    program = merge_chunks([raw], cfg)

    # Count dip sequences in the postprocessed program
    dip_count = sum(
        1 for i, c in enumerate(program.commands)
        if c.command == "G0" and c.x == INK_WELL_X and c.y == INK_WELL_Y
    )

    g1s = [c for c in program.commands if c.command == "G1"]
    xs = [c.x for c in g1s if c.x]; ys = [c.y for c in g1s if c.y]
    print(f"Paper     : A5 drawable X[{DX0},{DX1}] Y[{DY0},{DY1}] mm")
    print(f"Ink well  : ({INK_WELL_X}, {INK_WELL_Y}) mm")
    print(f"Dip every : {STROKES_PER_DIP} strokes  ({DIP_DURATION}s dip + {DRIP_DURATION}s drip)")
    print(f"Commands  : {len(program.commands)}  (including {dip_count} ink reloads)")
    if xs:
        print(f"Draw bbox : X={min(xs):.1f}–{max(xs):.1f}  Y={min(ys):.1f}–{max(ys):.1f}")
    print(f"Mode      : {'SIMULATE' if simulate else 'LIVE → Leo'}")
    print()

    # Show the first dip sequence so the user knows what to expect
    for i, cmd in enumerate(program.commands):
        if cmd.command == "G0" and cmd.x == INK_WELL_X and cmd.y == INK_WELL_Y:
            print("First ink reload sequence:")
            for c in program.commands[i-1:i+8]:
                print(f"  {c.to_gcode()}")
            print()
            break

    if simulate:
        plotter = SimulatedPlotter()
        await plotter.connect()
    else:
        plotter = SerialPlotter(port=port, baud_rate=baud)
        ok = await plotter.connect()
        if not ok:
            print(f"ERROR: could not connect to {port}")
            sys.exit(1)

    ok_count, err_count = await plotter.stream_program(program, verbose=not simulate)
    if not simulate:
        await plotter.disconnect()

    print(f"\nDone: {ok_count} ok  {err_count} errors  total={len(program.commands)}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--port", default="/dev/cu.usbserial-14120")
    p.add_argument("--baud", type=int, default=115200)
    p.add_argument("--simulate", action="store_true", default=False)
    args = p.parse_args()
    asyncio.run(run(args.simulate, args.port, args.baud))
