"""import command — load an SVG/DXF, split by color/layer, draw as color layers."""

import asyncio
from pathlib import Path

import click

from ._group import cli, console, _get_config


@cli.command(name="import")
@click.argument("filepath", type=click.Path(exists=True))
@click.option(
    "--paper",
    "paper_size",
    default="a4",
    type=click.Choice(["a3", "a4", "a5", "a6"], case_sensitive=False),
    help="Paper/canvas size",
)
@click.option(
    "--orientation",
    default="portrait",
    type=click.Choice(["portrait", "landscape"]),
)
@click.option(
    "--group-by",
    default="auto",
    type=click.Choice(["auto", "color", "layer"]),
    help="Split into color layers by SVG stroke color or DXF layer",
)
@click.option("--no-fit", is_flag=True, help="Do not scale the drawing to fit the paper")
@click.option("--simulate", is_flag=True, help="Simulated plotter (no hardware)")
@click.option("--preview", "save_preview", is_flag=True, help="Save a color-coded preview PNG")
@click.option("--save", "-o", default=None, help="Save GCode to this path")
@click.option("--port", default=None, help="Serial port")
@click.option("--baud", default=115200, help="Baud rate")
@click.pass_context
def import_cmd(
    ctx,
    filepath,
    paper_size,
    orientation,
    group_by,
    no_fit,
    simulate,
    save_preview,
    save,
    port,
    baud,
):
    """Import an SVG or DXF file and draw it, split into color/layer passes.

    Examples:

        promptplot import logo.svg --simulate --preview

        promptplot import part.dxf --group-by layer --paper a3 --preview
    """
    from ..config import PaperConfig
    from ..importers import import_file
    from ..orchestrate import merge_chunks

    config = _get_config()
    config.paper = PaperConfig.from_size(paper_size, orientation=orientation)
    if port:
        config.serial.port = port
    if baud:
        config.serial.baud_rate = baud

    commands, palette, result = import_file(filepath, config, group_by=group_by, fit=not no_fit)
    if not commands:
        console.print(f"[red]No drawable paths found in {filepath}[/red]")
        raise SystemExit(1)

    config.color.enabled = len(palette) > 1
    if config.color.enabled:
        config.color.palette = palette
        config.color.pause_for_swap = not simulate

    program = merge_chunks([commands], config)
    program.metadata.update({"imported_from": filepath, "palette": palette})

    console.print(
        f"[bold blue]imported[/bold blue] → {Path(filepath).name}  ({len(result.paths)} paths)"
    )
    console.print(f"[bold blue]layers[/bold blue]   → {len(palette)}  {palette}")
    console.print(f"[bold blue]commands[/bold blue] → {len(program.commands)}")

    if save:
        Path(save).parent.mkdir(parents=True, exist_ok=True)
        Path(save).write_text(program.to_gcode())
        console.print(f"[green]GCode saved to {save}[/green]")

    if save_preview:
        try:
            from ..visualizer import GCodeVisualizer

            preview_path = save or Path(filepath).stem
            preview_path = str(preview_path).replace(".gcode", "") + ".png"
            GCodeVisualizer(config).preview(program, preview_path)
            console.print(f"[green]Preview saved to {preview_path}[/green]")
        except ImportError:
            console.print("[yellow]matplotlib not available — skipping preview[/yellow]")

    if simulate or port:
        from ..plotter import SimulatedPlotter, SerialPlotter
        from ..orchestrate import stream_pen_layers

        async def _run():
            if simulate:
                plotter = SimulatedPlotter()
                await plotter.connect()
            else:
                plotter = SerialPlotter(port=config.serial.port, baud_rate=config.serial.baud_rate)
                if not await plotter.connect():
                    console.print(f"[red]Could not connect to {config.serial.port}[/red]")
                    raise SystemExit(1)
            ok, err = await stream_pen_layers(program, plotter, config, verbose=False)
            if not simulate:
                await plotter.disconnect()
            console.print(f"[bold]streamed[/bold] → {ok} ok, {err} errors")

        asyncio.run(_run())
