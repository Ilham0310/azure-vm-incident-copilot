# Decision Policy Documentation

## Overview

The Azure VM Incident Copilot uses a deterministic decision policy to classify diagnostic confidence into exactly one of three states. The policy evaluates telemetry completeness, confidence scores, signal conflicts, and pattern matches to determine the appropriate decision state. This document describes the decision rules, evaluation order, confidence scoring algorithm, and provides examples for each rule.

## Decision States

The system returns exactly one of three decision states:

1. **diagnose**: High confidence diagnosis with sufficient evidence
2. **diagnose_low_confidence**: Probable diagnosis with partial evidence
3. **abstain_request_next_check**: Insufficient data or safety concerns prevent diagnosis

## Decision Rules

### Rule A: diagnose

**Conditions:**
- Confidence score ≥ 0.70
- Data completeness ≥ 90%
- No conflicting signals (or conflicts fully explained)
- Root cause maps to one known incident pattern
- No safety rule violations

**Outcome:**
- Decision state: `diagnose`
- Confidence score: 0.70 - 1.0
- Diagnosis: Specific incident pattern description
- Next check: Specific remediation or verification action (if applicable)

**Example:**

```json
{
  "telemetry": {
    "power_state": "Running",
    "provisioning_state": "Succeeded",
    "resource_health_status": "Degraded",
    "cpu_percent": 98.0,
    "memory_percent": 45.0,
    "heartbeat_present": true,
    "boot_diagnostics_status": "Normal",
    "azure_vm_agent_status": "Healthy"
  },
  "completeness": 95.0,
  "confidence_score": 0.85,
  "decision": "diagnose",
  "diagnosis": "High CPU saturation",
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

### Rule B: diagnose_low_confidence

**Conditions:**
- Confidence score ≥ 0.40 and < 0.70
- Data completeness 60-89%
- Minor signal conflicts that can be partially explained
- Root cause is probable but not certain
- No safety rule violations

**Outcome:**
- Decision state: `diagnose_low_confidence`
- Confidence score: 0.40 - 0.69
- Diagnosis: Probable incident pattern description
- Next check: Gather additional telemetry for higher confidence

**Example:**

```json
{
  "telemetry": {
    "power_state": "Running",
    "provisioning_state": "Succeeded",
    "resource_health_status": "Degraded",
    "cpu_percent": 92.0,
    "heartbeat_present": null,
    "boot_diagnostics_status": null,
    "azure_vm_agent_status": null
  },
  "completeness": 65.0,
  "confidence_score": 0.55,
  "decision": "diagnose_low_confidence",
  "diagnosis": "Probable high CPU saturation",
  "evidence": [
    "power_state=Running",
    "provisioning_state=Succeeded",
    "resource_health_status=Degraded",
    "cpu_percent=92.0"
  ],
  "evidence_gap": [
    "heartbeat_present",
    "boot_diagnostics_status",
    "azure_vm_agent_status",
    "memory_percent",
    "os_disk_percent_full"
  ],
  "next_check": "Gather more telemetry for higher confidence diagnosis"
}
```

---

### Rule C: abstain_request_next_check

**Conditions (any one triggers abstain):**
- Confidence score < 0.40, OR
- Data completeness < 60%, OR
- Critical signals missing or unknown (power_state, provisioning_state, resource_health_status), OR
- Severe unresolvable signal conflict, OR
- Platform-initiated event detected (resource_health_annotation contains keywords), OR
- Any safety rule violation detected

**Outcome:**
- Decision state: `abstain_request_next_check`
- Confidence score: 0.0 - 0.39 (or any score if safety rule violated)
- Diagnosis: Reason for abstaining
- Next check: Specific diagnostic action to gather more data (required field)

**Example 1: Low Completeness**

```json
{
  "telemetry": {
    "power_state": "Running",
    "provisioning_state": "Succeeded",
    "resource_health_status": "Available"
  },
  "completeness": 45.0,
  "confidence_score": 0.25,
  "decision": "abstain_request_next_check",
  "diagnosis": "Insufficient telemetry data",
  "evidence": [
    "power_state=Running",
    "provisioning_state=Succeeded",
    "resource_health_status=Available"
  ],
  "evidence_gap": [
    "heartbeat_present",
    "boot_diagnostics_status",
    "cpu_percent",
    "memory_percent",
    "azure_vm_agent_status",
    "os_disk_percent_full"
  ],
  "next_check": "Gather more telemetry data to reach at least 60% completeness"
}
```

**Example 2: Platform Event**

```json
{
  "telemetry": {
    "power_state": "Running",
    "provisioning_state": "Succeeded",
    "resource_health_status": "Degraded",
    "resource_health_annotation": "Platform maintenance in progress - host update scheduled"
  },
  "completeness": 85.0,
  "confidence_score": 0.65,
  "decision": "abstain_request_next_check",
  "diagnosis": "Platform-initiated event detected",
  "evidence": [
    "power_state=Running",
    "provisioning_state=Succeeded",
    "resource_health_status=Degraded",
    "resource_health_annotation=Platform maintenance in progress"
  ],
  "next_check": "Wait for platform maintenance to complete, then re-assess VM state"
}
```

**Example 3: Missing Critical Signals**

```json
{
  "telemetry": {
    "power_state": "Unknown",
    "provisioning_state": "Unknown",
    "resource_health_status": "Unknown"
  },
  "completeness": 10.0,
  "confidence_score": 0.05,
  "decision": "abstain_request_next_check",
  "diagnosis": "Critical signals missing or unknown",
  "evidence": [],
  "evidence_gap": [
    "power_state",
    "provisioning_state",
    "resource_health_status"
  ],
  "next_check": "Gather critical telemetry: power_state, provisioning_state, resource_health_status"
}
```

## Evaluation Order

The decision engine evaluates conditions in the following order (highest priority first):

```
1. Safety Rule Checks (6 rules)
   ├─ Platform Event Safety
   ├─ Boot Failure Safety
   ├─ Low Confidence Destructive Action Safety
   ├─ Network Security Safety
   ├─ Disk Safety
   └─ Failed State Safety
   
