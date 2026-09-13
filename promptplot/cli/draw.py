"""draw command — batch / live / orchestrate LLM drawing.

Split out of the former monolithic cli.py during the v3.1 reorg.
"""

import asyncio
import time
from pathlib import Path

import click

from ._group import cli, console, _print_score


# ===== sliced body (draw) =====
@cli.command()
@click.argument("prompt")
@click.option("--port", default=None, help="Serial port (auto-detect if omitted)")
@click.option("--baud", default=115200, help="Baud rate")
@click.option("--simulate", is_flag=True, help="Simulated plotter (no hardware)")
@click.option(
    "--paper", "paper_size", default=None,
    type=click.Choice(["a3", "a4", "a5", "a6"], case_sensitive=False),
    help="Paper/canvas size (overrides config)",
)
@click.option(
    "--orientation", default="portrait",
    type=click.Choice(["portrait", "landscape"]),
    help="Paper orientation (used with --paper)",
)
@click.option("--provider", default=None, help="LLM provider")
@click.option("--model", default=None, help="Model name")
@click.option(
    "--style", default="artistic", type=click.Choice(["artistic", "precise", "sketch", "minimal"])
)
@click.option("--multipass", is_flag=True, help="Multi-pass generation")
@click.option(
    "--live",
    is_flag=True,
    help="Real-time: LLM generates each command and sends it to the plotter immediately",
)
@click.option("--max-steps", default=80, help="Max LLM steps in --live mode")
@click.option("--save", "-o", default=None, help="Also save GCode to file")
@click.option("--preview", "save_preview", is_flag=True, help="Save preview PNG")
@click.option(
    "--min-grade",
    default="D",
    type=click.Choice(["A", "B", "C", "D", "F"]),
    help="Minimum quality grade to proceed to plotter (batch mode only)",
)
@click.option("--resume", is_flag=True, help="Resume from last checkpoint")
@click.option("--plan", "planning", is_flag=True, help="Enable LLM composition planning phase")
@click.option(
    "--orchestrate", is_flag=True, help="Use SupervisorWorkerWorkflow (fan-out per region)"
)
@click.option(
    "--regions", "regions_count", default=4, type=int, help="Number of regions for --orchestrate"
)
@click.option(
    "--colors", default=1, type=int,
    help="Number of pen colors — the LLM assigns colors and the plotter pauses for swaps",
)
@click.pass_context
def draw(
    ctx,
    prompt,
    port,
    baud,
    simulate,
    paper_size,
    orientation,
    provider,
    model,
    style,
    multipass,
    live,
    max_steps,
    save,
    save_preview,
    min_grade,
    resume,
    planning,
    orchestrate,
    regions_count,
    colors,
):
    """Generate and draw in one shot: prompt → LLM → quality check → plotter.

    Two modes:

      Batch (default): LLM generates full drawing → quality check → stream to plotter.

      Live (--live): LLM generates one command at a time → validate → send to plotter
      immediately. The pen moves while the LLM is still thinking. No global optimization
      but maximum real-time feel.

    Examples:

        promptplot draw "a spiral" --simulate

        promptplot draw "a cat" --port /dev/cu.usbserial-1420

        promptplot draw "a cat" --live --simulate

        promptplot draw "detailed cityscape" --multipass --min-grade B
    """
    config = ctx.obj["config"]

    if paper_size:
        from ..config import PaperConfig
        config.paper = PaperConfig.from_size(paper_size, orientation=orientation)
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
    if planning:
        config.workflow.planning_enabled = True
    if colors > 1:
        config.color.enabled = True
        base = ["black", "red", "blue", "green", "orange", "purple", "brown", "magenta"]
        config.color.palette = base[:colors] if colors <= len(base) else [f"pen{i}" for i in range(colors)]
        config.color.pause_for_swap = not simulate

    grade_order = {"A": 4, "B": 3, "C": 2, "D": 1, "F": 0}

    async def _run_live():
        """Real-time mode: LLM → validate → plotter, one command at a time."""
        from ..workflow import LiveDrawWorkflow
        from ..llm import get_llm_provider
        from ..models import GCodeProgram
        from ..scoring import score_gcode
        from ..plotter import SimulatedPlotter, SerialPlotter

        console.print()
        console.print(f"[bold blue]prompt[/bold blue] [dim]→[/dim] {prompt}")
        console.print(f"[bold magenta]mode[/bold magenta]   [dim]→[/dim] live (real-time)")
        console.print()

        # Connect plotter
        if simulate:
            plotter_inst = SimulatedPlotter(command_delay=0.02)
            console.print("  [yellow]simulated[/yellow] plotter")
        else:
            plotter_inst = SerialPlotter(
                port=config.serial.port,
                baud_rate=config.serial.baud_rate,
                timeout=config.serial.timeout,
            )
            console.print(f"  [cyan]connecting[/cyan] {config.serial.port}")

        llm = get_llm_provider(config.llm)

        from rich.live import Live
        from rich.table import Table as RichTable

        # Live display state
        step_log = []
        sent_total = [0]
        err_total = [0]

        def _build_display():
            tbl = RichTable(
                show_header=True,
                header_style="bold cyan",
                title=f"Live Drawing — {sent_total[0]} sent, {err_total[0]} errors",
                min_width=60,
            )
            tbl.add_column("#", width=4, justify="right")
            tbl.add_column("GCode", min_width=30)
            tbl.add_column("Status", width=10)
            # Show last 15 commands
            for entry in step_log[-15:]:
                num, gcode, status, warns = entry
                if status == "ok":
                    status_str = "[green]ok[/green]"
                elif status == "DONE":
                    status_str = "[bold green]DONE[/bold green]"
                elif status == "skip":
                    status_str = "[yellow]skip[/yellow]"
                else:
                    status_str = "[red]err[/red]"
                extra = f" [dim]{'; '.join(warns)}[/dim]" if warns else ""
                tbl.add_row(str(num), gcode + extra, status_str)
            return tbl

        async with plotter_inst:
            console.print(f"  [green]connected[/green]  {plotter_inst.port}")
            console.print()

            with Live(_build_display(), console=console, refresh_per_second=4) as live_display:

                async def on_step(step_num, max_s, gcode, ok, warnings):
                    if gcode == "COMPLETE":
                        step_log.append((step_num, "COMPLETE", "DONE", []))
                    elif ok:
                        sent_total[0] += 1
                        step_log.append((step_num, gcode, "ok", warnings))
                    else:
                        err_total[0] += 1
                        step_log.append((step_num, gcode, "err", warnings))
                    live_display.update(_build_display())

                wf = LiveDrawWorkflow(
                    llm=llm,
                    config=config,
                    plotter=plotter_inst,
                    max_steps=max_steps,
                    on_step=on_step,
                )
                t0 = time.time()
                result = await wf.run(prompt=prompt)
                elapsed = time.time() - t0

        # Post-run summary
        console.print()
        n_cmds = len(result["commands"])
        console.print(
            f"  [green]done[/green]  {result['sent_count']} sent, "
            f"{result['error_count']} errors, {result['skipped_count']} skipped  "
            f"[dim]({elapsed:.1f}s)[/dim]"
        )

        # Score the final result
        program = GCodeProgram(**result["program"])
        if len([c for c in program.commands if c.command == "G1"]) > 0:
            report = score_gcode(program, config.paper)
            grade_color = {
                "A": "bold green",
                "B": "green",
                "C": "yellow",
                "D": "red",
                "F": "bold red",
            }.get(report.grade, "white")
            console.print(
                f"  [cyan]quality[/cyan] grade [{grade_color}]{report.grade}[/{grade_color}]  "
                f"utilization {report.canvas_utilization:.0%}  "
                f"strokes {report.stroke_count}"
            )

        # Save
        if save:
            Path(save).parent.mkdir(parents=True, exist_ok=True)
            Path(save).write_text(result["gcode"])
            console.print(f"  [green]saved[/green]  {save}")

        if save_preview:
            try:
                from ..visualizer import GCodeVisualizer

                viz = GCodeVisualizer(config)
                preview_path = (save or "drawing").replace(".gcode", "") + ".png"
                viz.preview(program, preview_path)
                console.print(f"  [green]preview[/green] {preview_path}")
            except ImportError:
                pass

    async def _run():
        from ..workflow import BatchGCodeWorkflow, SupervisorWorkerWorkflow
        from ..llm import get_llm_provider
        from ..models import GCodeProgram
        from ..scoring import score_gcode
        from ..plotter import SimulatedPlotter, SerialPlotter

        # --- Phase 1: Generate ---
        console.print()
        console.print(f"[bold blue]prompt[/bold blue] [dim]→[/dim] {prompt}")
        if orchestrate:
            console.print(
                f"[bold magenta]mode[/bold magenta]   [dim]→[/dim] orchestrate ({regions_count} regions)"
            )
        console.print()

        t0 = time.time()
        llm = get_llm_provider(config.llm)
        if orchestrate:
            strategy = "grid_3x3" if regions_count >= 9 else "grid_2x2"
            wf = SupervisorWorkerWorkflow(
                llm=llm,
                config=config,
                regions=regions_count,
                strategy=strategy,
                style=style,
            )
        else:
            wf = BatchGCodeWorkflow(llm=llm, config=config, style=style)

        with console.status("[bold cyan]Generating GCode from LLM...", spinner="dots"):
            result = await wf.run(prompt=prompt)

        program = GCodeProgram(**result["program"])
        gen_time = time.time() - t0
        console.print(
            f"  [green]generated[/green] {len(program.commands)} commands " f"in {gen_time:.1f}s"
        )

        # --- Phase 2: Score ---
        report = score_gcode(program, config.paper)
        grade_color = {
            "A": "bold green",
            "B": "green",
            "C": "yellow",
            "D": "red",
            "F": "bold red",
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
            console.print(
                "  [dim]Tip: lower --min-grade or try --multipass for richer output.[/dim]"
            )
            # Still save if requested
            if save:
                Path(save).write_text(result["gcode"])
                console.print(f"  [green]saved[/green]     {save}")
            return

        # --- Phase 4: Preview (optional) ---
        if save_preview:
            try:
                from ..visualizer import GCodeVisualizer

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
            console.print(
                f"  [cyan]connecting[/cyan] {config.serial.port} @ {config.serial.baud_rate}"
            )

        from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn

        async with plotter:
            console.print(f"  [green]connected[/green]  {plotter.port}")
            console.print()

            errors_list = []

            if config.color.enabled:
                # Multi-color: draw each pen layer, park + pause for a swap between them.
                from ..orchestrate import stream_pen_layers, split_color_layers

                n_layers = len({c for c, _ in split_color_layers(program)})
                console.print(f"  [magenta]color layers[/magenta] {n_layers} "
                              f"({', '.join(config.color.palette)})")
                success, err_count = await stream_pen_layers(
                    program, plotter, config, verbose=False
                )
            else:
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
                        program,
                        on_command=on_command,
                    )

            console.print()
            console.print(f"  [green]done[/green]      " f"{success} ok, {err_count} errors")
            if errors_list:
                for idx, gcode in errors_list[:5]:
                    console.print(f"  [red]error[/red]     cmd {idx}: {gcode}")

            # --- Phase 7: Final quality summary ---
            console.print()
            _print_score(report)

    if live:
        asyncio.run(_run_live())
    else:
        asyncio.run(_run())
