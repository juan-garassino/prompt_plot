"""Agent session: transcript, artifacts and resume.

Layout (one directory per session, autocontext-style durable artifacts):

    ~/.promptplot/agent_sessions/<id>/
        transcript.json   # full message list — reload to resume
        trace.jsonl       # append-only tool-call log
        renders/          # every png/gcode the agent produced
        report.md         # written on close()
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

SESSIONS_DIR = Path.home() / ".promptplot" / "agent_sessions"


class AgentSession:
    def __init__(self, session_id: Optional[str] = None, base_dir: Optional[Path] = None):
        self.id = session_id or uuid.uuid4().hex[:10]
        self.dir = (base_dir or SESSIONS_DIR) / self.id
        self.renders_dir = self.dir / "renders"
        self.renders_dir.mkdir(parents=True, exist_ok=True)
        self.messages: List[Dict[str, Any]] = []
        self._load()

    # -- transcript -------------------------------------------------------
    def _transcript_path(self) -> Path:
        return self.dir / "transcript.json"

    def _load(self) -> None:
        p = self._transcript_path()
        if p.exists():
            self.messages = json.loads(p.read_text())

    def save(self) -> None:
        self._transcript_path().write_text(json.dumps(self.messages, indent=1))

    def add(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})
        self.save()

    # -- trace ------------------------------------------------------------
    def trace(self, tool: str, args: Dict[str, Any], summary: str, seconds: float) -> None:
        entry = {
            "t": time.time(),
            "tool": tool,
            "args": args,
            "summary": summary[:400],
            "seconds": round(seconds, 2),
        }
        with open(self.dir / "trace.jsonl", "a") as fh:
            fh.write(json.dumps(entry) + "\n")

    # -- artifacts ---------------------------------------------------------
    def render_path(self, stem: str, ext: str) -> Path:
        n = len(list(self.renders_dir.glob("*"))) + 1
        return self.renders_dir / f"{n:03d}_{stem}.{ext}"

    def list_renders(self) -> List[str]:
        return sorted(str(p) for p in self.renders_dir.glob("*"))

    # -- report -----------------------------------------------------------
    def close(self, final_text: str = "") -> Path:
        lines = [f"# PromptPlot agent session {self.id}", ""]
        user_turns = [m["content"] for m in self.messages if m["role"] == "user"]
        if user_turns:
            lines += ["## Prompts", *[f"- {u[:200]}" for u in user_turns], ""]
        renders = self.list_renders()
        if renders:
            lines += ["## Artifacts", *[f"- {r}" for r in renders], ""]
        if final_text:
            lines += ["## Final answer", "", final_text]
        p = self.dir / "report.md"
        p.write_text("\n".join(lines))
        return p
