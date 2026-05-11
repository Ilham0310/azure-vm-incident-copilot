# LLM Setup Guide

## Overview

This guide walks you through setting up LLM providers for the Azure VM Incident Copilot. The system supports three LLM providers with automatic fallback: Groq (primary), Gemini (fallback), and Ollama (local fallback). You need at least one provider configured for LLM features to work.

## Quick Start

**Minimum requirement**: Set up at least one LLM provider (Groq recommended for best performance).

```bash
# 1. Copy environment template
cp .env.example .env

# 2. Add your API key (choose one or more)
# Edit .env and add:
GROQ_API_KEY=your-groq-api-key-here
# or
GEMINI_API_KEY=your-gemini-api-key-here
# or install Ollama (see below)

# 3. Enable LLM features
echo "LLM_ENABLED=true" >> .env

# 4. Initialize SOP knowledge base (first time only)
python -m setup.initialize_sop_kb

# 5. Start the system
python main.py --ui
```

## Provider Setup

### Option 1: Groq (Recommended - Fastest)

Groq provides the fastest inference with Llama 3.3 70B model.

**Free Tier**: 30 requests/minute, no credit card required

**Setup Steps**:

1. **Get API Key**:
   - Visit: https://console.groq.com/keys
   - Sign up for a free account (GitHub/Google login available)
   - Click "Create API Key"
   - Copy the key (starts with `gsk_`)

2. **Add to .env**:
   ```bash
   GROQ_API_KEY=gsk_your_actual_key_here
   ```

3. **Verify**:
   ```bash
   python -c "from src.llm.groq_provider import GroqProvider; print('Available' if GroqProvider().is_available() else 'Not available')"
   ```

**Troubleshooting**:
- **"Invalid API key"**: Verify the key starts with `gsk_` and has no extra spaces
- **"Rate limit exceeded"**: Free tier allows 30 req/min. Wait 60 seconds or upgrade
- **"Connection error"**: Check internet connectivity

### Option 2: Gemini (Fallback)

Google's Gemini 2.0 Flash provides good performance as a fallback option.

**Free Tier**: 1500 requests/day, no credit card required

**Setup Steps**:

1. **Get API Key**:
   - Visit: https://aistudio.google.com/apikey
   - Sign in with Google account
   - Click "Create API Key"
   - Copy the key

2. **Add to .env**:
   ```bash
   GEMINI_API_KEY=your_actual_key_here
   ```

3. **Verify**:
   ```bash
   python -c "from src.llm.gemini_provider import GeminiProvider; print('Available' if GeminiProvider().is_available() else 'Not available')"
   ```

**Troubleshooting**:
- **"API key not valid"**: Verify you copied the complete key
- **"Quota exceeded"**: Free tier allows 1500 req/day. Resets at midnight PT
- **"Region not supported"**: Gemini may not be available in all regions. Use VPN or try Groq/Ollama

### Option 3: Ollama (Local - No API Key)

Ollama runs models locally on your machine. No API key required, unlimited requests, works offline.

**Requirements**: 8GB RAM minimum, 16GB recommended

**Setup Steps**:

1. **Install Ollama**:
   
   **Windows**:
   - Download: https://ollama.com/download/windows
   - Run the installer
   - Ollama starts automatically as a service

   **macOS**:
   - Download: https://ollama.com/download/mac
   - Drag to Applications folder
   - Launch Ollama from Applications

   **Linux**:
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ```

2. **Pull the Model**:
   ```bash
   ollama pull llama3.2
   ```
   
   This downloads ~2GB. Wait for completion.

3. **Verify Ollama is Running**:
   ```bash
   curl http://localhost:11434/api/tags
   ```
   
   Should return JSON with available models.

4. **Add to .env** (optional, uses default):
   ```bash
   OLLAMA_BASE_URL=http://localhost:11434
   ```

5. **Verify**:
   ```bash
   python -c "from src.llm.ollama_provider import OllamaProvider; print('Available' if OllamaProvider().is_available() else 'Not available')"
   ```

**Troubleshooting**:
- **"Connection refused"**: Ollama service not running
  - Windows: Check system tray for Ollama icon
  - macOS: Launch Ollama from Applications
  - Linux: `sudo systemctl start ollama`
- **"Model not found"**: Run `ollama pull llama3.2`
- **"Out of memory"**: Ollama requires 8GB RAM. Close other applications or use smaller model: `ollama pull llama3.2:1b`

## Provider Fallback Chain

The system automatically tries providers in order:

```
Groq (fastest, ~1-2s)
  ↓ fails
