"""
Groq LLM Provider

Implements LLM provider interface for Groq API using Llama 3.3 70B model.
Supports JSON mode and handles rate limiting with exponential backoff.
"""

import os
import time
import logging
from typing import Optional

from .base_provider import LLMProvider, ProviderMetadata

logger = logging.getLogger(__name__)


class GroqProvider(LLMProvider):
    """
    Groq LLM provider using llama-3.3-70b-versatile model.
    
    Features:
    - JSON mode via response_format parameter
    - Rate limiting: 30 requests/minute (free tier)
    - Exponential backoff on rate limit errors
    """
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__()
        self._api_key = api_key or os.getenv("GROQ_API_KEY")
        self._client = None
        
        self._metadata = ProviderMetadata(
            name="Groq",
            model="llama-3.3-70b-versatile",
            rate_limit_rpm=30,
            supports_json_mode=True,
            requires_api_key=True,
            is_local=False
        )
    
    def is_available(self) -> bool:
        """Check if Groq API key is configured"""
        if not self._api_key:
            logger.debug("Groq provider unavailable: GROQ_API_KEY not set")
            return False
        
        # Try to initialize client
        try:
            self._get_client()
            return True
        except Exception as e:
            logger.debug(f"Groq provider unavailable: {e}")
            return False
    
    def _get_client(self):
        """Lazy initialization of Groq client"""
        if self._client is None:
            try:
                import httpx
                from groq import Groq
                # Use custom httpx client to handle corporate proxy/SSL issues
                http_client = httpx.Client(verify=False)
                self._client = Groq(api_key=self._api_key, http_client=http_client)
            except ImportError:
                raise ImportError(
                    "groq package not installed. Install with: pip install groq"
                )
        return self._client
    
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 2000
    ) -> str:
        """
        Generate response from Groq API with JSON mode.
        
        Implements exponential backoff for rate limit errors (429).
        """
        client = self._get_client()
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # Retry logic for rate limiting
        max_retries = 3
        base_delay = 2.0  # seconds
        
        for attempt in range(max_retries):
            try:
                response = client.chat.completions.create(
                    model=self.metadata.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format={"type": "json_object"}  # Force JSON output
                )
                
                content = response.choices[0].message.content
                logger.info(f"Groq generation successful (attempt {attempt + 1})")
                return content
                
            except Exception as e:
                error_str = str(e).lower()
                
                # Handle rate limiting (429)
                if "429" in error_str or "rate limit" in error_str:
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)  # Exponential backoff
                        logger.warning(
                            f"Groq rate limit hit, retrying in {delay}s "
                            f"(attempt {attempt + 1}/{max_retries})"
                        )
                        time.sleep(delay)
                        continue
                    else:
                        logger.error("Groq rate limit exceeded after retries")
                        raise
                
                # Handle other errors (5xx, network, etc.)
                logger.error(f"Groq API error: {e}")
                raise
        
        raise RuntimeError("Groq generation failed after all retries")
