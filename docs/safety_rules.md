# Safety Rules Documentation

## Overview

The Azure VM Incident Copilot enforces six safety rules to prevent unsafe remediation suggestions in all scenarios. Safety rules are the highest priority in the decision evaluation order and can override pattern matches and decision logic. This document describes each safety rule, its conditions, actions, priority order, and provides examples of violations and correct behavior.

## Safety Rule Priority

Safety rules are evaluated **first** in the decision pipeline, before any other logic:

```
1. Safety Rules (highest priority)
2. Critical Signal Checks
3. Data Completeness Checks
4. Pattern Matching
5. Decision Selection
```

**Key Principles:**
- Safety rules can trigger `abstain_request_next_check` regardless of confidence score
- Safety rules can modify or remove unsafe suggestions from `next_check`
- Safety rules add safety context to the explanation field
- Safety rules are deterministic and always enforced

## Safety Rules

### Safety Rule 1: Platform Event Safety

**Purpose:** Prevent VM restart suggestions during platform-initiated maintenance events.

**Condition:**
```
IF resource_health_annotation contains platform event keywords:
   - "platform"
   - "maintenance"
   - "host update"
   - "planned maintenance"
   - "degradation"
```

**Action:**
- Decision state: `abstain_request_next_check`
- Never suggest VM restart in `next_check`
- Add safety context to explanation

**Rationale:**
Platform-initiated events (maintenance, host updates, planned degradation) should not be interrupted by user actions. Restarting a VM during platform maintenance can cause extended downtime or data loss.

**Example Violation:**

```json
{
  "telemetry": {
    "power_state": "Running",
    "provisioning_state": "Succeeded",
    "resource_health_status": "Degraded",
    "resource_health_annotation": "Platform maintenance in progress - host update scheduled"
  },
  "decision": "abstain_request_next_check",
  "diagnosis": "Platform-initiated event detected",
  "next_check": "Wait for platform maintenance to complete, then re-assess VM state",
  "explanation": "Platform maintenance detected. Do not restart VM during platform events."
}
```

**Correct Behavior:**

```json
{
  "telemetry": {
    "power_state": "Running",
    "provisioning_state": "Succeeded",
    "resource_health_status": "Available",
    "resource_health_annotation": null
  },
  "decision": "diagnose",
  "diagnosis": "VM is healthy",
  "next_check": null,
  "explanation": "VM is running normally with no issues detected."
}
```

---

### Safety Rule 2: Boot Failure Safety

**Purpose:** Prevent VM restart suggestions when boot diagnostics indicate OS-level failures.

**Condition:**
```
IF boot_diagnostics_status = "BSOD" OR boot_diagnostics_status = "KernelPanic"
```

**Action:**
- Decision state: `diagnose` (not abstain, because we have a clear diagnosis)
- Never suggest "restart" in `next_check`
- Suggest reviewing boot diagnostics logs instead
- Add safety context to explanation

**Rationale:**
BSOD (Blue Screen of Death) and kernel panics indicate OS-level failures that require investigation, not restart. Restarting the VM will likely result in the same failure and may destroy diagnostic evidence.

**Example Violation:**

```json
{
  "telemetry": {
    "power_state": "Running",
    "provisioning_state": "Succeeded",
    "resource_health_status": "Degraded",
    "boot_diagnostics_status": "BSOD",
    "boot_diagnostics_error": "CRITICAL_PROCESS_DIED"
  },
  "decision": "diagnose",
  "diagnosis": "Boot BSOD",
  "next_check": "Review boot diagnostics logs and serial console output (do not restart VM)",
  "explanation": "Boot failure detected: BSOD. Do not restart VM - investigate boot diagnostics first."
}
```

**Correct Behavior:**

```json
{
  "telemetry": {
    "power_state": "Running",
    "provisioning_state": "Succeeded",
    "resource_health_status": "Available",
    "boot_diagnostics_status": "Normal"
  },
  "decision": "diagnose",
  "diagnosis": "VM is healthy",
  "next_check": null,
  "explanation": "VM is running normally with no boot issues detected."
}
```

---

### Safety Rule 3: Low Confidence Destructive Action Safety

