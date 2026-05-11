# Incident Patterns Documentation

## Overview

The Azure VM Incident Copilot recognizes 20 known incident patterns based on telemetry signals. Each pattern has specific matching conditions, expected diagnosis, evidence list, and recommended next check action. This document provides detailed information about each pattern, including telemetry examples and diagnostic guidance.

## Pattern Categories

The 20 patterns are organized into the following categories:

1. **Power and Provisioning** (3 patterns): VM state issues
2. **Network Connectivity** (3 patterns): NSG and connection issues
3. **Performance** (4 patterns): CPU, memory, and disk saturation
4. **Boot Failures** (3 patterns): BSOD, kernel panic, stuck boot
5. **Agent Failures** (3 patterns): VM agent and monitoring agent issues
6. **Resource Health** (2 patterns): Platform degradation and health issues
7. **Application Health** (1 pattern): Application-level issues
8. **Signal Conflicts** (1 pattern): Inconsistent telemetry

## Pattern Details

### Category 1: Power and Provisioning

---

#### Pattern 1: VM Stopped by User

**Pattern ID:** `vm_stopped_by_user`

**Matching Conditions:**
```
power_state = "Stopped"
provisioning_state = "Succeeded"
```

**Diagnosis:** "VM Stopped by user deallocation"

**Evidence:**
- `power_state=Stopped`
- `provisioning_state=Succeeded`

**Next Check:** "Start VM if needed, or confirm intentional stop"

**Telemetry Example:**

```json
{
  "power_state": "Stopped",
  "provisioning_state": "Succeeded",
  "resource_health_status": "Available"
}
```

**Expected Output:**

```json
{
  "decision": "diagnose",
  "diagnosis": "VM Stopped by user deallocation",
  "confidence_score": 0.85,
  "evidence": [
    "power_state=Stopped",
    "provisioning_state=Succeeded",
    "resource_health_status=Available"
  ],
  "evidence_gap": [],
  "next_check": "Start VM if needed, or confirm intentional stop",
  "explanation": "VM is stopped with successful provisioning. This indicates user-initiated deallocation. No remediation needed unless VM should be running."
}
```

---

#### Pattern 14: VM Deallocated

**Pattern ID:** `vm_deallocated`

**Matching Conditions:**
```
power_state = "Deallocated"
```

**Diagnosis:** "Deallocated VM"

**Evidence:**
- `power_state=Deallocated`

**Next Check:** "Start VM if needed"

**Telemetry Example:**

```json
{
  "power_state": "Deallocated",
  "provisioning_state": "Succeeded",
  "resource_health_status": "Available"
}
```

**Expected Output:**

```json
{
  "decision": "diagnose",
  "diagnosis": "Deallocated VM",
  "confidence_score": 0.80,
  "evidence": [
    "power_state=Deallocated",
    "provisioning_state=Succeeded"
  ],
  "next_check": "Start VM if needed"
}
```

---

#### Pattern 15: Provisioning Failed

**Pattern ID:** `provisioning_failed`

**Matching Conditions:**
```
provisioning_state = "Failed"
```

**Diagnosis:** "Provisioning failed"

**Evidence:**
- `provisioning_state=Failed`

**Next Check:** "Review provisioning logs and retry deployment"

**Telemetry Example:**

```json
{
  "power_state": "Failed",
  "provisioning_state": "Failed",
  "resource_health_status": "Unavailable"
}
```

**Expected Output:**

```json
{
  "decision": "diagnose",
  "diagnosis": "Provisioning failed",
  "confidence_score": 0.75,
  "evidence": [
    "power_state=Failed",
    "provisioning_state=Failed",
    "resource_health_status=Unavailable"
  ],
  "next_check": "Review provisioning logs and retry deployment"
}
```

---

### Category 2: Network Connectivity

---

#### Pattern 2: NSG Blocks RDP

**Pattern ID:** `nsg_blocks_rdp`

**Matching Conditions:**
```
nsg_allow_rdp_3389 = false
connection_troubleshoot_rdp = "Deny"
```

**Diagnosis:** "NSG blocks RDP"

**Evidence:**
- `nsg_allow_rdp_3389=False`
- `connection_troubleshoot_rdp=Deny`

**Next Check:** "Review NSG rules for port 3389 and update if RDP access is required"

