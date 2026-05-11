#!/usr/bin/env python3
"""
scan_resource_group.py
Scans all VMs in the configured Azure resource group, collects telemetry
from each, and runs the incident copilot triage on each one.

Usage:
    python scan_resource_group.py

Requires:
    - az login (Azure CLI authenticated)
    - pip install azure-identity azure-mgmt-compute azure-mgmt-network azure-mgmt-monitor
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()

from src.models import TelemetryInput
from src.confidence_scorer import ConfidenceScorer
from src.decision_engine import DecisionEngine

SUBSCRIPTION = os.getenv("AZURE_SUBSCRIPTION_ID", "be8946da-5ca2-4129-ae53-b6124a0aa2d1")
RG = os.getenv("AZURE_RESOURCE_GROUP", "AZ26POC1-CO-LAB")


def az_cmd(args: list) -> dict:
    """Run an az CLI command and return parsed JSON output."""
    cmd = ["cmd", "/c", "az"] + args + ["-o", "json"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"az command failed: {result.stderr.strip()}")
    return json.loads(result.stdout) if result.stdout.strip() else {}


def list_vms() -> list:
    """List all VMs in the resource group."""
    vms = az_cmd(["vm", "list", "--resource-group", RG,
                  "--query", "[].{name:name, id:id, vmSize:hardwareProfile.vmSize}"])
    return vms


def get_vm_instance_view(vm_name: str) -> dict:
    """Get VM instance view with power state and agent status."""
    return az_cmd(["vm", "get-instance-view",
                   "--resource-group", RG, "--name", vm_name])


def get_nsg_rules(vm_name: str) -> dict:
    """Check NSG rules for the VM's NIC."""
    try:
        # Get NIC
        vm = az_cmd(["vm", "show", "--resource-group", RG, "--name", vm_name,
                     "--query", "networkProfile.networkInterfaces[0].id"])
        if not vm:
            return {"rdp_allowed": True, "ssh_allowed": True}
        nic_id = vm if isinstance(vm, str) else str(vm)
        nic_name = nic_id.strip('"').split("/")[-1]

        # Get NSG from NIC
        nic = az_cmd(["network", "nic", "show", "--resource-group", RG,
                      "--name", nic_name,
                      "--query", "{nsg:networkSecurityGroup.id}"])
        if not nic or not nic.get("nsg"):
            return {"rdp_allowed": True, "ssh_allowed": True}

        nsg_name = nic["nsg"].split("/")[-1]

        # Get NSG rules
        rules = az_cmd(["network", "nsg", "rule", "list",
                        "--resource-group", RG, "--nsg-name", nsg_name,
                        "--query", "[].{name:name, access:access, direction:direction, destPort:destinationPortRange, priority:priority}"])

        rdp_blocked = any(
            r.get("access") == "Deny" and r.get("direction") == "Inbound"
            and "3389" in str(r.get("destPort", ""))
            for r in rules
        )
        ssh_blocked = any(
            r.get("access") == "Deny" and r.get("direction") == "Inbound"
            and "22" in str(r.get("destPort", ""))
            for r in rules
        )
        return {"rdp_allowed": not rdp_blocked, "ssh_allowed": not ssh_blocked}
    except Exception as e:
        print(f"    NSG check failed: {e}")
        return {"rdp_allowed": True, "ssh_allowed": True}


