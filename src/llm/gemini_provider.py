"""
Gemini LLM Provider

Implements LLM provider interface for Google Gemini API using gemini-2.0-flash model.
Supports JSON mode and handles API errors with retry logic.
"""

import os
import time
import logging
from typing import Optional

from .base_provider import LLMProvider, ProviderMetadata

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    """
    Google Gemini LLM provider using gemini-2.0-flash-exp model.
    
    Features:
    - JSON mode via response_mime_type parameter
    - Rate limiting: 1500 requests/day (free tier)
    - Retry logic for transient errors
    """
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__()
        self._api_key = api_key or os.getenv("GEMINI_API_KEY")
        self._model = None
        
        self._metadata = ProviderMetadata(
            name="Gemini",
            model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
            rate_limit_rpd=1500,
            supports_json_mode=True,
            requires_api_key=True,
            is_local=False
        )
    
    def is_available(self) -> bool:
        """Check if Gemini API key is configured"""
        if not self._api_key:
            logger.debug("Gemini provider unavailable: GEMINI_API_KEY not set")
            return False
        
        # Try to initialize model
        try:
            self._get_model()
            return True
        except Exception as e:
            logger.debug(f"Gemini provider unavailable: {e}")
            return False
    
    def _get_model(self):
        """Lazy initialization of Gemini model"""
        if self._model is None:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self._api_key)
                self._model = genai.GenerativeModel(
                    model_name=self.metadata.model,
                    generation_config={
                        "response_mime_type": "application/json"
                    }
                )
            except ImportError:
                raise ImportError(
                    "google-generativeai package not installed. "
                    "Install with: pip install google-generativeai"
                )
        return self._model
    
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 2000
    ) -> str:
        """
        Generate response from Gemini API with JSON mode.
        
        Implements retry logic for transient API errors.
        """
        model = self._get_model()
        
        # Gemini combines system and user prompts
        combined_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        # Retry logic for transient errors
        max_retries = 2
        base_delay = 1.0  # seconds
        
        for attempt in range(max_retries):
            try:
                response = model.generate_content(
                    combined_prompt,
                    generation_config={
                        "temperature": temperature,
                        "max_output_tokens": max_tokens,
                        "response_mime_type": "application/json"
                    }
                )
                
                content = response.text
                logger.info(f"Gemini generation successful (attempt {attempt + 1})")
                return content
                
            except Exception as e:
                error_str = str(e).lower()
                
                # Handle rate limiting
                if "quota" in error_str or "rate limit" in error_str:
                    logger.error(f"Gemini rate limit exceeded: {e}")
                    raise
                
                # Handle transient errors with retry
                if attempt < max_retries - 1:
                    delay = base_delay * (attempt + 1)
                    logger.warning(
                        f"Gemini API error, retrying in {delay}s "
                        f"(attempt {attempt + 1}/{max_retries}): {e}"
                    )
                    time.sleep(delay)
                    continue
                
                # Final attempt failed
                logger.error(f"Gemini API error after retries: {e}")
                raise
        
        raise RuntimeError("Gemini generation failed after all retries")
