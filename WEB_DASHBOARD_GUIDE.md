# 🌐 Web Dashboard Guide - Azure Agent Mode

**Run Azure VM monitoring through your browser - No command line needed!**

This guide shows you how to set up and use the Web Dashboard to monitor your Azure VMs in real-time.

---

## 📋 What You'll Need

Before starting, make sure you have:

- ✅ Python 3.8+ installed
- ✅ Project dependencies installed
- ✅ Azure credentials ready (Tenant ID, Client ID, Secret, etc.)
- ✅ A web browser (Chrome, Firefox, Edge, Safari)

**Don't have these?** See [SETUP_GUIDE.md](SETUP_GUIDE.md) first.

---

## 🚀 Quick Start (5 Minutes)

### Step 1: Install Web UI Dependencies

Open your terminal and run:

```bash
pip install -r requirements-ui.txt
```

This installs:
- FastAPI (web framework)
- Uvicorn (web server)
- Jinja2 (templates)

**Check it worked:**
```bash
pip list | grep fastapi
```

You should see `fastapi` in the list.

---

### Step 2: Start the Web Dashboard

In your terminal, run:

```bash
python main.py --ui
```

**You should see:**
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

✅ **Success!** The web server is running.

---

### Step 3: Open the Dashboard

Open your web browser and go to:

```
http://localhost:8000
```

**You should see:**
- A blue header saying "Azure VM Incident Copilot"
- Five tabs: Dashboard, Live Feed, Manual Triage, Agent Control, Benchmark
- A clean, modern interface

✅ **Success!** The dashboard is loaded.

---

## 🎯 Using the Agent Control Tab

### Step 1: Click "Agent Control" Tab

Click the **"Agent Control"** tab at the top of the page.

You'll see a form with these fields:
- VM Name
- Resource Group
- Subscription ID
- Workspace ID (optional)
- Interval (seconds)

---

### Step 2: Fill in Your Azure Details

**Where to find these values:**

#### VM Name
- Azure Portal → Virtual Machines → Your VM → Name
- Example: `my-production-vm`

#### Resource Group
- Azure Portal → Resource Groups → Your group name
- Example: `production-rg`

#### Subscription ID
- Azure Portal → Subscriptions → Copy the ID
- Example: `12345678-1234-1234-1234-123456789012`

#### Workspace ID (Optional)
- Azure Portal → Log Analytics workspaces → Your workspace → Properties → Workspace ID
- Example: `a1b2c3d4-5678-90ab-cdef-1234567890ab`
- **Leave blank if you don't have Log Analytics**

#### Interval (seconds)
- How often to check the VM
- Default: `300` (5 minutes)
- For testing: Use `60` (1 minute)

---

### Step 3: Configure Azure Credentials

**IMPORTANT:** The agent needs Azure credentials to access your VM.

#### Option A: Using .env File (Recommended)

1. **Create .env file:**
   ```bash
   cp .env.example .env
   ```

2. **Edit .env file** with your credentials:
   ```
   AZURE_TENANT_ID=your-tenant-id-here
   AZURE_CLIENT_ID=your-client-id-here
   AZURE_CLIENT_SECRET=your-secret-here
   AZURE_SUBSCRIPTION_ID=your-subscription-id-here
   ```

3. **Restart the web dashboard:**
   - Press `Ctrl+C` in terminal
   - Run `python main.py --ui` again

#### Option B: Using Environment Variables

**Windows:**
```cmd
set AZURE_TENANT_ID=your-tenant-id
set AZURE_CLIENT_ID=your-client-id
set AZURE_CLIENT_SECRET=your-secret
set AZURE_SUBSCRIPTION_ID=your-subscription-id
python main.py --ui
```

**macOS/Linux:**
```bash
export AZURE_TENANT_ID=your-tenant-id
export AZURE_CLIENT_ID=your-client-id
export AZURE_CLIENT_SECRET=your-secret
export AZURE_SUBSCRIPTION_ID=your-subscription-id
python main.py --ui
```