**Telemetry Example:**

```json
{
  "power_state": "Running",
  "provisioning_state": "Succeeded",
  "resource_health_status": "Available",
  "nsg_allow_rdp_3389": false,
  "connection_troubleshoot_rdp": "Deny"
}
```

**Expected Output:**

```json
{
  "decision": "diagnose",
  "diagnosis": "NSG blocks RDP",
  "confidence_score": 0.90,
  "evidence": [
    "power_state=Running",
    "nsg_allow_rdp_3389=False",
    "connection_troubleshoot_rdp=Deny"
  ],
  "next_check": "Review NSG rules for port 3389 and update if RDP access is required"
}
```

---

#### Pattern 3: NSG Blocks SSH

**Pattern ID:** `nsg_blocks_ssh`

**Matching Conditions:**
```
nsg_allow_ssh_22 = false
connection_troubleshoot_ssh = "Deny"
```

**Diagnosis:** "NSG blocks SSH"

**Evidence:**
- `nsg_allow_ssh_22=False`
- `connection_troubleshoot_ssh=Deny`

**Next Check:** "Review NSG rules for port 22 and update if SSH access is required"

**Telemetry Example:**

```json
{
  "power_state": "Running",
  "provisioning_state": "Succeeded",
  "resource_health_status": "Available",
  "nsg_allow_ssh_22": false,
  "connection_troubleshoot_ssh": "Deny"
}
```

**Expected Output:**

```json
{
  "decision": "diagnose",
  "diagnosis": "NSG blocks SSH",
  "confidence_score": 0.90,
  "evidence": [
    "power_state=Running",
    "nsg_allow_ssh_22=False",
    "connection_troubleshoot_ssh=Deny"
  ],
  "next_check": "Review NSG rules for port 22 and update if SSH access is required"
}
```

---

#### Pattern 11: Conflicting NSG Signals

**Pattern ID:** `conflicting_nsg_signals`

**Matching Conditions:**
```
nsg_allow_rdp_3389 = false
connection_troubleshoot_rdp = "Allow"
```

**Diagnosis:** "Conflicting NSG and connection troubleshoot signals"

**Evidence:**
- `nsg_allow_rdp_3389=False`
- `connection_troubleshoot_rdp=Allow`

**Next Check:** "Review NSG configuration and connection troubleshoot results for inconsistencies"

**Telemetry Example:**

```json
{
  "power_state": "Running",
  "provisioning_state": "Succeeded",
  "resource_health_status": "Available",
  "nsg_allow_rdp_3389": false,
  "connection_troubleshoot_rdp": "Allow"
}
```

**Expected Output:**

```json
{
  "decision": "diagnose_low_confidence",
  "diagnosis": "Conflicting NSG and connection troubleshoot signals",
  "confidence_score": 0.55,
  "evidence": [
    "power_state=Running",
    "nsg_allow_rdp_3389=False",
    "connection_troubleshoot_rdp=Allow"
  ],
  "next_check": "Review NSG configuration and connection troubleshoot results for inconsistencies"
}
```

---

### Category 3: Performance

---

#### Pattern 4: High CPU Saturation

**Pattern ID:** `high_cpu`

**Matching Conditions:**
```
cpu_percent > 95
```

**Diagnosis:** "High CPU saturation"

**Evidence:**
- `cpu_percent=<value>`

**Next Check:** "Identify high CPU processes and optimize or scale VM"

**Telemetry Example:**

```json
{
  "power_state": "Running",
  "provisioning_state": "Succeeded",
  "resource_health_status": "Degraded",
  "cpu_percent": 98.0,
  "memory_percent": 45.0,
  "heartbeat_present": true
}
```

**Expected Output:**

```json
{
  "decision": "diagnose",
  "diagnosis": "High CPU saturation",
  "confidence_score": 0.85,
  "evidence": [
    "power_state=Running",
    "provisioning_state=Succeeded",
    "resource_health_status=Degraded",
    "cpu_percent=98.0"
  ],
  "next_check": "Identify high CPU processes and optimize or scale VM"
}
```

---

#### Pattern 6: Memory Exhaustion

**Pattern ID:** `memory_exhaustion`

**Matching Conditions:**
```
memory_percent > 95
```

