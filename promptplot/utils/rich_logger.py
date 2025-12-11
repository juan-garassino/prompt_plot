"""
Rich-based logging utilities for PromptPlot workflows

Provides clean, professional output using Rich panels, progress bars, trees, and tables.
All panels use consistent width (60% of terminal by default) for clean appearance.
Uses ASCII symbols only, no emojis.
"""

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text
from rich.tree import Tree
from rich.live import Live
from rich import box
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
import time
import shutil

# Color scheme for consistent styling
COLORS = {
    'primary': 'blue',
    'success': 'green',
    'warning': 'yellow', 
    'error': 'red',
    'info': 'cyan',
    'muted': 'dim white',
    'highlight': 'magenta',
    'command': 'bright_cyan',
    'gcode': 'bright_green',
}

# ASCII symbols for status indicators
SYMBOLS = {
    'success': '[K]',
    'error': '[E]',
    'warning': '[!]',
    'info': '[i]',
    'step': '[:]',
    'arrow': '[>]',
    'bullet': '[*]',
    'check': '[v]',
    'cross': '[x]',
    'pending': '[P]',
    'running': '[~]',
}


class WorkflowLogger:
    """Rich-based logger for workflow steps and progress."""
    
    def __init__(self, console: Optional[Console] = None, width_percent: float = 0.6):
        """Initialize the logger.
        
        Args:
            console: Rich console instance (creates new if None)
            width_percent: Width as percentage of terminal (0.0-1.0), default 60%
        """
        self.console = console or Console()
        terminal_width = shutil.get_terminal_size().columns
        self.width = max(80, int(terminal_width * width_percent))
        self.current_step = 0
        self.total_steps = 0
        self.start_time = time.time()
        self._current_tree = None
        self._tree_items = []
        
    # ==================== TREE-BASED OUTPUT ====================
    
    def tree_start(self, title: str, style: str = "primary"):
        """Start a new tree for hierarchical output."""
        self._current_tree = Tree(f"[bold {COLORS[style]}]{title}[/bold {COLORS[style]}]")
        self._tree_items = []
        return self._current_tree
    
    def tree_add(self, message: str, status: str = "info", parent: Any = None):
        """Add an item to the current tree."""
        symbol = SYMBOLS.get(status, SYMBOLS['bullet'])
        color = COLORS.get(status, COLORS['muted'])
        
        formatted = f"[{color}]{symbol}[/{color}] {message}"
        
        if parent is not None:
            branch = parent.add(formatted)
        elif self._current_tree is not None:
            branch = self._current_tree.add(formatted)
        else:
            branch = None
            
        return branch
    
    def tree_end(self, border_style: str = "primary"):
        """End the current tree and display it in a panel."""
        if self._current_tree is not None:
            panel = Panel(
                self._current_tree,
                border_style=COLORS.get(border_style, COLORS['primary']),
                box=box.ROUNDED,
                width=self.width
            )
            self.console.print(panel)
            self._current_tree = None
            self._tree_items = []
    
    def tree_result(self, title: str, results: Dict[str, Any], success: bool = True):
        """Display results in a tree format inside a panel."""
        style = 'success' if success else 'error'
        symbol = SYMBOLS['success'] if success else SYMBOLS['error']
        
        tree = Tree(f"[bold {COLORS[style]}]{symbol} {title}[/bold {COLORS[style]}]")
        
        for key, value in results.items():
            tree.add(f"[{COLORS['muted']}]{key}:[/{COLORS['muted']}] [bold]{value}[/bold]")
        
        panel = Panel(
            tree,
            border_style=COLORS[style],
            box=box.ROUNDED,
            width=self.width
        )
        self.console.print(panel)
        
    # ==================== PROGRESS BAR ====================
    
    @contextmanager
    def progress_context(self, description: str = "Processing", total: int = 100):
        """Context manager for progress bar display."""
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=30),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=self.console,
            expand=False
        )
        
        with progress:
            task = progress.add_task(description, total=total)
            yield progress, task
    
    def progress_panel(self, current: int, total: int, description: str = "Progress"):
        """Display progress as a visual bar inside a panel."""
        if total <= 0:
            total = 1
        progress_pct = (current / total * 100)
        bar_width = 40
        filled = int(bar_width * current / total)
        
        bar = f"[{COLORS['success']}]{'█' * filled}[/{COLORS['success']}][{COLORS['muted']}]{'░' * (bar_width - filled)}[/{COLORS['muted']}]"
        
        content = f"[bold]{description}[/bold]\n\n"
        content += f"{bar}\n\n"
        content += f"[{COLORS['info']}]{current}[/{COLORS['info']}] / [{COLORS['muted']}]{total}[/{COLORS['muted']}] "
        content += f"([bold {COLORS['success']}]{progress_pct:.1f}%[/bold {COLORS['success']}])"
        
        panel = Panel(
            content,
            border_style=COLORS['info'],
            box=box.ROUNDED,
            width=self.width
        )
        self.console.print(panel)
        
    # ==================== WORKFLOW LIFECYCLE ====================
        
    def workflow_start(self, title: str, prompt: str):
        """Display workflow start banner."""
        content = f"[bold {COLORS['primary']}]{title}[/bold {COLORS['primary']}]\n\n"
        content += f"[{COLORS['muted']}]Prompt:[/{COLORS['muted']}] [italic]{prompt}[/italic]"
        
        panel = Panel(
            content,
            title="PromptPlot Workflow",
            border_style=COLORS['primary'],
            box=box.ROUNDED,
            width=self.width
        )
        self.console.print(panel)
        self.start_time = time.time()
        
    def workflow_complete(self, success: bool, commands_count: int = 0, gcode_preview: List[str] = None):
        """Display workflow completion banner with tree structure."""
        elapsed = time.time() - self.start_time
        style = 'success' if success else 'error'
        symbol = SYMBOLS['success'] if success else SYMBOLS['error']
        
        if success:
            tree = Tree(f"[bold {COLORS[style]}]{symbol} Workflow completed successfully![/bold {COLORS[style]}]")
            
            if commands_count > 0:
                tree.add(f"[{COLORS['muted']}]Generated:[/{COLORS['muted']}] [bold]{commands_count}[/bold] G-code commands")
            
            if gcode_preview:
                preview_branch = tree.add(f"[{COLORS['muted']}]Preview:[/{COLORS['muted']}]")
                for i, line in enumerate(gcode_preview[:5], 1):
                    preview_branch.add(f"[{COLORS['muted']}]{i:2d}.[/{COLORS['muted']}] [{COLORS['gcode']}]{line}[/{COLORS['gcode']}]")
                if len(gcode_preview) > 5:
                    preview_branch.add(f"[{COLORS['muted']}]... and {len(gcode_preview) - 5} more commands[/{COLORS['muted']}]")
            
            tree.add(f"[{COLORS['muted']}]Completed in {elapsed:.1f} seconds[/{COLORS['muted']}]")
        else:
            tree = Tree(f"[bold {COLORS[style]}]{symbol} Workflow failed[/bold {COLORS[style]}]")
            tree.add(f"[{COLORS['muted']}]Check the error messages above for details[/{COLORS['muted']}]")
        
        panel = Panel(
            tree,
            title="Success" if success else "Error",
            border_style=COLORS[style],
            box=box.ROUNDED,
            width=self.width
        )
        self.console.print(panel)
        
    # ==================== STEP LOGGING ====================
        
    def step_start(self, step_name: str, description: str = ""):
        """Start a new workflow step."""
        self.current_step += 1
        
        title = f"Step {self.current_step}: {step_name}"
        content = f"[bold {COLORS['info']}]{step_name}[/bold {COLORS['info']}]"
        if description:
            content += f"\n[{COLORS['muted']}]{description}[/{COLORS['muted']}]"
            
        panel = Panel(
            content,
            title=f"{SYMBOLS['step']} {title}",
            border_style=COLORS['info'],
            box=box.ROUNDED,
            width=self.width
        )
        self.console.print(panel)
        
    def step_info(self, message: str, details: Optional[Dict[str, Any]] = None):
        """Log step information with optional tree details."""
        if details:
            tree = Tree(f"[{COLORS['info']}]{SYMBOLS['info']}[/{COLORS['info']}] {message}")
            for key, value in details.items():
                tree.add(f"[{COLORS['muted']}]{key}:[/{COLORS['muted']}] {value}")
            
            panel = Panel(tree, border_style=COLORS['muted'], box=box.ROUNDED, width=self.width)
        else:
            content = f"[{COLORS['info']}]{SYMBOLS['info']}[/{COLORS['info']}] {message}"
            panel = Panel(content, border_style=COLORS['muted'], box=box.ROUNDED, width=self.width)
        
        self.console.print(panel)
            
    def step_success(self, message: str, details: Optional[Dict[str, Any]] = None):
        """Log step success with optional tree details."""
        if details:
            tree = Tree(f"[{COLORS['success']}]{SYMBOLS['success']}[/{COLORS['success']}] {message}")
            for key, value in details.items():
                tree.add(f"[{COLORS['muted']}]{key}:[/{COLORS['muted']}] {value}")
            
            panel = Panel(tree, border_style=COLORS['success'], box=box.ROUNDED, width=self.width)
        else:
            content = f"[{COLORS['success']}]{SYMBOLS['success']}[/{COLORS['success']}] {message}"
            panel = Panel(content, border_style=COLORS['success'], box=box.ROUNDED, width=self.width)
        
        self.console.print(panel)
            
    def step_warning(self, message: str, details: Optional[Dict[str, Any]] = None):
        """Log step warning with optional tree details."""
        if details:
            tree = Tree(f"[{COLORS['warning']}]{SYMBOLS['warning']}[/{COLORS['warning']}] {message}")
            for key, value in details.items():
                tree.add(f"[{COLORS['muted']}]{key}:[/{COLORS['muted']}] {value}")
            
            panel = Panel(tree, border_style=COLORS['warning'], box=box.ROUNDED, width=self.width)
        else:
            content = f"[{COLORS['warning']}]{SYMBOLS['warning']}[/{COLORS['warning']}] {message}"
            panel = Panel(content, border_style=COLORS['warning'], box=box.ROUNDED, width=self.width)
        
        self.console.print(panel)
            
    def step_error(self, message: str, details: Optional[Dict[str, Any]] = None):
        """Log step error with optional tree details."""
        if details:
            tree = Tree(f"[{COLORS['error']}]{SYMBOLS['error']}[/{COLORS['error']}] {message}")
            for key, value in details.items():
                tree.add(f"[{COLORS['muted']}]{key}:[/{COLORS['muted']}] {value}")
            
            panel = Panel(tree, border_style=COLORS['error'], box=box.ROUNDED, width=self.width)
        else:
            content = f"[{COLORS['error']}]{SYMBOLS['error']}[/{COLORS['error']}] {message}"
            panel = Panel(content, border_style=COLORS['error'], box=box.ROUNDED, width=self.width)
        
        self.console.print(panel)

            
    def retry_attempt(self, attempt: int, max_attempts: int, reason: str = ""):
        """Log retry attempt with tree structure."""
        tree = Tree(f"[{COLORS['warning']}]{SYMBOLS['warning']} Retry attempt {attempt}/{max_attempts}[/{COLORS['warning']}]")
        if reason:
            tree.add(f"[{COLORS['muted']}]Reason: {reason}[/{COLORS['muted']}]")
        
        panel = Panel(tree, title="Retry", border_style=COLORS['warning'], box=box.ROUNDED, width=self.width)
        self.console.print(panel)
        
    def llm_call(self, provider: str, model: str = "", prompt_preview: str = ""):
        """Log LLM API call with tree structure."""
        tree = Tree(f"[bold {COLORS['highlight']}]{SYMBOLS['arrow']} Calling {provider}[/bold {COLORS['highlight']}]")
        if model:
            tree.add(f"[{COLORS['muted']}]Model: {model}[/{COLORS['muted']}]")
        if prompt_preview:
            tree.add(f"[{COLORS['muted']}]Prompt: {prompt_preview[:100]}...[/{COLORS['muted']}]")
            
        panel = Panel(tree, title="LLM API Call", border_style=COLORS['highlight'], box=box.ROUNDED, width=self.width)
        self.console.print(panel)
        
    def validation_result(self, success: bool, commands_count: int = 0, errors: List[str] = None):
        """Log validation results with tree structure."""
        style = 'success' if success else 'error'
        symbol = SYMBOLS['success'] if success else SYMBOLS['error']
        
        if success:
            tree = Tree(f"[{COLORS[style]}]{symbol} Validation successful[/{COLORS[style]}]")
            if commands_count > 0:
                tree.add(f"[{COLORS['muted']}]Generated {commands_count} valid commands[/{COLORS['muted']}]")
        else:
            tree = Tree(f"[{COLORS[style]}]{symbol} Validation failed[/{COLORS[style]}]")
            if errors:
                errors_branch = tree.add(f"[{COLORS['muted']}]Errors:[/{COLORS['muted']}]")
                for error in errors[:3]:
                    errors_branch.add(f"{SYMBOLS['bullet']} {error}")
                if len(errors) > 3:
                    errors_branch.add(f"{SYMBOLS['bullet']} ... and {len(errors) - 3} more errors")
                    
        panel = Panel(tree, title="Validation", border_style=COLORS[style], box=box.ROUNDED, width=self.width)
        self.console.print(panel)
        
    def strategy_analysis(self, strategy_name: str, complexity: Dict[str, Any]):
        """Log strategy analysis results in a table."""
        table = Table(title="Strategy Analysis", box=box.ROUNDED, width=self.width)
        table.add_column("Property", style=COLORS['muted'])
        table.add_column("Value", style="bold")
        
        table.add_row("Selected Strategy", f"[{COLORS['highlight']}]{strategy_name}[/{COLORS['highlight']}]")
        table.add_row("Complexity Level", str(complexity.get('complexity_level', 'unknown')))
        table.add_row("Requires Curves", str(complexity.get('requires_curves', False)))
        table.add_row("Estimated Commands", str(complexity.get('estimated_commands', 0)))
        table.add_row("Confidence Score", f"{complexity.get('confidence_score', 0):.2f}")
        
        self.console.print(table)
        
    def gcode_preview(self, gcode_lines: List[str], title: str = "Generated G-code"):
        """Display G-code preview in a table."""
        table = Table(title=title, box=box.ROUNDED, width=self.width)
        table.add_column("Line", style=COLORS['muted'], width=4)
        table.add_column("Command", style=COLORS['gcode'])
        
        for i, line in enumerate(gcode_lines[:10], 1):
            table.add_row(str(i), line)
            
        if len(gcode_lines) > 10:
            table.add_row("...", f"[{COLORS['muted']}]and {len(gcode_lines) - 10} more commands[/{COLORS['muted']}]")
            
        self.console.print(table)
        
    def plotter_status(self, connected: bool, port: str = "", commands_sent: int = 0, success_rate: float = 0.0):
        """Display plotter connection status with tree structure."""
        style = 'success' if connected else 'error'
        symbol = SYMBOLS['success'] if connected else SYMBOLS['error']
        
        if connected:
            tree = Tree(f"[{COLORS[style]}]{symbol} Connected to plotter[/{COLORS[style]}]")
            if port:
                tree.add(f"[{COLORS['muted']}]Port: {port}[/{COLORS['muted']}]")
            if commands_sent > 0:
                tree.add(f"[{COLORS['muted']}]Commands sent: {commands_sent}[/{COLORS['muted']}]")
                tree.add(f"[{COLORS['muted']}]Success rate: {success_rate:.1%}[/{COLORS['muted']}]")
        else:
            tree = Tree(f"[{COLORS[style]}]{symbol} Not connected to plotter[/{COLORS[style]}]")
            
        panel = Panel(tree, title="Plotter Status", border_style=COLORS[style], box=box.ROUNDED, width=self.width)
        self.console.print(panel)

    # ==================== STREAMING WORKFLOW METHODS ====================
    
    def stream_command(self, step: int, command: str, status: str = "pending"):
        """Display a single streamed command with status."""
        status_symbols = {
            'pending': SYMBOLS['pending'],
            'executing': SYMBOLS['running'],
            'success': SYMBOLS['success'],
            'error': SYMBOLS['error'],
            'skipped': SYMBOLS['arrow'],
        }
        status_colors = {
            'pending': COLORS['warning'],
            'executing': COLORS['info'],
            'success': COLORS['success'],
            'error': COLORS['error'],
            'skipped': COLORS['muted'],
        }
        symbol = status_symbols.get(status, SYMBOLS['pending'])
        color = status_colors.get(status, COLORS['muted'])
        
        content = f"[{color}]{symbol}[/{color}] [{COLORS['muted']}]Step {step:3d}:[/{COLORS['muted']}] [{COLORS['command']}]{command}[/{COLORS['command']}]"
        
        panel = Panel(content, box=box.ROUNDED, width=self.width, border_style=color)
        self.console.print(panel)
        
    def stream_start(self, title: str, prompt: str, max_steps: int = 0):
        """Display streaming workflow start with tree structure."""
        tree = Tree(f"[bold {COLORS['highlight']}]{title}[/bold {COLORS['highlight']}]")
        tree.add(f"[{COLORS['muted']}]Prompt:[/{COLORS['muted']}] [italic]{prompt}[/italic]")
        if max_steps > 0:
            tree.add(f"[{COLORS['muted']}]Max steps:[/{COLORS['muted']}] {max_steps}")
        
        panel = Panel(tree, title="Streaming Workflow", border_style=COLORS['highlight'], box=box.ROUNDED, width=self.width)
        self.console.print(panel)
        
    def stream_progress(self, current: int, total: int, command: str = ""):
        """Display streaming progress with visual bar."""
        self.progress_panel(current, total, f"Streaming: {command}" if command else "Streaming Progress")
        
    def command_executed(self, step: int, command: str, response: str = "", success: bool = True):
        """Log a command execution result."""
        symbol = SYMBOLS['success'] if success else SYMBOLS['error']
        color = COLORS['success'] if success else COLORS['error']
            
        content = f"[{color}]{symbol}[/{color}] [{COLORS['muted']}]#{step:3d}[/{COLORS['muted']}] [{COLORS['gcode']}]{command:20s}[/{COLORS['gcode']}] [{color}]{response}[/{color}]"
        
        panel = Panel(content, box=box.ROUNDED, width=self.width, border_style=color)
        self.console.print(panel)
        
    def plotter_command(self, command: str, response: str = "ok", success: bool = True):
        """Log a command sent to the plotter."""
        symbol = SYMBOLS['arrow'] if success else SYMBOLS['cross']
        color = COLORS['success'] if success else COLORS['error']
            
        content = f"[{color}]{symbol}[/{color}] [{COLORS['gcode']}]{command:25s}[/{COLORS['gcode']}] [{color}]{response}[/{color}]"
        
        panel = Panel(content, box=box.ROUNDED, width=self.width, border_style=color)
        self.console.print(panel)
        
    def commands_table(self, commands: List[Dict[str, Any]], title: str = "Commands"):
        """Display commands in a formatted table."""
        table = Table(title=title, box=box.ROUNDED, width=self.width, show_lines=False)
        table.add_column("#", style=COLORS['muted'], width=4)
        table.add_column("Command", style=COLORS['gcode'])
        table.add_column("X", style=COLORS['info'], justify="right", width=8)
        table.add_column("Y", style=COLORS['info'], justify="right", width=8)
        table.add_column("Status", width=8)
        
        for i, cmd in enumerate(commands[:15], 1):
            status = SYMBOLS['success'] if cmd.get('success', True) else SYMBOLS['error']
            table.add_row(
                str(i),
                cmd.get('command', ''),
                f"{cmd.get('x', ''):.2f}" if cmd.get('x') is not None else "-",
                f"{cmd.get('y', ''):.2f}" if cmd.get('y') is not None else "-",
                status
            )
            
        if len(commands) > 15:
            table.add_row("...", f"[{COLORS['muted']}]+{len(commands) - 15} more[/{COLORS['muted']}]", "", "", "")
            
        self.console.print(table)
        
    def execution_summary(self, total: int, success: int, failed: int, elapsed: float):
        """Display execution summary with tree structure."""
        success_rate = (success / total * 100) if total > 0 else 0
        
        tree = Tree(f"[bold {COLORS['info']}]Execution Summary[/bold {COLORS['info']}]")
        tree.add(f"[{COLORS['muted']}]Total Commands:[/{COLORS['muted']}] [bold]{total}[/bold]")
        tree.add(f"[{COLORS['success']}]Successful:[/{COLORS['success']}] [bold]{success}[/bold]")
        tree.add(f"[{COLORS['error']}]Failed:[/{COLORS['error']}] [bold]{failed}[/bold]")
        tree.add(f"[{COLORS['muted']}]Success Rate:[/{COLORS['muted']}] [bold {COLORS['success']}]{success_rate:.1f}%[/bold {COLORS['success']}]")
        tree.add(f"[{COLORS['muted']}]Elapsed Time:[/{COLORS['muted']}] [bold]{elapsed:.2f}s[/bold]")
        
        panel = Panel(tree, border_style=COLORS['info'], box=box.ROUNDED, width=self.width)
        self.console.print(panel)
        
    def reflection_prompt(self, attempt: int, max_attempts: int, error: str):
        """Display reflection/retry information with tree structure."""
        tree = Tree(f"[{COLORS['warning']}]{SYMBOLS['warning']} Reflection Attempt {attempt}/{max_attempts}[/{COLORS['warning']}]")
        error_branch = tree.add(f"[{COLORS['muted']}]Previous error:[/{COLORS['muted']}]")
        error_branch.add(f"[{COLORS['error']}]{error[:200]}{'...' if len(error) > 200 else ''}[/{COLORS['error']}]")
        
        panel = Panel(tree, title="LLM Reflection", border_style=COLORS['warning'], box=box.ROUNDED, width=self.width)
        self.console.print(panel)
        
    def ink_change(self, color: str, position: str = ""):
        """Display ink/pen change notification with tree structure."""
        tree = Tree(f"[bold {COLORS['highlight']}]{SYMBOLS['warning']} Ink Change Required[/bold {COLORS['highlight']}]")
        tree.add(f"[{COLORS['muted']}]New color:[/{COLORS['muted']}] [bold]{color}[/bold]")
        if position:
            tree.add(f"[{COLORS['muted']}]Position:[/{COLORS['muted']}] {position}")
        
        panel = Panel(tree, title="Pen Change", border_style=COLORS['highlight'], box=box.ROUNDED, width=self.width)
        self.console.print(panel)
        
    def pause_resume(self, paused: bool, reason: str = ""):
        """Display pause/resume notification."""
        if paused:
            tree = Tree(f"[{COLORS['warning']}]{SYMBOLS['pending']} Workflow Paused[/{COLORS['warning']}]")
            if reason:
                tree.add(f"[{COLORS['muted']}]Reason: {reason}[/{COLORS['muted']}]")
            border = COLORS['warning']
        else:
            tree = Tree(f"[{COLORS['success']}]{SYMBOLS['arrow']} Workflow Resumed[/{COLORS['success']}]")
            border = COLORS['success']
            
        panel = Panel(tree, border_style=border, box=box.ROUNDED, width=self.width)
        self.console.print(panel)
