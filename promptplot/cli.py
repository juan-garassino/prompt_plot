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
@click.option("--score", "show_score", is_flag=True, help="Show quality score")
@click.option("--multipass", is_flag=True, help="Enable multi-pass generation")
@click.option("--style-from", "style_from", default=None, type=click.Path(exists=True),
              help="Reference GCode file for style transfer")
@click.pass_context
def generate(ctx, prompt, provider, model, output, visualize, simulate, reference, style,
             show_score, multipass, style_from):
    """Generate GCode from a text prompt via LLM."""
    config = ctx.obj["config"]

    if provider:
        config.llm.default_provider = provider
    if model:
        setattr(config.llm, f"{config.llm.default_provider}_model", model)
    if reference:
        config.vision.enabled = True
        config.vision.reference_image = reference
    if multipass:
        config.workflow.multipass.enabled = True

    logger.cli_header("3.0.0")

    async def _run():
        from .workflow import BatchGCodeWorkflow
        from .llm import get_llm_provider

        # Style transfer from reference GCode
        _style_profile = None
        if style_from:
            from .pipeline import FilePipeline
            from .scoring import extract_style_profile
            fp = FilePipeline(config)
            ref_program = fp.load_gcode_file(style_from)
            _style_profile = extract_style_profile(ref_program, config.paper)

        llm = get_llm_provider(config.llm)
        wf = BatchGCodeWorkflow(
            llm=llm, config=config, style=style,
            style_profile=_style_profile,
        )
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

        if visualize or show_score:
            from .models import GCodeProgram
            program = GCodeProgram(**result["program"])

            if show_score:
                from .scoring import score_gcode
                report = score_gcode(program, config.paper)
                _print_score(report)

            if visualize:
                try:
                    from .visualizer import GCodeVisualizer
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


def _print_score(report):
    """Print a QualityReport as a formatted table."""
    table = Table(title="Quality Score")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    d = report.to_dict()
    for k, v in d.items():
        label = k.replace("_", " ").title()
        if k == "grade":
            color = {"A": "bold green", "B": "green", "C": "yellow", "D": "red", "F": "bold red"}.get(v, "white")
            table.add_row(label, f"[{color}]{v}[/{color}]")
        elif isinstance(v, float):
            table.add_row(label, f"{v:.3f}")
        else:
            table.add_row(label, str(v))
    console.print(table)


@cli.command()
@click.argument("filepath")
@click.pass_context
def score(ctx, filepath):
    """Score a GCode file for quality metrics."""
    config = ctx.obj["config"]
    from .pipeline import FilePipeline
    from .scoring import score_gcode
    pipeline = FilePipeline(config)
    program = pipeline.load_gcode_file(filepath)
    report = score_gcode(program, config.paper)
    _print_score(report)


@cli.command()
@click.argument("filepath")
@click.option("--output", "-o", default=None, help="Output PNG path")
@click.option("--stats", is_flag=True, help="Show statistics")
@click.option("--score", "show_score", is_flag=True, help="Show quality score")
@click.pass_context
def preview(ctx, filepath, output, stats, show_score):
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
            table.add_row("Bounds", f"X[{b.get('min_x', 0):.1f}–{b.get('max_x', 0):.1f}] Y[{b.get('min_y', 0):.1f}–{b.get('max_y', 0):.1f}]")
        console.print(table)

    if show_score:
        from .scoring import score_gcode
        report = score_gcode(program, config.paper)
        _print_score(report)


@cli.command()
@click.argument("prompt")
@click.option("--port", default=None, help="Serial port (auto-detect if omitted)")
@click.option("--baud", default=115200, help="Baud rate")
@click.option("--simulate", is_flag=True, help="Simulated plotter (no hardware)")
@click.option("--provider", default=None, help="LLM provider")
@click.option("--model", default=None, help="Model name")
@click.option("--style", default="artistic",
              type=click.Choice(["artistic", "precise", "sketch", "minimal"]))
@click.option("--multipass", is_flag=True, help="Multi-pass generation")
@click.option("--save", "-o", default=None, help="Also save GCode to file")
@click.option("--preview", "save_preview", is_flag=True, help="Save preview PNG")
@click.option("--min-grade", default="D",
              type=click.Choice(["A", "B", "C", "D", "F"]),
              help="Minimum quality grade to proceed to plotter")