**Diagnosis:** "Memory exhaustion"

**Evidence:**
- `memory_percent=<value>`

**Next Check:** "Identify memory-intensive processes and optimize or scale VM"

**Telemetry Example:**

```json
{
  "power_state": "Running",
  "provisioning_state": "Succeeded",
  "resource_health_status": "Degraded",
  "cpu_percent": 45.0,
  "memory_percent": 98.0,
  "heartbeat_present": true
}
```

**Expected Output:**

```json
{
  "decision": "diagnose",
  "diagnosis": "Memory exhaustion",
  "confidence_score": 0.85,
  "evidence": [
    "power_state=Running",
    "memory_percent=98.0"
  ],
  "next_check": "Identify memory-intensive processes and optimize or scale VM"
}
```

---

#### Pattern 5: OS Disk Full

**Pattern ID:** `os_disk_full`

**Matching Conditions:**
```
os_disk_percent_full > 95
```

**Diagnosis:** "OS disk full"

**Evidence:**
- `os_disk_percent_full=<value>`

**Next Check:** "Free up disk space or expand OS disk capacity"

**Telemetry Example:**

```json
{
  "power_state": "Running",
  "provisioning_state": "Succeeded",
  "resource_health_status": "Degraded",
  "os_disk_percent_full": 98.0,
  "cpu_percent": 45.0,
  "memory_percent": 50.0
}
```

**Expected Output:**

```json
{
  "decision": "diagnose",
  "diagnosis": "OS disk full",
  "confidence_score": 0.85,
  "evidence": [
    "power_state=Running",
    "os_disk_percent_full=98.0"
  ],
  "next_check": "Free up disk space or expand OS disk capacity"
}
```

---

#### Pattern 13: Disk IO Saturation

**Pattern ID:** `disk_io_saturation`

**Matching Conditions:**
```
os_disk_latency_ms > 100 OR data_disk_latency_ms > 100
```

**Diagnosis:** "Disk IO saturation"

**Evidence:**
- `os_disk_latency_ms=<value>`
- `data_disk_latency_ms=<value>`

**Next Check:** "Optimize disk IO or upgrade to premium storage"

**Telemetry Example:**

```json
{
  "power_state": "Running",
  "provisioning_state": "Succeeded",
  "resource_health_status": "Degraded",
  "os_disk_latency_ms": 150.0,
  "data_disk_latency_ms": 200.0,
  "cpu_percent": 45.0
}
```

**Expected Output:**

```json
{
  "decision": "diagnose",
  "diagnosis": "Disk IO saturation",
  "confidence_score": 0.80,
  "evidence": [
    "power_state=Running",
    "os_disk_latency_ms=150.0",
    "data_disk_latency_ms=200.0"
  ],
  "next_check": "Optimize disk IO or upgrade to premium storage"
}
```

---

### Category 4: Boot Failures

---

#### Pattern 7: Boot BSOD

**Pattern ID:** `boot_bsod`

**Matching Conditions:**
```
boot_diagnostics_status = "BSOD"
```

**Diagnosis:** "Boot BSOD"

**Evidence:**
- `boot_diagnostics_status=BSOD`

**Next Check:** "Review boot diagnostics logs and serial console output (do not restart VM)"

**Safety Rule:** Safety Rule 2 (Boot Failure Safety) applies - never suggest restart

**Telemetry Example:**

```json
{
  "power_state": "Running",
  "provisioning_state": "Succeeded",
  "resource_health_status": "Degraded",
  "boot_diagnostics_status": "BSOD",
  "boot_diagnostics_error": "CRITICAL_PROCESS_DIED"
}
```

**Expected Output:**

```json
{
  "decision": "diagnose",
  "diagnosis": "Boot BSOD",
  "confidence_score": 0.90,
  "evidence": [
    "power_state=Running",
    "boot_diagnostics_status=BSOD"
  ],
  "next_check": "Review boot diagnostics logs and serial console output (do not restart VM)",
  "explanation": "Boot failure detected: BSOD. Do not restart VM - investigate boot diagnostics first."
}
```

---

#### Pattern 8: Boot Kernel Panic

**Pattern ID:** `boot_kernel_panic`

**Matching Conditions:**
```
boot_diagnostics_status = "KernelPanic"
```

