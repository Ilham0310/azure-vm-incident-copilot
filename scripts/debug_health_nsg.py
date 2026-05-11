"""Debug health resource and NSG data for testVM2."""
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

# 1. Health resource
print("=== Health Resource ===")
q1 = f"""
HealthResources
| where type =~ 'microsoft.resourcehealth/availabilitystatuses'
| where resourceGroup =~ '{RG}'
| where name contains '{VM}'
| project name, properties
| take 3
"""
req = QueryRequest(subscriptions=[SUB], query=q1)
resp = client.resources(req)
if resp.data:
    for row in resp.data:
        print(json.dumps(dict(row), indent=2, default=str))
else:
    print("No health resources found")

# 2. NSG in the RG
print("\n=== NSG Resources ===")
q2 = f"""
Resources
| where type =~ 'microsoft.network/networksecuritygroups'
| where resourceGroup =~ '{RG}'
| project name, id
"""
req2 = QueryRequest(subscriptions=[SUB], query=q2)
resp2 = client.resources(req2)
if resp2.data:
    for row in resp2.data:
        print(f"NSG: {row.get('name')} | id: {row.get('id', '')[:80]}")
else:
    print("No NSGs found in RG")

# 3. VM NIC and NSG association
print("\n=== VM Network Interface ===")
q3 = f"""
Resources
| where type =~ 'microsoft.compute/virtualmachines'
| where name =~ '{VM}'
| where resourceGroup =~ '{RG}'
| extend nics = properties.networkProfile.networkInterfaces
| project name, nics
"""
req3 = QueryRequest(subscriptions=[SUB], query=q3)
resp3 = client.resources(req3)
if resp3.data:
    print(json.dumps(dict(resp3.data[0]), indent=2, default=str))
