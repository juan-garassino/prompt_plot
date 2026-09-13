"""CC-01: Nested Field — mirrored to negative coords for top-right home / arm-extended setup.

Uses compose_and_stream end-to-end (no .gcode file). Skips bounds validation
because paper bounds are positive but we need negative coords.
"""
import asyncio
from promptplot.config import PromptPlotConfig
from promptplot.models import GCodeProgram, GCodeCommand, DrawProgram
from promptplot.primitives import expand_primitives
from promptplot.postprocess import ensure_pen_safety, insert_pen_dwells
from promptplot.plotter import SerialPlotter

PORT = "/dev/cu.usbserial-14220"

def cc_blocks():
    return [
        {"commands": [
            {"command": "PRIMITIVE", "type": "circle",
             "params": {"cx": 105, "cy": 150, "radius": r, "segments": 60}}
            for r in (8, 16, 24, 32, 40)
        ]},
        {"commands": [{"command": "PRIMITIVE", "type": "hatch",
                       "params": {"x": 45, "y": 160, "width": 50, "height": 50,
                                  "angle": 0, "spacing": 3}}]},
        {"commands": [{"command": "PRIMITIVE", "type": "crosshatch",
                       "params": {"x": 115, "y": 160, "width": 50, "height": 50,
                                  "spacing": 4}}]},
        {"commands": [{"command": "PRIMITIVE", "type": "stipple",
                       "params": {"x": 45, "y": 90, "width": 50, "height": 50,
                                  "density": 0.6, "dot_size": 0.6}}]},
        {"commands": [{"command": "PRIMITIVE", "type": "spiral",
                       "params": {"cx": 140, "cy": 115, "r_start": 0, "r_end": 22,
                                  "turns": 5, "segments": 240}}]},
    ]


def negate_xy(cmd):
    upd = {}
    if cmd.x is not None: upd["x"] = -cmd.x
    if cmd.y is not None: upd["y"] = -cmd.y
    return cmd.model_copy(update=upd) if upd else cmd


async def main():
    cfg = PromptPlotConfig()
    all_cmds = [GCodeCommand(command="M5")]
    for b in cc_blocks():
        dp = DrawProgram(**b)
        gp = expand_primitives(dp, cfg.pen)
        if all_cmds[-1].command != "M5":
            all_cmds.append(GCodeCommand(command="M5"))
        all_cmds.extend(gp.commands)
    if all_cmds[-1].command != "M5":
        all_cmds.append(GCodeCommand(command="M5"))

    mirrored = [negate_xy(c) for c in all_cmds]
    safe = ensure_pen_safety(mirrored, cfg.pen)
    program = GCodeProgram(commands=safe)
    program = insert_pen_dwells(program, cfg.pen)
    program.commands.append(GCodeCommand(command="G0", x=0.0, y=0.0, comment="return home"))

    print(f"composed {len(program.commands)} commands (mirrored, Grbl P seconds)")
    print("first 8:")
    for c in program.commands[:8]:
        print("  " + c.to_gcode())

    plt = SerialPlotter(port=PORT, baud_rate=115200)
    ok = await plt.connect()
    if not ok:
        print("connect failed")
        return
    print("connected. streaming...\n")
    success, errors = await plt.stream_program(program, verbose=True)
    await plt.disconnect()
    print(f"\ndone: {success} ok, {errors} errors")

asyncio.run(main())
