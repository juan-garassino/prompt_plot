"""
LLM Provider Abstraction Layer

This module provides a unified interface for different LLM providers,
extracted from the existing workflow patterns in the boilerplate files.

Supported providers:
- OpenAI (GPT-4, GPT-4o-mini, etc.)
- Gemini (gemini-1.5-flash, gemini-1.5-pro, etc.)
- Azure OpenAI
- Ollama (local models)
"""

import os
import asyncio
from abc import ABC, abstractmethod
from typing import Any, Optional, Dict, Union
from llama_index.llms.ollama import Ollama
from llama_index.core.llms import CompletionResponse, ChatResponse

# Azure OpenAI
try:
    from llama_index.llms.azure_openai import AzureOpenAI
    AZURE_OPENAI_AVAILABLE = True
except ImportError:
    AZURE_OPENAI_AVAILABLE = False
    AzureOpenAI = None

# OpenAI
try:
    from llama_index.llms.openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None

# Gemini
try:
    from llama_index.llms.gemini import Gemini
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    Gemini = None


class LLMProviderError(Exception):
    """Base exception for LLM provider errors"""
    def __init__(self, message: str, provider: str, details: Optional[Dict] = None):
        self.message = message
        self.provider = provider
        self.details = details or {}
        super().__init__(self.message)


class LLMTimeoutError(LLMProviderError):
    """Exception raised when LLM request times out"""
    pass


