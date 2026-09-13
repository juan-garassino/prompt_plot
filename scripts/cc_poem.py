"""CC-POEM: "The Road Not Taken" — small typewriter block-letters, A5.

Full A–Z uppercase font, all 13 lines centered vertically and per-line
horizontally. No LLM call.

Usage:
  python scripts/cc_poem.py --simulate
  python scripts/cc_poem.py
"""

import asyncio
import argparse
import sys

from promptplot.config import PromptPlotConfig, PaperConfig
from promptplot.plotter import SerialPlotter, SimulatedPlotter
from promptplot.models import GCodeCommand, GCodeProgram
from promptplot.orchestrate import merge_chunks

PAPER = PaperConfig(width=148.0, height=210.0, margin_x=10.0, margin_y=10.0)
DX0, DY0, DX1, DY1 = PAPER.get_drawable_area()

PEN_UP_DWELL   = 0.3
PEN_DOWN_DWELL = 0.3

# Letter geometry — half the size of the HELLO WORLD font
W = 4.0     # letter width  mm
H = 7.0     # letter height mm
GAP = 2.0   # inter-letter gap
WORD_GAP = 4.0   # space-character width
LINE_H = 10.0    # baseline-to-baseline (H + 3 mm line spacing)

POEM = [
    "THE ROAD NOT TAKEN",
    "BY ROBERT FROST",
    "",                         # blank line → extra gap
    "TWO ROADS DIVERGED",
    "IN A YELLOW WOOD",
    "AND SORRY I COULD",
    "NOT TRAVEL BOTH",
    "AND BE ONE TRAVELER",
    "LONG I STOOD AND",
    "LOOKED DOWN ONE AS",
    "FAR AS I COULD TO",
    "WHERE IT BENT IN",
    "THE UNDERGROWTH",
]

# All 26 uppercase letters defined in local (0..W)×(0..H) space.
# Each letter is a list of polyline strokes [[pt, pt, ...], ...].
LETTERS = {
    "A": [
        [(0, 0), (W/2, H), (W, 0)],
        [(W*0.2, H*0.4), (W*0.8, H*0.4)],
    ],
    "B": [
        [(0, 0), (0, H), (W*0.7, H), (W, H*0.75), (W*0.7, H/2), (0, H/2)],
        [(0, H/2), (W*0.7, H/2), (W, H*0.25), (W*0.7, 0), (0, 0)],
    ],
    "C": [
        [(W*0.9, H*0.8), (W*0.6, H), (W*0.2, H), (0, H*0.7),
         (0, H*0.3), (W*0.2, 0), (W*0.6, 0), (W*0.9, H*0.2)],
    ],
    "D": [
        [(0, 0), (0, H), (W*0.6, H), (W, H*0.7), (W, H*0.3), (W*0.6, 0), (0, 0)],
    ],
    "E": [
        [(0, 0), (0, H), (W, H)],
        [(0, H/2), (W*0.75, H/2)],
        [(0, 0), (W, 0)],
    ],
    "F": [
        [(0, 0), (0, H), (W, H)],
        [(0, H/2), (W*0.7, H/2)],
    ],
    "G": [
        [(W*0.9, H*0.8), (W*0.6, H), (W*0.2, H), (0, H*0.7),
         (0, H*0.3), (W*0.2, 0), (W*0.6, 0), (W, H*0.3),
         (W, H/2), (W/2, H/2)],
    ],
    "H": [
        [(0, 0), (0, H)],
        [(0, H/2), (W, H/2)],
        [(W, 0), (W, H)],
    ],
    "I": [
        [(W*0.1, H), (W*0.9, H)],
        [(W/2, H), (W/2, 0)],
        [(W*0.1, 0), (W*0.9, 0)],
    ],
    "J": [
        [(W*0.2, H), (W*0.8, H)],
        [(W*0.6, H), (W*0.6, H*0.2), (W*0.4, 0), (W*0.1, H*0.15)],
    ],
    "K": [
        [(0, 0), (0, H)],
        [(0, H/2), (W, H)],
        [(0, H/2), (W, 0)],
    ],
    "L": [
        [(0, H), (0, 0), (W, 0)],
    ],
    "M": [
        [(0, 0), (0, H), (W/2, H*0.4), (W, H), (W, 0)],
    ],
    "N": [
        [(0, 0), (0, H), (W, 0), (W, H)],
    ],
    "O": [
        [(W*0.2, 0), (0, H*0.2), (0, H*0.8), (W*0.2, H),
         (W*0.8, H), (W, H*0.8), (W, H*0.2), (W*0.8, 0), (W*0.2, 0)],
    ],
    "P": [
        [(0, 0), (0, H), (W*0.7, H), (W, H*0.75), (W*0.7, H/2), (0, H/2)],
    ],
    "Q": [
        [(W*0.2, 0), (0, H*0.2), (0, H*0.8), (W*0.2, H),
         (W*0.8, H), (W, H*0.8), (W, H*0.2), (W*0.8, 0), (W*0.2, 0)],
        [(W*0.6, H*0.3), (W*0.95, 0)],
    ],
    "R": [
        [(0, 0), (0, H), (W*0.7, H), (W, H*0.75), (W*0.7, H/2), (0, H/2)],
        [(W/2, H/2), (W, 0)],
    ],
    "S": [
        [(W*0.9, H*0.85), (W*0.6, H), (W*0.2, H), (0, H*0.75),
         (W/2, H/2), (W, H*0.25), (W*0.8, 0), (W*0.4, 0), (W*0.1, H*0.15)],
    ],
    "T": [
        [(0, H), (W, H)],
        [(W/2, H), (W/2, 0)],
    ],
    "U": [
        [(0, H), (0, H*0.2), (W*0.2, 0), (W*0.8, 0), (W, H*0.2), (W, H)],
    ],
    "V": [
        [(0, H), (W/2, 0), (W, H)],
    ],
    "W": [
        [(0, H), (W*0.2, 0), (W/2, H/2), (W*0.8, 0), (W, H)],
    ],
    "X": [
        [(0, H), (W, 0)],
        [(0, 0), (W, H)],
    ],
    "Y": [
        [(0, H), (W/2, H/2), (W, H)],
        [(W/2, H/2), (W/2, 0)],
    ],
    "Z": [
        [(0, H), (W, H), (0, 0), (W, 0)],
    ],
    " ": [],
}


