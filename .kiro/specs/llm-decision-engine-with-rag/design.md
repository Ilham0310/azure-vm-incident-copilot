# Design Document: LLM Decision Engine with RAG

## Executive Summary

The Azure VM Incident Copilot is a read-only, LLM-augmented diagnostic system that automates triage for Azure VM incidents. The system processes structured telemetry (30+ fields), retrieves semantically similar past incidents and relevant SOPs via RAG, feeds this context into a free LLM (Groq/Gemini/Ollama) for diagnosis, enforces deterministic safety rules post-LLM, and continuously improves through engineer feedback stored in a local vector database.

### Key Design Principles

| Principle | Implementation |
|-----------|----------------|
| Read-Only Operation | Zero write calls to Azure; all remediation is advisory |
| LLM-First Decision | Groq Llama 3.3 70B as primary decision engine |
| RAG-Augmented Context | ChromaDB + SentenceTransformers (local, free) |
| Deterministic Safety | Safety Guard layer overrides LLM unconditionally |
| Self-Learning | Engineer feedback stored as verified cases in ChromaDB |
| Free LLM Stack | Groq → Gemini Flash → Ollama (all free tiers) |
| Novel Incident Detection | LLM flags patterns outside known 20 SOPs |

### Design Goals

1. **Backward Compatibility**: Maintain the existing `decide(telemetry, confidence_score, completeness) → Decision` interface
2. **Safety First**: All 6 safety rules remain deterministic and override LLM output
3. **Novel Incident Detection**: Identify incidents that don't match the 20 predefined patterns
4. **Self-Learning**: Store past incidents and human feedback to improve over time
5. **SOP Integration**: Consult 12+ Standard Operating Procedures for next_check recommendations
6. **Provider Resilience**: Automatic fallback between Groq → Gemini → Ollama
7. **Local Embeddings**: No API calls for vector generation (sentence-transformers)
8. **Performance**: <10s for 95% of decisions

### System Context

The existing system uses:
- 20 hardcoded incident patterns with exact matching conditions
- 6 deterministic safety rules enforced before pattern matching
- Confidence scoring algorithm (40% completeness, 30% pattern, 30% consistency)
- Three decision states: diagnose, diagnose_low_confidence, abstain_request_next_check

The upgraded system adds:
- LLM reasoning layer that replaces hardcoded pattern matching
- RAG memory store (ChromaDB) for past incidents
- SOP knowledge base (ChromaDB) for next_check recommendations
- Human feedback loop for continuous learning
- Novel incident detection and flagging
- Provider fallback mechanism (Groq → Gemini → Ollama)


## Architecture

### 6-Layer Pipeline Overview

