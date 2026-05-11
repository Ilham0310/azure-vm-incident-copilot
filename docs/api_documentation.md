# API Documentation

## Overview

The Azure VM Incident Copilot provides a RESTful API for triage operations, memory management, feedback submission, and system monitoring. All endpoints are accessible via the web UI server.

**Base URL**: `http://localhost:8000`

**Authentication**: None (internal tool)

**Content-Type**: `application/json`

## Table of Contents

- [Core Triage Endpoints](#core-triage-endpoints)
  - [POST /api/triage](#post-apitriage)
- [Memory Management](#memory-management)
  - [GET /api/memory/stats](#get-apimemorystats)
  - [GET /api/novel-incidents](#get-apinovel-incidents)
  - [POST /api/memory/prune](#post-apimemoryprune)
- [Feedback Loop](#feedback-loop)
  - [POST /api/feedback/{incident_id}](#post-apifeedbackincident_id)
- [Shadow Mode](#shadow-mode)
  - [GET /api/shadow-mode/stats](#get-apishadow-modestats)
- [Monitoring](#monitoring)
  - [GET /health](#get-health)
  - [GET /api/logs/decision/{request_id}](#get-apilogsdecisionrequest_id)
- [Agent Control](#agent-control)
  - [POST /api/agent/start](#post-apiagentstart)
  - [POST /api/agent/stop](#post-apiagentstop)
  - [GET /api/agent/status](#get-apiagentstatus)
  - [POST /api/agent/scan-now](#post-apiagentscan-now)
- [Dashboard Data](#dashboard-data)
  - [GET /api/status](#get-apistatus)
  - [GET /api/feed](#get-apifeed)

---

## Core Triage Endpoints

### POST /api/triage

Submit telemetry for real-time analysis and diagnosis.

**Request Body**:
```json
{
  "telemetry": {
    "vm_name": "prod-web-001",
    "power_state": "Running",
    "provisioning_state": "Succeeded",
    "resource_health_status": "Available",
    "heartbeat_present": false,
    "azure_vm_agent_status": "NotReporting",
    "cpu_percent": 22.5,
    "memory_percent": 67.0,
    "boot_diagnostics_status": "Normal"
  }
}
```

**Required Fields** (minimum 3):
- `power_state`: "Running" | "Stopped" | "Deallocated" | "Failed" | "Unknown"
- `provisioning_state`: "Succeeded" | "Failed" | "In Progress" | "Unknown"
- `resource_health_status`: "Available" | "Degraded" | "Unavailable" | "Unknown"

**Optional Fields** (30+ available, see schema for complete list):
- `vm_name`, `subscription_id`, `resource_group`, `location`, `vm_size`
- `heartbeat_present`, `heartbeat_last_received`, `boot_diagnostics_status`
- `cpu_percent`, `memory_percent`, `os_disk_percent_full`, `os_disk_latency_ms`
- `nsg_allow_rdp_3389`, `nsg_allow_ssh_22`, `connection_troubleshoot_rdp`
- `ssl_cert_days_remaining`, `last_backup_status`

**Response 200 (Success)**:
```json
{
  "decision": "diagnose",
  "diagnosis": "Azure VM agent has stopped reporting; VM appears healthy by metrics but monitoring pipeline is broken.",
  "confidence_score": 0.84,
  "evidence": [
    "heartbeat_present=false",
    "azure_vm_agent_status=NotReporting",
    "power_state=Running"
  ],
  "evidence_gap": [
    "heartbeat_last_received",
    "boot_diagnostics_status"
  ],
  "next_check": "Per SOP_Azure Request Admin Access: Use JIT access to restart VM agent via Azure Run Command. Command: 'Restart-Service WindowsAzureGuestAgent'",
  "explanation": "The VM is running with normal CPU/memory but the Azure VM agent has stopped reporting heartbeats. This is a classic agent failure pattern. Restarting the agent service via Run Command is safe and non-disruptive.",
  
  "incident_id": "a3f7c9d2e1b4",
  "llm_provider": "groq",
  "similar_incidents_used": 2,
  "sops_consulted": [
    "SOP_Azure Request Admin Access on VM",
    "SOP_Azure System Backup on VM"
  ],
  "is_novel_incident": false,
  "novel_incident_description": "",
  "pattern_matched": "vm_running_no_heartbeat",
  "safety_rules_applied": []
}
```

**Response Fields**:

**Core Fields**:
- `decision`: Decision state (diagnose | diagnose_low_confidence | abstain_request_next_check)
- `diagnosis`: Human-readable root cause description
- `confidence_score`: Float 0.0-1.0 indicating diagnostic certainty
- `evidence`: List of telemetry signals supporting the diagnosis
- `evidence_gap`: List of missing or incomplete signals
- `next_check`: Specific action to gather more information (required when decision=abstain)
- `explanation`: Reasoning for the decision

**LLM Metadata** (when LLM_ENABLED=true):
- `incident_id`: 12-character hex identifier for feedback tracking
- `llm_provider`: Provider used (groq | gemini | ollama | rule_engine_fallback)
- `similar_incidents_used`: Number of past incidents retrieved from RAG memory
- `sops_consulted`: List of SOPs referenced in next_check
- `is_novel_incident`: Boolean flag indicating if this is a new pattern
- `novel_incident_description`: Description of novel pattern (if applicable)
- `pattern_matched`: Pattern name or "llm_detected_<name>" for novel incidents
- `safety_rules_applied`: List of safety rules that overrode LLM output

**Response 400 (Validation Error)**:
```json
{
  "error": "Schema validation failed",
  "details": [
    {
      "field": "cpu_percent",
      "message": "Value 105.0 is greater than maximum 100",
      "constraint": "maximum: 100",
      "actual_value": "105.0"
    }
  ]
}
```

**Response 500 (Server Error)**:
```json
{
  "detail": "Internal server error message"
}
```

**Example Usage**:

```bash
# cURL
curl -X POST http://localhost:8000/api/triage \
  -H "Content-Type: application/json" \
  -d '{
    "telemetry": {
      "power_state": "Running",
      "provisioning_state": "Succeeded",
      "resource_health_status": "Available",
      "heartbeat_present": false,
      "azure_vm_agent_status": "NotReporting"
    }
  }'

# Python
import requests

response = requests.post(
    "http://localhost:8000/api/triage",
    json={
        "telemetry": {
            "power_state": "Running",
            "provisioning_state": "Succeeded",
            "resource_health_status": "Available",
            "heartbeat_present": False,
            "azure_vm_agent_status": "NotReporting"
        }
    }
)

result = response.json()
print(f"Decision: {result['decision']}")
print(f"Diagnosis: {result['diagnosis']}")
print(f"Incident ID: {result['incident_id']}")
```

---

## Memory Management

### GET /api/memory/stats

Get memory store statistics including total incidents, verified count, and patterns distribution.

**Response 200**:
```json
{
  "total": 147,
  "verified": 23,
  "novel_incidents": 5,
  "patterns": {
    "vm_running_no_heartbeat": 34,
    "high_cpu": 28,
    "nsg_blocks_rdp": 19,
    "disk_full": 15,
    "llm_detected_ssl_expiry": 5,
    "...": "..."
  },
  "top_patterns": [
    {"pattern": "vm_running_no_heartbeat", "count": 34},
    {"pattern": "high_cpu", "count": 28},
    {"pattern": "nsg_blocks_rdp", "count": 19},
    {"pattern": "disk_full", "count": 15},
    {"pattern": "llm_detected_ssl_expiry", "count": 5}
  ]
}
```

**Response Fields**:
- `total`: Total number of incidents stored
- `verified`: Number of incidents with human_verified=True
- `novel_incidents`: Number of incidents flagged as novel by LLM
- `patterns`: Dictionary of pattern names and their counts
- `top_patterns`: Top 5 patterns by frequency

**Example Usage**:

```bash
# cURL
curl http://localhost:8000/api/memory/stats | jq

# Python
import requests

response = requests.get("http://localhost:8000/api/memory/stats")
stats = response.json()

print(f"Total incidents: {stats['total']}")
print(f"Verified: {stats['verified']}")
print(f"Novel: {stats['novel_incidents']}")
```

---

### GET /api/novel-incidents

Get all novel incidents flagged by the LLM.

**Query Parameters**:
- `limit` (optional, default: 50): Maximum number of incidents to return

**Response 200**:
```json
[
  {
    "incident_id": "c5f8a2b3d1e4",
    "telemetry_summary": "VM state: Running. Provisioning: Succeeded. Health: Available. CPU: 15%. Memory: 45%. SSL cert: 5 days remaining.",
    "diagnosis": "SSL certificate expiring in 5 days. Renewal required to prevent service disruption.",
    "confidence": 0.88,
    "timestamp": "2026-04-07T10:30:00Z",
    "pattern": "llm_detected_ssl_expiry",
    "vm_name": "prod-web-001"
  },
  {
    "incident_id": "d6g9b3c4e2f5",
    "telemetry_summary": "VM state: Running. Provisioning: Succeeded. Health: Degraded. Backup: Failed for 7 days.",
    "diagnosis": "Backup job has failed for 7 consecutive days. Data loss risk if VM fails.",
    "confidence": 0.82,
    "timestamp": "2026-04-06T14:20:00Z",
    "pattern": "llm_detected_backup_failure",
    "vm_name": "prod-db-002"
  }
]
```

**Response Fields** (per incident):
- `incident_id`: 12-character hex identifier
- `telemetry_summary`: Text summary of telemetry used for embedding
- `diagnosis`: LLM-generated diagnosis
- `confidence`: Confidence score (0.0-1.0)
- `timestamp`: ISO 8601 timestamp
- `pattern`: Pattern name (starts with "llm_detected_" for novel incidents)
- `vm_name`: VM name from telemetry

**Example Usage**:

```bash
# cURL
curl http://localhost:8000/api/novel-incidents?limit=10 | jq

# Python
import requests

response = requests.get(
    "http://localhost:8000/api/novel-incidents",
    params={"limit": 10}
)

novel_incidents = response.json()
for incident in novel_incidents:
    print(f"{incident['vm_name']}: {incident['diagnosis']}")
```

---

### POST /api/memory/prune

Prune old incidents from memory store. Incidents with `human_verified=True` are never deleted.

**Request Body**:
```json
{
  "before": "2026-01-01"
}
```

**Request Fields**:
- `before`: ISO date string (YYYY-MM-DD). Incidents older than this date will be deleted (except verified ones)

**Response 200**:
```json
{
  "status": "ok",
  "deleted_count": 42,
  "message": "Deleted 42 incidents older than 2026-01-01"
}
```

**Response 400 (Invalid Date)**:
```json
{
  "error": "Invalid date format. Use ISO format: YYYY-MM-DD"
}
```

**Example Usage**:

```bash
# cURL
curl -X POST http://localhost:8000/api/memory/prune \
  -H "Content-Type: application/json" \
  -d '{"before": "2026-01-01"}'

# Python
import requests

response = requests.post(
    "http://localhost:8000/api/memory/prune",
    json={"before": "2026-01-01"}
)

result = response.json()
print(f"Deleted {result['deleted_count']} incidents")
```

---

## Feedback Loop

### POST /api/feedback/{incident_id}

Submit engineer feedback for a past diagnosis to enable continuous learning.

**Path Parameters**:
- `incident_id`: 12-character hex identifier from triage response

**Request Body**:
```json
{
  "correct": false,
  "corrected_diagnosis": "The VM agent failed due to a corrupted extension, not a simple service stop.",
  "corrected_next_check": "Remove and reinstall the Microsoft.Azure.Monitor extension via portal > Extensions.",
  "outcome": "resolved"
}
```

**Request Fields**:
- `correct` (required): Boolean indicating if the diagnosis was correct
- `corrected_diagnosis` (optional): Corrected diagnosis if `correct=false`
- `corrected_next_check` (optional): Corrected next_check if `correct=false`
- `outcome` (optional, default: "resolved"): Outcome of the incident
  - `"resolved"`: Issue was successfully resolved
  - `"escalated"`: Issue required escalation
  - `"false_positive"`: Not actually an incident

**Response 200**:
```json
{
  "status": "ok",
  "message": "Feedback recorded. Future similar incidents will benefit from this correction.",
  "incident_id": "a3f7c9d2e1b4",
  "human_verified": true
}
```

**Response 404 (Incident Not Found)**:
```json
{
  "error": "Incident not found",
  "incident_id": "nonexistent123"
}
```

**Example Usage**:

```bash
# Mark as correct
curl -X POST http://localhost:8000/api/feedback/a3f7c9d2e1b4 \
  -H "Content-Type: application/json" \
  -d '{
    "correct": true,
    "outcome": "resolved"
  }'

# Provide corrections
curl -X POST http://localhost:8000/api/feedback/b4e8d3f1a2c5 \
  -H "Content-Type: application/json" \
  -d '{
    "correct": false,
    "corrected_diagnosis": "VM agent failed due to corrupted extension",
    "corrected_next_check": "Remove and reinstall the extension",
    "outcome": "resolved"
  }'
```

**Python Example**:

```python
import requests

def submit_feedback(incident_id, correct, corrected_diagnosis=None, 
                   corrected_next_check=None, outcome="resolved"):
    """Submit feedback for an incident."""
    response = requests.post(
        f"http://localhost:8000/api/feedback/{incident_id}",
        json={
            "correct": correct,
            "corrected_diagnosis": corrected_diagnosis,
            "corrected_next_check": corrected_next_check,
            "outcome": outcome
        }
    )
    return response.json()

# Mark as correct
result = submit_feedback("a3f7c9d2e1b4", correct=True)

# Provide corrections
result = submit_feedback(
    "b4e8d3f1a2c5",
    correct=False,
    corrected_diagnosis="VM agent failed due to corrupted extension",
    corrected_next_check="Remove and reinstall the extension"
)
```

**How Feedback Improves the System**:

1. **Human Verification**: Incident marked with `human_verified=True`
2. **Prioritized Retrieval**: Verified cases appear first in RAG similarity search
3. **Corrected Versions**: Stored alongside original LLM output
4. **Learning Loop**: Future similar incidents benefit from corrections

---

## Shadow Mode

### GET /api/shadow-mode/stats

Get shadow mode statistics including agreement rates and disagreement cases.

**Response 200**:
```json
{
  "total_decisions": 47,
  "decision_agreement_rate": 89.36,
  "diagnosis_exact_match_rate": 72.34,
  "diagnosis_similar_rate": 91.49,
  "next_check_exact_match_rate": 68.09,
  "disagreement_cases": [
    {
      "timestamp": "2026-04-07T10:30:00Z",
      "vm_name": "prod-web-001",
      "rule_decision": "diagnose",
      "llm_decision": "abstain_request_next_check",
      "rule_diagnosis": "NSG blocks RDP",
      "llm_diagnosis": "Insufficient data for diagnosis",
      "pattern_matched": "nsg_blocks_rdp"
    }
  ]
}
```

**Response Fields**:
- `total_decisions`: Total number of shadow mode comparisons
- `decision_agreement_rate`: Percentage where both engines chose same decision state
- `diagnosis_exact_match_rate`: Percentage of exact diagnosis text matches
- `diagnosis_similar_rate`: Percentage of exact or semantically similar diagnoses
- `next_check_exact_match_rate`: Percentage of exact next_check matches
- `disagreement_cases`: List of recent disagreements (up to 10)

**Example Usage**:

```bash
# cURL
curl http://localhost:8000/api/shadow-mode/stats | jq

# Python
import requests

response = requests.get("http://localhost:8000/api/shadow-mode/stats")
stats = response.json()

print(f"Total decisions: {stats['total_decisions']}")
print(f"Agreement rate: {stats['decision_agreement_rate']:.2f}%")
print(f"Disagreements: {len(stats['disagreement_cases'])}")
```

---

## Monitoring

### GET /health

System health check including LLM provider status, memory store, and SOP knowledge base.

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
    "total_incidents": 147,
    "collection_status": "ok"
  },
  "sop_kb": {
    "total_sops": 12,
    "collection_status": "ok"
  }
}
```

**Response Fields**:
- `status`: Overall system status (healthy | degraded | unhealthy)
- `providers`: Status of each LLM provider (available | unavailable)
- `active_provider`: Currently active provider (groq | gemini | ollama | rule_engine)
- `memory_store`: Memory store status and incident count
- `sop_kb`: SOP knowledge base status and SOP count

**Status Values**:
- `healthy`: All systems operational
- `degraded`: Some components unavailable but system functional
- `unhealthy`: Critical components failed

**Example Usage**:

```bash
# cURL
curl http://localhost:8000/health | jq

# Python
import requests

response = requests.get("http://localhost:8000/health")
health = response.json()

print(f"Status: {health['status']}")
print(f"Active provider: {health['active_provider']}")
print(f"Total incidents: {health['memory_store']['total_incidents']}")
```

---

### GET /api/logs/decision/{request_id}

Get all logs for a specific request_id including LLM decision, RAG retrievals, safety overrides, and feedback.

**Path Parameters**:
- `request_id`: Request identifier from triage response

**Response 200**:
```json
{
  "request_id": "req_a3f7c9d2e1b4",
  "llm_decision": {
    "timestamp": "2026-04-07T10:30:00Z",
    "provider": "groq",
    "prompt_tokens": 1234,
    "completion_tokens": 456,
    "latency_ms": 1823,
    "decision": "diagnose",
    "diagnosis": "Azure VM agent has stopped reporting..."
  },
  "rag_retrievals": [
    {
      "timestamp": "2026-04-07T10:30:00Z",
      "query_type": "similar_incidents",
      "top_k": 5,
      "results_found": 3,
      "latency_ms": 234
    },
    {
      "timestamp": "2026-04-07T10:30:00Z",
      "query_type": "relevant_sops",
      "top_k": 3,
      "results_found": 2,
      "latency_ms": 187
    }
  ],
  "safety_overrides": [],
  "feedback": []
}
```

**Response 404 (Not Found)**:
```json
{
  "error": "No logs found for this request_id",
  "request_id": "req_nonexistent"
}
```

**Example Usage**:

```bash
# cURL
curl http://localhost:8000/api/logs/decision/req_a3f7c9d2e1b4 | jq

# Python
import requests

response = requests.get(
    "http://localhost:8000/api/logs/decision/req_a3f7c9d2e1b4"
)

logs = response.json()
print(f"LLM provider: {logs['llm_decision']['provider']}")
print(f"Latency: {logs['llm_decision']['latency_ms']}ms")
```

---

## Agent Control

### POST /api/agent/start

Start agent scheduler for automated telemetry collection.

**Request Body**:
```json
{
  "vm_name": "prod-web-001",
  "resource_group": "prod-rg",
  "subscription_id": "12345678-1234-1234-1234-123456789012",
  "workspace_id": "workspace-id-here",
  "interval_seconds": 300
}
```

**Response 200**:
```json
{
  "message": "Agent started successfully"
}
```

**Response 400 (Already Running)**:
```json
{
  "error": "Agent is already running"
}
```

---

### POST /api/agent/stop

Stop running agent scheduler.

**Response 200**:
```json
{
  "message": "Agent stopped successfully"
}
```

**Response 400 (Not Running)**:
```json
{
  "error": "Agent is not running"
}
```

---

### GET /api/agent/status

Get agent running status and configuration.

**Response 200**:
```json
{
  "running": true,
  "config": {
    "vm_name": "prod-web-001",
    "resource_group": "prod-rg",
    "subscription_id": "12345678-1234-1234-1234-123456789012",
    "interval_seconds": 300
  },
  "last_run": "2026-04-07T10:30:00Z"
}
```

---

### POST /api/agent/scan-now

Trigger one collection cycle immediately.

**Response 200**:
```json
{
  "message": "Scan triggered successfully"
}
```

**Response 400 (Agent Not Running)**:
```json
{
  "error": "Agent is not running. Start agent first."
}
```

---

## Dashboard Data

### GET /api/status

Get latest VM status from results/output.jsonl.

**Response 200**: Returns the latest diagnostic output record.

**Response 404**:
```json
{
  "error": "No results found. Run agent first."
}
```

---

### GET /api/feed

Get last N rows from results/output.jsonl with optional decision filter.

**Query Parameters**:
- `decision` (optional): Filter by decision state (diagnose | diagnose_low_confidence | abstain_request_next_check)
- `limit` (optional, default: 50): Maximum number of rows to return

**Response 200**: Returns array of diagnostic output records.

**Example Usage**:

```bash
# Get last 50 records
curl http://localhost:8000/api/feed | jq

# Get last 20 diagnose decisions
curl "http://localhost:8000/api/feed?decision=diagnose&limit=20" | jq
```

---

## Error Handling

All endpoints follow consistent error response format:

**Validation Error (400/422)**:
```json
{
  "error": "Error type",
  "details": [...]
}
```

**Not Found (404)**:
```json
{
  "error": "Resource not found",
  "resource_id": "..."
}
```

**Server Error (500)**:
```json
{
  "detail": "Internal server error message"
}
```

## Rate Limiting

No rate limiting is enforced by the API server. However, LLM providers have their own limits:

- **Groq**: 30 requests/minute (free tier)
- **Gemini**: 1500 requests/day (free tier)
- **Ollama**: Unlimited (local)

## CORS

CORS is not configured by default. For production deployment with web clients, configure CORS middleware in `ui/app.py`.

## WebSocket Support

Not currently supported. All endpoints are HTTP REST.

## Versioning

API version: 1.0.0

No versioning scheme currently implemented. Breaking changes will be documented in release notes.

## Support

For API issues:

1. Check health endpoint: `GET /health`
2. Review logs: `logs/llm_decisions.jsonl`, `logs/rag_retrievals.jsonl`
3. Consult [Troubleshooting Guide](../TROUBLESHOOTING.md)
4. See [LLM Setup Guide](llm_setup.md) for provider configuration

## Related Documentation

- [LLM Setup Guide](llm_setup.md) - Configure LLM providers
- [Shadow Mode Guide](shadow_mode_guide.md) - Validate LLM accuracy
- [Feedback API](feedback_api.md) - Detailed feedback loop documentation
- [Migration Guide](migration_to_llm.md) - Migrate from rule-based to LLM engine
