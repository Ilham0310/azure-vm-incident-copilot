# Azure VM Incident Copilot

A read-only diagnostic system for Azure VM incidents that automates triage for server down, SSH/RDP failures, performance degradation, network issues, and boot failures.

## Overview

The Azure VM Incident Copilot is a read-only, LLM-augmented diagnostic system that automates triage for Azure VM incidents. The system accepts structured Azure VM telemetry in JSON format, validates it against a comprehensive triage schema with 30+ telemetry fields, uses LLM reasoning with Retrieval-Augmented Generation (RAG) to diagnose issues, and returns structured diagnostic output with diagnosis, evidence, gaps, and next steps.

### Key Features

- **LLM-Based Decision Engine**: Uses Groq/Gemini/Ollama for intelligent reasoning beyond hardcoded patterns
- **RAG Memory Store**: Learns from past incidents and human feedback for continuous improvement
- **SOP Knowledge Base**: Consults 12+ Standard Operating Procedures for actionable recommendations
- **Novel Incident Detection**: Identifies new failure patterns outside the 20 predefined incident types
- **Read-Only Operation**: No write operations or remediation actions are executed
- **Safety-First**: Six deterministic safety rules override LLM output unconditionally
- **Multi-Provider Fallback**: Automatic switching between Groq → Gemini → Ollama → Rule Engine
- **Shadow Mode**: Validate LLM accuracy by running both engines in parallel
- **Modular Architecture**: Clear separation of concerns across seven components
- **Comprehensive Validation**: 30+ telemetry fields with strict type and range constraints
- **Property-Based Testing**: 20 correctness properties with 100+ iterations per property

## Installation

1. Clone the repository
2. Install runtime dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Install test dependencies (optional):
   ```bash
   pip install -r requirements-test.txt
   ```
4. Configure environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your Azure credentials and LLM API keys
   ```
5. Set up LLM providers (at least one required for LLM features):
   - **Groq** (recommended): Get API key from https://console.groq.com/keys
   - **Gemini** (fallback): Get API key from https://aistudio.google.com/apikey
   - **Ollama** (local): Install from https://ollama.com/download
   
   See [LLM Setup Guide](docs/llm_setup.md) for detailed instructions.

## Setup

Before running the system for the first time, generate required configuration files:

```bash
python main.py --setup
```

This creates:
- `schemas/azure_vm_triage_schema.json` - Input validation schema
- `schemas/output_schema.json` - Output validation schema
- `policy/decision_policy.json` - Decision policy rules and safety rules
- `data/benchmark_cases.csv` - 35 benchmark test cases

Alternatively, run the standalone setup script:

```bash
python setup/run_setup.py
```

### Initialize SOP Knowledge Base (Required for LLM Features)

If using LLM-based decision engine, initialize the SOP knowledge base:

```bash
python -m setup.initialize_sop_kb
```

This loads 12 Standard Operating Procedures into ChromaDB for RAG-based recommendations.

### Environment Variables

Configure your Azure credentials and LLM providers in a `.env` file:

```bash
cp .env.example .env
```

**Azure Credentials** (required for agent mode):

```
AZURE_TENANT_ID=your-tenant-id-here
AZURE_CLIENT_ID=your-client-id-here
AZURE_CLIENT_SECRET=your-client-secret-here
AZURE_SUBSCRIPTION_ID=your-subscription-id-here
AZURE_RESOURCE_GROUP=your-resource-group-here
AZURE_VM_NAME=your-vm-name-here
AZURE_WORKSPACE_ID=your-workspace-id-here
```

**LLM Configuration** (required for LLM features):

```
# At least one provider required
GROQ_API_KEY=your-groq-api-key-here
GEMINI_API_KEY=your-gemini-api-key-here
OLLAMA_BASE_URL=http://localhost:11434

# Enable LLM features
LLM_ENABLED=true

