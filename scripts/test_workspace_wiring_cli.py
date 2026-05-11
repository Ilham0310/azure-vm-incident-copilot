#!/usr/bin/env python3
"""
Workspace Wiring Self-Test (Azure CLI login)

Validates that both Log Analytics workspaces are reachable and contain
the expected tables for the dual-workspace VM Insights setup:

  monitor1      -> InsightsMetrics, VMComputer  (VM Insights data)
  loganalytics  -> Heartbeat                    (agent heartbeat + logs)

Prerequisites:
  1. Run `az login` in your terminal first.
  2. Set MONITOR_WORKSPACE_ID and LOG_ANALYTICS_WORKSPACE_ID in .env
     (or export them as environment variables).

Exit codes:
  0  All checks passed (warnings are OK).
  1  Configuration or Azure CLI error (cannot proceed).
  2  One or more workspace queries failed.

Usage:
  python scripts/test_workspace_wiring_cli.py
"""

import subprocess
import json
import sys
import os
import ssl
import warnings
from datetime import datetime, timedelta, timezone

# Corporate proxy SSL workaround
os.environ["CURL_CA_BUNDLE"] = ""
os.environ["REQUESTS_CA_BUNDLE"] = ""
ssl._create_default_https_context = ssl._create_unverified_context
warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Optional: load .env if python-dotenv is available
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

# Add project root to path so we can import agent.config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.config import AgentConfig


# ---------------------------------------------------------------------------
# Azure CLI login check (subprocess — lightweight, no SDK needed)
# ---------------------------------------------------------------------------

def _check_az_login():
    """
    Verify Azure CLI is installed and the user is logged in.

    Returns:
        (ok, info_line)
    """
    try:
        result = subprocess.run(
            "az account show --output json",
            shell=True, capture_output=True, text=True, timeout=15
        )
    except FileNotFoundError:
        return False, "Azure CLI 'az' is not installed or not on PATH."
    except subprocess.TimeoutExpired:
        return False, "'az account show' timed out (15s)."

    if result.returncode != 0:
        snippet = (result.stderr or "").strip()
        if len(snippet) > 200:
            snippet = snippet[:200] + "..."
        return False, f"Azure CLI is not logged in: {snippet}"

    try:
        acct = json.loads(result.stdout)
        name = acct.get("name", "<unknown>")
        sub_id = acct.get("id", "<unknown>")
        return True, f"subscription='{name}' ({sub_id})"
    except Exception:
        return True, "(could not parse account details)"


# ---------------------------------------------------------------------------
# KQL runner using Azure SDK (same as collector.py)
# ---------------------------------------------------------------------------

