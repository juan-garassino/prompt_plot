"""Concrete LLM provider implementations and the provider registry/factory.

Split out of the former monolithic llm.py during the v3.1 reorg.
"""

import os
import asyncio
import base64
import json as _json_mod
from pathlib import Path
from typing import Any, Optional, List, AsyncGenerator

import httpx

try:
    import openai as _openai

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import anthropic as _anthropic

    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    import google.generativeai as _genai

    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

from ..config import LLMConfig
from .base import (
    LLMProvider,
    LLMProviderError,
    _load_image_base64,
    _image_media_type,
)
from .prompts import _PRIMITIVES_PROMPT_BLOCK


# ===== sliced body (provider classes, _PROVIDERS, factory functions) below =====
class AzureOpenAIProvider(LLMProvider):
    def __init__(
        self,
        model: str = "gpt-4o",
        deployment_name: str = "gpt-4o-gs",
        api_key: Optional[str] = None,
        api_version: Optional[str] = None,
        azure_endpoint: Optional[str] = None,
        timeout: int = 1220,
        temperature: float = 0.1,
    ):
        super().__init__(timeout, temperature)
        self.model = model
        self.deployment_name = deployment_name
        self.api_key = api_key or os.environ.get("GPT4_API_KEY")
        self.api_version = api_version or os.environ.get("GPT4_API_VERSION")
        self.azure_endpoint = azure_endpoint or os.environ.get("GPT4_ENDPOINT")
        if not all([self.api_key, self.api_version, self.azure_endpoint]):
            raise LLMProviderError("Missing Azure OpenAI config", self.provider_name)

    @property
    def provider_name(self) -> str:
        return "azure_openai"

    async def acomplete(self, prompt: str) -> str:
        if not OPENAI_AVAILABLE:
            raise LLMProviderError("pip install openai", self.provider_name)
        client = _openai.AsyncAzureOpenAI(
            api_key=self.api_key,
            api_version=self.api_version,
            azure_endpoint=self.azure_endpoint,
        )
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=self.deployment_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
            ),
            timeout=self.timeout,
        )
        return response.choices[0].message.content

    async def acomplete_multimodal(
        self, prompt: str, image_paths: Optional[List[Path]] = None
    ) -> str:
        if not image_paths or not OPENAI_AVAILABLE:
            return await self.acomplete(prompt)
        try:
            client = _openai.AsyncAzureOpenAI(
                api_key=self.api_key,
                api_version=self.api_version,
                azure_endpoint=self.azure_endpoint,
            )
            content = [{"type": "text", "text": prompt}]
            for p in image_paths:
                b64 = _load_image_base64(p)
                mt = _image_media_type(p)
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mt};base64,{b64}"},
                    }
                )
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=self.deployment_name,
                    messages=[{"role": "user", "content": content}],
                    temperature=self.temperature,
                ),
                timeout=self.timeout,
            )
            return response.choices[0].message.content
        except Exception:
            return await self.acomplete(prompt)


class OllamaProvider(LLMProvider):
    def __init__(
        self,
        model: str = "llama3.2:3b",
        request_timeout: int = 10000,
        base_url: Optional[str] = None,
        temperature: float = 0.1,
        vision_model: str = "llama3.2-vision:11b",
    ):
        super().__init__(timeout=request_timeout // 1000, temperature=temperature)
        self.model = model
        self.request_timeout = request_timeout
        self.base_url = (base_url or "http://localhost:11434").rstrip("/")
        self.vision_model = vision_model

    @property
    def provider_name(self) -> str:
        return "ollama"

    async def acomplete(self, prompt: str) -> str:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": self.temperature},
                },
            )
            response.raise_for_status()
            return response.json()["response"]

    async def acomplete_multimodal(
        self, prompt: str, image_paths: Optional[List[Path]] = None
    ) -> str:
        if not image_paths:
            return await self.acomplete(prompt)
        try:
            images = [_load_image_base64(p) for p in image_paths]
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.vision_model,
                        "prompt": prompt,
                        "images": images,
                        "stream": False,
                        "options": {"temperature": self.temperature},
                    },
                )
                response.raise_for_status()
                return response.json()["response"]
        except Exception:
            return await self.acomplete(prompt)