# Optional: Enable shadow mode for validation
LLM_SHADOW_MODE=false
```

See [LLM Setup Guide](docs/llm_setup.md) for detailed provider setup instructions.

The `.env` file is automatically loaded when running `main.py`. Never commit `.env` to version control.

## Usage

### Single Case Triage

Process a single telemetry file:

```bash
python main.py --input incident.json
```

Write output to a file:

```bash
python main.py --input incident.json --output result.json
```

### Benchmark Testing

Process all benchmark cases:

```bash
python main.py --benchmark data/benchmark_cases.csv
```

## Input Format

The system accepts JSON telemetry with 30+ fields including:

- **Power State**: Running, Stopped, Deallocated, Failed, Unknown
- **Provisioning State**: Succeeded, Failed, In Progress, Unknown
- **Resource Health**: Available, Degraded, Unavailable, Unknown
- **Boot Diagnostics**: Normal, BSOD, KernelPanic, Stuck, Unknown
- **Metrics**: CPU, memory, disk latency, disk usage
- **Network**: NSG rules, connection troubleshoot results
- **Agents**: VM agent status, monitor agent status, app health

See `schemas/azure_vm_triage_schema.json` for complete field definitions.

## Output Format

The system returns structured JSON with 11+ fields:

**Core Fields**:
- `decision`: diagnose | diagnose_low_confidence | abstain_request_next_check
- `diagnosis`: Human-readable description of the issue
- `confidence_score`: Float 0.0-1.0 indicating diagnostic certainty
- `evidence`: List of telemetry signals supporting the diagnosis
- `evidence_gap`: List of missing or incomplete signals
- `next_check`: Specific diagnostic action to gather more information
- `explanation`: Reasoning for the decision

**LLM Metadata** (when LLM_ENABLED=true):
- `incident_id`: 12-character hex identifier for feedback tracking
- `llm_provider`: Provider used (groq, gemini, ollama, or rule_engine_fallback)
- `similar_incidents_used`: Number of past incidents retrieved from RAG memory
- `sops_consulted`: List of SOPs referenced in next_check recommendations
- `is_novel_incident`: Boolean flag indicating if this is a new pattern
- `pattern_matched`: Pattern name or "llm_detected_<name>" for novel incidents
- `safety_rules_applied`: List of safety rules that overrode LLM output

## Decision Policy

The system applies three decision rules:

- **diagnose**: Confidence ≥ 0.70, completeness ≥ 90%, no conflicts
- **diagnose_low_confidence**: Confidence 0.40-0.69, completeness 60-89%, minor conflicts
- **abstain_request_next_check**: Confidence < 0.40, completeness < 60%, or safety rule violation

### LLM vs Rule-Based Engine

**Rule-Based Engine** (default, `LLM_ENABLED=false`):
- Uses 20 hardcoded incident patterns with exact matching
- Deterministic: identical inputs produce identical outputs
- Fast: <50ms decision time
- Limited to predefined patterns

**LLM Engine** (`LLM_ENABLED=true`):
- Uses Groq/Gemini/Ollama for intelligent reasoning
- Retrieves similar past incidents from RAG memory (top 5)
- Consults relevant SOPs from knowledge base (top 3)
- Detects novel incidents outside 20 predefined patterns
- Learns from human feedback via feedback loop
- Slower: 2-10s decision time (depends on provider)
- All safety rules still enforced deterministically

**Shadow Mode** (`LLM_SHADOW_MODE=true`):
- Runs both engines in parallel
- Compares outputs and logs differences
- Always returns rule-based result (safe validation)
- Use for validating LLM accuracy before full deployment

## Safety Rules

Six hard constraints prevent unsafe suggestions (enforced deterministically, override LLM output):

1. **Platform Event Safety**: Never suggest restart during platform maintenance
2. **Boot Failure Safety**: Never suggest restart for BSOD/KernelPanic
3. **Low Confidence Destructive Action Safety**: Prevent destructive actions when confidence < 0.9
4. **Network Security Safety**: Never suggest disabling NSG/firewall rules
5. **Disk Safety**: Prevent disk deletion/OS reset when confidence < 0.9
6. **Failed State Safety**: Never suggest auto-remediation for failed VMs

**Important**: Safety rules are applied AFTER LLM output generation and override any unsafe suggestions unconditionally. The LLM cannot bypass safety rules.

## Testing

Run all tests:

```bash
pytest tests/ -v
```

Run with coverage:

```bash
pytest tests/ -v --cov=src --cov-report=term
```

Run only property-based tests:

```bash
pytest tests/property/ -v
```

Run only unit tests:

```bash
pytest tests/unit/ -v
```

## Project Structure

```
.
├── main.py                  # CLI entry point
├── setup/                   # Setup generators
│   ├── run_setup.py        # Standalone setup runner
│   ├── generate_schema.py
│   ├── generate_output_schema.py
│   ├── generate_policy.py
│   └── generate_benchmark.py
├── src/                     # Source code
│   ├── models.py           # Pydantic models and enums
│   ├── validator.py        # Schema validation
│   ├── confidence_scorer.py # Confidence calculation
│   ├── decision_engine.py  # Decision policy
│   ├── explanation_formatter.py # Output formatting
│   ├── benchmark_loader.py # Benchmark loading
│   └── test_harness.py     # Benchmark testing
├── tests/                   # Test suite
│   ├── unit/               # Unit tests
│   └── property/           # Property-based tests
├── schemas/                 # Generated schemas
├── policy/                  # Generated policy
├── data/                    # Generated benchmark data
└── docs/                    # Documentation