def build_telemetry(vm_name: str) -> dict:
    """Collect real telemetry from a VM and build the input dict."""
    print(f"  Collecting telemetry for {vm_name}...")

    # Get instance view
    iv = get_vm_instance_view(vm_name)
    instance_view = iv.get("instanceView", {})
    statuses = instance_view.get("statuses", [])

    # Parse power state
    power_state = "Unknown"
    provisioning_state = "Unknown"
    for s in statuses:
        code = s.get("code", "")
        if code.startswith("PowerState/"):
            ps = code.split("/")[1]
            power_state = {"running": "Running", "stopped": "Stopped",
                           "deallocated": "Deallocated"}.get(ps.lower(), ps.capitalize())
        if code.startswith("ProvisioningState/"):
            prov = code.split("/")[1].lower()
            provisioning_state = {"succeeded": "Succeeded", "failed": "Failed",
                                  "updating": "Succeeded",  # treat Updating as Succeeded for triage
                                  "creating": "Succeeded"}.get(prov, "Unknown")

    # Parse VM agent status
    agent_status = "Unknown"
    vm_agent = instance_view.get("vmAgent", {})
    if vm_agent:
        agent_statuses = vm_agent.get("statuses", [])
        for s in agent_statuses:
            code = s.get("code", "").lower()
            if "ready" in code:
                agent_status = "Healthy"
            elif "notready" in code or "not ready" in code:
                agent_status = "NotReporting"

    # Check heartbeat (agent reporting = heartbeat present)
    heartbeat_present = agent_status == "Healthy"

    # Get NSG info
    nsg = get_nsg_rules(vm_name)

    # Try to get CPU metrics from Azure Monitor
    cpu_percent = None
    try:
        vm_id = iv.get("id", "")
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(minutes=10)
        timespan = f"{start_time.strftime('%Y-%m-%dT%H:%M:%SZ')}/{end_time.strftime('%Y-%m-%dT%H:%M:%SZ')}"

        metrics_json = az_cmd([
            "monitor", "metrics", "list",
            "--resource", vm_id,
            "--metric", "Percentage CPU",
            "--interval", "PT1M",
            "--start-time", start_time.strftime('%Y-%m-%dT%H:%M:%SZ'),
            "--end-time", end_time.strftime('%Y-%m-%dT%H:%M:%SZ'),
            "--query", "value[0].timeseries[0].data[-1].average"
        ])
        if metrics_json is not None:
            cpu_percent = round(float(metrics_json), 1)
    except Exception as e:
        print(f"    CPU metrics unavailable: {e}")

    # Build telemetry
    telemetry = {
        "power_state": power_state,
        "provisioning_state": provisioning_state,
        "resource_health_status": "Available" if power_state == "Running" else "Degraded",
        "resource_health_annotation": None,
        "heartbeat_present": heartbeat_present,
        "heartbeat_last_received": datetime.now(timezone.utc).isoformat() if heartbeat_present else None,
        "boot_diagnostics_status": "Normal",
        "boot_diagnostics_error": None,
        "azure_vm_agent_status": agent_status,
        "cpu_percent": cpu_percent,
        "memory_percent": None,
        "memory_available_mb": None,
        "os_disk_latency_ms": None,
        "data_disk_latency_ms": None,
        "os_disk_percent_full": None,
        "app_health_status": "Unknown",
        "app_error_message": None,
        "nsg_allow_rdp_3389": nsg["rdp_allowed"],
        "nsg_allow_ssh_22": nsg["ssh_allowed"],
        "connection_troubleshoot_rdp": "Allow" if nsg["rdp_allowed"] else "Deny",
        "connection_troubleshoot_ssh": "Allow" if nsg["ssh_allowed"] else "Deny",
        "connection_troubleshoot_verdict": "Reachable",
        "monitor_agent_status": "Unknown",
        "ssl_cert_days_remaining": None,
        "last_backup_status": "Unknown",
        "last_backup_time": None,
    }

    print(f"    Power={power_state}, Agent={agent_status}, CPU={cpu_percent}%, "
          f"RDP={'Allow' if nsg['rdp_allowed'] else 'DENY'}, "
          f"SSH={'Allow' if nsg['ssh_allowed'] else 'DENY'}")
    return telemetry


def run_triage(vm_name: str, telemetry: dict):
    """Run the copilot triage engine on collected telemetry."""
    # Filter out None values for fields that aren't set
    filtered = {k: v for k, v in telemetry.items() if v is not None}

    try:
        tel = TelemetryInput(**filtered)
    except Exception as e:
        print(f"    Validation error: {e}")
        return None

    scorer = ConfidenceScorer()
    engine = DecisionEngine()

    completeness, confidence, conflicts = scorer.score_telemetry(tel)
    decision = engine.decide(tel, confidence, completeness)

    print(f"\n  {'='*50}")
    print(f"  TRIAGE RESULT: {vm_name}")
    print(f"  {'='*50}")
    print(f"  Decision:     {decision.state.value}")
    print(f"  Diagnosis:    {decision.diagnosis}")
    print(f"  Confidence:   {confidence:.2f}")
    print(f"  Completeness: {completeness:.1f}%")
    print(f"  Conflicts:    {conflicts}")
    print(f"  Next check:   {decision.next_check}")
    if hasattr(decision, 'safety_rules_applied') and decision.safety_rules_applied:
        print(f"  Safety rules: {', '.join(decision.safety_rules_applied)}")
    print(f"  Evidence:     {decision.evidence[:3]}")
    print(f"  {'='*50}\n")

    return {
        "vm": vm_name,
        "decision": decision.state.value,
        "diagnosis": decision.diagnosis,
        "confidence": confidence,
        "completeness": completeness,
        "next_check": decision.next_check,
    }


def main():
    print("=" * 60)
    print("Azure VM Incident Copilot — Resource Group Scanner")
    print(f"Subscription: {SUBSCRIPTION}")
    print(f"Resource Group: {RG}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # List all VMs
    print("\nDiscovering VMs...")
    vms = list_vms()
    print(f"Found {len(vms)} VMs: {[v['name'] for v in vms]}\n")

    # Triage each VM
    results = []
    for vm in vms:
        vm_name = vm["name"]
        print(f"\n{'─'*60}")
        print(f"Processing: {vm_name} ({vm.get('vmSize', '?')})")
        print(f"{'─'*60}")
        try:
            telemetry = build_telemetry(vm_name)
            result = run_triage(vm_name, telemetry)
            if result:
                results.append(result)
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({"vm": vm_name, "error": str(e)})

    # Summary
    print("\n" + "=" * 60)
    print("SCAN SUMMARY")
    print("=" * 60)
    for r in results:
        if "error" in r:
            print(f"  {r['vm']:20s} ERROR: {r['error']}")
        else:
            print(f"  {r['vm']:20s} → {r['decision']:30s} (conf={r['confidence']:.2f})")
            print(f"  {'':20s}   {r['diagnosis']}")
    print("=" * 60)

    # Save results
    os.makedirs("results", exist_ok=True)
    out_path = f"results/scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
