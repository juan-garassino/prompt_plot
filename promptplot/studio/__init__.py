"""Studio — the native science-illustration design layer.

Briefs (per-subject guidelines under ``studio/<domain>/``) + the designer →
critic → synth loop that turns a brief into an implementable piece spec using
PromptPlot's own LLM providers. See STUDIO.md / DESIGN_RUBRIC.md / STYLES.md in
``promptplot/generative/`` for the governance canon.
"""

from __future__ import annotations

from .briefs import Brief, get_brief, list_briefs, load_briefs

__all__ = ["Brief", "get_brief", "list_briefs", "load_briefs"]
