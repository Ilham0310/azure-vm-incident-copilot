"""Check for Recovery Services Vaults and Key Vaults in subscription."""
import os, sys, ssl, warnings
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

# Recovery Services Vaults
q1 = "Resources | where type =~ 'microsoft.recoveryservices/vaults' | project name, resourceGroup | take 5"
req = QueryRequest(subscriptions=[SUB], query=q1)
resp = client.resources(req)
print("Recovery Services Vaults:")
if resp.data:
    for r in resp.data:
        print(f"  {r.get('name')} in {r.get('resourceGroup')}")
else:
    print("  None found in subscription")

# Key Vaults
q2 = "Resources | where type =~ 'microsoft.keyvault/vaults' | where resourceGroup =~ 'AZ26POC1-CO-LAB' | project name, resourceGroup"
req2 = QueryRequest(subscriptions=[SUB], query=q2)
resp2 = client.resources(req2)
print("\nKey Vaults in AZ26POC1-CO-LAB:")
if resp2.data:
    for r in resp2.data:
        print(f"  {r.get('name')}")
else:
    print("  None found")
