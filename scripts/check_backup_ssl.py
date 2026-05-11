"""Check backup and SSL resources for testVM2."""
import os, sys, ssl, warnings, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''
ssl._create_default_https_context = ssl._create_unverified_context
warnings.filterwarnings('ignore')

from dotenv import load_dotenv; load_dotenv()
from azure.identity import AzureCliCredential
from azure.mgmt.resourcegraph import ResourceGraphClient
from azure.mgmt.resourcegraph.models import QueryRequest

SUB = os.getenv('AZURE_SUBSCRIPTION_ID')
VM  = os.getenv('AZURE_VM_NAME', 'testVM2')
RG  = os.getenv('AZURE_RESOURCE_GROUP', 'AZ26POC1-CO-LAB')

cred = AzureCliCredential()
client = ResourceGraphClient(cred)

# Check Recovery Services Vaults in RG
print("=== Recovery Services Vaults ===")
q1 = f"""
Resources
| where type =~ 'microsoft.recoveryservices/vaults'
| where resourceGroup =~ '{RG}'
| project name, id
"""
req = QueryRequest(subscriptions=[SUB], query=q1)
resp = client.resources(req)
if resp.data:
    for row in resp.data:
        print(f"  Vault: {row.get('name')}")
else:
    print("  No Recovery Services Vaults found in RG")

# Check Key Vaults in RG
print("\n=== Key Vaults ===")
q2 = f"""
Resources
| where type =~ 'microsoft.keyvault/vaults'
| where resourceGroup =~ '{RG}'
| project name, id
"""
req2 = QueryRequest(subscriptions=[SUB], query=q2)
resp2 = client.resources(req2)
if resp2.data:
    for row in resp2.data:
        print(f"  KeyVault: {row.get('name')}")
else:
    print("  No Key Vaults found in RG")

# Check app health extension
print("\n=== VM Extensions ===")
q3 = f"""
Resources
| where type =~ 'microsoft.compute/virtualmachines/extensions'
| where resourceGroup =~ '{RG}'
| where name contains '{VM}'
| project name, extType=tostring(properties.type)
"""
req3 = QueryRequest(subscriptions=[SUB], query=q3)
resp3 = client.resources(req3)
if resp3.data:
    for row in resp3.data:
        print(f"  Extension: {row.get('name')} | type: {row.get('extType')}")
else:
    print("  No extensions found")