```
══════════════════════════════════════════════════════════════════════
                   AZURE VM INCIDENT COPILOT — v2.0
                   6-Layer LLM + RAG + Self-Learning
══════════════════════════════════════════════════════════════════════

   ┌─────────────────────────────────────────────────────────────────┐
   │  EXTERNAL INPUT                                                  │
   │  Azure ARG · Azure Monitor · Log Analytics · Manual JSON        │
   └──────────────────────────────┬──────────────────────────────────┘
                                  │  TelemetryInput (JSON, 30+ fields)
                                  ▼
╔═════════════════════════════════════════════════════════════════════╗
║  LAYER 1 — TELEMETRY COLLECTOR                                      ║
║  Aggregates signals from Azure data sources into a unified          ║
║  TelemetryInput JSON. VM name, power state, health, metrics,        ║
║  NSG rules, boot diagnostics, agent statuses, SSL, backup.          ║
╚══════════════════════════════════╦══════════════════════════════════╝
                                   ║ validated JSON
                                   ▼
╔═════════════════════════════════════════════════════════════════════╗
║  LAYER 2 — SCHEMA VALIDATOR                                         ║
║  src/validator.py (SchemaValidator)                                  ║
║                                                                      ║
║  ● Pydantic TelemetryInput model — 30+ fields, 8 enums              ║
║  ● Numeric range checks (cpu 0-100, latency ≥ 0, etc.)              ║
║  ● Calculates data_completeness_percent and missing_signals[]       ║
║  ● Returns ValidationResult: valid TelemetryInput OR error list      ║
║  ● Rejects < 3 required fields; ignores unknown fields               ║
╚══════════════════════════════════╦══════════════════════════════════╝
                                   ║ ValidatedTelemetry + completeness
                                   ▼
╔═════════════════════════════════════════════════════════════════════╗
║  LAYER 3 — RAG MEMORY + SOP CONTEXT  [★ NEW]                        ║
║                                                                      ║
║  ┌──────────────────────────────────────────────────────────────┐   ║
║  │  IncidentMemoryStore (src/rag/memory_store.py)               │   ║
║  │  Backend: ChromaDB PersistentClient (local, free)            │   ║
║  │  Embeddings: sentence-transformers/all-MiniLM-L6-v2 (local)  │   ║
║  │                                                              │   ║
║  │  QUERY PATH:                                                  │   ║
║  │  telemetry → text summary → embed → cosine search →          │   ║
║  │  top-3 similar past incidents (similarity ≥ 0.65)            │   ║
║  │  Returns: past telemetry + diagnosis + resolution + outcome  │   ║
║  │  Sorts by: human_verified DESC, similarity DESC              │   ║
║  │                                                              │   ║
║  │  WRITE PATH (Layer 6 feedback):                              │   ║
║  │  new incident → embed → upsert with metadata                 │   ║
║  │  feedback → update outcome + human_verified flag             │   ║
║  └──────────────────────────────────────────────────────────────┘   ║
║                                                                      ║
║  ┌──────────────────────────────────────────────────────────────┐   ║
║  │  SOPKnowledgeBase (src/rag/sop_knowledge.py)                 │   ║
║  │  Backend: ChromaDB (separate collection, pre-populated)      │   ║
║  │  12 SOPs from SOP library (embedded once on first run)       │   ║
║  │                                                              │   ║
║  │  QUERY PATH:                                                  │   ║
║  │  telemetry_text → embed → cosine search →                    │   ║
║  │  top-2 most relevant SOPs (title + steps + warnings)         │   ║
║  └──────────────────────────────────────────────────────────────┘   ║
║                                                                      ║
║  OUTPUT: similar_incidents[0..3] + relevant_sops[0..2]              ║
╚══════════════════════════════════╦══════════════════════════════════╝
                                   ║ telemetry + RAG context
                                   ▼
╔═════════════════════════════════════════════════════════════════════╗
║  LAYER 4 — LLM DECISION ENGINE  [★ NEW]                             ║
║  src/llm/llm_engine.py (LLMDecisionEngine)                          ║
║                                                                      ║
║  PROVIDER FALLBACK CHAIN (tries in order):                          ║
║  ┌────────────────┐  ┌────────────────┐  ┌────────────────────┐    ║
║  │ PRIMARY        │  │ FALLBACK 1     │  │ FALLBACK 2         │    ║
║  │ Groq           │→ │ Gemini 2.0     │→ │ Ollama (local)     │    ║
║  │ Llama 3.3 70B  │  │ Flash          │  │ Llama 3.2          │    ║
║  │ 30 req/min     │  │ 1500 req/day   │  │ Unlimited offline  │    ║
║  │ Free tier      │  │ Free tier      │  │ No API key needed  │    ║
║  └────────────────┘  └────────────────┘  └────────────────────┘    ║
║          ↓ If all fail                                               ║
║  ┌────────────────────────────────────────────────────────────────┐  ║
║  │ EMERGENCY FALLBACK: Rule-based DecisionEngine (legacy v1.0)   │  ║
║  └────────────────────────────────────────────────────────────────┘  ║
║                                                                      ║
║  PROMPT PIPELINE:                                                    ║
║  System Prompt (SYSTEM_PROMPT — static, expert persona)             ║
║        +                                                             ║
║  User Prompt (Jinja2 template):                                      ║
║    • Telemetry text summary + full JSON                              ║
║    • Completeness % + missing signals                                ║
║    • Top-3 similar past incidents                                    ║
║    • Top-2 relevant SOPs                                             ║
║                                                                      ║
║  LLM OUTPUT (JSON, forced via response_format):                     ║
║  {                                                                   ║
║    decision, diagnosis, confidence_score,                           ║
║    pattern_matched, evidence[], evidence_gap[],                     ║
║    next_check, explanation,                                          ║
║    is_novel_incident, novel_incident_description                     ║
║  }                                                                   ║
╚══════════════════════════════════╦══════════════════════════════════╝
                                   ║ LLM Decision object
                                   ▼
╔═════════════════════════════════════════════════════════════════════╗
║  LAYER 5 — SAFETY GUARD  (deterministic, cannot be bypassed)        ║
║  src/safety_guard.py (SafetyGuard.apply_safety_override)            ║
║                                                                      ║
║  Rule 1: Platform/maintenance event detected →                      ║
║          Force ABSTAIN, strip restart from next_check               ║
║  Rule 2: boot_diagnostics = BSOD/KernelPanic →                     ║
║          Remove "restart" from next_check                           ║
║  Rule 3: "disable nsg"/"disable firewall" in next_check →          ║
║          Replace with safe NSG rule review instruction              ║
║  Rule 4: confidence < 0.90 + destructive action in next_check →    ║
║          Remove delete/wipe/destroy/format phrases                  ║
║  Rule 5: power_state = Failed →                                     ║
║          Force ABSTAIN, replace next_check with Azure Support       ║
║  Rule 6: Tracks all rules applied → safety_rules_applied[]         ║
╚══════════════════════════════════╦══════════════════════════════════╝
                                   ║ SafeDecision
                                   ▼
╔═════════════════════════════════════════════════════════════════════╗
║  LAYER 6 — SELF-LEARNING FEEDBACK LOOP  [★ NEW]                     ║
║                                                                      ║
║  AUTO-STORE: Every pipeline run → store incident in ChromaDB        ║
║    incident_id = hash(vm_name + timestamp)                          ║
║    metadata: decision, diagnosis, confidence, pattern,              ║
║              outcome="pending", human_verified=False                ║
║                                                                      ║
║  ENGINEER FEEDBACK (via UI or API):                                 ║
║    ✓ Correct → human_verified=True, outcome="resolved"              ║
║    ✗ Wrong → store corrected diagnosis + resolution                 ║
║              human_verified=True, outcome="corrected"               ║
║                                                                      ║
║  NEXT INCIDENT BENEFIT:                                             ║
║    Similar telemetry → Layer 3 finds this verified case             ║
║    LLM sees: "Past incident (similarity: 0.91, human_verified: True) ║
║               Diagnosis: X, Resolution: Y, Outcome: resolved"      ║
║    → Higher confidence, more accurate diagnosis                     ║
╚══════════════════════════════════╦══════════════════════════════════╝
                                   ║ DiagnosticOutput + incident_id
                                   ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │  OUTPUT                                                          │
  │  DiagnosticOutput JSON (11 fields)                               │
  │  + incident_id (for feedback tracking)                           │
  │  Delivered via: CLI stdout / API response / UI dashboard         │
  └─────────────────────────────────────────────────────────────────┘
```

### Data Flow Summary

```
Telemetry JSON
    → [L2] Validate + score completeness
    → [L3] Embed + find similar incidents + relevant SOPs
    → [L4] LLM: analyze telemetry + RAG context → structured JSON decision
    → [L5] Safety Guard: override unsafe suggestions
    → [L6] Store in ChromaDB (pending)
    → DiagnosticOutput
    → [L6 async] Engineer marks correct/incorrect → update ChromaDB
    → [L3 future] Next similar incident benefits from this case
```


