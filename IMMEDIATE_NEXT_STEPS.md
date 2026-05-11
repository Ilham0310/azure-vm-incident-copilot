# Immediate Next Steps

## Issue 1: LLM showing "Provider: unknown"

**Root Cause**: Web UI started before `LLM_ENABLED=true` was set in `.env`

**Fix** (takes 30 seconds):

1. Stop the web UI (press `Ctrl+C` in the terminal)
2. Restart it:
   ```bash
   python main.py --ui
   ```
3. Go to http://localhost:8000
4. Start the agent
5. Check "Provider" field - should now show "groq" instead of "unknown"

## Issue 2: SOP Knowledge Base Not Initialized

**Root Cause**: LLM needs SOP documents loaded into vector database

**Fix** (takes 1-2 minutes):

```bash
python -m setup.initialize_sop_kb
```

Expected output:
```
Initializing SOP knowledge base...
✓ Loaded 12 SOPs from data/sops/
✓ Created embeddings and stored in ChromaDB
✓ SOP knowledge base ready
```

## Issue 3: Low Telemetry Completeness (20-30%)

**Root Cause**: Azure Monitor Agent not installed, no performance metrics available

**Current State**:
- ✅ Basic VM info (power state, provisioning state, resource health)
- ❌ Performance metrics (CPU, memory, disk)
- ❌ Heartbeat monitoring
- ❌ Application logs

**Decision**: Choose your monitoring level

### Quick Decision Matrix

| Option | Completeness | Setup Time | What You Get |
|--------|-------------|------------|--------------|
| **A: Current State** | 20-30% | 0 min (done) | Basic VM status only |
| **B: Add Monitor Agent** | 60-80% | 10-15 min | + CPU, memory, disk metrics |
| **C: Add Log Analytics** | 80-90% | 15-20 min | + Heartbeat, logs, full monitoring |

### Recommendation

**For testing/demo**: Stick with Option A (current state)
- Agent works fine with basic telemetry
- LLM will abstain more often due to insufficient data
- No Azure setup needed

**For production**: Use Option C (full monitoring)
- See detailed guide in `TELEMETRY_SETUP_GUIDE.md`
- Requires Azure Monitor Agent + Log Analytics workspace
- Best LLM decision quality

## What Happens After Fixes?

Once you restart the web UI and initialize SOPs:

1. **LLM Provider**: Will show "groq" instead of "unknown"
2. **LLM Reasoning**: Will include SOP recommendations in decisions
3. **Decision Quality**: Will improve with SOP context

Example decision with SOPs:
```
Decision: abstain_request_next_check
Confidence: 0.64
Diagnosis: Insufficient telemetry data
Evidence: power_state=Running, provisioning_state=Succeeded, resource_health_status=Available
Evidence Gap: heartbeat_present, cpu_percent, memory_percent, os_disk_percent_full
Next Check: Gather more telemetry data to reach at least 60% completeness
LLM Provider: groq
SOPs Consulted: sop_start_stop_vm.md, sop_vm_scale.md
```

## Testing the Fixes

After restarting web UI and initializing SOPs:

1. Go to http://localhost:8000
2. Click "Start Agent"
3. Fill in:
   - VM Name: Test-VM
   - Resource Group: AZ26POC1-CO-LAB
   - Subscription ID: be8946da-5ca2-4129-ae53-b6124a0aa2d1
   - Workspace ID: (leave empty for now)
   - Interval: 300 seconds
4. Click "Start"
5. Wait 30 seconds
6. Check the decision details:
   - Provider should show "groq" ✅
   - Pattern Matched should show a value (not "unknown") ✅
   - Similar Incidents Retrieved should show 0 (normal for first run) ✅

## Summary

**Right now, do these 2 things**:

1. **Restart web UI** (fixes LLM provider):
   ```bash
   # Press Ctrl+C, then:
   python main.py --ui
   ```

2. **Initialize SOPs** (enables LLM recommendations):
   ```bash
   python -m setup.initialize_sop_kb
   ```

**Later, if you want better telemetry**:
- Read `TELEMETRY_SETUP_GUIDE.md`
- Choose Option B or C
- Follow the Azure setup steps

## Questions?

- **Q: Will the agent work with 20% completeness?**
  - A: Yes! It will just abstain more often and ask for more data.

- **Q: Do I need to install Azure Monitor Agent?**
  - A: No, not for testing. Only if you want performance metrics.

- **Q: Why does LLM keep abstaining?**
  - A: Because the VM is healthy and there's not enough data to diagnose anything. This is correct behavior!

- **Q: How do I test if LLM can diagnose issues?**
  - A: Stop the VM (`az vm deallocate --name Test-VM --resource-group AZ26POC1-CO-LAB`), then run the agent. It should diagnose "VM is deallocated".
