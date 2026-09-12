"""art command — seeded, reproducible generative drawings (no LLM).

Same seed + params + version → identical GCode. Use ``--seed now`` (default) for
a timestamp seed that is printed and embedded in the filename so it can be
reproduced later with ``--seed <that number>``.
"""

import asyncio
import time
from pathlib import Path

import click

from ._group import cli, console, _get_config


def _parse_params(pairs):
    """Turn ('cell=10', 'wobble=0.2') into {'cell': 10, 'wobble': 0.2}."""
    out = {}
    for pair in pairs:
        if "=" not in pair:
            raise click.BadParameter(f"--param must be key=value, got {pair!r}")
        k, v = pair.split("=", 1)
        k, v = k.strip(), v.strip()
        try:
            out[k] = int(v)
        except ValueError:
            try:
                out[k] = float(v)
            except ValueError:
                out[k] = v
    return out


@cli.command()
@click.argument("generator", required=False)
@click.option(
    "--list", "list_only", is_flag=True, help="List available generators and their params"
)
@click.option("--seed", default="now", help="Seed number, or 'now' for a timestamp seed")
@click.option("--colors", default=1, type=int, help="Number of pen colors (color layers)")
@click.option(
    "--palette", default=None, help="Comma-separated pen colors, e.g. black,red,blue,yellow"
)
@click.option(
    "--paper",
    "paper_size",
    default="a5",
    type=click.Choice(["a3", "a4", "a5", "a6"], case_sensitive=False),
    help="Paper/canvas size",
)
@click.option(
    "--orientation",
    default="portrait",
    type=click.Choice(["portrait", "landscape"]),
)
@click.option("--margin", default=10.0, type=float, help="Margin from the paper corner (mm)")
@click.option("--param", "params", multiple=True, help="Generator param key=value (repeatable)")
@click.option(
    "--anaglyph",
    is_flag=True,
    help="Duplicate the drawing into offset red/cyan pen layers (3D effect)",
)
@click.option(
    "--anaglyph-offset", default=1.6, type=float, help="Layer offset in mm (with --anaglyph)"
)
@click.option(
    "--glitch",
    "glitch_bands",
    default=0,
    type=int,
    help="Seeded glitch bands that tear sideways (with --anaglyph)",
)
@click.option(
    "--max-ink",
    "max_ink",
    default=0,
    type=int,
    help="Cap pen passes per ink cell (paper protection post-process; 0 = off)",
)
@click.option(
    "--max-ink-cell",
    "max_ink_cell",
    default=1.2,
    type=float,
    help="Ink-cell size in mm for --max-ink (bigger = more aggressive thinning)",
)
@click.option("--simulate", is_flag=True, help="Simulated plotter (no hardware)")
@click.option("--preview", "save_preview", is_flag=True, help="Save a color-coded preview PNG")
@click.option("--save", "-o", default=None, help="Save GCode to this path")
@click.option("--port", default=None, help="Serial port")
@click.option("--baud", default=115200, help="Baud rate")
@click.pass_context
def art(
    ctx,
    generator,
    list_only,
    seed,
    colors,
    palette,
    paper_size,
    orientation,
    margin,
    params,
    anaglyph,
    anaglyph_offset,
    glitch_bands,
    max_ink,
    max_ink_cell,
    simulate,
    save_preview,
    save,
    port,
    baud,
):
    """Generate a seeded generative drawing.

    Examples:

        promptplot art --list

        promptplot art tiled_field --seed 12345 --colors 3 --simulate --preview

        promptplot art ripple_field --seed now --paper a4 --preview
    """
    from ..generative import list_generators, run_generator, format_generators_for_help
    from ..config import PaperConfig

    if list_only or not generator:
        console.print("[bold]Available generators:[/bold]")
        console.print(format_generators_for_help())
        return

    if generator not in list_generators():
        console.print(f"[red]Unknown generator:[/red] {generator}")
        console.print(f"Available: {', '.join(list_generators())}")
        raise SystemExit(1)

    # Resolve seed: 'now' -> timestamp (printed + embedded for reproducibility)
    if str(seed).lower() in ("now", "time", "auto"):
        seed_val = int(time.time())
    else:
        seed_val = int(seed)

    config = _get_config()
    config.paper = PaperConfig.from_size(paper_size, orientation=orientation, margin=margin)
    if port:
        config.serial.port = port
    if baud:
        config.serial.baud_rate = baud
    if palette:
        names = [c.strip() for c in palette.split(",") if c.strip()]
        colors = max(colors, len(names))
    else:
        names = None
    if colors > 1:
        config.color.enabled = True
        base = ["black", "red", "blue", "green", "orange", "purple", "brown", "magenta"]
        if names:
            config.color.palette = names[:colors]
        else:
            config.color.palette = (
                base[:colors] if colors <= len(base) else [f"pen{i}" for i in range(colors)]
            )
        config.color.pause_for_swap = not simulate

    bounds = config.paper.get_drawable_area()
    param_dict = _parse_params(params)

    console.print(f"[bold blue]generator[/bold blue] → {generator}")
    console.print(
        f"[bold blue]seed[/bold blue]      → {seed_val}   [dim](reproduce with --seed {seed_val})[/dim]"
    )
    console.print(
        f"[bold blue]paper[/bold blue]     → {paper_size} {orientation}  bounds={tuple(round(b,1) for b in bounds)}"
    )
    if param_dict:
        console.print(f"[bold blue]params[/bold blue]    → {param_dict}")

    from ..orchestrate import merge_chunks

    raw = run_generator(generator, bounds, seed_val, colors=colors, params=param_dict)
    if not raw:
        console.print("[red]Generator produced no commands.[/red]")
        raise SystemExit(1)

    if anaglyph:
        from ..generative import SeededRNG, anaglyph_layers

        layer_count = colors if colors > 1 else 4
        raw = anaglyph_layers(
            raw,
            SeededRNG(seed_val + 7919),  # derived, still fully seed-reproducible
            offset=(anaglyph_offset, anaglyph_offset * 0.6),
            layers=layer_count,
            glitch_bands=glitch_bands,
            bounds=bounds,
        )
        colors = layer_count
        config.color.enabled = True
        if not names:
            base_glitch = ["cyan", "red", "yellow", "black"]
            config.color.palette = (
                base_glitch[:layer_count]
                if layer_count <= 4
                else base_glitch + [f"pen{i}" for i in range(layer_count - 4)]
            )
        config.color.pause_for_swap = not simulate
        console.print(
            f"[bold blue]anaglyph[/bold blue]  → {layer_count} layers, offset {anaglyph_offset}mm"
            + (f", {glitch_bands} glitch bands" if glitch_bands else "")
        )

    if max_ink > 0:
        from ..generative import limit_ink_density

        before = len(raw)
        raw = limit_ink_density(raw, max_passes=max_ink, cell=max_ink_cell)
        console.print(
            f"[bold blue]max-ink[/bold blue]   → ≤{max_ink} passes/mm² ({before}→{len(raw)} cmds)"
        )

    program = merge_chunks([raw], config)
    program.metadata.update(
        {"generator": generator, "seed": seed_val, "params": param_dict, "version": "3.1"}
    )
    console.print(f"[bold blue]commands[/bold blue]  → {len(program.commands)}")

    # Determine output paths (embed the seed for reproducibility)
    out_dir = Path(config.workflow.output_directory)
    stem = f"{generator}_seed{seed_val}"
    if save:
        gcode_path = save
    else:
        out_dir.mkdir(parents=True, exist_ok=True)
        gcode_path = str(out_dir / f"{stem}.gcode")
    Path(gcode_path).parent.mkdir(parents=True, exist_ok=True)
    Path(gcode_path).write_text(program.to_gcode())
    console.print(f"[green]GCode saved to {gcode_path}[/green]")

    if save_preview:
        try:
            from ..visualizer import GCodeVisualizer

            preview_path = gcode_path.replace(".gcode", "") + ".png"
            GCodeVisualizer(config).preview(program, preview_path)
            console.print(f"[green]Preview saved to {preview_path}[/green]")
        except ImportError:
            console.print("[yellow]matplotlib not available — skipping preview[/yellow]")

    # Stream if a plotter target is implied
    if simulate or port:
        from ..plotter import SimulatedPlotter, SerialPlotter
        from ..orchestrate import stream_pen_layers, trace_frame

        async def _run():
            if simulate:
                plotter = SimulatedPlotter()
                await plotter.connect()
            else:
                # heartbeat off: single-reader discipline during long streams
                plotter = SerialPlotter(
                    port=config.serial.port,
                    baud_rate=config.serial.baud_rate,
                    enable_heartbeat=False,
                )
                if not await plotter.connect():
                    console.print(f"[red]Could not connect to {config.serial.port}[/red]")
                    raise SystemExit(1)
                # Mandatory guardrail: pen-up tour of the drawable limits first.
                console.print(
                    "[cyan]tracing limits (pen up) — check the drawing lands on the paper[/cyan]"
                )
                await trace_frame(plotter, config.paper, laps=1)
            ok, err = await stream_pen_layers(program, plotter, config, verbose=False)
            if not simulate:
                await plotter.send_command("M5")
                await plotter.send_command("G0 X0 Y0")
                await plotter.disconnect()
            console.print(f"[bold]streamed[/bold] → {ok} ok, {err} errors")

        asyncio.run(_run())