## Component Details

### Layer 2: Schema Validator

**File**: `src/validator.py`  
**Class**: `SchemaValidator`

The SchemaValidator is the first gate in the pipeline. It parses raw JSON telemetry, validates all 30+ fields, computes data completeness, and identifies missing signals that the LLM will be informed about.

#### Validation Pipeline

```
Raw JSON String
    │
    ├─ Step 1: JSON.parse() with line/column error capture
    │          JSONDecodeError → JSONParseError(line, col, description)
    │
    ├─ Step 2: jsonschema validation against azure_vm_triage_schema.json
    │          Type errors → SchemaValidationError(field, constraint, actual)
    │          Enum violations → SchemaValidationError
    │          Range violations → SchemaValidationError
    │
    ├─ Step 3: Pydantic TelemetryInput model construction
    │          Adds vm_name field (Optional[str])
    │          Adds ssl_cert_days_remaining (Optional[int])
    │          Adds last_backup_status (Optional[str])
    │
    └─ Step 4: Completeness calculation
               total_optional_fields = 27
               present = count(non-null optional fields)
               completeness = (present / 27) * 100
               missing_signals = [field for field if null]
```

#### Enum Constraints

| Field | Valid Values |
|-------|-------------|
| power_state | Running, Stopped, Deallocated, Failed, Unknown |
| provisioning_state | Succeeded, Failed, In Progress, Unknown |
| resource_health_status | Available, Degraded, Unavailable, Unknown |
| boot_diagnostics_status | Normal, BSOD, KernelPanic, Stuck, Unknown |
| azure_vm_agent_status | Healthy, Degraded, NotReporting, Failed, Unknown |
| app_health_status | Healthy, Degraded, Unhealthy, Unknown |
| connection_troubleshoot_rdp/ssh | Allow, Deny, Inconclusive, Timeout, Unknown |
| monitor_agent_status | Healthy, Degraded, Failed, NotInstalled, Unknown |


### Layer 3a: Incident Memory Store

**File**: `src/rag/memory_store.py`  
**Class**: `IncidentMemoryStore`  
**Backend**: ChromaDB PersistentClient  
**Embedding Model**: sentence-transformers/all-MiniLM-L6-v2 (local, 22MB, no API key)

The memory store converts telemetry into a text representation, embeds it, and retrieves the most semantically similar past incidents to feed into the LLM as few-shot context.

#### Telemetry-to-Text Conversion

The embedding query is built from key discriminative signals only (not all 30+ fields), ensuring embedding quality:

```
"VM state: Running. Provisioning: Succeeded. Health: Unavailable.
 CPU: 23%. Memory: 41%. Heartbeat: False. Boot: Normal.
 RDP allowed: True. App health: Unknown. VM agent: NotReporting."
```

#### Similarity Search Logic

```python
# HNSW cosine distance → similarity
similarity = 1 - cosine_distance

# Filtering
if similarity >= 0.65:  # min threshold
    include in results

# Sorting priority
key = (human_verified DESC, similarity DESC)
# Verified corrections appear first → LLM trusts them more
```

#### Storage Schema (ChromaDB metadata per incident)

```json
{
  "vm_name": "prod-web-001",
  "timestamp": "2026-04-07T10:30:00Z",
  "decision": "diagnose",
  "diagnosis": "VM agent failed to report heartbeat",
  "next_check": "Restart VM agent via run command",
  "confidence": "0.82",
  "human_verified": "True",
  "outcome": "resolved",
  "pattern": "vm_running_no_heartbeat",
  "power_state": "Running",
  "health_status": "Available"
}
```


### Layer 3b: SOP Knowledge Base

**File**: `src/rag/sop_knowledge.py`  
**Class**: `SOPKnowledgeBase`  
**Collection**: `sops` (separate from incidents)

The SOP knowledge base is pre-populated once on first run with all 12 SOP documents. Each SOP is embedded as: "{title}. Triggers: {triggers}. Steps: {steps}" for high-quality semantic matching.

#### SOP Coverage

| SOP ID | Title | Key Triggers |
|--------|-------|--------------|
| sop_start_stop_vm | Start/Stop VMs | VM stopped, deallocated |
| sop_firewall_whitelist | Firewall Whitelisting | NSG blocks RDP/SSH |
| sop_disk_cleanup | Disk Cleanup | OS disk > 90% full |
| sop_disk_expansion | Disk Expansion | Storage insufficient |
| sop_ssl_renewal | SSL Renewal | SSL < 30 days remaining |
| sop_backup | System Backup | Backup job failed |
| sop_vm_scale | VM Scale Up/Down | High CPU, memory |
| sop_finops_rightsize | FinOps Rightsize | Oversized, low utilization |
| sop_request_admin_access | Admin Access | Need JIT access |
| sop_decommission | Decommission VM | Permanent failed state |
| sop_url_onboarding | URL Onboarding | App gateway misconfigured |
| sop_terminate_unused | Terminate Unused | Orphaned resources |


### Layer 4: LLM Decision Engine

**File**: `src/llm/llm_engine.py`  
**Class**: `LLMDecisionEngine`

The LLM engine is the core intelligence layer. It orchestrates provider selection, prompt construction, response parsing, and maps LLM output back to the internal Decision model.

#### Provider Selection

```python
class ProviderChain:
    providers = [GroqProvider, GeminiProvider, OllamaProvider]
    
    def get_provider(self) -> LLMProvider:
        # Uses cached active provider
        # Re-checks availability if cached provider fails
        # Returns first available provider
        # Raises RuntimeError if none available
```

