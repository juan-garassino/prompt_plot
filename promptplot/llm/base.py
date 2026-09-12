"""LLM provider abstract base class and shared image helpers.

Split out of the former monolithic llm.py during the v3.1 reorg.
"""

import asyncio
import base64
import json as _json_mod
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional, List, AsyncGenerator


# ===== sliced body (LLMProviderError, LLMProvider, image helpers) below =====
class LLMProviderError(Exception):
    def __init__(self, message: str, provider: str = "unknown"):
        self.provider = provider
        super().__init__(message)


class LLMProvider(ABC):
    """Abstract base for LLM providers."""

    def __init__(self, timeout: int = 30, temperature: float = 0.1):
        self.timeout = timeout
        self.temperature = temperature

    @property
    @abstractmethod
    def provider_name(self) -> str: ...

    @abstractmethod
    async def acomplete(self, prompt: str) -> str: ...

    def complete(self, prompt: str) -> str:
        return asyncio.get_event_loop().run_until_complete(self.acomplete(prompt))

    async def acomplete_multimodal(
        self, prompt: str, image_paths: Optional[List[Path]] = None
    ) -> str:
        """Complete with optional image inputs. Falls back to text-only by default."""
        return await self.acomplete(prompt)

    async def astream_commands(self, prompt: str) -> AsyncGenerator[Any, None]:
        """Stream GCode commands as the LLM generates them (one JSON per line).

        Default implementation: single blocking call, yields commands after completion.
        Override in providers that support true streaming.
        """
        from ..models import GCodeCommand

        raw = await self.acomplete(prompt)
        for line in raw.splitlines():
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    d = _json_mod.loads(line)
                    cmd = d.get("command", "")
                    if cmd:
                        yield GCodeCommand(
                            command=cmd,
                            x=d.get("x"),
                            y=d.get("y"),
                            f=d.get("f"),
                            s=d.get("s"),
                        )
                except Exception:
                    pass


def _load_image_base64(path: Path) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _image_media_type(path: Path) -> str:
    suffix = path.suffix.lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(suffix, "image/png")
