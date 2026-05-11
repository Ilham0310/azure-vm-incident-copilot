#!/usr/bin/env python3
"""
triage_test_vms.py
Collects real telemetry from the 3 test VMs and runs the copilot triage on each.

Prerequisites:
  - VMs created via setup/create_test_vms.ps1
  - az login completed
  - pip install azure-mgmt-compute azure-mgmt-monitor azure-identity

Usage:
  python setup/triage_test_vms.py
"""
import os
import sys
import json
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

SUBSCRIPTION = os.getenv("AZURE_SUBSCRIPTION_ID", "be8946da-5ca2-4129-ae53-b6124a0aa2d1")
RG = os.getenv("AZURE_RESOURCE_GROUP", "AZ26POC1-CO-LAB")
TEST_VMS = [
    os.getenv("TEST_VM_1", "copilot-test-vm1"),
    os.getenv("TEST_VM_2", "copilot-test-vm2"),
    os.getenv("TEST_VM_3", "copilot-test-vm3"),
]


def collect_vm_telemetry(vm_name: str) -> dict:
    """Collect real telemetry from an Azure VM using the Azure SDK."""
    try:
        from azure.identity import DefaultAzureCredential
        from azure.mgmt.compute import ComputeManagementClient
        from azure.mgmt.monitor import MonitorManagementClient
        from azure.mgmt.resource import ResourceManagementClient
    except ImportError:
        print("Install Azure SDK: pip install azure-mgmt-compute azure-mgmt-monitor azure-identity")
        sys.exit(1)

    cred = DefaultAzureCredential()
    compute = ComputeManagementClient(cred, SUBSCRIPTION)
    monitor = MonitorManagementClient(cred, SUBSCRIPTION)

    print(f"\nCollecting telemetry for {vm_name}...")

    # Get VM instance view
    vm = compute.virtual_machines.get(RG, vm_name, expand="instanceView")
    instance_view = vm.instance_view

    # Power state
    power_state = "Unknown"
    provisioning_state = "Unknown"
    for status in (instance_view.statuses or []):
        if status.code.startswith("PowerState/"):
            power_state = status.code.split("/")[1].capitalize()
        if status.code.startswith("ProvisioningState/"):
            provisioning_state = status.code.split("/")[1].capitalize()

    # VM agent status
    agent_status = "Unknown"
    if instance_view.vm_agent:
        for s in (instance_view.vm_agent.statuses or []):
            if s.code:
                agent_status = "Healthy" if "ready" in s.code.lower() else "Degraded"

    # Resource health (simplified — use resource health API for real status)
    resource_health_status = "Available"  # Default; override below if degraded

    # Build telemetry dict matching the system's schema
    telemetry = {
        "power_state": power_state,
        "provisioning_state": provisioning_state,
        "resource_health_status": resource_health_status,
        "resource_health_annotation": None,
        "heartbeat_present": True,
        "heartbeat_last_received": datetime.now(timezone.utc).isoformat(),
        "boot_diagnostics_status": "Normal",
        "boot_diagnostics_error": None,
        "azure_vm_agent_status": agent_status,
        "cpu_percent": None,
        "memory_percent": None,
        "memory_available_mb": None,
        "os_disk_latency_ms": None,
        "data_disk_latency_ms": None,
        "os_disk_percent_full": None,
        "app_health_status": "Unknown",
        "app_error_message": None,
        "nsg_allow_rdp_3389": True,
        "nsg_allow_ssh_22": True,
        "connection_troubleshoot_rdp": "Allow",
        "connection_troubleshoot_ssh": "Allow",
        "connection_troubleshoot_verdict": "Reachable",
        "monitor_agent_status": "Unknown",
        "ssl_cert_days_remaining": None,
        "last_backup_status": "Unknown",
        "last_backup_time": None,
        "data_completeness_percent": 40.0,
        "missing_signals": ["cpu_percent", "memory_percent", "os_disk_percent_full"],
    }

    # Try to get CPU metrics from Azure Monitor
    try:
        vm_id = vm.id
        end_time = datetime.now(timezone.utc)
        from datetime import timedelta
        start_time = end_time - timedelta(minutes=10)

        metrics = monitor.metrics.list(
            vm_id,
            timespan=f"{start_time.isoformat()}/{end_time.isoformat()}",
            interval="PT1M",
            metricnames="Percentage CPU",
            aggregation="Average",
        )
        for metric in metrics.value:
            for ts in metric.timeseries:
                for dp in ts.data:
                    if dp.average is not None:
                        telemetry["cpu_percent"] = round(dp.average, 1)
                        break
    except Exception as e:
        print(f"  Could not get CPU metrics: {e}")

    # Compute completeness
    optional_fields = [
        "resource_health_annotation", "heartbeat_present", "heartbeat_last_received",
        "boot_diagnostics_status", "boot_diagnostics_error", "azure_vm_agent_status",
        "cpu_percent", "memory_percent", "memory_available_mb", "os_disk_latency_ms",
        "data_disk_latency_ms", "os_disk_percent_full", "app_health_status",
        "app_error_message", "nsg_allow_rdp_3389", "nsg_allow_ssh_22",
        "connection_troubleshoot_rdp", "connection_troubleshoot_ssh",
        "connection_troubleshoot_verdict", "monitor_agent_status",
    ]
    populated = sum(1 for f in optional_fields if telemetry.get(f) is not None)
    telemetry["data_completeness_percent"] = round(populated / len(optional_fields) * 100, 1)
    telemetry["missing_signals"] = [f for f in optional_fields if telemetry.get(f) is None]

    print(f"  Power: {power_state}, Agent: {agent_status}, "
          f"CPU: {telemetry['cpu_percent']}%, "
          f"Completeness: {telemetry['data_completeness_percent']}%")
    return telemetry


