"""Check disk I/O metrics via az rest."""
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

# Try different disk metric names
for metric in ["OS Disk Read Bytes/sec", "OS Disk Write Bytes/sec",
               "Disk Read Bytes", "Disk Write Bytes",
               "OS Disk Read Operations/Sec", "OS Disk Write Operations/Sec"]:
    encoded = metric.replace(' ', '%20').replace('/', '%2F')
    url = (
        f"https://management.azure.com/subscriptions/{SUB}"
        f"/resourceGroups/{RG}/providers/Microsoft.Compute/virtualMachines/{VM}"
        f"/providers/microsoft.insights/metrics"
        f"?api-version=2023-10-01&metricnames={encoded}&aggregation=Average&timespan=PT5M"
    )
    r = subprocess.run(f'az rest --method GET --url "{url}" --output json',
                       shell=True, capture_output=True, text=True, timeout=15)
    if r.returncode == 0:
        d = json.loads(r.stdout or '{}')
        for m in d.get('value', []):
            ts = m.get('timeseries', [])
            val = ts[0]['data'][-1].get('average') if ts and ts[0].get('data') else None
            print(f"  {m['name']['value']}: {val}")
    else:
        print(f"  {metric}: ERROR")
