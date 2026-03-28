"""
Rich-based logging and display for PromptPlot v3.0

Single source of all terminal output. Everything goes through WorkflowLogger
or the Rich Console — no colorama, no raw print_tree().
Kept as-is from utils/rich_logger.py with new methods for brush, dwell, pipeline, CLI.
"""

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    Progress, SpinnerColumn, TextColumn, BarColumn,
    TaskProgressColumn, TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text
from rich.tree import Tree
from rich.live import Live
from rich import box
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
import time
import shutil

COLORS = {
    "primary": "blue",
    "success": "green",
    "warning": "yellow",
    "error": "red",
    "info": "cyan",
    "muted": "dim white",
    "highlight": "magenta",
    "command": "bright_cyan",
    "gcode": "bright_green",
}

SYMBOLS = {
    "success": "[K]",
    "error": "[E]",
    "warning": "[!]",
    "info": "[i]",
    "step": "[:]",
    "arrow": "[>]",
    "bullet": "[*]",
    "check": "[v]",
    "cross": "[x]",
    "pending": "[P]",
    "running": "[~]",
}


class WorkflowLogger:
    """Rich-based logger for workflow steps and progress."""

    def __init__(self, console: Optional[Console] = None, width_percent: float = 0.6):
        self.console = console or Console()
        terminal_width = shutil.get_terminal_size().columns
        self.width = max(80, int(terminal_width * width_percent))
        self.current_step = 0
        self.total_steps = 0
        self.start_time = time.time()
        self._current_tree = None
        self._tree_items: List[Any] = []

    # ==================== TREE-BASED OUTPUT ====================

    def tree_start(self, title: str, style: str = "primary"):
        self._current_tree = Tree(f"[bold {COLORS[style]}]{title}[/bold {COLORS[style]}]")
        self._tree_items = []
        return self._current_tree

    def tree_add(self, message: str, status: str = "info", parent: Any = None):
        symbol = SYMBOLS.get(status, SYMBOLS["bullet"])
        color = COLORS.get(status, COLORS["muted"])
        formatted = f"[{color}]{symbol}[/{color}] {message}"
        if parent is not None:
            return parent.add(formatted)
        elif self._current_tree is not None:
            return self._current_tree.add(formatted)
        return None

    def tree_end(self, border_style: str = "primary"):
        if self._current_tree is not None:
            panel = Panel(
                self._current_tree,
                border_style=COLORS.get(border_style, COLORS["primary"]),
                box=box.ROUNDED,
                width=self.width,
            )
            self.console.print(panel)
            self._current_tree = None
            self._tree_items = []

    def tree_result(self, title: str, results: Dict[str, Any], success: bool = True):
        style = "success" if success else "error"
        symbol = SYMBOLS["success"] if success else SYMBOLS["error"]
        tree = Tree(f"[bold {COLORS[style]}]{symbol} {title}[/bold {COLORS[style]}]")
        for key, value in results.items():
            tree.add(f"[{COLORS['muted']}]{key}:[/{COLORS['muted']}] [bold]{value}[/bold]")
        panel = Panel(tree, border_style=COLORS[style], box=box.ROUNDED, width=self.width)
        self.console.print(panel)

    # ==================== PROGRESS BAR ====================

    @contextmanager
    def progress_context(self, description: str = "Processing", total: int = 100):
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=30),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=self.console,
            expand=False,
        )
        with progress:
            task = progress.add_task(description, total=total)
            yield progress, task

    def progress_panel(self, current: int, total: int, description: str = "Progress"):
        if total <= 0:
            total = 1
        pct = current / total * 100
        bar_width = 40
        filled = int(bar_width * current / total)
        bar = (
            f"[{COLORS['success']}]{'█' * filled}[/{COLORS['success']}]"
            f"[{COLORS['muted']}]{'░' * (bar_width - filled)}[/{COLORS['muted']}]"
        )
        content = f"[bold]{description}[/bold]\n\n{bar}\n\n"
        content += (
            f"[{COLORS['info']}]{current}[/{COLORS['info']}] / "
            f"[{COLORS['muted']}]{total}[/{COLORS['muted']}] "
            f"([bold {COLORS['success']}]{pct:.1f}%[/bold {COLORS['success']}])"
        )
        panel = Panel(content, border_style=COLORS["info"], box=box.ROUNDED, width=self.width)
        self.console.print(panel)

    # ==================== WORKFLOW LIFECYCLE ====================

    def workflow_start(self, title: str, prompt: str):
        content = (
            f"[bold {COLORS['primary']}]{title}[/bold {COLORS['primary']}]\n\n"
            f"[{COLORS['muted']}]Prompt:[/{COLORS['muted']}] [italic]{prompt}[/italic]"
        )
        panel = Panel(
            content, title="PromptPlot Workflow",
            border_style=COLORS["primary"], box=box.ROUNDED, width=self.width,
        )
        self.console.print(panel)
        self.start_time = time.time()

    def workflow_complete(self, success: bool, commands_count: int = 0,
                          gcode_preview: Optional[List[str]] = None):
        elapsed = time.time() - self.start_time
        style = "success" if success else "error"
        symbol = SYMBOLS["success"] if success else SYMBOLS["error"]
        if success:
            tree = Tree(f"[bold {COLORS[style]}]{symbol} Workflow completed![/bold {COLORS[style]}]")
            if commands_count > 0:
                tree.add(f"[{COLORS['muted']}]Generated:[/{COLORS['muted']}] [bold]{commands_count}[/bold] G-code commands")
            if gcode_preview:
                pb = tree.add(f"[{COLORS['muted']}]Preview:[/{COLORS['muted']}]")
                for i, line in enumerate(gcode_preview[:5], 1):
                    pb.add(f"[{COLORS['muted']}]{i:2d}.[/{COLORS['muted']}] [{COLORS['gcode']}]{line}[/{COLORS['gcode']}]")
                if len(gcode_preview) > 5:
                    pb.add(f"[{COLORS['muted']}]... and {len(gcode_preview) - 5} more commands[/{COLORS['muted']}]")
            tree.add(f"[{COLORS['muted']}]Completed in {elapsed:.1f} seconds[/{COLORS['muted']}]")
        else:
            tree = Tree(f"[bold {COLORS[style]}]{symbol} Workflow failed[/bold {COLORS[style]}]")
            tree.add(f"[{COLORS['muted']}]Check the error messages above for details[/{COLORS['muted']}]")
        panel = Panel(tree, title="Success" if success else "Error",
                      border_style=COLORS[style], box=box.ROUNDED, width=self.width)
        self.console.print(panel)

    # ==================== STEP LOGGING ====================

    def step_start(self, step_name: str, description: str = ""):
        self.current_step += 1
        title = f"Step {self.current_step}: {step_name}"
        content = f"[bold {COLORS['info']}]{step_name}[/bold {COLORS['info']}]"
        if description:
            content += f"\n[{COLORS['muted']}]{description}[/{COLORS['muted']}]"
        panel = Panel(content, title=f"{SYMBOLS['step']} {title}",
                      border_style=COLORS["info"], box=box.ROUNDED, width=self.width)
        self.console.print(panel)

    def _step_msg(self, message: str, status: str, details: Optional[Dict[str, Any]] = None):
        symbol = SYMBOLS.get(status, SYMBOLS["info"])
        color = COLORS.get(status, COLORS["muted"])
        if details:
            tree = Tree(f"[{color}]{symbol}[/{color}] {message}")
            for k, v in details.items():
                tree.add(f"[{COLORS['muted']}]{k}:[/{COLORS['muted']}] {v}")
            panel = Panel(tree, border_style=color, box=box.ROUNDED, width=self.width)
        else:
            content = f"[{color}]{symbol}[/{color}] {message}"
            panel = Panel(content, border_style=color, box=box.ROUNDED, width=self.width)
        self.console.print(panel)

    def step_info(self, message: str, details: Optional[Dict[str, Any]] = None):
        self._step_msg(message, "info", details)

    def step_success(self, message: str, details: Optional[Dict[str, Any]] = None):
        self._step_msg(message, "success", details)

    def step_warning(self, message: str, details: Optional[Dict[str, Any]] = None):
        self._step_msg(message, "warning", details)

    def step_error(self, message: str, details: Optional[Dict[str, Any]] = None):
        self._step_msg(message, "error", details)

    def retry_attempt(self, attempt: int, max_attempts: int, reason: str = ""):
        tree = Tree(f"[{COLORS['warning']}]{SYMBOLS['warning']} Retry attempt {attempt}/{max_attempts}[/{COLORS['warning']}]")
        if reason:
            tree.add(f"[{COLORS['muted']}]Reason: {reason}[/{COLORS['muted']}]")
        panel = Panel(tree, title="Retry", border_style=COLORS["warning"],
                      box=box.ROUNDED, width=self.width)
        self.console.print(panel)

    def llm_call(self, provider: str, model: str = "", prompt_preview: str = ""):
        tree = Tree(f"[bold {COLORS['highlight']}]{SYMBOLS['arrow']} Calling {provider}[/bold {COLORS['highlight']}]")
        if model:
            tree.add(f"[{COLORS['muted']}]Model: {model}[/{COLORS['muted']}]")
        if prompt_preview:
            tree.add(f"[{COLORS['muted']}]Prompt: {prompt_preview[:100]}...[/{COLORS['muted']}]")
        panel = Panel(tree, title="LLM API Call", border_style=COLORS["highlight"],
                      box=box.ROUNDED, width=self.width)
        self.console.print(panel)

    def validation_result(self, success: bool, commands_count: int = 0,
                          errors: Optional[List[str]] = None):
        style = "success" if success else "error"
        symbol = SYMBOLS["success"] if success else SYMBOLS["error"]
        if success:
            tree = Tree(f"[{COLORS[style]}]{symbol} Validation successful[/{COLORS[style]}]")
            if commands_count > 0:
                tree.add(f"[{COLORS['muted']}]Generated {commands_count} valid commands[/{COLORS['muted']}]")
        else:
            tree = Tree(f"[{COLORS[style]}]{symbol} Validation failed[/{COLORS[style]}]")
            if errors:
                eb = tree.add(f"[{COLORS['muted']}]Errors:[/{COLORS['muted']}]")
                for e in errors[:3]:
                    eb.add(f"{SYMBOLS['bullet']} {e}")
                if len(errors) > 3:
                    eb.add(f"{SYMBOLS['bullet']} ... and {len(errors) - 3} more")
        panel = Panel(tree, title="Validation", border_style=COLORS[style],
                      box=box.ROUNDED, width=self.width)
        self.console.print(panel)

    def strategy_analysis(self, strategy_name: str, complexity: Dict[str, Any]):
        table = Table(title="Strategy Analysis", box=box.ROUNDED, width=self.width)
        table.add_column("Property", style=COLORS["muted"])
        table.add_column("Value", style="bold")
        table.add_row("Selected Strategy", f"[{COLORS['highlight']}]{strategy_name}[/{COLORS['highlight']}]")
        table.add_row("Complexity Level", str(complexity.get("complexity_level", "unknown")))
        table.add_row("Requires Curves", str(complexity.get("requires_curves", False)))
        table.add_row("Estimated Commands", str(complexity.get("estimated_commands", 0)))
        table.add_row("Confidence Score", f"{complexity.get('confidence_score', 0):.2f}")
        self.console.print(table)

    def gcode_preview(self, gcode_lines: List[str], title: str = "Generated G-code"):
        table = Table(title=title, box=box.ROUNDED, width=self.width)
        table.add_column("Line", style=COLORS["muted"], width=4)
        table.add_column("Command", style=COLORS["gcode"])
        for i, line in enumerate(gcode_lines[:10], 1):
            table.add_row(str(i), line)
        if len(gcode_lines) > 10:
            table.add_row("...", f"[{COLORS['muted']}]and {len(gcode_lines) - 10} more[/{COLORS['muted']}]")
        self.console.print(table)

    def plotter_status(self, connected: bool, port: str = "",
                       commands_sent: int = 0, success_rate: float = 0.0):
        style = "success" if connected else "error"
        symbol = SYMBOLS["success"] if connected else SYMBOLS["error"]
        if connected:
            tree = Tree(f"[{COLORS[style]}]{symbol} Connected to plotter[/{COLORS[style]}]")
            if port:
                tree.add(f"[{COLORS['muted']}]Port: {port}[/{COLORS['muted']}]")
            if commands_sent > 0:
                tree.add(f"[{COLORS['muted']}]Commands sent: {commands_sent}[/{COLORS['muted']}]")
                tree.add(f"[{COLORS['muted']}]Success rate: {success_rate:.1%}[/{COLORS['muted']}]")
        else:
            tree = Tree(f"[{COLORS[style]}]{symbol} Not connected to plotter[/{COLORS[style]}]")
        panel = Panel(tree, title="Plotter Status", border_style=COLORS[style],
                      box=box.ROUNDED, width=self.width)
        self.console.print(panel)

    # ==================== STREAMING ====================

    def stream_command(self, step: int, command: str, status: str = "pending"):
        sym_map = {"pending": SYMBOLS["pending"], "executing": SYMBOLS["running"],
                   "success": SYMBOLS["success"], "error": SYMBOLS["error"],
                   "skipped": SYMBOLS["arrow"]}
        col_map = {"pending": COLORS["warning"], "executing": COLORS["info"],
                   "success": COLORS["success"], "error": COLORS["error"],
                   "skipped": COLORS["muted"]}
        s = sym_map.get(status, SYMBOLS["pending"])
        c = col_map.get(status, COLORS["muted"])
        content = f"[{c}]{s}[/{c}] [{COLORS['muted']}]Step {step:3d}:[/{COLORS['muted']}] [{COLORS['command']}]{command}[/{COLORS['command']}]"
        panel = Panel(content, box=box.ROUNDED, width=self.width, border_style=c)
        self.console.print(panel)

    def stream_start(self, title: str, prompt: str, max_steps: int = 0):
        tree = Tree(f"[bold {COLORS['highlight']}]{title}[/bold {COLORS['highlight']}]")
        tree.add(f"[{COLORS['muted']}]Prompt:[/{COLORS['muted']}] [italic]{prompt}[/italic]")
        if max_steps > 0:
            tree.add(f"[{COLORS['muted']}]Max steps:[/{COLORS['muted']}] {max_steps}")
        panel = Panel(tree, title="Streaming Workflow", border_style=COLORS["highlight"],
                      box=box.ROUNDED, width=self.width)
        self.console.print(panel)

    def stream_progress(self, current: int, total: int, command: str = ""):
        desc = f"Streaming: {command}" if command else "Streaming Progress"
        self.progress_panel(current, total, desc)

    def command_executed(self, step: int, command: str, response: str = "",
                         success: bool = True):
        symbol = SYMBOLS["success"] if success else SYMBOLS["error"]
        color = COLORS["success"] if success else COLORS["error"]
        content = (
            f"[{color}]{symbol}[/{color}] [{COLORS['muted']}]#{step:3d}[/{COLORS['muted']}] "
            f"[{COLORS['gcode']}]{command:20s}[/{COLORS['gcode']}] [{color}]{response}[/{color}]"
        )
        panel = Panel(content, box=box.ROUNDED, width=self.width, border_style=color)
        self.console.print(panel)

    def plotter_command(self, command: str, response: str = "ok", success: bool = True):
        symbol = SYMBOLS["arrow"] if success else SYMBOLS["cross"]
        color = COLORS["success"] if success else COLORS["error"]
        content = (
            f"[{color}]{symbol}[/{color}] [{COLORS['gcode']}]{command:25s}[/{COLORS['gcode']}] "
            f"[{color}]{response}[/{color}]"
        )
        panel = Panel(content, box=box.ROUNDED, width=self.width, border_style=color)
        self.console.print(panel)

    def commands_table(self, commands: List[Dict[str, Any]], title: str = "Commands"):
        table = Table(title=title, box=box.ROUNDED, width=self.width, show_lines=False)
        table.add_column("#", style=COLORS["muted"], width=4)
        table.add_column("Command", style=COLORS["gcode"])
        table.add_column("X", style=COLORS["info"], justify="right", width=8)
        table.add_column("Y", style=COLORS["info"], justify="right", width=8)
        table.add_column("Status", width=8)
        for i, cmd in enumerate(commands[:15], 1):
            st = SYMBOLS["success"] if cmd.get("success", True) else SYMBOLS["error"]
            table.add_row(
                str(i), cmd.get("command", ""),
                f"{cmd.get('x', ''):.2f}" if cmd.get("x") is not None else "-",
                f"{cmd.get('y', ''):.2f}" if cmd.get("y") is not None else "-",
                st,
            )
        if len(commands) > 15:
            table.add_row("...", f"[{COLORS['muted']}]+{len(commands) - 15} more[/{COLORS['muted']}]", "", "", "")
        self.console.print(table)

    def execution_summary(self, total: int, success: int, failed: int, elapsed: float):
        rate = (success / total * 100) if total > 0 else 0
        tree = Tree(f"[bold {COLORS['info']}]Execution Summary[/bold {COLORS['info']}]")
        tree.add(f"[{COLORS['muted']}]Total Commands:[/{COLORS['muted']}] [bold]{total}[/bold]")
        tree.add(f"[{COLORS['success']}]Successful:[/{COLORS['success']}] [bold]{success}[/bold]")
        tree.add(f"[{COLORS['error']}]Failed:[/{COLORS['error']}] [bold]{failed}[/bold]")
        tree.add(f"[{COLORS['muted']}]Success Rate:[/{COLORS['muted']}] [bold {COLORS['success']}]{rate:.1f}%[/bold {COLORS['success']}]")
        tree.add(f"[{COLORS['muted']}]Elapsed Time:[/{COLORS['muted']}] [bold]{elapsed:.2f}s[/bold]")
        panel = Panel(tree, border_style=COLORS["info"], box=box.ROUNDED, width=self.width)
        self.console.print(panel)

    def reflection_prompt(self, attempt: int, max_attempts: int, error: str):
        tree = Tree(f"[{COLORS['warning']}]{SYMBOLS['warning']} Reflection Attempt {attempt}/{max_attempts}[/{COLORS['warning']}]")
        eb = tree.add(f"[{COLORS['muted']}]Previous error:[/{COLORS['muted']}]")
        eb.add(f"[{COLORS['error']}]{error[:200]}{'...' if len(error) > 200 else ''}[/{COLORS['error']}]")
        panel = Panel(tree, title="LLM Reflection", border_style=COLORS["warning"],
                      box=box.ROUNDED, width=self.width)
        self.console.print(panel)

    def ink_change(self, color: str, position: str = ""):
        tree = Tree(f"[bold {COLORS['highlight']}]{SYMBOLS['warning']} Ink Change Required[/bold {COLORS['highlight']}]")
        tree.add(f"[{COLORS['muted']}]New color:[/{COLORS['muted']}] [bold]{color}[/bold]")
        if position:
            tree.add(f"[{COLORS['muted']}]Position:[/{COLORS['muted']}] {position}")
        panel = Panel(tree, title="Pen Change", border_style=COLORS["highlight"],
                      box=box.ROUNDED, width=self.width)
        self.console.print(panel)

    def pause_resume(self, paused: bool, reason: str = ""):
        if paused:
            tree = Tree(f"[{COLORS['warning']}]{SYMBOLS['pending']} Workflow Paused[/{COLORS['warning']}]")
            if reason:
                tree.add(f"[{COLORS['muted']}]Reason: {reason}[/{COLORS['muted']}]")
            border = COLORS["warning"]
        else:
            tree = Tree(f"[{COLORS['success']}]{SYMBOLS['arrow']} Workflow Resumed[/{COLORS['success']}]")
            border = COLORS["success"]
        panel = Panel(tree, border_style=border, box=box.ROUNDED, width=self.width)
        self.console.print(panel)

    # ==================== NEW METHODS (v3.0) ====================

    def brush_reload(self, station_pos: tuple, stroke_count: int):
        tree = Tree(f"[bold {COLORS['highlight']}]{SYMBOLS['arrow']} Brush Reload[/bold {COLORS['highlight']}]")
        tree.add(f"[{COLORS['muted']}]Station:[/{COLORS['muted']}] ({station_pos[0]:.1f}, {station_pos[1]:.1f})")
        tree.add(f"[{COLORS['muted']}]After stroke:[/{COLORS['muted']}] {stroke_count}")
        panel = Panel(tree, border_style=COLORS["highlight"], box=box.ROUNDED, width=self.width)
        self.console.print(panel)

    def dwell_info(self, command: str, delay_ms: int):
        content = (
            f"[{COLORS['info']}]{SYMBOLS['info']}[/{COLORS['info']}] "
            f"G4 P{delay_ms} after [{COLORS['gcode']}]{command}[/{COLORS['gcode']}]"
        )
        panel = Panel(content, border_style=COLORS["muted"], box=box.ROUNDED, width=self.width)
        self.console.print(panel)

    def pipeline_step(self, step_num: int, total: int, name: str, status: str = "running"):
        symbol = SYMBOLS.get(status, SYMBOLS["running"])
        color = COLORS.get(status, COLORS["info"])
        content = (
            f"[{color}]{symbol}[/{color}] "
            f"[{COLORS['muted']}]Step {step_num}/{total}:[/{COLORS['muted']}] "
            f"[bold]{name}[/bold]"
        )
        panel = Panel(content, border_style=color, box=box.ROUNDED, width=self.width)
        self.console.print(panel)

    def config_table(self, config_dict: Dict[str, Any]):
        table = Table(title="Configuration", box=box.ROUNDED, width=self.width)
        table.add_column("Key", style=COLORS["muted"])
        table.add_column("Value", style="bold")
        for k, v in config_dict.items():
            table.add_row(str(k), str(v))
        self.console.print(table)

    def cli_header(self, version: str):
        try:
            from pyfiglet import figlet_format
            title = figlet_format("PromptPlot", font="slant")
        except ImportError:
            title = "PromptPlot"
        content = (
            f"[bold {COLORS['primary']}]{title.rstrip()}[/bold {COLORS['primary']}]\n"
            f"[{COLORS['muted']}]  v{version} — pen plotter GCode generator[/{COLORS['muted']}]"
        )
        panel = Panel(content, box=box.ROUNDED, width=self.width,
                      border_style=COLORS["primary"])
        self.console.print(panel)
