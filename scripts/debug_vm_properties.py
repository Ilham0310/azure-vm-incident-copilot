"""Dump raw VM properties from ARG to find correct field paths."""
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

# Get raw properties to understand the structure
query = f"""
Resources
| where type =~ 'microsoft.compute/virtualmachines'
| where name =~ '{VM}'
| where resourceGroup =~ '{RG}'
| project name, properties
"""

print("Fetching raw VM properties from ARG...")
req = QueryRequest(subscriptions=[SUB], query=query)
resp = client.resources(req)
if resp.data:
    row = resp.data[0]
    props = row.get('properties', {})
    # Print key sections
    print("\n=== provisioningState ===")
    print(props.get('provisioningState'))
    
    print("\n=== extended.instanceView keys ===")
    ext = props.get('extended', {})
    iv = ext.get('instanceView', {})
    print(list(iv.keys()))
    
    print("\n=== powerState ===")
    print(json.dumps(iv.get('powerState'), indent=2, default=str))
    
    print("\n=== vmAgent ===")
    print(json.dumps(iv.get('vmAgent'), indent=2, default=str))
    
    print("\n=== bootDiagnostics ===")
    print(json.dumps(iv.get('bootDiagnostics'), indent=2, default=str))
    
    print("\n=== statuses ===")
    print(json.dumps(iv.get('statuses'), indent=2, default=str))
    
    print("\n=== hyperVGeneration / osProfile ===")
    print("osProfile:", list(props.get('osProfile', {}).keys()))
    print("storageProfile:", list(props.get('storageProfile', {}).keys()))
else:
    print("No data returned")
