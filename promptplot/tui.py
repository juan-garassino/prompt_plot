"""
PromptPlot TUI — Rich-based terminal UI for live drawing.

A split-screen interface:
  - Header: connection status, model, paper size
  - Command log: rolling window of GCode commands as they stream
  - Footer: quality stats updated live
  - Input: prompt box at the bottom

Launch via: promptplot ui [--simulate] [--port /dev/cu.usbserial-1420]
"""

import asyncio
import time
from collections import deque
from typing import Optional

from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.prompt import Prompt

from .config import PromptPlotConfig, get_config


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class TUIState:
    """Mutable state shared between the UI renderer and async workflows."""

    def __init__(self, config: PromptPlotConfig):
        self.config = config
        # Connection
        self.plotter_type: str = "disconnected"
        self.plotter_port: str = ""
        self.connected: bool = False
        # Model
        self.provider: str = config.llm.default_provider
        self.model: str = getattr(config.llm, f"{config.llm.default_provider}_model", "?")
        # Paper
        self.paper: str = f"{config.paper.width:.0f}x{config.paper.height:.0f}mm"
        # Drawing state
        self.prompt: str = ""
        self.mode: str = ""  # "batch" / "live" / ""
        self.phase: str = "idle"  # idle / generating / streaming / done
        self.commands: deque = deque(maxlen=200)
        self.sent: int = 0
        self.errors: int = 0
        self.skipped: int = 0
        self.elapsed: float = 0.0
        # Quality
        self.grade: str = "-"
        self.utilization: float = 0.0
        self.strokes: int = 0
        self.draw_travel: float = 0.0


# ---------------------------------------------------------------------------
# Layout builders
# ---------------------------------------------------------------------------

def _header(state: TUIState) -> Panel:
    tbl = Table.grid(padding=(0, 3))
    tbl.add_column(min_width=20)
    tbl.add_column(min_width=20)
    tbl.add_column(min_width=20)
    tbl.add_column(min_width=15)

    if state.connected:
        conn = f"[green]● connected[/green] {state.plotter_port}"
    else:
        conn = "[dim]○ disconnected[/dim]"

    tbl.add_row(
        conn,
        f"[cyan]{state.provider}[/cyan] {state.model}",
        f"[dim]paper[/dim] {state.paper}",
        f"[dim]phase[/dim] {state.phase}",
    )
    return Panel(tbl, title="[bold]promptplot[/bold]", border_style="blue", height=3)


def _command_log(state: TUIState) -> Panel:
    lines = []
    for entry in list(state.commands)[-30:]:
        idx, gcode, status, warns = entry
        if status == "ok":
            sym = "[green]●[/green]"
        elif status == "DONE":
            sym = "[bold green]✓[/bold green]"
        elif status == "skip":
            sym = "[yellow]○[/yellow]"
        else:
            sym = "[red]✗[/red]"
        warn_str = f" [dim]{'; '.join(warns)}[/dim]" if warns else ""
        lines.append(f" {sym} [dim]{idx:3d}[/dim]  {gcode}{warn_str}")

    if not lines:
        if state.phase == "idle":
            lines = ["", "  [dim]Type a prompt below to start drawing.[/dim]", ""]
        elif state.phase == "generating":
            lines = ["", "  [dim]Generating...[/dim]", ""]

    content = "\n".join(lines)
    title = f"commands — {state.sent} sent"
    if state.errors:
        title += f", [red]{state.errors} errors[/red]"
    if state.skipped:
        title += f", [yellow]{state.skipped} skipped[/yellow]"

    return Panel(content, title=title, border_style="dim", height=35)


def _footer(state: TUIState) -> Panel:
    if state.phase == "idle":
        content = "[dim]Waiting for prompt...[/dim]"
    elif state.phase == "generating":
        content = f"[cyan]Generating GCode...[/cyan]  {state.elapsed:.1f}s"
    elif state.phase == "streaming":
        content = (
            f"[green]Streaming[/green]  "
            f"{state.sent} sent  "
            f"{state.elapsed:.1f}s"
        )
    else:
        grade_color = {
            "A": "bold green", "B": "green", "C": "yellow",
            "D": "red", "F": "bold red",
        }.get(state.grade, "dim")
        content = (
            f"[green]Done[/green]  "
            f"grade [{grade_color}]{state.grade}[/{grade_color}]  "
            f"utilization {state.utilization:.0%}  "
            f"strokes {state.strokes}  "
            f"draw/travel {state.draw_travel:.1f}  "
            f"[dim]{state.elapsed:.1f}s[/dim]"
        )

    return Panel(content, border_style="dim", height=3)


