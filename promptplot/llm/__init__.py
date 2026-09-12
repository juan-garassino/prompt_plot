"""LLM package — providers + prompt builders.

Re-exports the full public surface that used to live in the flat ``llm.py``
so existing imports (``from promptplot.llm import X``) keep working unchanged.
"""

from .base import (
    LLMProvider,
    LLMProviderError,
    _load_image_base64,
    _image_media_type,
)
from .providers import (
    AzureOpenAIProvider,
    OllamaProvider,
    OpenAIProvider,
    GeminiProvider,
    OpenRouterProvider,
    NvidiaProvider,
    AnthropicProvider,
    create_llm_provider,
    get_llm_provider,
    OPENAI_AVAILABLE,
    ANTHROPIC_AVAILABLE,
    GEMINI_AVAILABLE,
    _PROVIDERS,
)
from .prompts import (
    build_gcode_prompt,
    build_preview_reflection_prompt,
    build_reflection_prompt,
    build_next_command_prompt,
    build_composition_plan_prompt,
    build_region_worker_prompt,
    classify_creative_mode,
    estimate_complexity,
    STYLE_PRESETS,
    FEW_SHOT_EXAMPLES,
    _PRIMITIVES_PROMPT_BLOCK,
)

__all__ = [
    "LLMProvider",
    "LLMProviderError",
    "AzureOpenAIProvider",
    "OllamaProvider",
    "OpenAIProvider",
    "GeminiProvider",
    "OpenRouterProvider",
    "NvidiaProvider",
    "AnthropicProvider",
    "create_llm_provider",
    "get_llm_provider",
    "OPENAI_AVAILABLE",
    "ANTHROPIC_AVAILABLE",
    "GEMINI_AVAILABLE",
    "build_gcode_prompt",
    "build_preview_reflection_prompt",
    "build_reflection_prompt",
    "build_next_command_prompt",
    "build_composition_plan_prompt",
    "build_region_worker_prompt",
    "classify_creative_mode",
    "estimate_complexity",
    "STYLE_PRESETS",
    "FEW_SHOT_EXAMPLES",
]
