# Azure VM Incident Copilot - Frequently Asked Questions (FAQ)

## General Questions

### What is the Azure VM Incident Copilot?

The Azure VM Incident Copilot is a read-only diagnostic system that automates triage for Azure VM incidents. It accepts structured telemetry data (30+ fields), applies deterministic decision logic with 23 incident patterns and 6 safety rules, and returns structured diagnostic output with diagnosis, evidence, gaps, and next steps.

### Is this a remediation tool?

No. This is a read-only diagnostic system. It never executes write operations, restart commands, or remediation actions. It only provides diagnostic recommendations and references to Standard Operating Procedures (SOPs).

### What types of incidents can it diagnose?

The system can diagnose 23 types of incidents:
- VM state issues (stopped, deallocated, failed)
- Network issues (NSG blocks RDP/SSH, conflicting rules)
- Performance issues (high CPU, memory, disk I/O)
- Boot failures (BSOD, kernel panic, stuck boot)
- Agent issues (VM agent, monitor agent down)
- Health issues (resource health unavailable, no heartbeat)
- Application issues (app health unhealthy)
- Backup issues (backup job failed)
- Certificate issues (SSL cert expiring)
- Rightsizing opportunities (oversized VMs)

### Does it require Azure connectivity?

No for local mode. You can process local JSON files without any Azure connectivity.

Yes for agent mode. The automated telemetry collector requires Azure API access to collect VM metrics, logs, and state.


---

## Installation & Setup

### What are the system requirements?

- Python 3.8 or higher
- 2 GB RAM minimum
- ~500 MB disk space for dependencies
- Internet connection (for initial setup only)
- Operating System: Windows, macOS, or Linux

### Do I need to install Azure CLI?

No. The system uses Azure SDK for Python (`azure-identity`, `azure-mgmt-compute`, etc.) and does not require Azure CLI. However, Azure CLI can be helpful for testing credentials.

### How do I install dependencies?

```bash
# Core dependencies (required)
pip install -r requirements.txt

# Test dependencies (optional)
pip install -r requirements-test.txt

# Azure agent dependencies (optional)
pip install -r requirements-agent.txt

# Web UI dependencies (optional)
pip install -r requirements-ui.txt
```

### What is the setup script for?

The setup script (`python main.py --setup`) generates required configuration files:
- Input schema (30+ telemetry fields)
- Output schema (7 required fields)
- Decision policy (rules and safety constraints)
- Benchmark test cases (38 scenarios)

You must run this before using the system for the first time.

### Can I use a virtual environment?

Yes, highly recommended:
```bash
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
```


---

## Usage

### How do I process a single telemetry file?

```bash
python main.py --input incident.json
```

The output is printed to stdout as JSON. To save to a file:
```bash
python main.py --input incident.json --output result.json
```

### What format should the input JSON be?

The input must be valid JSON matching the triage schema. Minimum required fields:
- `vm_name` (string)
- `power_state` (enum: Running, Stopped, Deallocated, Failed, Unknown)
- `provisioning_state` (enum: Succeeded, Failed, InProgress, Unknown)
- `resource_health_state` (enum: Available, Degraded, Unavailable, Unknown)

Optional fields (20 total) include metrics, network, agents, logs, etc.

See `schemas/azure_vm_triage_schema.json` for complete schema.

### What does the output look like?

The output is JSON with 7 required fields:
```json
{
  "decision": "diagnose",
  "diagnosis": "VM my-vm is stopped",
  "confidence_score": 0.95,
  "evidence": ["power_state=Stopped"],
  "evidence_gap": ["boot_diagnostics not available"],
  "next_check": "Start the VM. Follow SOP_Azure Start/Stop VMs",
  "explanation": "High confidence based on clear power state signal"
}
```

### What are the possible decision outcomes?

