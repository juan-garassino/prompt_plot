"""Tests for multimodal provider fallback behavior."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path

from promptplot.llm import LLMProvider, OllamaProvider


class FakeProvider(LLMProvider):
    """Concrete provider for testing the base class fallback."""

    @property
    def provider_name(self) -> str:
        return "fake"

    def _create_llm_instance(self):
        return MagicMock()


class TestMultimodalFallback:
    @pytest.mark.asyncio
    async def test_acomplete_multimodal_no_images_calls_acomplete(self):
        """acomplete_multimodal with no images falls back to acomplete."""
        provider = FakeProvider(timeout=10)
        provider.acomplete = AsyncMock(return_value="text response")
        result = await provider.acomplete_multimodal("test prompt", None)
        assert result == "text response"
        provider.acomplete.assert_awaited_once_with("test prompt")

    @pytest.mark.asyncio
    async def test_acomplete_multimodal_empty_list_calls_acomplete(self):
        """acomplete_multimodal with empty image list falls back to acomplete."""
        provider = FakeProvider(timeout=10)
        provider.acomplete = AsyncMock(return_value="text response")
        result = await provider.acomplete_multimodal("test prompt", [])
        assert result == "text response"

    @pytest.mark.asyncio
    async def test_base_class_default_fallback(self):
        """The base LLMProvider.acomplete_multimodal falls back to acomplete."""
        provider = FakeProvider(timeout=10)
        provider.acomplete = AsyncMock(return_value="fallback text")
        # Even with image paths, base class ignores them
        result = await provider.acomplete_multimodal(
            "test prompt", [Path("/tmp/test.png")]
        )
        assert result == "fallback text"


class TestOllamaMultimodalFallback:
    @pytest.mark.asyncio
    async def test_ollama_no_multimodal_package(self):
        """Ollama falls back to text when multimodal package is not installed."""
        with patch("promptplot.llm.OLLAMA_MULTIMODAL_AVAILABLE", False):
            provider = OllamaProvider(model="llama3.2:3b", request_timeout=5000)
            provider.acomplete = AsyncMock(return_value="text only")
            result = await provider.acomplete_multimodal(
                "test prompt", [Path("/tmp/test.png")]
            )
            assert result == "text only"
            provider.acomplete.assert_awaited_once()
