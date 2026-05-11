#!/usr/bin/env python3
"""
Generate 30 expanded novel-case benchmark cases.

These cases represent genuinely out-of-distribution signal combinations
that do not map to any of the 23 known rule-engine patterns.
Each case combines multiple subsystem failures in ways the rule engine
cannot handle with a single pattern match.

Output: data/expanded_novel_cases.csv
"""
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OUTPUT_FILE = "data/expanded_novel_cases.csv"

# 30 novel cases: multi-signal combinations not covered by any single known pattern
NOVEL_CASES = [
    # Category 1: VM Agent + App Health (5 cases)
    {"case_id": "N01", "case_name": "Agent NotReporting + App Degraded + Normal CPU",
     "expected_decision": "diagnose_low_confidence",
     "telemetry": {"power_state": "Running", "provisioning_state": "Succeeded",
                   "resource_health_status": "Available", "heartbeat_present": True,
                   "azure_vm_agent_status": "NotReporting", "boot_diagnostics_status": "Normal",
                   "cpu_percent": 35.0, "memory_percent": 45.0, "os_disk_percent_full": 40.0,
                   "app_health_status": "Degraded", "nsg_allow_rdp_3389": True, "nsg_allow_ssh_22": True,
                   "monitor_agent_status": "NotReporting", "ssl_cert_days_remaining": 90}},
    {"case_id": "N02", "case_name": "Agent Failed + App Unhealthy + Memory Normal",
     "expected_decision": "diagnose_low_confidence",
     "telemetry": {"power_state": "Running", "provisioning_state": "Succeeded",
                   "resource_health_status": "Degraded", "heartbeat_present": False,
                   "azure_vm_agent_status": "Failed", "boot_diagnostics_status": "Normal",
                   "cpu_percent": 25.0, "memory_percent": 50.0, "os_disk_percent_full": 35.0,
                   "app_health_status": "Unhealthy", "nsg_allow_rdp_3389": True, "nsg_allow_ssh_22": True,
                   "monitor_agent_status": "Failed", "ssl_cert_days_remaining": 60}},
    {"case_id": "N03", "case_name": "Agent Degraded + App Healthy + High Disk Latency",
     "expected_decision": "diagnose_low_confidence",
     "telemetry": {"power_state": "Running", "provisioning_state": "Succeeded",
                   "resource_health_status": "Available", "heartbeat_present": True,
                   "azure_vm_agent_status": "Degraded", "boot_diagnostics_status": "Normal",
                   "cpu_percent": 40.0, "memory_percent": 55.0, "os_disk_latency_ms": 150.0,
                   "os_disk_percent_full": 60.0, "app_health_status": "Healthy",
                   "nsg_allow_rdp_3389": True, "nsg_allow_ssh_22": True,
                   "monitor_agent_status": "Degraded", "ssl_cert_days_remaining": 45}},
    {"case_id": "N04", "case_name": "Agent Healthy + Monitor NotReporting + App Degraded",
     "expected_decision": "diagnose_low_confidence",
     "telemetry": {"power_state": "Running", "provisioning_state": "Succeeded",
                   "resource_health_status": "Available", "heartbeat_present": True,
                   "azure_vm_agent_status": "Healthy", "boot_diagnostics_status": "Normal",
                   "cpu_percent": 30.0, "memory_percent": 40.0, "os_disk_percent_full": 45.0,
                   "app_health_status": "Degraded", "nsg_allow_rdp_3389": True, "nsg_allow_ssh_22": True,
                   "monitor_agent_status": "NotReporting", "ssl_cert_days_remaining": 30}},
    {"case_id": "N05", "case_name": "Agent NotReporting + App Unhealthy + SSL Expiring",
     "expected_decision": "diagnose_low_confidence",
     "telemetry": {"power_state": "Running", "provisioning_state": "Succeeded",
                   "resource_health_status": "Degraded", "heartbeat_present": False,
                   "azure_vm_agent_status": "NotReporting", "boot_diagnostics_status": "Normal",
                   "cpu_percent": 45.0, "memory_percent": 60.0, "os_disk_percent_full": 50.0,
                   "app_health_status": "Unhealthy", "nsg_allow_rdp_3389": True, "nsg_allow_ssh_22": True,
                   "monitor_agent_status": "NotReporting", "ssl_cert_days_remaining": 5}},

    # Category 2: Intermittent Heartbeat + Normal Metrics (5 cases)
    {"case_id": "N06", "case_name": "No Heartbeat + All Metrics Normal + Available",
     "expected_decision": "diagnose_low_confidence",
     "telemetry": {"power_state": "Running", "provisioning_state": "Succeeded",
                   "resource_health_status": "Available", "heartbeat_present": False,
                   "azure_vm_agent_status": "Healthy", "boot_diagnostics_status": "Normal",
                   "cpu_percent": 20.0, "memory_percent": 35.0, "os_disk_percent_full": 30.0,
                   "app_health_status": "Healthy", "nsg_allow_rdp_3389": True, "nsg_allow_ssh_22": True,
                   "monitor_agent_status": "Healthy", "ssl_cert_days_remaining": 120}},
    {"case_id": "N07", "case_name": "No Heartbeat + Moderate CPU + Degraded Health",
     "expected_decision": "diagnose_low_confidence",
     "telemetry": {"power_state": "Running", "provisioning_state": "Succeeded",
                   "resource_health_status": "Degraded", "heartbeat_present": False,
                   "azure_vm_agent_status": "Healthy", "boot_diagnostics_status": "Normal",
                   "cpu_percent": 70.0, "memory_percent": 55.0, "os_disk_percent_full": 45.0,
                   "app_health_status": "Healthy", "nsg_allow_rdp_3389": True, "nsg_allow_ssh_22": True,
                   "monitor_agent_status": "Healthy", "ssl_cert_days_remaining": 90}},
    {"case_id": "N08", "case_name": "No Heartbeat + High Memory + Normal CPU",
     "expected_decision": "diagnose_low_confidence",
     "telemetry": {"power_state": "Running", "provisioning_state": "Succeeded",
                   "resource_health_status": "Available", "heartbeat_present": False,
                   "azure_vm_agent_status": "Degraded", "boot_diagnostics_status": "Normal",
                   "cpu_percent": 30.0, "memory_percent": 88.0, "os_disk_percent_full": 40.0,
                   "app_health_status": "Healthy", "nsg_allow_rdp_3389": True, "nsg_allow_ssh_22": True,
                   "monitor_agent_status": "Degraded", "ssl_cert_days_remaining": 60}},
    {"case_id": "N09", "case_name": "No Heartbeat + Disk Pressure + App OK",
     "expected_decision": "diagnose_low_confidence",
     "telemetry": {"power_state": "Running", "provisioning_state": "Succeeded",
                   "resource_health_status": "Available", "heartbeat_present": False,
                   "azure_vm_agent_status": "Healthy", "boot_diagnostics_status": "Normal",
                   "cpu_percent": 25.0, "memory_percent": 40.0, "os_disk_percent_full": 85.0,
                   "app_health_status": "Healthy", "nsg_allow_rdp_3389": True, "nsg_allow_ssh_22": True,
                   "monitor_agent_status": "Healthy", "ssl_cert_days_remaining": 90}},
    {"case_id": "N10", "case_name": "No Heartbeat + NSG Inconclusive + Normal",
     "expected_decision": "diagnose_low_confidence",
     "telemetry": {"power_state": "Running", "provisioning_state": "Succeeded",
                   "resource_health_status": "Available", "heartbeat_present": False,
                   "azure_vm_agent_status": "Healthy", "boot_diagnostics_status": "Normal",
                   "cpu_percent": 35.0, "memory_percent": 45.0, "os_disk_percent_full": 40.0,
                   "app_health_status": "Unknown", "nsg_allow_rdp_3389": True, "nsg_allow_ssh_22": True,
                   "connection_troubleshoot_verdict": "Inconclusive",
                   "monitor_agent_status": "Healthy", "ssl_cert_days_remaining": 90}},

    # Category 3: Network + Healthy Guest (5 cases)
    {"case_id": "N11", "case_name": "Network Timeout + Healthy VM + RDP Allow",
     "expected_decision": "diagnose_low_confidence",
     "telemetry": {"power_state": "Running", "provisioning_state": "Succeeded",
                   "resource_health_status": "Available", "heartbeat_present": True,
                   "azure_vm_agent_status": "Healthy", "boot_diagnostics_status": "Normal",
                   "cpu_percent": 20.0, "memory_percent": 30.0, "os_disk_percent_full": 25.0,
                   "app_health_status": "Healthy", "nsg_allow_rdp_3389": True, "nsg_allow_ssh_22": True,
                   "connection_troubleshoot_rdp": "Timeout", "connection_troubleshoot_ssh": "Allow",
                   "monitor_agent_status": "Healthy", "ssl_cert_days_remaining": 90}},
    {"case_id": "N12", "case_name": "SSH Timeout + RDP Allow + App Degraded",
     "expected_decision": "diagnose_low_confidence",
     "telemetry": {"power_state": "Running", "provisioning_state": "Succeeded",
                   "resource_health_status": "Available", "heartbeat_present": True,
                   "azure_vm_agent_status": "Healthy", "boot_diagnostics_status": "Normal",
                   "cpu_percent": 40.0, "memory_percent": 50.0, "os_disk_percent_full": 35.0,
                   "app_health_status": "Degraded", "nsg_allow_rdp_3389": True, "nsg_allow_ssh_22": True,
                   "connection_troubleshoot_rdp": "Allow", "connection_troubleshoot_ssh": "Timeout",
                   "monitor_agent_status": "Healthy", "ssl_cert_days_remaining": 60}},
    {"case_id": "N13", "case_name": "Both Timeout + NSG Allow + Healthy Agent",
     "expected_decision": "diagnose_low_confidence",
     "telemetry": {"power_state": "Running", "provisioning_state": "Succeeded",
                   "resource_health_status": "Degraded", "heartbeat_present": True,
                   "azure_vm_agent_status": "Healthy", "boot_diagnostics_status": "Normal",
                   "cpu_percent": 30.0, "memory_percent": 40.0, "os_disk_percent_full": 30.0,
                   "app_health_status": "Healthy", "nsg_allow_rdp_3389": True, "nsg_allow_ssh_22": True,
                   "connection_troubleshoot_rdp": "Timeout", "connection_troubleshoot_ssh": "Timeout",
                   "monitor_agent_status": "Healthy", "ssl_cert_days_remaining": 90}},
    {"case_id": "N14", "case_name": "Inconclusive Troubleshoot + High Memory",
     "expected_decision": "diagnose_low_confidence",
     "telemetry": {"power_state": "Running", "provisioning_state": "Succeeded",
                   "resource_health_status": "Available", "heartbeat_present": True,
                   "azure_vm_agent_status": "Healthy", "boot_diagnostics_status": "Normal",
                   "cpu_percent": 35.0, "memory_percent": 85.0, "os_disk_percent_full": 40.0,
                   "app_health_status": "Healthy", "nsg_allow_rdp_3389": True, "nsg_allow_ssh_22": True,
                   "connection_troubleshoot_rdp": "Inconclusive", "connection_troubleshoot_ssh": "Inconclusive",
                   "monitor_agent_status": "Healthy", "ssl_cert_days_remaining": 90}},
    {"case_id": "N15", "case_name": "NSG Deny SSH + Troubleshoot Allow + App Unhealthy",
     "expected_decision": "diagnose_low_confidence",
     "telemetry": {"power_state": "Running", "provisioning_state": "Succeeded",
                   "resource_health_status": "Available", "heartbeat_present": True,
                   "azure_vm_agent_status": "Healthy", "boot_diagnostics_status": "Normal",
                   "cpu_percent": 25.0, "memory_percent": 40.0, "os_disk_percent_full": 35.0,
                   "app_health_status": "Unhealthy", "nsg_allow_rdp_3389": True, "nsg_allow_ssh_22": False,
                   "connection_troubleshoot_rdp": "Allow", "connection_troubleshoot_ssh": "Allow",
                   "monitor_agent_status": "Healthy", "ssl_cert_days_remaining": 45}},

    # Category 4: Resource Health Degraded + Inconclusive Signals (5 cases)
    {"case_id": "N16", "case_name": "Degraded Health + Normal Metrics + No Annotation",
     "expected_decision": "diagnose_low_confidence",
     "telemetry": {"power_state": "Running", "provisioning_state": "Succeeded",
                   "resource_health_status": "Degraded", "heartbeat_present": True,
                   "azure_vm_agent_status": "Healthy", "boot_diagnostics_status": "Normal",
                   "cpu_percent": 30.0, "memory_percent": 40.0, "os_disk_percent_full": 35.0,
                   "app_health_status": "Healthy", "nsg_allow_rdp_3389": True, "nsg_allow_ssh_22": True,
                   "monitor_agent_status": "Healthy", "ssl_cert_days_remaining": 90}},
    {"case_id": "N17", "case_name": "Unavailable Health + Running + Normal CPU",
     "expected_decision": "diagnose_low_confidence",
     "telemetry": {"power_state": "Running", "provisioning_state": "Succeeded",
                   "resource_health_status": "Unavailable", "heartbeat_present": True,
                   "azure_vm_agent_status": "Healthy", "boot_diagnostics_status": "Normal",
                   "cpu_percent": 35.0, "memory_percent": 45.0, "os_disk_percent_full": 40.0,
                   "app_health_status": "Healthy", "nsg_allow_rdp_3389": True, "nsg_allow_ssh_22": True,
                   "monitor_agent_status": "Healthy", "ssl_cert_days_remaining": 60}},
    {"case_id": "N18", "case_name": "Degraded Health + Backup Failed + Moderate Load",
     "expected_decision": "diagnose_low_confidence",
     "telemetry": {"power_state": "Running", "provisioning_state": "Succeeded",
                   "resource_health_status": "Degraded", "heartbeat_present": True,
                   "azure_vm_agent_status": "Healthy", "boot_diagnostics_status": "Normal",
                   "cpu_percent": 55.0, "memory_percent": 60.0, "os_disk_percent_full": 50.0,
                   "app_health_status": "Healthy", "nsg_allow_rdp_3389": True, "nsg_allow_ssh_22": True,
                   "monitor_agent_status": "Healthy", "last_backup_status": "Failed",
                   "ssl_cert_days_remaining": 90}},
    {"case_id": "N19", "case_name": "Degraded Health + SSL Expired + Agent OK",
     "expected_decision": "diagnose_low_confidence",
     "telemetry": {"power_state": "Running", "provisioning_state": "Succeeded",
                   "resource_health_status": "Degraded", "heartbeat_present": True,
                   "azure_vm_agent_status": "Healthy", "boot_diagnostics_status": "Normal",
                   "cpu_percent": 30.0, "memory_percent": 40.0, "os_disk_percent_full": 35.0,
                   "app_health_status": "Healthy", "nsg_allow_rdp_3389": True, "nsg_allow_ssh_22": True,
                   "monitor_agent_status": "Healthy", "ssl_cert_days_remaining": 0}},
    {"case_id": "N20", "case_name": "Unavailable Health + High Disk + App Degraded",
     "expected_decision": "diagnose_low_confidence",
     "telemetry": {"power_state": "Running", "provisioning_state": "Succeeded",
                   "resource_health_status": "Unavailable", "heartbeat_present": True,
                   "azure_vm_agent_status": "Healthy", "boot_diagnostics_status": "Normal",
                   "cpu_percent": 40.0, "memory_percent": 50.0, "os_disk_percent_full": 88.0,
                   "app_health_status": "Degraded", "nsg_allow_rdp_3389": True, "nsg_allow_ssh_22": True,
                   "monitor_agent_status": "Healthy", "ssl_cert_days_remaining": 30}},

    # Category 5: Multi-signal ambiguous (5 cases)
    {"case_id": "N21", "case_name": "Moderate CPU + High Memory + Disk Pressure + App OK",
     "expected_decision": "diagnose_low_confidence",
     "telemetry": {"power_state": "Running", "provisioning_state": "Succeeded",
                   "resource_health_status": "Available", "heartbeat_present": True,
                   "azure_vm_agent_status": "Healthy", "boot_diagnostics_status": "Normal",
                   "cpu_percent": 75.0, "memory_percent": 85.0, "os_disk_percent_full": 80.0,
                   "app_health_status": "Healthy", "nsg_allow_rdp_3389": True, "nsg_allow_ssh_22": True,
                   "monitor_agent_status": "Healthy", "ssl_cert_days_remaining": 90}},
    {"case_id": "N22", "case_name": "Low CPU + High Memory + Agent Degraded + Backup Failed",
     "expected_decision": "diagnose_low_confidence",
     "telemetry": {"power_state": "Running", "provisioning_state": "Succeeded",
                   "resource_health_status": "Available", "heartbeat_present": True,
                   "azure_vm_agent_status": "Degraded", "boot_diagnostics_status": "Normal",
                   "cpu_percent": 15.0, "memory_percent": 92.0, "os_disk_percent_full": 45.0,
                   "app_health_status": "Healthy", "nsg_allow_rdp_3389": True, "nsg_allow_ssh_22": True,
                   "monitor_agent_status": "Degraded", "last_backup_status": "Failed",
                   "ssl_cert_days_remaining": 60}},
    {"case_id": "N23", "case_name": "High CPU + Normal Memory + SSL Expiring + App Degraded",
     "expected_decision": "diagnose_low_confidence",
     "telemetry": {"power_state": "Running", "provisioning_state": "Succeeded",
                   "resource_health_status": "Degraded", "heartbeat_present": True,
                   "azure_vm_agent_status": "Healthy", "boot_diagnostics_status": "Normal",
                   "cpu_percent": 92.0, "memory_percent": 45.0, "os_disk_percent_full": 40.0,
                   "app_health_status": "Degraded", "nsg_allow_rdp_3389": True, "nsg_allow_ssh_22": True,
                   "monitor_agent_status": "Healthy", "ssl_cert_days_remaining": 3}},
    {"case_id": "N24", "case_name": "Boot Stuck + Agent OK + App Healthy",
     "expected_decision": "diagnose_low_confidence",
     "telemetry": {"power_state": "Running", "provisioning_state": "Succeeded",
                   "resource_health_status": "Available", "heartbeat_present": True,
                   "azure_vm_agent_status": "Healthy", "boot_diagnostics_status": "Stuck",
                   "cpu_percent": 30.0, "memory_percent": 40.0, "os_disk_percent_full": 35.0,
                   "app_health_status": "Healthy", "nsg_allow_rdp_3389": True, "nsg_allow_ssh_22": True,
                   "monitor_agent_status": "Healthy", "ssl_cert_days_remaining": 90}},
    {"case_id": "N25", "case_name": "Normal Metrics + Disk IO High + Monitor Failed",
     "expected_decision": "diagnose_low_confidence",
     "telemetry": {"power_state": "Running", "provisioning_state": "Succeeded",
                   "resource_health_status": "Available", "heartbeat_present": True,
                   "azure_vm_agent_status": "Healthy", "boot_diagnostics_status": "Normal",
                   "cpu_percent": 25.0, "memory_percent": 35.0, "os_disk_latency_ms": 200.0,
                   "os_disk_percent_full": 40.0, "app_health_status": "Healthy",
                   "nsg_allow_rdp_3389": True, "nsg_allow_ssh_22": True,
                   "monitor_agent_status": "Failed", "ssl_cert_days_remaining": 90}},

    # Category 6: Cross-subsystem ambiguous (5 cases)
    {"case_id": "N26", "case_name": "Platform Available + App Unhealthy + All Metrics Normal",
     "expected_decision": "diagnose_low_confidence",
     "telemetry": {"power_state": "Running", "provisioning_state": "Succeeded",
                   "resource_health_status": "Available", "heartbeat_present": True,
                   "azure_vm_agent_status": "Healthy", "boot_diagnostics_status": "Normal",
                   "cpu_percent": 20.0, "memory_percent": 30.0, "os_disk_percent_full": 25.0,
                   "app_health_status": "Unhealthy", "app_error_message": "Connection pool exhausted",
                   "nsg_allow_rdp_3389": True, "nsg_allow_ssh_22": True,
                   "monitor_agent_status": "Healthy", "ssl_cert_days_remaining": 90}},
    {"case_id": "N27", "case_name": "Backup Failed + Disk 75% + SSL 7 days + App OK",
     "expected_decision": "diagnose_low_confidence",
     "telemetry": {"power_state": "Running", "provisioning_state": "Succeeded",
                   "resource_health_status": "Available", "heartbeat_present": True,
                   "azure_vm_agent_status": "Healthy", "boot_diagnostics_status": "Normal",
                   "cpu_percent": 30.0, "memory_percent": 40.0, "os_disk_percent_full": 75.0,
                   "app_health_status": "Healthy", "nsg_allow_rdp_3389": True, "nsg_allow_ssh_22": True,
                   "monitor_agent_status": "Healthy", "last_backup_status": "Failed",
                   "ssl_cert_days_remaining": 7}},
    {"case_id": "N28", "case_name": "Memory 90% + CPU Normal + Agent Degraded + Disk OK",
     "expected_decision": "diagnose_low_confidence",
     "telemetry": {"power_state": "Running", "provisioning_state": "Succeeded",
                   "resource_health_status": "Available", "heartbeat_present": True,
                   "azure_vm_agent_status": "Degraded", "boot_diagnostics_status": "Normal",
                   "cpu_percent": 25.0, "memory_percent": 90.0, "os_disk_percent_full": 35.0,
                   "app_health_status": "Healthy", "nsg_allow_rdp_3389": True, "nsg_allow_ssh_22": True,
                   "monitor_agent_status": "Degraded", "ssl_cert_days_remaining": 90}},
    {"case_id": "N29", "case_name": "CPU 80% + Disk 70% + Memory 70% + All Agents OK",
     "expected_decision": "diagnose_low_confidence",
     "telemetry": {"power_state": "Running", "provisioning_state": "Succeeded",
                   "resource_health_status": "Available", "heartbeat_present": True,
                   "azure_vm_agent_status": "Healthy", "boot_diagnostics_status": "Normal",
                   "cpu_percent": 80.0, "memory_percent": 70.0, "os_disk_percent_full": 70.0,
                   "app_health_status": "Healthy", "nsg_allow_rdp_3389": True, "nsg_allow_ssh_22": True,
                   "monitor_agent_status": "Healthy", "ssl_cert_days_remaining": 90}},
    {"case_id": "N30", "case_name": "Provisioning Updating + Running + Agent OK + App Degraded",
     "expected_decision": "diagnose_low_confidence",
     "telemetry": {"power_state": "Running", "provisioning_state": "Succeeded",
                   "resource_health_status": "Degraded", "heartbeat_present": True,
                   "azure_vm_agent_status": "Healthy", "boot_diagnostics_status": "Normal",
                   "cpu_percent": 45.0, "memory_percent": 55.0, "os_disk_percent_full": 50.0,
                   "app_health_status": "Degraded", "nsg_allow_rdp_3389": True, "nsg_allow_ssh_22": True,
                   "monitor_agent_status": "Healthy", "ssl_cert_days_remaining": 15}},
]


def main():
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    fieldnames = ["case_id", "case_name", "expected_decision", "telemetry_json", "is_novel", "category"]
    rows = []
    for case in NOVEL_CASES:
        cat_num = int(case["case_id"][1:3])
        if cat_num <= 5: category = "agent_app_health"
        elif cat_num <= 10: category = "intermittent_heartbeat"
        elif cat_num <= 15: category = "network_healthy_guest"
        elif cat_num <= 20: category = "resource_health_inconclusive"
        elif cat_num <= 25: category = "multi_signal_ambiguous"
        else: category = "cross_subsystem"

        rows.append({
            "case_id": case["case_id"],
            "case_name": case["case_name"],
            "expected_decision": case["expected_decision"],
            "telemetry_json": json.dumps(case["telemetry"]),
            "is_novel": "True",
            "category": category,
        })

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated {len(rows)} expanded novel cases → {OUTPUT_FILE}")
    print(f"Categories: {set(r['category'] for r in rows)}")


if __name__ == "__main__":
    main()
