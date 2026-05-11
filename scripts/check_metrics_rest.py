"""Check VM metrics via az rest (no SDK extension needed)."""
import os, sys, ssl, warnings, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''
ssl._create_default_https_context = ssl._create_unverified_context
warnings.filterwarnings('ignore')

from dotenv import load_dotenv; load_dotenv()

SUB = os.getenv('AZURE_SUBSCRIPTION_ID')
VM  = os.getenv('AZURE_VM_NAME', 'testVM2')
RG  = os.getenv('AZURE_RESOURCE_GROUP', 'AZ26POC1-CO-LAB')

# Query multiple metrics at once
metrics = "OS Disk Read Bytes/sec,OS Disk Write Bytes/sec,Percentage CPU,Available Memory Bytes"
url = (
    f"https://management.azure.com/subscriptions/{SUB}"
    f"/resourceGroups/{RG}/providers/Microsoft.Compute/virtualMachines/{VM}"
    f"/providers/microsoft.insights/metrics"
    f"?api-version=2023-10-01&metricnames={metrics}&aggregation=Average&timespan=PT5M"
)

result = subprocess.run(
    f'az rest --method GET --url "{url}" --output json',
    shell=True, capture_output=True, text=True, timeout=20
)
if result.returncode == 0:
    data = json.loads(result.stdout)
    for m in data.get('value', []):
        name = m.get('name', {}).get('value', '')
        ts = m.get('timeseries', [])
        if ts and ts[0].get('data'):
            val = ts[0]['data'][-1].get('average')
            print(f"  {name}: {val}")
        else:
            print(f"  {name}: no data")
else:
    print(f"Error: {result.stderr[:200]}")
