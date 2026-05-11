"""
Generate expanded benchmark dataset with 100 cases for IEEE Access paper evaluation.

This module creates a CSV file containing:
- 23 cases: All 23 known incident patterns (one per pattern) [from original]
- 5 cases: Clean/healthy VM cases [from original]
- 5 cases: Missing telemetry cases [from original]
- 5 cases: Conflicting signal cases [from original]
- 8 cases: High CPU variations (cpu_percent 92-99)
- 10 cases: Disk full variations (os_disk_percent_full 91-99)
- 9 cases: Memory exhaustion variations (memory_percent 93-99)
- 10 cases: NSG block variations (5 RDP, 5 SSH)
- 5 cases: SSL expiry variations (ssl_cert_days_remaining 0-14)
- 5 cases: Backup failure variations
- 5 cases: Multi-signal cases (e.g. high CPU + disk full + agent degraded)
- 5 cases: Platform event cases (planned maintenance / host update)
- 5 cases: Novel pattern cases (combinations not in known 20 patterns)
- 2 extra from original (patterns 21-23 minus overlap = patterns already counted above)

Total: 100 benchmark cases

Does NOT overwrite original data/benchmark_cases.csv.
Writes to data/benchmark_cases_v2.csv.
"""

import csv
import json
import os
import sys
from typing import List, Dict

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import original generator to reuse the first 38 cases
from setup.generate_benchmark import generate_benchmark_cases as generate_original_cases


def baseline_telemetry() -> Dict:
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