def _build_layout(state: TUIState) -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="footer", size=3),
    )
    layout["header"].update(_header(state))
    layout["body"].update(_command_log(state))
    layout["footer"].update(_footer(state))
    return layout


# ---------------------------------------------------------------------------
# Drawing runners
# ---------------------------------------------------------------------------

async def _run_live_draw(state: TUIState, prompt: str, plotter, live_display: Live):
    """Run LiveDrawWorkflow and update TUI state in real time."""
    from .workflow import LiveDrawWorkflow
    from .llm import get_llm_provider
    from .models import GCodeProgram
    from .scoring import score_gcode

    state.prompt = prompt
    state.mode = "live"
    state.phase = "streaming"
    state.commands.clear()
    state.sent = 0
    state.errors = 0
    state.skipped = 0
    state.grade = "-"
    t0 = time.time()

    llm = get_llm_provider(state.config.llm)

    async def on_step(step_num, max_s, gcode, ok, warnings):
        state.elapsed = time.time() - t0
        if gcode == "COMPLETE":
            state.commands.append((step_num, "COMPLETE", "DONE", []))
        elif ok:
            state.sent += 1
            state.commands.append((step_num, gcode, "ok", warnings))
        else:
            if "parse" in gcode or "error" in gcode.lower():
                state.skipped += 1
                state.commands.append((step_num, gcode, "skip", warnings))
            else:
                state.errors += 1
                state.commands.append((step_num, gcode, "err", warnings))
        live_display.update(_build_layout(state))

    wf = LiveDrawWorkflow(
        llm=llm, config=state.config, plotter=plotter,
        max_steps=80, on_step=on_step,
    )
    result = await wf.run(prompt=prompt)
    state.elapsed = time.time() - t0

    # Score
    program = GCodeProgram(**result["program"])
    g1_cmds = [c for c in program.commands if c.command == "G1"]
    if g1_cmds:
        report = score_gcode(program, state.config.paper)
        state.grade = report.grade
        state.utilization = report.canvas_utilization
        state.strokes = report.stroke_count
        state.draw_travel = report.draw_travel_ratio

    state.phase = "done"
    live_display.update(_build_layout(state))
    return result


async def _run_batch_draw(state: TUIState, prompt: str, plotter, live_display: Live):
    """Run BatchGCodeWorkflow + stream to plotter, updating TUI state."""
    from .workflow import BatchGCodeWorkflow
    from .llm import get_llm_provider
    from .models import GCodeProgram
    from .scoring import score_gcode

    state.prompt = prompt
    state.mode = "batch"
    state.phase = "generating"
    state.commands.clear()
    state.sent = 0
    state.errors = 0
    state.skipped = 0
    state.grade = "-"
    live_display.update(_build_layout(state))
    t0 = time.time()

    llm = get_llm_provider(state.config.llm)
    wf = BatchGCodeWorkflow(llm=llm, config=state.config)
    result = await wf.run(prompt=prompt)

    program = GCodeProgram(**result["program"])
    gen_time = time.time() - t0
    state.elapsed = gen_time
    state.commands.append((0, f"Generated {len(program.commands)} commands in {gen_time:.1f}s", "ok", []))
    live_display.update(_build_layout(state))

    # Score
    g1_cmds = [c for c in program.commands if c.command == "G1"]
    if g1_cmds:
        report = score_gcode(program, state.config.paper)
        state.grade = report.grade
        state.utilization = report.canvas_utilization
        state.strokes = report.stroke_count
        state.draw_travel = report.draw_travel_ratio

    # Stream to plotter
    state.phase = "streaming"
    live_display.update(_build_layout(state))

    cmd_idx = [0]

    async def on_command(idx, total, gcode, ok):
        state.elapsed = time.time() - t0
        cmd_idx[0] += 1
        if ok:
            state.sent += 1
            state.commands.append((cmd_idx[0], gcode, "ok", []))
        else:
            state.errors += 1
            state.commands.append((cmd_idx[0], gcode, "err", []))
        live_display.update(_build_layout(state))

    async with plotter:
        state.connected = True
        state.plotter_port = plotter.port
        live_display.update(_build_layout(state))
        await plotter.stream_program(program, on_command=on_command)

    state.elapsed = time.time() - t0
    state.phase = "done"
    state.connected = False
    live_display.update(_build_layout(state))
    return result