**Diagnosis:** "Boot kernel panic"

**Evidence:**
- `boot_diagnostics_status=KernelPanic`

**Next Check:** "Review boot diagnostics logs and kernel panic details (do not restart VM)"

**Safety Rule:** Safety Rule 2 (Boot Failure Safety) applies - never suggest restart

**Telemetry Example:**

```json
{
  "power_state": "Running",
  "provisioning_state": "Succeeded",
  "resource_health_status": "Degraded",
  "boot_diagnostics_status": "KernelPanic",
  "boot_diagnostics_error": "Kernel panic - not syncing"
}
```

**Expected Output:**

```json
{
  "decision": "diagnose",
  "diagnosis": "Boot kernel panic",
  "confidence_score": 0.90,
  "evidence": [
    "power_state=Running",
    "boot_diagnostics_status=KernelPanic"
  ],
  "next_check": "Review boot diagnostics logs and kernel panic details (do not restart VM)"
}
```

---

#### Pattern 18: Boot Stuck

**Pattern ID:** `boot_stuck`

**Matching Conditions:**
```
boot_diagnostics_status = "Stuck"
```

**Diagnosis:** "Boot stuck at startup"

**Evidence:**
- `boot_diagnostics_status=Stuck`

**Next Check:** "Review boot diagnostics logs and serial console output"

**Telemetry Example:**

```json
{
  "power_state": "Running",
  "provisioning_state": "Succeeded",
  "resource_health_status": "Degraded",
  "boot_diagnostics_status": "Stuck"
}
```

**Expected Output:**

```json
{
  "decision": "diagnose",
  "diagnosis": "Boot stuck at startup",
  "confidence_score": 0.85,
  "evidence": [
    "power_state=Running",
    "boot_diagnostics_status=Stuck"
  ],
  "next_check": "Review boot diagnostics logs and serial console output"
}
```

---

### Category 5: Agent Failures

---

#### Pattern 9: VM Running No Heartbeat

**Pattern ID:** `vm_running_no_heartbeat`

**Matching Conditions:**
```
power_state = "Running"
heartbeat_present = false
```

**Diagnosis:** "VM running but no heartbeat"

**Evidence:**
- `power_state=Running`
- `heartbeat_present=False`

**Next Check:** "Check VM agent status and network connectivity"

**Telemetry Example:**

```json
{
  "power_state": "Running",
  "provisioning_state": "Succeeded",
  "resource_health_status": "Degraded",
  "heartbeat_present": false,
  "cpu_percent": 45.0,
  "memory_percent": 50.0
}
```

**Expected Output:**

```json
{
  "decision": "diagnose",
  "diagnosis": "VM running but no heartbeat",
  "confidence_score": 0.80,
  "evidence": [
    "power_state=Running",
    "heartbeat_present=False"
  ],
  "next_check": "Check VM agent status and network connectivity"
}
```

---

#### Pattern 19: VM Agent Failed

**Pattern ID:** `vm_agent_failed`

**Matching Conditions:**
```
azure_vm_agent_status = "Failed"
```

**Diagnosis:** "Azure VM agent failure"

**Evidence:**
- `azure_vm_agent_status=Failed`

**Next Check:** "Restart VM agent or reinstall VM extensions"

**Telemetry Example:**

```json
{
  "power_state": "Running",
  "provisioning_state": "Succeeded",
  "resource_health_status": "Degraded",
  "azure_vm_agent_status": "Failed",
  "heartbeat_present": false
}
```

**Expected Output:**

```json
{
  "decision": "diagnose",
  "diagnosis": "Azure VM agent failure",
  "confidence_score": 0.85,
  "evidence": [
    "power_state=Running",
    "azure_vm_agent_status=Failed"
  ],
  "next_check": "Restart VM agent or reinstall VM extensions"
}
```

---

#### Pattern 20: Monitor Agent Failed

**Pattern ID:** `monitor_agent_failed`

**Matching Conditions:**
```
monitor_agent_status = "Failed"
```

**Diagnosis:** "Monitoring agent failure"

**Evidence:**
- `monitor_agent_status=Failed`

**Next Check:** "Restart monitoring agent or reinstall monitoring extensions"

**Telemetry Example:**