def generate_expanded_cases() -> List[Dict]:
    """
    Generates 100 benchmark cases for IEEE Access paper evaluation.
    
    Includes original 38 cases plus 62 new cases covering:
    - High CPU variations, disk full, memory exhaustion
    - NSG block variations, SSL expiry, backup failures
    - Multi-signal, platform event, and novel pattern cases
    
    Returns:
        List of 100 benchmark case dictionaries with is_novel field
    """
    # Start with original 38 cases, adding is_novel field
    original_cases = generate_original_cases()
    cases = []
    
    # Known pattern names from the 23 patterns
    known_patterns = {
        "vm_stopped_by_user", "nsg_blocks_rdp", "nsg_blocks_ssh",
        "high_cpu", "os_disk_full", "memory_exhaustion",
        "boot_bsod", "boot_kernel_panic", "vm_running_no_heartbeat",
        "resource_health_unavailable", "conflicting_nsg_signals",
        "app_unhealthy_vm_healthy", "disk_io_saturation", "vm_deallocated",
        "provisioning_failed", "failed_state_insufficient_data",
        "platform_degradation", "boot_stuck", "vm_agent_failed",
        "monitor_agent_failed", "ssl_cert_expiry_warning",
        "azure_backup_job_failure", "vm_oversized_rightsize_candidate"
    }
    
    for c in original_cases:
        c["is_novel"] = "False" if c["incident_pattern"] in known_patterns else "False"
        # Mark novel patterns from original set
        if c["incident_pattern"] in ("clean", "missing_telemetry", "conflicting_signals"):
            c["is_novel"] = "False"
        cases.append(c)
    
    case_num = 39  # Continue numbering from 039
    
    # ========================================================================
    # 8 High CPU cases (cpu_percent 92-99)
    # ========================================================================
    cpu_values = [92.0, 94.0, 95.2, 96.0, 96.8, 97.5, 98.7, 99.0]
    for i, cpu in enumerate(cpu_values):
        t = baseline_telemetry()
        t["cpu_percent"] = cpu
        t["resource_health_status"] = "Degraded"
        # Vary other signals for realism
        t["memory_percent"] = 40.0 + i * 3
        t["os_disk_latency_ms"] = 10.0 + i * 2
        cases.append({
            "case_id": f"{case_num:03d}",
            "case_name": f"High CPU Variation {i+1} ({cpu}%)",
            "incident_pattern": "high_cpu",
            "telemetry_input": json.dumps(t),
            "expected_decision": "diagnose",
            "expected_diagnosis": "High CPU saturation",
            "is_novel": "False",
            "notes": f"CPU at {cpu}%, memory at {t['memory_percent']}%"
        })
        case_num += 1

    # ========================================================================
    # 10 Disk full cases (os_disk_percent_full 91-99)
    # ========================================================================
    disk_values = [91.0, 92.0, 93.0, 94.0, 95.0, 96.0, 97.0, 97.5, 98.0, 99.0]
    for i, disk in enumerate(disk_values):
        t = baseline_telemetry()
        t["os_disk_percent_full"] = disk
        t["resource_health_status"] = "Degraded"
        t["os_disk_latency_ms"] = 50.0 + i * 15
        cases.append({
            "case_id": f"{case_num:03d}",
            "case_name": f"Disk Full Variation {i+1} ({disk}%)",
            "incident_pattern": "os_disk_full",
            "telemetry_input": json.dumps(t),
            "expected_decision": "diagnose",
            "expected_diagnosis": "OS disk full",
            "is_novel": "False",
            "notes": f"OS disk at {disk}%, latency {t['os_disk_latency_ms']}ms"
        })
        case_num += 1

    # ========================================================================
    # 9 Memory exhaustion cases (memory_percent 93-99)
    # ========================================================================
    mem_values = [93.0, 94.0, 95.0, 96.0, 96.5, 97.0, 97.5, 98.0, 99.0]
    mem_avail = [450, 380, 320, 260, 230, 200, 160, 120, 50]
    for i, (mem, avail) in enumerate(zip(mem_values, mem_avail)):
        t = baseline_telemetry()
        t["memory_percent"] = mem
        t["memory_available_mb"] = float(avail)
        t["resource_health_status"] = "Degraded"
        cases.append({
            "case_id": f"{case_num:03d}",
            "case_name": f"Memory Exhaustion Variation {i+1} ({mem}%)",
            "incident_pattern": "memory_exhaustion",
            "telemetry_input": json.dumps(t),
            "expected_decision": "diagnose",
            "expected_diagnosis": "Memory exhaustion",
            "is_novel": "False",
            "notes": f"Memory at {mem}%, available {avail}MB"
        })
        case_num += 1

    # ========================================================================
    # 10 NSG block cases (5 RDP, 5 SSH)
    # ========================================================================
    for i in range(5):
        t = baseline_telemetry()
        t["nsg_allow_rdp_3389"] = False
        t["connection_troubleshoot_rdp"] = "Deny"
        t["connection_troubleshoot_verdict"] = "NotReachable"
        # Vary other signals
        t["cpu_percent"] = 20.0 + i * 10
        t["app_health_status"] = ["Healthy", "Degraded", "Healthy", "Unhealthy", "Healthy"][i]
        cases.append({
            "case_id": f"{case_num:03d}",
            "case_name": f"NSG Blocks RDP Variation {i+1}",
            "incident_pattern": "nsg_blocks_rdp",
            "telemetry_input": json.dumps(t),
            "expected_decision": "diagnose",
            "expected_diagnosis": "NSG blocks RDP",
            "is_novel": "False",
            "notes": f"RDP blocked, CPU at {t['cpu_percent']}%"
        })
        case_num += 1

    for i in range(5):
        t = baseline_telemetry()
        t["nsg_allow_ssh_22"] = False
        t["connection_troubleshoot_ssh"] = "Deny"
        t["connection_troubleshoot_verdict"] = "NotReachable"
        t["memory_percent"] = 30.0 + i * 8
        cases.append({
            "case_id": f"{case_num:03d}",
            "case_name": f"NSG Blocks SSH Variation {i+1}",
            "incident_pattern": "nsg_blocks_ssh",
            "telemetry_input": json.dumps(t),
            "expected_decision": "diagnose",
            "expected_diagnosis": "NSG blocks SSH",
            "is_novel": "False",
            "notes": f"SSH blocked, memory at {t['memory_percent']}%"
        })
        case_num += 1

    # ========================================================================
    # 5 SSL expiry cases (ssl_cert_days_remaining 0-14)
    # ========================================================================
    ssl_days = [0, 1, 3, 7, 14]
    for i, days in enumerate(ssl_days):
        t = baseline_telemetry()
        t["ssl_cert_days_remaining"] = days
        cases.append({
            "case_id": f"{case_num:03d}",
            "case_name": f"SSL Expiry {days} Days Remaining",
            "incident_pattern": "ssl_cert_expiry_warning",
            "telemetry_input": json.dumps(t),
            "expected_decision": "diagnose",
            "expected_diagnosis": f"SSL certificate expiring in {days} days",
            "is_novel": "False",
            "notes": f"SSL cert expires in {days} days"
        })
        case_num += 1

    # ========================================================================
    # 5 Backup failure cases
    # ========================================================================
    backup_scenarios = [
        ("Failed", "2024-01-15T02:00:00Z", "Recent backup failure"),
        ("Failed", "2024-01-10T02:00:00Z", "Backup failed 5 days ago"),
        ("Failed", "2024-01-01T02:00:00Z", "Backup failed 2 weeks ago"),
        ("Failed", None, "Backup failed, no timestamp"),
        ("Failed", "2024-01-14T02:00:00Z", "Backup failed with high disk"),
    ]
    for i, (status, btime, note) in enumerate(backup_scenarios):
        t = baseline_telemetry()
        t["last_backup_status"] = status
        if btime:
            t["last_backup_time"] = btime
        else:
            t["last_backup_time"] = None
        if i == 4:
            t["os_disk_percent_full"] = 85.0
        cases.append({
            "case_id": f"{case_num:03d}",
            "case_name": f"Backup Failure Variation {i+1}",
            "incident_pattern": "azure_backup_job_failure",
            "telemetry_input": json.dumps(t),
            "expected_decision": "diagnose",
            "expected_diagnosis": "Azure VM backup job failed",
            "is_novel": "False",
            "notes": note
        })
        case_num += 1

    # ========================================================================
    # 5 Multi-signal cases (e.g. high CPU + disk full + agent degraded)
    # ========================================================================
    multi_signal_cases = [
        {
            "name": "High CPU + Disk Full",
            "mods": {"cpu_percent": 96.0, "os_disk_percent_full": 95.0,
                     "resource_health_status": "Degraded"},
            "pattern": "high_cpu",
            "decision": "diagnose",
            "diagnosis": "High CPU saturation",
        },
        {
            "name": "Memory Exhaustion + Disk IO Saturation",
            "mods": {"memory_percent": 97.0, "memory_available_mb": 150.0,
                     "os_disk_latency_ms": 200.0, "data_disk_latency_ms": 180.0,
                     "resource_health_status": "Degraded"},
            "pattern": "memory_exhaustion",
            "decision": "diagnose",
            "diagnosis": "Memory exhaustion",
        },
        {
            "name": "High CPU + Agent Degraded + App Unhealthy",
            "mods": {"cpu_percent": 95.0, "azure_vm_agent_status": "Degraded",
                     "app_health_status": "Unhealthy",
                     "app_error_message": "Service timeout",
                     "resource_health_status": "Degraded"},
            "pattern": "high_cpu",
            "decision": "diagnose",
            "diagnosis": "High CPU saturation",
        },
        {
            "name": "Disk Full + Backup Failed + Monitor Degraded",
            "mods": {"os_disk_percent_full": 98.0, "last_backup_status": "Failed",
                     "monitor_agent_status": "Degraded",
                     "resource_health_status": "Degraded"},
            "pattern": "os_disk_full",
            "decision": "diagnose",
            "diagnosis": "OS disk full",
        },
        {
            "name": "Memory + CPU + SSL Expiring",
            "mods": {"cpu_percent": 94.0, "memory_percent": 95.0,
                     "memory_available_mb": 250.0, "ssl_cert_days_remaining": 3,
                     "resource_health_status": "Degraded"},
            "pattern": "high_cpu",
            "decision": "diagnose",
            "diagnosis": "High CPU saturation",
        },
    ]
    for i, ms in enumerate(multi_signal_cases):
        t = baseline_telemetry()
        t.update(ms["mods"])
        cases.append({
            "case_id": f"{case_num:03d}",
            "case_name": f"Multi-Signal: {ms['name']}",
            "incident_pattern": ms["pattern"],
            "telemetry_input": json.dumps(t),
            "expected_decision": ms["decision"],
            "expected_diagnosis": ms["diagnosis"],
            "is_novel": "False",
            "notes": f"Multi-signal case: {ms['name']}"
        })
        case_num += 1

    # ========================================================================
    # 5 Platform event cases
    # ========================================================================
    platform_annotations = [
        "Planned maintenance scheduled for host update",
        "Platform degradation detected on host node",
        "Host update in progress - VM may experience brief interruption",
        "Planned maintenance: memory-preserving update",
        "Platform initiated reboot for security patch",
    ]
    for i, annotation in enumerate(platform_annotations):
        t = baseline_telemetry()
        t["resource_health_status"] = "Degraded"
        t["resource_health_annotation"] = annotation
        cases.append({
            "case_id": f"{case_num:03d}",
            "case_name": f"Platform Event Variation {i+1}",
            "incident_pattern": "platform_degradation",
            "telemetry_input": json.dumps(t),
            "expected_decision": "abstain_request_next_check",
            "expected_diagnosis": "Platform-initiated event detected",
            "is_novel": "False",
            "notes": f"Platform annotation: {annotation[:50]}..."
        })
        case_num += 1

    # ========================================================================
    # 5 Novel pattern cases (combinations not in known 20 patterns)
    # ========================================================================
    novel_cases = [
        {
            "name": "Memory High + Disk IO + App Unhealthy + Agent Healthy",
            "mods": {"memory_percent": 96.0, "memory_available_mb": 200.0,
                     "os_disk_latency_ms": 180.0, "data_disk_latency_ms": 150.0,
                     "app_health_status": "Unhealthy",
                     "app_error_message": "Connection pool exhausted",
                     "resource_health_status": "Degraded"},
            "decision": "diagnose_low_confidence",
            "diagnosis": "Novel pattern: memory pressure with disk IO and app failure",
        },
        {
            "name": "Agent NotReporting + Monitor Failed + App Degraded",
            "mods": {"azure_vm_agent_status": "NotReporting",
                     "monitor_agent_status": "Failed",
                     "app_health_status": "Degraded",
                     "heartbeat_present": False,
                     "resource_health_status": "Degraded"},
            "decision": "diagnose_low_confidence",
            "diagnosis": "Novel pattern: multiple agent failures with app degradation",
        },
        {
            "name": "SSL Expired + Backup Failed + High Disk",
            "mods": {"ssl_cert_days_remaining": 0, "last_backup_status": "Failed",
                     "os_disk_percent_full": 88.0,
                     "resource_health_status": "Degraded"},
            "decision": "diagnose_low_confidence",
            "diagnosis": "Novel pattern: SSL expired with backup failure and high disk",
        },
        {
            "name": "Boot Stuck + Agent Degraded + Network Timeout",
            "mods": {"boot_diagnostics_status": "Stuck",
                     "boot_diagnostics_error": "Boot process hung",
                     "azure_vm_agent_status": "Degraded",
                     "connection_troubleshoot_rdp": "Timeout",
                     "connection_troubleshoot_ssh": "Timeout",
                     "resource_health_status": "Unavailable"},
            "decision": "diagnose",
            "diagnosis": "Boot stuck at startup",
        },
        {
            "name": "Intermittent Heartbeat + High Memory + NSG Inconclusive",
            "mods": {"heartbeat_present": True,
                     "memory_percent": 94.0, "memory_available_mb": 300.0,
                     "connection_troubleshoot_rdp": "Inconclusive",
                     "connection_troubleshoot_ssh": "Inconclusive",
                     "resource_health_status": "Degraded"},
            "decision": "diagnose_low_confidence",
            "diagnosis": "Novel pattern: memory pressure with inconclusive network",
        },
    ]
    for i, nc in enumerate(novel_cases):
        t = baseline_telemetry()
        t.update(nc["mods"])
        cases.append({
            "case_id": f"{case_num:03d}",
            "case_name": f"Novel: {nc['name']}",
            "incident_pattern": "novel",
            "telemetry_input": json.dumps(t),
            "expected_decision": nc["decision"],
            "expected_diagnosis": nc["diagnosis"],
            "is_novel": "True",
            "notes": f"Novel pattern not in known 23 patterns"
        })
        case_num += 1

    # Verify we have exactly 100 cases
    assert len(cases) == 100, f"Expected 100 cases, got {len(cases)}"
    
    return cases


def write_benchmark_v2(cases: List[Dict], output_path: str = "data/benchmark_cases_v2.csv"):
    """
    Writes 100 benchmark cases to CSV.
    Does NOT overwrite original benchmark_cases.csv.
    
    Args:
        cases: List of 100 benchmark case dictionaries
        output_path: Target file path
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    fieldnames = ["case_id", "case_name", "incident_pattern", "telemetry_input",
                  "expected_decision", "expected_diagnosis", "is_novel", "notes"]
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(cases)
    
    print(f"Generated {len(cases)} benchmark cases to {output_path}")


if __name__ == "__main__":
    cases = generate_expanded_cases()
    write_benchmark_v2(cases)