Three outcomes:
1. **diagnose** - High confidence (≥0.70), high completeness (≥90%), no conflicts
2. **diagnose_low_confidence** - Medium confidence (0.40-0.69), medium completeness (60-89%)
3. **abstain_request_next_check** - Low confidence (<0.40), low completeness (<60%), or safety rule triggered

### How do I run benchmark tests?

```bash
python main.py --benchmark data/benchmark_cases.csv
```

This processes all 38 benchmark cases and reports pass/fail results.


---

## Azure Agent Mode

### What is agent mode?

Agent mode automatically collects telemetry from Azure VMs using Azure APIs, processes it through the diagnostic pipeline, and saves results to files. It can run once or continuously at intervals.

### How do I configure Azure credentials?

Create a `.env` file from the template:
```bash
cp .env.example .env
```

Edit `.env` with your Azure credentials:
```
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_ID=your-client-id
AZURE_CLIENT_SECRET=your-secret
AZURE_SUBSCRIPTION_ID=your-subscription-id
AZURE_RESOURCE_GROUP=your-resource-group
AZURE_VM_NAME=your-vm-name
```

### What Azure permissions are required?

Minimum permissions:
- **Reader** role on the VM resource group
- **Log Analytics Reader** role on the workspace (if using Log Analytics)

To create a service principal with Reader role:
```bash
az ad sp create-for-rbac --name "incident-copilot" \
  --role "Reader" \
  --scopes /subscriptions/{subscription-id}/resourceGroups/{resource-group}
```

### How do I run the agent once?

```bash
python main.py --agent --vm my-vm --rg my-resource-group --once
```

Or using a config file:
```bash
python main.py --agent --config agent_config.json --once
```

### How do I run the agent continuously?

```bash
python main.py --agent --vm my-vm --rg my-resource-group --interval 300
```

This runs every 300 seconds (5 minutes). Press Ctrl+C to stop.

### Where are agent results saved?

Results are saved to `results/` directory with timestamped filenames:
```
results/2026-03-31_14-30-00_my-vm_diagnose.json
results/2026-03-31_14-35-00_my-vm_abstain.json
```

### What if Azure Monitor Agent is not installed?

The system gracefully handles missing Azure Monitor Agent:
- Host metrics (CPU) are still collected (always available)
- Guest metrics (memory, disk) are set to None
- System returns `abstain_request_next_check` with evidence gaps
- Warning logged: "Guest OS metrics unavailable"

This is expected behavior and not an error.


---

## Decision Logic

### How does the confidence score work?

Confidence score (0.0-1.0) is calculated based on:
- **Completeness**: Percentage of optional fields populated (20 fields)
- **Pattern matching**: Exact match vs partial match
- **Conflicts**: Contradictory signals reduce confidence

Formula:
```
confidence = base_confidence × completeness_factor × conflict_penalty
```

### What is completeness?

Completeness is the percentage of optional telemetry fields that are populated (not None).

Example:
- 20 optional fields total
- 18 fields populated
- Completeness = 18/20 = 90%

Higher completeness = more data = higher confidence.

### What are the decision thresholds?

**Rule A (diagnose):**
- Confidence ≥ 0.70
- Completeness ≥ 90%
- No conflicts

**Rule B (diagnose_low_confidence):**
- Confidence 0.40-0.69
- Completeness 60-89%
- Minor conflicts allowed

**Rule C (abstain):**
- Confidence < 0.40
- Completeness < 60%
- Safety rule triggered

### What are safety rules?

Safety rules are hard constraints that prevent unsafe suggestions:

1. **Platform Event Safety** - Never suggest restart during Azure maintenance
2. **Boot Failure Safety** - Never suggest restart for BSOD/KernelPanic
3. **Low Confidence Destructive Action** - Block destructive actions when confidence < 0.9
4. **Network Security Safety** - Never suggest disabling NSG/firewall
5. **Disk Safety** - Block disk deletion when confidence < 0.9
6. **Failed State Safety** - Never suggest auto-remediation for failed VMs