```json
{
  "power_state": "Running",
  "provisioning_state": "Succeeded",
  "resource_health_status": "Available",
  "monitor_agent_status": "Failed"
}
```

**Expected Output:**

```json
{
  "decision": "diagnose",
  "diagnosis": "Monitoring agent failure",
  "confidence_score": 0.80,
  "evidence": [
    "power_state=Running",
    "monitor_agent_status=Failed"
  ],
  "next_check": "Restart monitoring agent or reinstall monitoring extensions"
}
```

---

### Category 6: Resource Health

---

#### Pattern 10: Resource Health Unavailable

**Pattern ID:** `resource_health_unavailable`

**Matching Conditions:**
```
resource_health_status = "Unavailable"
cpu_percent < 90
memory_percent < 90
```

**Diagnosis:** "Resource health unavailable with normal metrics"

**Evidence:**
- `resource_health_status=Unavailable`
- `cpu_percent=<value>`
- `memory_percent=<value>`

**Next Check:** "Check Azure service health and VM agent status"

**Telemetry Example:**

```json
{
  "power_state": "Running",
  "provisioning_state": "Succeeded",
  "resource_health_status": "Unavailable",
  "cpu_percent": 45.0,
  "memory_percent": 50.0,
  "heartbeat_present": true
}
```

**Expected Output:**

```json
{
  "decision": "diagnose_low_confidence",
  "diagnosis": "Resource health unavailable with normal metrics",
  "confidence_score": 0.60,
  "evidence": [
    "power_state=Running",
    "resource_health_status=Unavailable",
    "cpu_percent=45.0",
    "memory_percent=50.0"
  ],
  "next_check": "Check Azure service health and VM agent status"
}
```

---

#### Pattern 17: Platform Degradation

**Pattern ID:** `platform_degradation`

**Matching Conditions:**
```
resource_health_annotation contains platform degradation keywords:
  - "platform"
  - "maintenance"
  - "host update"
  - "planned maintenance"
  - "degradation"
```

**Diagnosis:** "Platform degradation event"

**Evidence:**
- `resource_health_annotation=<value>`

**Next Check:** "Wait for platform maintenance to complete"

**Safety Rule:** Safety Rule 1 (Platform Event Safety) applies - abstain and never suggest restart

**Telemetry Example:**

```json
{
  "power_state": "Running",
  "provisioning_state": "Succeeded",
  "resource_health_status": "Degraded",
  "resource_health_annotation": "Platform maintenance in progress - host update scheduled"
}
```

**Expected Output:**

```json
{
  "decision": "abstain_request_next_check",
  "diagnosis": "Platform-initiated event detected",
  "confidence_score": 0.65,
  "evidence": [
    "power_state=Running",
    "resource_health_status=Degraded",
    "resource_health_annotation=Platform maintenance in progress"
  ],
  "next_check": "Wait for platform maintenance to complete, then re-assess VM state",
  "explanation": "Platform maintenance detected. Do not restart VM during platform events."
}
```

---

### Category 7: Application Health

---

#### Pattern 12: App Unhealthy VM Healthy

**Pattern ID:** `app_unhealthy_vm_healthy`

**Matching Conditions:**
```
app_health_status = "Unhealthy"
azure_vm_agent_status = "Healthy"
```

**Diagnosis:** "Application unhealthy with healthy VM"

**Evidence:**
- `app_health_status=Unhealthy`
- `azure_vm_agent_status=Healthy`

**Next Check:** "Review application logs and configuration (VM infrastructure is healthy)"

**Telemetry Example:**

```json
{
  "power_state": "Running",
  "provisioning_state": "Succeeded",
  "resource_health_status": "Available",
  "app_health_status": "Unhealthy",
  "azure_vm_agent_status": "Healthy",
  "cpu_percent": 45.0,
  "memory_percent": 50.0
}
```

**Expected Output:**

```json
{
  "decision": "diagnose",
  "diagnosis": "Application unhealthy with healthy VM",
  "confidence_score": 0.85,
  "evidence": [
    "power_state=Running",
    "app_health_status=Unhealthy",
    "azure_vm_agent_status=Healthy"
  ],
  "next_check": "Review application logs and configuration (VM infrastructure is healthy)"
}
```

---

### Category 8: Special Cases

---

#### Pattern 16: Failed State Insufficient Data

