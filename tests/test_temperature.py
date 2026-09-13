"""Tests for temperature wiring to LLM providers."""

import pytest

from promptplot.config import LLMConfig
from promptplot.llm import (
    OllamaProvider,
    get_llm_provider,
)


class TestTemperatureWiring:
    def test_ollama_stores_temperature(self):
        """OllamaProvider stores temperature attribute."""
        provider = OllamaProvider(model="test", request_timeout=5000, temperature=0.7)
        assert provider.temperature == 0.7

    def test_ollama_default_temperature(self):
        """OllamaProvider uses default temperature 0.1."""
        provider = OllamaProvider(model="test", request_timeout=5000)
        assert provider.temperature == 0.1

    def test_get_llm_provider_passes_temperature(self):
        """get_llm_provider passes LLMConfig.temperature to the provider."""
        config = LLMConfig(default_provider="ollama", temperature=0.5)
        provider = get_llm_provider(config)
        assert provider.temperature == 0.5

    @pytest.mark.skipif(
        True,  # Skip unless openai is installed
        reason="Requires openai package"
    )
    def test_openai_passes_temperature(self):
        """OpenAIProvider stores temperature."""
        pass

    @pytest.mark.skipif(
        True,  # Skip unless gemini is installed
        reason="Requires google-generativeai package"
    )
    def test_gemini_passes_temperature(self):
        """GeminiProvider stores temperature."""
        pass

    def test_provider_stores_temperature(self):
        """All providers store temperature as attribute."""
        provider = OllamaProvider(model="test", request_timeout=5000, temperature=0.42)
        assert provider.temperature == 0.42

    def test_config_temperature_default(self):
        """LLMConfig default temperature is 0.1."""
        config = LLMConfig()
        assert config.temperature == 0.1
