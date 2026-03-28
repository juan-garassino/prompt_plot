"""
Command-line interface for PromptPlot v3.0

Rich-based CLI replacing argparse+colorama with full Rich UI.
"""

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm

from .config import PromptPlotConfig, get_config, load_config
from .logger import WorkflowLogger

console = Console()
logger = WorkflowLogger(console)


def _get_config(config_path: Optional[str] = None) -> PromptPlotConfig:
    if config_path:
        return load_config(config_path)
    return get_config()


@click.group()
@click.version_option("3.0.0", prog_name="promptplot")
@click.option("--config", "config_path", default=None, help="Config file path")
@click.option("--debug", is_flag=True, help="Enable debug logging")
@click.pass_context
def cli(ctx, config_path, debug):
    """PromptPlot — LLM-driven pen plotter GCode generator."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = _get_config(config_path)
    ctx.obj["debug"] = debug


@cli.command()
@click.argument("prompt")
@click.option("--provider", default=None, help="LLM provider (ollama|openai|azure|gemini)")
@click.option("--model", default=None, help="Model name")
@click.option("--output", "-o", default=None, help="Output GCode file")
@click.option("--visualize", is_flag=True, help="Show preview after generation")
@click.option("--simulate", is_flag=True, help="Use simulated plotter")
@click.option("--reference", default=None, type=click.Path(exists=True),
              help="Reference image for visual guidance")
@click.option("--style", "style", default="artistic",
              type=click.Choice(["artistic", "precise", "sketch", "minimal"]),
              help="Drawing style preset")
@click.pass_context
def generate(ctx, prompt, provider, model, output, visualize, simulate, reference, style):
    """Generate GCode from a text prompt via LLM."""
    config = ctx.obj["config"]

    if provider:
        config.llm.default_provider = provider
    if model:
        setattr(config.llm, f"{config.llm.default_provider}_model", model)
    if reference:
        config.vision.enabled = True
        config.vision.reference_image = reference

    logger.cli_header("3.0.0")

    async def _run():
        from .workflow import BatchGCodeWorkflow
        from .llm import get_llm_provider

        llm = get_llm_provider(config.llm)
        wf = BatchGCodeWorkflow(llm=llm, config=config, style=style)
        result = await wf.run(prompt=prompt)

        gcode_text = result["gcode"]

        # Default output to output/<slug>_<timestamp>.gcode
        if not output:
            import re
            slug = re.sub(r"[^a-z0-9]+", "_", prompt.lower())[:40].strip("_")
            ts = time.strftime("%Y%m%d_%H%M%S")
            out_dir = Path(config.workflow.output_directory)
            out_dir.mkdir(parents=True, exist_ok=True)
            output = str(out_dir / f"{slug}_{ts}.gcode")

        Path(output).write_text(gcode_text)
        logger.step_success(f"GCode saved to {output}")

        if visualize:
            try:
                from .visualizer import GCodeVisualizer
                from .models import GCodeProgram
                program = GCodeProgram(**result["program"])
                viz = GCodeVisualizer(config)
                preview_path = output.replace(".gcode", ".png")
                viz.preview(program, preview_path)
                logger.step_success(f"Preview saved to {preview_path}")
            except ImportError:
                logger.step_warning("matplotlib not available for visualization")

    asyncio.run(_run())


@cli.command()
@click.argument("filepath")
@click.option("--port", default=None, help="Serial port")
@click.option("--baud", default=115200, help="Baud rate")
@click.option("--simulate", is_flag=True, help="Simulation mode")
@click.option("--brush", is_flag=True, help="Enable brush/ink mode")
@click.option("--preview-only", is_flag=True, help="Preview without plotting")
@click.option("--output", "-o", default=None, help="Preview output path")
@click.pass_context
def plot(ctx, filepath, port, baud, simulate, brush, preview_only, output):
    """Plot a GCode file to the plotter."""
    config = ctx.obj["config"]

    if port:
        config.serial.port = port
    if baud:
        config.serial.baud_rate = baud
    if brush:
        config.brush.enabled = True

    logger.cli_header("3.0.0")

    async def _run():
        from .pipeline import FilePipeline
        from .plotter import SimulatedPlotter, SerialPlotter

        pipeline = FilePipeline(config)

        plotter = None
        if not preview_only:
            if simulate:
                plotter = SimulatedPlotter()
            else:
                plotter = SerialPlotter(
                    port=config.serial.port,
                    baud_rate=config.serial.baud_rate,
                    timeout=config.serial.timeout,
                )

        processed, success, errors = await pipeline.process_file(
            filepath, plotter=plotter, preview_only=preview_only, output_path=output,
        )
        if not preview_only:
            logger.execution_summary(success + errors, success, errors, 0.0)

    asyncio.run(_run())


@cli.command()
@click.argument("filepath")
@click.option("--output", "-o", default=None, help="Output PNG path")
@click.option("--stats", is_flag=True, help="Show statistics")
@click.pass_context
def preview(ctx, filepath, output, stats):
    """Preview/visualize a GCode file."""
    config = ctx.obj["config"]

    from .pipeline import FilePipeline
    from .visualizer import GCodeVisualizer

    pipeline = FilePipeline(config)
    program = pipeline.load_gcode_file(filepath)

    viz = GCodeVisualizer(config)
    if output:
        save_to = output
    else:
        out_dir = Path(config.workflow.output_directory)
        out_dir.mkdir(parents=True, exist_ok=True)
        save_to = str(out_dir / f"preview_{Path(filepath).stem}.png")
    viz.preview(program, save_to)
    logger.step_success(f"Preview saved to {save_to}")

    if stats:
        s = viz.get_stats(program)
        table = Table(title="GCode Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        for k, v in s.items():
            if k != "bounds":
                table.add_row(k.replace("_", " ").title(), str(v))
        if "bounds" in s:
            b = s["bounds"]
            table.add_row("Bounds", f"X[{b[0]:.1f}–{b[1]:.1f}] Y[{b[2]:.1f}–{b[3]:.1f}]")
        console.print(table)


@cli.group(name="config")
def config_group():
    """Configuration management."""
    pass


@config_group.command(name="show")
@click.pass_context
def config_show(ctx):
    """Display current configuration."""
    config = ctx.obj["config"]
    logger.config_table(config)


@cli.group()
def plotter():
    """Plotter management."""
    pass


@plotter.command(name="connect")
@click.option("--port", default=None, help="Serial port")
@click.option("--simulate", is_flag=True, help="Use simulated plotter")
@click.pass_context
def plotter_connect(ctx, port, simulate):
    """Test plotter connection."""
    config = ctx.obj["config"]

    async def _run():
        from .plotter import SimulatedPlotter, SerialPlotter

        if simulate:
            p = SimulatedPlotter()
        else:
            p = SerialPlotter(
                port=port or config.serial.port,
                baud_rate=config.serial.baud_rate,
            )
        async with p:
            logger.step_success(f"Connected to {p.port}")
            await p.send_command("G0 X0 Y0")
            logger.step_success("Test command sent")

    asyncio.run(_run())


@plotter.command(name="list-ports")
def plotter_list_ports():
    """List available serial ports."""
    try:
        from serial.tools.list_ports import comports
        ports = list(comports())
        if not ports:
            console.print("[yellow]No serial ports found[/yellow]")
            return
        table = Table(title="Available Serial Ports")
        table.add_column("Port", style="cyan")
        table.add_column("Description", style="green")
        for p in ports:
            table.add_row(p.device, p.description)
        console.print(table)
    except ImportError:
        console.print("[red]pyserial not installed[/red]")


@cli.command()
@click.option("--provider", default=None, help="LLM provider")
@click.option("--model", default=None, help="Model name")
@click.pass_context
def interactive(ctx, provider, model):
    """Interactive REPL mode."""
    config = ctx.obj["config"]
    if provider:
        config.llm.default_provider = provider
    if model:
        setattr(config.llm, f"{config.llm.default_provider}_model", model)

    logger.cli_header("3.0.0")
    console.print("[dim]Type a drawing prompt, or 'quit' to exit.[/dim]")

    async def _run():
        from .workflow import BatchGCodeWorkflow
        from .llm import get_llm_provider

        llm = get_llm_provider(config.llm)
        wf = BatchGCodeWorkflow(llm=llm, config=config)

        while True:
            try:
                prompt = Prompt.ask("\n[bold cyan]prompt[/bold cyan]")
            except (EOFError, KeyboardInterrupt):
                break
            if prompt.lower() in ("quit", "exit", "q"):
                break
            if not prompt.strip():
                continue

            try:
                result = await wf.run(prompt=prompt)
                gcode = result["gcode"]
                console.print(Panel(gcode, title="Generated GCode", border_style="green"))

                if Confirm.ask("Save to file?", default=False):
                    import re as _re
                    _slug = _re.sub(r"[^a-z0-9]+", "_", prompt.lower())[:40].strip("_")
                    _ts = time.strftime("%Y%m%d_%H%M%S")
                    _out_dir = Path(config.workflow.output_directory)
                    _out_dir.mkdir(parents=True, exist_ok=True)
                    _default = str(_out_dir / f"{_slug}_{_ts}.gcode")
                    filename = Prompt.ask("Filename", default=_default)
                    Path(filename).parent.mkdir(parents=True, exist_ok=True)
                    Path(filename).write_text(gcode)
                    logger.step_success(f"Saved to {filename}")
            except Exception as e:
                logger.step_error(f"Generation failed: {e}")

    asyncio.run(_run())


def main():
    """Entry point for promptplot CLI."""
    cli(obj={})


if __name__ == "__main__":
    main()