If any safety rule triggers, decision is always `abstain_request_next_check`.

### How are incident patterns detected?

The system evaluates 23 predefined patterns in order:
1. Check if telemetry matches pattern trigger conditions
2. If match, calculate confidence based on signal strength
3. Apply safety rules
4. Return diagnosis with evidence and next steps

Patterns are evaluated sequentially. First match wins.

### Can I customize decision thresholds?

Yes. Edit `policy/decision_policy.json`:
```json
{
  "decision_rules": {
    "rule_a_diagnose": {
      "confidence_threshold": 0.70,
      "completeness_threshold": 0.90
    }
  }
}
```

Then regenerate: `python main.py --setup`


---

## Testing

### How do I run tests?

```bash
# All tests
pytest tests/ -v

# Specific test suite
pytest tests/e2e/ -v
pytest tests/property/ -v

# With coverage
pytest tests/ -v --cov=src --cov-report=term
```

### What are property-based tests?

Property-based tests verify correctness properties that must hold for ALL inputs, not just specific examples. The system uses Hypothesis library to generate 100+ random test cases per property.

Example properties:
- Valid telemetry always passes validation
- Identical inputs produce identical outputs (determinism)
- Safety rules always block unsafe actions
- Confidence score is always 0.0-1.0

### How many tests are there?

- **Unit tests**: Component-level tests
- **Property-based tests**: 20 properties × 100 iterations = 2000+ test cases
- **End-to-end tests**: 45 test scenarios
- **Benchmark tests**: 38 real-world cases

Total: 150+ explicit tests, 2000+ generated test cases

### Why are some tests skipped?

Tests marked as "skipped" require Azure SDK or Azure connectivity:
- Agent collection tests (require Azure API)
- Full pipeline E2E tests (require agent mode)

These are skipped automatically if dependencies are not installed or credentials are not configured.

### How do I debug a failing test?

```bash
# Run specific test with verbose output
pytest tests/e2e/test_e2e_complete.py::test_4_1 -v -s

# Use debug scripts
python debug_case.py
python debug_benchmark.py

# Enable Python debug mode
python -v main.py --input incident.json
```


---

## Customization

### Can I add custom incident patterns?

Yes. Edit `src/decision_engine.py` and add your pattern:

```python
# Pattern 24: Custom pattern
if (telemetry.custom_field is not None and 
    telemetry.custom_field > threshold):
    
    diagnosis = f"Custom issue detected on {vm_name}"
    evidence = [f"custom_field={telemetry.custom_field}"]
    next_check = "Follow SOP_Custom_Procedure"
    
    return Decision(
        state=DecisionState.DIAGNOSE,
        diagnosis=diagnosis,
        evidence=evidence,
        next_check=next_check
    )
```

Then regenerate schemas and benchmark data:
```bash
python main.py --setup
```

### Can I add custom telemetry fields?

Yes. Add fields to `src/models.py` in the `TelemetryInput` class:

```python
class TelemetryInput(BaseModel):
    # ... existing fields ...
    custom_field: Optional[float] = None
```

Update `TOTAL_OPTIONAL` in `src/confidence_scorer.py` if adding optional fields.

Then regenerate schemas:
```bash
python main.py --setup
```

### Can I modify safety rules?

Yes, but carefully. Edit `src/decision_engine.py` and modify the safety rule checks. Safety rules are critical for preventing unsafe suggestions.

After changes, regenerate policy:
```bash
python main.py --setup
```

And run all tests to verify:
```bash
pytest tests/ -v
```

### Can I integrate with monitoring systems?

Yes. The system is designed for integration:

**Webhook integration:**
```python
import requests

def send_alert(output):
    if output.decision == "diagnose":
        requests.post("https://webhook-url", json=output.model_dump())
```

**Email alerts:**
```python
import smtplib

def send_email(output):
    # Send email with diagnosis
```

**SIEM integration:**
```python
def send_to_siem(output):
    # Forward to Splunk, ELK, etc.
```


