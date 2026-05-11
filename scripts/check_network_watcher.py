"""Check Network Watcher availability for connection troubleshoot."""
import os, sys, ssl, warnings, json, subprocess
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
RG  = os.getenv('AZURE_RESOURCE_GROUP', 'AZ26POC1-CO-LAB')

cred = AzureCliCredential()
client = ResourceGraphClient(cred)

# Check Network Watchers
q = "Resources | where type =~ 'microsoft.network/networkwatchers' | project name, resourceGroup, location"
req = QueryRequest(subscriptions=[SUB], query=q)
resp = client.resources(req)
if resp.data:
    for row in resp.data:
        print(f"NetworkWatcher: {row.get('name')} | rg={row.get('resourceGroup')} | loc={row.get('location')}")
else:
    print("No Network Watchers found")

# Check VM's NIC public IP
q2 = (
    "Resources"
    " | where type =~ 'microsoft.network/networkinterfaces'"
    " | where name =~ 'testvm2423_z1'"
    " | extend pip = tostring(properties.ipConfigurations[0].properties.publicIPAddress.id)"
    " | project name, pip"
)
req2 = QueryRequest(subscriptions=[SUB], query=q2)
resp2 = client.resources(req2)
if resp2.data:
    print(f"\nNIC public IP ref: {resp2.data[0].get('pip', 'None')}")
