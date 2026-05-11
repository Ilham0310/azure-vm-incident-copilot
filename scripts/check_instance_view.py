"""Check VM instance view via az rest."""
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

url = (
    f"https://management.azure.com/subscriptions/{SUB}"
    f"/resourceGroups/{RG}/providers/Microsoft.Compute"
    f"/virtualMachines/{VM}/instanceView?api-version=2023-03-01"
)
result = subprocess.run(
    f'az rest --method GET --url "{url}" --output json',
    shell=True, capture_output=True, text=True, timeout=20
)
if result.returncode == 0:
    data = json.loads(result.stdout)
    print("=== Statuses ===")
    for s in data.get('statuses', []):
        print(f"  code={s.get('code')} display={s.get('displayStatus')}")
    print("\n=== VM Agent ===")
    agent = data.get('vmAgent', {})
    print(f"  status: {agent.get('statuses', [{}])[0].get('displayStatus') if agent else 'N/A'}")
    print("\n=== Boot Diagnostics ===")
    bd = data.get('bootDiagnostics', {})
    print(f"  status: {bd.get('status', {}).get('code') if bd else 'N/A'}")
    print("\n=== Extensions ===")
    for ext in data.get('extensions', []):
        print(f"  {ext.get('name')}: {ext.get('statuses', [{}])[0].get('displayStatus')}")
else:
    print(f"Error: {result.stderr[:300]}")