2. Critical Signal Checks
   └─ power_state, provisioning_state, resource_health_status must not be Unknown
   
3. Data Completeness Checks
   └─ Completeness must be ≥ 60% to proceed
   
4. Pattern Matching (20 patterns)
   └─ Match telemetry against known incident patterns
   
5. Decision Selection (Rules A, B, C)
   ├─ Rule A: confidence ≥ 0.70 AND completeness ≥ 90%
   ├─ Rule B: confidence ≥ 0.40 AND completeness ≥ 60%
   └─ Rule C: confidence < 0.40 OR completeness < 60%
```

**Priority Rules:**
- Safety rules override all other decisions
- Critical signal checks prevent diagnosis if signals are Unknown
- Completeness checks prevent diagnosis if data is insufficient
- Pattern matching provides diagnosis text and evidence
- Decision rules determine final state based on confidence and completeness

## Confidence Scoring Algorithm

The confidence score is calculated using three weighted components:

### Formula

```
confidence_score = (completeness_weight * 0.4) + 
                   (pattern_weight * 0.3) + 
                   (consistency_weight * 0.3)
```

### Component 1: Data Completeness Weight (40%)

**Calculation:**
```
completeness_weight = (completeness_percent / 100.0) * 0.4
```

**Examples:**
- 100% completeness → 0.40 contribution
- 90% completeness → 0.36 contribution
- 60% completeness → 0.24 contribution
- 0% completeness → 0.00 contribution

**Completeness Calculation:**
- Count non-null optional fields (27+ fields)
- Required fields are not counted (always present)
- Formula: `(non_null_optional_fields / total_optional_fields) * 100`

### Component 2: Pattern Match Weight (30%)

**Calculation:**
```
pattern_weight = 0.3  (exact match)
pattern_weight = 0.15 (partial match)
pattern_weight = 0.0  (no match)
```

**Match Types:**
- **Exact match**: All conditions for a known pattern are met
- **Partial match**: Some conditions met, but not all
- **No match**: No known pattern matches the telemetry

**Examples:**
- High CPU (cpu_percent > 95) → Exact match → 0.3 contribution
- High CPU (cpu_percent = 92) → Partial match → 0.15 contribution
- No pattern matched → 0.0 contribution

### Component 3: Signal Consistency Weight (30%)

**Calculation:**
```
consistency_weight = 0.3  (no conflicts)
consistency_weight = 0.15 (minor conflicts)
consistency_weight = 0.0  (major conflicts)
```

**Conflict Types:**

**No Conflicts:**
- All signals are consistent and explainable
- Example: power_state=Running, cpu_percent=98, resource_health_status=Degraded

**Minor Conflicts (explainable):**
- power_state=Running + heartbeat_present=false (VM running but agent not reporting)
- nsg_allow_rdp_3389=false + connection_troubleshoot_rdp=Allow (NSG vs troubleshoot mismatch)

**Major Conflicts (unresolvable):**
- power_state=Running + resource_health_status=Unavailable + all metrics normal
- power_state=Stopped + cpu_percent=95 (stopped VM with high CPU)

### Complete Examples

**Example 1: High Confidence (0.85)**

```
Telemetry:
- Completeness: 95% (all optional fields populated)
- Pattern: High CPU (exact match)
- Conflicts: None

Calculation:
- Completeness weight: (95 / 100) * 0.4 = 0.38
- Pattern weight: 0.3 (exact match)
- Consistency weight: 0.3 (no conflicts)
- Total: 0.38 + 0.3 + 0.3 = 0.98

