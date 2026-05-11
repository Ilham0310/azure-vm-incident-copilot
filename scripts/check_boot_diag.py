"""Check boot diagnostics and instance view via REST API."""
import os, sys, ssl, warnings, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''
ssl._create_default_https_context = ssl._create_unverified_context
warnings.filterwarnings('ignore')

from dotenv import load_dotenv; load_dotenv()
from azure.identity import AzureCliCredential
from azure.mgmt.compute import ComputeManagementClient

SUB = os.getenv('AZURE_SUBSCRIPTION_ID')
VM  = os.getenv('AZURE_VM_NAME', 'testVM2')
RG  = os.getenv('AZURE_RESOURCE_GROUP', 'AZ26POC1-CO-LAB')

cred = AzureCliCredential()
compute = ComputeManagementClient(cred, SUB)

print("Getting VM instance view...")
try:
    iv = compute.virtual_machines.instance_view(RG, VM)
    print(f"Statuses: {[(s.code, s.display_status) for s in (iv.statuses or [])]}")
    print(f"VM Agent: {iv.vm_agent}")
    print(f"Boot Diagnostics: {iv.boot_diagnostics}")
    print(f"Extensions: {[e.name for e in (iv.extensions or [])]}")
except Exception as e:
    print(f"Error: {e}")