**Purpose:** Prevent destructive actions when confidence is below 0.9 (90%).

**Condition:**
```
IF confidence_score < 0.9 AND next_check contains destructive keywords:
   - "delete"
   - "reset"
   - "remove"
   - "destroy"
   - "wipe"
```

**Action:**
- Remove destructive actions from `next_check`
- Replace with: "Gather more data before considering destructive actions (confidence too low)"
- Add safety context to explanation

**Rationale:**
Destructive actions (disk deletion, OS reset, VM deletion, configuration reset) are irreversible and can cause data loss. These actions should only be suggested when confidence is very high (≥ 0.9).

**Example Violation:**

```json
{
  "telemetry": {
    "power_state": "Failed",
    "provisioning_state": "Failed",
    "resource_health_status": "Unavailable"
  },
  "confidence_score": 0.65,
  "decision": "diagnose_low_confidence",
  "diagnosis": "VM in failed state",
  "next_check": "Gather more data before considering destructive actions (confidence too low)",
  "explanation": "Confidence too low (0.65) for destructive actions. Gather more telemetry first."
}
```

**Correct Behavior (High Confidence):**

```json
{
  "telemetry": {
    "power_state": "Failed",
    "provisioning_state": "Failed",
    "resource_health_status": "Unavailable",
    "boot_diagnostics_status": "BSOD",
    "boot_diagnostics_error": "CRITICAL_PROCESS_DIED",
    "cpu_percent": 0.0,
    "memory_percent": 0.0
  },
  "confidence_score": 0.95,
  "decision": "diagnose",
  "diagnosis": "VM in failed state with boot failure",
  "next_check": "Review boot diagnostics and consider OS disk replacement if necessary",
  "explanation": "High confidence (0.95) diagnosis: VM failed due to boot BSOD."
}
```

---

### Safety Rule 4: Network Security Safety

**Purpose:** Never suggest disabling NSG (Network Security Group) or firewall rules.

**Condition:**
```
IF next_check contains network security keywords:
   - "disable nsg"
   - "disable firewall"
   - "remove nsg rule"
   - "remove firewall rule"
```

**Action:**
- Replace with: "Review network security configuration manually (do not disable NSG or firewall rules)"
- Add safety context to explanation

**Rationale:**
Disabling NSG or firewall rules can expose VMs to security threats. Network security changes require manual review and approval, never automated suggestions.

**Example Violation:**

```json
{
  "telemetry": {
    "power_state": "Running",
    "provisioning_state": "Succeeded",
    "resource_health_status": "Available",
    "nsg_allow_rdp_3389": false,
    "connection_troubleshoot_rdp": "Deny"
  },
  "decision": "diagnose",
  "diagnosis": "NSG blocks RDP",
  "next_check": "Review network security configuration manually (do not disable NSG or firewall rules)",
  "explanation": "NSG blocks RDP on port 3389. Review NSG rules manually - do not disable security."
}
```

**Correct Behavior:**

```json
{
  "telemetry": {
    "power_state": "Running",
    "provisioning_state": "Succeeded",
    "resource_health_status": "Available",
    "nsg_allow_rdp_3389": false,
    "connection_troubleshoot_rdp": "Deny"
  },
  "decision": "diagnose",
  "diagnosis": "NSG blocks RDP",
  "next_check": "Review NSG rules for port 3389 and update if RDP access is required",
  "explanation": "NSG blocks RDP on port 3389. Review and update NSG rules if access is needed."
}
```

---

### Safety Rule 5: Disk Safety

**Purpose:** Prevent disk deletion or OS reset when confidence is below 0.9 (90%).

**Condition:**
```
IF confidence_score < 0.9 AND next_check contains disk keywords:
   - "delete disk"
   - "reset os"
```

**Action:**
- Replace with: "Review disk and OS state manually (confidence too low for disk operations)"
- Add safety context to explanation

**Rationale:**
Disk operations (deletion, OS reset) can cause permanent data loss. These operations should only be suggested when confidence is very high (≥ 0.9) and data integrity is preserved.

**Example Violation:**