#### Provider Feature Comparison

| Provider | Model | Free Limit | JSON Mode | Offline | Latency |
|----------|-------|------------|-----------|---------|---------|
| Groq | Llama 3.3 70B | 30 req/min | ✅ response_format=json_object | ❌ | ~1-2s |
| Gemini Flash | gemini-2.0-flash | 1500 req/day | ✅ response_mime_type | ❌ | ~2-3s |
| Ollama | llama3.2 | Unlimited | ✅ format="json" | ✅ | ~5-15s |
| Rule Engine | Legacy v1.0 | Unlimited | N/A (deterministic) | ✅ | <50ms |

#### Decision State Mapping

```python
decision_map = {
    "diagnose":                    DecisionState.DIAGNOSE,
    "diagnose_low_confidence":     DecisionState.DIAGNOSE_LOW_CONFIDENCE,
    "abstain_request_next_check":  DecisionState.ABSTAIN_REQUEST_NEXT_CHECK
}
```


### Layer 5: Safety Guard

**File**: `src/safety_guard.py`  
**Method**: `apply_safety_override(decision, telemetry) -> Decision`

The Safety Guard is deterministic and cannot be bypassed by any LLM output. It runs as a post-processing step on every LLM decision before it leaves the pipeline. All six rules are applied in sequence, not short-circuited.

#### Rule Evaluation Table

| Rule | Trigger Condition | Action | Override Type |
|------|------------------|--------|---------------|
| SR-1 | resource_health_annotation contains "platform", "maintenance", "host update" | Force ABSTAIN; strip restart keywords | Hard override |
| SR-2 | boot_diagnostics_status ∈ {BSOD, KernelPanic} | Remove "restart"/"reboot" from next_check | Soft sanitize |
| SR-3 | "disable nsg" or "disable firewall" in next_check (case-insensitive) | Replace phrase with safe alternative | Soft sanitize |
| SR-4 | confidence_score < 0.90 AND destructive keyword in next_check | Remove delete/wipe/destroy/format/reset | Soft sanitize |
| SR-5 | power_state = Failed | Force ABSTAIN; replace next_check with Azure Support message | Hard override |
| SR-6 | Always | Append safety_rules_applied list to decision metadata | Audit trail |


### Layer 6: Self-Learning Feedback Loop

**Files**: `src/pipeline.py` (auto-store), `ui/app.py` (feedback API)

Every incident is automatically stored after the safety guard as `outcome="pending"`. Engineers can mark decisions as correct or incorrect through the UI, upgrading the stored case to `human_verified=True`.

#### Learning Mechanism

```
Cycle 1: Incident A occurs
    → LLM has no similar cases → makes initial diagnosis
    → Stored as pending

Cycle 2: Engineer reviews → marks ✓ Correct
    → outcome = "resolved", human_verified = True

Cycle 3: Similar incident B occurs
    → RAG finds Incident A (similarity 0.89, human_verified=True)
    → LLM prompt includes: "Past verified case: same pattern, resolved by X"
    → LLM produces higher-confidence, more accurate diagnosis
```

#### Novel Incident Detection

When `is_novel_incident=True` in the LLM response, the incident is:
- Flagged with a "🆕 New Pattern" badge in the UI
- Surfaced in the Novel Incidents panel for priority review
- Stored with `pattern="llm_detected_<short_name>"`
- Engineer feedback creates a new effective "pattern" in the memory store


## Data Models & Schemas

### TelemetryInput (Complete 30+ Field Model)

```python
class TelemetryInput(BaseModel):
    # ── REQUIRED (3 fields) ──────────────────────────────
    power_state:               PowerState
    provisioning_state:        ProvisioningState
    resource_health_status:    ResourceHealthStatus
    
    # ── IDENTITY ─────────────────────────────────────────
    vm_name:                   Optional[str] = None
    subscription_id:           Optional[str] = None
    resource_group:            Optional[str] = None
    location:                  Optional[str] = None
    vm_size:                   Optional[str] = None
    
    # ── HEALTH SIGNALS ────────────────────────────────────
    resource_health_annotation: Optional[str] = None
    heartbeat_present:          Optional[bool] = None
    heartbeat_last_received:    Optional[datetime] = None
    boot_diagnostics_status:    Optional[BootDiagnosticsStatus] = None
    boot_diagnostics_error:     Optional[str] = None
    azure_vm_agent_status:      Optional[AzureVMAgentStatus] = None
    monitor_agent_status:       Optional[MonitorAgentStatus] = None
    
    # ── PERFORMANCE METRICS ───────────────────────────────
    cpu_percent:               Optional[float] = Field(None, ge=0, le=100)
    memory_percent:            Optional[float] = Field(None, ge=0, le=100)
    memory_available_mb:       Optional[float] = Field(None, ge=0)
    os_disk_percent_full:      Optional[float] = Field(None, ge=0, le=100)
    os_disk_latency_ms:        Optional[float] = Field(None, ge=0)
    data_disk_latency_ms:      Optional[float] = Field(None, ge=0)
    network_in_bytes:          Optional[float] = Field(None, ge=0)
    network_out_bytes:         Optional[float] = Field(None, ge=0)
    
    # ── APPLICATION HEALTH ────────────────────────────────
    app_health_status:         Optional[AppHealthStatus] = None
    app_error_message:         Optional[str] = None
    
    # ── NETWORK SECURITY ─────────────────────────────────
    nsg_allow_rdp_3389:        Optional[bool] = None
    nsg_allow_ssh_22:          Optional[bool] = None
    connection_troubleshoot_rdp: Optional[ConnectionTroubleshootResult] = None
    connection_troubleshoot_ssh: Optional[ConnectionTroubleshootResult] = None
    connection_troubleshoot_verdict: Optional[str] = None
    
    # ── COMPLIANCE / SECURITY ────────────────────────────
    ssl_cert_days_remaining:   Optional[int] = Field(None, ge=0)
    last_backup_status:        Optional[str] = None
    last_backup_timestamp:     Optional[datetime] = None
    
    # ── DATA QUALITY METADATA ────────────────────────────
    data_completeness_percent: Optional[float] = Field(None, ge=0, le=100)
    missing_signals:           Optional[List[str]] = None
    
    class Config:
        extra = "ignore"  # forward compatibility
```


