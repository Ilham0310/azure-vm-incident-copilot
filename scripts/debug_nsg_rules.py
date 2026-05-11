"""Debug NSG rules and NIC-NSG association for testVM2."""
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
NIC_ID = f"/subscriptions/{SUB}/resourceGroups/{RG}/providers/Microsoft.Network/networkInterfaces/testvm2423_z1"

cred = AzureCliCredential()
client = ResourceGraphClient(cred)

# Get NIC details including NSG association
print("=== NIC details ===")
q1 = f"""
Resources
| where type =~ 'microsoft.network/networkinterfaces'
| where id =~ '{NIC_ID}'
| project name, nsgId=tostring(properties.networkSecurityGroup.id),
    ipConfigs=properties.ipConfigurations
"""
req = QueryRequest(subscriptions=[SUB], query=q1)
resp = client.resources(req)
if resp.data:
    row = resp.data[0]
    print(f"NIC: {row.get('name')}")
    print(f"NSG: {row.get('nsgId')}")
    print(f"IPs: {json.dumps(row.get('ipConfigs'), indent=2, default=str)[:300]}")

# Get NSG rules for testVM2-nsg
print("\n=== testVM2-nsg rules ===")
q2 = f"""
Resources
| where type =~ 'microsoft.network/networksecuritygroups'
| where name =~ 'testVM2-nsg'
| where resourceGroup =~ '{RG}'
| mv-expand rule = properties.securityRules
| project
    ruleName = tostring(rule.name),
    direction = tostring(rule.properties.direction),
    access = tostring(rule.properties.access),
    port = tostring(rule.properties.destinationPortRange),
    priority = toint(rule.properties.priority)
| order by priority asc
"""
req2 = QueryRequest(subscriptions=[SUB], query=q2)
resp2 = client.resources(req2)
if resp2.data:
    for row in resp2.data:
        print(f"  {row.get('ruleName'):30} dir={row.get('direction'):8} access={row.get('access'):5} port={row.get('port'):10} pri={row.get('priority')}")
else:
    print("No rules found")