Result: confidence_score = 0.98 → diagnose
```

**Example 2: Medium Confidence (0.55)**

```
Telemetry:
- Completeness: 65% (some optional fields missing)
- Pattern: High CPU (partial match, cpu_percent=92)
- Conflicts: Minor (heartbeat_present=false)

Calculation:
- Completeness weight: (65 / 100) * 0.4 = 0.26
- Pattern weight: 0.15 (partial match)
- Consistency weight: 0.15 (minor conflicts)
- Total: 0.26 + 0.15 + 0.15 = 0.56

Result: confidence_score = 0.56 → diagnose_low_confidence
```

**Example 3: Low Confidence (0.25)**

```
Telemetry:
- Completeness: 45% (many optional fields missing)
- Pattern: No match
- Conflicts: None

Calculation:
- Completeness weight: (45 / 100) * 0.4 = 0.18
- Pattern weight: 0.0 (no match)
- Consistency weight: 0.3 (no conflicts)
- Total: 0.18 + 0.0 + 0.3 = 0.48

Result: confidence_score = 0.48 → abstain_request_next_check
```

## Decision Tree

```
┌─────────────────────────────────────────────────────────────┐
│                    Start: Telemetry Input                    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Check Safety Rules (6 rules)                    │
│  - Platform event?                                           │
│  - Boot failure (BSOD/KernelPanic)?                          │
│  - Low confidence destructive action?                        │
│  - Network security violation?                               │
│  - Disk operation with low confidence?                       │
│  - Failed state auto-remediation?                            │
└────────────┬───────────────────────────┬────────────────────┘
             │ Violation                 │ No violation
             ▼                           ▼
    ┌────────────────┐         ┌────────────────────────────┐
    │ abstain_       │         │ Check Critical Signals     │
    │ request_       │         │ (power, provisioning,      │
    │ next_check     │         │  resource_health)          │
    └────────────────┘         └────────┬───────────────────┘
                                        │
                         ┌──────────────┴──────────────┐
                         │ Unknown?                    │ All present
                         ▼                             ▼
                ┌────────────────┐         ┌────────────────────────────┐
                │ abstain_       │         │ Check Completeness         │
                │ request_       │         │ (count non-null fields)    │
                │ next_check     │         └────────┬───────────────────┘
                └────────────────┘                  │
                                     ┌──────────────┴──────────────┐
                                     │ < 60%                       │ ≥ 60%
                                     ▼                             ▼
                            ┌────────────────┐         ┌────────────────────────────┐
                            │ abstain_       │         │ Match Patterns (20)        │
                            │ request_       │         │ Calculate Confidence       │
                            │ next_check     │         └────────┬───────────────────┘
                            └────────────────┘                  │
                                                 ┌──────────────┴──────────────┐
                                                 │                             │
                                                 ▼                             ▼
                                    ┌────────────────────────┐   ┌────────────────────────┐
                                    │ confidence ≥ 0.70      │   │ confidence ≥ 0.40      │
                                    │ completeness ≥ 90%     │   │ completeness ≥ 60%     │
                                    │                        │   │                        │
                                    │ → diagnose             │   │ → diagnose_low_        │
                                    │                        │   │    confidence          │
                                    └────────────────────────┘   └────────────────────────┘
                                                 │
                                                 ▼
                                    ┌────────────────────────┐
                                    │ confidence < 0.40      │
                                    │ OR completeness < 60%  │
                                    │                        │
                                    │ → abstain_request_     │
                                    │    next_check          │
                                    └────────────────────────┘
```

## Determinism Guarantee

The decision policy is deterministic: identical telemetry inputs always produce identical diagnostic outputs.

**Determinism Properties:**
- No randomness in decision logic
- No external API calls that could vary
- No timestamps used in decision logic (only in telemetry input)
- Fixed thresholds and weights
- Pattern matching uses exact conditions
- Safety rules are deterministic

**Verification:**
- Property test: "Decision Determinism" validates this guarantee
- Same input processed multiple times produces identical output
- Confidence score, decision state, and diagnosis are always the same

## Usage in Code

The decision policy is implemented in `src/decision_engine.py`:

```python
from src.decision_engine import DecisionEngine

engine = DecisionEngine()

# Process telemetry
decision = engine.decide(
    telemetry=telemetry_input,
    confidence_score=0.85,
    completeness=95.0
)

# Access decision fields
print(f"Decision: {decision.state.value}")
print(f"Diagnosis: {decision.diagnosis}")
print(f"Evidence: {decision.evidence}")
print(f"Next Check: {decision.next_check}")
```

## Related Documentation

- [Safety Rules Documentation](safety_rules.md) - Details on the 6 safety rules
- [Incident Patterns Documentation](incident_patterns.md) - Details on the 20 known patterns
- [Architecture Documentation](architecture.md) - System architecture and component design