### DiagnosticOutput (Extended for LLM v2.0)

```python
class DiagnosticOutput(BaseModel):
    # ── CORE OUTPUTS (7 original fields) ─────────────────
    decision:          DecisionState
    diagnosis:         str
    confidence_score:  float = Field(ge=0.0, le=1.0)
    evidence:          List[str]
    evidence_gap:      List[str]
    next_check:        Optional[str] = None
    explanation:       str
    
    # ── LLM METADATA (new in v2.0) ────────────────────────
    incident_id:               Optional[str] = None   # for feedback tracking
    pattern_matched:           Optional[str] = None
    is_novel_incident:         bool = False
    novel_incident_description: str = ""
    llm_provider:              str = "unknown"
    similar_incidents_used:    int = 0
    sops_consulted:            List[str] = []
    safety_rules_applied:      List[str] = []
    
    @model_validator(mode='after')
    def validate_next_check(self):
        if self.decision == DecisionState.ABSTAIN_REQUEST_NEXT_CHECK:
            if not self.next_check or not self.next_check.strip():
                raise ValueError(
                    "next_check required when decision=abstain_request_next_check"
                )
        return self
```

### Decision (Internal LLM Model)

```python
class Decision(BaseModel):
    state:                     DecisionState
    diagnosis:                 str
    pattern_matched:           Optional[str] = None
    evidence:                  List[str]
    evidence_gap:              List[str]
    next_check:                Optional[str] = None
    reasoning:                 str
    confidence_score:          float = 0.0
    is_novel_incident:         bool = False
    novel_incident_description: str = ""
    llm_provider:              str = "unknown"
    similar_incidents_used:    int = 0
    sops_consulted:            List[str] = []
    safety_rules_applied:      List[str] = []
```

### FeedbackRequest (API Model)

```python
class FeedbackRequest(BaseModel):
    correct:              bool
    corrected_diagnosis:  Optional[str] = None
    corrected_next_check: Optional[str] = None
    outcome:              Literal["resolved", "escalated", "false_positive"]
```


### LLM Raw Response Schema

The LLM is instructed to return only valid JSON matching this exact schema:

```json
{
  "decision": "diagnose | diagnose_low_confidence | abstain_request_next_check",
  "diagnosis": "One clear sentence describing the root cause",
  "confidence_score": 0.0,
  "pattern_matched": "known_pattern_name or llm_detected_<short_name>",
  "evidence": ["signal=value", "signal2=value2"],
  "evidence_gap": ["missing_signal_1", "missing_signal_2"],
  "next_check": "Specific action referencing SOP name if applicable",
  "explanation": "2-3 sentence reasoning",
  "is_novel_incident": false,
  "novel_incident_description": "If novel, describe the new pattern"
}
```


## API Specifications

### Base Configuration

```
Base URL:    http://localhost:8000
Auth:        None (internal tool)
Content-Type: application/json
```

### Core Triage Endpoints

#### POST /api/triage

Submit telemetry for real-time analysis.

**Request**:
```json
{
  "vm_name": "prod-web-001",
  "power_state": "Running",
  "provisioning_state": "Succeeded",
  "resource_health_status": "Available",
  "heartbeat_present": false,
  "cpu_percent": 22.5,
  "memory_percent": 67.0,
  "azure_vm_agent_status": "NotReporting"
}
```

**Response 200**:
```json
{
  "incident_id": "a3f7c9d2e1b4",
  "decision": "diagnose",
  "diagnosis": "Azure VM agent has stopped reporting; VM appears healthy by metrics but monitoring pipeline is broken.",
  "confidence_score": 0.84,
  "pattern_matched": "vm_running_no_heartbeat",
  "evidence": ["heartbeat_present=false", "azure_vm_agent_status=NotReporting", "power_state=Running"],
  "evidence_gap": ["heartbeat_last_received", "boot_diagnostics_status"],
  "next_check": "Per SOP_Azure Request Admin Access: Use JIT access to restart VM agent via Azure Run Command. Command: 'Restart-Service WindowsAzureGuestAgent'",
  "explanation": "The VM is running with normal CPU/memory but the Azure VM agent has stopped reporting heartbeats. This is a classic agent failure pattern. Restarting the agent service via Run Command is safe and non-disruptive.",
  "is_novel_incident": false,
  "novel_incident_description": "",
  "llm_provider": "groq",
  "similar_incidents_used": 2,
  "sops_consulted": ["SOP_Azure Request Admin Access on VM", "SOP_Azure System Backup on VM"],
  "safety_rules_applied": []
}
```

**Response 422 (Validation Error)**:
```json
{
  "error": "schema_validation_error",
  "errors": [
    {
      "field": "cpu_percent",
      "message": "Value 105.0 is greater than maximum 100",
      "constraint": "maximum: 100",
      "actual_value": "105.0"
    }
  ]
}
```

**Response 503 (No LLM Available)**:
```json
{
  "error": "llm_unavailable",
  "message": "All LLM providers failed. Set GROQ_API_KEY or GEMINI_API_KEY in .env, or start Ollama locally.",
  "fallback_used": "rule_engine",
  "result": { "...": "rule-based fallback output..." }
}
```


#### POST /api/feedback/{incident_id}

