# 🚀 Agent Mode Web UI - Quick Start Guide

**Monitor your Azure VMs through a web browser - Complete telemetry collection and diagnosis!**

---

## What This Does

The agent mode automatically:
1. **Collects** all 30+ telemetry fields from your Azure VM using Azure CLI/SDK
2. **Creates** a JSON file with all the collected data
3. **Analyzes** the data using the LLM decision engine
4. **Displays** the diagnosis, confidence score, evidence, and next steps in the web UI

---

## Prerequisites

✅ Azure CLI installed (you mentioned you have this)  
✅ Python 3.8+ installed  
✅ Project dependencies installed  
✅ Azure credentials configured  

---

## Step-by-Step Setup

### 1. Install Dependencies

```bash
# Install web UI dependencies
pip install -r requirements-ui.txt

# Install agent dependencies (for Azure telemetry collection)
pip install -r requirements-agent.txt
```

### 2. Configure Azure Credentials

Create a `.env` file with your Azure credentials:

```bash
cp .env.example .env
```

Edit `.env` and add your Azure details:

```env
# Azure Authentication
AZURE_TENANT_ID=your-tenant-id-here
AZURE_CLIENT_ID=your-client-id-here
AZURE_CLIENT_SECRET=your-client-secret-here

# Azure Resources
AZURE_SUBSCRIPTION_ID=your-subscription-id-here
AZURE_RESOURCE_GROUP=your-resource-group-name
AZURE_VM_NAME=your-vm-name

# Optional: Log Analytics for detailed logs
AZURE_WORKSPACE_ID=your-workspace-id-here

# LLM Configuration (optional but recommended)
LLM_ENABLED=true
GROQ_API_KEY=your-groq-api-key-here
```

**How to get Azure credentials:**

```bash
# Login to Azure
az login

# Get your subscription ID and tenant ID
az account show

# Create a service principal with Reader role
az ad sp create-for-rbac --name "IncidentCopilotAgent" \
  --role "Reader" \
  --scopes "/subscriptions/YOUR_SUBSCRIPTION_ID"

# This outputs:
# - appId → Your AZURE_CLIENT_ID
# - password → Your AZURE_CLIENT_SECRET
# - tenant → Your AZURE_TENANT_ID
```

### 3. Start the Web Dashboard

```bash
python main.py --ui
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 4. Open Your Browser

Go to: **http://localhost:8000**

---

## Using the Agent Mode

### Tab 1: Agent Control

1. **Click "Agent Control" tab** at the top

2. **Fill in the form:**
   - **VM Name**: Your Azure VM name (e.g., `my-production-vm`)
   - **Resource Group**: Your resource group (e.g., `production-rg`)
   - **Subscription ID**: Your Azure subscription ID
   - **Workspace ID**: (Optional) Log Analytics workspace ID
   - **Interval**: How often to check (default: 300 seconds = 5 minutes)

3. **Click "Start Agent"** button

4. **Wait for confirmation**: "Agent started successfully"

✅ The agent is now running in the background!

---

### Tab 2: Dashboard - View Results

1. **Click "Dashboard" tab**

2. **You'll see two cards:**

   **VM Status Card:**
   - VM Name and Resource Group
   - Decision (diagnose / low confidence / abstain)
   - Confidence Score (0.0 to 1.0)
   - Diagnosis message
   - Evidence (what signals support the diagnosis)
   - Evidence Gap (what's missing)
   - Next Check (recommended action)
   - Last Scan timestamp

   **Agent Status Card:**
   - Status: Running/Stopped
   - Interval: Check frequency
   - Last Run: When it last ran

3. **Click "Scan Now"** to trigger an immediate check (don't wait for the interval)

4. **Enable "Auto-refresh"** checkbox to update every 30 seconds automatically

---

### Tab 3: Live Feed - See All Scans

1. **Click "Live Feed" tab**

2. **You'll see a table** with all scan results:
   - Timestamp
   - VM Name
   - Decision
   - Confidence
   - Diagnosis
   - Duration (how long the scan took)

3. **Filter results** using the dropdown (All / Diagnose / Low Confidence / Abstain)

4. **Export to CSV** to analyze trends

---

## What Telemetry is Collected?

The agent automatically collects **30+ fields** from Azure:

### VM State (Always Available)
- Power State (Running/Stopped/Deallocated/Failed)
- Provisioning State (Succeeded/Failed/InProgress)
- Resource Health (Available/Degraded/Unavailable)

### Metrics (from Azure Monitor)
- CPU Percentage
- Memory Percentage
- Disk Read/Write Latency
- Disk Usage Percentage
- Network Bytes In/Out

### Boot Diagnostics
- Boot State (Normal/BSOD/KernelPanic/Stuck)
- Screenshot analysis
- Serial console logs

### Network
- NSG Rules (RDP/SSH allow/deny)
- Connection troubleshoot results
- Public IP status

### Agents
- VM Agent Status
- Azure Monitor Agent Status
- Application Health Status

### Logs (from Log Analytics - if configured)
- Heartbeat presence
- Last heartbeat timestamp
- Event log errors
- Syslog errors

### Additional
- SSL Certificate expiry
- Last backup status
- Platform events (maintenance)

---

## How the Agent Works

```
┌─────────────────────────────────────────────────────────┐
│  1. COLLECT TELEMETRY (via Azure CLI/SDK)              │
│     - Calls Azure APIs to get VM state, metrics, logs  │
│     - Collects 30+ fields automatically                │
│     - Takes 5-15 seconds per VM                        │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  2. CREATE JSON FILE                                    │
│     - Saves to: results/telemetry_TIMESTAMP.json       │
│     - Contains all collected fields                     │
│     - Validated against schema                         │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  3. RUN DECISION ENGINE                                 │
│     - Uses LLM (Groq/Gemini/Ollama) if enabled         │
│     - Retrieves similar past incidents (RAG)           │
│     - Consults SOPs for recommendations                │
│     - Applies 6 safety rules                           │
│     - Calculates confidence score                      │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  4. SAVE RESULTS                                        │
│     - Saves to: results/output.jsonl                   │
│     - Appends each scan result                         │
│     - Includes diagnosis, evidence, next steps         │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  5. DISPLAY IN WEB UI                                   │
│     - Dashboard shows latest result                    │
│     - Live Feed shows all results                      │
│     - Auto-refreshes every 30 seconds (if enabled)     │
└─────────────────────────────────────────────────────────┘
```

---

## Example: What You'll See

### Scenario: VM is Stopped

**Dashboard shows:**
```
Decision: diagnose
Confidence: 0.95
Diagnosis: VM my-production-vm is stopped (PowerState=Stopped)

