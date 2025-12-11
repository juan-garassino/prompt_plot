#!/usr/bin/env python3
"""
LLM to Plotter Demo - Generate G-code and send to real plotter

This demo:
1. Uses an LLM (OpenAI/Gemini) to generate G-code from a prompt
2. Sends the generated G-code to a real pen plotter

Usage:
    uv run python examples/demo_llm_to_plotter.py /dev/cu.usbserial-14220 --prompt "draw a square"
    uv run python examples/demo_llm_to_plotter.py /dev/cu.usbserial-14220 --provider gemini
"""

import asyncio
import sys
import os
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from promptplot import SimpleGCodeWorkflow, get_config
from promptplot.plotter import SerialPlotter
from promptplot.llm.providers import OpenAIProvider, GeminiProvider


async def generate_gcode(prompt: str, provider: str = "openai"):
    """Generate G-code using LLM."""
    print(f"\n🤖 Generating G-code with {provider}...")
    print(f"   Prompt: '{prompt}'")
    
    # Create LLM provider
    if provider == "openai":
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            print("❌ OPENAI_API_KEY not set")
            return None
        llm_provider = OpenAIProvider(model='gpt-4o-mini', timeout=120)
    elif provider == "gemini":
        api_key = os.environ.get('GOOGLE_API_KEY')
        if not api_key:
            print("❌ GOOGLE_API_KEY not set")
            return None
        llm_provider = GeminiProvider(model='models/gemini-1.5-flash', timeout=120)
    else:
        print(f"❌ Unknown provider: {provider}")
        return None
    
    # Create workflow and generate
    workflow = SimpleGCodeWorkflow(
        llm=llm_provider.llm,
        max_retries=3,
        max_steps=10
    )
    
    result = await workflow.run(prompt=prompt)
    
    if result and result.get('commands_count', 0) > 0:
        print(f"✅ Generated {result['commands_count']} G-code commands")
        return result
    else:
        print("❌ Failed to generate G-code")
        return None


def convert_gcode_for_grbl(gcode: str) -> list:
    """
    Convert standard G-code to GRBL servo-compatible commands.
    
    GRBL pen plotters need:
    - M3 S1000 for pen down (not just M3)
    - M3 S0 for pen up (not M5)
    - S value on G1 commands to keep servo engaged in laser mode
    """
    lines = [line.strip() for line in gcode.split('\n') if line.strip()]
    converted = []
    pen_down = False
    
    for line in lines:
        # Skip comments
        if line.startswith(';'):
            continue
            
        # Convert pen commands
        if line == "M3" or line.startswith("M3 ") and "S" not in line:
            converted.append(("M3 S1000", True))  # Pen down
            pen_down = True
        elif line == "M5":
            converted.append(("M3 S0", True))     # Pen up
            pen_down = False
        elif line.startswith("G1"):
            # Add S value to keep servo engaged during moves
            if pen_down and "S" not in line:
                # Add S1000 to keep pen down during move
                if "F" in line:
                    # Insert S before F
                    parts = line.split("F")
                    cmd = parts[0].strip() + " S1000 F" + parts[1]
                else:
                    cmd = line + " S1000"
                converted.append((cmd, False))
            else:
                converted.append((line, False))
        elif line.startswith("G0"):
            # Rapid moves - pen should be up
            converted.append((line, False))
        elif line.startswith("G28"):
            # Home command
            converted.append((line, False))
        else:
            # Other commands pass through
            converted.append((line, False))
    
    return converted


async def send_to_plotter(port: str, gcode: str, pen_delay: float = 1.0):
    """Send G-code to the plotter."""
    print(f"\n🖊️  Sending to plotter on {port}...")
    
    # Convert G-code for GRBL servo compatibility
    commands = convert_gcode_for_grbl(gcode)
    print(f"   Total commands: {len(commands)}")
    
    # Connect to plotter
    plotter = SerialPlotter(port=port, timeout=10.0)
    
    try:
        await plotter.connect_with_retry()
        print(f"✅ Connected to plotter")
        
        # Home first
        print("   [0] G28 (homing)")
        await plotter.send_command_safe("G28")
        await asyncio.sleep(2.0)
        
        # Pen up to start
        print("   [0] M3 S0 (pen up)")
        await plotter.send_command_safe("M3 S0")
        await asyncio.sleep(pen_delay)
        
        # Send each command
        success_count = 0
        for i, (cmd, is_pen_cmd) in enumerate(commands):
            print(f"   [{i+1}/{len(commands)}] {cmd}")
            
            try:
                success = await plotter.send_command_safe(cmd)
                if success:
                    success_count += 1
                
                # Wait after pen commands to let servo settle
                if is_pen_cmd:
                    await asyncio.sleep(pen_delay)
                else:
                    await asyncio.sleep(0.05)  # Small delay between moves
                    
            except Exception as e:
                print(f"      ⚠️  Command failed: {e}")
        
        # Pen up at end
        print("   [end] M3 S0 (pen up)")
        await plotter.send_command_safe("M3 S0")
        await asyncio.sleep(pen_delay)
        
        # Home at end
        print("   [end] G28 (homing)")
        await plotter.send_command_safe("G28")
        
        print(f"\n✅ Sent {success_count}/{len(commands)} commands successfully")
        
    except Exception as e:
        print(f"❌ Plotter error: {e}")
    finally:
        await plotter.disconnect()
        print("🔌 Disconnected from plotter")


async def main():
    parser = argparse.ArgumentParser(description="Generate G-code with LLM and send to plotter")
    parser.add_argument("port", help="Serial port (e.g., /dev/cu.usbserial-14220)")
    parser.add_argument("--prompt", default="draw a small square", help="Drawing prompt")
    parser.add_argument("--provider", choices=["openai", "gemini"], default="openai", help="LLM provider")
    parser.add_argument("--pen-delay", type=float, default=1.0, help="Delay after pen up/down (seconds)")
    parser.add_argument("--dry-run", action="store_true", help="Generate G-code but don't send to plotter")
    
    args = parser.parse_args()
    
    print("🎨 PromptPlot - LLM to Plotter Demo")
    print("=" * 40)
    
    # Step 1: Generate G-code
    result = await generate_gcode(args.prompt, args.provider)
    
    if not result:
        print("\n❌ Failed to generate G-code")
        return 1
    
    # Show generated G-code
    gcode = result.get('gcode', '')
    print("\n📋 Generated G-code:")
    for i, line in enumerate(gcode.split('\n')[:10], 1):
        print(f"   {i:2d}. {line}")
    gcode_lines = gcode.split('\n')
    if len(gcode_lines) > 10:
        remaining = len(gcode_lines) - 10
        print(f"   ... and {remaining} more lines")
    
    if args.dry_run:
        print("\n🔍 Dry run - not sending to plotter")
        return 0
    
    # Step 2: Send to plotter
    await send_to_plotter(args.port, gcode, args.pen_delay)
    
    print("\n🎉 Done!")
    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⏹️  Interrupted")
        sys.exit(1)
