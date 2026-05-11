"""
Simple test to verify Azure CLI authentication works
"""
import os
import sys

# Add Azure CLI to PATH
azure_cli_path = r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin"
if azure_cli_path not in os.environ.get('PATH', ''):
    os.environ['PATH'] = azure_cli_path + os.pathsep + os.environ.get('PATH', '')

print("Testing Azure CLI authentication...")
print()

try:
    from azure.identity import AzureCliCredential
    from azure.mgmt.resourcegraph import ResourceGraphClient
    from azure.mgmt.resourcegraph.models import QueryRequest
    
    print("✓ Imports successful")
    print()
    
    # Test Azure CLI credential
    print("Creating AzureCliCredential...")
    credential = AzureCliCredential()
    print("✓ Credential created")
    print()
    
    # Test getting a token
    print("Getting token...")
    token = credential.get_token("https://management.azure.com/.default")
    print("✓ Token retrieved successfully!")
    print()
    
    # Test Resource Graph query
    print("Testing Resource Graph query...")
    subscription_id = "be8946da-5ca2-4129-ae53-b6124a0aa2d1"
    vm_name = "Test-VM"
    resource_group = "AZ26POC1-CO-LAB"
    
    client = ResourceGraphClient(credential)
    
    query = f"""
    Resources
    | where type =~ 'microsoft.compute/virtualmachines'
    | where name =~ '{vm_name}'
    | where resourceGroup =~ '{resource_group}'
    | project name, location, powerState = properties.extended.instanceView.powerState.code
    """
    
    request = QueryRequest(
        subscriptions=[subscription_id],
        query=query
    )
    
    response = client.resources(request)
    
    if response.data and len(response.data) > 0:
        vm = response.data[0]
        print(f"✓ Found VM: {vm.get('name')}")
        print(f"  Location: {vm.get('location')}")
        print(f"  Power State: {vm.get('powerState', 'Unknown')}")
        print()
        print("=" * 60)
        print("✅ Azure CLI authentication is working!")
        print("=" * 60)
    else:
        print("✗ VM not found")
        print()
        print("Check:")
        print("  - VM name is correct: Test-VM")
        print("  - Resource group is correct: AZ26POC1-CO-LAB")
        print("  - Subscription ID is correct")

except Exception as e:
    print(f"✗ Error: {e}")
    print()
    import traceback
    traceback.print_exc()
    print()
    print("=" * 60)
    print("Troubleshooting:")
    print("=" * 60)
    print("1. Make sure you're logged in:")
    print('   az login')
    print()
    print("2. Check your subscription:")
    print('   az account show')
    print()
    print("3. Verify VM exists:")
    print('   az vm show --name Test-VM --resource-group AZ26POC1-CO-LAB')
