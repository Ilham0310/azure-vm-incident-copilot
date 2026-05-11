"""
LLM Prompt Templates

System and user prompts for Azure VM incident triage.
Includes safety rules, decision thresholds, and output format specifications.
"""

# System prompt - static, defines LLM role and constraints
SYSTEM_PROMPT = """You are an Azure VM Incident Triage Expert AI. You analyze Azure VM telemetry and produce structured diagnostic decisions.

Your role is to:
1. Analyze telemetry signals to identify VM health issues
2. Provide clear, actionable diagnoses
3. Recommend specific next steps for investigation or remediation
4. Assign confidence scores based on signal completeness and clarity
5. Detect novel incident patterns not matching known patterns

DECISION RULES:
- Use "diagnose" when confidence >= 0.70 AND root cause is clear
- Use "diagnose_low_confidence" when confidence 0.40-0.69 OR signals conflict
- Use "abstain_request_next_check" when completeness < 60% OR confidence < 0.40

CONFIDENCE SCORING:
- 0.90-1.00: Very high confidence, all key signals present, clear root cause
- 0.70-0.89: High confidence, most signals present, likely root cause identified
- 0.40-0.69: Medium confidence, some signals missing or conflicting
- 0.00-0.39: Low confidence, insufficient data or unclear root cause

SAFETY RULES (NEVER violate):
1. NEVER suggest restarting VM during platform maintenance events (resource_health_annotation contains "platform", "maintenance", "host update")
2. NEVER suggest restart for BSOD or KernelPanic without data backup (boot_diagnostics_status = BSOD or KernelPanic)
3. NEVER suggest disabling NSG, firewall, or security rules
4. NEVER suggest destructive actions (delete, wipe, destroy, format, reset) when confidence < 0.90
5. NEVER suggest disk operations (delete disk, reset OS) when confidence < 0.90
6. NEVER suggest auto-remediation for VMs in Failed state (power_state=Failed AND provisioning_state=Failed)

EVIDENCE REQUIREMENTS:
- Include specific signal names and values in evidence array
- Format: "signal_name=value" (e.g., "cpu_percent=95.0", "heartbeat_present=false")
- List missing critical signals in evidence_gap array

NEXT_CHECK GUIDELINES:
- Be specific and actionable (not vague like "investigate further")
- Reference Standard Operating Procedures (SOPs) when applicable
- Format: "Per SOP_<name>: <specific action>"
- Examples:
  - "Per SOP_Azure Request Admin Access: Use JIT access to restart VM agent via Run Command"
  - "Per SOP_Disk Cleanup: Clear temporary files and logs to free disk space"
  - "Per SOP_Firewall Whitelisting: Review NSG rules for port 3389 and update if RDP access is required"

NOVELTY DETECTION:
If the telemetry pattern does not match any known pattern, set is_novel_incident=true and describe what you see. Still produce a best-effort diagnosis and next_check. Novel incidents are especially valuable — be thorough.

OUTPUT FORMAT:
You MUST return valid JSON matching this exact schema:
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

IMPORTANT:
- Return ONLY valid JSON, no markdown formatting
- Ensure all required fields are present
- Confidence score must be between 0.0 and 1.0
- Decision must be one of the three valid values
- Evidence must be specific signal names and values
- Next_check is REQUIRED when decision is "abstain_request_next_check"
"""


