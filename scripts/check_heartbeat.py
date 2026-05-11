"""Check which workspace has Heartbeat data."""
import os, sys, ssl, warnings
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''
ssl._create_default_https_context = ssl._create_unverified_context
warnings.filterwarnings('ignore')

from dotenv import load_dotenv; load_dotenv()
from datetime import datetime, timedelta, timezone
from azure.identity import AzureCliCredential
from azure.monitor.query import LogsQueryClient

cred = AzureCliCredential()
client = LogsQueryClient(cred, connection_verify=False)

MONITOR_ID = os.getenv('MONITOR_WORKSPACE_ID', 'cb2efd90-7264-4099-8194-85fa04327150')
LOGS_ID    = os.getenv('LOG_ANALYTICS_WORKSPACE_ID', '5d10cace-7461-4f3d-89ae-e9fc3405e7c9')

end = datetime.now(timezone.utc)
start = end - timedelta(hours=1)
query = "Heartbeat | where TimeGenerated > ago(1h) | summarize count=count(), lastbeat=max(TimeGenerated)"

for label, ws_id in [("monitor1", MONITOR_ID), ("LogAnalytics", LOGS_ID)]:
    try:
        resp = client.query_workspace(workspace_id=ws_id, query=query, timespan=(start, end))
        if resp.tables and resp.tables[0].rows:
            row = resp.tables[0].rows[0]
            print(f"[{label}] Heartbeat count={row[0]}, last={row[1]}")
        else:
            print(f"[{label}] Heartbeat: 0 rows")
    except Exception as e:
        print(f"[{label}] Error: {e}")