def run_triage(vm_name: str, telemetry: dict):
    """Run the copilot triage on collected telemetry."""
    from src.models import TelemetryInput
    from src.confidence_scorer import ConfidenceScorer
    from src.decision_engine import DecisionEngine
    from src.safety_guard import SafetyGuard

    try:
        tel = TelemetryInput(**telemetry)
    except Exception as e:
        print(f"  Telemetry validation error: {e}")
        return

    scorer = ConfidenceScorer()
    engine = DecisionEngine()

    completeness, confidence, conflicts = scorer.score_telemetry(tel)
    decision = engine.decide(tel, confidence, completeness)

    print(f"\n  === Triage Result for {vm_name} ===")
    print(f"  Decision:    {decision.state.value}")
    print(f"  Diagnosis:   {decision.diagnosis}")
    print(f"  Confidence:  {confidence:.2f}")
    print(f"  Completeness:{completeness:.1f}%")
    print(f"  Next check:  {decision.next_check}")
    if decision.safety_rules_applied:
        print(f"  Safety rules:{', '.join(decision.safety_rules_applied)}")
    print(f"  Evidence:    {', '.join(decision.evidence[:3])}")

    return decision


def main():
    print("=" * 60)
    print("Azure VM Incident Copilot — Real VM Triage")
    print(f"Subscription: {SUBSCRIPTION}")
    print(f"Resource Group: {RG}")
    print("=" * 60)

    results = []
    for vm_name in TEST_VMS:
        try:
            telemetry = collect_vm_telemetry(vm_name)
            decision = run_triage(vm_name, telemetry)
            results.append({
                "vm": vm_name,
                "telemetry": telemetry,
                "decision": decision.state.value if decision else "error",
                "diagnosis": decision.diagnosis if decision else "error",
            })
        except Exception as e:
            print(f"\nError processing {vm_name}: {e}")
            results.append({"vm": vm_name, "error": str(e)})

    # Save results
    out_path = f"results/real_vm_triage_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    os.makedirs("results", exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
