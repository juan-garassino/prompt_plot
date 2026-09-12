"""CC-HW: HELLO WORLD in typewriter block-letter strokes — A5 bounds.

No LLM call. Always validates bounds before streaming; aborts on violation.

Paper:  A5  148×210mm, 10mm margins → drawable [10,138]×[10,200] mm
Origin: machine home = (0, 0) — pen starts there, returns there at end.

Usage:
  python scripts/cc_hello_world.py --simulate    # dry-run, no hardware
  python scripts/cc_hello_world.py               # stream to plotter
"""

import asyncio
import argparse
import sys

from promptplot.config import PromptPlotConfig, PaperConfig
from promptplot.plotter import SerialPlotter, SimulatedPlotter
from promptplot.models import GCodeCommand, GCodeProgram
from promptplot.orchestrate import merge_chunks
from promptplot.postprocess import validate_bounds

# ---------------------------------------------------------------------------
# Paper / bounds — A5, 10mm margins → drawable [10,138]×[10,200] mm
# ---------------------------------------------------------------------------
PAPER = PaperConfig(width=148.0, height=210.0, margin_x=10.0, margin_y=10.0)
DX0, DY0, DX1, DY1 = PAPER.get_drawable_area()   # 10, 10, 138, 200

# ---------------------------------------------------------------------------
# Pen timing — conservative delays for mechanical servo/solenoid
# ---------------------------------------------------------------------------
PEN_UP_DWELL   = 0.5   # seconds after M5 (pen lift) before moving
PEN_DOWN_DWELL = 0.5   # seconds after M3 (pen lower) before drawing

# ---------------------------------------------------------------------------
# Letter geometry — local (0..W)×(0..H), origin = bottom-left of each letter
# ---------------------------------------------------------------------------
W = 7.0      # letter width mm
H = 12.0     # letter height mm
GAP = 3.0    # gap between letters mm
WORD_GAP = 7.0

LETTERS = {
    "H": [[(0, 0), (0, H)],
          [(0, H/2), (W, H/2)],
          [(W, 0), (W, H)]],
    "E": [[(0, 0), (0, H), (W, H)],
          [(0, H/2), (W*0.75, H/2)],
          [(0, 0), (W, 0)]],
    "L": [[(0, H), (0, 0), (W, 0)]],
    "O": [[(W*0.2, 0), (0, H*0.2), (0, H*0.8), (W*0.2, H),
           (W*0.8, H), (W, H*0.8), (W, H*0.2), (W*0.8, 0), (W*0.2, 0)]],
    "W": [[(0, H), (W*0.2, 0), (W*0.5, H*0.5), (W*0.8, 0), (W, H)]],
    "R": [[(0, 0), (0, H), (W*0.7, H), (W, H*0.75), (W*0.7, H*0.5), (0, H*0.5)],
          [(W*0.5, H*0.5), (W, 0)]],
    "D": [[(0, 0), (0, H), (W*0.6, H), (W, H*0.7), (W, H*0.3), (W*0.6, 0), (0, 0)]],
    " ": [],
}


def _text_width(text: str) -> float:
    """Total width the text occupies (cursor end position - cursor start)."""
    cursor = 0.0
    for ch in text.upper():
        if ch == " ":
            cursor += WORD_GAP
        elif ch in LETTERS:
            cursor += W + GAP
    return cursor - GAP  # subtract trailing gap after last letter


def make_cmds(text: str, ox: float, oy: float):
    """Build raw GCodeCommand list for text starting at (ox, oy) baseline."""
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
                                         f=3000))
            cmds.append(GCodeCommand(command="M5"))
        cursor += W + GAP
    return cmds


def preflight(program: GCodeProgram) -> bool:
    """Check coordinates before streaming.

    G1 (pen-down draw) must stay within drawable area (includes margins).
    G0 (pen-up travel) must stay within machine extents (full paper, no margins).
    """
    violations = []
    mx0, my0, mx1, my1 = 0.0, 0.0, PAPER.width, PAPER.height  # machine extents

    for i, cmd in enumerate(program.commands):
        if cmd.command == "G1":
            # Draw moves: must be inside drawable area (with margins)
            if cmd.x is not None and not (DX0 <= cmd.x <= DX1):
                violations.append(f"Cmd {i} G1 draw: X={cmd.x:.1f} outside drawable [{DX0},{DX1}]")
            if cmd.y is not None and not (DY0 <= cmd.y <= DY1):
                violations.append(f"Cmd {i} G1 draw: Y={cmd.y:.1f} outside drawable [{DY0},{DY1}]")
        elif cmd.command == "G0":
            # Travel moves: must be inside machine extents (no margins)
            if cmd.x is not None and not (mx0 <= cmd.x <= mx1):
                violations.append(f"Cmd {i} G0 travel: X={cmd.x:.1f} outside machine [{mx0},{mx1}]")
            if cmd.y is not None and not (my0 <= cmd.y <= my1):
                violations.append(f"Cmd {i} G0 travel: Y={cmd.y:.1f} outside machine [{my0},{my1}]")

    if violations:
        print(f"\n⛔  BOUNDS VIOLATION — {len(violations)} command(s) out of range")
        for v in violations[:15]:
            print(f"   {v}")
        if len(violations) > 15:
            print(f"   … and {len(violations)-15} more")
        return False
    return True


async def run(port: str, baud: int, simulate: bool):
    text = "HELLO WORLD"

    # Center in A5 drawable area
    tw = _text_width(text)
    ox = DX0 + (DX1 - DX0 - tw) / 2   # left edge of first letter
    oy = DY0 + (DY1 - DY0 - H) / 2    # baseline (bottom of letters)

    print(f"Paper A5: drawable X[{DX0},{DX1}] Y[{DY0},{DY1}] mm")
    print(f"Text '{text}': {tw:.1f}mm wide × {H:.1f}mm tall")
    print(f"Placed at: X={ox:.1f}–{ox+tw:.1f}  Y={oy:.1f}–{oy+H:.1f}")
    print(f"Pen dwells: up={PEN_UP_DWELL}s  down={PEN_DOWN_DWELL}s")
    print(f"Start / end position: (0, 0)")

    # Build config — A5 paper + conservative pen timing
    cfg = PromptPlotConfig()
    cfg.paper = PAPER
    cfg.pen.pen_up_delay   = PEN_UP_DWELL
    cfg.pen.pen_down_delay = PEN_DOWN_DWELL

    raw = make_cmds(text, ox, oy)
    program: GCodeProgram = merge_chunks([raw], cfg)

    # Hard pre-flight — abort before touching hardware
    if not preflight(program):
        print("Aborting — fix bounds before sending.")
        sys.exit(1)

    print(f"\n✓  {len(program.commands)} commands  all within bounds  simulate={simulate}\n")

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

    print(f"\nDone: {success} ok  {errors} errors  total={len(program.commands)}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--port", default="/dev/cu.usbserial-14120")
    p.add_argument("--baud", type=int, default=115200)
    p.add_argument("--simulate", action="store_true", default=False)
    args = p.parse_args()
    asyncio.run(run(args.port, args.baud, args.simulate))
