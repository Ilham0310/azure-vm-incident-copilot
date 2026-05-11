"""Check VMComputer and InsightsMetrics data in monitor1."""
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
MONITOR_ID = os.getenv('MONITOR_WORKSPACE_ID')
end = datetime.now(timezone.utc)
start = end - timedelta(hours=2)

for q, label in [
    ("VMComputer | where TimeGenerated > ago(2h) | summarize count=count(), lastSeen=max(TimeGenerated)", "VMComputer"),
    ("InsightsMetrics | where TimeGenerated > ago(30m) | where Namespace == 'Memory' | summarize count=count(), avgVal=avg(Val)", "InsightsMetrics Memory"),
    ("InsightsMetrics | where TimeGenerated > ago(30m) | summarize by Namespace", "InsightsMetrics Namespaces"),
]:
    try:
        resp = client.query_workspace(workspace_id=MONITOR_ID, query=q, timespan=(start, end))
        if resp.tables and resp.tables[0].rows:
            cols = [c if isinstance(c, str) else c.name for c in resp.tables[0].columns]
            for row in resp.tables[0].rows:
                print(f"[{label}] {dict(zip(cols, row))}")
        else:
            print(f"[{label}] No data")
    except Exception as e:
        print(f"[{label}] Error: {e}")
