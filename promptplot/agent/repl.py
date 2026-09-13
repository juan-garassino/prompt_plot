"""Interactive REPL and headless one-shot surface for the agent."""

from __future__ import annotations

import asyncio
from typing import Optional

from rich.console import Console

from ..config import PromptPlotConfig
from ..llm import create_llm_provider, get_llm_provider
from .loop import run_turns
from .session import AgentSession
from .tools import ToolContext

console = Console()


def _make_provider(config: PromptPlotConfig, provider: Optional[str], model: Optional[str]):
    if provider:
        kwargs = {"model": model} if model else {}
        return create_llm_provider(provider, **kwargs)
    return get_llm_provider(config.llm)


def _on_event(kind: str, payload) -> None:
    if kind == "tool_start":
        args = ", ".join(f"{k}={v!r}" for k, v in payload["args"].items())
        console.print(f"[dim]→ {payload['tool']}({args[:120]})[/dim]")
    elif kind == "tool_end":
        result = payload["result"]
        if "error" in result:
            console.print(f"[red]  ✗ {result['error'][:200]}[/red]")
        else:
            brief = {
                k: v for k, v in result.items() if k in ("png_path", "score", "ok", "generators")
            }
            console.print(f"[dim]  ✓ {str(brief)[:200]}[/dim]")
    elif kind == "error":
        console.print(f"[yellow]  protocol retry: {str(payload)[:120]}[/yellow]")


def run_once(
    prompt: str,
    config: PromptPlotConfig,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    max_turns: int = 12,
    session_id: Optional[str] = None,
    yes_plot: bool = False,
) -> str:
    llm = _make_provider(config, provider, model)
    session = AgentSession(session_id)
    ctx = ToolContext(config=config, session=session, provider=llm, yes_plot=yes_plot)
    console.print(f"[dim]session {session.id} · provider {llm.provider_name}[/dim]")
    answer = asyncio.run(run_turns(prompt, ctx, llm, max_turns=max_turns, on_event=_on_event))
    console.print(answer)
    return answer


def run_repl(
    config: PromptPlotConfig,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    max_turns: int = 12,
    session_id: Optional[str] = None,
    yes_plot: bool = False,
) -> None:
    llm = _make_provider(config, provider, model)
    session = AgentSession(session_id)
    ctx = ToolContext(
        config=config,
        session=session,
        provider=llm,
        yes_plot=yes_plot,
        approve=lambda name: console.input(
            f"[bold red]{name} touches hardware — proceed? \\[y/N] [/bold red]"
        )
        .strip()
        .lower()
        == "y",
    )
    console.print(
        f"[bold]PromptPlot Agent[/bold] · session {session.id} · "
        f"provider {llm.provider_name} · /help for commands"
    )
    while True:
        try:
            user = console.input("[bold cyan]plot> [/bold cyan]").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user:
            continue
        if user in ("/quit", "/exit"):
            break
        if user == "/help":
            console.print("/tools  /session  /renders  /quit — anything else goes to the agent")
            continue
        if user == "/tools":
            from .tools import TOOLBOX

            for t in TOOLBOX:
                console.print(f"[cyan]{t.name}[/cyan] [{t.tier}] — {t.description}")
            continue
        if user == "/session":
            console.print(f"id {session.id} · dir {session.dir} · {len(session.messages)} messages")
            continue
        if user == "/renders":
            for r in session.list_renders():
                console.print(r)
            continue
        answer = asyncio.run(run_turns(user, ctx, llm, max_turns=max_turns, on_event=_on_event))
        console.print(f"\n{answer}\n")
    report = session.close()
    console.print(f"[dim]report: {report}[/dim]")
