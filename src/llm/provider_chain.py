"""
LLM Provider Fallback Chain

Manages automatic fallback between multiple LLM providers:
Groq → Gemini → Ollama → Rule Engine

Caches the active provider to avoid re-checking on every request.
"""

import logging
from typing import Optional, List
from datetime import datetime

from .base_provider import LLMProvider
from .groq_provider import GroqProvider
from .gemini_provider import GeminiProvider
from .ollama_provider import OllamaProvider

logger = logging.getLogger(__name__)


class ProviderChain:
    """
    Manages LLM provider fallback chain with caching.
    
    Fallback order:
    1. Groq (fastest, 30 req/min)
    2. Gemini (fast, 1500 req/day)
    3. Ollama (slow but offline, unlimited)
    4. Rule Engine (deterministic fallback)
    """
    
    def __init__(self):
        self._providers: List[LLMProvider] = [
            GroqProvider(),
            GeminiProvider(),
            OllamaProvider()
        ]
        self._active_provider: Optional[LLMProvider] = None
        self._last_check_time: Optional[datetime] = None
    
    def get_provider(self) -> Optional[LLMProvider]:
        """
        Get the first available LLM provider.
        
        Uses cached provider if available, otherwise checks all providers
        in fallback order.
        
        Returns:
            LLMProvider instance or None if all providers unavailable
        """
        # Try cached provider first
        if self._active_provider is not None:
            if self._active_provider.is_available():
                logger.debug(f"Using cached provider: {self._active_provider}")
                return self._active_provider
            else:
                logger.warning(
                    f"Cached provider {self._active_provider} no longer available, "
                    "checking fallback chain"
                )
                self._active_provider = None
        
        # Check all providers in order
        for provider in self._providers:
            logger.debug(f"Checking provider: {provider}")
            if provider.is_available():
                self._active_provider = provider
                self._last_check_time = datetime.now()
                logger.info(f"Active LLM provider: {provider}")
                return provider
        
        # No providers available
        logger.error("No LLM providers available")
        return None
    
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 2000
    ) -> tuple[str, str]:
        """
        Generate response using the first available provider.
        
        Automatically falls back to next provider on failure.
        
        Args:
            system_prompt: System-level instructions
            user_prompt: User query/context
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            
        Returns:
            Tuple of (response_text, provider_name)
            
        Raises:
            RuntimeError: If all providers fail
        """
        for provider in self._providers:
            if not provider.is_available():
                logger.debug(f"Skipping unavailable provider: {provider}")
                continue
            
            try:
                logger.info(f"Attempting generation with {provider}")
                response = provider.generate(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                
                # Success - cache this provider
                self._active_provider = provider
                logger.info(f"Generation successful with {provider}")
                return response, provider.metadata.name
                
            except Exception as e:
                logger.warning(
                    f"Provider {provider} failed: {e}. "
                    "Trying next provider in chain..."
                )
                # Clear cached provider on failure
                if self._active_provider == provider:
                    self._active_provider = None
                continue
        
        # All providers failed
        raise RuntimeError(
            "All LLM providers failed. "
            "Set GROQ_API_KEY or GEMINI_API_KEY in .env, "
            "or start Ollama locally with: ollama serve"
        )
    
    def get_provider_status(self) -> dict:
        """
        Get availability status of all providers.
        
        Returns:
            Dict mapping provider name to availability status
        """
        status = {}
        for provider in self._providers:
            try:
                available = provider.is_available()
                status[provider.metadata.name.lower()] = (
                    "available" if available else "unavailable"
                )
            except Exception as e:
                status[provider.metadata.name.lower()] = f"error: {e}"
        
        return status
    
    def get_active_provider_name(self) -> Optional[str]:
        """Get the name of the currently active provider"""
        if self._active_provider:
            return self._active_provider.metadata.name
        return None
