"""The agent turn loop — deliberately simple (claw-code shape).

One user message in → up to ``max_turns`` LLM/tool cycles → final text out.
``on_event(kind, payload)`` streams progress to the surface (REPL prints,
headless ignores): kinds are "text", "tool_start", "tool_end", "error".
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, Optional

from . import protocol
from .session import AgentSession
from .tools import TOOLBOX, ToolContext, dispatch

KEEP_LAST = 30  # sliding-window compaction


async def run_turns(
    user_msg: str,
    ctx: ToolContext,
    provider: Any,
    max_turns: int = 12,
    on_event: Optional[Callable[[str, Any], None]] = None,
) -> str:
    emit = on_event or (lambda kind, payload: None)
    session: AgentSession = ctx.session
    system = protocol.build_system_prompt(TOOLBOX)
    session.add("user", user_msg)

    tool_specs = protocol.tools_to_openai(TOOLBOX)
    parse_retries = 0
    for _turn in range(max_turns):
        window = session.messages[-KEEP_LAST:]
        native = None
        try:
            native = await provider.acomplete_tools(system, window, tool_specs)
        except Exception as e:  # native path is best-effort; fall back
            emit("error", f"native tools failed, falling back: {e}")
        if native is not None:
            if "final" in native and "tool" not in native:
                kind, payload, args = "final", str(native.get("final") or ""), {}
            else:
                kind, payload, args = "tool", str(native.get("tool")), native.get("args") or {}
        else:
            prompt = protocol.messages_to_prompt(system, window)
            reply = await provider.acomplete(prompt)
            kind, payload, args = protocol.parse_reply(reply)

        if kind == "error":
            parse_retries += 1
            emit("error", payload)
            session.add("user", f"PROTOCOL ERROR: {payload}")
            if parse_retries > 2:
                session.add("assistant", reply)
                return f"(agent stopped: unparseable replies) last reply: {reply[:400]}"
            continue

        parse_retries = 0
        if kind == "final":
            session.add("assistant", payload)
            emit("text", payload)
            session.close(payload)
            return payload

        # tool call
        emit("tool_start", {"tool": payload, "args": args})
        session.add("assistant", json.dumps({"tool": payload, "args": args}))
        result = await dispatch(ctx, payload, args)
        emit("tool_end", {"tool": payload, "result": result})
        session.add("user", f"TOOL RESULT {payload}: {json.dumps(result)}")

    session.close("")
    return "(agent stopped: max turns reached)"
