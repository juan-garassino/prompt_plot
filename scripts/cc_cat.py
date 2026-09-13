"""CC-CAT: Small cat — head, ears, eyes, nose, mouth, whiskers, body, tail.

Hand-crafted by Claude Code. PRIMITIVE blocks for circles/ellipse;
raw G1 strokes for ears, whiskers, nose, mouth, tail.

Usage:
  python scripts/cc_cat.py --simulate
  python scripts/cc_cat.py
"""

import asyncio
import argparse
import math
import sys

from promptplot.config import PromptPlotConfig, PaperConfig
from promptplot.plotter import SerialPlotter, SimulatedPlotter
from promptplot.models import GCodeCommand, GCodeProgram, DrawProgram
from promptplot.orchestrate import merge_chunks
from promptplot.primitives import expand_primitives

# ---------------------------------------------------------------------------
# A5 paper — same as cc_hello_world
# ---------------------------------------------------------------------------
PAPER = PaperConfig(width=148.0, height=210.0, margin_x=10.0, margin_y=10.0)
DX0, DY0, DX1, DY1 = PAPER.get_drawable_area()   # 10, 10, 138, 200

PEN_UP_DWELL   = 0.5
PEN_DOWN_DWELL = 0.5

# ---------------------------------------------------------------------------
# Cat geometry — all coordinates in mm, origin = machine home (0,0)
# Centered at (74, 115) on A5
# ---------------------------------------------------------------------------
CX, CY = 74.0, 115.0   # drawing center

# Head
HEAD_CX, HEAD_CY, HEAD_R = CX, CY + 10, 13.0

# Body
BODY_CX, BODY_CY, BODY_RX, BODY_RY = CX, CY - 8, 17.0, 11.0

# Ears (triangles)
EAR_L = [(HEAD_CX - 13, HEAD_CY + 8),
          (HEAD_CX - 10, HEAD_CY + 21),
          (HEAD_CX - 4,  HEAD_CY + 8)]
EAR_R = [(HEAD_CX + 4,  HEAD_CY + 8),
          (HEAD_CX + 10, HEAD_CY + 21),
          (HEAD_CX + 13, HEAD_CY + 8)]

# Eyes (small circles)
EYE_L = (HEAD_CX - 5, HEAD_CY + 3, 1.5)   # (cx, cy, r)
EYE_R = (HEAD_CX + 5, HEAD_CY + 3, 1.5)

# Nose (small inverted triangle)
NOSE = [(HEAD_CX - 2, HEAD_CY - 2),
        (HEAD_CX + 2, HEAD_CY - 2),
        (HEAD_CX,     HEAD_CY - 5)]

# Mouth (two lines down from nose tip)
MOUTH = [
    [(HEAD_CX, HEAD_CY - 5), (HEAD_CX - 3, HEAD_CY - 8)],
    [(HEAD_CX, HEAD_CY - 5), (HEAD_CX + 3, HEAD_CY - 8)],
]

# Whiskers (3 per side)
WHISKERS_L = [
    [(HEAD_CX - 13, HEAD_CY + 0), (HEAD_CX - 5, HEAD_CY - 1)],
    [(HEAD_CX - 13, HEAD_CY - 3), (HEAD_CX - 5, HEAD_CY - 3)],
    [(HEAD_CX - 13, HEAD_CY - 6), (HEAD_CX - 5, HEAD_CY - 5)],
]
WHISKERS_R = [
    [(HEAD_CX + 5, HEAD_CY - 1), (HEAD_CX + 13, HEAD_CY + 0)],
    [(HEAD_CX + 5, HEAD_CY - 3), (HEAD_CX + 13, HEAD_CY - 3)],
    [(HEAD_CX + 5, HEAD_CY - 5), (HEAD_CX + 13, HEAD_CY - 6)],
]

