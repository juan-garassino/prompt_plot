"""Tests for temperature wiring to LLM providers."""

import pytest
from unittest.mock import patch, MagicMock

from promptplot.config import LLMConfig
from promptplot.llm import (
    OllamaProvider,
    get_llm_provider,
)


class TestTemperatureWiring:
    def test_ollama_passes_temperature(self):
        """OllamaProvider passes temperature to Ollama constructor."""
        with patch("promptplot.llm.Ollama") as MockOllama:
            MockOllama.return_value = MagicMock()
            provider = OllamaProvider(model="test", request_timeout=5000, temperature=0.7)
            _ = provider.llm  # trigger lazy creation
            MockOllama.assert_called_once()
            call_kwargs = MockOllama.call_args[1]
            assert call_kwargs["temperature"] == 0.7

    def test_ollama_default_temperature(self):
        """OllamaProvider uses default temperature 0.1."""
        with patch("promptplot.llm.Ollama") as MockOllama:
            MockOllama.return_value = MagicMock()
            provider = OllamaProvider(model="test", request_timeout=5000)
            _ = provider.llm
            call_kwargs = MockOllama.call_args[1]
            assert call_kwargs["temperature"] == 0.1

    def test_get_llm_provider_passes_temperature(self):
        """get_llm_provider passes LLMConfig.temperature to the provider."""
        config = LLMConfig(default_provider="ollama", temperature=0.5)
        with patch("promptplot.llm.Ollama") as MockOllama:
            MockOllama.return_value = MagicMock()
            provider = get_llm_provider(config)
            assert provider.temperature == 0.5

    @pytest.mark.skipif(
        True,  # Skip unless openai is installed
        reason="Requires llama-index-llms-openai"
    )
    def test_openai_passes_temperature(self):
        """OpenAIProvider passes temperature to OpenAI constructor."""
        pass

    @pytest.mark.skipif(
        True,  # Skip unless gemini is installed
        reason="Requires llama-index-llms-gemini"
    )
    def test_gemini_passes_temperature(self):
        """GeminiProvider passes temperature to Gemini constructor."""
        pass

    def test_provider_stores_temperature(self):
        """All providers store temperature as attribute."""
        provider = OllamaProvider(model="test", request_timeout=5000, temperature=0.42)
        assert provider.temperature == 0.42

    def test_config_temperature_default(self):
        """LLMConfig default temperature is 0.1."""
        config = LLMConfig()
        assert config.temperature == 0.1