# ---------------------------------------------------------------------------
# Main TUI loop
# ---------------------------------------------------------------------------

def run_tui(
    config: PromptPlotConfig,
    simulate: bool = True,
    port: Optional[str] = None,
    baud: int = 115200,
    live_mode: bool = True,
):
    """Launch the PromptPlot TUI."""
    console = Console()
    state = TUIState(config)

    if simulate:
        state.plotter_type = "simulated"
    elif port:
        state.plotter_type = "serial"
        state.plotter_port = port

    def _get_plotter():
        from .plotter import SimulatedPlotter, SerialPlotter
        if simulate:
            return SimulatedPlotter(command_delay=0.02)
        else:
            return SerialPlotter(
                port=port or config.serial.port,
                baud_rate=baud,
                timeout=config.serial.timeout,
            )

    console.clear()

    while True:
        # Show current layout in idle state
        state.phase = "idle"
        state.commands.clear()
        state.sent = 0
        state.errors = 0
        state.skipped = 0
        state.grade = "-"
        state.utilization = 0.0
        state.strokes = 0
        state.draw_travel = 0.0

        # Print the idle screen
        console.print(_build_layout(state))
        console.print()

        # Get prompt from user
        try:
            prompt = Prompt.ask("[bold cyan]draw[/bold cyan]")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Bye.[/dim]")
            break

        if prompt.lower() in ("quit", "exit", "q"):
            console.print("[dim]Bye.[/dim]")
            break
        if not prompt.strip():
            continue

        # Handle slash commands
        if prompt.startswith("/"):
            parts = prompt.split()
            cmd = parts[0].lower()
            if cmd == "/live":
                live_mode = True
                console.print("  [green]Switched to live mode[/green]")
                continue
            elif cmd == "/batch":
                live_mode = False
                console.print("  [green]Switched to batch mode[/green]")
                continue
            elif cmd in ("/style", "/s"):
                if len(parts) > 1 and parts[1] in ("artistic", "precise", "sketch", "minimal"):
                    # Would need to pass style through — for now just note it
                    console.print(f"  [green]Style: {parts[1]}[/green]")
                else:
                    console.print("  [dim]Styles: artistic, precise, sketch, minimal[/dim]")
                continue
            elif cmd == "/status":
                console.print(f"  mode: {'live' if live_mode else 'batch'}")
                console.print(f"  plotter: {state.plotter_type} {state.plotter_port}")
                console.print(f"  model: {state.provider} {state.model}")
                console.print(f"  paper: {state.paper}")
                continue
            elif cmd in ("/help", "/h", "/?"):
                console.print("  [bold]Commands:[/bold]")
                console.print("  /live          Switch to live mode (real-time)")
                console.print("  /batch         Switch to batch mode")
                console.print("  /style <name>  Set style (artistic|precise|sketch|minimal)")
                console.print("  /status        Show current settings")
                console.print("  /help          This help")
                console.print("  quit           Exit")
                console.print()
                console.print("  [bold]Or just type what you want drawn.[/bold]")
                continue
            else:
                console.print(f"  [dim]Unknown command: {cmd}. Type /help[/dim]")
                continue

        # Run the drawing
        console.clear()
        plotter = _get_plotter()

        if live_mode:
            state.plotter_port = plotter.port
            state.connected = True

            async def _run():
                async with plotter:
                    with Live(_build_layout(state), console=console, refresh_per_second=8) as live_display:
                        return await _run_live_draw(state, prompt, plotter, live_display)

            try:
                result = asyncio.run(_run())
            except KeyboardInterrupt:
                console.print("\n  [yellow]Interrupted[/yellow]")
            state.connected = False
        else:
            with Live(_build_layout(state), console=console, refresh_per_second=8) as live_display:
                try:
                    result = asyncio.run(
                        _run_batch_draw(state, prompt, plotter, live_display)
                    )
                except KeyboardInterrupt:
                    console.print("\n  [yellow]Interrupted[/yellow]")

        # Show final state and wait for next prompt
        console.print()
        console.print(_build_layout(state))
        console.print()
