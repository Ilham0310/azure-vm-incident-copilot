# Azure VM Incident Copilot - Complete Setup Guide

This guide provides step-by-step instructions for setting up and running the Azure VM Incident Copilot system from scratch.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Initial Setup](#initial-setup)
4. [Configuration](#configuration)
5. [Running the System](#running-the-system)
6. [Testing](#testing)
7. [Azure Agent Mode](#azure-agent-mode)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software

- **Python 3.8 or higher**
  - Check version: `python --version`
  - Download from: https://www.python.org/downloads/

- **pip** (Python package manager)
  - Usually included with Python
  - Check version: `pip --version`

- **Git** (optional, for cloning repository)
  - Download from: https://git-scm.com/downloads

### System Requirements

- Operating System: Windows, macOS, or Linux
- Disk Space: ~500 MB for dependencies
- RAM: 2 GB minimum
- Internet connection (for initial setup only)

---

## Installation

### Step 1: Clone or Download the Repository

**Option A: Using Git**
```bash
git clone <repository-url>
cd azure-vm-incident-copilot
```

**Option B: Download ZIP**
1. Download the project ZIP file
2. Extract to a directory
3. Open terminal/command prompt in that directory

### Step 2: Create Virtual Environment (Recommended)

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

You should see `(venv)` in your terminal prompt.


### Step 3: Install Dependencies

**Install core runtime dependencies:**
```bash
pip install -r requirements.txt
```

This installs:
- `jsonschema>=4.0.0` - JSON schema validation
- `pydantic>=2.0.0` - Data models and validation
- `pandas>=1.5.0` - Data processing
- `click>=8.0.0` - CLI framework
- `python-dotenv>=1.0.0` - Environment variable management

**Install test dependencies (optional):**
```bash
pip install -r requirements-test.txt
```

This installs:
- `pytest>=7.0.0` - Testing framework
- `pytest-cov>=4.0.0` - Coverage reporting
- `hypothesis>=6.0.0` - Property-based testing

**Install Azure agent dependencies (optional, for agent mode):**
```bash
pip install -r requirements-agent.txt
```

This installs:
- `azure-identity` - Azure authentication
- `azure-mgmt-compute` - VM management
- `azure-mgmt-network` - Network management
- `azure-monitor-query` - Metrics and logs

**Install UI dependencies (optional, for web dashboard):**
```bash
pip install -r requirements-ui.txt
```

This installs:
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `jinja2` - Template engine

### Step 4: Verify Installation

Check that all packages are installed:
```bash
pip list
```

You should see all the packages listed above.

---

## Initial Setup

### Step 1: Run Setup Script

Generate required configuration files:
```bash
python main.py --setup
```

This creates:
- `schemas/azure_vm_triage_schema.json` - Input validation schema (30+ fields)
- `schemas/output_schema.json` - Output validation schema (7 fields)
- `policy/decision_policy.json` - Decision rules and safety rules
- `data/benchmark_cases.csv` - 38 benchmark test cases

**Expected output:**
```
============================================================
Azure VM Incident Copilot - Setup
============================================================

Step 1/4: Generating triage schema...
✓ Created schemas/azure_vm_triage_schema.json

Step 2/4: Generating output schema...
✓ Created schemas/output_schema.json

Step 3/4: Generating decision policy...
✓ Created policy/decision_policy.json

Step 4/4: Generating benchmark cases...
✓ Created data/benchmark_cases.csv (38 cases)

============================================================
Setup complete!
============================================================
```


### Step 2: Verify Generated Files

Check that all files were created:
```bash
# Windows
dir schemas
dir policy
dir data

# macOS/Linux
ls -la schemas/
ls -la policy/
ls -la data/
```

You should see:
- `schemas/azure_vm_triage_schema.json` (~15 KB)
- `schemas/output_schema.json` (~3 KB)
- `policy/decision_policy.json` (~8 KB)
- `data/benchmark_cases.csv` (~25 KB)

---

## Configuration

### Option 1: Local File Processing (No Configuration Needed)

For processing local JSON files, no configuration is required. Skip to [Running the System](#running-the-system).

### Option 2: Azure Agent Mode (Requires Azure Credentials)

If you want to use the automated telemetry collection agent, configure Azure credentials.

#### Step 1: Copy Environment Template

```bash
cp .env.example .env
```

#### Step 2: Edit .env File

Open `.env` in a text editor and fill in your Azure credentials:

```bash
# Azure Authentication
AZURE_TENANT_ID=12345678-1234-1234-1234-123456789012
AZURE_CLIENT_ID=87654321-4321-4321-4321-210987654321
AZURE_CLIENT_SECRET=your-secret-here

# Azure Resources
AZURE_SUBSCRIPTION_ID=abcdef12-3456-7890-abcd-ef1234567890
AZURE_RESOURCE_GROUP=my-resource-group
AZURE_VM_NAME=my-vm-name

# Azure Monitor (Optional)
AZURE_WORKSPACE_ID=workspace-id-here

# Agent Configuration (Optional)
AGENT_INTERVAL_SECONDS=300
AGENT_OUTPUT_DIR=results/
AGENT_ALERT_ON_DIAGNOSE=true
AGENT_ALERT_ON_LOW_CONFIDENCE=true
```

#### Step 3: Secure Your Credentials

**IMPORTANT:** Never commit `.env` to version control!

The `.gitignore` file already includes `.env`, but verify:
```bash
# Check .gitignore contains .env
cat .gitignore | grep ".env"
```

#### Step 4: Get Azure Credentials

**To get your Azure credentials:**

1. **Tenant ID, Subscription ID:**
   - Azure Portal → Azure Active Directory → Properties
   - Or run: `az account show`

2. **Service Principal (Client ID + Secret):**
   ```bash
   az ad sp create-for-rbac --name "incident-copilot" \
     --role "Reader" \
     --scopes /subscriptions/{subscription-id}
   ```
   This outputs `appId` (Client ID) and `password` (Client Secret)

3. **Log Analytics Workspace ID:**
   - Azure Portal → Log Analytics workspaces → Your workspace → Properties
   - Copy "Workspace ID"


---

## Running the System

### Mode 1: Single File Processing

Process a single telemetry JSON file:

```bash
python main.py --input incident.json
```

**Example output:**
```json
{
  "decision": "diagnose",
  "diagnosis": "VM my-vm is stopped (PowerState=Stopped)",
  "confidence_score": 0.95,
  "evidence": [
    "power_state=Stopped",
    "provisioning_state=Succeeded"
  ],
  "evidence_gap": [
    "boot_diagnostics not available"
  ],
  "next_check": "Start the VM via Azure Portal. Follow SOP_Azure Start/Stop VMs",
  "explanation": "High confidence diagnosis based on clear power state signal"
}
```

**Save output to file:**
```bash
python main.py --input incident.json --output result.json
```

### Mode 2: Benchmark Testing

Process all 38 benchmark cases:

```bash
python main.py --benchmark data/benchmark_cases.csv
```

**Example output:**
```
============================================================
Benchmark Results
============================================================
Total cases: 38
Passed: 38
Failed: 0
Success rate: 100.0%

Execution time: 2.34 seconds
Average per case: 0.06 seconds
============================================================
```

### Mode 3: Azure Agent Mode (Single Run)

Collect telemetry from Azure VM and diagnose once:

```bash
python main.py --agent --vm my-vm --rg my-resource-group --once
```

Or using config file:
```bash
python main.py --agent --config agent_config.json --once
```

### Mode 4: Azure Agent Mode (Continuous)

Run agent continuously with 5-minute intervals:

```bash
python main.py --agent --vm my-vm --rg my-resource-group --interval 300
```

Press `Ctrl+C` to stop.

### Mode 5: Web Dashboard UI

Start the web interface:

```bash
python main.py --ui
```

Open browser to: http://localhost:8000

**Features:**
- Upload telemetry JSON files
- View diagnostic results
- Browse incident patterns
- Test different scenarios


---

## Testing

### Run All Tests

```bash
pytest tests/ -v
```

**Expected output:**
```
tests/e2e/test_e2e_complete.py::TestSchemaValidation::test_2_1 PASSED
tests/e2e/test_e2e_complete.py::TestSchemaValidation::test_2_2 PASSED
...
tests/property/test_properties_validation.py::test_valid_telemetry_always_passes PASSED
tests/property/test_properties_decision.py::test_deterministic_decision PASSED
...

============ 150 passed, 13 skipped in 45.23s ============
```

### Run Specific Test Suites

**End-to-end tests:**
```bash
pytest tests/e2e/ -v
```

**Property-based tests:**
```bash
pytest tests/property/ -v
```

**Unit tests:**
```bash
pytest tests/unit/ -v
```

### Run Tests with Coverage

```bash
pytest tests/ -v --cov=src --cov-report=term
```

**Expected coverage:**
```
Name                              Stmts   Miss  Cover
-----------------------------------------------------
src/benchmark_loader.py              45      2    96%
src/confidence_scorer.py             78      3    96%
src/decision_engine.py              156      5    97%
src/explanation_formatter.py         42      1    98%
src/models.py                       124      8    94%
src/test_harness.py                  67      4    94%
src/validator.py                     89      6    93%
-----------------------------------------------------
TOTAL                               601     29    95%
```

### Run Specific Test

```bash
pytest tests/e2e/test_e2e_complete.py::TestDecisionEngine::test_4_1 -v
```

### Generate HTML Coverage Report

```bash
pytest tests/ --cov=src --cov-report=html
```

Open `htmlcov/index.html` in browser.

---

## Azure Agent Mode

### Prerequisites for Agent Mode

1. **Azure SDK installed:**
   ```bash
   pip install -r requirements-agent.txt
   ```

2. **Azure credentials configured** (see [Configuration](#configuration))

3. **Azure permissions:**
   - Reader role on VM resource group
   - Log Analytics Reader role (if using workspace)


### Agent Configuration File (Optional)

Create `agent_config.json`:

```json
{
  "subscription_id": "12345678-1234-1234-1234-123456789012",
  "resource_group": "my-resource-group",
  "vm_name": "my-vm",
  "log_analytics_workspace_id": "workspace-id",
  "interval_seconds": 300,
  "output_dir": "results/",
  "alert_on_diagnose": true,
  "alert_on_low_confidence": true
}
```

Run with config:
```bash
python main.py --agent --config agent_config.json
```

### What the Agent Collects

The agent automatically collects 30+ telemetry fields:

**VM State:**
- Power state (Running, Stopped, Deallocated, Failed)
- Provisioning state (Succeeded, Failed, In Progress)
- Resource health (Available, Degraded, Unavailable)

**Metrics (from Azure Monitor):**
- CPU percentage
- Memory percentage
- Disk latency (read/write)
- Disk usage percentage
- Network bytes in/out

**Boot Diagnostics:**
- Boot state (Normal, BSOD, KernelPanic, Stuck)
- Screenshot analysis
- Serial console logs

**Network:**
- NSG rules (RDP/SSH allow/deny)
- Connection troubleshoot results
- Public IP status

**Agents:**
- VM agent status
- Azure Monitor agent status
- Application health status

**Logs (from Log Analytics):**
- Heartbeat presence
- Last heartbeat timestamp
- Event log errors
- Syslog errors

**Additional Fields:**
- SSL certificate expiry (days remaining)
- Last backup status and timestamp
- Platform events (maintenance, updates)

### Agent Output

Results are saved to `results/` directory:
```
results/
├── 2026-03-31_14-30-00_my-vm_diagnose.json
├── 2026-03-31_14-35-00_my-vm_diagnose.json
└── 2026-03-31_14-40-00_my-vm_abstain.json
```

Each file contains:
- Collected telemetry
- Diagnostic decision
- Evidence and gaps
- Next steps


---

## Troubleshooting

### Common Issues

#### 1. Module Not Found Error

**Error:**
```
ModuleNotFoundError: No module named 'jsonschema'
```

**Solution:**
```bash
pip install -r requirements.txt
```

Make sure virtual environment is activated.

#### 2. Schema Files Not Found

**Error:**
```
Error: Schema file not found. Run 'python main.py --setup' first.
```

**Solution:**
```bash
python main.py --setup
```

#### 3. Python Version Too Old

**Error:**
```
SyntaxError: invalid syntax
```

**Solution:**
Check Python version:
```bash
python --version
```

Must be 3.8 or higher. Upgrade Python if needed.

#### 4. Azure Authentication Failed

**Error:**
```
DefaultAzureCredential failed to retrieve a token
```

**Solution:**
1. Verify `.env` file has correct credentials
2. Check service principal has Reader role
3. Test Azure CLI authentication:
   ```bash
   az login
   az account show
   ```

#### 5. Missing Azure Monitor Agent Data

**Warning:**
```
WARNING: Guest OS metrics unavailable for my-vm
```

**Solution:**
This is expected if Azure Monitor Agent is not installed. The system will:
- Use host metrics (CPU) which are always available
- Mark guest metrics (memory, disk) as None
- Return `abstain_request_next_check` with evidence gaps

To fix:
1. Install Azure Monitor Agent on VM
2. Configure Data Collection Rule (DCR)
3. Wait 5-10 minutes for data to appear

#### 6. Benchmark Tests Failing

**Error:**
```
AssertionError: Expected 'diagnose' but got 'abstain_request_next_check'
```

**Solution:**
1. Regenerate benchmark data:
   ```bash
   rm data/benchmark_cases.csv
   python main.py --setup
   ```

2. Run tests again:
   ```bash
   pytest tests/ -v
   ```


#### 7. Port Already in Use (Web UI)

**Error:**
```
OSError: [Errno 48] Address already in use
```

**Solution:**
1. Stop other process using port 8000
2. Or use different port:
   ```bash
   # Edit ui/app.py and change port
   uvicorn.run(app, host="0.0.0.0", port=8001)
   ```

#### 8. Permission Denied on Windows

**Error:**
```
PermissionError: [WinError 5] Access is denied
```

**Solution:**
Run terminal as Administrator, or:
```bash
# Use --user flag
pip install --user -r requirements.txt
```

---

## Quick Start Checklist

Use this checklist for first-time setup:

- [ ] Python 3.8+ installed (`python --version`)
- [ ] Virtual environment created and activated
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] Setup script run (`python main.py --setup`)
- [ ] Schema files generated (check `schemas/` directory)
- [ ] Test with sample file (`python main.py --input sample_test.json`)
- [ ] Run tests (`pytest tests/ -v`)
- [ ] (Optional) Configure `.env` for Azure agent mode
- [ ] (Optional) Install agent dependencies (`pip install -r requirements-agent.txt`)
- [ ] (Optional) Test agent mode (`python main.py --agent --once`)

---

## Next Steps

After completing setup:

1. **Read Documentation:**
   - `README.md` - Project overview
   - `docs/architecture.md` - System design
   - `docs/decision_policy.md` - Decision rules
   - `docs/safety_rules.md` - Safety constraints
   - `docs/incident_patterns.md` - 23 incident patterns

2. **Try Example Cases:**
   - Process benchmark cases: `python main.py --benchmark data/benchmark_cases.csv`
   - Create custom test cases in `data/` directory
   - Experiment with different telemetry combinations

3. **Explore the Code:**
   - `src/models.py` - Data models (30+ telemetry fields)
   - `src/decision_engine.py` - Decision logic (23 patterns, 6 safety rules)
   - `src/confidence_scorer.py` - Confidence calculation
   - `tests/property/` - Property-based tests (20 properties)

4. **Customize for Your Environment:**
   - Add custom incident patterns in `src/decision_engine.py`
   - Modify safety rules in `policy/decision_policy.json`
   - Create organization-specific SOPs
   - Integrate with monitoring systems


---

## Advanced Configuration

### Custom Decision Policy

Edit `policy/decision_policy.json` to customize:

```json
{
  "decision_rules": {
    "rule_a_diagnose": {
      "confidence_threshold": 0.70,
      "completeness_threshold": 0.90,
      "allow_conflicts": false
    },
    "rule_b_diagnose_low_confidence": {
      "confidence_threshold": 0.40,
      "completeness_threshold": 0.60,
      "allow_minor_conflicts": true
    }
  },
  "safety_rules": {
    "platform_event_safety": true,
    "boot_failure_safety": true,
    "low_confidence_destructive_action_safety": true,
    "network_security_safety": true,
    "disk_safety": true,
    "failed_state_safety": true
  }
}
```

### Custom Incident Patterns

Add patterns to `src/decision_engine.py`:

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

### Integration with Monitoring Systems

**Webhook Integration:**
```python
# In agent/scheduler.py
def send_alert(self, output):
    if output.decision == "diagnose":
        requests.post(
            "https://your-webhook-url",
            json=output.model_dump()
        )
```

**Email Alerts:**
```python
import smtplib
from email.mime.text import MIMEText

def send_email_alert(output):
    msg = MIMEText(output.diagnosis)
    msg['Subject'] = f"VM Alert: {output.decision}"
    msg['From'] = "copilot@example.com"
    msg['To'] = "ops@example.com"
    
    smtp = smtplib.SMTP('smtp.example.com')
    smtp.send_message(msg)
    smtp.quit()
```

---

## Performance Tuning

### Optimize Collection Interval

For production use:
- **High-priority VMs:** 60-120 seconds
- **Standard VMs:** 300 seconds (5 minutes)
- **Low-priority VMs:** 600-900 seconds (10-15 minutes)

### Reduce Log Analytics Costs

Limit query scope:
```python
# In agent/collector.py
query = """
Heartbeat
| where TimeGenerated > ago(5m)  # Only last 5 minutes
| where Computer == '{vm_name}'
| take 1
"""
```

### Batch Processing

Process multiple VMs:
```python
vms = ["vm1", "vm2", "vm3"]
for vm in vms:
    config = AgentConfig(vm_name=vm, ...)
    collector = TelemetryCollectorAgent(config)
    result = collector.collect()
    # Process result
```

---

## Support and Resources

### Documentation

- **Project README:** `README.md`
- **Architecture:** `docs/architecture.md`
- **Decision Policy:** `docs/decision_policy.md`
- **Safety Rules:** `docs/safety_rules.md`
- **Incident Patterns:** `docs/incident_patterns.md`
- **E2E Tests:** `tests/e2e/README.md`

### Example Files

- **Sample telemetry:** `sample_test.json`
- **Benchmark cases:** `data/benchmark_cases.csv`
- **Config template:** `.env.example`
- **Agent config:** `agent_config.json` (create from template)

### Testing Resources

- **Property tests:** `tests/property/` (20 correctness properties)
- **E2E tests:** `tests/e2e/` (45 test cases)
- **Test strategies:** `tests/property/strategies.py`

### Debugging Tools

- **Debug single case:** `python debug_case.py`
- **Debug benchmark:** `python debug_benchmark.py`
- **Manual decision test:** `python test_decision_engine_manual.py`

---

## Version Information

- **Python:** 3.8+
- **Core Dependencies:** See `requirements.txt`
- **Test Dependencies:** See `requirements-test.txt`
- **Agent Dependencies:** See `requirements-agent.txt`
- **UI Dependencies:** See `requirements-ui.txt`

---

## License

Research project - see LICENSE file for details.

---

## Contact

For questions, issues, or contributions, please contact the project maintainers.

---

**End of Setup Guide**