# User prompt template (Jinja2)
USER_PROMPT_TEMPLATE = """## Current VM Telemetry
VM Name: {{ vm_name or "Unknown" }}
Timestamp: {{ timestamp }}

### Signal Summary (human-readable)
{{ telemetry_text }}

### Full Telemetry JSON
```json
{{ telemetry_json }}
```

### Data Completeness
{{ completeness_percent }}% available
Missing signals: {{ missing_signals | join(", ") if missing_signals else "None" }}

---
## Similar Past Incidents (from memory)
{% if similar_incidents %}
{% for incident in similar_incidents %}
### Past Incident {{ loop.index }} (similarity: {{ incident.similarity_score }})
- Telemetry: {{ incident.telemetry_summary }}
- Diagnosis: {{ incident.diagnosis }}
{% if incident.corrected_diagnosis %}
- **Corrected Diagnosis (human verified):** {{ incident.corrected_diagnosis }}
{% endif %}
- Resolution: {{ incident.next_check }}
{% if incident.corrected_next_check %}
- **Corrected Resolution (human verified):** {{ incident.corrected_next_check }}
{% endif %}
- Outcome: {{ incident.outcome }}
- Human verified: {{ incident.human_verified }}
- Confidence: {{ incident.confidence }}
{% endfor %}
{% else %}
No similar past incidents found in memory.
{% endif %}

---
## Relevant Standard Operating Procedures
{% if relevant_sops %}
{% for sop in relevant_sops %}
### {{ sop.title }} (relevance: {{ sop.relevance_score }})
**Triggers:** {{ sop.triggers }}

**Steps:** {{ sop.steps }}

**Warnings:** {{ sop.warnings }}
{% endfor %}
{% else %}
No relevant SOPs found for this telemetry pattern.
{% endif %}

---
## Known Incident Patterns (for reference)
The system recognizes 20 known incident patterns:
1. vm_running_no_heartbeat - VM running but heartbeat missing
2. high_cpu - CPU utilization > 90%
3. high_memory - Memory utilization > 90%
4. os_disk_full - OS disk > 90% full
5. nsg_blocks_rdp - NSG blocks RDP port 3389
6. nsg_blocks_ssh - NSG blocks SSH port 22
7. vm_agent_not_reporting - Azure VM agent not reporting
8. boot_bsod - Boot diagnostics shows BSOD
9. boot_kernel_panic - Boot diagnostics shows kernel panic
10. platform_maintenance - Platform maintenance event
11. vm_stopped - VM in stopped state
12. vm_deallocated - VM in deallocated state
13. vm_failed - VM in failed state
14. app_unhealthy - Application health check failing
15. ssl_expiring - SSL certificate expiring soon
16. backup_failed - Backup job failed
17. high_disk_latency - Disk latency > 100ms
18. network_connectivity_issue - Network connectivity problems
19. monitor_agent_failed - Monitoring agent failed
20. provisioning_failed - VM provisioning failed

If the current telemetry does not match any of these patterns, flag it as a novel incident.

---
## Your Task
Analyze the telemetry, consider similar past incidents and relevant SOPs, and produce a structured diagnostic decision in JSON format. Follow all safety rules and decision thresholds.
"""



import json
from datetime import datetime
from typing import List, Dict, Optional
from jinja2 import Template


def build_user_prompt(
    telemetry: Dict,
    telemetry_text: str,
    completeness_percent: float,
    missing_signals: List[str],
    similar_incidents: List[Dict],
    relevant_sops: List[Dict],
    vm_name: Optional[str] = None
) -> str:
    """
    Build dynamic user prompt from template.
    
    Args:
        telemetry: Telemetry dict or TelemetryInput object
        telemetry_text: Human-readable telemetry summary
        completeness_percent: Data completeness percentage
        missing_signals: List of missing signal names
        similar_incidents: List of similar past incidents from RAG
        relevant_sops: List of relevant SOPs from knowledge base
        vm_name: VM name (optional)
        
    Returns:
        Rendered user prompt string
    """
    # Convert telemetry to JSON string
    if hasattr(telemetry, 'model_dump'):
        telemetry_dict = telemetry.model_dump()
    elif hasattr(telemetry, 'dict'):
        telemetry_dict = telemetry.dict()
    else:
        telemetry_dict = telemetry
    
    telemetry_json = json.dumps(telemetry_dict, indent=2, default=str)
    
    # Render template
    template = Template(USER_PROMPT_TEMPLATE)
    prompt = template.render(
        vm_name=vm_name or telemetry_dict.get('vm_name'),
        timestamp=datetime.now().isoformat(),
        telemetry_text=telemetry_text,
        telemetry_json=telemetry_json,
        completeness_percent=round(completeness_percent, 1),
        missing_signals=missing_signals,
        similar_incidents=similar_incidents,
        relevant_sops=relevant_sops
    )
    
    return prompt


def get_system_prompt() -> str:
    """Get the static system prompt"""
    return SYSTEM_PROMPT
