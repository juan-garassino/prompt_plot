"""CC-COOKIE: Chocolate chip cookie — circle outline + 7 chips.

Hand-crafted by Claude Code. No LLM calls.

Usage:
  python scripts/cc_cookie.py --simulate
  python scripts/cc_cookie.py
"""

import asyncio
import argparse
import math
import sys

from promptplot.config import PromptPlotConfig, PaperConfig
from promptplot.plotter import SerialPlotter, SimulatedPlotter
from promptplot.models import GCodeCommand, GCodeProgram
from promptplot.orchestrate import merge_chunks

PAPER = PaperConfig(width=148.0, height=210.0, margin_x=10.0, margin_y=10.0)
DX0, DY0, DX1, DY1 = PAPER.get_drawable_area()

PEN_UP_DWELL = 0.5
PEN_DOWN_DWELL = 0.5

CX, CY = 74.0, 105.0    # cookie center
COOKIE_R = 28.0          # cookie radius

# Chocolate chip positions (absolute mm) + radii
# 7 chips scattered inside the cookie, no chip closer than CHIP_R to the edge
CHIP_R_OUTER = 3.0
CHIP_R_INNER = 1.2
CHIPS = [
    (74.0, 116.0),   # top center
    (63.0, 113.0),   # upper left
    (85.0, 113.0),   # upper right
    (61.0, 103.0),   # left
    (87.0, 103.0),   # right
    (66.0,  93.0),   # lower left
    (82.0,  93.0),   # lower right
]


def circle_cmds(cx, cy, r, segments, f=2000):
    cmds = []
    for i in range(segments + 1):
        angle = 2 * math.pi * i / segments
        x = round(cx + r * math.cos(angle), 2)
        y = round(cy + r * math.sin(angle), 2)
        cmd = "G0" if i == 0 else "G1"
        cmds.append(GCodeCommand(command=cmd, x=x, y=y, f=f if i > 0 else None))
    cmds.append(GCodeCommand(command="M5"))
    return cmds


def build_cookie():
    cmds = []
    cmds += circle_cmds(CX, CY, COOKIE_R, segments=64, f=2500)
    for cx, cy in CHIPS:
        cmds += circle_cmds(cx, cy, CHIP_R_OUTER, segments=14, f=1800)
        cmds += circle_cmds(cx, cy, CHIP_R_INNER, segments=8,  f=1800)
    return cmds


def preflight(program: GCodeProgram) -> bool:
    violations = []
    mx0, my0, mx1, my1 = 0.0, 0.0, PAPER.width, PAPER.height
    for i, cmd in enumerate(program.commands):
        if cmd.command == "G1":
            if cmd.x is not None and not (DX0 <= cmd.x <= DX1):
                violations.append(f"Cmd {i} G1 X={cmd.x:.1f} outside [{DX0},{DX1}]")
            if cmd.y is not None and not (DY0 <= cmd.y <= DY1):
                violations.append(f"Cmd {i} G1 Y={cmd.y:.1f} outside [{DY0},{DY1}]")
        elif cmd.command == "G0":
            if cmd.x is not None and not (mx0 <= cmd.x <= mx1):
                violations.append(f"Cmd {i} G0 X={cmd.x:.1f} outside [{mx0},{mx1}]")
            if cmd.y is not None and not (my0 <= cmd.y <= my1):
                violations.append(f"Cmd {i} G0 Y={cmd.y:.1f} outside [{my0},{my1}]")
    if violations:
        print(f"\n⛔  {len(violations)} bounds violations:")
        for v in violations[:15]:
            print(f"   {v}")
        return False
    return True


async def run(port: str, baud: int, simulate: bool):
    cfg = PromptPlotConfig()
    cfg.paper = PAPER
    cfg.pen.pen_up_delay   = PEN_UP_DWELL
    cfg.pen.pen_down_delay = PEN_DOWN_DWELL

    raw = build_cookie()
    program: GCodeProgram = merge_chunks([raw], cfg)

    xs = [c.x for c in program.commands if c.x is not None]
    ys = [c.y for c in program.commands if c.y is not None]
    print(f"Paper A5: drawable X[{DX0},{DX1}] Y[{DY0},{DY1}] mm")
    print(f"Cookie bbox: X={min(xs):.1f}–{max(xs):.1f}  Y={min(ys):.1f}–{max(ys):.1f}")
    print(f"Commands: {len(program.commands)}  simulate={simulate}")

    if not preflight(program):
        print("Aborting.")
        sys.exit(1)
    print("✓ All within bounds\n")

    if simulate:
        plotter = SimulatedPlotter()
    else:
        plotter = SerialPlotter(port=port, baud_rate=baud)
        ok = await plotter.connect()
        if not ok:
            print(f"ERROR: could not connect to {port}")
            sys.exit(1)

    success, errors = await plotter.stream_program(program, verbose=True)
    if not simulate:
        await plotter.disconnect()
    print(f"\nDone: {success} ok  {errors} errors")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--port", default="/dev/cu.usbserial-14120")
    p.add_argument("--baud", type=int, default=115200)
    p.add_argument("--simulate", action="store_true", default=False)
    args = p.parse_args()
    asyncio.run(run(args.port, args.baud, args.simulate))
