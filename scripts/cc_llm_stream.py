"""
Real-time LLM streaming to pen plotter.

The LLM outputs one GCode command per line (NDJSON).
We parse each line the moment the token arrives and send it to Leo immediately.
No waiting for the full response.

Usage:
  python scripts/cc_llm_stream.py --simulate
  python scripts/cc_llm_stream.py --provider nvidia
  python scripts/cc_llm_stream.py --provider openrouter
"""

import asyncio
import argparse
import sys

from promptplot.config import PromptPlotConfig, PaperConfig
from promptplot.plotter import SerialPlotter, SimulatedPlotter
from promptplot.postprocess import validate_single_command
from promptplot.llm import NvidiaProvider, OpenRouterProvider

PAPER = PaperConfig(width=148.0, height=210.0, margin_x=10.0, margin_y=10.0)

PROVIDERS = {
    "nvidia": lambda: NvidiaProvider(
        model="meta/llama-3.2-11b-vision-instruct",
        max_tokens=1024,
        timeout=180,
    ),
    "openrouter": lambda: OpenRouterProvider(
        model="google/gemma-4-26b-a4b-it:free",
        max_tokens=1024,
        timeout=180,
    ),
}

# Ask the model to emit ONE command per line as plain JSON — no wrapper array.
STREAM_PROMPT_TEMPLATE = """\
You are a GCode controller for a pen plotter.
Paper: 148x210mm. Draw area: X[10,138] Y[10,200]. Center: (74,105).

Output ONE command per line as JSON. Nothing else — no markdown, no explanation.
Format examples:
{{"command":"G0","x":74,"y":105}}
{{"command":"M3","s":1000}}
{{"command":"G1","x":84,"y":105,"f":2000}}
{{"command":"M5"}}

Rules:
- Start every stroke: G0 to position then M3 then G1 lines then M5
- G0 = pen up travel, M3 = pen down, G1 = draw, M5 = pen up
- All X/Y coords in mm, within [10,138] x [10,200]
- End with M5 then G0 x:0 y:0

Task: {task}"""


async def run(task: str, provider_name: str, simulate: bool, port: str, baud: int):
    cfg = PromptPlotConfig()
    cfg.paper = PAPER

    provider = PROVIDERS[provider_name]()
    print(f"Provider : {provider_name.upper()} — {provider.model}")
    print(f"Task     : {task}")
    print(f"Streaming: {'simulate' if simulate else port}")
    print()

    if simulate:
        plotter = SimulatedPlotter()
        await plotter.connect()
    else:
        plotter = SerialPlotter(port=port, baud_rate=baud)
        ok = await plotter.connect()
        if not ok:
            print(f"ERROR: could not connect to {port}")
            sys.exit(1)

    pen_is_down = False
    sent = 0
    skipped = 0
    prompt = STREAM_PROMPT_TEMPLATE.format(task=task)

    print("─" * 50)
    async for cmd in provider.astream_commands(prompt):
        # Validate + auto-insert pen safety commands
        fixed, warnings, prefix = validate_single_command(cmd, PAPER, pen_is_down=pen_is_down)

        for pre in prefix:
            ok = await plotter.send_command(pre.to_gcode())
            label = "↑ M5" if pre.command == "M5" else "↓ M3"
            print(f"  {label} (auto-inserted)")
            sent += 1

        ok = await plotter.send_command(fixed.to_gcode())
        if ok:
            sent += 1
            # Track pen state
            if fixed.command == "M3":
                pen_is_down = True
            elif fixed.command == "M5":
                pen_is_down = False
            # Show progress
            if fixed.command == "G0":
                print(f"  → travel  ({fixed.x:.1f}, {fixed.y:.1f})")
            elif fixed.command == "G1":
                print(f"  → draw    ({fixed.x:.1f}, {fixed.y:.1f})")
            elif fixed.command in ("M3", "M5"):
                print(f"  → {'pen down' if fixed.command=='M3' else 'pen up '}")
        else:
            skipped += 1
            print(f"  ✗ failed: {fixed}")

        if warnings:
            for w in warnings:
                print(f"  ! {w}")

    # Always end pen up at home
    if pen_is_down:
        await plotter.send_command("M5")
        print("  ↑ M5 (final)")

    if not simulate:
        await plotter.disconnect()

    print("─" * 50)
    print(f"Done: {sent} sent  {skipped} skipped")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("task", nargs="?", default="draw a triangle")
    p.add_argument("--provider", default="nvidia", choices=["nvidia", "openrouter"])
    p.add_argument("--port", default="/dev/cu.usbserial-14120")
    p.add_argument("--baud", type=int, default=115200)
    p.add_argument("--simulate", action="store_true", default=False)
    args = p.parse_args()
    asyncio.run(run(args.task, args.provider, args.simulate, args.port, args.baud))
