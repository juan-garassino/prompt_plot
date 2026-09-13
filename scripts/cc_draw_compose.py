"""CC-01: Nested Field — via compose_and_stream, positive coords, no intermediate .gcode."""
import asyncio
from promptplot.config import PromptPlotConfig
from promptplot.plotter import SerialPlotter
from promptplot.orchestrate import compose_and_stream

PORT = "/dev/cu.usbserial-14220"

BLOCKS = [
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


async def main():
    cfg = PromptPlotConfig()
    plt = SerialPlotter(port=PORT, baud_rate=115200)
    ok = await plt.connect()
    if not ok:
        print("connect failed")
        return
    print("connected. compose_and_stream...\n")
    program, success, errors = await compose_and_stream(BLOCKS, plt, cfg, verbose=True)
    await plt.disconnect()
    print(f"\ndone: {len(program.commands)} cmds  {success} ok  {errors} err")


asyncio.run(main())
