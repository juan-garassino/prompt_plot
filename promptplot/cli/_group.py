"""CLI root group, shared helpers, and entry point.

Split out of the former monolithic cli.py during the v3.1 reorg.
"""

from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from ..config import PromptPlotConfig, get_config, load_config
from ..logger import WorkflowLogger

console = Console()
logger = WorkflowLogger(console)


# ===== sliced body (_get_config, cli group, _print_score, main) =====
def _get_config(config_path: Optional[str] = None) -> PromptPlotConfig:
    if config_path:
        return load_config(config_path)
    return get_config()


@click.group()
@click.version_option("3.1.0", prog_name="promptplot")
@click.option("--config", "config_path", default=None, help="Config file path")
@click.option("--debug", is_flag=True, help="Enable debug logging")
@click.pass_context
def cli(ctx, config_path, debug):
    """PromptPlot — LLM-driven pen plotter GCode generator."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = _get_config(config_path)
    ctx.obj["debug"] = debug


def _print_score(report):
    """Print a QualityReport as a formatted table."""
    table = Table(title="Quality Score")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    d = report.to_dict()
    for k, v in d.items():
        label = k.replace("_", " ").title()
        if k == "grade":
            color = {
                "A": "bold green",
                "B": "green",
                "C": "yellow",
                "D": "red",
                "F": "bold red",
            }.get(v, "white")
            table.add_row(label, f"[{color}]{v}[/{color}]")
        elif isinstance(v, float):
            table.add_row(label, f"{v:.3f}")
        else:
            table.add_row(label, str(v))
    console.print(table)


def main():
    """Entry point for promptplot CLI."""
    cli(obj={})


if __name__ == "__main__":
    main()
