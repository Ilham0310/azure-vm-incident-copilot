"""Debug what the ARG query actually returns for testVM2."""
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

# Simplified query — just get the raw VM properties first
query = f"""
Resources
| where type =~ 'microsoft.compute/virtualmachines'
| where name =~ '{VM}'
| where resourceGroup =~ '{RG}'
| extend
    power_state = tostring(properties.extended.instanceView.powerState.code),
    prov_state  = tostring(properties.provisioningState),
    vm_agent    = tostring(properties.extended.instanceView.vmAgent.statuses[0].displayStatus),
    boot_diag   = tostring(properties.extended.instanceView.bootDiagnostics.status.code),
    boot_error  = tostring(properties.extended.instanceView.bootDiagnostics.consoleScreenshotBlobUri)
| project name, power_state, prov_state, vm_agent, boot_diag, boot_error
"""

print("Running simplified ARG query...")
req = QueryRequest(subscriptions=[SUB], query=query)
resp = client.resources(req)
if resp.data:
    row = resp.data[0]
    print(json.dumps(dict(row), indent=2, default=str))
else:
    print("No data returned")
