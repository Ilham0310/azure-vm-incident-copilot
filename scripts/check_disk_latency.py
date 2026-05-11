"""Check disk latency metrics in InsightsMetrics."""
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
start = end - timedelta(hours=1)

# Check LogicalDisk metrics
q = """
InsightsMetrics
| where TimeGenerated > ago(30m)
| where Namespace == 'LogicalDisk'
| summarize avg(Val) by Name
"""
resp = client.query_workspace(workspace_id=MONITOR_ID, query=q, timespan=(start, end))
if resp.tables and resp.tables[0].rows:
    cols = [c if isinstance(c, str) else c.name for c in resp.tables[0].columns]
    print("LogicalDisk metrics:")
    for row in resp.tables[0].rows:
        print(f"  {dict(zip(cols, row))}")
else:
    print("No LogicalDisk data")

# Check Network metrics
q2 = """
InsightsMetrics
| where TimeGenerated > ago(30m)
| where Namespace == 'Network'
| summarize avg(Val) by Name
"""
resp2 = client.query_workspace(workspace_id=MONITOR_ID, query=q2, timespan=(start, end))
if resp2.tables and resp2.tables[0].rows:
    cols2 = [c if isinstance(c, str) else c.name for c in resp2.tables[0].columns]
    print("\nNetwork metrics:")
    for row in resp2.tables[0].rows:
        print(f"  {dict(zip(cols2, row))}")