---

## Troubleshooting

### Why am I getting "Module not found" errors?

Dependencies not installed. Run:
```bash
pip install -r requirements.txt
```

Make sure virtual environment is activated.

### Why am I getting "Schema file not found"?

Setup script not run. Run:
```bash
python main.py --setup
```

### Why is the decision always "abstain"?

Common reasons:
1. **Low completeness** - Not enough telemetry fields populated (need ≥60%)
2. **Low confidence** - Weak or conflicting signals (need ≥0.40)
3. **Safety rule triggered** - System blocked unsafe action

Check `evidence_gap` field in output to see missing fields.

### Why are guest OS metrics unavailable?

Azure Monitor Agent not installed on VM. This is expected and not an error. The system will:
- Use host metrics (CPU) which are always available
- Mark guest metrics (memory, disk) as None
- Return abstain with evidence gaps

To fix: Install Azure Monitor Agent and configure Data Collection Rule (DCR).

### How do I get more detailed error messages?

Run with Python verbose mode:
```bash
python -v main.py --input incident.json
```

Or check logs in agent mode:
```bash
python main.py --agent --vm my-vm --rg my-rg --once 2>&1 | tee agent.log
```

### Where can I get help?

1. Check documentation:
   - `SETUP_GUIDE.md` - Complete setup instructions
   - `TROUBLESHOOTING.md` - Common issues and solutions
   - `QUICK_REFERENCE.md` - Quick command reference

2. Run debug scripts:
   - `python debug_case.py`
   - `python debug_benchmark.py`

3. Contact project maintainers with:
   - Python version
   - Error message (full traceback)
   - Steps to reproduce
   - Input file (sanitized)


---

## Performance & Scalability

### How fast is the system?

Typical performance:
- Single file processing: 50-100ms
- Benchmark (38 cases): 2-3 seconds
- Agent collection: 5-15 seconds per VM

Performance depends on:
- Number of telemetry fields
- Azure API response time (agent mode)
- Log Analytics query complexity

### Can I process multiple VMs?

Yes. Use batch processing:

```python
vms = ["vm1", "vm2", "vm3"]
for vm in vms:
    config = AgentConfig(vm_name=vm, ...)
    collector = TelemetryCollectorAgent(config)
    result = collector.collect()
    # Process result
```

Or run multiple agent instances in parallel.

### What is the recommended collection interval?

Depends on VM priority:
- **High-priority VMs**: 60-120 seconds
- **Standard VMs**: 300 seconds (5 minutes, default)
- **Low-priority VMs**: 600-900 seconds (10-15 minutes)

Shorter intervals = more API calls = higher Azure costs.

### How can I reduce Log Analytics costs?

Limit query scope:
```python
query = """
Heartbeat
| where TimeGenerated > ago(5m)  # Only last 5 minutes
| where Computer == '{vm_name}'
| take 1
"""
```

Or reduce collection frequency for low-priority VMs.

### Can I run this in production?

Yes, with considerations:
- Use service principal with least-privilege permissions (Reader role)
- Monitor Azure API rate limits
- Set appropriate collection intervals
- Implement error handling and retries
- Monitor Log Analytics query costs
- Use `.env` file for credentials (never commit to git)


---

## Architecture & Design

### Why is this read-only?

Safety and compliance. A read-only system:
- Cannot accidentally break VMs
- Cannot violate change management policies
- Cannot trigger cascading failures
- Provides recommendations, not actions
- Requires human approval for changes

### Why deterministic decision logic?

Deterministic logic ensures:
- Identical inputs produce identical outputs
- Reproducible results for debugging
- Predictable behavior in production
- Easier testing and validation
- No AI/ML black box

### What is the confidence score based on?

Three factors:
1. **Signal strength** - How clear is the pattern match?
2. **Completeness** - How much telemetry data is available?
3. **Conflicts** - Are there contradictory signals?

