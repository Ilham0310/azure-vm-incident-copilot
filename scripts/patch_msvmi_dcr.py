#!/usr/bin/env python3
"""
Patch MSVMI-westeurope-testvm2 DCR to send InsightsMetrics to monitor1.

Current state:  InsightsMetrics → LogAnalytics (wrong)
Target state:   InsightsMetrics → monitor1     (correct)

Run once, then verify with: python scripts/debug_workspace_mapping_cli.py
"""
import subprocess, json, sys, os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

SUB  = os.getenv("AZURE_SUBSCRIPTION_ID", "be8946da-5ca2-4129-ae53-b6124a0aa2d1")
RG   = "az26poc1-co-lab"
DCR  = "MSVMI-westeurope-testvm2"
# monitor1 workspace details
MONITOR_WS_CUSTOMER_ID  = os.getenv("MONITOR_WORKSPACE_ID",  "cb2efd90-7264-4099-8194-85fa04327150")
MONITOR_WS_RESOURCE_ID  = (
    f"/subscriptions/{SUB}/resourceGroups/{RG}"
    f"/providers/microsoft.operationalinsights/workspaces/monitor1"
)

# New DCR body — same as current but destination changed to monitor1
new_body = {
    "location": "westeurope",
    "properties": {
        "dataSources": {
            "performanceCounters": [
                {
                    "counterSpecifiers": ["\\VmInsights\\DetailedMetrics"],
                    "name": "Microsoft-InsightsMetrics",
                    "samplingFrequencyInSeconds": 60,
                    "streams": ["Microsoft-InsightsMetrics"]
                }
            ]
        },
        "destinations": {
            "logAnalytics": [
                {
                    "name": "vmInsightworkspace",
                    "workspaceId": MONITOR_WS_CUSTOMER_ID,
                    "workspaceResourceId": MONITOR_WS_RESOURCE_ID
                }
            ]
        },
        "dataFlows": [
            {
                "streams": ["Microsoft-InsightsMetrics"],
                "destinations": ["vmInsightworkspace"]
            }
        ]
    }
}

body_str = json.dumps(new_body)
url = (
    f"https://management.azure.com/subscriptions/{SUB}"
    f"/resourceGroups/{RG}/providers/Microsoft.Insights"
    f"/dataCollectionRules/{DCR}?api-version=2022-06-01"
)

# Write body to temp file to avoid shell quoting issues
body_file = "scripts/_dcr_patch_body.json"
with open(body_file, "w") as f:
    json.dump(new_body, f)

print(f"Patching DCR '{DCR}' destination → monitor1 ({MONITOR_WS_CUSTOMER_ID[:8]}...)")

cmd = f'az rest --method PUT --url "{url}" --body @{body_file} --output json'
result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)

if result.returncode != 0:
    print(f"[ERROR] Patch failed: {result.stderr[:300]}")
    sys.exit(1)

resp = json.loads(result.stdout or "{}")
dest = (resp.get("properties") or {}).get("destinations", {}).get("logAnalytics", [])
if dest:
    ws_id = dest[0].get("workspaceId", "")
    ws_name = dest[0].get("workspaceResourceId", "").split("/")[-1]
    print(f"[OK] DCR now sends InsightsMetrics to workspace '{ws_name}' (customerId={ws_id})")
    if ws_id == MONITOR_WS_CUSTOMER_ID:
        print("[OK] Destination matches MONITOR_WORKSPACE_ID — patch successful.")
    else:
        print(f"[WARN] Destination customerId {ws_id} != MONITOR_WORKSPACE_ID {MONITOR_WS_CUSTOMER_ID}")
else:
    print("[WARN] Could not verify destination from response.")
