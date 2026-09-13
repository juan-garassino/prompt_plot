"""`promptplot plate` — compose a lamina: pieces + style + layout → plottable sheet."""

from __future__ import annotations

import asyncio
from pathlib import Path

import click

from ._group import cli, console, _get_config


def _parse_panels(tokens, base_seed):
    """PANEL tokens are `generator[:seed]`; panel i defaults to base_seed+i."""
    from ..lamina import Panel

    panels = []
    for i, tok in enumerate(tokens):
        if ":" in tok:
            name, seed_s = tok.rsplit(":", 1)
            seed = int(seed_s)
        else:
            name, seed = tok, base_seed + i
        panels.append(Panel(generator=name, seed=seed))
    return panels


def _parse_params(pairs):
    """--param i.key=value → {panel_index: {key: value}} with numeric coercion."""
    scoped = {}
    for p in pairs:
        left, v = p.split("=", 1)
        idx_s, key = left.split(".", 1)
        try:
            val = int(v)
        except ValueError:
            try:
                val = float(v)
            except ValueError:
                val = v
        scoped.setdefault(int(idx_s), {})[key] = val
    return scoped


@cli.command("plate")
@click.argument("panels", nargs=-1)
@click.option("--style", default="bauhaus", show_default=True, help="Style preset (lamina.styles)")
@click.option("--title", default=None, help="Plate title (spaced caps)")
@click.option("--subtitle", default=None)
@click.option("--paper", default="a4", show_default=True)
@click.option("--orientation", default="portrait", show_default=True)
@click.option("--margin", default=12.0, show_default=True)
@click.option("--gutter", default=8.0, show_default=True)
@click.option("--rows", default=None, type=int, help="Panel grid rows (default 1)")
@click.option("--seed", "base_seed", default=7, show_default=True, help="Base seed; panel i defaults to seed+i")
@click.option("--param", "params", multiple=True, help="Panel param override: i.key=value (repeatable)")
@click.option("--spec", "spec_path", default=None, help="Load a PlateSpec JSON instead of PANEL tokens")
@click.option("--preview", "preview_path", default=None, help="Write a PNG preview to this path")
@click.option("--save", default=None, help="Write the .gcode to this path")
@click.option("--simulate", is_flag=True, help="Stream to the simulated plotter")
@click.option("--port", default=None, help="Stream to hardware on this serial port")
@click.option("--baud", default=None, type=int)
def plate(panels, style, title, subtitle, paper, orientation, margin, gutter, rows,
          base_seed, params, spec_path, preview_path, save, simulate, port, baud):
    """Compose a plottable sheet from one or more pieces.

    PANEL tokens are `generator[:seed]`, e.g.:

        promptplot plate bauhaus_locality:7 bauhaus_memory:7 --style science_poster
    """
    from ..lamina import PlateSpec, compose_plate, spec_from_json

    config = _get_config()

    if spec_path:
        spec = spec_from_json(Path(spec_path).read_text())
    else:
        if not panels:
            raise click.ClickException("Provide PANEL tokens (generator[:seed]) or --spec plate.json")
        plist = _parse_panels(panels, base_seed)
        for idx, overrides in _parse_params(params).items():
            if idx >= len(plist):
                raise click.ClickException(f"--param index {idx} out of range")
            plist[idx].params.update(overrides)
        spec = PlateSpec(
            panels=plist, style=style, title=title, subtitle=subtitle, paper=paper,
            orientation=orientation, margin=margin, gutter=gutter, rows=rows,
        )

    try:
        program, pen_plan = compose_plate(spec, config)
    except (KeyError, ValueError) as e:
        raise click.ClickException(str(e))

    console.print(f"[bold]plate[/bold] {len(spec.panels)} panel(s) · style={spec.style} · {spec.paper} {spec.orientation}")
    console.print(f"[bold blue]commands[/bold blue] → {len(program.commands)}")
    console.print("[bold]pen plan[/bold] (swap between layers):")
    for layer in pen_plan:
        console.print(f"  pen {layer['pen']}: {layer['name']}  ({layer['strokes']} cmds)")

    if save:
        Path(save).parent.mkdir(parents=True, exist_ok=True)
        Path(save).write_text(program.to_gcode())
        console.print(f"[green]GCode saved to {save}[/green]")

    if preview_path:
        try:
            from ..visualizer import GCodeVisualizer

            Path(preview_path).parent.mkdir(parents=True, exist_ok=True)
            GCodeVisualizer(config).preview(program, preview_path)
            console.print(f"[green]Preview saved to {preview_path}[/green]")
        except ImportError:
            console.print("[yellow]matplotlib not available — skipping preview[/yellow]")

    if simulate or port:
        from ..plotter import SimulatedPlotter, SerialPlotter
        from ..orchestrate import stream_pen_layers, trace_frame

        config.color.pause_for_swap = not simulate

        async def _run():
            if simulate:
                plotter = SimulatedPlotter()
                await plotter.connect()
            else:
                # heartbeat off: single-reader discipline during long streams
                plotter = SerialPlotter(
                    port=port or config.serial.port,
                    baud_rate=baud or config.serial.baud_rate,
                    enable_heartbeat=False,
                )
                if not await plotter.connect():
                    console.print(f"[red]Could not connect to {port or config.serial.port}[/red]")
                    raise SystemExit(1)
                # Mandatory guardrail: pen-up tour of the drawable limits first.
                console.print("[cyan]tracing limits (pen up) — check the plate lands on the paper[/cyan]")
                await trace_frame(plotter, config.paper, laps=1)
            ok, err = await stream_pen_layers(program, plotter, config, verbose=False)
            if not simulate:
                await plotter.send_command("M5")
                await plotter.send_command("G0 X0 Y0")
                await plotter.disconnect()
            console.print(f"[bold]streamed[/bold] → {ok} ok, {err} errors")

        asyncio.run(_run())
