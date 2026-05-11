"""
Ollama LLM Provider

Implements LLM provider interface for local Ollama instance.
Default model: llama3.1:8b (set OLLAMA_MODEL in .env to override).
Supports JSON mode and works offline without API keys.
"""

import os
import logging
from typing import Optional

from .base_provider import LLMProvider, ProviderMetadata

logger = logging.getLogger(__name__)

# Timeout for Ollama requests — llama3.1:8b on CPU takes ~30-120s per call
# First call may take longer due to model loading into RAM
OLLAMA_TIMEOUT = 600  # seconds (10 minutes for cold start on CPU)


class OllamaProvider(LLMProvider):
    """
    Ollama LLM provider (default: llama3.1:8b).

    Features:
    - JSON mode via format parameter
    - No rate limits (runs locally)
    - No API key required
    - Works offline
    """

    def __init__(self, base_url: Optional[str] = None):
        super().__init__()
        self._base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self._client = None

        self._metadata = ProviderMetadata(
            name="Ollama",
            model=os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
            rate_limit_rpm=None,  # Unlimited
            supports_json_mode=True,
            requires_api_key=False,
            is_local=True
        )

    def is_available(self) -> bool:
        """Check if Ollama is running locally with a short timeout."""
        try:
            import requests as _req
            r = _req.get(f"{self._base_url}/api/tags", timeout=5)
            models = [m["name"] for m in r.json().get("models", [])]
            target = self.metadata.model.split(":")[0]
            available = any(target in m for m in models)
            if not available:
                logger.debug(
                    f"Ollama running but model '{self.metadata.model}' not found. "
                    f"Run: ollama pull {self.metadata.model}"
                )
            return available
        except Exception as e:
            logger.debug(f"Ollama provider unavailable: {e}")
            return False

    def _get_client(self):
        """Lazy initialization of Ollama client with extended timeout."""
        if self._client is None:
            try:
                import ollama
                # Pass timeout via kwargs (forwarded to httpx)
                self._client = ollama.Client(
                    host=self._base_url,
                    timeout=OLLAMA_TIMEOUT,
                )
            except ImportError:
                raise ImportError(
                    "ollama package not installed. Install with: pip install ollama"
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
        Generate response from local Ollama instance with JSON mode.

        Uses direct HTTP POST to /api/chat with a long timeout to handle
        llama3.1:8b cold start on CPU (can take 5-10 minutes first call).
        """
        import json as _json
        import requests as _req

        payload = {
            "model": self.metadata.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
            "format": "json",
            "stream": False,
        }

        try:
            resp = _req.post(
                f"{self._base_url}/api/chat",
                json=payload,
                timeout=OLLAMA_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["message"]["content"]
            logger.info(f"Ollama generation successful (model={self.metadata.model})")
            return content

        except _req.exceptions.Timeout:
            logger.error(
                f"Ollama timed out after {OLLAMA_TIMEOUT}s. "
                f"Model may still be loading on CPU."
            )
            raise
        except Exception as e:
            error_str = str(e).lower()
            if "not found" in error_str or "pull" in error_str:
                logger.error(
                    f"Ollama model '{self.metadata.model}' not found. "
                    f"Pull it with: ollama pull {self.metadata.model}"
                )
            else:
                logger.error(f"Ollama API error: {e}")
            raise