Gemini (medium, ~2-3s)
  ↓ fails
Ollama (slower, ~5-15s, offline)
  ↓ fails
Rule Engine (instant, deterministic fallback)
```

**Best Practice**: Configure at least two providers for reliability.

## Configuration

### Environment Variables

Edit your `.env` file:

```bash
# ============================================
# LLM Provider Configuration
# ============================================

# Groq API (Primary - Fastest)
GROQ_API_KEY=gsk_your_key_here

# Gemini API (Fallback)
GEMINI_API_KEY=your_key_here

# Ollama (Local - No API Key)
OLLAMA_BASE_URL=http://localhost:11434

# ============================================
# RAG Configuration
# ============================================

# Number of similar past incidents to retrieve (default: 5)
RAG_TOP_K=5

# Number of relevant SOPs to retrieve (default: 3)
SOP_TOP_K=3

# Embedding model (default: all-MiniLM-L6-v2)
EMBEDDING_MODEL=all-MiniLM-L6-v2

# ChromaDB persistence paths
CHROMA_MEMORY_PATH=data/chroma_memory
CHROMA_SOP_PATH=data/chroma_sops

# ============================================
# LLM Feature Flags
# ============================================

# Enable LLM-based decision engine (default: false)
LLM_ENABLED=true

# Enable shadow mode (default: false)
# Runs both rule-based and LLM engines and compares outputs
LLM_SHADOW_MODE=false
```

### Feature Flags

**LLM_ENABLED**:
- `false` (default): Use rule-based pattern matching
- `true`: Use LLM-based reasoning with RAG

**LLM_SHADOW_MODE**:
- `false` (default): Use single engine (rule-based or LLM)
- `true`: Run both engines and compare outputs (always returns rule-based result)

**Recommendation**: Start with `LLM_SHADOW_MODE=true` to validate LLM accuracy before enabling fully.

## Initialize SOP Knowledge Base

The SOP knowledge base must be initialized before first use:

```bash
python -m setup.initialize_sop_kb
```

This loads 12 Standard Operating Procedures into ChromaDB:
- Azure Start/Stop VMs
- Azure Firewall Whitelisting
- Azure VM Scale Up/Down
- Azure Disk Cleanup
- Azure VM Disk Expansion
- Azure System Backup
- Azure Request Admin Access
- Azure Request Cloud Resource Access
- Azure URL Onboarding
- Azure FinOps Rightsize
- Azure SSL Certificate Renewal
- Azure Decommission VM

**Output**:
```
Initializing SOP Knowledge Base...
Loading SOPs from data/sops/...
✓ Loaded 12 SOPs
✓ Generated embeddings
✓ Stored in ChromaDB at data/chroma_sops/
SOP Knowledge Base initialized successfully!
```

**Troubleshooting**:
- **"No SOPs found"**: Ensure `data/sops/*.md` files exist
- **"ChromaDB error"**: Check `data/chroma_sops/` directory is writable
- **"Embedding model download failed"**: Check internet connection, model downloads automatically (~22MB)

## Verify Setup

### Check Provider Status

```bash
python -c "
from src.llm.llm_engine import LLMDecisionEngine
engine = LLMDecisionEngine()
status = engine.get_provider_status()
for provider, state in status.items():
    print(f'{provider}: {state}')
"
```

**Expected Output**:
```
groq: available
gemini: available
ollama: unavailable
```

### Check Health Endpoint

Start the UI and check health:

```bash
python main.py --ui
# In another terminal:
curl http://localhost:8000/health | jq
```

**Expected Output**:
```json
{
  "status": "healthy",
  "providers": {
    "groq": "available",
    "gemini": "available",
    "ollama": "unavailable"
  },
  "active_provider": "groq",
  "memory_store": {
    "total_incidents": 0,
    "collection_status": "ok"
  },
  "sop_kb": {
    "total_sops": 12,
    "collection_status": "ok"
  }
}
```

### Test LLM Decision

Create a test telemetry file `test_incident.json`:

```json
{
  "power_state": "Running",
  "provisioning_state": "Succeeded",
  "resource_health_status": "Available",
  "heartbeat_present": false,
  "azure_vm_agent_status": "NotReporting",
  "cpu_percent": 22.5,
  "memory_percent": 67.0
}
```

Run triage:

```bash
python main.py --input test_incident.json
```

**Expected Output** (with LLM enabled):
```json
{
  "decision": "diagnose",
  "diagnosis": "Azure VM agent has stopped reporting...",
  "confidence_score": 0.84,
  "llm_provider": "groq",
  "similar_incidents_used": 0,
  "sops_consulted": ["SOP_Azure Request Admin Access"],
  ...
}
```

## Common Issues

### No LLM Providers Available

**Symptom**: Warning "No LLM API keys configured. Falling back to rule-based engine."

**Solution**: Set at least one API key in `.env`:
```bash
GROQ_API_KEY=gsk_your_key_here
```

### All Providers Failing

**Symptom**: Every request falls back to rule engine

**Checklist**:
1. Verify API keys are correct (no extra spaces)
2. Check internet connectivity
3. Verify rate limits not exceeded
4. Check Ollama is running: `curl http://localhost:11434/api/tags`
5. Review logs: `tail -f logs/llm_decisions.jsonl`

### Slow Performance

**Symptom**: Triage takes >10 seconds

**Solutions**:
- Use Groq as primary provider (fastest: ~1-2s)
- Reduce `RAG_TOP_K` and `SOP_TOP_K` in `.env`
- Ensure Ollama is not the active provider (check `/health` endpoint)
- Check network latency to API providers

### Embedding Model Download Failed

**Symptom**: "Failed to load embedding model"

**Solutions**:
1. Check internet connection
2. Manually download model:
   ```python
   from sentence_transformers import SentenceTransformer
   model = SentenceTransformer('all-MiniLM-L6-v2')
   ```
3. If behind proxy, set environment variables:
   ```bash
   export HTTP_PROXY=http://proxy:port
   export HTTPS_PROXY=http://proxy:port
   ```

### SOP Knowledge Base Empty

**Symptom**: Health check shows `"total_sops": 0`

**Solution**: Initialize the SOP knowledge base:
```bash
python -m setup.initialize_sop_kb
```

## Performance Benchmarks

Typical latency by provider (P95):

| Provider | Latency | Notes |
|----------|---------|-------|
| Groq | 1-2s | Fastest, recommended for production |
| Gemini | 2-3s | Good fallback, slightly slower |
| Ollama | 5-15s | Local, no API key, works offline |
| Rule Engine | <50ms | Deterministic fallback |

**Total Pipeline Latency** (with RAG):
- RAG retrieval: ~200-500ms
- LLM inference: 1-15s (depends on provider)
- Safety guard: <10ms
- **Total**: 2-10s for 95% of requests (with Groq)

## Best Practices

1. **Use Groq as primary**: Fastest and most reliable for production
2. **Configure multiple providers**: Ensures availability if one fails
3. **Start with shadow mode**: Validate LLM accuracy before full deployment
4. **Monitor rate limits**: Groq (30/min), Gemini (1500/day)
5. **Keep Ollama as fallback**: Works offline, no rate limits
6. **Initialize SOPs first**: Required for next_check recommendations
7. **Check health endpoint**: Monitor provider status regularly

## Next Steps

After setup:

1. **Validate with shadow mode**: See [Shadow Mode Guide](shadow_mode_guide.md)
2. **Configure RAG settings**: See [LLM Configuration Guide](llm_configuration.md)
3. **Migrate from rule-based**: See [Migration Guide](migration_to_llm.md)
4. **Use feedback loop**: See [Feedback API Documentation](feedback_api.md)

## Support

For issues not covered here:

1. Check logs: `logs/llm_decisions.jsonl`, `logs/rag_retrievals.jsonl`
2. Review health endpoint: `curl http://localhost:8000/health`
3. Test providers individually using verification commands above
4. Consult [Troubleshooting Guide](../TROUBLESHOOTING.md)

## API Key Security

**Important**: Never commit API keys to version control!

- Store keys in `.env` file (already in `.gitignore`)
- Use environment variables in production
- Rotate keys periodically
- Use separate keys for dev/staging/production

**Production Deployment**:
```bash
# Set environment variables instead of .env file
export GROQ_API_KEY=gsk_production_key
export GEMINI_API_KEY=production_key
export LLM_ENABLED=true
```
