# Telemetry Setup Guide

## Current Status

Your agent is working with **basic telemetry** (20-30% completeness):
- ✅ Power state (Running/Stopped/Deallocated)
- ✅ Provisioning state (Succeeded/Failed)
- ✅ Resource health status (Available/Degraded/Unavailable)
- ❌ CPU usage, memory usage, disk usage
- ❌ Heartbeat monitoring
- ❌ Application health

## Why Low Completeness?

The missing metrics require:
1. **Azure Monitor Agent** installed on the VM
2. **Data Collection Rule (DCR)** to specify what to collect
3. **Log Analytics Workspace** (optional, for logs and heartbeat)

## Option A: Accept Basic Monitoring (Current State)

**Completeness**: 20-30%

**What you get**:
- VM power state and provisioning state
- Resource health status from Azure
- NSG firewall rules

**What you're missing**:
- Performance metrics (CPU, memory, disk)
- Heartbeat monitoring
- Application health

**When to use**: Quick setup, no Azure Monitor Agent installation needed

**Action**: None - you're already here!

## Option B: Add Azure Monitor Agent for Performance Metrics

**Completeness**: 60-80%

**What you get**:
- Everything from Option A
- CPU usage percentage
- Memory usage percentage and available MB
- Disk latency and disk usage percentage

**What you're still missing**:
- Heartbeat monitoring (requires Log Analytics)
- Application health logs

**Setup Steps**:

### 1. Install Azure Monitor Agent on Test-VM

```bash
# Via Azure CLI
az vm extension set \
  --name AzureMonitorWindowsAgent \
  --publisher Microsoft.Azure.Monitor \
  --resource-group AZ26POC1-CO-LAB \
  --vm-name Test-VM \
  --enable-auto-upgrade true
```

Or via Azure Portal:
1. Go to Azure Portal → Virtual Machines → Test-VM
2. Click "Extensions + applications" in left menu
3. Click "+ Add"
4. Search for "Azure Monitor Agent"
5. Click "Azure Monitor Windows Agent" → Create
6. Click "Review + create" → Create

### 2. Create Data Collection Rule (DCR)

```bash
# Create DCR for performance counters
az monitor data-collection rule create \
  --name "Test-VM-Performance-DCR" \
  --resource-group AZ26POC1-CO-LAB \
  --location <your-region> \
  --data-flows '[{"streams":["Microsoft-Perf"],"destinations":["azureMonitorMetrics"]}]' \
  --performance-counters '[
    {"name":"perfCounterDataSource","streams":["Microsoft-Perf"],"samplingFrequencyInSeconds":60,"counterSpecifiers":[
      "\\Processor(_Total)\\% Processor Time",
      "\\Memory\\Available MBytes",
      "\\Memory\\% Committed Bytes In Use",
      "\\LogicalDisk(_Total)\\% Free Space",
      "\\LogicalDisk(_Total)\\Avg. Disk sec/Read"
    ]}
  ]'

# Associate DCR with VM
az monitor data-collection rule association create \
  --name "Test-VM-DCR-Association" \
  --resource-group AZ26POC1-CO-LAB \
  --rule-id "/subscriptions/be8946da-5ca2-4129-ae53-b6124a0aa2d1/resourceGroups/AZ26POC1-CO-LAB/providers/Microsoft.Insights/dataCollectionRules/Test-VM-Performance-DCR" \
  --resource "/subscriptions/be8946da-5ca2-4129-ae53-b6124a0aa2d1/resourceGroups/AZ26POC1-CO-LAB/providers/Microsoft.Compute/virtualMachines/Test-VM"
```

Or via Azure Portal:
1. Go to Azure Portal → Monitor → Data Collection Rules
2. Click "+ Create"
3. Fill in:
   - Name: Test-VM-Performance-DCR
   - Resource Group: AZ26POC1-CO-LAB
   - Region: (same as your VM)
4. Click "Next: Resources"
5. Click "+ Add resources" → Select Test-VM → Add
6. Click "Next: Collect and deliver"
7. Click "+ Add data source"
8. Select "Performance Counters"
9. Select these counters:
   - Processor > % Processor Time
   - Memory > Available MBytes
   - Memory > % Committed Bytes In Use
   - LogicalDisk > % Free Space
   - LogicalDisk > Avg. Disk sec/Read
10. Set sampling rate: 60 seconds
11. Destination: Azure Monitor Metrics
12. Click "Review + create" → Create

### 3. Wait 5-10 minutes for metrics to start flowing

### 4. Verify metrics are available

```bash
# Check if metrics are being collected
az monitor metrics list \
  --resource "/subscriptions/be8946da-5ca2-4129-ae53-b6124a0aa2d1/resourceGroups/AZ26POC1-CO-LAB/providers/Microsoft.Compute/virtualMachines/Test-VM" \
  --metric "Percentage CPU"
```

## Option C: Add Log Analytics Workspace (Full Monitoring)

**Completeness**: 80-90%

**What you get**:
- Everything from Option B
- Heartbeat monitoring (VM agent health)
- Application logs and events
- Custom log queries

**Setup Steps**:

### 1. Create Log Analytics Workspace

```bash
# Create workspace
az monitor log-analytics workspace create \
  --resource-group AZ26POC1-CO-LAB \
  --workspace-name Test-VM-Workspace \
  --location <your-region>

# Get workspace ID
az monitor log-analytics workspace show \
  --resource-group AZ26POC1-CO-LAB \
  --workspace-name Test-VM-Workspace \
  --query customerId -o tsv
```

