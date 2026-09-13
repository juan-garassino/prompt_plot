"""
Test OpenRouter and NVIDIA NIM providers — one LLM call each, then stream.

Usage:
  python scripts/cc_llm_test.py --simulate
  python scripts/cc_llm_test.py --provider nvidia
  python scripts/cc_llm_test.py --provider openrouter
"""

import asyncio
import argparse
import json
import sys
import re

from promptplot.config import PromptPlotConfig, PaperConfig
from promptplot.plotter import SerialPlotter, SimulatedPlotter
from promptplot.models import GCodeCommand, GCodeProgram
from promptplot.orchestrate import merge_chunks
from promptplot.llm import (
    NvidiaProvider,
    OpenRouterProvider,
    build_gcode_prompt,
)

PAPER = PaperConfig(width=148.0, height=210.0, margin_x=10.0, margin_y=10.0)

PROVIDERS = {
    "nvidia": lambda: NvidiaProvider(
        model="meta/llama-3.2-11b-vision-instruct",
        max_tokens=2048,
        timeout=180,
    ),
    "openrouter": lambda: OpenRouterProvider(
        model="nvidia/nemotron-3-ultra-550b-a55b:free",
        max_tokens=2048,
        timeout=180,
    ),
}

PROMPT = "draw a simple flower: circle center, 6 oval petals around it"

# Short, focused prompt that fits in small-model context windows
MINI_SYSTEM = """You are a GCode generator for a pen plotter.
Paper: 148x210mm, margins 10mm each side. Draw area: X[10,138] Y[10,200].
Center everything at (74,105).

Respond ONLY with valid JSON, no markdown, no explanation:
{"commands": [{"command":"G0","x":X,"y":Y}, {"command":"M3","s":1000}, {"command":"G1","x":X,"y":Y,"f":2000}, ..., {"command":"M5"}]}

Commands: G0 = move pen up (travel), M3 = pen down, G1 = draw line, M5 = pen up.
Every drawing stroke: G0 to start → M3 → G1 lines → M5.
Coordinates in mm. Keep all coords within X[10,138] Y[10,200]."""


def parse_commands(raw: str) -> list[GCodeCommand]:
    """Extract GCodeCommands from whatever JSON the LLM returned."""
    raw = raw.strip()
    # Strip markdown fences
    raw = re.sub(r"^```[a-z]*\n?", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"\n?```$", "", raw, flags=re.MULTILINE)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Models with chain-of-thought wrap JSON in prose — find the first { and parse from there
        start = raw.find('{"commands"')
        if start == -1:
            start = raw.find('{')
        if start == -1:
            raise ValueError("No JSON found in LLM response")
        try:
            data = json.loads(raw[start:])
        except json.JSONDecodeError:
            # Walk backwards from the end to find valid JSON
            for end in range(len(raw), start, -1):
                try:
                    data = json.loads(raw[start:end])
                    break
                except json.JSONDecodeError:
                    continue
            else:
                raise ValueError("Could not parse JSON from LLM response")

    cmds_raw = data.get("commands", [])
    cmds = []
    for item in cmds_raw:
        if isinstance(item, dict):
            cmd_str = item.get("command", "")
            # Support flat format {"command":"G1","x":10,"y":20} and
            # params format {"command":"G1","params":{"X":10,"Y":20}}
            params = item.get("params", {})
            x = item.get("x") or item.get("X") or params.get("x") or params.get("X")
            y = item.get("y") or item.get("Y") or params.get("y") or params.get("Y")
            f = item.get("f") or item.get("F") or params.get("f") or params.get("F")
            s = item.get("s") or item.get("S") or params.get("s") or params.get("S")
            if x is not None:
                x = float(x)
            if y is not None:
                y = float(y)
            if f is not None:
                f = int(f)
            if s is not None:
                s = int(s)
            cmds.append(GCodeCommand(command=cmd_str, x=x, y=y, f=f, s=s))
    return cmds


async def run_provider(name: str, simulate: bool, port: str, baud: int):
    cfg = PromptPlotConfig()
    cfg.paper = PAPER

    provider = PROVIDERS[name]()
    print(f"\n{'='*60}")
    print(f"Provider: {name.upper()} — {provider.model}")
    print(f"Prompt:   {PROMPT}")
    print(f"{'='*60}")

    system_prompt = MINI_SYSTEM + f"\n\nTask: {PROMPT}"
    print(f"Prompt length: {len(system_prompt)} chars")
    print("Calling LLM...", flush=True)
    try:
        raw = await provider.acomplete(system_prompt)
    except Exception as e:
        import traceback
        print(f"LLM call failed: {type(e).__name__}: {e}")
        traceback.print_exc()
        return False
    print(f"Got {len(raw)} chars")
    print("--- Raw response (first 300 chars) ---")
    print(raw[:300])
    print("--------------------------------------")

    try:
        cmds = parse_commands(raw)
    except Exception as e:
        print(f"ERROR: could not parse response: {e}")
        return False

    if not cmds:
        print("ERROR: no commands parsed")
        return False

    print(f"Parsed {len(cmds)} commands")
    program: GCodeProgram = merge_chunks([cmds], cfg)
    print(f"After postprocess: {len(program.commands)} commands")

    g1s = [c for c in program.commands if c.command == "G1"]
    if g1s:
        xs = [c.x for c in g1s if c.x is not None]
        ys = [c.y for c in g1s if c.y is not None]
        if xs:
            print(f"Draw bbox: X={min(xs):.1f}–{max(xs):.1f}  Y={min(ys):.1f}–{max(ys):.1f}")

    if simulate:
        plotter = SimulatedPlotter()
        await plotter.connect()
    else:
        plotter = SerialPlotter(port=port, baud_rate=baud)
        ok = await plotter.connect()
        if not ok:
            print(f"ERROR: could not connect to {port}")
            return False

    print(f"Streaming {'(simulated)' if simulate else 'to plotter'}...")
    ok_count, err_count = await plotter.stream_program(program, verbose=False)
    if not simulate:
        await plotter.disconnect()

    print(f"Done: {ok_count} ok  {err_count} errors")
    return err_count == 0


async def main(provider: str, simulate: bool, port: str, baud: int):
    if provider == "both":
        for name in ["nvidia", "openrouter"]:
            try:
                await run_provider(name, simulate, port, baud)
            except Exception as e:
                import traceback
                print(f"ERROR [{name}]: {e}")
                traceback.print_exc()
    else:
        await run_provider(provider, simulate, port, baud)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--provider", default="both", choices=["nvidia", "openrouter", "both"])
    p.add_argument("--port", default="/dev/cu.usbserial-14120")
    p.add_argument("--baud", type=int, default=115200)
    p.add_argument("--simulate", action="store_true", default=False)
    args = p.parse_args()
    asyncio.run(main(args.provider, args.simulate, args.port, args.baud))
