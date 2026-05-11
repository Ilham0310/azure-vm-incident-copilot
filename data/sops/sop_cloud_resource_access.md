# SOP: Request Azure Cloud Resource Access

## ID
sop_cloud_resource_access

## Description
Procedure for requesting access to Azure cloud resources (storage accounts, databases, key vaults, etc.).

## Triggers
- Application needs access to Azure Storage
- VM needs to read secrets from Key Vault
- Service needs database connection
- Managed identity configuration required

## Steps
1. Identify required access:
   - Resource type (Storage, Key Vault, SQL Database, etc.)
   - Access level (Read, Write, Contributor, Owner)
   - Scope (specific resource or resource group)
2. Determine authentication method:
   - Managed Identity (preferred for Azure VMs)
   - Service Principal
   - Shared Access Signature (SAS) for storage
3. For Managed Identity (VM to Azure resource):
   - Enable system-assigned managed identity on VM:
     - Azure Portal > VM > Identity > System assigned > On > Save
   - Grant identity access to target resource:
     - Navigate to target resource (e.g., Storage Account)
     - Go to Access control (IAM) > Add role assignment
     - Role: Storage Blob Data Reader (or appropriate role)
     - Assign access to: Managed Identity
     - Select VM's managed identity
     - Save
4. For Service Principal:
   - Create service principal: `az ad sp create-for-rbac --name <app-name>`
   - Save client ID, client secret, tenant ID
   - Grant service principal access to resource (same as step 3)
5. For Key Vault access:
   - Navigate to Key Vault > Access policies > Add access policy
   - Select permissions (Get, List for secrets)
   - Select principal (managed identity or service principal)
   - Save
6. Test access:
   - From VM, test connection to resource
   - Verify authentication works
   - Check application logs for errors
7. Document access granted in CMDB

## Warnings
- Use managed identities instead of storing credentials when possible
- Follow principle of least privilege - grant minimum required permissions
- Rotate service principal secrets every 90 days
- Never commit credentials to source control
- Audit access regularly and remove unused permissions
