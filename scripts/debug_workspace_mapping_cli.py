#!/usr/bin/env python3
"""
Workspace Mapping Debug Audit (Azure CLI login)

Cross-checks:
  1. AgentConfig workspace IDs/names against real Azure resources.
  2. Duplicate workspace names across resource groups.
  3. DCR associations on testVM2 and their destination workspace IDs.

Performance notes:
  - Workspace list is scoped to the VM's resource group first (fast).
  - Falls back to subscription-wide list only if needed.
  - DCR details fetched via az rest (no extension required).

Exit codes:
  0  Everything consistent.
  1  Config errors or name/ID/DCR mismatches found.
  2  Fatal Azure CLI errors (auth, not found, etc.).

Usage:
  python scripts/debug_workspace_mapping_cli.py
"""

import subprocess
import json
import sys
import os
from typing import Optional, List, Dict, Tuple

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent.config import AgentConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_az(cmd: str, timeout: int = 20) -> Tuple[bool, str, str]:
    """Run an Azure CLI command. Returns (success, stdout, stderr_snippet)."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
    except FileNotFoundError:
        return False, "", "Azure CLI 'az' not found on PATH."
    except subprocess.TimeoutExpired:
        return False, "", f"Command timed out after {timeout}s."

    stderr = (result.stderr or "").strip()
    if len(stderr) > 300:
        stderr = stderr[:300] + "..."
    if result.returncode != 0:
        return False, result.stdout, stderr
    return True, result.stdout, ""


def _parse_json(s: str):
    try:
        return json.loads(s or "null")
    except json.JSONDecodeError:
        return None


def _section(title: str):
    print(f"\n{'=' * 64}")
    print(f"  {title}")
    print('=' * 64)


# ---------------------------------------------------------------------------
# Workspace resolution: match customerId against a list of workspace objects
# ---------------------------------------------------------------------------

def _find_by_customer_id(customer_id: str, ws_list: List[Dict]) -> Optional[Dict]:
    for ws in ws_list:
        if ws.get("customerId", "").lower() == customer_id.lower():
            return ws
    return None


def _find_by_name(name: str, ws_list: List[Dict]) -> List[Dict]:
    return [ws for ws in ws_list if ws.get("name", "").lower() == name.lower()]


# ---------------------------------------------------------------------------
# DCR helpers (az rest — no extension required)
# ---------------------------------------------------------------------------

def _get_dcr_associations(sub_id: str, rg: str, vm_name: str) -> Optional[List[Dict]]:
    url = (
        f"https://management.azure.com/subscriptions/{sub_id}"
        f"/resourceGroups/{rg}/providers/Microsoft.Compute"
        f"/virtualMachines/{vm_name}"
        f"/providers/Microsoft.Insights/dataCollectionRuleAssociations"
        f"?api-version=2022-06-01"
    )
    ok, out, err = _run_az(f'az rest --method GET --url "{url}" --output json', timeout=20)
    if not ok:
        print(f"  [ERROR] Failed to list DCR associations: {err or out[:200]}")
        return None
    data = _parse_json(out) or {}
    return data.get("value") or []


def _get_dcr(dcr_resource_id: str) -> Optional[Dict]:
    url = f"https://management.azure.com{dcr_resource_id}?api-version=2022-06-01"
    ok, out, err = _run_az(f'az rest --method GET --url "{url}" --output json', timeout=20)
    if not ok:
        print(f"  [ERROR] Failed to fetch DCR: {err or out[:200]}")
        return None
    return _parse_json(out) or {}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    if load_dotenv is not None:
        load_dotenv()

    print("=" * 64)
    print("  Workspace Mapping Debug Audit")
    print("=" * 64)

    config_errors: int = 0
    mapping_mismatches: int = 0
    fatal_az_errors: int = 0

    # ---- Load config -------------------------------------------------------
    try:
        config = AgentConfig.from_env()
    except ValueError as exc:
        print(f"[CONFIG ERROR] {exc}")
        return 2

    ws_errors = config.validate_workspace_mapping()
    if ws_errors:
        for e in ws_errors:
            print(f"[CONFIG ERROR] {e}")
        config_errors += len(ws_errors)

    print(f"\n[INFO] VM:                           {config.vm_name}")
    print(f"[INFO] Resource Group:               {config.resource_group}")
    print(f"[INFO] Subscription:                 {config.subscription_id}")
    print(f"[INFO] MONITOR_WORKSPACE_ID:         {config.monitor_workspace_id}")
    print(f"[INFO] MONITOR_WORKSPACE_NAME:       {config.monitor_workspace_name}")
    print(f"[INFO] LOG_ANALYTICS_WORKSPACE_ID:   {config.log_analytics_workspace_id}")
    print(f"[INFO] LOG_ANALYTICS_WORKSPACE_NAME: {config.log_analytics_workspace_name}")

    # ---- Step 1: Azure CLI login -------------------------------------------
    _section("Step 1: Azure CLI login")
    ok, out, err = _run_az("az account show --output json", timeout=15)
    if not ok:
        print(f"  [AZ ERROR] 'az account show' failed: {err or out[:200]}")
        print("  [AZ ERROR] Run 'az login' first.")
        return 2
    account = _parse_json(out) or {}
    sub = account.get("id", "<unknown>")
    tenant = account.get("tenantId", "<unknown>")
    sub_name = account.get("name", "<unknown>")
    print(f"  [OK] Authenticated. Subscription='{sub_name}' ({sub}), Tenant={tenant}")

    if sub != config.subscription_id:
        print(f"  [WARN] Active subscription ({sub}) differs from "
              f"AZURE_SUBSCRIPTION_ID ({config.subscription_id}).")
        mapping_mismatches += 1

    # ---- Step 2: Resolve IDs → real workspace objects ----------------------
    _section("Step 2: Resolve configured IDs to real Azure workspaces")

    # Fetch workspace list scoped to the VM's RG first (fast: ~2s vs ~60s)
    ok_rg, out_rg, _ = _run_az(
        f"az monitor log-analytics workspace list "
        f"--resource-group {config.resource_group} --output json",
        timeout=15
    )
    rg_ws_list = _parse_json(out_rg) if ok_rg else []

    # Also fetch subscription-wide for duplicate detection (run in background)
    ok_sub, out_sub, err_sub = _run_az(
        "az monitor log-analytics workspace list --output json",
        timeout=60
    )
    if not ok_sub:
        print(f"  [WARN] Could not list all workspaces subscription-wide: {err_sub}")
        all_ws = rg_ws_list  # fall back to RG-scoped list
    else:
        all_ws = _parse_json(out_sub) or []

    print(f"  [INFO] Workspaces in RG '{config.resource_group}': {len(rg_ws_list)}")
    print(f"  [INFO] Workspaces in subscription: {len(all_ws)}")

    monitor_ws = None
    logs_ws = None

    if config.monitor_workspace_id:
        monitor_ws = _find_by_customer_id(config.monitor_workspace_id, all_ws)
        if monitor_ws:
            name = monitor_ws.get("name")
            rg = monitor_ws.get("resourceGroup")
            print(f"  [OK] MONITOR_WORKSPACE_ID → name='{name}', rg='{rg}'")
        else:
            print(f"  [ERROR] MONITOR_WORKSPACE_ID '{config.monitor_workspace_id}' "
                  "not found in any workspace in this subscription.")
            fatal_az_errors += 1

    if config.log_analytics_workspace_id:
        logs_ws = _find_by_customer_id(config.log_analytics_workspace_id, all_ws)
        if logs_ws:
            name = logs_ws.get("name")
            rg = logs_ws.get("resourceGroup")
            print(f"  [OK] LOG_ANALYTICS_WORKSPACE_ID → name='{name}', rg='{rg}'")
        else:
            print(f"  [ERROR] LOG_ANALYTICS_WORKSPACE_ID '{config.log_analytics_workspace_id}' "
                  "not found in any workspace in this subscription.")
            fatal_az_errors += 1

    # Cross-check: resolved name vs configured name (case-insensitive)
    if monitor_ws:
        resolved = monitor_ws.get("name", "")
        if resolved.lower() != config.monitor_workspace_name.lower():
            print(f"  [MISMATCH] MONITOR_WORKSPACE_ID resolves to name='{resolved}' "
                  f"but MONITOR_WORKSPACE_NAME='{config.monitor_workspace_name}'.")
            print(f"  [FIX] Set MONITOR_WORKSPACE_NAME={resolved} in .env")
            mapping_mismatches += 1
        else:
            print(f"  [OK] MONITOR name consistent: '{resolved}'")

    if logs_ws:
        resolved = logs_ws.get("name", "")
        if resolved.lower() != config.log_analytics_workspace_name.lower():
            print(f"  [MISMATCH] LOG_ANALYTICS_WORKSPACE_ID resolves to name='{resolved}' "
                  f"but LOG_ANALYTICS_WORKSPACE_NAME='{config.log_analytics_workspace_name}'.")
            print(f"  [FIX] Set LOG_ANALYTICS_WORKSPACE_NAME={resolved} in .env")
            mapping_mismatches += 1
        else:
            print(f"  [OK] LOG_ANALYTICS name consistent: '{resolved}'")

    # ---- Step 3: Duplicate name detection ----------------------------------
    _section("Step 3: Duplicate workspace name detection")

    for label, wanted_name, configured_id in [
        ("monitor1",     config.monitor_workspace_name,       config.monitor_workspace_id),
        ("loganalytics", config.log_analytics_workspace_name, config.log_analytics_workspace_id),
    ]:
        matches = _find_by_name(wanted_name, all_ws)
        print(f"\n  [CHECK] Name='{wanted_name}' ({label})")
        if not matches:
            print(f"    [WARN] No workspace found with name='{wanted_name}' "
                  "in this subscription.")
        elif len(matches) == 1:
            ws = matches[0]
            cid = ws.get("customerId", "")
            rg = ws.get("resourceGroup", "")
            print(f"    [OK] Unique. rg='{rg}', customerId={cid}")
            if configured_id and cid.lower() != configured_id.lower():
                print(f"    [MISMATCH] Configured ID ({configured_id}) does NOT match "
                      f"the workspace named '{wanted_name}' (customerId={cid}).")
                mapping_mismatches += 1
            elif configured_id:
                print(f"    [OK] Configured ID matches.")
        else:
            print(f"    [WARN] Name '{wanted_name}' is AMBIGUOUS — "
                  f"found {len(matches)} workspaces:")
            for ws in matches:
                cid = ws.get("customerId", "")
                rg = ws.get("resourceGroup", "")
                marker = " ← configured" if (configured_id and cid.lower() == configured_id.lower()) else ""
                print(f"      - rg='{rg}', customerId={cid}{marker}")
            if configured_id:
                cids = [ws.get("customerId", "").lower() for ws in matches]
                if configured_id.lower() not in cids:
                    print(f"    [MISMATCH] Configured ID ({configured_id}) does not "
                          f"match ANY workspace named '{wanted_name}'.")
                    mapping_mismatches += 1
            mapping_mismatches += 1  # Ambiguity is a risk

    # ---- Step 4: DCR associations on testVM2 -------------------------------
    _section(f"Step 4: DCR associations on {config.vm_name}")

    assocs = _get_dcr_associations(
        config.subscription_id, config.resource_group, config.vm_name
    )
    if assocs is None:
        fatal_az_errors += 1
    elif not assocs:
        print(f"  [WARN] No DCR associations found for {config.vm_name}.")
        print(f"  [WARN] VM Insights may not be enabled — "
              "go to Azure Portal → VM → Insights → Enable.")
    else:
        print(f"  [INFO] {len(assocs)} DCR association(s) found.")

        # Build lookup: workspace ARM resource ID → label
        ws_arm_lookup: Dict[str, str] = {}
        if monitor_ws:
            ws_arm_lookup[monitor_ws.get("id", "").lower()] = (
                f"MONITOR_WORKSPACE_ID ({monitor_ws.get('name')})"
            )
        if logs_ws:
            ws_arm_lookup[logs_ws.get("id", "").lower()] = (
                f"LOG_ANALYTICS_WORKSPACE_ID ({logs_ws.get('name')})"
            )

        for assoc in assocs:
            props = assoc.get("properties") or {}
            dcr_id = props.get("dataCollectionRuleId", "")
            assoc_name = assoc.get("name", "<unnamed>")
            print(f"\n  [CHECK] Association: '{assoc_name}'")

            if not dcr_id:
                print(f"    [WARN] No dataCollectionRuleId in association properties.")
                continue

            dcr_short = dcr_id.split("/")[-1]
            print(f"    [INFO] DCR: '{dcr_short}'")

            dcr = _get_dcr(dcr_id)
            if dcr is None:
                fatal_az_errors += 1
                continue

            dcr_props = dcr.get("properties") or {}
            destinations = dcr_props.get("destinations") or {}
            la_dests = destinations.get("logAnalytics") or []
            az_metrics_dest = destinations.get("azureMonitorMetrics")
            data_flows = dcr_props.get("dataFlows") or []

            # Collect stream names for context
            streams = set()
            for flow in data_flows:
                streams.update(flow.get("streams") or [])
            if streams:
                print(f"    [INFO] Streams: {', '.join(sorted(streams))}")

            if az_metrics_dest and not la_dests:
                # Sends to Azure Monitor Metrics (not Log Analytics) — that's fine
                print(f"    [OK] Destination: Azure Monitor Metrics "
                      f"('{az_metrics_dest.get('name')}') — not a Log Analytics workspace.")
                continue

            if not la_dests:
                print(f"    [WARN] DCR '{dcr_short}' has no logAnalytics destinations.")
                continue

            for dest in la_dests:
                dest_name = dest.get("name", "<unnamed>")
                ws_rid = dest.get("workspaceResourceId", "")
                ws_cid = dest.get("workspaceId", "")
                ws_short = ws_rid.split("/")[-1] if ws_rid else "<unknown>"

                matched_label = ws_arm_lookup.get(ws_rid.lower())
                if matched_label:
                    print(f"    [OK] Destination '{dest_name}' → {matched_label}")
                else:
                    # Try matching by customerId
                    if ws_cid:
                        if monitor_ws and ws_cid.lower() == monitor_ws.get("customerId", "").lower():
                            print(f"    [OK] Destination '{dest_name}' → "
                                  f"MONITOR_WORKSPACE_ID (matched by customerId)")
                            continue
                        if logs_ws and ws_cid.lower() == logs_ws.get("customerId", "").lower():
                            print(f"    [OK] Destination '{dest_name}' → "
                                  f"LOG_ANALYTICS_WORKSPACE_ID (matched by customerId)")
                            continue

                    print(f"    [MISMATCH] DCR '{dcr_short}' destination '{dest_name}' "
                          f"sends to workspace '{ws_short}' which is NEITHER "
                          "MONITOR_WORKSPACE_ID nor LOG_ANALYTICS_WORKSPACE_ID.")
                    print(f"    [MISMATCH] workspaceResourceId: {ws_rid}")
                    mapping_mismatches += 1

    # ---- Summary -----------------------------------------------------------
    _section("SUMMARY")

    if fatal_az_errors > 0:
        print(f"[SUMMARY] Azure CLI errors: {fatal_az_errors}. Fix CLI/auth first.")
    if config_errors > 0:
        print(f"[SUMMARY] Config issues: {config_errors}. See [CONFIG ERROR] lines above.")
    if mapping_mismatches > 0:
        print(f"[SUMMARY] Name/ID/DCR mismatches: {mapping_mismatches}. "
              "See [MISMATCH] lines above.")
    if not (fatal_az_errors or config_errors or mapping_mismatches):
        print("[SUMMARY] Workspace names, IDs, and DCR destinations are consistent.")

    if fatal_az_errors > 0:
        return 2
    if config_errors or mapping_mismatches:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