def _text_width(text: str) -> float:
    cursor = 0.0
    for ch in text.upper():
        if ch == " ":
            cursor += WORD_GAP
        elif ch in LETTERS:
            cursor += W + GAP
    return max(0.0, cursor - GAP)


def make_line_cmds(text: str, ox: float, oy: float):
    cmds = []
    cursor = ox
    for ch in text.upper():
        if ch == " ":
            cursor += WORD_GAP
            continue
        for seg in LETTERS.get(ch, []):
            if not seg:
                continue
            x0, y0 = seg[0]
            cmds.append(GCodeCommand(command="G0",
                                     x=round(cursor + x0, 2),
                                     y=round(oy + y0, 2)))
            for x, y in seg[1:]:
                cmds.append(GCodeCommand(command="G1",
                                         x=round(cursor + x, 2),
                                         y=round(oy + y, 2),
                                         f=2500))
            cmds.append(GCodeCommand(command="M5"))
        cursor += W + GAP
    return cmds


def preflight(program: GCodeProgram) -> bool:
    violations = []
    mx0, my0, mx1, my1 = 0.0, 0.0, PAPER.width, PAPER.height
    for i, cmd in enumerate(program.commands):
        if cmd.command == "G1":
            if cmd.x is not None and not (DX0 <= cmd.x <= DX1):
                violations.append(f"Cmd {i} G1 X={cmd.x:.2f} [{DX0},{DX1}]")
            if cmd.y is not None and not (DY0 <= cmd.y <= DY1):
                violations.append(f"Cmd {i} G1 Y={cmd.y:.2f} [{DY0},{DY1}]")
        elif cmd.command == "G0":
            if cmd.x is not None and not (mx0 <= cmd.x <= mx1):
                violations.append(f"Cmd {i} G0 X={cmd.x:.2f} [{mx0},{mx1}]")
            if cmd.y is not None and not (my0 <= cmd.y <= my1):
                violations.append(f"Cmd {i} G0 Y={cmd.y:.2f} [{my0},{my1}]")
    if violations:
        print(f"\n⛔  {len(violations)} bounds violations:")
        for v in violations[:20]:
            print(f"   {v}")
        return False
    return True


async def run(port: str, baud: int, simulate: bool):
    cfg = PromptPlotConfig()
    cfg.paper = PAPER
    cfg.pen.pen_up_delay   = PEN_UP_DWELL
    cfg.pen.pen_down_delay = PEN_DOWN_DWELL

    n = len(POEM)
    total_h = (n - 1) * LINE_H + H

    cx = (DX0 + DX1) / 2
    cy = (DY0 + DY1) / 2
    y_top = cy + (total_h - H) / 2   # baseline of first (top) line

    raw = []
    for i, line in enumerate(POEM):
        if not line:
            continue
        y = y_top - i * LINE_H
        ox = cx - _text_width(line) / 2
        raw += make_line_cmds(line, ox, y)

    program: GCodeProgram = merge_chunks([raw], cfg)

    g1xs = [c.x for c in program.commands if c.command == "G1" and c.x is not None]
    g1ys = [c.y for c in program.commands if c.command == "G1" and c.y is not None]
    print(f"Paper A5: drawable X[{DX0},{DX1}] Y[{DY0},{DY1}] mm")
    if g1xs:
        print(f"Draw bbox: X={min(g1xs):.1f}–{max(g1xs):.1f}  Y={min(g1ys):.1f}–{max(g1ys):.1f}")
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

    success, errors = await plotter.stream_program(program, verbose=False)
    if not simulate:
        await plotter.disconnect()
    print(f"Done: {success} ok  {errors} errors  total={len(program.commands)}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--port", default="/dev/cu.usbserial-14120")
    p.add_argument("--baud", type=int, default=115200)
    p.add_argument("--simulate", action="store_true", default=False)
    args = p.parse_args()
    asyncio.run(run(args.port, args.baud, args.simulate))