**How to get Azure credentials:** See [Azure Credentials Guide](#-azure-credentials-guide) below.

---

### Step 4: Start the Agent

1. **Fill in all required fields** (VM Name, Resource Group, Subscription ID)
2. **Click the green "Start Agent" button**
3. **Wait for confirmation**

**You should see:**
- A popup saying "Agent started successfully"
- The agent will start collecting telemetry every X seconds

✅ **Success!** The agent is now running.

---

### Step 5: View Results

#### Option 1: Dashboard Tab

1. Click the **"Dashboard"** tab
2. You'll see two cards:
   - **VM Status**: Current VM health and diagnosis
   - **Agent Status**: Agent running status and last run time

**What you'll see:**
- VM Name and Resource Group
- Decision (diagnose / low confidence / abstain)
- Confidence Score (0.0 to 1.0)
- Diagnosis message
- Last scan timestamp

#### Option 2: Live Feed Tab

1. Click the **"Live Feed"** tab
2. You'll see a table with all scan results:
   - Timestamp
   - VM Name
   - Decision
   - Confidence
   - Diagnosis
   - Duration

**Filter results:**
- Use the dropdown to filter by decision type
- Click "Export CSV" to download results

---

### Step 6: Stop the Agent

When you're done:

1. Go to **"Agent Control"** tab
2. Click the red **"Stop Agent"** button
3. Wait for confirmation

**You should see:**
- A popup saying "Agent stopped successfully"

✅ **Success!** The agent has stopped.

---

## 🔍 Testing Everything Works

### Test 1: Check Agent Status

1. Go to **Dashboard** tab
2. Look at the **Agent Status** card
3. **Should show:**
   - Status: Running (green badge)
   - Interval: 300s (or your configured value)
   - Last Run: Recent timestamp

✅ **Pass:** Agent is running correctly.

---

### Test 2: Trigger Manual Scan

1. Go to **Dashboard** tab
2. Click the blue **"Scan Now"** button
3. Wait 5-10 seconds
4. **Should show:**
   - Popup: "Scan triggered successfully"
   - VM Status card updates with new data

✅ **Pass:** Manual scan works.

---

### Test 3: Check VM Status

1. Go to **Dashboard** tab
2. Look at the **VM Status** card
3. **Should show:**
   - VM Name: Your VM name
   - Resource Group: Your resource group
   - Decision: One of (diagnose / diagnose_low_confidence / abstain_request_next_check)
   - Confidence: A number between 0.0 and 1.0
   - Diagnosis: A message describing the VM state
   - Last Scan: Recent timestamp

✅ **Pass:** VM monitoring works.

---

### Test 4: View Live Feed

1. Go to **Live Feed** tab
2. **Should show:**
   - Table with multiple rows (if agent has run multiple times)
   - Each row shows: timestamp, VM name, decision, confidence, diagnosis, duration

✅ **Pass:** Live feed works.

---

### Test 5: Auto-Refresh

1. Go to **Dashboard** tab
2. Check the **"Auto-refresh (30s)"** checkbox
3. Wait 30 seconds
4. **Should show:**
   - Dashboard automatically updates every 30 seconds
   - No need to manually refresh

✅ **Pass:** Auto-refresh works.

---

## 🎨 Dashboard Features

### Dashboard Tab
- **VM Status Card**: Current VM health and diagnosis
- **Agent Status Card**: Agent running status
- **Scan Now Button**: Trigger immediate scan
- **Auto-refresh Checkbox**: Auto-update every 30 seconds

### Live Feed Tab
- **Table View**: All scan results in chronological order
- **Filter Dropdown**: Filter by decision type
- **Export CSV Button**: Download results as CSV
- **Real-time Updates**: See new scans as they happen

### Manual Triage Tab
- **JSON Input**: Paste telemetry JSON manually
- **Run Triage Button**: Process the JSON
- **Result Display**: See diagnosis, evidence, next steps
- **Useful for**: Testing scenarios without Azure

### Agent Control Tab
- **Configuration Form**: Set VM details and interval
- **Start/Stop Buttons**: Control the agent
- **Agent Logs**: View agent activity (console output)

### Benchmark Tab
- **Run Benchmark Button**: Test all 38 scenarios
- **Summary Cards**: Total, passed, failed, pass rate
- **Results Table**: Detailed results for each case
- **Useful for**: Verifying system works correctly

---

## 🛠️ Troubleshooting

### Problem: "Agent is not running" error when clicking "Scan Now"

**Solution:**
1. Go to **Agent Control** tab
2. Fill in all required fields
3. Click **"Start Agent"** button
4. Wait for "Agent started successfully" message
5. Try "Scan Now" again

---

### Problem: "Authentication failed" error

**Solution:**
1. Check your `.env` file has correct credentials
2. Verify credentials work:
   ```bash
   az login
   az account show
   ```
3. Restart the web dashboard:
   - Press `Ctrl+C` in terminal
   - Run `python main.py --ui` again

---

### Problem: "VM not found" error

**Solution:**
1. Verify VM name is correct (case-sensitive)
2. Verify resource group is correct
3. Check VM exists:
   ```bash
   az vm show --name my-vm --resource-group my-rg
   ```

---

### Problem: Dashboard shows "No data available"

**Solution:**
1. Make sure agent is running (check Agent Status card)
2. Wait for first scan to complete (check interval setting)
3. Click "Scan Now" to trigger immediate scan
4. Check terminal for error messages

---

### Problem: "Port already in use" error

**Solution:**
1. Another process is using port 8000
2. Stop the other process, or
3. Use a different port:
   ```bash
   # Edit ui/app.py, change port to 8001
   uvicorn.run(app, host="0.0.0.0", port=8001)
   ```
4. Access at: http://localhost:8001

---

### Problem: Dashboard is slow or unresponsive

**Solution:**
1. Check terminal for errors
2. Reduce scan interval (use 300 seconds or more)
3. Disable auto-refresh if not needed
4. Close other browser tabs
5. Restart the web dashboard

---

## 🔐 Azure Credentials Guide

### What You Need

To use the agent, you need:
1. **Tenant ID** - Your Azure AD tenant
2. **Client ID** - Service principal app ID
3. **Client Secret** - Service principal password
4. **Subscription ID** - Your Azure subscription

### How to Get Them

#### Step 1: Get Tenant ID and Subscription ID

**Using Azure Portal:**
1. Go to Azure Portal → Azure Active Directory → Properties
2. Copy **Tenant ID**
3. Go to Subscriptions
4. Copy **Subscription ID**

**Using Azure CLI:**
```bash
az account show
```

Look for:
- `tenantId` → Your Tenant ID
- `id` → Your Subscription ID

---

#### Step 2: Create Service Principal

**Using Azure CLI:**
```bash
az ad sp create-for-rbac --name "IncidentCopilotAgent" --role "Reader" --scopes "/subscriptions/be8946da-5ca2-4129-ae53-b6124a0aa2d1"
```

**Output:**
```json
{
  "appId": "12345678-1234-1234-1234-123456789012",
  "password": "your-secret-here",
  "tenant": "87654321-4321-4321-4321-210987654321"
}
```

- `appId` → Your **Client ID**
- `password` → Your **Client Secret**
- `tenant` → Your **Tenant ID** (verify matches)

---

#### Step 3: Verify Permissions

The service principal needs **Reader** role on your resource group:

```bash
az role assignment list --assignee {client-id}
```

Should show:
- Role: Reader
- Scope: /subscriptions/{sub-id}/resourceGroups/{rg-name}

---

#### Step 4: Save Credentials

**Create .env file:**
```bash
cp .env.example .env
```

**Edit .env:**
```
AZURE_TENANT_ID=87654321-4321-4321-4321-210987654321
AZURE_CLIENT_ID=12345678-1234-1234-1234-123456789012
AZURE_CLIENT_SECRET=your-secret-here
AZURE_SUBSCRIPTION_ID=abcdef12-3456-7890-abcd-ef1234567890
```

**IMPORTANT:** Never commit .env to git! It's already in .gitignore.

---

## 📊 Understanding the Results

### Decision Types

#### 🟢 diagnose
- **Meaning**: High confidence diagnosis
- **Confidence**: ≥ 0.70
- **Completeness**: ≥ 90%
- **Action**: Follow the "Next Check" recommendation

#### 🟡 diagnose_low_confidence
- **Meaning**: Medium confidence diagnosis
- **Confidence**: 0.40 - 0.69
- **Completeness**: 60% - 89%
- **Action**: Gather more data, then follow recommendation

#### 🔴 abstain_request_next_check
- **Meaning**: Not enough data or safety rule triggered
- **Confidence**: < 0.40
- **Completeness**: < 60%
- **Action**: Follow "Next Check" to gather more telemetry

---

### Confidence Score

- **0.9 - 1.0**: Very high confidence - safe to act
- **0.7 - 0.9**: High confidence - likely correct
- **0.4 - 0.7**: Medium confidence - verify first
- **0.0 - 0.4**: Low confidence - gather more data

---

### Evidence

Shows which telemetry signals support the diagnosis:
- `power_state=Stopped` - VM is stopped
- `cpu_percent=95.0` - High CPU usage
- `nsg_allows_rdp=False` - RDP port blocked

---

### Evidence Gap

Shows which telemetry fields are missing:
- `boot_diagnostics not available` - Need boot screenshots
- `memory_percent not available` - Need Azure Monitor Agent
- `heartbeat not available` - Need Log Analytics

---

## 🎓 Best Practices

### 1. Start with Testing

- Use interval of 60 seconds for testing
- Monitor 1 VM first
- Verify results are accurate
- Then scale to more VMs

### 2. Production Settings

- Use interval of 300 seconds (5 minutes) or more
- Monitor critical VMs more frequently
- Use auto-refresh sparingly (increases load)
- Export feed data regularly for analysis

### 3. Security

- Never share your .env file
- Rotate credentials regularly (every 90 days)
- Use least-privilege permissions (Reader role only)
- Monitor Azure API usage

### 4. Monitoring

- Check Agent Status card regularly
- Review Live Feed for patterns
- Export CSV data for trending
- Set up alerts for "diagnose" decisions

---

## 🚪 Stopping the Dashboard

When you're done:

1. **Stop the agent** (if running):
   - Go to Agent Control tab
   - Click "Stop Agent"

2. **Close the browser**

3. **Stop the web server**:
   - Go to terminal
   - Press `Ctrl+C`

**You should see:**
```
INFO:     Shutting down
INFO:     Finished server process
```

✅ **Done!** Everything is stopped.

---

## 📚 Next Steps

### Learn More
- [SETUP_GUIDE.md](SETUP_GUIDE.md) - Complete setup instructions
- [FAQ.md](FAQ.md) - Frequently asked questions
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Common issues

### Advanced Features
- Customize incident patterns
- Add custom telemetry fields
- Integrate with monitoring systems
- Set up email alerts

### Get Help
- Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- Review terminal output for errors
- Contact project maintainers

---

## ✅ Quick Checklist

Use this to verify everything is working:

- [ ] Web UI dependencies installed (`pip install -r requirements-ui.txt`)
- [ ] Web dashboard started (`python main.py --ui`)
- [ ] Dashboard opens in browser (http://localhost:8000)
- [ ] Azure credentials configured (.env file)
- [ ] Agent Control form filled in
- [ ] Agent started successfully
- [ ] Dashboard shows VM status
- [ ] Live Feed shows scan results
- [ ] Manual scan works ("Scan Now" button)
- [ ] Auto-refresh works (checkbox)
- [ ] Agent stopped successfully

---

**🎉 Congratulations! You're now monitoring Azure VMs through the web dashboard!**

**Questions?** See [FAQ.md](FAQ.md) or [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