# Tail: S-curve from right of body sweeping up
TAIL = [
    (BODY_CX + BODY_RX,       BODY_CY),
    (BODY_CX + BODY_RX + 7,   BODY_CY + 7),
    (BODY_CX + BODY_RX + 6,   BODY_CY + 14),
    (BODY_CX + BODY_RX + 2,   BODY_CY + 18),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def circle_cmds(cx, cy, r, segments=32):
    """Raw GCodeCommands for a closed circle."""
    cmds = []
    for i in range(segments + 1):
        angle = 2 * math.pi * i / segments
        x = round(cx + r * math.cos(angle), 2)
        y = round(cy + r * math.sin(angle), 2)
        if i == 0:
            cmds.append(GCodeCommand(command="G0", x=x, y=y))
        else:
            cmds.append(GCodeCommand(command="G1", x=x, y=y, f=2000))
    cmds.append(GCodeCommand(command="M5"))
    return cmds


def ellipse_cmds(cx, cy, rx, ry, segments=48):
    """Raw GCodeCommands for a closed ellipse."""
    cmds = []
    for i in range(segments + 1):
        angle = 2 * math.pi * i / segments
        x = round(cx + rx * math.cos(angle), 2)
        y = round(cy + ry * math.sin(angle), 2)
        if i == 0:
            cmds.append(GCodeCommand(command="G0", x=x, y=y))
        else:
            cmds.append(GCodeCommand(command="G1", x=x, y=y, f=2000))
    cmds.append(GCodeCommand(command="M5"))
    return cmds


def poly_cmds(points, close=True):
    """Raw GCodeCommands for a polyline/polygon."""
    cmds = []
    for i, (x, y) in enumerate(points):
        if i == 0:
            cmds.append(GCodeCommand(command="G0", x=round(x, 2), y=round(y, 2)))
        else:
            cmds.append(GCodeCommand(command="G1", x=round(x, 2), y=round(y, 2), f=2500))
    if close and len(points) > 1:
        x0, y0 = points[0]
        cmds.append(GCodeCommand(command="G1", x=round(x0, 2), y=round(y0, 2), f=2500))
    cmds.append(GCodeCommand(command="M5"))
    return cmds


def line_cmds(p0, p1):
    """Single stroke from p0 to p1."""
    cmds = [
        GCodeCommand(command="G0", x=round(p0[0], 2), y=round(p0[1], 2)),
        GCodeCommand(command="G1", x=round(p1[0], 2), y=round(p1[1], 2), f=2500),
        GCodeCommand(command="M5"),
    ]
    return cmds


def build_cat():
    all_cmds = []
    all_cmds += ellipse_cmds(BODY_CX, BODY_CY, BODY_RX, BODY_RY)   # body
    all_cmds += circle_cmds(HEAD_CX, HEAD_CY, HEAD_R)                # head
    all_cmds += poly_cmds(EAR_L)                                     # left ear
    all_cmds += poly_cmds(EAR_R)                                     # right ear
    all_cmds += circle_cmds(*EYE_L, segments=16)                     # left eye
    all_cmds += circle_cmds(*EYE_R, segments=16)                     # right eye
    all_cmds += poly_cmds(NOSE)                                      # nose
    for seg in MOUTH:
        all_cmds += line_cmds(*seg)                                  # mouth
    for seg in WHISKERS_L + WHISKERS_R:
        all_cmds += line_cmds(*seg)                                  # whiskers
    all_cmds += poly_cmds(TAIL, close=False)                         # tail
    return all_cmds


def preflight(program: GCodeProgram) -> bool:
    violations = []
    mx0, my0, mx1, my1 = 0.0, 0.0, PAPER.width, PAPER.height
    for i, cmd in enumerate(program.commands):
        if cmd.command == "G1":
            if cmd.x is not None and not (DX0 <= cmd.x <= DX1):
                violations.append(f"Cmd {i} G1: X={cmd.x:.1f} outside [{DX0},{DX1}]")
            if cmd.y is not None and not (DY0 <= cmd.y <= DY1):
                violations.append(f"Cmd {i} G1: Y={cmd.y:.1f} outside [{DY0},{DY1}]")
        elif cmd.command == "G0":
            if cmd.x is not None and not (mx0 <= cmd.x <= mx1):
                violations.append(f"Cmd {i} G0: X={cmd.x:.1f} outside [{mx0},{mx1}]")
            if cmd.y is not None and not (my0 <= cmd.y <= my1):
                violations.append(f"Cmd {i} G0: Y={cmd.y:.1f} outside [{my0},{my1}]")
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

    raw = build_cat()
    program: GCodeProgram = merge_chunks([raw], cfg)

    # print bounding box
    xs = [c.x for c in program.commands if c.x is not None]
    ys = [c.y for c in program.commands if c.y is not None]
    print(f"Paper A5: drawable X[{DX0},{DX1}] Y[{DY0},{DY1}] mm")
    print(f"Cat bbox: X={min(xs):.1f}–{max(xs):.1f}  Y={min(ys):.1f}–{max(ys):.1f}")
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
