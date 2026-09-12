"""config / plotter / interactive / ui / library commands.

Split out of the former monolithic cli.py during the v3.1 reorg.
"""

import asyncio
import json
import time
from pathlib import Path

import click
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm

from ._group import cli, console, logger


# ===== sliced body (config, plotter, interactive, ui, library) =====
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
        from ..plotter import SimulatedPlotter, SerialPlotter

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
        from ..workflow import BatchGCodeWorkflow
        from ..llm import get_llm_provider

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


@cli.command()
@click.option("--port", default=None, help="Serial port")
@click.option("--baud", default=115200, help="Baud rate")
@click.option("--simulate", is_flag=True, help="Simulated plotter (no hardware)")
@click.option("--provider", default=None, help="LLM provider")
@click.option("--model", default=None, help="Model name")
@click.option("--live/--batch", default=True, help="Start in live or batch mode")
@click.pass_context
def ui(ctx, port, baud, simulate, provider, model, live):
    """Launch the PromptPlot TUI.

    A split-screen terminal interface: status header, rolling command log,
    quality footer, and a prompt input. Type what you want drawn.

    Examples:

        promptplot ui --simulate

        promptplot ui --port /dev/cu.usbserial-1420

        promptplot ui --simulate --batch
    """
    config = ctx.obj["config"]
    if provider:
        config.llm.default_provider = provider
    if model:
        setattr(config.llm, f"{config.llm.default_provider}_model", model)
    if port:
        config.serial.port = port

    from ..tui import run_tui

    run_tui(config, simulate=simulate, port=port, baud=baud, live_mode=live)


@cli.group()
def library():
    """Curated .gcode library replay."""
    pass


def _library_dir() -> Path:
    return Path.home() / ".promptplot" / "library"


def _library_index() -> dict:
    idx = _library_dir() / "index.json"
    if idx.exists():
        try:
            return json.loads(idx.read_text())
        except Exception:
            return {}
    return {}


@library.command(name="list")
def library_list():
    """List curated .gcode files."""
    d = _library_dir()
    if not d.exists():
        console.print(f"[yellow]No library at {d}[/yellow]")
        return
    index = _library_index()
    table = Table(title="Library")
    table.add_column("Name", style="cyan")
    table.add_column("Path", style="dim")
    table.add_column("Description", style="green")
    for p in sorted(d.glob("*.gcode")):
        meta = index.get(p.stem, {})
        table.add_row(p.stem, str(p), meta.get("description", ""))
    console.print(table)


@library.command(name="play")
@click.argument("name")
@click.option("--port", default=None, help="Serial port")
@click.option("--simulate", is_flag=True, help="Simulated plotter")
@click.pass_context
def library_play(ctx, name, port, simulate):
    """Stream a library .gcode file by name."""
    config = ctx.obj["config"]
    if port:
        config.serial.port = port
    path = _library_dir() / f"{name}.gcode"
    if not path.exists():
        console.print(f"[red]Not found:[/red] {path}")
        return

    async def _run():
        from ..pipeline import FilePipeline
        from ..plotter import SimulatedPlotter, SerialPlotter

        pipeline = FilePipeline(config)
        plotter = (
            SimulatedPlotter()
            if simulate
            else SerialPlotter(
                port=config.serial.port,
                baud_rate=config.serial.baud_rate,
                timeout=config.serial.timeout,
            )
        )
        await pipeline.process_file(str(path), plotter=plotter)

    asyncio.run(_run())
