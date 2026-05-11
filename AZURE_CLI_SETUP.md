# 🚀 Azure VM Incident Copilot - Azure CLI Authentication Setup

**Complete procedure to run the agent using Azure CLI credentials**

---

## Prerequisites

✅ Azure CLI installed (you have this)  
✅ Python 3.8+ installed  
✅ Access to Azure subscription with VMs  

---

## Step-by-Step Procedure

### Step 1: Login to Azure CLI

Open your terminal and login:

```bash
az login
```

This will:
- Open your browser for authentication
- Show you a list of your subscriptions
- Set the default subscription

**Verify you're logged in:**
```bash
az account show
```

You should see:
```json
{
  "id": "your-subscription-id",
  "name": "Your Subscription Name",
  "tenantId": "your-tenant-id",
  "user": {
    "name": "your-email@company.com"
  }
}
```

---

### Step 2: Set Your Default Subscription (if you have multiple)

```bash
# List all subscriptions
az account list --output table

# Set the one you want to use
az account set --subscription "your-subscription-id"

# Verify it's set
az account show
```

---

### Step 3: Verify You Can Access Your VM

```bash
# Replace with your actual values
az vm show \
  --name Test-VM \
  --resource-group AZ26POC1-CO-LAB \
  --output table
```

**Example:**
```bash
az vm show \
  --name my-production-vm \
  --resource-group production-rg \
  --output table
```

You should see your VM details. If you get an error, check:
- VM name is correct (case-sensitive)
- Resource group is correct
- You have Reader permissions

---

### Step 4: Install Python Dependencies

```bash
# Navigate to project directory
cd path/to/azure-vm-incident-copilot

# Install agent dependencies
pip install -r requirements-agent.txt

# Install web UI dependencies
pip install -r requirements-ui.txt
```

---

### Step 5: Run Initial Setup (First Time Only)

```bash
python main.py --setup
```

This creates:
- `schemas/azure_vm_triage_schema.json`
- `schemas/output_schema.json`
- `policy/decision_policy.json`
- `data/benchmark_cases.csv`

---

### Step 6: Start the Web Dashboard

```bash
python main.py --ui
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**Keep this terminal open!**

---

### Step 7: Open the Web UI

Open your browser and go to:
```
http://localhost:8000
```

---

### Step 8: Configure and Start the Agent

1. **Click "Agent Control" tab**

2. **Fill in the form:**
   - **VM Name**: `your-vm-name` (e.g., `my-production-vm`)
   - **Resource Group**: `your-resource-group` (e.g., `production-rg`)
   - **Subscription ID**: Copy from `az account show` output
   - **Workspace ID**: (Optional) Leave blank if you don't have Log Analytics
   - **Interval**: `300` (5 minutes) or `60` (1 minute for testing)

3. **Click "Start Agent" button**

4. **Wait for confirmation**: "Agent started successfully"

---

### Step 9: View Results

**Option A: Dashboard Tab**
1. Click "Dashboard" tab
2. See real-time VM status
3. Click "Scan Now" for immediate check
4. Enable "Auto-refresh" for automatic updates

**Option B: Live Feed Tab**
1. Click "Live Feed" tab
2. See all scan results in a table
3. Filter by decision type
4. Export to CSV

**Option C: Check JSON Files**
```bash
# View collected telemetry
ls results/

# View latest telemetry
cat results/telemetry_*.json | tail -1

# View all diagnoses
cat results/output.jsonl
```

---

## Complete Example Session

```bash
# 1. Login to Azure
az login

# 2. Verify subscription
az account show

# 3. Test VM access
az vm show --name my-vm --resource-group my-rg --output table

# 4. Install dependencies (first time only)
pip install -r requirements-agent.txt
pip install -r requirements-ui.txt

# 5. Run setup (first time only)
python main.py --setup

# 6. Start web UI
python main.py --ui

# 7. Open browser to http://localhost:8000

# 8. In browser:
#    - Go to "Agent Control" tab
#    - Fill in: VM Name, Resource Group, Subscription ID
#    - Click "Start Agent"
#    - Go to "Dashboard" tab to see results
```

---

## What Happens Behind the Scenes

```
┌─────────────────────────────────────────────────────────┐
│  1. Azure CLI Authentication                            │
│     - You logged in with: az login                      │
│     - Credentials stored in: ~/.azure/                  │
│     - DefaultAzureCredential() reads these credentials  │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  2. Agent Starts (every 5 minutes)                      │
│     - Uses your Azure CLI credentials automatically     │
│     - No need for .env file or service principal        │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  3. Collect Telemetry via Azure SDK                     │
│     - Azure Resource Graph API (VM state, NSG, health)  │
│     - Azure Monitor Metrics API (CPU, memory, disk)     │
│     - Azure Monitor Logs API (heartbeat, agent status)  │
│     - Collects 30+ fields in 5-15 seconds               │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  4. Save Telemetry JSON                                 │
│     - File: results/telemetry_2026-04-07_14-30-00.json │
│     - Contains all 30+ collected fields                 │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  5. Run Decision Engine                                 │
│     - Validates telemetry against schema                │
│     - Calculates confidence score                       │
│     - Matches incident patterns                         │
│     - Applies 6 safety rules                            │
│     - Uses LLM if enabled (Groq/Gemini/Ollama)          │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  6. Save Diagnosis                                      │
│     - File: results/output.jsonl (appends each result)  │
│     - Contains: decision, diagnosis, confidence,        │
│       evidence, gaps, next steps                        │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  7. Display in Web UI                                   │
│     - Dashboard shows latest result                     │
│     - Live Feed shows all results                       │
│     - Auto-refreshes every 30 seconds (if enabled)      │
└─────────────────────────────────────────────────────────┘
```

---

## Troubleshooting

### Problem: "az: command not found"

**Solution:**
```bash
# Verify Azure CLI is installed
az --version