```json
{
  "telemetry": {
    "power_state": "Running",
    "provisioning_state": "Succeeded",
    "resource_health_status": "Degraded",
    "os_disk_percent_full": 98.0
  },
  "confidence_score": 0.75,
  "decision": "diagnose",
  "diagnosis": "OS disk full",
  "next_check": "Review disk and OS state manually (confidence too low for disk operations)",
  "explanation": "Confidence too low (0.75) for disk operations. Review disk state manually."
}
```

**Correct Behavior (High Confidence):**

```json
{
  "telemetry": {
    "power_state": "Running",
    "provisioning_state": "Succeeded",
    "resource_health_status": "Degraded",
    "os_disk_percent_full": 98.0,
    "cpu_percent": 45.0,
    "memory_percent": 50.0,
    "heartbeat_present": true,
    "boot_diagnostics_status": "Normal"
  },
  "confidence_score": 0.92,
  "decision": "diagnose",
  "diagnosis": "OS disk full",
  "next_check": "Free up disk space or expand OS disk capacity",
  "explanation": "High confidence (0.92) diagnosis: OS disk is 98% full."
}
```

---

### Safety Rule 6: Failed State Safety

**Purpose:** Never suggest auto-remediation for VMs in failed state.

**Condition:**
```
IF power_state = "Failed" AND provisioning_state = "Failed" AND next_check contains:
   - "auto-remediation"
   - "automatic remediation"
```

**Action:**
- Replace with: "Contact Azure support for failed VM state (do not attempt auto-remediation)"
- Add safety context to explanation

**Rationale:**
VMs in failed state (both power_state and provisioning_state are "Failed") require manual investigation and Azure support. Auto-remediation can worsen the situation or destroy diagnostic evidence.

**Example Violation:**

```json
{
  "telemetry": {
    "power_state": "Failed",
    "provisioning_state": "Failed",
    "resource_health_status": "Unavailable"
  },
  "decision": "diagnose",
  "diagnosis": "VM in failed state",
  "next_check": "Contact Azure support for failed VM state (do not attempt auto-remediation)",
  "explanation": "VM in failed state. Contact Azure support - do not attempt auto-remediation."
}
```

**Correct Behavior:**

```json
{
  "telemetry": {
    "power_state": "Stopped",
    "provisioning_state": "Succeeded",
    "resource_health_status": "Available"
  },
  "decision": "diagnose",
  "diagnosis": "VM Stopped by user deallocation",
  "next_check": "Start VM if needed, or confirm intentional stop",
  "explanation": "VM is stopped with successful provisioning. User-initiated deallocation."
}
```

## Safety Rule Enforcement

### Implementation

Safety rules are implemented in `src/decision_engine.py`:

```python
def _check_safety_rules(self, telemetry: TelemetryInput, confidence_score: float) -> Optional[Decision]:
    """
    Check all 6 safety rules.
    
    Returns Decision with abstain if any safety rule is violated, None otherwise.
    """
    # Safety Rule 1: Platform Event Safety
    if self._check_platform_event_safety(telemetry):
        return Decision(
            state=DecisionState.ABSTAIN_REQUEST_NEXT_CHECK,
            diagnosis="Platform-initiated event detected",
            evidence=self._get_evidence(telemetry),
            evidence_gap=self._get_evidence_gap(telemetry),
            next_check="Wait for platform maintenance to complete, then re-assess VM state",
            confidence_score=confidence_score
        )
    
    # Safety Rule 2: Boot Failure Safety
    if self._check_boot_failure_safety(telemetry):
        boot_status = str(telemetry.boot_diagnostics_status)
        return Decision(
            state=DecisionState.DIAGNOSE,
            diagnosis=f"Boot failure detected: {boot_status}",
            evidence=self._get_evidence(telemetry),
            evidence_gap=self._get_evidence_gap(telemetry),
            next_check="Review boot diagnostics logs and serial console output (do not restart VM)",
            confidence_score=confidence_score
        )
    
    # Safety Rules 3-6 are enforced in next_check generation
    return None
```

### Sanitization

Safety rules 3-6 are enforced by sanitizing the `next_check` field:

