"""Quick test of Azure Resource Graph SDK connectivity."""
import os, ssl, warnings, sys
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''
ssl._create_default_https_context = ssl._create_unverified_context
warnings.filterwarnings('ignore')

from dotenv import load_dotenv; load_dotenv()
from azure.identity import AzureCliCredential
from azure.mgmt.resourcegraph import ResourceGraphClient
from azure.mgmt.resourcegraph.models import QueryRequest

SUB = os.getenv('AZURE_SUBSCRIPTION_ID', 'be8946da-5ca2-4129-ae53-b6124a0aa2d1')
VM  = os.getenv('AZURE_VM_NAME', 'testVM2')
RG  = os.getenv('AZURE_RESOURCE_GROUP', 'AZ26POC1-CO-LAB')

print(f"Testing ARG query for VM={VM}, RG={RG}, Sub={SUB[:8]}...")

try:
    cred = AzureCliCredential()
    client = ResourceGraphClient(cred)
    query = (
        "Resources"
        " | where type =~ 'microsoft.compute/virtualmachines'"
        f" | where name =~ '{VM}'"
        f" | where resourceGroup =~ '{RG}'"
        " | project name, resourceGroup, location"
    )
    req = QueryRequest(subscriptions=[SUB], query=query)
    resp = client.resources(req)
    if resp.data:
        print(f"[OK] ARG returned {len(resp.data)} row(s): {resp.data[0]}")
    else:
        print("[WARN] ARG returned 0 rows — VM not found or no access.")
    sys.exit(0)
except Exception as e:
    print(f"[ERROR] ARG query failed: {e}")
    sys.exit(1)
