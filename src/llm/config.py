"""
LLM Configuration Management

Centralized configuration loader with validation and defaults.
Loads all environment variables, validates required settings, and provides
a single source of truth for LLM and RAG configuration.
"""

import os
import logging
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class LLMConfig:
    """
    Centralized configuration for LLM Decision Engine.
    
    Loads all environment variables with sensible defaults,
    validates required settings, and creates directories as needed.
    """
    
    def __init__(self):
        """Initialize configuration from environment variables"""
        # LLM Provider API Keys
        self.groq_api_key: Optional[str] = os.getenv("GROQ_API_KEY")
        self.gemini_api_key: Optional[str] = os.getenv("GEMINI_API_KEY")
        self.ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        
        # RAG Configuration
        self.rag_top_k: int = self._parse_int("RAG_TOP_K", 5)
        self.sop_top_k: int = self._parse_int("SOP_TOP_K", 3)
        self.embedding_model: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        
        # ChromaDB Paths
        self.chroma_memory_path: str = os.getenv("CHROMA_MEMORY_PATH", "data/chroma_memory")
        self.chroma_sop_path: str = os.getenv("CHROMA_SOP_PATH", "data/chroma_sops")
        
        # Feature Flags
        self.llm_enabled: bool = self._parse_bool("LLM_ENABLED", False)
        self.llm_shadow_mode: bool = self._parse_bool("LLM_SHADOW_MODE", False)
        
        # Validate configuration
        self._validate()
        
        # Create directories if needed
        self._ensure_directories()
        
        # Log configuration summary
        self._log_summary()
    
    def _parse_int(self, key: str, default: int) -> int:
        """Parse integer environment variable with validation"""
        value = os.getenv(key)
        if value is None:
            return default
        
        try:
            parsed = int(value)
            if parsed <= 0:
                logger.warning(
                    f"{key}={value} is not positive, using default {default}"
                )
                return default
            return parsed
        except ValueError:
            logger.warning(
                f"{key}={value} is not a valid integer, using default {default}"
            )
            return default
    
    def _parse_bool(self, key: str, default: bool) -> bool:
        """Parse boolean environment variable"""
        value = os.getenv(key)
        if value is None:
            return default
        
        return value.lower() in ("true", "1", "yes", "on")
    
    def _validate(self):
        """Validate configuration settings"""
        # Validate RAG parameters
        if self.rag_top_k <= 0:
            raise ValueError(f"RAG_TOP_K must be positive, got {self.rag_top_k}")
        
        if self.sop_top_k <= 0:
            raise ValueError(f"SOP_TOP_K must be positive, got {self.sop_top_k}")
        
        # Validate Ollama URL format
        try:
            parsed = urlparse(self.ollama_base_url)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError(
                    f"OLLAMA_BASE_URL must be a valid URL, got {self.ollama_base_url}"
                )
        except Exception as e:
            raise ValueError(
                f"OLLAMA_BASE_URL is invalid: {self.ollama_base_url} - {e}"
            )
        
        # Validate ChromaDB paths are writable
        for path_name, path_value in [
            ("CHROMA_MEMORY_PATH", self.chroma_memory_path),
            ("CHROMA_SOP_PATH", self.chroma_sop_path)
        ]:
            path = Path(path_value)
            parent = path.parent if not path.exists() else path
            
            # Check if parent directory exists and is writable
            if parent.exists() and not os.access(parent, os.W_OK):
                raise ValueError(
                    f"{path_name} directory is not writable: {path_value}"
                )
        
        # Warn if no API keys are configured
        if not self.groq_api_key and not self.gemini_api_key:
            logger.warning(
                "No LLM API keys configured (GROQ_API_KEY, GEMINI_API_KEY). "
                "System will attempt to use Ollama or fallback to rule-based engine."
            )
        
        # Warn about specific missing keys
        if not self.groq_api_key:
            logger.info(
                "GROQ_API_KEY not set. Groq provider will be unavailable. "
                "Get a free API key from: https://console.groq.com/keys"
            )
        
        if not self.gemini_api_key:
            logger.info(
                "GEMINI_API_KEY not set. Gemini provider will be unavailable. "
                "Get a free API key from: https://aistudio.google.com/apikey"
            )
    
    def _ensure_directories(self):
        """Create ChromaDB directories if they don't exist"""
        for path_name, path_value in [
            ("CHROMA_MEMORY_PATH", self.chroma_memory_path),
            ("CHROMA_SOP_PATH", self.chroma_sop_path)
        ]:
            path = Path(path_value)
            if not path.exists():
                try:
                    path.mkdir(parents=True, exist_ok=True)
                    logger.info(f"Created directory: {path_value}")
                except Exception as e:
                    logger.error(
                        f"Failed to create {path_name} directory {path_value}: {e}"
                    )
                    raise
    
    def _log_summary(self):
        """Log configuration summary"""
        logger.info("LLM Configuration loaded:")
        logger.info(f"  LLM Enabled: {self.llm_enabled}")
        logger.info(f"  Shadow Mode: {self.llm_shadow_mode}")
        logger.info(f"  Groq API Key: {'✓ Set' if self.groq_api_key else '✗ Not set'}")
        logger.info(f"  Gemini API Key: {'✓ Set' if self.gemini_api_key else '✗ Not set'}")
        logger.info(f"  Ollama URL: {self.ollama_base_url}")
        logger.info(f"  RAG Top-K: {self.rag_top_k}")
        logger.info(f"  SOP Top-K: {self.sop_top_k}")
        logger.info(f"  Embedding Model: {self.embedding_model}")
        logger.info(f"  Memory Path: {self.chroma_memory_path}")
        logger.info(f"  SOP Path: {self.chroma_sop_path}")
    
    def has_any_provider(self) -> bool:
        """Check if at least one LLM provider is configured"""
        return bool(self.groq_api_key or self.gemini_api_key or self.ollama_base_url)
    
    def get_available_providers(self) -> list[str]:
        """Get list of potentially available providers"""
        providers = []
        if self.groq_api_key:
            providers.append("groq")
        if self.gemini_api_key:
            providers.append("gemini")
        # Ollama is always potentially available (may not be running)
        providers.append("ollama")
        return providers


# Global configuration instance
_config: Optional[LLMConfig] = None


def get_config() -> LLMConfig:
    """
    Get global configuration instance (singleton pattern).
    
    Returns:
        LLMConfig instance
    """
    global _config
    if _config is None:
        _config = LLMConfig()
    return _config


def reload_config() -> LLMConfig:
    """
    Reload configuration from environment variables.
    
    Useful for testing or when environment changes.
    
    Returns:
        New LLMConfig instance
    """
    global _config
    _config = LLMConfig()
    return _config
