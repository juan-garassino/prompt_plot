"""Stream ONE color layer of a seeded generative drawing to the plotter.

Regenerates the drawing deterministically from the seed, splits it into color
layers, and streams just the requested layer index. Used to drive a multi-color
pen exercise one pen at a time (draw layer, swap pen, run next layer).

Usage:
  python scripts/cc_art_layer.py flow_field --seed 42 --paper a5 \
      --palette black,red,blue,yellow --param particles=64 --layer 0 \
      --port /dev/cu.usbserial-14120
  # ...swap pen, then --layer 1, --layer 2, --layer 3
"""

import argparse
import asyncio
import sys

from promptplot.config import PromptPlotConfig, PaperConfig
from promptplot.generative import run_generator
from promptplot.orchestrate import merge_chunks, split_color_layers, trace_frame
from promptplot.plotter import SerialPlotter, SimulatedPlotter


def _parse_params(pairs):
    out = {}
    for p in pairs:
        k, v = p.split("=", 1)
        try:
            out[k] = int(v)
        except ValueError:
            try:
                out[k] = float(v)
            except ValueError:
                out[k] = v
    return out


async def run(args):
    cfg = PromptPlotConfig()
    cfg.paper = PaperConfig.from_size(args.paper, orientation=args.orientation, margin=args.margin)
    palette = [c.strip() for c in args.palette.split(",") if c.strip()]
    cfg.color.enabled = True
    cfg.color.palette = palette

    bounds = cfg.paper.get_drawable_area()
    raw = run_generator(
        args.generator, bounds, args.seed, colors=len(palette), params=_parse_params(args.param)
    )
    program = merge_chunks([raw], cfg)
    layers = split_color_layers(program)

    if args.layer >= len(layers):
        print(f"layer {args.layer} out of range (only {len(layers)} layers)")
        sys.exit(1)

    color_idx, cmds = layers[args.layer]
    name = palette[color_idx] if color_idx < len(palette) else f"color {color_idx}"
    print(f"layer {args.layer + 1}/{len(layers)}  pen={name}  commands={len(cmds)}")

    if args.simulate:
        plotter = SimulatedPlotter()
        await plotter.connect()
    else:
        # Heartbeat OFF: this script streams raw send_command (state stays IDLE),
        # so the 30s heartbeat poll would collide with the ack read and drop
        # commands (incl. pen-ups). Disabling it keeps the stream reliable.
        plotter = SerialPlotter(port=args.port, baud_rate=args.baud, enable_heartbeat=False)
        if not await plotter.connect():
            print(f"ERROR: could not connect to {args.port}")
            sys.exit(1)

    async def _send(g, retries=2):
        for _ in range(retries + 1):
            if await plotter.send_command(g):
                return True
        return False

    # Mandatory guardrail: show the drawable limits (pen-up) before marking paper.
    if not args.no_frame and not args.simulate:
        print("tracing limits (pen up) — check the drawing will land on the paper...")
        await trace_frame(plotter, cfg.paper, laps=1)

    ok = err = 0
    for c in cmds:
        g = c.to_gcode()
        if g == "COMPLETE":
            continue
        # Retry pen commands harder — a dropped M5/M3 ruins the drawing (pen drags).
        retries = 4 if c.command in ("M5", "M3") else 2
        if await _send(g, retries=retries):
            ok += 1
        else:
            err += 1
    # always finish pen-up + home
    await _send("M5", retries=4)
    await _send("G0 X0 Y0")
    if not args.simulate:
        await plotter.disconnect()
    print(f"done: {ok} ok, {err} errors")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("generator")
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--paper", default="a5")
    ap.add_argument("--orientation", default="portrait", choices=["portrait", "landscape"])
    ap.add_argument("--margin", type=float, default=10.0, help="Margin from the paper corner (mm)")
    ap.add_argument("--palette", default="black,red,blue,yellow")
    ap.add_argument("--param", action="append", default=[])
    ap.add_argument("--layer", type=int, required=True)
    ap.add_argument("--no-frame", action="store_true", help="Skip the pre-draw limits trace")
    ap.add_argument("--port", default="/dev/cu.usbserial-14120")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--simulate", action="store_true")
    asyncio.run(run(ap.parse_args()))
