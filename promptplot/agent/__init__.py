"""PromptPlot Agent — a self-sufficient agentic control layer.

The fourth controller (alongside File / in-process LLM workflow / Claude Code):
an LLM-agnostic chat loop over a typed toolbox that renders, scores, critiques
and (behind a confirm gate) plots. Works with any of the seven configured
providers; no external agent framework.
"""

from __future__ import annotations

from .loop import run_turns
from .session import AgentSession
from .tools import TOOLBOX, Tool, ToolContext

__all__ = ["run_turns", "AgentSession", "TOOLBOX", "Tool", "ToolContext"]