Submit engineer feedback for a past diagnosis.

**Path Parameter**: `incident_id` — 12-character hex string from triage response

**Request**:
```json
{
  "correct": false,
  "corrected_diagnosis": "The VM agent failed due to a corrupted extension, not a simple service stop.",
  "corrected_next_check": "Remove and reinstall the Microsoft.Azure.Monitor extension via portal > Extensions.",
  "outcome": "resolved"
}
```

**Response 200**:
```json
{
  "status": "ok",
  "message": "Feedback recorded. Future similar incidents will benefit from this correction.",
  "incident_id": "a3f7c9d2e1b4",
  "human_verified": true
}
```

#### GET /api/memory/stats

Returns memory store statistics for the dashboard.

**Response 200**:
```json
{
  "total": 47,
  "verified": 23,
  "patterns": {
    "vm_running_no_heartbeat": 8,
    "high_cpu": 6,
    "nsg_blocks_rdp": 5,
    "llm_detected_extension_corrupt": 3,
    "os_disk_full": 4
  },
  "top_patterns": [
    ["vm_running_no_heartbeat", 8],
    ["high_cpu", 6],
    ["nsg_blocks_rdp", 5],
    ["os_disk_full", 4],
    ["llm_detected_extension_corrupt", 3]
  ]
}
```

#### GET /api/memory/similar

Find similar past incidents for a given incident.

**Query Parameters**: `telemetry_id` (incident_id string)

**Response 200**:
```json
{
  "similar_incidents": [
    {
      "telemetry_summary": "VM state: Running. Health: Available. Heartbeat: False. Agent: NotReporting.",
      "diagnosis": "VM agent heartbeat failure after Windows Update",
      "next_check": "Restart WindowsAzureGuestAgent via Run Command",
      "decision": "diagnose",
      "confidence": 0.88,
      "human_verified": true,
      "outcome": "resolved",
      "pattern": "vm_running_no_heartbeat",
      "similarity_score": 0.923
    }
  ]
}
```


#### POST /api/memory/clear

Clear all ChromaDB memory (testing only).

**Request**:
```json
{ "confirm": "yes_delete_all_memory" }
```

**Response 200**:
```json
{ 
  "status": "ok", 
  "message": "All incident memory cleared.", 
  "deleted_count": 47 
}
```

#### GET /health

System health check including LLM provider availability.

**Response 200**:
```json
{
  "status": "healthy",
  "providers": {
    "groq": "available",
    "gemini": "available",
    "ollama": "unavailable"
  },
  "active_provider": "groq",
  "memory_store": {
    "total_incidents": 47,
    "collection_status": "ok"
  },
  "sop_kb": {
    "total_sops": 12,
    "collection_status": "ok"
  }
}
```

### CLI Interface

```bash
# Setup phase (generate schemas, policy, benchmark data)
python main.py --setup

# Single VM triage
python main.py --input incident.json
python main.py --input incident.json --output result.json

# Batch benchmark mode
python main.py --benchmark data/benchmark_cases.csv

# UI server mode
python main.py --ui # → http://localhost:8000

# Exit codes
# 0  = success
# 1  = JSON parse error
# 2  = schema validation error
# 3  = file not found
# 4  = file read error
# 5  = decision engine error
# 6  = LLM provider unavailable (rule engine fallback used)
# 99 = unexpected internal error
```


## Prompt Engineering Strategy

### System Prompt Design

The system prompt establishes the LLM as a domain expert with explicit behavioral constraints. It is static — the same for every request. Key elements:

#### 1. Role Definition (Expert Framing)

```
You are an Azure VM Incident Triage Expert AI. You analyze Azure VM telemetry 
and produce structured diagnostic decisions.
```

Expert framing improves output quality versus generic assistant framing.

#### 2. Explicit Output Format (JSON Schema)

The LLM is given the exact JSON schema it must return. With Groq and Gemini, `response_format=json_object` enforces JSON mode at the API level, preventing markdown wrapping.

#### 3. Decision Rules (Explicit Thresholds)

```
- Use "diagnose" when confidence >= 0.70 AND root cause is clear
- Use "diagnose_low_confidence" when confidence 0.40-0.69 OR signals conflict
- Use "abstain_request_next_check" when completeness < 60% OR confidence < 0.40
```

Explicit thresholds prevent the LLM from over-diagnosing or under-diagnosing.

#### 4. Safety Rules in Prompt (Belt + Suspenders)

Safety rules appear in both the system prompt AND the Safety Guard layer. The prompt prevents the LLM from generating unsafe suggestions; the Safety Guard catches any that slip through:

```
SAFETY RULES (NEVER violate):
1. NEVER suggest restarting VM during platform maintenance events
2. NEVER suggest restart for BSOD or KernelPanic without data backup
3. NEVER suggest disabling NSG, firewall, or security rules
...
```

#### 5. Novelty Detection Instruction

```
NOVELTY DETECTION:
If the telemetry pattern does not match any known pattern, set is_novel_incident=true 
and describe what you see. Still produce a best-effort diagnosis and next_check.
Novel incidents are especially valuable — be thorough.
```


### User Prompt Template (Jinja2)

The user prompt is dynamic — assembled fresh for each incident. Structure:

```
## Current VM Telemetry
VM Name: {{ vm_name }}
Timestamp: {{ timestamp }}

### Signal Summary (human-readable)
{{ telemetry_text }}    ← embedded summary for quick LLM parsing

### Full Telemetry JSON
{{ telemetry_json }}    ← complete JSON for completeness

### Data Completeness
{{ completeness_percent }}% available
Missing: {{ missing_signals }}

---
## Similar Past Incidents (from memory)  ← RAG context

{% for incident in similar_incidents %}
### Past Incident {{ loop.index }} (similarity: {{ incident.similarity_score }})
- Telemetry: {{ incident.telemetry_summary }}
- Diagnosis: {{ incident.diagnosis }}
- Resolution: {{ incident.next_check }}
- Outcome: {{ incident.outcome }}
- Human verified: {{ incident.human_verified }}
{% endfor %}

---
## Relevant SOPs              ← SOP context

{% for sop in relevant_sops %}
### {{ sop.title }}
Steps: {{ sop.steps }}
Warnings: {{ sop.warnings }}
{% endfor %}
```