_OPENAI_SYSTEM_PROMPT = (
    """\
You are an expert GCode artist for pen plotters. You create detailed, dense pen drawings.

CORE RULES:
- Output ONLY valid JSON with a "commands" array. No commentary.
- Use G0 for travel (pen up), G1 for drawing (pen down), M3 S1000 for pen down, M5 for pen up.
- Approximate ALL curves with short G1 line segments (3-8mm each). Never use G2/G3.

PEN PLOTTER REALITY — THIS IS CRITICAL:
- A pen plotter draws with a physical pen on paper. Each stroke is a continuous line.
- To start a new line or shape, you MUST lift the pen (M5), travel (G0), then lower it (M3).
- Clean drawings require MANY pen lifts. Each shape outline, each hatching line, each detail
  is a SEPARATE stroke: M5 → G0 to start → M3 → G1 segments → M5.
- Do NOT draw everything in one continuous stroke. That creates messy, overlapping lines.
- A good drawing has 15-40 distinct strokes (pen lift cycles), not 3-5 giant ones.

SHADING AND TEXTURE:
- To shade or fill an area, use parallel hatching lines: many short parallel strokes
  spaced 2-5mm apart. Each hatching line is its own stroke (pen up, move, pen down, draw, pen up).
- Cross-hatching: overlay two sets of parallel lines at different angles for darker areas.
- Stippling: many tiny dots or very short strokes for soft gradients.
- Vary line density to create contrast: tight lines (2-3mm apart) for dark areas,
  wide spacing (8-10mm) for light areas, empty space for highlights.

DRAWING TECHNIQUE:
- Straight lines: single G1 segment per edge. Keep lines CLEAN and precise.
- Curves and arcs: 16-30 short G1 segments (3-8mm each) to approximate smooth shapes.
- Circles: at least 16 G1 segments. Larger circles need 24-36 segments.
- Each shape should be a CLOSED outline (return to start point) drawn as one stroke.
- Then add fill/hatching as SEPARATE strokes inside the shape.

DENSITY REQUIREMENTS:
- Simple subjects (one shape): 40-80 commands minimum.
- Moderate scenes (2-3 elements): 100-200 commands.
- Complex/detailed scenes (4+ elements): 250-500 commands.
- NEVER generate fewer than 40 commands. Sparse output looks terrible on paper.

COMPOSITION:
- Use the FULL canvas. Place elements across all quadrants — top, bottom, left, right.
- Fill at least 60-80% of the drawable area. Do not cluster everything in the center.
- Create visual contrast: some areas dense with hatching, others left open.
- Layer elements at different scales — large structural shapes with smaller decorative ones.

"""
    + _PRIMITIVES_PROMPT_BLOCK
    + """

When to use primitives vs raw GCode:
- Use PRIMITIVES for: circles, ellipses, regular polygons, hatching, cross-hatching, spirals, stipple fills
- Use raw G0/G1 for: freeform/organic lines, irregular shapes, text-like strokes, unique artistic lines
- You can MIX both freely in the same commands array.
"""
)


class OpenAIProvider(LLMProvider):
    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
        timeout: int = 120,
        temperature: float = 0.1,
        max_tokens: int = 16384,
    ):
        super().__init__(timeout, temperature)
        self.model = model
        self.max_tokens = max_tokens
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise LLMProviderError("Missing OPENAI_API_KEY", self.provider_name)

    @property
    def provider_name(self) -> str:
        return "openai"

    async def acomplete(self, prompt: str) -> str:
        if not OPENAI_AVAILABLE:
            raise LLMProviderError("pip install openai", self.provider_name)
        client = _openai.AsyncOpenAI(api_key=self.api_key)
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": _OPENAI_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            ),
            timeout=self.timeout,
        )
        return response.choices[0].message.content

    async def acomplete_multimodal(
        self, prompt: str, image_paths: Optional[List[Path]] = None
    ) -> str:
        if not image_paths or not OPENAI_AVAILABLE:
            return await self.acomplete(prompt)
        try:
            client = _openai.AsyncOpenAI(api_key=self.api_key)
            content = [{"type": "text", "text": prompt}]
            for p in image_paths:
                b64 = _load_image_base64(p)
                mt = _image_media_type(p)
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mt};base64,{b64}"},
                    }
                )
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": _OPENAI_SYSTEM_PROMPT},
                        {"role": "user", "content": content},
                    ],
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                ),
                timeout=self.timeout,
            )
            return response.choices[0].message.content
        except Exception:
            return await self.acomplete(prompt)