@click.pass_context
def draw(ctx, prompt, port, baud, simulate, provider, model, style,
         multipass, save, save_preview, min_grade):
    """Generate and draw in one shot: prompt → LLM → quality check → plotter.

    This is the main command for going from a text description to a physical drawing.

    Examples:

        promptplot draw "a spiral" --simulate

        promptplot draw "a cat" --port /dev/cu.usbserial-1420

        promptplot draw "detailed cityscape" --multipass --min-grade B
    """
    config = ctx.obj["config"]

    if provider:
        config.llm.default_provider = provider
    if model:
        setattr(config.llm, f"{config.llm.default_provider}_model", model)
    if port:
        config.serial.port = port
    if baud:
        config.serial.baud_rate = baud
    if multipass:
        config.workflow.multipass.enabled = True

    grade_order = {"A": 4, "B": 3, "C": 2, "D": 1, "F": 0}

    async def _run():
        from .workflow import BatchGCodeWorkflow
        from .llm import get_llm_provider
        from .models import GCodeProgram
        from .scoring import score_gcode
        from .postprocess import run_pipeline
        from .plotter import SimulatedPlotter, SerialPlotter

        # --- Phase 1: Generate ---
        console.print()
        console.print(f"[bold blue]prompt[/bold blue] [dim]→[/dim] {prompt}")
        console.print()

        t0 = time.time()
        llm = get_llm_provider(config.llm)
        wf = BatchGCodeWorkflow(llm=llm, config=config, style=style)

        with console.status("[bold cyan]Generating GCode from LLM...", spinner="dots"):
            result = await wf.run(prompt=prompt)

        program = GCodeProgram(**result["program"])
        gen_time = time.time() - t0
        console.print(
            f"  [green]generated[/green] {len(program.commands)} commands "
            f"in {gen_time:.1f}s"
        )

        # --- Phase 2: Score ---
        report = score_gcode(program, config.paper)
        grade_color = {
            "A": "bold green", "B": "green", "C": "yellow",
            "D": "red", "F": "bold red",
        }.get(report.grade, "white")
        console.print(
            f"  [cyan]quality[/cyan]   "
            f"grade [{grade_color}]{report.grade}[/{grade_color}]  "
            f"utilization {report.canvas_utilization:.0%}  "
            f"strokes {report.stroke_count}  "
            f"draw/travel {report.draw_travel_ratio:.1f}"
        )

        # --- Phase 3: Quality gate ---
        if grade_order.get(report.grade, 0) < grade_order.get(min_grade, 0):
            console.print(
                f"\n  [bold red]Grade {report.grade} below minimum {min_grade} — "
                f"not sending to plotter.[/bold red]"
            )
            console.print("  [dim]Tip: lower --min-grade or try --multipass for richer output.[/dim]")
            # Still save if requested
            if save:
                Path(save).write_text(result["gcode"])
                console.print(f"  [green]saved[/green]     {save}")
            return

        # --- Phase 4: Preview (optional) ---
        if save_preview:
            try:
                from .visualizer import GCodeVisualizer
                viz = GCodeVisualizer(config)
                preview_path = (save or "drawing").replace(".gcode", "") + ".png"
                viz.preview(program, preview_path)
                console.print(f"  [green]preview[/green]   {preview_path}")
            except ImportError:
                pass

        # --- Phase 5: Save GCode (optional) ---
        if save:
            Path(save).parent.mkdir(parents=True, exist_ok=True)
            Path(save).write_text(result["gcode"])
            console.print(f"  [green]saved[/green]     {save}")

        # --- Phase 6: Stream to plotter ---
        console.print()
        if simulate:
            plotter = SimulatedPlotter(command_delay=0.02)
            console.print("  [yellow]simulated[/yellow] plotter (no hardware)")
        else:
            plotter = SerialPlotter(
                port=config.serial.port,
                baud_rate=config.serial.baud_rate,
                timeout=config.serial.timeout,
            )
            console.print(f"  [cyan]connecting[/cyan] {config.serial.port} @ {config.serial.baud_rate}")

        from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn

        async with plotter:
            console.print(f"  [green]connected[/green]  {plotter.port}")
            console.print()

            errors_list = []

            with Progress(
                TextColumn("  [bold]{task.description}"),
                BarColumn(bar_width=40),
                TextColumn("{task.completed}/{task.total}"),
                TimeElapsedColumn(),
                console=console,
            ) as progress:
                task = progress.add_task("drawing", total=len(program.commands))

                async def on_command(idx, total, gcode, ok):
                    progress.update(task, completed=idx + 1)
                    if not ok:
                        errors_list.append((idx, gcode))

                success, err_count = await plotter.stream_program(
                    program, on_command=on_command,
                )

            console.print()
            console.print(
                f"  [green]done[/green]      "
                f"{success} ok, {err_count} errors"
            )
            if errors_list:
                for idx, gcode in errors_list[:5]:
                    console.print(f"  [red]error[/red]     cmd {idx}: {gcode}")

            # --- Phase 7: Final quality summary ---
            console.print()
            _print_score(report)

    asyncio.run(_run())


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
