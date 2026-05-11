# LLM Configuration Guide

This guide explains how to configure the LLM Decision Engine with RAG capabilities.

## Overview

The LLM Decision Engine uses a centralized configuration system (`src/llm/config.py`) that loads all settings from environment variables with sensible defaults. Configuration is validated on startup, and directories are created automatically.

## Configuration File

All configuration is managed through environment variables, typically stored in a `.env` file at the project root. Use `.env.example` as a template:

```bash
cp .env.example .env
```

## Configuration Sections

### 1. LLM Provider Configuration

Configure API keys for the LLM providers. The system uses a fallback chain: Groq → Gemini → Ollama → Rule Engine.

```bash
# Groq API (Primary Provider - Fastest)
# Get your API key from: https://console.groq.com/keys
GROQ_API_KEY=your-groq-api-key-here

# Gemini API (Fallback Provider)
# Get your API key from: https://aistudio.google.com/apikey
GEMINI_API_KEY=your-gemini-api-key-here

# Ollama (Local Provider - No API Key Required)
# Install from: https://ollama.com/download
# Default: http://localhost:11434
OLLAMA_BASE_URL=http://localhost:11434
```

**Notes:**
- At least one provider should be configured for LLM features to work
- If no API keys are set, the system will attempt to use Ollama
- If Ollama is not running, the system falls back to the rule-based engine

### 2. RAG Configuration

Configure the Retrieval-Augmented Generation (RAG) system:

```bash
# Number of similar past incidents to retrieve (default: 5)
RAG_TOP_K=5

# Number of relevant SOPs to retrieve (default: 3)
SOP_TOP_K=3

# Embedding model for vector generation (default: all-MiniLM-L6-v2)
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

**Notes:**
- `RAG_TOP_K` must be a positive integer (1-10 recommended)
- `SOP_TOP_K` must be a positive integer (1-5 recommended)
- The embedding model is downloaded automatically on first run (~22MB)

### 3. ChromaDB Storage Paths

Configure where incident memory and SOP knowledge base are stored:

```bash
# ChromaDB persistence paths
CHROMA_MEMORY_PATH=data/chroma_memory
CHROMA_SOP_PATH=data/chroma_sops
```

**Notes:**
- Directories are created automatically if they don't exist
- Paths must be writable by the application
- Use absolute paths if running from different working directories

### 4. Feature Flags

Enable or disable LLM features:

```bash
# Enable LLM-based decision engine (default: false)
LLM_ENABLED=false

# Enable shadow mode (default: false)
# Runs both rule-based and LLM engines and compares outputs
LLM_SHADOW_MODE=false
```

**Notes:**
- Set `LLM_ENABLED=true` to use LLM instead of rule-based engine
- Set `LLM_SHADOW_MODE=true` to run both engines and log differences
- Shadow mode is useful for validating LLM accuracy before full rollout

## Configuration Validation

The configuration system validates all settings on startup:

### Automatic Validation

- **Positive integers**: `RAG_TOP_K` and `SOP_TOP_K` must be positive
- **URL format**: `OLLAMA_BASE_URL` must be a valid URL
- **Directory permissions**: ChromaDB paths must be writable
- **Invalid values**: Non-numeric values use defaults with warnings

### Warnings

The system logs warnings for:
- Missing API keys (Groq, Gemini)
- Invalid configuration values (uses defaults)
- No LLM providers configured

### Errors

The system raises errors for:
- Invalid URL format for `OLLAMA_BASE_URL`
- Non-writable ChromaDB directories
- Negative or zero values for `RAG_TOP_K` or `SOP_TOP_K` after parsing

## Using the Configuration

### In Python Code

```python
from src.llm.config import get_config

# Get configuration (singleton)
config = get_config()

# Access settings
print(f"Groq API Key: {config.groq_api_key}")
print(f"RAG Top-K: {config.rag_top_k}")
print(f"Memory Path: {config.chroma_memory_path}")

# Check provider availability
if config.has_any_provider():
    providers = config.get_available_providers()
    print(f"Available providers: {providers}")
```

### Reload Configuration

```python
from src.llm.config import reload_config

# Reload after environment changes
config = reload_config()
```

## Testing Configuration

Run the configuration test example:

```bash
python -m examples.test_config
```

This will display:
- All configuration values
- Provider availability
- Warnings for missing settings

## Troubleshooting

### No LLM Providers Available

**Symptom**: Warning "No LLM API keys configured"

**Solution**: Set at least one API key:
```bash
export GROQ_API_KEY="your-key-here"
# or
export GEMINI_API_KEY="your-key-here"
```

### Invalid Configuration Value

**Symptom**: Warning "RAG_TOP_K=abc is not a valid integer"

**Solution**: Set a valid positive integer:
```bash
export RAG_TOP_K=5
```

### Directory Not Writable

**Symptom**: Error "CHROMA_MEMORY_PATH directory is not writable"

**Solution**: Ensure the directory exists and has write permissions:
```bash
mkdir -p data/chroma_memory
chmod 755 data/chroma_memory
```

### Ollama Connection Failed

**Symptom**: "Ollama provider unavailable"

**Solution**: 
1. Install Ollama: https://ollama.com/download
2. Start Ollama: `ollama serve`
3. Pull the model: `ollama pull llama3.2`

## Best Practices

1. **Use .env file**: Store configuration in `.env` file (not committed to git)
2. **Set API keys**: Configure at least Groq or Gemini for best performance
3. **Start with defaults**: Use default values for RAG settings initially
4. **Enable shadow mode**: Test LLM accuracy before enabling fully
5. **Monitor logs**: Check logs for configuration warnings on startup

## Configuration Reference

| Variable | Type | Default | Required | Description |
|----------|------|---------|----------|-------------|
| `GROQ_API_KEY` | string | None | No | Groq API key for primary LLM |
| `GEMINI_API_KEY` | string | None | No | Gemini API key for fallback LLM |
| `OLLAMA_BASE_URL` | URL | http://localhost:11434 | No | Ollama server URL |
| `RAG_TOP_K` | int | 5 | No | Number of similar incidents to retrieve |
| `SOP_TOP_K` | int | 3 | No | Number of SOPs to retrieve |
| `EMBEDDING_MODEL` | string | all-MiniLM-L6-v2 | No | Sentence transformer model |
| `CHROMA_MEMORY_PATH` | path | data/chroma_memory | No | Incident memory storage path |
| `CHROMA_SOP_PATH` | path | data/chroma_sops | No | SOP knowledge base path |
| `LLM_ENABLED` | bool | false | No | Enable LLM decision engine |
| `LLM_SHADOW_MODE` | bool | false | No | Run both engines and compare |

## See Also

- [LLM Setup Guide](llm_setup.md) - Getting API keys and installing Ollama
- [RAG Memory Guide](rag_memory.md) - Understanding the memory store
- [SOP Knowledge Base](sop_knowledge.md) - Managing SOPs