```python
def _sanitize_next_check(self, next_check: str, telemetry: TelemetryInput, confidence_score: float) -> str:
    """
    Apply safety rules 3-6 to sanitize next_check suggestions.
    """
    if not next_check:
        return next_check
    
    next_check_lower = next_check.lower()
    
    # Safety Rule 4: Network Security Safety (always enforced)
    if "disable nsg" in next_check_lower or "disable firewall" in next_check_lower:
        return "Review network security configuration manually (do not disable NSG or firewall rules)"
    
    # Safety Rule 3: Low Confidence Destructive Action Safety
    if confidence_score < 0.9:
        destructive_keywords = ["delete disk", "reset os", "delete vm", "reset configuration"]
        if any(keyword in next_check_lower for keyword in destructive_keywords):
            return "Gather more data before considering destructive actions (confidence too low)"
    
    # Safety Rule 5: Disk Safety
    if confidence_score < 0.9:
        if "delete disk" in next_check_lower or "reset os" in next_check_lower:
            return "Review disk and OS state manually (confidence too low for disk operations)"
    
    # Safety Rule 6: Failed State Safety
    if (telemetry.power_state == PowerState.FAILED and
        telemetry.provisioning_state == ProvisioningState.FAILED):
        if "auto" in next_check_lower or "remediate" in next_check_lower:
            return "Contact Azure support for failed VM state (do not attempt auto-remediation)"
    
    return next_check
```

## Safety Rule Testing

Each safety rule is validated by property-based tests:

- **Property 11**: Boot Failure Safety (BSOD/KernelPanic never suggests restart)
- **Property 12**: Low Confidence Destructive Action Safety (confidence < 0.9 prevents destructive actions)
- **Property 13**: Network Security Safety (never suggests disabling NSG/firewall)
- **Property 14**: Platform Event Triggers Abstain (platform events trigger abstain and no restart)
- **Property 15**: Failed State Safety (failed states never suggest auto-remediation)

## Safety Rule Priority Order

When multiple safety rules apply, they are evaluated in this order:

1. **Platform Event Safety** (highest priority)
2. **Boot Failure Safety**
3. **Low Confidence Destructive Action Safety**
4. **Network Security Safety**
5. **Disk Safety**
6. **Failed State Safety**

**Example: Multiple Rules Apply**

```json
{
  "telemetry": {
    "power_state": "Failed",
    "provisioning_state": "Failed",
    "resource_health_status": "Unavailable",
    "resource_health_annotation": "Platform maintenance in progress",
    "boot_diagnostics_status": "BSOD"
  },
  "confidence_score": 0.45,
  "decision": "abstain_request_next_check",
  "diagnosis": "Platform-initiated event detected",
  "next_check": "Wait for platform maintenance to complete, then re-assess VM state",
  "explanation": "Platform maintenance detected (highest priority). Multiple safety concerns: platform event, boot failure, failed state."
}
```

In this example:
- Safety Rule 1 (Platform Event) triggers first → abstain
- Safety Rule 2 (Boot Failure) would also apply, but Rule 1 takes precedence
- Safety Rule 6 (Failed State) would also apply, but Rule 1 takes precedence

## Summary Table

| Rule | Condition | Action | Priority |
|------|-----------|--------|----------|
| 1. Platform Event Safety | resource_health_annotation contains platform keywords | abstain_request_next_check, no restart | Highest |
| 2. Boot Failure Safety | boot_diagnostics_status = BSOD or KernelPanic | diagnose, no restart | High |
| 3. Low Confidence Destructive Action Safety | confidence < 0.9 AND destructive keywords | Remove destructive actions | Medium |
| 4. Network Security Safety | next_check suggests disabling NSG/firewall | Replace with manual review | Medium |
| 5. Disk Safety | confidence < 0.9 AND disk keywords | Replace with manual review | Medium |
| 6. Failed State Safety | power_state=Failed AND provisioning_state=Failed | No auto-remediation | Low |

## Related Documentation

- [Decision Policy Documentation](decision_policy.md) - Decision rules A, B, C
- [Incident Patterns Documentation](incident_patterns.md) - 20 known patterns
- [Architecture Documentation](architecture.md) - System architecture and component design
