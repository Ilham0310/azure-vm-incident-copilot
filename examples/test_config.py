"""
Example: Testing LLM Configuration

This script demonstrates how to use the centralized LLM configuration.
"""

import logging
from src.llm.config import get_config

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """Test configuration loading"""
    logger.info("Loading LLM configuration...")
    
    try:
        config = get_config()
        
        logger.info("\n" + "="*60)
        logger.info("LLM Configuration Summary")
        logger.info("="*60)
        
        # Provider Configuration
        logger.info("\nProvider Configuration:")
        logger.info(f"  Groq API Key: {'✓ Configured' if config.groq_api_key else '✗ Not set'}")
        logger.info(f"  Gemini API Key: {'✓ Configured' if config.gemini_api_key else '✗ Not set'}")
        logger.info(f"  Ollama URL: {config.ollama_base_url}")
        
        # RAG Configuration
        logger.info("\nRAG Configuration:")
        logger.info(f"  RAG Top-K: {config.rag_top_k}")
        logger.info(f"  SOP Top-K: {config.sop_top_k}")
        logger.info(f"  Embedding Model: {config.embedding_model}")
        
        # Storage Paths
        logger.info("\nStorage Paths:")
        logger.info(f"  Memory Path: {config.chroma_memory_path}")
        logger.info(f"  SOP Path: {config.chroma_sop_path}")
        
        # Feature Flags
        logger.info("\nFeature Flags:")
        logger.info(f"  LLM Enabled: {config.llm_enabled}")
        logger.info(f"  Shadow Mode: {config.llm_shadow_mode}")
        
        # Provider Availability
        logger.info("\nProvider Availability:")
        available_providers = config.get_available_providers()
        for provider in available_providers:
            logger.info(f"  {provider}: potentially available")
        
        logger.info("\n" + "="*60)
        
        if not config.has_any_provider():
            logger.warning(
                "\n⚠️  No LLM providers configured! "
                "Set GROQ_API_KEY or GEMINI_API_KEY in .env file."
            )
        else:
            logger.info("\n✓ Configuration loaded successfully!")
        
    except Exception as e:
        logger.error(f"Configuration error: {e}")
        raise


if __name__ == "__main__":
    main()