**Pattern ID:** `failed_state_insufficient_data`

**Matching Conditions:**
```
power_state = "Failed"
data_completeness_percent < 30
```

**Diagnosis:** "Failed state with insufficient data"

**Evidence:**
- `power_state=Failed`
- `data_completeness_percent=<value>`

**Next Check:** "Gather more telemetry data to diagnose failure cause"

**Safety Rule:** Safety Rule 6 (Failed State Safety) may apply if provisioning_state is also Failed

**Telemetry Example:**

```json
{
  "power_state": "Failed",
  "provisioning_state": "Unknown",
  "resource_health_status": "Unavailable",
  "data_completeness_percent": 25.0
}
```

**Expected Output:**

```json
{
  "decision": "abstain_request_next_check",
  "diagnosis": "Failed state with insufficient data",
  "confidence_score": 0.20,
  "evidence": [
    "power_state=Failed",
    "data_completeness_percent=25.0"
  ],
  "evidence_gap": [
    "heartbeat_present",
    "boot_diagnostics_status",
    "cpu_percent",
    "memory_percent",
    "azure_vm_agent_status"
  ],
  "next_check": "Gather more telemetry data to diagnose failure cause"
}
```

---

## Pattern Matching Logic

### Evaluation Order

Patterns are evaluated in the order they appear in the decision engine code. The first pattern that matches all conditions is selected.

**Priority Order:**
1. VM Stopped by User
2. NSG Blocks RDP
3. NSG Blocks SSH
4. High CPU Saturation
5. OS Disk Full
6. Memory Exhaustion
7. Boot BSOD
8. Boot Kernel Panic
9. VM Running No Heartbeat
10. Resource Health Unavailable
11. Conflicting NSG Signals
12. App Unhealthy VM Healthy
13. Disk IO Saturation
14. VM Deallocated
15. Provisioning Failed
16. Failed State Insufficient Data
17. Platform Degradation
18. Boot Stuck
19. VM Agent Failed
20. Monitor Agent Failed

### Pattern Match Types

**Exact Match:**
- All conditions for the pattern are met
- Contributes 0.3 to confidence score (30% weight)

**Partial Match:**
- Some conditions are met, but not all
- Contributes 0.15 to confidence score (15% weight)

**No Match:**
- No pattern conditions are met
- Contributes 0.0 to confidence score

### Pattern Selection

When multiple patterns could match, the first matching pattern in the evaluation order is selected. This ensures deterministic behavior.

**Example:**

```json
{
  "power_state": "Running",
  "provisioning_state": "Succeeded",
  "resource_health_status": "Degraded",
  "cpu_percent": 98.0,
  "memory_percent": 97.0
}
```

In this case:
- Pattern 4 (High CPU) matches first → selected
- Pattern 6 (Memory Exhaustion) also matches but is not selected
- Only one pattern is returned per diagnosis

## Pattern Coverage

The 20 patterns cover the following incident types:

| Category | Pattern Count | Coverage |
|----------|---------------|----------|
| Power and Provisioning | 3 | VM state issues, deallocation, provisioning failures |
| Network Connectivity | 3 | NSG blocks, connection issues, signal conflicts |
| Performance | 4 | CPU, memory, disk saturation, IO latency |
| Boot Failures | 3 | BSOD, kernel panic, stuck boot |
| Agent Failures | 3 | VM agent, monitoring agent, heartbeat issues |
| Resource Health | 2 | Platform degradation, health unavailable |
| Application Health | 1 | Application-level issues |
| Special Cases | 1 | Failed state with insufficient data |

## Pattern Testing

Each pattern is validated by:

1. **Unit Tests:** Specific telemetry examples for each pattern
2. **Benchmark Tests:** Real-world cases covering all 20 patterns
3. **Property Tests:** Universal properties that hold across all patterns

**Benchmark Coverage:**
- 20 benchmark cases (one per pattern)
- 5 clean cases (no pattern matched)
- 5 missing-telemetry cases (low completeness)
- 5 conflicting-signal cases (signal conflicts)

## Related Documentation

- [Decision Policy Documentation](decision_policy.md) - Decision rules A, B, C
- [Safety Rules Documentation](safety_rules.md) - 6 safety rules
- [Architecture Documentation](architecture.md) - System architecture and component design
