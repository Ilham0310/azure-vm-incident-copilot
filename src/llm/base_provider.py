"""
Base LLM Provider Interface

Defines the abstract interface that all LLM providers must implement.
Supports provider fallback chain and JSON mode enforcement.
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class ProviderMetadata:
    """Metadata about an LLM provider"""
    name: str
    model: str
    rate_limit_rpm: Optional[int] = None  # Requests per minute
    rate_limit_rpd: Optional[int] = None  # Requests per day
    supports_json_mode: bool = True
    requires_api_key: bool = True
    is_local: bool = False


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    
    All providers must implement:
    - is_available(): Check if provider is configured and accessible
    - generate(): Generate a response from the LLM
    - supports_json_mode(): Whether the provider supports JSON output mode
    """
    
    def __init__(self):
        self._metadata: Optional[ProviderMetadata] = None
    
    @property
    def metadata(self) -> ProviderMetadata:
        """Get provider metadata"""
        if self._metadata is None:
            raise NotImplementedError("Provider must set _metadata in __init__")
        return self._metadata
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if the provider is available and configured.
        
        Returns:
            True if provider can be used, False otherwise
        """
        pass
    
    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 2000
    ) -> str:
        """
        Generate a response from the LLM.
        
        Args:
            system_prompt: System-level instructions for the LLM
            user_prompt: User query/context for the LLM
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens in response
            
        Returns:
            Raw LLM response as string (should be JSON if supports_json_mode)
            
        Raises:
            Exception: If generation fails
        """
        pass
    
    def supports_json_mode(self) -> bool:
        """
        Check if provider supports JSON output mode.
        
        Returns:
            True if provider can enforce JSON output
        """
        return self.metadata.supports_json_mode
    
    def __str__(self) -> str:
        return f"{self.metadata.name} ({self.metadata.model})"
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.metadata.name}>"