### Temperature and Sampling Strategy

All providers use `temperature=0.1` (near-deterministic). This is intentional:
- Incident triage requires reproducible, fact-based diagnoses
- Low temperature reduces hallucination risk in structured JSON output
- Slight non-zero value allows the LLM to handle novel patterns slightly better than temperature=0

### Prompt Token Budget

| Section | Approx Tokens | Notes |
|---------|---------------|-------|
| System prompt | ~600 | Static, cached by provider |
| Telemetry summary | ~100 | Key signals only |
| Full telemetry JSON | ~300 | Complete but compact |
| Similar incidents (3) | ~400 | Most valuable context |
| Relevant SOPs (2) | ~250 | Steps + warnings |
| **Total** | **~1650** | Well within 8K context |
| LLM Output | ~350 | Structured JSON |


## Error Handling & Fallback Logic

### Layer-by-Layer Error Handling

```
Layer 2 (Validator):
  JSONDecodeError → JSONParseError(line, col)  → HTTP 400
  jsonschema.ValidationError → detailed field errors → HTTP 422
  Pydantic ValidationError → field-level messages → HTTP 422
  FileNotFoundError → HTTP 404
  PermissionError → HTTP 500

Layer 3 (RAG):
  ChromaDB unavailable → log warning, return [] (no similar cases)
                        → pipeline continues without RAG context
  Embedding model download fails → retry 3x with backoff
                                 → if still fails, return []
  
  Empty collection (first run) → return [] silently
  SentenceTransformer OOM → catch RuntimeError → return []

Layer 4 (LLM Engine):
  Groq API error (429 rate limit) → immediate switch to Gemini
  Groq API error (5xx) → retry once → switch to Gemini
  Gemini API error → switch to Ollama
  Ollama not running → switch to rule-based engine
  All providers failed → use rule-based engine + log CRITICAL
  JSON parse failure → parse_error fallback response (abstain + safe)
  Malformed JSON from LLM → strip markdown fences → retry parse
                           → if fails, return safe abstain fallback

Layer 5 (Safety Guard):
  Any exception in safety guard → log ERROR → return original decision
  (Safety guard failure is non-fatal but logged for review)

Layer 6 (Memory Store):
  Store failure → log WARNING → return DiagnosticOutput without incident_id
  Feedback update failure → log WARNING → return HTTP 200 with warning
```


### LLM Provider Fallback Decision Tree

```
Start: LLM call needed
    │
    ├─ GROQ_API_KEY set?
    │   ├─ YES → try Groq Llama 3.3 70B
    │   │         ├─ Success → use result, cache provider
    │   │         ├─ 429 (rate limit) → wait 2s, try once more
    │   │         │   ├─ Success → use result
    │   │         │   └─ Fail → try Gemini
    │   │         └─ 5xx error → try Gemini immediately
    │   └─ NO → try Gemini
    │
    ├─ GEMINI_API_KEY set?
    │   ├─ YES → try Gemini 2.0 Flash
    │   │         ├─ Success → use result
    │   │         └─ Error → try Ollama
    │   └─ NO → try Ollama
    │
    ├─ Ollama running locally?
    │   ├─ YES → try Ollama llama3.2
    │   │         ├─ Success → use result (will be slow, ~5-15s)
    │   │         └─ Error → use rule engine
    │   └─ NO → use rule engine
    │
    └─ Rule Engine (legacy v1.0)
        → deterministic pattern matching
        → result flagged with llm_provider="rule_engine_fallback"
        → operator alerted via health endpoint
```

### JSON Parse Error Recovery

When the LLM returns malformed JSON (rare but possible with Ollama):

```python
def _parse_llm_response(self, raw: str) -> dict:
    # Step 1: Strip markdown fences
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    
    # Step 2: Try parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Step 3: Fallback to safe abstain
        return {
            "decision": "abstain_request_next_check",
            "diagnosis": "LLM returned malformed JSON",
            "confidence_score": 0.0,
            "evidence": [],
            "evidence_gap": ["llm_parse_error"],
            "next_check": "Manual review required",
            "explanation": "LLM output could not be parsed",
            "is_novel_incident": False
        }
```


## Performance Considerations

### Latency Targets

| Component | Target | P95 | Notes |
|-----------|--------|-----|-------|
| Schema Validation | <50ms | <100ms | Pydantic + jsonschema |
| RAG Memory Query | <300ms | <500ms | ChromaDB HNSW index |
| SOP KB Query | <200ms | <400ms | Smaller collection |
| Embedding Generation | <100ms | <200ms | Local sentence-transformers |
| LLM Inference (Groq) | <2s | <3s | Network + inference |
| LLM Inference (Gemini) | <3s | <5s | Network + inference |
| LLM Inference (Ollama) | <10s | <15s | Local CPU inference |
| Safety Guard | <10ms | <20ms | Deterministic rules |
| Memory Store Write | <100ms | <200ms | Async, non-blocking |
| **Total (Groq)** | **<3s** | **<5s** | Typical case |
| **Total (Ollama)** | **<12s** | **<18s** | Offline fallback |

### Optimization Strategies

#### 1. Embedding Model Caching
```python
# Load once at startup, reuse for all requests
_embedding_model = None

def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    return _embedding_model
```