class LLMValidationError(LLMProviderError):
    """Exception raised when LLM response validation fails"""
    pass


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    
    Provides a common interface for both sync and async completion methods,
    with consistent error handling across different LLM services.
    
    Based on patterns extracted from existing workflow files:
    - generate_llm_simple.py uses both Ollama and AzureOpenAI
    - generate_llm_advanced.py uses sync completion
    - llm_stream_*.py files use async completion
    """
    
    def __init__(self, timeout: int = 30):
        """
        Initialize the LLM provider.
        
        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        self._llm = None
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the name of this provider"""
        pass
    
    @abstractmethod
    def _create_llm_instance(self) -> Any:
        """Create the underlying LLM instance"""
        pass
    
    @property
    def llm(self) -> Any:
        """Get the underlying LLM instance, creating it if necessary"""
        if self._llm is None:
            self._llm = self._create_llm_instance()
        return self._llm
    
    @abstractmethod
    async def acomplete(self, prompt: str) -> str:
        """
        Async completion method.
        
        Args:
            prompt: The prompt to complete
            
        Returns:
            The completion text
            
        Raises:
            LLMProviderError: If completion fails
            LLMTimeoutError: If request times out
        """
        pass
    
    @abstractmethod
    def complete(self, prompt: str) -> str:
        """
        Sync completion method.
        
        Args:
            prompt: The prompt to complete
            
        Returns:
            The completion text
            
        Raises:
            LLMProviderError: If completion fails
            LLMTimeoutError: If request times out
        """
        pass
    
    def _handle_error(self, error: Exception, operation: str) -> None:
        """
        Handle and wrap errors consistently.
        
        Args:
            error: The original error
            operation: Description of the operation that failed
        """
        if isinstance(error, asyncio.TimeoutError):
            raise LLMTimeoutError(
                f"Timeout during {operation}",
                self.provider_name,
                {"timeout": self.timeout, "operation": operation}
            )
        elif isinstance(error, LLMProviderError):
            # Re-raise our own errors
            raise error
        else:
            # Wrap other errors
            raise LLMProviderError(
                f"Error during {operation}: {str(error)}",
                self.provider_name,
                {"operation": operation, "original_error": str(error)}
            )


class AzureOpenAIProvider(LLMProvider):
    """
    Azure OpenAI provider implementation.
    
    Extracted from existing usage patterns in boilerplate files.
    Configuration matches the pattern used in generate_llm_simple.py and generate_llm_advanced.py.
    """
    
    def __init__(
        self,
        model: str = "gpt-4o",
        deployment_name: str = "gpt-4o-gs", 
        api_key: Optional[str] = None,
        api_version: Optional[str] = None,
        azure_endpoint: Optional[str] = None,
        timeout: int = 1220
    ):
        """
        Initialize Azure OpenAI provider.
        
        Args:
            model: Model name (e.g., "gpt-4o")
            deployment_name: Azure deployment name
            api_key: API key (defaults to GPT4_API_KEY env var)
            api_version: API version (defaults to GPT4_API_VERSION env var)
            azure_endpoint: Azure endpoint (defaults to GPT4_ENDPOINT env var)
            timeout: Request timeout in seconds
        """
        super().__init__(timeout)
        self.model = model
        self.deployment_name = deployment_name
        self.api_key = api_key or os.environ.get("GPT4_API_KEY")
        self.api_version = api_version or os.environ.get("GPT4_API_VERSION")
        self.azure_endpoint = azure_endpoint or os.environ.get("GPT4_ENDPOINT")
        
        # Validate required configuration
        if not all([self.api_key, self.api_version, self.azure_endpoint]):
            missing = []
            if not self.api_key:
                missing.append("api_key (or GPT4_API_KEY env var)")
            if not self.api_version:
                missing.append("api_version (or GPT4_API_VERSION env var)")
            if not self.azure_endpoint:
                missing.append("azure_endpoint (or GPT4_ENDPOINT env var)")
            
            raise LLMProviderError(
                f"Missing required Azure OpenAI configuration: {', '.join(missing)}",
                self.provider_name,
                {"missing_config": missing}
            )
    
    @property
    def provider_name(self) -> str:
        return "azure_openai"
    
    def _create_llm_instance(self):
        """Create Azure OpenAI LLM instance"""
        if not AZURE_OPENAI_AVAILABLE:
            raise LLMProviderError(
                "Azure OpenAI not available. Install with: pip install llama-index-llms-azure-openai",
                self.provider_name
            )
        
        try:
            return AzureOpenAI(
                model=self.model,
                deployment_name=self.deployment_name,
                api_key=self.api_key,
                api_version=self.api_version,
                azure_endpoint=self.azure_endpoint,
                timeout=self.timeout
            )
        except Exception as e:
            raise LLMProviderError(
                f"Failed to create Azure OpenAI instance: {str(e)}",
                self.provider_name,
                {"config": {
                    "model": self.model,
                    "deployment_name": self.deployment_name,
                    "timeout": self.timeout
                }}
            )
    
    async def acomplete(self, prompt: str) -> str:
        """
        Async completion using Azure OpenAI.
        
        Args:
            prompt: The prompt to complete
            
        Returns:
            The completion text
        """
        try:
            response = await asyncio.wait_for(
                self.llm.acomplete(prompt),
                timeout=self.timeout
            )
            
            if isinstance(response, CompletionResponse):
                return response.text
            else:
                return str(response)
                
        except Exception as e:
            self._handle_error(e, "async completion")
    
    def complete(self, prompt: str) -> str:
        """
        Sync completion using Azure OpenAI.
        
        Args:
            prompt: The prompt to complete
            
        Returns:
            The completion text
        """
        try:
            response = self.llm.complete(prompt)
            
            if isinstance(response, CompletionResponse):
                return response.text
            else:
                return str(response)
                
        except Exception as e:
            self._handle_error(e, "sync completion")


class OllamaProvider(LLMProvider):
    """
    Ollama provider implementation.
    
    Extracted from existing usage patterns in boilerplate files.
    Configuration matches the pattern used as fallback in existing workflows.
    """
    
    def __init__(
        self,
        model: str = "llama3.2:3b",
        request_timeout: int = 10000,
        base_url: Optional[str] = None
    ):
        """
        Initialize Ollama provider.
        
        Args:
            model: Model name (e.g., "llama3.2:3b")
            request_timeout: Request timeout in milliseconds (Ollama uses ms)
            base_url: Base URL for Ollama server (optional)
        """
        # Convert milliseconds to seconds for parent class
        super().__init__(timeout=request_timeout // 1000)
        self.model = model
        self.request_timeout = request_timeout
        self.base_url = base_url
    
    @property
    def provider_name(self) -> str:
        return "ollama"
    
    def _create_llm_instance(self) -> Ollama:
        """Create Ollama LLM instance"""
        try:
            kwargs = {
                "model": self.model,
                "request_timeout": self.request_timeout
            }
            
            if self.base_url:
                kwargs["base_url"] = self.base_url
            
            return Ollama(**kwargs)
            
        except Exception as e:
            raise LLMProviderError(
                f"Failed to create Ollama instance: {str(e)}",
                self.provider_name,
                {"config": {
                    "model": self.model,
                    "request_timeout": self.request_timeout,
                    "base_url": self.base_url
                }}
            )
    
    async def acomplete(self, prompt: str) -> str:
        """
        Async completion using Ollama.
        
        Args:
            prompt: The prompt to complete
            
        Returns:
            The completion text
        """
        try:
            response = await asyncio.wait_for(
                self.llm.acomplete(prompt),
                timeout=self.timeout
            )
            
            if isinstance(response, CompletionResponse):
                return response.text
            else:
                return str(response)
                
        except Exception as e:
            self._handle_error(e, "async completion")
    
    def complete(self, prompt: str) -> str:
        """
        Sync completion using Ollama.
        
        Args:
            prompt: The prompt to complete
            
        Returns:
            The completion text
        """
        try:
            response = self.llm.complete(prompt)
            
            if isinstance(response, CompletionResponse):
                return response.text
            else:
                return str(response)
                
        except Exception as e:
            self._handle_error(e, "sync completion")


class OpenAIProvider(LLMProvider):
    """
    OpenAI provider implementation.
    
    Uses the standard OpenAI API (not Azure).
    Supports GPT-4, GPT-4o-mini, GPT-3.5-turbo, etc.
    """
    
    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
        timeout: int = 120
    ):
        """
        Initialize OpenAI provider.
        
        Args:
            model: Model name (e.g., "gpt-4o-mini", "gpt-4o", "gpt-4")
            api_key: API key (defaults to OPENAI_API_KEY env var)
            timeout: Request timeout in seconds
        """
        super().__init__(timeout)
        self.model = model
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        
        if not self.api_key:
            raise LLMProviderError(
                "Missing OpenAI API key. Set OPENAI_API_KEY env var or pass api_key parameter.",
                self.provider_name,
                {"missing_config": ["api_key (or OPENAI_API_KEY env var)"]}
            )
    
    @property
    def provider_name(self) -> str:
        return "openai"
    
    def _create_llm_instance(self):
        """Create OpenAI LLM instance"""
        if not OPENAI_AVAILABLE:
            raise LLMProviderError(
                "OpenAI not available. Install with: pip install llama-index-llms-openai",
                self.provider_name
            )
        
        try:
            return OpenAI(
                model=self.model,
                api_key=self.api_key,
                timeout=self.timeout
            )
        except Exception as e:
            raise LLMProviderError(
                f"Failed to create OpenAI instance: {str(e)}",
                self.provider_name,
                {"config": {"model": self.model, "timeout": self.timeout}}
            )
    
    async def acomplete(self, prompt: str) -> str:
        """Async completion using OpenAI."""
        try:
            response = await asyncio.wait_for(
                self.llm.acomplete(prompt),
                timeout=self.timeout
            )
            return response.text if isinstance(response, CompletionResponse) else str(response)
        except Exception as e:
            self._handle_error(e, "async completion")
    
    def complete(self, prompt: str) -> str:
        """Sync completion using OpenAI."""
        try:
            response = self.llm.complete(prompt)
            return response.text if isinstance(response, CompletionResponse) else str(response)
        except Exception as e:
            self._handle_error(e, "sync completion")


class GeminiProvider(LLMProvider):
    """
    Google Gemini provider implementation.
    
    Supports Gemini 1.5 Flash, Gemini 1.5 Pro, etc.
    """
    
    def __init__(
        self,
        model: str = "models/gemini-1.5-flash",
        api_key: Optional[str] = None,
        timeout: int = 120
    ):
        """
        Initialize Gemini provider.
        
        Args:
            model: Model name (e.g., "models/gemini-1.5-flash", "models/gemini-1.5-pro")
            api_key: API key (defaults to GOOGLE_API_KEY env var)
            timeout: Request timeout in seconds
        """
        super().__init__(timeout)
        self.model = model
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        
        if not self.api_key:
            raise LLMProviderError(
                "Missing Google API key. Set GOOGLE_API_KEY env var or pass api_key parameter.",
                self.provider_name,
                {"missing_config": ["api_key (or GOOGLE_API_KEY env var)"]}
            )
    
    @property
    def provider_name(self) -> str:
        return "gemini"
    
    def _create_llm_instance(self):
        """Create Gemini LLM instance"""
        if not GEMINI_AVAILABLE:
            raise LLMProviderError(
                "Gemini not available. Install with: pip install llama-index-llms-gemini",
                self.provider_name
            )
        
        try:
            return Gemini(
                model=self.model,
                api_key=self.api_key,
            )
        except Exception as e:
            raise LLMProviderError(
                f"Failed to create Gemini instance: {str(e)}",
                self.provider_name,
                {"config": {"model": self.model}}
            )
    
    async def acomplete(self, prompt: str) -> str:
        """Async completion using Gemini."""
        try:
            response = await asyncio.wait_for(
                self.llm.acomplete(prompt),
                timeout=self.timeout
            )
            return response.text if isinstance(response, CompletionResponse) else str(response)
        except Exception as e:
            self._handle_error(e, "async completion")
    
    def complete(self, prompt: str) -> str:
        """Sync completion using Gemini."""
        try:
            response = self.llm.complete(prompt)
            return response.text if isinstance(response, CompletionResponse) else str(response)
        except Exception as e:
            self._handle_error(e, "sync completion")


def create_llm_provider(
    provider_type: str,
    **kwargs
) -> LLMProvider:
    """
    Factory function to create LLM providers.
    
    Args:
        provider_type: Type of provider ("openai", "gemini", "azure_openai", or "ollama")
        **kwargs: Provider-specific configuration
        
    Returns:
        Configured LLM provider instance
        
    Raises:
        ValueError: If provider_type is not supported
        LLMProviderError: If provider creation fails
    """
    providers = {
        "openai": OpenAIProvider,
        "gemini": GeminiProvider,
        "azure_openai": AzureOpenAIProvider,
        "ollama": OllamaProvider
    }
    
    if provider_type not in providers:
        raise ValueError(
            f"Unsupported provider type: {provider_type}. "
            f"Supported types: {list(providers.keys())}"
        )
    
    try:
        return providers[provider_type](**kwargs)
    except Exception as e:
        if isinstance(e, LLMProviderError):
            raise e
        else:
            raise LLMProviderError(
                f"Failed to create {provider_type} provider: {str(e)}",
                provider_type,
                {"kwargs": kwargs}
            )


def get_llm_provider(llm_config) -> LLMProvider:
    """
    Get LLM provider instance from configuration.
    
    Args:
        llm_config: LLM configuration object
        
    Returns:
        Configured LLM provider instance
        
    Raises:
        LLMProviderError: If provider creation fails
    """
    provider_type = llm_config.default_provider
    
    if provider_type == "azure_openai":
        return AzureOpenAIProvider(
            model=llm_config.azure_model,
            deployment_name=llm_config.azure_deployment_name,
            api_key=llm_config.azure_api_key,
            api_version=llm_config.azure_api_version,
            azure_endpoint=llm_config.azure_endpoint,
            timeout=llm_config.azure_timeout
        )
    elif provider_type == "ollama":
        return OllamaProvider(
            model=llm_config.ollama_model,
            request_timeout=llm_config.ollama_timeout,
            base_url=llm_config.ollama_base_url
        )
    elif provider_type == "openai":
        return OpenAIProvider(
            model=getattr(llm_config, 'openai_model', 'gpt-4o-mini'),
            api_key=getattr(llm_config, 'openai_api_key', None),
            timeout=getattr(llm_config, 'openai_timeout', 120)
        )
    elif provider_type == "gemini":
        return GeminiProvider(
            model=getattr(llm_config, 'gemini_model', 'models/gemini-1.5-flash'),
            api_key=getattr(llm_config, 'gemini_api_key', None),
            timeout=getattr(llm_config, 'gemini_timeout', 120)
        )
    else:
        raise LLMProviderError(
            f"Unknown provider type: {provider_type}. Supported: openai, gemini, azure_openai, ollama",
            provider_type
        )