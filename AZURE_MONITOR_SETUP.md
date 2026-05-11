# Azure Monitor Agent Setup Guide

Complete step-by-step guide to configure Azure Monitor Agent and get full telemetry for your VM.

---

## Overview

This guide will help you:
1. Create a Log Analytics Workspace (if you don't have one)
2. Find your Workspace ID
3. Configure Data Collection Rules (DCR)
4. Verify Azure Monitor Agent is collecting data
5. Update your web UI configuration

**Time Required**: 15-20 minutes  
**Result**: 60-80% telemetry completeness (vs current 11.54%)

---

## Step 1: Create Log Analytics Workspace

### 1.1 Go to Azure Portal
- Open: https://portal.azure.com
- Sign in with: Mohammed.Ilham@philips.com

### 1.2 Create Workspace
1. In the search bar at top, type: **"Log Analytics workspaces"**
2. Click **"Log Analytics workspaces"** from results
3. Click **"+ Create"** button

### 1.3 Fill Workspace Details
- **Subscription**: ITGS Sandbox
- **Resource Group**: AZ26POC1-CO-LAB (same as your VM)
- **Name**: `test-vm-workspace` (or any name you prefer)
- **Region**: West Europe (same as your VM)

4. Click **"Review + Create"**
5. Click **"Create"**
6. Wait 1-2 minutes for deployment to complete
7. Click **"Go to resource"**

---

## Step 2: Get Your Workspace ID

### 2.1 Find Workspace ID
1. You should now be on your workspace page
2. Look at the left menu, click **"Properties"**
3. You'll see a field called **"Workspace ID"**
4. It looks like: `12345678-1234-1234-1234-123456789abc`
5. Click the **copy icon** next to it to copy the ID

### 2.2 Save Workspace ID
**IMPORTANT**: Keep this ID handy - you'll need it in Step 5

Example format:
```
Workspace ID: 12345678-1234-1234-1234-123456789abc
```

---

## Step 3: Configure Data Collection Rules (DCR)

**IMPORTANT**: There are TWO ways to do this. Try Method A first (easier). If you can't find the options, use Method B.

---

### METHOD A: Using VM Insights (Easier - Recommended)

This method automatically creates the DCR for you.

1. Go to Azure Portal → Search for **"Test-VM"**
2. Click on your VM **"Test-VM"**
3. In the left menu, scroll down to **"Monitoring"** section
4. Click **"Insights"**
5. You'll see a button **"Enable"** or **"Configure"**
6. Click **"Enable"**
7. A panel will open asking for Log Analytics workspace
8. Select your workspace: **"test-vm-workspace"**
9. Click **"Enable"** or **"Configure"**
10. Wait 2-3 minutes for setup to complete

**That's it!** This automatically:
- Creates a Data Collection Rule
- Associates it with your VM
- Configures performance counters
- Starts collecting metrics

**Skip to Step 4** if you used this method.

---

### METHOD B: Manual DCR Creation (If Method A doesn't work)

### 3.1 Create Data Collection Rule
1. In Azure Portal search bar, type: **"Monitor"**
2. Click **"Monitor"** from results
3. In left menu, scroll down and click **"Data Collection Rules"**
4. Click **"+ Create"** button

### 3.2 Basics Tab
- **Rule Name**: `test-vm-dcr`
- **Subscription**: ITGS Sandbox
- **Resource Group**: AZ26POC1-CO-LAB
- **Region**: West Europe
- **Platform Type**: Linux

Click **"Next: Resources >"**

### 3.3 Resources Tab
1. Click **"+ Add resources"**
2. In the panel that opens:
   - Expand **"ITGS Sandbox"**
   - Expand **"AZ26POC1-CO-LAB"**
   - Check the box next to **"Test-VM"**
3. Click **"Apply"**
4. You should see Test-VM listed

Click **"Next: Collect and deliver >"**

### 3.4 Collect and Deliver Tab

#### Add Performance Counters Data Source
1. Click **"+ Add data source"**
2. **Data source type**: Select **"Performance Counters"**
3. Under **"Basic"** or **"Custom"** tab, you'll see counter selection
4. Look for a section that shows performance counters - select these:
   - ✅ Processor (or CPU-related counters)
   - ✅ Memory
   - ✅ Disk (or Logical Disk)
   - ✅ Network (optional)
5. **Sample rate** or **Collection frequency**: 60 seconds

#### Configure Destination (Same Page)
6. Scroll down on the same page to **"Destination"** section
7. **Destination type**: Select **"Azure Monitor Logs"** or **"Log Analytics"**
8. **Log Analytics workspace**: Select your workspace `test-vm-workspace`
   - If you don't see it, click the dropdown and find it
   - It should show: `test-vm-workspace (AZ26POC1-CO-LAB)`
9. Click **"Add data source"** button at the bottom

#### Add Syslog Data Source (Optional but Recommended)
1. Click **"+ Add data source"** again
2. **Data source type**: Select **"Linux Syslog"** or **"Syslog"**
3. You'll see a list of facilities (auth, cron, daemon, etc.)
4. For each facility, set minimum log level to **"LOG_ERR"** or **"Error"**
5. Scroll down to **"Destination"** section (same page)
6. **Destination type**: Azure Monitor Logs
7. **Log Analytics workspace**: Select `test-vm-workspace`
8. Click **"Add data source"**

### 3.5 Review and Create
1. Click **"Review + create"**
2. Click **"Create"**
3. Wait 1-2 minutes for deployment

---

## Step 4: Verify Azure Monitor Agent Status

### 4.1 Check Agent Extension
1. Go to Azure Portal → Search for **"Test-VM"**
2. Click on your VM **"Test-VM"**
3. In left menu, click **"Extensions + applications"**
4. You should see: **"AzureMonitorLinuxAgent"**
5. Status should be: **"Provisioning succeeded"**

### 4.2 Wait for Data Collection
**IMPORTANT**: After creating the DCR, wait 10-15 minutes for:
- Agent to start collecting metrics
- Data to flow to Log Analytics workspace
- Metrics to become available in queries

☕ Take a coffee break! This is normal Azure behavior.

---

## Step 5: Update Web UI Configuration

### 5.1 Stop Current Web UI
1. Go to the terminal where web UI is running
2. Press **Ctrl+C** to stop it

### 5.2 Update .env File (Optional)
You can optionally add the workspace ID to your `.env` file:

```bash
# Open .env file and update this line:
AZURE_WORKSPACE_ID=your-workspace-id-here
```

Replace `your-workspace-id-here` with the ID you copied in Step 2.

**OR** you can provide it directly in the web UI (next step).

### 5.3 Restart Web UI
```bash
python main.py --ui
```

### 5.4 Configure Agent in Web UI
1. Open browser: http://localhost:8000
2. In the **"Agent Configuration"** section:
   - **VM Name**: Test-VM
   - **Resource Group**: AZ26POC1-CO-LAB
   - **Subscription ID**: be8946da-5ca2-4129-ae53-b6124a0aa2d1
   - **Workspace ID**: (paste the ID from Step 2)
   - **Interval**: 300 seconds
3. Click **"Start Agent"**

---

## Step 6: Verify Telemetry Collection

### 6.1 Wait for First Scan
After starting the agent, wait 5 minutes for the first collection cycle.

### 6.2 Check Dashboard
1. Refresh the web UI dashboard
2. Look at the **"Latest Status"** card
3. Check **"Data Completeness"** - it should now show 60-80% (instead of 11.54%)

### 6.3 Verify Metrics Are Present
In the diagnostic output, you should now see:
- ✅ `cpu_percent`: 25.5 (example value)
- ✅ `memory_percent`: 45.2 (example value)
- ✅ `os_disk_percent_full`: 35.8 (example value)
- ✅ `heartbeat_present`: true

### 6.4 Check LLM Provider
The output should also show:
- ✅ `llm_provider`: "groq" or "gemini" (instead of "unknown")

---

## Troubleshooting

### Issue 1: Workspace ID Not Working
**Symptom**: Still showing "heartbeat_present: null"

**Solution**:
1. Verify you copied the correct Workspace ID (not Workspace Name)
2. Wait full 15 minutes after creating DCR
3. Check agent extension status in Azure Portal

### Issue 2: Metrics Still Missing
**Symptom**: cpu_percent, memory_percent still null

**Solution**:
1. Go to Azure Portal → Test-VM → Insights
2. Click "Enable" if not already enabled
3. This creates additional monitoring configurations
4. Wait another 10 minutes

### Issue 3: Agent Extension Not Installed
**Symptom**: No "AzureMonitorLinuxAgent" in Extensions

**Solution**:
1. Go to Test-VM → Extensions + applications
2. Click "+ Add"
3. Search for "Azure Monitor Agent"
4. Select "Azure Monitor Agent for Linux"
5. Click "Next" → "Review + create" → "Create"
6. Wait 5 minutes for installation
7. Then follow Step 3 to create DCR

### Issue 4: LLM Still Shows "unknown"
**Symptom**: llm_provider still shows "unknown"

**Solution**:
1. Stop web UI (Ctrl+C)
2. Verify .env has: `LLM_ENABLED=true`
3. Verify API keys are set in .env
4. Restart: `python main.py --ui`
5. Start agent again in web UI

---

## Quick Reference

### Your Configuration
```
VM Name: Test-VM
Resource Group: AZ26POC1-CO-LAB
Subscription ID: be8946da-5ca2-4129-ae53-b6124a0aa2d1
Region: West Europe
VM OS: Ubuntu 24.04 LTS
Workspace ID: [You'll get this in Step 2]
```

### Expected Results After Setup
- **Data Completeness**: 60-80% (up from 11.54%)
- **LLM Provider**: groq or gemini (not "unknown")
- **Metrics Available**: CPU, memory, disk, heartbeat
- **Decision Quality**: Much better with more data

---

## Next Steps After Setup

Once you have 60-80% completeness:

1. **Initialize SOP Knowledge Base**:
   ```bash
   python -m setup.initialize_sop_kb
   ```

2. **Test LLM Decisions**: Let the agent run for a few cycles and observe the decisions

3. **Review Diagnostics**: Check if LLM provides better insights with complete data

---

## Need Help?

If you get stuck at any step:
1. Take a screenshot of the error
2. Note which step you're on
3. Check the Troubleshooting section above
4. Verify all IDs and names match exactly

**Common Mistakes**:
- ❌ Using Workspace Name instead of Workspace ID
- ❌ Not waiting 15 minutes after DCR creation
- ❌ Wrong region (must be West Europe)
- ❌ Forgetting to restart web UI after .env changes