#### 2. ChromaDB Persistent Client
```python
# Use PersistentClient, not ephemeral client
client = chromadb.PersistentClient(path="data/chroma_memory")
# HNSW index for fast cosine similarity search
collection = client.get_or_create_collection(
    name="incidents",
    metadata={"hnsw:space": "cosine"}
)
```

#### 3. LLM Provider Caching
```python
# Cache active provider to avoid re-checking on every request
_active_provider = None

def get_provider():
    global _active_provider
    if _active_provider and _active_provider.is_available():
        return _active_provider
    # Only re-check if cached provider fails
    _active_provider = _find_first_available_provider()
    return _active_provider
```

#### 4. Async Memory Store Writes
```python
# Don't block response on memory store write
async def store_incident_async(incident_data):
    # Write to ChromaDB in background
    await asyncio.to_thread(memory_store.add, incident_data)

# In main pipeline:
asyncio.create_task(store_incident_async(result))
return result  # Don't wait for storage
```


### Memory Growth Management

| Incidents Stored | ChromaDB Size | Query Latency | Action |
|------------------|---------------|---------------|--------|
| 0-1,000 | <50MB | <100ms | Normal operation |
| 1,000-5,000 | 50-250MB | <200ms | Normal operation |
| 5,000-10,000 | 250-500MB | <300ms | Log INFO: approaching limit |
| 10,000+ | >500MB | <500ms | Log WARNING: recommend pruning |

**Pruning Strategy**:
- Manual pruning via `/api/memory/prune?before=2026-01-01`
- Keep all `human_verified=True` incidents
- Remove `outcome=false_positive` incidents older than 90 days
- Remove `outcome=pending` incidents older than 180 days


## Free LLM Provider Configuration

### Groq (Primary)

**Model**: `llama-3.3-70b-versatile`  
**Free Tier**: 30 requests/minute, 14,400 requests/day  
**Setup**:
```bash
# Get API key from https://console.groq.com/keys
export GROQ_API_KEY="gsk_..."

# Or in .env file
GROQ_API_KEY=gsk_...
```

**Pros**:
- Fastest inference (~1-2s)
- Best JSON mode support
- High quality outputs

**Cons**:
- Rate limits can be hit during batch processing
- Requires internet connection

### Gemini Flash (Fallback 1)

**Model**: `gemini-2.0-flash-exp`  
**Free Tier**: 1,500 requests/day, 1M tokens/day  
**Setup**:
```bash
# Get API key from https://aistudio.google.com/apikey
export GEMINI_API_KEY="AIza..."

# Or in .env file
GEMINI_API_KEY=AIza...
```

**Pros**:
- Generous daily limits
- Good JSON mode support
- Fast inference (~2-3s)

**Cons**:
- Slightly slower than Groq
- Requires internet connection

### Ollama (Fallback 2)

**Model**: `llama3.2` (3B parameters)  
**Free Tier**: Unlimited (runs locally)  
**Setup**:
```bash
# Install Ollama from https://ollama.com/download
# Windows: Download installer
# macOS: brew install ollama
# Linux: curl -fsSL https://ollama.com/install.sh | sh

# Pull model (one-time, ~2GB download)
ollama pull llama3.2

# Start server (runs in background)
ollama serve

# Verify
curl http://localhost:11434/api/tags
```

**Pros**:
- Works offline
- No API keys needed
- Unlimited requests

**Cons**:
- Slower inference (~5-15s on CPU)
- Lower quality outputs than 70B models
- Requires local installation

### Rule Engine (Emergency Fallback)

**Model**: Legacy v1.0 pattern matching  
**Free Tier**: Unlimited (deterministic)  
**Setup**: No setup required (built-in)

**Pros**:
- Instant (<50ms)
- Works offline
- Deterministic

**Cons**:
- Cannot detect novel incidents
- Limited to 20 hardcoded patterns
- No learning capability


## Implementation Phases

### Phase 1: Core LLM Integration (Foundation)
- Implement LLM provider abstraction layer
- Add Groq, Gemini, Ollama providers
- Implement provider fallback chain
- Add JSON response parsing and validation
- Maintain backward compatibility with existing interface

### Phase 2: RAG Memory Store (Learning)
- Implement ChromaDB incident memory store
- Add sentence-transformers embedding model
- Implement similarity search and retrieval
- Add automatic incident storage after each decision
- Implement telemetry-to-text conversion

### Phase 3: SOP Knowledge Base (Guidance)
- Create SOP data structure and storage
- Populate 12 SOPs from documentation
- Implement SOP embedding and retrieval
- Integrate SOP recommendations into prompts
- Add SOP reference tracking in outputs

### Phase 4: Prompt Engineering (Intelligence)
- Design system prompt with safety rules
- Create dynamic user prompt template (Jinja2)
- Implement RAG context injection
- Add novelty detection instructions
- Tune temperature and sampling parameters

### Phase 5: Safety Guard Integration (Protection)
- Integrate existing safety guard with LLM outputs
- Ensure all 6 rules override LLM unconditionally
- Add safety rule tracking to outputs
- Test safety guard with adversarial LLM outputs

### Phase 6: Feedback Loop (Improvement)
- Implement feedback API endpoints
- Add human verification flag to memory store
- Implement corrected diagnosis storage
- Prioritize verified cases in RAG retrieval
- Add feedback UI components to dashboard

### Phase 7: API & UI Extensions (Usability)
- Add LLM metadata to API responses
- Implement memory stats endpoint
- Add novel incident detection UI
- Implement feedback submission UI
- Add LLM provider health monitoring

### Phase 8: Testing & Validation (Quality)
- Property-based tests for LLM integration
- Benchmark LLM vs rule-based engine
- Test provider fallback scenarios
- Validate safety guard overrides
- Test feedback loop end-to-end