Higher values = higher confidence.

### Why 23 incident patterns?

These are the most common Azure VM incidents based on:
- Azure support case analysis
- Production incident data
- Industry best practices
- Common troubleshooting scenarios

You can add custom patterns for your environment.

### Why 6 safety rules?

Safety rules prevent the most dangerous suggestions:
- Restart during maintenance (causes extended downtime)
- Restart with boot failure (makes problem worse)
- Destructive actions with low confidence (data loss risk)
- Disabling security controls (security risk)
- Disk operations with low confidence (data loss risk)
- Auto-remediation of failed VMs (unpredictable results)

### What is the technology stack?

- **Language**: Python 3.8+
- **Data validation**: Pydantic, jsonschema
- **Testing**: pytest, Hypothesis (property-based testing)
- **Azure SDK**: azure-identity, azure-mgmt-compute, azure-monitor-query
- **CLI**: Click
- **Web UI**: FastAPI, Uvicorn (optional)

### Is this production-ready?

Yes, with caveats:
- ✅ Comprehensive test suite (150+ tests, 2000+ generated cases)
- ✅ Property-based testing for correctness
- ✅ Safety rules prevent unsafe actions
- ✅ Read-only operation (no write risk)
- ⚠️ Monitor Azure API rate limits
- ⚠️ Implement error handling for production
- ⚠️ Test thoroughly in your environment first


---

## Comparison & Alternatives

### How is this different from Azure Monitor alerts?

| Feature | Incident Copilot | Azure Monitor Alerts |
|---------|------------------|---------------------|
| Scope | Multi-signal triage | Single metric threshold |
| Logic | 23 patterns + safety rules | Simple threshold |
| Output | Diagnosis + evidence + next steps | Alert notification |
| Safety | 6 safety rules | None |
| Cost | Compute only | Per alert rule |
| Customization | Full control | Limited |

### How is this different from Azure Advisor?

| Feature | Incident Copilot | Azure Advisor |
|---------|------------------|---------------|
| Purpose | Incident diagnosis | Optimization recommendations |
| Timing | Real-time | Periodic (daily) |
| Scope | VM incidents | All Azure resources |
| Depth | Deep VM diagnostics | High-level recommendations |
| Safety | 6 safety rules | N/A |

### How is this different from Azure Service Health?

| Feature | Incident Copilot | Azure Service Health |
|---------|------------------|---------------------|
| Scope | Individual VMs | Azure platform |
| Focus | VM-specific issues | Platform-wide issues |
| Data | VM telemetry | Service status |
| Action | Diagnostic recommendations | Status notifications |

### Can I use this with other cloud providers?

The architecture is cloud-agnostic, but the current implementation is Azure-specific. To adapt for AWS/GCP:
1. Replace Azure SDK with AWS boto3 or GCP client libraries
2. Update telemetry collection logic
3. Adjust incident patterns for cloud-specific issues
4. Update field names and enums

Core decision logic and safety rules are cloud-agnostic.

---

## Additional Resources

### Documentation
- `README.md` - Project overview
- `SETUP_GUIDE.md` - Complete setup instructions
- `QUICK_REFERENCE.md` - Quick command reference
- `TROUBLESHOOTING.md` - Common issues and solutions
- `ARCHITECTURE_DIAGRAM.md` - System architecture diagrams
- `docs/architecture.md` - Detailed architecture
- `docs/decision_policy.md` - Decision rules
- `docs/safety_rules.md` - Safety constraints
- `docs/incident_patterns.md` - 23 incident patterns

### Example Files
- `sample_test.json` - Sample telemetry input
- `data/benchmark_cases.csv` - 38 benchmark cases
- `.env.example` - Environment variable template

### Debug Tools
- `debug_case.py` - Debug single case
- `debug_benchmark.py` - Debug benchmark cases
- `test_decision_engine_manual.py` - Manual decision engine testing

---

**For more information, see the complete documentation in the project repository.**