# If not installed, install it:
# Windows: Download from https://aka.ms/installazurecliwindows
# Or use: winget install -e --id Microsoft.AzureCLI
```

---

### Problem: "Please run 'az login' to setup account"

**Solution:**
```bash
# Login again
az login

# Verify
az account show
```

---

### Problem: "VM not found" error

**Solution:**
```bash
# List all VMs in subscription
az vm list --output table

# Check specific VM
az vm show --name YOUR_VM_NAME --resource-group YOUR_RG --output table

# Make sure VM name and resource group are correct (case-sensitive)
```

---

### Problem: "DefaultAzureCredential failed to retrieve a token"

**Solution:**
```bash
# Clear Azure CLI cache
az account clear

# Login again
az login

# Restart the web UI
# Press Ctrl+C in terminal
python main.py --ui
```

---

### Problem: "Guest OS metrics unavailable"

**This is normal!** It means:
- Azure Monitor Agent is not installed on the VM
- The agent will still work using host metrics (CPU)
- Guest metrics (memory, disk) will be None

**To fix (optional):**
1. Install Azure Monitor Agent on your VM
2. Create a Data Collection Rule (DCR)
3. Associate DCR with your VM
4. Wait 5-10 minutes for data to appear

**For now, you can ignore this warning.**

---

### Problem: "Port 8000 already in use"

**Solution:**
```bash
# Find what's using port 8000
netstat -ano | findstr :8000

# Kill the process or use a different port
# Edit ui/app.py and change port to 8001
```

---

## Verify Everything is Working

### Test 1: Azure CLI Access
```bash
az vm show --name YOUR_VM_NAME --resource-group YOUR_RG
```
✅ Should show VM details

### Test 2: Python Dependencies
```bash
python -c "from azure.identity import DefaultAzureCredential; print('OK')"
```
✅ Should print "OK"

### Test 3: Web UI
```bash
python main.py --ui
# Open http://localhost:8000
```
✅ Should show dashboard

### Test 4: Agent Start
- Go to Agent Control tab
- Fill in VM details
- Click "Start Agent"
✅ Should show "Agent started successfully"

### Test 5: View Results
- Go to Dashboard tab
- Click "Scan Now"
- Wait 10-15 seconds
✅ Should show VM status with diagnosis

---

## Stopping Everything

### Stop the Agent
1. Go to "Agent Control" tab in browser
2. Click "Stop Agent" button
3. Wait for "Agent stopped successfully"

### Stop the Web UI
1. Go to terminal where `python main.py --ui` is running
2. Press `Ctrl+C`
3. Wait for "Shutting down"

### Logout from Azure (optional)
```bash
az logout
```

---

## Next Steps

### Enable LLM Features (Optional)
```bash
# Get Groq API key from https://console.groq.com/keys
# Add to .env file:
echo "LLM_ENABLED=true" >> .env
echo "GROQ_API_KEY=your-key-here" >> .env

# Restart web UI
python main.py --ui
```

### Monitor Multiple VMs
- Start the agent for VM1
- Open another terminal
- Start another agent instance for VM2
- Each runs independently

### Set Up Alerts
- Export Live Feed to CSV
- Analyze trends
- Set up email alerts for "diagnose" decisions

---

## Quick Reference Card

```bash
# Login
az login

# Verify
az account show

# Test VM access
az vm show --name VM_NAME --resource-group RG_NAME

# Start web UI
python main.py --ui

# Open browser
http://localhost:8000

# Stop web UI
Ctrl+C
```

---

## Summary

✅ **No .env file needed** - Azure CLI credentials are used automatically  
✅ **No service principal needed** - Your user account is used  
✅ **Simple authentication** - Just `az login` and you're ready  
✅ **Full telemetry collection** - 30+ fields via Azure SDK  
✅ **Web UI access** - Monitor everything in your browser  
✅ **JSON files saved** - All data in `results/` folder  

**You're all set! Start monitoring your Azure VMs now.**
