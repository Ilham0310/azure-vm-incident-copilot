"""Check host metrics via MetricsQueryClient."""
import os, sys, ssl, warnings
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''
ssl._create_default_https_context = ssl._create_unverified_context
warnings.filterwarnings('ignore')

from dotenv import load_dotenv; load_dotenv()
from datetime import datetime, timedelta, timezone
from azure.identity import AzureCliCredential
from azure.monitor.query import MetricsQueryClient, MetricAggregationType

SUB = os.getenv('AZURE_SUBSCRIPTION_ID')
VM  = os.getenv('AZURE_VM_NAME', 'testVM2')
RG  = os.getenv('AZURE_RESOURCE_GROUP', 'AZ26POC1-CO-LAB')

vm_resource_id = (
    f"/subscriptions/{SUB}/resourceGroups/{RG}"
    f"/providers/Microsoft.Compute/virtualMachines/{VM}"
)

cred = AzureCliCredential()
client = MetricsQueryClient(cred, connection_verify=False)

end = datetime.now(timezone.utc)
start = end - timedelta(minutes=10)

for metric_name in [
    "OS Disk Read Operations/Sec",
    "OS Disk Write Operations/Sec",
    "Data Disk Read Operations/Sec",
    "Disk Read Operations/Sec",
    "Disk Write Operations/Sec",
    "Percentage CPU",
    "Available Memory Bytes",
]:
    try:
        resp = client.query_resource(
            resource_uri=vm_resource_id,
            metric_names=[metric_name],
            timespan=(start, end),
            aggregations=[MetricAggregationType.AVERAGE]
        )
        if resp.metrics and resp.metrics[0].timeseries:
            ts = resp.metrics[0].timeseries[0]
            if ts.data:
                val = ts.data[-1].average
                print(f"  {metric_name}: {val}")
            else:
                print(f"  {metric_name}: no data points")
        else:
            print(f"  {metric_name}: no timeseries")
    except Exception as e:
        print(f"  {metric_name}: ERROR {str(e)[:80]}")