def _run_kql(workspace_id, query):
    """
    Execute a KQL query against a Log Analytics workspace using the
    Azure SDK with AzureCliCredential (current az login context).

    Returns:
        (success, rows, error_message)
        - success:       True if query ran successfully.
        - rows:          list[dict] of result rows, or [] on failure.
        - error_message: '' on success, short human-readable string otherwise.
    """
    try:
        from azure.identity import AzureCliCredential
        from azure.monitor.query import LogsQueryClient
    except ImportError as e:
        return False, [], (
            f"Azure SDK not installed: {e}. "
            "Run: pip install azure-identity azure-monitor-query"
        )

    try:
        credential = AzureCliCredential()
        # Disable SSL verification for corporate proxy environments
        import httpx
        transport = httpx.HTTPTransport(verify=False)
        http_client = httpx.Client(transport=transport)
        
        # LogsQueryClient doesn't accept http_client directly,
        # so we pass connection_verify=False via kwargs
        client = LogsQueryClient(credential, connection_verify=False)

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(minutes=60)

        response = client.query_workspace(
            workspace_id=workspace_id,
            query=query,
            timespan=(start_time, end_time)
        )

        if response.tables and len(response.tables) > 0:
            table = response.tables[0]
            # Handle both SDK versions: columns may be objects with .name or plain strings
            columns = []
            for col in table.columns:
                if hasattr(col, 'name'):
                    columns.append(col.name)
                else:
                    columns.append(str(col))
            rows = [
                dict(zip(columns, row))
                for row in table.rows
            ]
            return True, rows, ""

        return True, [], ""

    except Exception as e:
        err_str = str(e)
        if len(err_str) > 300:
            err_str = err_str[:300] + "..."
        return False, [], err_str


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if load_dotenv is not None:
        load_dotenv()

    print("=" * 64)
    print("Workspace Wiring Self-Test")
    print("=" * 64)

    # ---- Config ----------------------------------------------------------
    try:
        config = AgentConfig.from_env()
    except ValueError as exc:
        print(f"[CONFIG ERROR] {exc}")
        print("[CONFIG ERROR] Set AZURE_SUBSCRIPTION_ID, AZURE_RESOURCE_GROUP, "
              "and AZURE_VM_NAME in .env or environment.")
        return 1

    ws_errors = config.validate_workspaces()
    if ws_errors:
        for msg in ws_errors:
            print(f"[CONFIG ERROR] {msg}")
        return 1

    print(f"[OK] Config loaded: VM={config.vm_name}, RG={config.resource_group}")
    print(f"[OK] monitor workspace  : {config.monitor_workspace_name} "
          f"({config.monitor_workspace_id})")
    print(f"[OK] loganalytics workspace: {config.log_analytics_workspace_name} "
          f"({config.log_analytics_workspace_id})")

    # ---- Azure CLI login -------------------------------------------------
    print(f"\n[CHECK] Azure CLI login status")
    az_ok, az_info = _check_az_login()
    if not az_ok:
        print(f"[AZ ERROR] {az_info}")
        print("[AZ ERROR] Run 'az login' in your terminal first.")
        return 1
    print(f"[OK] Azure CLI is available and authenticated: {az_info}")

    monitor_id = config.monitor_workspace_id
    logs_id = config.log_analytics_workspace_id
    overall_errors = 0

    # ---- monitor1: InsightsMetrics ---------------------------------------
    print(f"\n[CHECK] {config.monitor_workspace_name} ({monitor_id}) "
          f"-> InsightsMetrics")
    ok, rows, err = _run_kql(monitor_id, (
        "InsightsMetrics "
        "| where TimeGenerated > ago(30m) "
        "| take 5"
    ))
    if not ok:
        print(f"  [ERROR] {config.monitor_workspace_name}: "
              f"failed to query InsightsMetrics: {err}")
        overall_errors += 1
    elif not rows:
        print(f"  [WARN] {config.monitor_workspace_name}: InsightsMetrics "
              "reachable but returned no rows in last 30m.")
        print(f"  [WARN] This is normal for a newly created workspace. "
              "VM Insights needs 10-15 min to populate.")
    else:
        print(f"  [OK] {config.monitor_workspace_name}: InsightsMetrics "
              f"returned {len(rows)} row(s).")

    # ---- monitor1: VMComputer --------------------------------------------
    print(f"\n[CHECK] {config.monitor_workspace_name} ({monitor_id}) "
          f"-> VMComputer")
    ok, rows, err = _run_kql(monitor_id, (
        "VMComputer "
        "| where TimeGenerated > ago(60m) "
        "| summarize arg_max(TimeGenerated, *) by Computer "
        "| take 1"
    ))
    if not ok:
        print(f"  [ERROR] {config.monitor_workspace_name}: "
              f"failed to query VMComputer: {err}")
        overall_errors += 1
    elif not rows:
        print(f"  [WARN] {config.monitor_workspace_name}: VMComputer "
              "reachable but returned no rows in last 60m.")
        print(f"  [WARN] VMComputer populates after VM Insights onboarding (~15 min).")
    else:
        row = rows[0]
        computer = row.get("Computer", "<unknown>")
        mem_mb = row.get("PhysicalMemoryMB", "<unknown>")
        print(f"  [OK] {config.monitor_workspace_name}: VMComputer has entry "
              f"for Computer={computer}, PhysicalMemoryMB={mem_mb}.")

    # ---- loganalytics: Heartbeat -----------------------------------------
    print(f"\n[CHECK] {config.log_analytics_workspace_name} ({logs_id}) "
          f"-> Heartbeat")
    ok, rows, err = _run_kql(logs_id, (
        "Heartbeat "
        "| where TimeGenerated > ago(30m) "
        "| take 5"
    ))
    if not ok:
        print(f"  [ERROR] {config.log_analytics_workspace_name}: "
              f"failed to query Heartbeat: {err}")
        overall_errors += 1
    elif not rows:
        print(f"  [WARN] {config.log_analytics_workspace_name}: Heartbeat "
              "reachable but returned no rows in last 30m.")
        print(f"  [WARN] AMA may still be syncing — wait 10-15 minutes after agent install.")
    else:
        print(f"  [OK] {config.log_analytics_workspace_name}: Heartbeat "
              f"returned {len(rows)} row(s).")

    # ---- Summary ---------------------------------------------------------
    print("\n" + "=" * 64)
    if overall_errors > 0:
        print(f"[SUMMARY] Completed with {overall_errors} error(s). "
              "See [ERROR] lines above.")
        return 2

    print("[SUMMARY] Workspace wiring looks healthy.")
    print("[SUMMARY] Any [WARN] above indicates empty tables — "
          "common immediately after onboarding (wait 10-15 min).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