class GeminiProvider(LLMProvider):
    def __init__(
        self,
        model: str = "models/gemini-1.5-flash",
        api_key: Optional[str] = None,
        timeout: int = 120,
        temperature: float = 0.1,
    ):
        super().__init__(timeout, temperature)
        self.model = model
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        if not self.api_key:
            raise LLMProviderError("Missing GOOGLE_API_KEY", self.provider_name)

    @property
    def provider_name(self) -> str:
        return "gemini"

    async def acomplete(self, prompt: str) -> str:
        if not GEMINI_AVAILABLE:
            raise LLMProviderError("pip install google-generativeai", self.provider_name)
        _genai.configure(api_key=self.api_key)
        gen_model = _genai.GenerativeModel(self.model)
        response = await asyncio.to_thread(
            gen_model.generate_content,
            prompt,
            generation_config=_genai.types.GenerationConfig(temperature=self.temperature),
        )
        return response.text

    async def acomplete_multimodal(
        self, prompt: str, image_paths: Optional[List[Path]] = None
    ) -> str:
        if not image_paths or not GEMINI_AVAILABLE:
            return await self.acomplete(prompt)
        try:
            _genai.configure(api_key=self.api_key)
            gen_model = _genai.GenerativeModel(self.model)
            parts = [prompt]
            for p in image_paths:
                img_data = _load_image_base64(p)
                mt = _image_media_type(p)
                parts.append({"mime_type": mt, "data": base64.b64decode(img_data)})
            response = await asyncio.to_thread(
                gen_model.generate_content,
                parts,
                generation_config=_genai.types.GenerationConfig(temperature=self.temperature),
            )
            return response.text
        except Exception:
            return await self.acomplete(prompt)


class OpenRouterProvider(LLMProvider):
    """OpenRouter — OpenAI-compatible API aggregating hundreds of models."""

    def __init__(
        self,
        model: str = "nvidia/llama-3.1-nemotron-70b-instruct",
        api_key: Optional[str] = None,
        timeout: int = 120,
        temperature: float = 0.1,
        max_tokens: int = 16384,
    ):
        super().__init__(timeout, temperature)
        self.model = model
        self.max_tokens = max_tokens
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not self.api_key:
            raise LLMProviderError("Missing OPENROUTER_API_KEY", self.provider_name)

    @property
    def provider_name(self) -> str:
        return "openrouter"

    async def acomplete(self, prompt: str) -> str:
        if not OPENAI_AVAILABLE:
            raise LLMProviderError("pip install openai", self.provider_name)
        client = _openai.AsyncOpenAI(
            api_key=self.api_key,
            base_url="https://openrouter.ai/api/v1",
        )
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": _OPENAI_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            ),
            timeout=self.timeout,
        )
        if not response.choices:
            raise LLMProviderError("Empty choices in OpenRouter response", self.provider_name)
        return response.choices[0].message.content

    async def astream_commands(self, prompt: str) -> AsyncGenerator[Any, None]:
        """True streaming: parse GCodeCommands line-by-line as tokens arrive."""
        if not OPENAI_AVAILABLE:
            raise LLMProviderError("pip install openai", self.provider_name)
        from ..models import GCodeCommand

        client = _openai.AsyncOpenAI(
            api_key=self.api_key,
            base_url="https://openrouter.ai/api/v1",
        )
        stream = await client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stream=True,
        )
        buffer = ""
        async for chunk in stream:
            delta = (chunk.choices[0].delta.content or "") if chunk.choices else ""
            buffer += delta
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if line.startswith("{") and line.endswith("}"):
                    try:
                        d = _json_mod.loads(line)
                        cmd = d.get("command", "")
                        if cmd:
                            yield GCodeCommand(
                                command=cmd,
                                x=float(d["x"]) if "x" in d else None,
                                y=float(d["y"]) if "y" in d else None,
                                f=int(d["f"]) if "f" in d else None,
                                s=int(d["s"]) if "s" in d else None,
                            )
                    except Exception:
                        pass


class NvidiaProvider(LLMProvider):
    """NVIDIA NIM — OpenAI-compatible API for NVIDIA-hosted models."""

    def __init__(
        self,
        model: str = "nvidia/llama-3.1-nemotron-70b-instruct",
        api_key: Optional[str] = None,
        timeout: int = 120,
        temperature: float = 0.1,
        max_tokens: int = 16384,
    ):
        super().__init__(timeout, temperature)
        self.model = model
        self.max_tokens = max_tokens
        self.api_key = api_key or os.environ.get("NVIDIA_API_KEY")
        if not self.api_key:
            raise LLMProviderError("Missing NVIDIA_API_KEY", self.provider_name)

    @property
    def provider_name(self) -> str:
        return "nvidia"

    async def acomplete(self, prompt: str) -> str:
        if not OPENAI_AVAILABLE:
            raise LLMProviderError("pip install openai", self.provider_name)
        client = _openai.AsyncOpenAI(
            api_key=self.api_key,
            base_url="https://integrate.api.nvidia.com/v1",
        )
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": _OPENAI_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            ),
            timeout=self.timeout,
        )
        return response.choices[0].message.content

    async def astream_commands(self, prompt: str) -> AsyncGenerator[Any, None]:
        """True streaming: parse GCodeCommands line-by-line as tokens arrive."""
        if not OPENAI_AVAILABLE:
            raise LLMProviderError("pip install openai", self.provider_name)
        from ..models import GCodeCommand

        client = _openai.AsyncOpenAI(
            api_key=self.api_key,
            base_url="https://integrate.api.nvidia.com/v1",
        )
        stream = await client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stream=True,
        )
        buffer = ""
        async for chunk in stream:
            delta = (chunk.choices[0].delta.content or "") if chunk.choices else ""
            buffer += delta
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if line.startswith("{") and line.endswith("}"):
                    try:
                        d = _json_mod.loads(line)
                        cmd = d.get("command", "")
                        if cmd:
                            yield GCodeCommand(
                                command=cmd,
                                x=float(d["x"]) if "x" in d else None,
                                y=float(d["y"]) if "y" in d else None,
                                f=int(d["f"]) if "f" in d else None,
                                s=int(d["s"]) if "s" in d else None,
                            )
                    except Exception:
                        pass


