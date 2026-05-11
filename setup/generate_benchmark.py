"""
Generate benchmark dataset with 38 cases covering all 23 incident patterns.

This module creates a CSV file containing:
- 23 cases: All 23 known incident patterns (one per pattern)
- 5 cases: Clean/healthy VM cases (no issues, all signals green)
- 5 cases: Missing telemetry cases (low completeness < 60%)
- 5 cases: Conflicting signal cases (minor and major conflicts)

Total: 38 benchmark cases
"""

import csv
import json
import os
from typing import List, Dict


def generate_benchmark_cases() -> List[Dict]:
    """
    Generates 38 benchmark cases covering:
    - 23 cases: All 23 known incident patterns (one per pattern)
    - 5 cases: Clean/healthy VM cases (no issues, all signals green)
    - 5 cases: Missing telemetry cases (low completeness < 60%)
    - 5 cases: Conflicting signal cases (minor and major conflicts)
    
    Returns:
        List of 38 benchmark case dictionaries
    """
    cases = []
    
    # Helper function to create baseline healthy telemetry
    def baseline_telemetry():
        """Returns baseline healthy telemetry with all fields populated."""
        return {
            "power_state": "Running",
            "provisioning_state": "Succeeded",
            "resource_health_status": "Available",
            "resource_health_annotation": None,
            "heartbeat_present": True,
            "heartbeat_last_received": "2024-01-15T10:30:00Z",
            "boot_diagnostics_status": "Normal",
            "boot_diagnostics_error": None,
            "azure_vm_agent_status": "Healthy",
            "cpu_percent": 35.0,
            "memory_percent": 42.0,
            "memory_available_mb": 3200.0,
            "os_disk_latency_ms": 8.5,
            "data_disk_latency_ms": 6.2,
            "os_disk_percent_full": 45.0,
            "app_health_status": "Healthy",
            "app_error_message": None,
            "nsg_allow_rdp_3389": True,
            "nsg_allow_ssh_22": True,
            "connection_troubleshoot_rdp": "Allow",
            "connection_troubleshoot_ssh": "Allow",
            "connection_troubleshoot_verdict": "Reachable",
            "monitor_agent_status": "Healthy",
            "ssl_cert_days_remaining": 90,
            "last_backup_status": "Completed",
            "last_backup_time": "2024-01-15T02:00:00Z",
            "data_completeness_percent": 96.7,
            "missing_signals": []
        }
    
    # Pattern 1: VM Stopped by User
    telemetry = baseline_telemetry()
    telemetry["power_state"] = "Stopped"
    cases.append({
        "case_id": "001",
        "case_name": "VM Stopped by User",
        "incident_pattern": "vm_stopped_by_user",
        "telemetry_input": json.dumps(telemetry),
        "expected_decision": "diagnose",
        "expected_diagnosis": "VM Stopped by user deallocation",
        "notes": "Clean stop with successful provisioning"
    })
    
    # Pattern 2: NSG Blocks RDP
    telemetry = baseline_telemetry()
    telemetry["nsg_allow_rdp_3389"] = False
    telemetry["connection_troubleshoot_rdp"] = "Deny"
    cases.append({
        "case_id": "002",
        "case_name": "NSG Blocks RDP",
        "incident_pattern": "nsg_blocks_rdp",
        "telemetry_input": json.dumps(telemetry),
        "expected_decision": "diagnose",
        "expected_diagnosis": "NSG blocks RDP",
        "notes": "Network security group denies RDP access"
    })
    
    # Pattern 3: NSG Blocks SSH
    telemetry = baseline_telemetry()
    telemetry["nsg_allow_ssh_22"] = False
    telemetry["connection_troubleshoot_ssh"] = "Deny"
    cases.append({
        "case_id": "003",
        "case_name": "NSG Blocks SSH",
        "incident_pattern": "nsg_blocks_ssh",
        "telemetry_input": json.dumps(telemetry),
        "expected_decision": "diagnose",
        "expected_diagnosis": "NSG blocks SSH",
        "notes": "Network security group denies SSH access"
    })
    
    # Pattern 4: High CPU Saturation
    telemetry = baseline_telemetry()
    telemetry["cpu_percent"] = 98.5
    telemetry["resource_health_status"] = "Degraded"
    cases.append({
        "case_id": "004",
        "case_name": "High CPU Saturation",
        "incident_pattern": "high_cpu",
        "telemetry_input": json.dumps(telemetry),
        "expected_decision": "diagnose",
        "expected_diagnosis": "High CPU saturation",
        "notes": "CPU at 98.5%, memory normal"
    })
    
    # Pattern 5: OS Disk Full
    telemetry = baseline_telemetry()
    telemetry["os_disk_percent_full"] = 97.0
    telemetry["resource_health_status"] = "Degraded"
    cases.append({
        "case_id": "005",
        "case_name": "OS Disk Full",
        "incident_pattern": "os_disk_full",
        "telemetry_input": json.dumps(telemetry),
        "expected_decision": "diagnose",
        "expected_diagnosis": "OS disk full",
        "notes": "OS disk at 97% capacity"
    })
    
    # Pattern 6: Memory Exhaustion
    telemetry = baseline_telemetry()
    telemetry["memory_percent"] = 98.0
    telemetry["memory_available_mb"] = 100.0
    telemetry["resource_health_status"] = "Degraded"
    cases.append({
        "case_id": "006",
        "case_name": "Memory Exhaustion",
        "incident_pattern": "memory_exhaustion",
        "telemetry_input": json.dumps(telemetry),
        "expected_decision": "diagnose",
        "expected_diagnosis": "Memory exhaustion",
        "notes": "Memory at 98% utilization"
    })
    
    # Pattern 7: Boot BSOD
    telemetry = baseline_telemetry()
    telemetry["boot_diagnostics_status"] = "BSOD"
    telemetry["boot_diagnostics_error"] = "CRITICAL_PROCESS_DIED"
    telemetry["resource_health_status"] = "Unavailable"
    cases.append({
        "case_id": "007",
        "case_name": "Boot BSOD",
        "incident_pattern": "boot_bsod",
        "telemetry_input": json.dumps(telemetry),
        "expected_decision": "diagnose",
        "expected_diagnosis": "Boot BSOD",
        "notes": "Blue screen of death detected"
    })
    
    # Pattern 8: Boot Kernel Panic
    telemetry = baseline_telemetry()
    telemetry["boot_diagnostics_status"] = "KernelPanic"
    telemetry["boot_diagnostics_error"] = "Kernel panic - not syncing"
    telemetry["resource_health_status"] = "Unavailable"
    cases.append({
        "case_id": "008",
        "case_name": "Boot Kernel Panic",
        "incident_pattern": "boot_kernel_panic",
        "telemetry_input": json.dumps(telemetry),
        "expected_decision": "diagnose",
        "expected_diagnosis": "Boot kernel panic",
        "notes": "Linux kernel panic detected"
    })
    
    # Pattern 9: VM Running No Heartbeat
    telemetry = baseline_telemetry()
    telemetry["heartbeat_present"] = False
    telemetry["azure_vm_agent_status"] = "NotReporting"
    telemetry["resource_health_status"] = "Degraded"
    cases.append({
        "case_id": "009",
        "case_name": "VM Running No Heartbeat",
        "incident_pattern": "vm_running_no_heartbeat",
        "telemetry_input": json.dumps(telemetry),
        "expected_decision": "diagnose_low_confidence",
        "expected_diagnosis": "VM running but no heartbeat",
        "notes": "VM agent not reporting"
    })
    
    # Pattern 10: Resource Health Unavailable
    telemetry = baseline_telemetry()
    telemetry["resource_health_status"] = "Unavailable"
    cases.append({
        "case_id": "010",
        "case_name": "Resource Health Unavailable",
        "incident_pattern": "resource_health_unavailable",
        "telemetry_input": json.dumps(telemetry),
        "expected_decision": "diagnose_low_confidence",
        "expected_diagnosis": "Resource health unavailable with normal metrics",
        "notes": "Health unavailable but metrics normal"
    })
    
    # Pattern 11: Conflicting NSG Signals
    telemetry = baseline_telemetry()
    telemetry["nsg_allow_rdp_3389"] = False
    telemetry["connection_troubleshoot_rdp"] = "Allow"
    cases.append({
        "case_id": "011",
        "case_name": "Conflicting NSG Signals",
        "incident_pattern": "conflicting_nsg_signals",
        "telemetry_input": json.dumps(telemetry),
        "expected_decision": "diagnose_low_confidence",
        "expected_diagnosis": "Conflicting NSG and connection troubleshoot signals",
        "notes": "NSG denies but troubleshoot allows"
    })
    
    # Pattern 12: App Unhealthy VM Healthy
    telemetry = baseline_telemetry()
    telemetry["app_health_status"] = "Unhealthy"
    telemetry["app_error_message"] = "Service unavailable"
    cases.append({
        "case_id": "012",
        "case_name": "App Unhealthy VM Healthy",
        "incident_pattern": "app_unhealthy_vm_healthy",
        "telemetry_input": json.dumps(telemetry),
        "expected_decision": "diagnose",
        "expected_diagnosis": "Application unhealthy with healthy VM",
        "notes": "App layer issue, VM infrastructure healthy"
    })
    
    # Pattern 13: Disk IO Saturation
    telemetry = baseline_telemetry()
    telemetry["os_disk_latency_ms"] = 250.0
    telemetry["data_disk_latency_ms"] = 180.0
    telemetry["resource_health_status"] = "Degraded"
    cases.append({
        "case_id": "013",
        "case_name": "Disk IO Saturation",
        "incident_pattern": "disk_io_saturation",
        "telemetry_input": json.dumps(telemetry),
        "expected_decision": "diagnose",
        "expected_diagnosis": "Disk IO saturation",
        "notes": "High disk latency on both OS and data disks"
    })
    
    # Pattern 14: VM Deallocated
    telemetry = baseline_telemetry()
    telemetry["power_state"] = "Deallocated"
    cases.append({
        "case_id": "014",
        "case_name": "VM Deallocated",
        "incident_pattern": "vm_deallocated",
        "telemetry_input": json.dumps(telemetry),
        "expected_decision": "diagnose",
        "expected_diagnosis": "Deallocated VM",
        "notes": "VM fully deallocated"
    })
    
    # Pattern 15: Provisioning Failed
    telemetry = baseline_telemetry()
    telemetry["power_state"] = "Failed"
    telemetry["provisioning_state"] = "Failed"
    telemetry["resource_health_status"] = "Unavailable"
    cases.append({
        "case_id": "015",
        "case_name": "Provisioning Failed",
        "incident_pattern": "provisioning_failed",
        "telemetry_input": json.dumps(telemetry),
        "expected_decision": "diagnose_low_confidence",
        "expected_diagnosis": "Provisioning failed",
        "notes": "VM provisioning failed"
    })
    
    # Pattern 16: Failed State Insufficient Data
    cases.append({
        "case_id": "016",
        "case_name": "Failed State Insufficient Data",
        "incident_pattern": "failed_state_insufficient_data",
        "telemetry_input": json.dumps({
            "power_state": "Failed",
            "provisioning_state": "Succeeded",
            "resource_health_status": "Unavailable",
            "data_completeness_percent": 10.0,
            "missing_signals": ["heartbeat_present", "boot_diagnostics_status", "azure_vm_agent_status", 
                               "cpu_percent", "memory_percent", "os_disk_latency_ms", "os_disk_percent_full",
                               "app_health_status", "nsg_allow_rdp_3389", "nsg_allow_ssh_22", 
                               "connection_troubleshoot_rdp", "connection_troubleshoot_ssh", 
                               "monitor_agent_status", "memory_available_mb", "data_disk_latency_ms",
                               "heartbeat_last_received", "boot_diagnostics_error", "app_error_message",
                               "connection_troubleshoot_verdict", "resource_health_annotation"]
        }),
        "expected_decision": "abstain_request_next_check",
        "expected_diagnosis": "Failed state with insufficient data",
        "notes": "Very low data completeness"
    })
    
    # Pattern 17: Platform Degradation
    telemetry = baseline_telemetry()
    telemetry["resource_health_status"] = "Degraded"
    telemetry["resource_health_annotation"] = "Platform maintenance in progress - host update"
    cases.append({
        "case_id": "017",
        "case_name": "Platform Degradation",
        "incident_pattern": "platform_degradation",
        "telemetry_input": json.dumps(telemetry),
        "expected_decision": "abstain_request_next_check",
        "expected_diagnosis": "Platform degradation event",
        "notes": "Platform-initiated maintenance"
    })
    
    # Pattern 18: Boot Stuck
    telemetry = baseline_telemetry()
    telemetry["boot_diagnostics_status"] = "Stuck"
    telemetry["boot_diagnostics_error"] = "Boot process stuck at startup"
    telemetry["resource_health_status"] = "Unavailable"
    cases.append({
        "case_id": "018",
        "case_name": "Boot Stuck",
        "incident_pattern": "boot_stuck",
        "telemetry_input": json.dumps(telemetry),
        "expected_decision": "diagnose",
        "expected_diagnosis": "Boot stuck at startup",
        "notes": "Boot process not completing"
    })
    
    # Pattern 19: VM Agent Failed
    telemetry = baseline_telemetry()
    telemetry["azure_vm_agent_status"] = "Failed"
    telemetry["resource_health_status"] = "Degraded"
    cases.append({
        "case_id": "019",
        "case_name": "VM Agent Failed",
        "incident_pattern": "vm_agent_failed",
        "telemetry_input": json.dumps(telemetry),
        "expected_decision": "diagnose_low_confidence",
        "expected_diagnosis": "Azure VM agent failure",
        "notes": "VM agent in failed state"
    })
    
    # Pattern 20: Monitor Agent Failed
    telemetry = baseline_telemetry()
    telemetry["monitor_agent_status"] = "Failed"
    cases.append({
        "case_id": "020",
        "case_name": "Monitor Agent Failed",
        "incident_pattern": "monitor_agent_failed",
        "telemetry_input": json.dumps(telemetry),
        "expected_decision": "diagnose_low_confidence",
        "expected_diagnosis": "Monitoring agent failure",
        "notes": "Monitor agent not functioning"
    })
    
    # Clean cases (5 cases) - All fields populated with healthy values
    telemetry = baseline_telemetry()
    telemetry["data_completeness_percent"] = 100.0
    cases.append({
        "case_id": "021",
        "case_name": "Healthy VM - All Green",
        "incident_pattern": "clean",
        "telemetry_input": json.dumps(telemetry),
        "expected_decision": "diagnose",
        "expected_diagnosis": "VM healthy - no issues detected",
        "notes": "All signals green"
    })
    
    telemetry = baseline_telemetry()
    telemetry["cpu_percent"] = 25.0
    telemetry["memory_percent"] = 40.0
    telemetry["data_completeness_percent"] = 100.0
    cases.append({
        "case_id": "022",
        "case_name": "Healthy VM - Low Load",
        "incident_pattern": "clean",
        "telemetry_input": json.dumps(telemetry),
        "expected_decision": "diagnose",
        "expected_diagnosis": "VM healthy - no issues detected",
        "notes": "Low resource utilization, all healthy"
    })
    
    telemetry = baseline_telemetry()
    telemetry["cpu_percent"] = 55.0
    telemetry["memory_percent"] = 60.0
    telemetry["os_disk_percent_full"] = 65.0
    telemetry["data_completeness_percent"] = 100.0
    cases.append({
        "case_id": "023",
        "case_name": "Healthy VM - Normal Load",
        "incident_pattern": "clean",
        "telemetry_input": json.dumps(telemetry),
        "expected_decision": "diagnose",
        "expected_diagnosis": "VM healthy - normal load",
        "notes": "Moderate resource usage, all healthy"
    })
    
    telemetry = baseline_telemetry()
    telemetry["cpu_percent"] = 85.0
    telemetry["memory_percent"] = 80.0
    telemetry["os_disk_percent_full"] = 75.0
    telemetry["data_completeness_percent"] = 100.0
    cases.append({
        "case_id": "024",
        "case_name": "Healthy VM - High Load But Stable",
        "incident_pattern": "clean",
        "telemetry_input": json.dumps(telemetry),
        "expected_decision": "diagnose",
        "expected_diagnosis": "VM healthy - high load but stable",
        "notes": "High but not critical resource usage"
    })
    
    telemetry = baseline_telemetry()
    telemetry["heartbeat_last_received"] = "2024-01-15T10:29:45Z"
    telemetry["data_completeness_percent"] = 100.0
    cases.append({
        "case_id": "025",
        "case_name": "Healthy VM - Recently Started",
        "incident_pattern": "clean",
        "telemetry_input": json.dumps(telemetry),
        "expected_decision": "diagnose",
        "expected_diagnosis": "VM healthy - recently started",
        "notes": "VM just started, all systems healthy"
    })
    
    # Missing telemetry cases (5 cases) - Only 3 required fields
    cases.append({
        "case_id": "026",
        "case_name": "Missing Telemetry - Low Completeness",
        "incident_pattern": "missing_telemetry",
        "telemetry_input": json.dumps({
            "power_state": "Running",
            "provisioning_state": "Succeeded",
            "resource_health_status": "Unknown",
            "data_completeness_percent": 10.0,
            "missing_signals": ["heartbeat_present", "heartbeat_last_received", "boot_diagnostics_status", 
                               "boot_diagnostics_error", "azure_vm_agent_status", "cpu_percent", "memory_percent",
                               "memory_available_mb", "os_disk_latency_ms", "data_disk_latency_ms",
                               "os_disk_percent_full", "app_health_status", "app_error_message",
                               "nsg_allow_rdp_3389", "nsg_allow_ssh_22", "connection_troubleshoot_rdp",
                               "connection_troubleshoot_ssh", "connection_troubleshoot_verdict",
                               "monitor_agent_status", "resource_health_annotation"]
        }),
        "expected_decision": "abstain_request_next_check",
        "expected_diagnosis": "Insufficient telemetry data",
        "notes": "Only 10% completeness"
    })
    
    cases.append({
        "case_id": "027",
        "case_name": "Missing Telemetry - No Metrics",
        "incident_pattern": "missing_telemetry",
        "telemetry_input": json.dumps({
            "power_state": "Running",
            "provisioning_state": "Succeeded",
            "resource_health_status": "Available",
            "data_completeness_percent": 10.0,
            "missing_signals": ["heartbeat_present", "heartbeat_last_received", "boot_diagnostics_status",
                               "boot_diagnostics_error", "azure_vm_agent_status", "cpu_percent", "memory_percent",
                               "memory_available_mb", "os_disk_latency_ms", "data_disk_latency_ms",
                               "os_disk_percent_full", "app_health_status", "app_error_message",
                               "nsg_allow_rdp_3389", "nsg_allow_ssh_22", "connection_troubleshoot_rdp",
                               "connection_troubleshoot_ssh", "connection_troubleshoot_verdict",
                               "monitor_agent_status", "resource_health_annotation"]
        }),
        "expected_decision": "abstain_request_next_check",
        "expected_diagnosis": "Missing performance metrics",
        "notes": "No performance metrics available"
    })
    
    cases.append({
        "case_id": "028",
        "case_name": "Missing Telemetry - No Agent Data",
        "incident_pattern": "missing_telemetry",
        "telemetry_input": json.dumps({
            "power_state": "Running",
            "provisioning_state": "Succeeded",
            "resource_health_status": "Available",
            "data_completeness_percent": 10.0,
            "missing_signals": ["heartbeat_present", "heartbeat_last_received", "boot_diagnostics_status",
                               "boot_diagnostics_error", "azure_vm_agent_status", "cpu_percent", "memory_percent",
                               "memory_available_mb", "os_disk_latency_ms", "data_disk_latency_ms",
                               "os_disk_percent_full", "app_health_status", "app_error_message",
                               "nsg_allow_rdp_3389", "nsg_allow_ssh_22", "connection_troubleshoot_rdp",
                               "connection_troubleshoot_ssh", "connection_troubleshoot_verdict",
                               "monitor_agent_status", "resource_health_annotation"]
        }),
        "expected_decision": "abstain_request_next_check",
        "expected_diagnosis": "Missing agent telemetry",
        "notes": "No agent status data"
    })
    
    cases.append({
        "case_id": "029",
        "case_name": "Missing Telemetry - Critical Signals Unknown",
        "incident_pattern": "missing_telemetry",
        "telemetry_input": json.dumps({
            "power_state": "Unknown",
            "provisioning_state": "Unknown",
            "resource_health_status": "Unknown",
            "data_completeness_percent": 10.0,
            "missing_signals": ["heartbeat_present", "heartbeat_last_received", "boot_diagnostics_status",
                               "boot_diagnostics_error", "azure_vm_agent_status", "cpu_percent", "memory_percent",
                               "memory_available_mb", "os_disk_latency_ms", "data_disk_latency_ms",
                               "os_disk_percent_full", "app_health_status", "app_error_message",
                               "nsg_allow_rdp_3389", "nsg_allow_ssh_22", "connection_troubleshoot_rdp",
                               "connection_troubleshoot_ssh", "connection_troubleshoot_verdict",
                               "monitor_agent_status", "resource_health_annotation"]
        }),
        "expected_decision": "abstain_request_next_check",
        "expected_diagnosis": "Critical signals missing",
        "notes": "All critical signals unknown"
    })
    
    cases.append({
        "case_id": "030",
        "case_name": "Missing Telemetry - Partial Boot Data",
        "incident_pattern": "missing_telemetry",
        "telemetry_input": json.dumps({
            "power_state": "Running",
            "provisioning_state": "Succeeded",
            "resource_health_status": "Degraded",
            "data_completeness_percent": 10.0,
            "missing_signals": ["heartbeat_present", "heartbeat_last_received", "boot_diagnostics_status",
                               "boot_diagnostics_error", "azure_vm_agent_status", "cpu_percent", "memory_percent",
                               "memory_available_mb", "os_disk_latency_ms", "data_disk_latency_ms",
                               "os_disk_percent_full", "app_health_status", "app_error_message",
                               "nsg_allow_rdp_3389", "nsg_allow_ssh_22", "connection_troubleshoot_rdp",
                               "connection_troubleshoot_ssh", "connection_troubleshoot_verdict",
                               "monitor_agent_status", "resource_health_annotation"]
        }),
        "expected_decision": "abstain_request_next_check",
        "expected_diagnosis": "Missing boot diagnostics data",
        "notes": "Boot diagnostics not available"
    })
    
    # Conflicting signal cases (5 cases)
    # Case 031: Major conflict - stopped VM with high CPU (abstain)
    cases.append({
        "case_id": "031",
        "case_name": "Conflicting Signals - Power vs Metrics",
        "incident_pattern": "conflicting_signals",
        "telemetry_input": json.dumps({
            "power_state": "Stopped",
            "provisioning_state": "Succeeded",
            "resource_health_status": "Available",
            "cpu_percent": 95.0,
            "memory_percent": 85.0,
            "data_completeness_percent": 10.0,
            "missing_signals": ["heartbeat_present", "heartbeat_last_received", "boot_diagnostics_status",
                               "boot_diagnostics_error", "azure_vm_agent_status", "memory_available_mb",
                               "os_disk_latency_ms", "data_disk_latency_ms", "os_disk_percent_full",
                               "app_health_status", "app_error_message", "nsg_allow_rdp_3389",
                               "nsg_allow_ssh_22", "connection_troubleshoot_rdp", "connection_troubleshoot_ssh",
                               "connection_troubleshoot_verdict", "monitor_agent_status", "resource_health_annotation"]
        }),
        "expected_decision": "abstain_request_next_check",
        "expected_diagnosis": "Conflicting signals: stopped VM with high CPU",
        "notes": "Major conflict: stopped VM reporting high CPU"
    })
    
    # Case 032: Minor conflict - health unavailable but metrics normal (diagnose_low_confidence)
    telemetry = baseline_telemetry()
    telemetry["resource_health_status"] = "Unavailable"
    telemetry["cpu_percent"] = 20.0
    telemetry["memory_percent"] = 25.0
    telemetry["os_disk_latency_ms"] = 5.0
    # Remove some fields to get 60-89% completeness
    del telemetry["app_error_message"]
    del telemetry["boot_diagnostics_error"]
    del telemetry["resource_health_annotation"]
    del telemetry["connection_troubleshoot_verdict"]
    del telemetry["data_disk_latency_ms"]
    telemetry["data_completeness_percent"] = 72.0
    cases.append({
        "case_id": "032",
        "case_name": "Conflicting Signals - Health vs Metrics",
        "incident_pattern": "conflicting_signals",
        "telemetry_input": json.dumps(telemetry),
        "expected_decision": "diagnose_low_confidence",
        "expected_diagnosis": "Resource health unavailable but all metrics normal",
        "notes": "Minor conflict: health unavailable but metrics healthy"
    })
    
    # Case 033: Minor conflict - NSG allows but troubleshoot denies (diagnose_low_confidence)
    telemetry = baseline_telemetry()
    telemetry["nsg_allow_ssh_22"] = True
    telemetry["connection_troubleshoot_ssh"] = "Deny"
    # Remove some fields to get 60-89% completeness
    del telemetry["app_error_message"]
    del telemetry["boot_diagnostics_error"]
    del telemetry["resource_health_annotation"]
    del telemetry["connection_troubleshoot_verdict"]
    del telemetry["data_disk_latency_ms"]
    telemetry["data_completeness_percent"] = 72.0
    cases.append({
        "case_id": "033",
        "case_name": "Conflicting Signals - NSG Mismatch",
        "incident_pattern": "conflicting_signals",
        "telemetry_input": json.dumps(telemetry),
        "expected_decision": "diagnose_low_confidence",
        "expected_diagnosis": "Conflicting network signals",
        "notes": "NSG allows but troubleshoot denies"
    })
    
    # Case 034: Minor conflict - agent healthy but no heartbeat (diagnose_low_confidence)
    telemetry = baseline_telemetry()
    telemetry["heartbeat_present"] = False
    telemetry["azure_vm_agent_status"] = "Healthy"
    # Remove some fields to get 60-89% completeness
    del telemetry["app_error_message"]
    del telemetry["boot_diagnostics_error"]
    del telemetry["resource_health_annotation"]
    del telemetry["connection_troubleshoot_verdict"]
    del telemetry["data_disk_latency_ms"]
    telemetry["data_completeness_percent"] = 72.0
    cases.append({
        "case_id": "034",
        "case_name": "Conflicting Signals - Agent vs Heartbeat",
        "incident_pattern": "conflicting_signals",
        "telemetry_input": json.dumps(telemetry),
        "expected_decision": "diagnose_low_confidence",
        "expected_diagnosis": "Agent healthy but no heartbeat",
        "notes": "Minor conflict: agent reports healthy but no heartbeat"
    })
    
    # Case 035: Minor conflict - app healthy but VM degraded (diagnose_low_confidence)
    telemetry = baseline_telemetry()
    telemetry["resource_health_status"] = "Unavailable"
    telemetry["app_health_status"] = "Healthy"
    telemetry["azure_vm_agent_status"] = "Degraded"
    # Remove some fields to get 60-89% completeness
    del telemetry["app_error_message"]
    del telemetry["boot_diagnostics_error"]
    del telemetry["resource_health_annotation"]
    del telemetry["connection_troubleshoot_verdict"]
    del telemetry["data_disk_latency_ms"]
    telemetry["data_completeness_percent"] = 72.0
    cases.append({
        "case_id": "035",
        "case_name": "Conflicting Signals - App vs VM Health",
        "incident_pattern": "conflicting_signals",
        "telemetry_input": json.dumps(telemetry),
        "expected_decision": "diagnose_low_confidence",
        "expected_diagnosis": "App healthy but VM degraded",
        "notes": "Minor conflict: app healthy but VM infrastructure degraded"
    })
    
    # Pattern 21: SSL Certificate Expiry Warning (5 days - diagnose)
    telemetry = baseline_telemetry()
    telemetry["ssl_cert_days_remaining"] = 5
    cases.append({
        "case_id": "036",
        "case_name": "SSL Certificate Expiring Soon",
        "incident_pattern": "ssl_cert_expiry_warning",
        "telemetry_input": json.dumps(telemetry),
        "expected_decision": "diagnose",
        "expected_diagnosis": "SSL certificate expiring in 5 days",
        "notes": "SSL cert expiring in 5 days - urgent action needed"
    })
    
    # Pattern 22: Azure Backup Job Failure (diagnose)
    telemetry = baseline_telemetry()
    telemetry["last_backup_status"] = "Failed"
    telemetry["last_backup_time"] = "2024-01-15T02:00:00Z"
    cases.append({
        "case_id": "037",
        "case_name": "Azure Backup Job Failed",
        "incident_pattern": "azure_backup_job_failure",
        "telemetry_input": json.dumps(telemetry),
        "expected_decision": "diagnose",
        "expected_diagnosis": "Azure VM backup job failed",
        "notes": "Backup job failed - check Recovery Services Vault"
    })
    
    # Pattern 23: VM Oversized / Rightsize Candidate (diagnose_low_confidence)
    telemetry = baseline_telemetry()
    telemetry["cpu_percent"] = 5.0
    telemetry["memory_percent"] = 15.0
    cases.append({
        "case_id": "038",
        "case_name": "VM Oversized - Rightsize Candidate",
        "incident_pattern": "vm_oversized_rightsize_candidate",
        "telemetry_input": json.dumps(telemetry),
        "expected_decision": "diagnose_low_confidence",
        "expected_diagnosis": "VM over-provisioned. CPU at 5.0%, Memory at 15.0% — rightsize candidate",
        "notes": "VM over-provisioned - needs trend analysis before resizing"
    })
    
    return cases


def write_benchmark_file(cases: List[Dict], output_path: str = "data/benchmark_cases.csv"):
    """
    Writes benchmark cases to CSV if it doesn't already exist (idempotent).
    
    Args:
        cases: List of benchmark case dictionaries
        output_path: Target file path
    """
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Check if file already exists
    if os.path.exists(output_path):
        print(f"  File already exists, skipping: {output_path}")
        return
    
    # Write cases to CSV
    fieldnames = ["case_id", "case_name", "incident_pattern", "telemetry_input", 
                  "expected_decision", "expected_diagnosis", "notes"]
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(cases)
    
    print(f"  Created: {output_path} ({len(cases)} cases)")


if __name__ == "__main__":
    cases = generate_benchmark_cases()
    write_benchmark_file(cases)
    print(f"Benchmark dataset generated successfully! ({len(cases)} cases)")