Evidence:
  • power_state=Stopped
  • provisioning_state=Succeeded
  • resource_health_state=Available

Evidence Gap:
  • boot_diagnostics not available
  • memory_percent not available

Next Check:
  Start the VM via Azure Portal. Follow SOP_Azure Start/Stop VMs
```

### Scenario: High CPU Usage

**Dashboard shows:**
```
Decision: diagnose
Confidence: 0.85
Diagnosis: VM my-production-vm has high CPU usage (95.2%)

Evidence:
  • cpu_percent=95.2
  • power_state=Running
  • vm_agent_status=Ready

Evidence Gap:
  • memory_percent not available (install Azure Monitor Agent)

Next Check:
  Investigate processes consuming CPU. Check application logs.
  Follow SOP_Performance Troubleshooting
```

### Scenario: Not Enough Data

**Dashboard shows:**
```
Decision: abstain_request_next_check
Confidence: 0.35
Diagnosis: Insufficient telemetry to diagnose

Evidence:
  • power_state=Running
  • provisioning_state=Succeeded

Evidence Gap:
  • cpu_percent not available
  • memory_percent not available
  • boot_diagnostics not available
  • heartbeat not available

Next Check:
  Install Azure Monitor Agent and configure Data Collection Rule (DCR)
  to collect guest OS metrics
```

---

## Viewing the JSON Files

All collected telemetry and results are saved to the `results/` folder:

```
results/
├── telemetry_2026-04-07_14-30-00.json    ← Collected telemetry
├── telemetry_2026-04-07_14-35-00.json
├── output.jsonl                           ← All diagnoses (one per line)
└── 2026-04-07_14-30-00_my-vm_diagnose.json ← Individual result
```

**View telemetry JSON:**
```bash
cat results/telemetry_2026-04-07_14-30-00.json
```

**View all diagnoses:**
```bash
cat results/output.jsonl
```

---

## Stopping the Agent

1. Go to **Agent Control** tab
2. Click **"Stop Agent"** button
3. Wait for confirmation: "Agent stopped successfully"

To stop the web server:
- Press `Ctrl+C` in the terminal

---

## Troubleshooting

### "Authentication failed"
- Check your `.env` file has correct credentials
- Verify with: `az login` and `az account show`
- Make sure service principal has Reader role

### "VM not found"
- Verify VM name is correct (case-sensitive)
- Verify resource group is correct
- Check: `az vm show --name my-vm --resource-group my-rg`

### "Guest OS metrics unavailable"
- This is normal if Azure Monitor Agent is not installed
- The system will use host metrics (CPU) which are always available
- To fix: Install Azure Monitor Agent on the VM

### "Port already in use"
- Another process is using port 8000
- Stop it or change the port in `ui/app.py`

---

## Best Practices

### For Testing
- Use interval of 60 seconds
- Monitor 1 VM first
- Enable auto-refresh to see updates

### For Production
- Use interval of 300 seconds (5 minutes) or more
- Monitor critical VMs more frequently
- Export Live Feed data regularly for analysis
- Set up alerts for "diagnose" decisions

---

## Next Steps

1. **Enable LLM features** for smarter diagnosis:
   - Set `LLM_ENABLED=true` in `.env`
   - Add Groq API key (get from https://console.groq.com/keys)
   - See [docs/llm_setup.md](docs/llm_setup.md)

2. **Set up Log Analytics** for detailed logs:
   - Create Log Analytics workspace
   - Install Azure Monitor Agent on VM
   - Add workspace ID to `.env`

3. **Customize patterns** for your environment:
   - Edit `src/decision_engine.py`
   - Add custom incident patterns
   - See [docs/incident_patterns.md](docs/incident_patterns.md)

---

## Quick Reference

**Start web UI:**
```bash
python main.py --ui
```

**Access dashboard:**
```
http://localhost:8000
```

**View results folder:**
```bash
ls results/
```

**Check agent logs:**
```bash
# Logs are shown in the terminal where you ran python main.py --ui
```

**Test Azure credentials:**
```bash
az login
az account show
az vm show --name my-vm --resource-group my-rg
```

---

## Summary

✅ **Cleaned up** 13 redundant documentation files  
✅ **Agent mode** automatically collects 30+ telemetry fields via Azure CLI/SDK  
✅ **Web UI** displays all results in real-time  
✅ **JSON files** saved to `results/` folder for analysis  
✅ **LLM-powered** diagnosis with RAG and SOP consultation  

**You're all set!** Start the web UI and monitor your Azure VMs through your browser.
