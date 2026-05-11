"""Check memory metrics available in InsightsMetrics."""
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

# Check all Memory metric names
q = "InsightsMetrics | where TimeGenerated > ago(30m) | where Namespace == 'Memory' | summarize avg(Val) by Name"
resp = client.query_workspace(workspace_id=MONITOR_ID, query=q, timespan=(start, end))
if resp.tables and resp.tables[0].rows:
    cols = [c if isinstance(c, str) else c.name for c in resp.tables[0].columns]
    print("Memory metrics available:")
    for row in resp.tables[0].rows:
        print(f"  {dict(zip(cols, row))}")

# Also check VM size from ARG for total memory
from azure.identity import AzureCliCredential as Cred2
from azure.mgmt.resourcegraph import ResourceGraphClient
from azure.mgmt.resourcegraph.models import QueryRequest
SUB = os.getenv('AZURE_SUBSCRIPTION_ID')
VM  = os.getenv('AZURE_VM_NAME', 'testVM2')
RG  = os.getenv('AZURE_RESOURCE_GROUP', 'AZ26POC1-CO-LAB')

cred2 = Cred2()
arg = ResourceGraphClient(cred2)
q2 = (
    "Resources"
    " | where type =~ 'microsoft.compute/virtualmachines'"
    f" | where name =~ '{VM}'"
    f" | where resourceGroup =~ '{RG}'"
    " | project vmSize = tostring(properties.hardwareProfile.vmSize)"
)
req = QueryRequest(subscriptions=[SUB], query=q2)
resp2 = arg.resources(req)
if resp2.data:
    vm_size = resp2.data[0].get('vmSize', '')
    print(f"\nVM Size: {vm_size}")
    print("(Use Azure VM size catalog to get total memory for this size)")
