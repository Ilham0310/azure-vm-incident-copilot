"""
Unit tests for LLM configuration management
"""

import os
import pytest
from pathlib import Path
from src.llm.config import LLMConfig, get_config, reload_config


class TestLLMConfig:
    """Test suite for LLMConfig class"""
    
    def test_default_values(self, monkeypatch):
        """Test that default values are used when env vars not set"""
        # Clear all LLM-related env vars
        for key in [
            "GROQ_API_KEY", "GEMINI_API_KEY", "OLLAMA_BASE_URL",
            "RAG_TOP_K", "SOP_TOP_K", "EMBEDDING_MODEL",
            "CHROMA_MEMORY_PATH", "CHROMA_SOP_PATH",
            "LLM_ENABLED", "LLM_SHADOW_MODE"
        ]:
            monkeypatch.delenv(key, raising=False)
        
        config = LLMConfig()
        
        assert config.groq_api_key is None
        assert config.gemini_api_key is None
        assert config.ollama_base_url == "http://localhost:11434"
        assert config.rag_top_k == 5
        assert config.sop_top_k == 3
        assert config.embedding_model == "all-MiniLM-L6-v2"
        assert config.chroma_memory_path == "data/chroma_memory"
        assert config.chroma_sop_path == "data/chroma_sops"
        assert config.llm_enabled is False
        assert config.llm_shadow_mode is False
    
    def test_environment_variable_loading(self, monkeypatch):
        """Test that environment variables are loaded correctly"""
        monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
        monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://custom:8080")
        monkeypatch.setenv("RAG_TOP_K", "10")
        monkeypatch.setenv("SOP_TOP_K", "5")
        monkeypatch.setenv("EMBEDDING_MODEL", "custom-model")
        monkeypatch.setenv("LLM_ENABLED", "true")
        monkeypatch.setenv("LLM_SHADOW_MODE", "yes")
        
        config = LLMConfig()
        
        assert config.groq_api_key == "test-groq-key"
        assert config.gemini_api_key == "test-gemini-key"
        assert config.ollama_base_url == "http://custom:8080"
        assert config.rag_top_k == 10
        assert config.sop_top_k == 5
        assert config.embedding_model == "custom-model"
        assert config.llm_enabled is True
        assert config.llm_shadow_mode is True
    
    def test_invalid_rag_top_k_uses_default(self, monkeypatch, caplog):
        """Test that invalid RAG_TOP_K uses default and logs warning"""
        monkeypatch.setenv("RAG_TOP_K", "-1")
        
        config = LLMConfig()
        
        assert config.rag_top_k == 5  # default
        assert "not positive" in caplog.text
    
    def test_invalid_sop_top_k_uses_default(self, monkeypatch, caplog):
        """Test that invalid SOP_TOP_K uses default and logs warning"""
        monkeypatch.setenv("SOP_TOP_K", "0")
        
        config = LLMConfig()
        
        assert config.sop_top_k == 3  # default
        assert "not positive" in caplog.text
    
    def test_invalid_ollama_url(self, monkeypatch):
        """Test that invalid OLLAMA_BASE_URL raises ValueError"""
        monkeypatch.setenv("OLLAMA_BASE_URL", "not-a-url")
        
        with pytest.raises(ValueError, match="OLLAMA_BASE_URL"):
            LLMConfig()
    
    def test_non_numeric_rag_top_k_uses_default(self, monkeypatch, caplog):
        """Test that non-numeric RAG_TOP_K uses default and logs warning"""
        monkeypatch.setenv("RAG_TOP_K", "not-a-number")
        
        config = LLMConfig()
        
        assert config.rag_top_k == 5  # default
        assert "not a valid integer" in caplog.text
    
    def test_has_any_provider(self, monkeypatch):
        """Test has_any_provider method"""
        # No providers
        for key in ["GROQ_API_KEY", "GEMINI_API_KEY"]:
            monkeypatch.delenv(key, raising=False)
        
        config = LLMConfig()
        assert config.has_any_provider() is True  # Ollama is always available
        
        # With Groq
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        config = LLMConfig()
        assert config.has_any_provider() is True
    
    def test_get_available_providers(self, monkeypatch):
        """Test get_available_providers method"""
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        
        config = LLMConfig()
        providers = config.get_available_providers()
        
        assert "ollama" in providers
        assert "groq" not in providers
        assert "gemini" not in providers
        
        # Add Groq
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        config = LLMConfig()
        providers = config.get_available_providers()
        
        assert "groq" in providers
        assert "ollama" in providers
    
    def test_boolean_parsing(self, monkeypatch):
        """Test boolean environment variable parsing"""
        test_cases = [
            ("true", True),
            ("True", True),
            ("TRUE", True),
            ("1", True),
            ("yes", True),
            ("on", True),
            ("false", False),
            ("False", False),
            ("0", False),
            ("no", False),
            ("off", False),
            ("", False),
        ]
        
        for value, expected in test_cases:
            monkeypatch.setenv("LLM_ENABLED", value)
            config = LLMConfig()
            assert config.llm_enabled == expected, f"Failed for value: {value}"
    
    def test_directory_creation(self, monkeypatch, tmp_path):
        """Test that ChromaDB directories are created if they don't exist"""
        memory_path = tmp_path / "test_memory"
        sop_path = tmp_path / "test_sops"
        
        monkeypatch.setenv("CHROMA_MEMORY_PATH", str(memory_path))
        monkeypatch.setenv("CHROMA_SOP_PATH", str(sop_path))
        
        config = LLMConfig()
        
        assert memory_path.exists()
        assert sop_path.exists()
        assert config.chroma_memory_path == str(memory_path)
        assert config.chroma_sop_path == str(sop_path)
    
    def test_singleton_pattern(self, monkeypatch):
        """Test that get_config returns the same instance"""
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        
        # Clear singleton
        import src.llm.config as config_module
        config_module._config = None
        
        config1 = get_config()
        config2 = get_config()
        
        assert config1 is config2
    
    def test_reload_config(self, monkeypatch):
        """Test that reload_config creates a new instance"""
        import src.llm.config as config_module
        config_module._config = None
        
        monkeypatch.setenv("RAG_TOP_K", "5")
        config1 = get_config()
        assert config1.rag_top_k == 5
        
        monkeypatch.setenv("RAG_TOP_K", "10")
        config2 = reload_config()
        assert config2.rag_top_k == 10
        assert config1 is not config2