Or via Azure Portal:
1. Go to Azure Portal → Log Analytics workspaces
2. Click "+ Create"
3. Fill in:
   - Resource Group: AZ26POC1-CO-LAB
   - Name: Test-VM-Workspace
   - Region: (same as your VM)
4. Click "Review + create" → Create
5. Once created, go to the workspace
6. Click "Agents" in left menu
7. Copy the "Workspace ID" (you'll need this)

### 2. Install Azure Monitor Agent (if not already done)

Follow Step 1 from Option B above.

### 3. Create DCR with Log Analytics destination

```bash
# Create DCR with both metrics and logs
az monitor data-collection rule create \
  --name "Test-VM-Full-DCR" \
  --resource-group AZ26POC1-CO-LAB \
  --location <your-region> \
  --data-flows '[
    {"streams":["Microsoft-Perf"],"destinations":["azureMonitorMetrics"]},
    {"streams":["Microsoft-Event","Microsoft-Syslog"],"destinations":["logAnalyticsWorkspace"]}
  ]' \
  --log-analytics '[{"workspaceResourceId":"/subscriptions/be8946da-5ca2-4129-ae53-b6124a0aa2d1/resourceGroups/AZ26POC1-CO-LAB/providers/Microsoft.OperationalInsights/workspaces/Test-VM-Workspace","name":"logAnalyticsWorkspace"}]' \
  --performance-counters '[
    {"name":"perfCounterDataSource","streams":["Microsoft-Perf"],"samplingFrequencyInSeconds":60,"counterSpecifiers":[
      "\\Processor(_Total)\\% Processor Time",
      "\\Memory\\Available MBytes",
      "\\Memory\\% Committed Bytes In Use",
      "\\LogicalDisk(_Total)\\% Free Space",
      "\\LogicalDisk(_Total)\\Avg. Disk sec/Read"
    ]}
  ]' \
  --windows-event-logs '[
    {"name":"eventLogsDataSource","streams":["Microsoft-Event"],"xPathQueries":[
      "Application!*[System[(Level=1 or Level=2 or Level=3)]]",
      "System!*[System[(Level=1 or Level=2 or Level=3)]]"
    ]}
  ]'

# Associate DCR with VM
az monitor data-collection rule association create \
  --name "Test-VM-Full-DCR-Association" \
  --resource-group AZ26POC1-CO-LAB \
  --rule-id "/subscriptions/be8946da-5ca2-4129-ae53-b6124a0aa2d1/resourceGroups/AZ26POC1-CO-LAB/providers/Microsoft.Insights/dataCollectionRules/Test-VM-Full-DCR" \
  --resource "/subscriptions/be8946da-5ca2-4129-ae53-b6124a0aa2d1/resourceGroups/AZ26POC1-CO-LAB/providers/Microsoft.Compute/virtualMachines/Test-VM"
```

Or via Azure Portal:
1. Follow Option B steps but add Log Analytics workspace as destination
2. Add Windows Event Logs data source (Application and System logs)

### 4. Update .env with workspace ID

```bash
# Edit .env file
AZURE_WORKSPACE_ID=<your-workspace-id-from-step-1>
```

### 5. Restart agent to pick up workspace ID

Stop and restart the web UI:
```bash
# Press Ctrl+C to stop
python main.py --ui
```

### 6. Wait 5-10 minutes for logs to start flowing

### 7. Verify heartbeat is working

```bash
# Query heartbeat table
az monitor log-analytics query \
  --workspace "<workspace-id>" \
  --analytics-query "Heartbeat | where Computer == 'Test-VM' | summarize max(TimeGenerated)"
```

## Recommendation

For production use, I recommend **Option C** (full monitoring) because:
- You get complete visibility into VM health
- LLM can make better decisions with more data
- Heartbeat monitoring is critical for detecting VM agent failures
- Cost is minimal (Log Analytics is pay-per-GB, typically $2-3/month per VM)

For testing/demo purposes, **Option A** (current state) is fine if you:
- Just want to see the system working
- Don't need accurate performance metrics
- Accept that LLM will often abstain due to insufficient data

## Next Steps

1. **Restart Web UI** to fix LLM provider issue:
   ```bash
   # Press Ctrl+C to stop current UI
   python main.py --ui
   ```

2. **Initialize SOP Knowledge Base**:
   ```bash
   python -m setup.initialize_sop_kb
   ```

3. **Choose monitoring level** (A, B, or C above)

4. **Test the agent** and verify completeness improves

## Troubleshooting

### Agent shows "Provider: unknown"
- Restart the web UI to reload environment variables

### Metrics still showing None after 10 minutes
- Check Azure Monitor Agent is installed: `az vm extension list --resource-group AZ26POC1-CO-LAB --vm-name Test-VM`
- Check DCR is associated: `az monitor data-collection rule association list --resource-group AZ26POC1-CO-LAB`
- Check VM is running: `az vm show --name Test-VM --resource-group AZ26POC1-CO-LAB --query "powerState"`

### Heartbeat not showing up
- Verify Log Analytics workspace ID is correct in `.env`
- Check Azure Monitor Agent is sending data: Go to Azure Portal → Log Analytics workspace → Agents → Check "Heartbeats received"
- Wait 10-15 minutes for first heartbeat to appear

### LLM still abstaining with 60%+ completeness
- This is normal if the VM is healthy (no issues to diagnose)
- Try stopping the VM to trigger a diagnosis: `az vm deallocate --name Test-VM --resource-group AZ26POC1-CO-LAB`
- Then start it again: `az vm start --name Test-VM --resource-group AZ26POC1-CO-LAB`