class AnthropicProvider(LLMProvider):
    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        api_key: Optional[str] = None,
        timeout: int = 120,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ):
        super().__init__(timeout, temperature)
        self.model = model
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.max_tokens = max_tokens
        if not self.api_key:
            raise LLMProviderError("Missing ANTHROPIC_API_KEY", self.provider_name)

    @property
    def provider_name(self) -> str:
        return "anthropic"

    async def acomplete(self, prompt: str) -> str:
        if not ANTHROPIC_AVAILABLE:
            raise LLMProviderError("pip install anthropic", self.provider_name)
        client = _anthropic.AsyncAnthropic(api_key=self.api_key)
        response = await asyncio.wait_for(
            client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
            ),
            timeout=self.timeout,
        )
        return response.content[0].text

    async def acomplete_multimodal(
        self, prompt: str, image_paths: Optional[List[Path]] = None
    ) -> str:
        if not image_paths or not ANTHROPIC_AVAILABLE:
            return await self.acomplete(prompt)
        try:
            client = _anthropic.AsyncAnthropic(api_key=self.api_key)
            content = []
            for p in image_paths:
                b64 = _load_image_base64(p)
                mt = _image_media_type(p)
                content.append(
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": mt, "data": b64},
                    }
                )
            content.append({"type": "text", "text": prompt})
            response = await asyncio.wait_for(
                client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    messages=[{"role": "user", "content": content}],
                    temperature=self.temperature,
                ),
                timeout=self.timeout,
            )
            return response.content[0].text
        except Exception:
            return await self.acomplete(prompt)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_PROVIDERS = {
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
    "azure_openai": AzureOpenAIProvider,
    "ollama": OllamaProvider,
    "anthropic": AnthropicProvider,
    "openrouter": OpenRouterProvider,
    "nvidia": NvidiaProvider,
}


def create_llm_provider(provider_type: str, **kwargs) -> LLMProvider:
    if provider_type not in _PROVIDERS:
        raise ValueError(f"Unknown provider: {provider_type}. Options: {list(_PROVIDERS.keys())}")
    return _PROVIDERS[provider_type](**kwargs)


def get_llm_provider(llm_config: LLMConfig) -> LLMProvider:
    p = llm_config.default_provider
    temp = llm_config.temperature
    if p == "azure_openai":
        return AzureOpenAIProvider(
            model=llm_config.azure_model,
            deployment_name=llm_config.azure_deployment_name,
            api_key=llm_config.azure_api_key,
            api_version=llm_config.azure_api_version,
            azure_endpoint=llm_config.azure_endpoint,
            timeout=llm_config.azure_timeout,
            temperature=temp,
        )
    elif p == "ollama":
        return OllamaProvider(
            model=llm_config.ollama_model,
            request_timeout=llm_config.ollama_timeout,
            base_url=llm_config.ollama_base_url,
            temperature=temp,
            vision_model=llm_config.ollama_vision_model,
        )
    elif p == "openai":
        return OpenAIProvider(
            model=llm_config.openai_model,
            api_key=llm_config.openai_api_key,
            timeout=llm_config.openai_timeout,
            temperature=temp,
        )
    elif p == "gemini":
        return GeminiProvider(
            model=llm_config.gemini_model,
            api_key=llm_config.gemini_api_key,
            timeout=llm_config.gemini_timeout,
            temperature=temp,
        )
    elif p == "anthropic":
        return AnthropicProvider(
            model=llm_config.anthropic_model,
            api_key=llm_config.anthropic_api_key,
            timeout=llm_config.anthropic_timeout,
            temperature=temp,
            max_tokens=llm_config.anthropic_max_tokens,
        )
    elif p == "openrouter":
        return OpenRouterProvider(
            model=llm_config.openrouter_model,
            api_key=llm_config.openrouter_api_key,
            timeout=llm_config.openrouter_timeout,
            temperature=temp,
        )
    elif p == "nvidia":
        return NvidiaProvider(
            model=llm_config.nvidia_model,
            api_key=llm_config.nvidia_api_key,
            timeout=llm_config.nvidia_timeout,
            temperature=temp,
        )
    raise ValueError(f"Unknown provider: {p}")