```

## Requirements

- Python 3.8 or higher
- No Azure connectivity required for local testing (runs entirely locally)
- For LLM features: At least one LLM provider configured (Groq/Gemini API key or Ollama installed)
- For agent mode: Azure credentials with read permissions

## License

Research project - see LICENSE file for details.

## Documentation

### Getting Started
- [Setup Guide](SETUP_GUIDE.md) - Complete end-to-end setup instructions
- [LLM Setup Guide](docs/llm_setup.md) - 🤖 Configure LLM providers (Groq, Gemini, Ollama)
- [Web Dashboard Guide](WEB_DASHBOARD_GUIDE.md) - 🌐 Run Azure Agent through your browser (no command line!)
- [Quick Reference](QUICK_REFERENCE.md) - Common commands and quick tips
- [Project Checklist](PROJECT_CHECKLIST.md) - Track your setup progress
- [Troubleshooting](TROUBLESHOOTING.md) - Solutions to common issues
- [FAQ](FAQ.md) - Frequently asked questions
- [Documentation Index](DOCUMENTATION_INDEX.md) - Complete documentation catalog

### LLM Features
- [LLM Configuration Guide](docs/llm_configuration.md) - Configure RAG and embedding settings
- [Shadow Mode Guide](docs/shadow_mode_guide.md) - Validate LLM accuracy before deployment
- [Migration Guide](docs/migration_to_llm.md) - Migrate from rule-based to LLM engine
- [Feedback API](docs/feedback_api.md) - Submit feedback for continuous learning

### Technical Documentation
- [Architecture](docs/architecture.md) - System architecture and component design
- [Architecture Diagrams](ARCHITECTURE_DIAGRAM.md) - Visual system diagrams
- [Decision Policy](docs/decision_policy.md) - Decision rules and evaluation logic
- [Safety Rules](docs/safety_rules.md) - Safety constraints and examples
- [Incident Patterns](docs/incident_patterns.md) - 23 known incident patterns

## Contributing

This is a research project. For questions or issues, please contact the project maintainers.


### Workspace Wiring Self-Test (Azure CLI login)

Validates that both Log Analytics workspaces are reachable and contain
the expected tables before running the agent.

**Steps:**

1. Log in to Azure CLI in your terminal:
   ```bash
   az login
   ```

2. Set the workspace IDs in `.env` (or export them):
   ```bash
   export MONITOR_WORKSPACE_ID=<workspace-id-for-monitor1>
   export LOG_ANALYTICS_WORKSPACE_ID=<workspace-id-for-loganalytics>
   ```
   To retrieve the IDs:
   ```bash
   az monitor log-analytics workspace show \
     --workspace-name monitor1 --resource-group <your-rg> \
     --query customerId --output tsv

   az monitor log-analytics workspace show \
     --workspace-name loganalytics --resource-group <your-rg> \
     --query customerId --output tsv
   ```

3. Run the self-test:
   ```bash
   python scripts/test_workspace_wiring_cli.py
   # or via main CLI:
   python main.py --self-test-workspaces
   ```

4. Interpret the output:
   - `[OK]`    — Expected healthy behavior.
   - `[WARN]`  — Table reachable but empty; common immediately after VM Insights onboarding (wait 10-15 min).
   - `[ERROR]` — Configuration or connectivity issue that must be fixed before running the agent.

Exit codes: `0` = all healthy, `1` = config/auth error, `2` = query failures.
