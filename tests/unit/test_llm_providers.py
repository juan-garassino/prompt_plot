"""
Unit tests for LLM provider abstraction and implementations.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
import asyncio
import json

from promptplot.llm.providers import LLMProvider
from promptplot.core.exceptions import LLMException
from tests.utils.mocks import MockLLMProvider


class TestLLMProviderBase:
    """Test base LLM provider interface."""
    
    @pytest.mark.unit
    def test_provider_is_abstract(self):
        """Test that LLMProvider cannot be instantiated directly."""
        with pytest.raises(TypeError):
            LLMProvider()
            
    @pytest.mark.unit
    def test_mock_provider_implementation(self):
        """Test mock provider implementation."""
        responses = ['{"command": "G1", "x": 10, "y": 20}']
        provider = MockLLMProvider(responses=responses)
        
        result = provider.complete("Draw a line")
        assert result == responses[0]
        assert provider.last_prompt == "Draw a line"
        assert provider.call_count == 1
        
    @pytest.mark.unit
    async def test_mock_provider_async(self):
        """Test mock provider async implementation."""
        responses = ['{"command": "G1", "x": 10, "y": 20}']
        provider = MockLLMProvider(responses=responses)
        
        result = await provider.acomplete("Draw a line")
        assert result == responses[0]
        assert provider.last_prompt == "Draw a line"
        
    @pytest.mark.unit
    def test_mock_provider_multiple_responses(self):
        """Test mock provider with multiple responses."""
        responses = [
            '{"command": "G1", "x": 10, "y": 20}',
            '{"command": "G1", "x": 30, "y": 40}',
            '{"command": "M5"}'
        ]
        provider = MockLLMProvider(responses=responses)
        
        # Test cycling through responses
        for i, expected in enumerate(responses):
            result = provider.complete(f"Prompt {i}")
            assert result == expected
            
        # Test cycling back to first response
        result = provider.complete("Prompt 3")
        assert result == responses[0]


# Note: Real provider tests are skipped since we don't have API keys
# These would test actual Azure OpenAI and Ollama providers with real API calls


class TestLLMProviderIntegration:
    """Test LLM provider integration scenarios."""
    
    @pytest.mark.unit
    def test_provider_response_parsing(self):
        """Test parsing LLM responses."""
        provider = MockLLMProvider(responses=[
            '{"command": "G1", "x": 10.5, "y": 20.5, "f": 1000}',
            '{"command": "M3", "s": 255}',
            '{"command": "G28"}'
        ])
        
        # Test parsing valid JSON responses
        for i in range(3):
            response = provider.complete(f"prompt {i}")
            parsed = json.loads(response)
            assert "command" in parsed
            
    @pytest.mark.unit
    def test_provider_invalid_response(self):
        """Test handling invalid LLM responses."""
        provider = MockLLMProvider(responses=[
            'Invalid JSON response',
            '{"incomplete": json',
            ''
        ])
        
        # Test that invalid responses are returned as-is
        # (validation should happen at a higher level)
        response1 = provider.complete("prompt 1")
        assert response1 == 'Invalid JSON response'
        
        response2 = provider.complete("prompt 2")
        assert response2 == '{"incomplete": json'
        
        response3 = provider.complete("prompt 3")
        assert response3 == ''
        
    @pytest.mark.unit
    async def test_provider_concurrent_requests(self):
        """Test concurrent requests to provider."""
        provider = MockLLMProvider(responses=[
            '{"command": "G1", "x": 10, "y": 20}',
            '{"command": "G1", "x": 30, "y": 40}',
            '{"command": "M5"}'
        ])
        
        # Make concurrent requests
        tasks = [
            provider.acomplete(f"prompt {i}")
            for i in range(5)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # All requests should complete
        assert len(results) == 5
        for result in results:
            assert result.startswith('{"command":')
            
    @pytest.mark.unit
    def test_provider_prompt_history(self):
        """Test provider maintains prompt history."""
        provider = MockLLMProvider()
        
        prompts = [
            "Draw a line from (0,0) to (10,10)",
            "Draw a circle with radius 5",
            "Move pen up"
        ]
        
        for prompt in prompts:
            provider.complete(prompt)
            assert provider.last_prompt == prompt
            
    @pytest.mark.unit
    def test_provider_call_counting(self):
        """Test provider tracks call count."""
        provider = MockLLMProvider()
        
        assert provider.call_count == 0
        
        for i in range(5):
            provider.complete(f"prompt {i}")
            assert provider.call_count == i + 1