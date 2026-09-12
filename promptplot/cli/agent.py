"""`promptplot agent` — the self-sufficient agentic controller."""

from __future__ import annotations

import click

from ._group import cli, _get_config


@cli.command()
@click.option("-p", "--prompt", default=None, help="Headless one-shot prompt (omit for REPL)")
@click.option(
    "--provider",
    default=None,
    help="LLM provider (openai|azure|anthropic|gemini|ollama|openrouter|nvidia)",
)
@click.option("--model", default=None, help="Model override for the provider")
@click.option("--max-turns", default=12, show_default=True, help="Max LLM/tool cycles per message")
@click.option("--session", "session_id", default=None, help="Resume an existing session id")
@click.option("--yes-plot", is_flag=True, help="Allow hardware tools without interactive confirm")
def agent(prompt, provider, model, max_turns, session_id, yes_plot):
    """Chat with PromptPlot's own agent: it renders, scores and iterates via tools."""
    from ..agent.repl import run_once, run_repl

    config = _get_config()
    if prompt:
        run_once(
            prompt,
            config,
            provider=provider,
            model=model,
            max_turns=max_turns,
            session_id=session_id,
            yes_plot=yes_plot,
        )
    else:
        run_repl(
            config,
            provider=provider,
            model=model,
            max_turns=max_turns,
            session_id=session_id,
            yes_plot=yes_plot,
        )


@cli.command("mcp")
def mcp_serve():
    """Serve the PromptPlot toolbox over MCP stdio (for Claude Desktop & other clients)."""
    try:
        from ..agent.mcp_server import main as mcp_main
    except ImportError as e:
        raise click.ClickException(f"MCP SDK not installed: {e}. Try: pip install mcp")
    mcp_main()
