"""`promptplot studio` — the native science-illustration design layer."""

from __future__ import annotations

import click

from ._group import cli, console, _get_config


@cli.group()
def studio():
    """Browse design briefs and run the designer→critic→synth loop."""


@studio.command("list")
@click.option("--domain", default=None, help="Only one studio domain (e.g. nets)")
def studio_list(domain):
    """List all design briefs (studio/<domain>/*.md)."""
    from ..studio.briefs import list_briefs

    rows = list_briefs(domain=domain)
    if not rows:
        console.print("[yellow]No briefs found.[/yellow]")
        return
    from rich.table import Table

    table = Table(title="Studio briefs")
    for col in ("domain", "slug", "title", "tagline", "status"):
        table.add_column(col)
    for r in rows:
        table.add_row(r["domain"], r["slug"], r["title"], r["tagline"], r["status"][:60])
    console.print(table)


@studio.command("brief")
@click.argument("slug")
@click.option("--domain", default=None, help="Studio domain to search (default: all)")
def studio_brief(slug, domain):
    """Show one brief rendered as markdown."""
    from rich.markdown import Markdown

    from ..studio.briefs import get_brief

    try:
        b = get_brief(slug, domain=domain)
    except KeyError as e:
        raise click.ClickException(str(e))
    console.print(Markdown(b.to_context()))


@studio.command("design")
@click.argument("slug")
@click.option("--style", default="bauhaus", show_default=True, help="Style canon (STYLES.md)")
@click.option("--mode", type=click.Choice(["params", "code"]), default="params", show_default=True)
@click.option("--rounds", default=3, show_default=True)
@click.option("--provider", "provider_name", default=None, help="LLM provider (openai|anthropic|ollama|nvidia|...)")
@click.option("--model", default=None, help="Model override")
@click.option("--paper", default="a4", show_default=True)
@click.option("--orientation", default="portrait", show_default=True)
@click.option("--out", "out_dir", default=None, help="Output dir (default: studio/<domain>/<slug>/)")
def studio_design(slug, style, mode, rounds, provider_name, model, paper, orientation, out_dir):
    """Run the native design loop for a brief: designer → render → critic → synth."""
    from pathlib import Path

    from ..agent.repl import _make_provider
    from ..studio.briefs import get_brief
    from ..studio.loop import run_design_loop_sync

    config = _get_config()
    try:
        brief = get_brief(slug)
    except KeyError as e:
        raise click.ClickException(str(e))
    provider = _make_provider(config, provider_name, model)
    console.print(
        f"[bold]studio design[/bold] {brief.title} — style={style} mode={mode} "
        f"rounds={rounds} provider={getattr(provider, 'provider_name', '?')}"
    )
    res = run_design_loop_sync(
        slug,
        provider,
        style=style,
        mode=mode,
        rounds=rounds,
        out_dir=Path(out_dir) if out_dir else None,
        config=config,
        brief=brief,
        paper=paper,
        orientation=orientation,
    )
    for r in res.rounds:
        mark = {"pass": "[green]PASS[/green]", "revise": "[yellow]REVISE[/yellow]"}.get(r.verdict, "[red]FAIL[/red]")
        console.print(f"  r{r.index:02d} {mark}  {r.critique.get('one_line', r.instruction)[:90]}")
    best = res.best
    if best is not None and best.render_path is not None:
        console.print(f"[bold]best:[/bold] r{best.index:02d} → {best.render_path}")
    console.print(f"[bold]proposal:[/bold] {res.out_dir / 'final' / 'PROPOSAL.md'}")
