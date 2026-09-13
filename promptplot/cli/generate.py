"""generate / plot / score / preview commands.

Split out of the former monolithic cli.py during the v3.1 reorg.
"""

import asyncio
import time
from pathlib import Path

import click
from rich.table import Table

from ._group import cli, console, logger, _print_score


# ===== sliced body (generate, plot, score, preview) =====
@cli.command()
@click.argument("prompt")
@click.option("--provider", default=None, help="LLM provider (ollama|openai|azure|gemini)")
@click.option("--model", default=None, help="Model name")
@click.option("--output", "-o", default=None, help="Output GCode file")
@click.option("--visualize", is_flag=True, help="Show preview after generation")
@click.option("--simulate", is_flag=True, help="Use simulated plotter")
@click.option(
    "--reference",
    default=None,
    type=click.Path(exists=True),
    help="Reference image for visual guidance",
)
@click.option(
    "--style",
    "style",
    default="artistic",
    type=click.Choice(["artistic", "precise", "sketch", "minimal"]),
    help="Drawing style preset",
)
@click.option("--score", "show_score", is_flag=True, help="Show quality score")
@click.option("--multipass", is_flag=True, help="Enable multi-pass generation")
@click.option(
    "--style-from",
    "style_from",
    default=None,
    type=click.Path(exists=True),
    help="Reference GCode file for style transfer",
)
@click.pass_context
def generate(
    ctx,
    prompt,
    provider,
    model,
    output,
    visualize,
    simulate,
    reference,
    style,
    show_score,
    multipass,
    style_from,
):
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
        from ..workflow import BatchGCodeWorkflow
        from ..llm import get_llm_provider

        # Style transfer from reference GCode
        _style_profile = None
        if style_from:
            from ..pipeline import FilePipeline
            from ..scoring import extract_style_profile

            fp = FilePipeline(config)
            ref_program = fp.load_gcode_file(style_from)
            _style_profile = extract_style_profile(ref_program, config.paper)

        llm = get_llm_provider(config.llm)
        wf = BatchGCodeWorkflow(
            llm=llm,
            config=config,
            style=style,
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
            from ..models import GCodeProgram

            program = GCodeProgram(**result["program"])

            if show_score:
                from ..scoring import score_gcode

                report = score_gcode(program, config.paper)
                _print_score(report)

            if visualize:
                try:
                    from ..visualizer import GCodeVisualizer

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
        from ..pipeline import FilePipeline
        from ..plotter import SimulatedPlotter, SerialPlotter

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
            filepath,
            plotter=plotter,
            preview_only=preview_only,
            output_path=output,
        )
        if not preview_only:
            logger.execution_summary(success + errors, success, errors, 0.0)

    asyncio.run(_run())


@cli.command()
@click.argument("filepath")
@click.pass_context
def score(ctx, filepath):
    """Score a GCode file for quality metrics."""
    config = ctx.obj["config"]
    from ..pipeline import FilePipeline
    from ..scoring import score_gcode

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

    from ..pipeline import FilePipeline
    from ..visualizer import GCodeVisualizer

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
            table.add_row(
                "Bounds",
                f"X[{b.get('min_x', 0):.1f}–{b.get('max_x', 0):.1f}] Y[{b.get('min_y', 0):.1f}–{b.get('max_y', 0):.1f}]",
            )
        console.print(table)

    if show_score:
        from ..scoring import score_gcode

        report = score_gcode(program, config.paper)
        _print_score(report)
