"""Provider-agnostic tool calling.

Universal JSON envelope that works with every configured provider through the
plain ``acomplete`` text interface: the model must answer with EXACTLY ONE of

    {"tool": "<name>", "args": {...}}
    {"final": "<answer to the user>"}

A native function-calling fast path per provider can be added later; the
envelope is the portable baseline (works with Ollama and friends).
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from .tools import Tool

SYSTEM_TEMPLATE = """You are PromptPlot Agent, an art director + operator for a pen plotter.
You control the machine ONLY through tools. Iterate: render, check the score,
adjust parameters, render again. Prefer small seeds and few colors unless asked.
Never invent file paths — use the paths returned by tools.

TOOLS
{tool_block}

PROTOCOL — your entire reply must be a single JSON object, nothing else:
  {{"tool": "<tool name>", "args": {{...}}}}     to call a tool
  {{"final": "<your answer to the user>"}}       when you are done
Do not wrap the JSON in markdown fences. Do not add commentary outside the JSON.
"""


def build_system_prompt(tools: List[Tool]) -> str:
    lines = []
    for t in tools:
        params = ", ".join(f"{k}: {v.get('type', 'any')}" for k, v in t.params.items()) or "none"
        lines.append(f"- {t.name}({params}) — {t.description}")
    return SYSTEM_TEMPLATE.format(tool_block="\n".join(lines))


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def parse_reply(text: str) -> Tuple[str, Any, Dict[str, Any]]:
    """Returns ("tool", name, args) | ("final", text, {}) | ("error", msg, {})."""
    obj = _extract_json(text)
    if obj is None:
        return ("error", "reply was not a single JSON object; follow the PROTOCOL exactly", {})
    if "final" in obj:
        return ("final", str(obj["final"]), {})
    if "tool" in obj:
        args = obj.get("args") or {}
        if not isinstance(args, dict):
            return ("error", '"args" must be a JSON object', {})
        return ("tool", str(obj["tool"]), args)
    return ("error", 'JSON must contain either "tool" or "final"', {})


def messages_to_prompt(system: str, messages: List[Dict[str, str]]) -> str:
    """Flatten chat history for providers that only expose text completion."""
    parts = [system, ""]
    for m in messages:
        role = m["role"].upper()
        parts.append(f"[{role}]\n{m['content']}\n")
    parts.append("[ASSISTANT]\n")
    return "\n".join(parts)
