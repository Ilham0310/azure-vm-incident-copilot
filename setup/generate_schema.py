"""
Generate Azure VM triage schema with 30+ telemetry field definitions.

This module creates a JSON Schema that defines:
- All 30+ telemetry field definitions
- Enum constraints for 8 enum types
- Numeric range constraints
- Required fields: power_state, provisioning_state, resource_health_status
"""

import json
import os
from typing import Dict


def generate_triage_schema() -> Dict:
    """
    Generates the Azure VM triage schema with 30+ field definitions.
    
    Returns:
        Dictionary representing JSON Schema with:
        - All 30+ telemetry field definitions
        - Enum constraints for 8 enum types
        - Numeric range constraints
        - Required fields: power_state, provisioning_state, resource_health_status
    """
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "Azure VM Triage Telemetry Input",
        "description": "Schema for Azure VM incident telemetry with 30+ signal fields",
        "type": "object",
        "required": ["power_state", "provisioning_state", "resource_health_status"],
        "properties": {
            # Power and provisioning state (required)
            "power_state": {
                "type": "string",
                "enum": ["Running", "Stopped", "Deallocated", "Failed", "Unknown"],
                "description": "VM power state"
            },
            "provisioning_state": {
                "type": "string",
                "enum": ["Succeeded", "Failed", "In Progress", "Unknown"],
                "description": "VM provisioning state"
            },
            "resource_health_status": {
                "type": "string",
                "enum": ["Available", "Degraded", "Unavailable", "Unknown"],
                "description": "Azure resource health status"
            },
            
            # Resource health annotation
            "resource_health_annotation": {
                "type": ["string", "null"],
                "description": "Resource health annotation text (may contain platform event keywords)"
            },
            
            # Heartbeat signals
            "heartbeat_present": {
                "type": ["boolean", "null"],
                "description": "Whether VM heartbeat is present"
            },
            "heartbeat_last_received": {
                "type": ["string", "null"],
                "format": "date-time",
                "description": "Timestamp of last heartbeat (ISO 8601 format)"
            },
            
            # Boot diagnostics
            "boot_diagnostics_status": {
                "type": ["string", "null"],
                "enum": ["Normal", "BSOD", "KernelPanic", "Stuck", "Unknown", None],
                "description": "Boot diagnostics status"
            },
            "boot_diagnostics_error": {
                "type": ["string", "null"],
                "description": "Boot diagnostics error message"
            },
            
            # Azure VM agent
            "azure_vm_agent_status": {
                "type": ["string", "null"],
                "enum": ["Healthy", "Degraded", "NotReporting", "Failed", "Unknown", None],
                "description": "Azure VM agent status"
            },
            
            # CPU metrics
            "cpu_percent": {
                "type": ["number", "null"],
                "minimum": 0,
                "maximum": 100,
                "description": "CPU utilization percentage"
            },
            
            # Memory metrics
            "memory_available_mb": {
                "type": ["number", "null"],
                "minimum": 0,
                "description": "Available memory in megabytes"
            },
            "memory_percent": {
                "type": ["number", "null"],
                "minimum": 0,
                "maximum": 100,
                "description": "Memory utilization percentage"
            },
            
            # Disk metrics
            "os_disk_latency_ms": {
                "type": ["number", "null"],
                "minimum": 0,
                "description": "OS disk latency in milliseconds"
            },
            "data_disk_latency_ms": {
                "type": ["number", "null"],
                "minimum": 0,
                "description": "Data disk latency in milliseconds"
            },
            "os_disk_percent_full": {
                "type": ["number", "null"],
                "minimum": 0,
                "maximum": 100,
                "description": "OS disk usage percentage"
            },
            
            # Application health
            "app_health_status": {
                "type": ["string", "null"],
                "enum": ["Healthy", "Degraded", "Unhealthy", "Unknown", None],
                "description": "Application health status"
            },
            "app_error_message": {
                "type": ["string", "null"],
                "description": "Application error message"
            },
            
            # Network Security Group (NSG) rules
            "nsg_allow_rdp_3389": {
                "type": ["boolean", "null"],
                "description": "Whether NSG allows RDP on port 3389"
            },
            "nsg_allow_ssh_22": {
                "type": ["boolean", "null"],
                "description": "Whether NSG allows SSH on port 22"
            },
            
            # Connection troubleshoot results
            "connection_troubleshoot_rdp": {
                "type": ["string", "null"],
                "enum": ["Allow", "Deny", "Inconclusive", "Timeout", "Unknown", None],
                "description": "Connection troubleshoot result for RDP"
            },
            "connection_troubleshoot_ssh": {
                "type": ["string", "null"],
                "enum": ["Allow", "Deny", "Inconclusive", "Timeout", "Unknown", None],
                "description": "Connection troubleshoot result for SSH"
            },
            "connection_troubleshoot_verdict": {
                "type": ["string", "null"],
                "description": "Connection troubleshoot verdict text"
            },
            
            # Monitor agent
            "monitor_agent_status": {
                "type": ["string", "null"],
                "enum": ["Healthy", "Degraded", "Failed", "NotInstalled", "Unknown", None],
                "description": "Monitoring agent status"
            },
            
            # SSL certificate monitoring
            "ssl_cert_days_remaining": {
                "type": ["integer", "null"],
                "minimum": 0,
                "description": "Days remaining until SSL certificate expiry"
            },
            
            # Backup monitoring
            "last_backup_status": {
                "type": ["string", "null"],
                "enum": ["Completed", "Failed", "Warning", "InProgress", "Unknown", None],
                "description": "Last backup job status"
            },
            "last_backup_time": {
                "type": ["string", "null"],
                "format": "date-time",
                "description": "Timestamp of last backup job (ISO 8601 format)"
            },
            
            # Data completeness metadata
            "data_completeness_percent": {
                "type": ["number", "null"],
                "minimum": 0,
                "maximum": 100,
                "description": "Percentage of telemetry fields populated"
            },
            "missing_signals": {
                "type": ["array", "null"],
                "items": {"type": "string"},
                "description": "List of missing telemetry signal names"
            }
        },
        "additionalProperties": True  # Allow unknown fields for forward compatibility
    }
    
    return schema


def write_schema_file(schema: Dict, output_path: str = "schemas/azure_vm_triage_schema.json"):
    """
    Writes schema to file if it doesn't already exist (idempotent).
    
    Args:
        schema: Schema dictionary
        output_path: Target file path
    """
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Check if file already exists
    if os.path.exists(output_path):
        print(f"  File already exists, skipping: {output_path}")
        return
    
    # Write schema to file
    with open(output_path, 'w') as f:
        json.dump(schema, f, indent=2)
    
    print(f"  Created: {output_path}")


if __name__ == "__main__":
    schema = generate_triage_schema()
    write_schema_file(schema)
    print("Triage schema generated successfully!")
