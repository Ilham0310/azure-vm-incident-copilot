# SOP: Request Admin Access to Azure VM

## ID
sop_request_admin_access

## Description
Procedure for requesting and obtaining Just-In-Time (JIT) admin access to Azure VMs.

## Triggers
- Need to troubleshoot VM issues requiring admin access
- Need to restart services or agents
- Need to review logs or configuration files
- azure_vm_agent_status is NotReporting and requires manual intervention

## Steps
1. Verify JIT access is configured:
   - Navigate to Azure Portal > Security Center > Just-in-time VM access
   - Confirm VM is listed
2. Request JIT access:
   - Click on VM
   - Click "Request access"
   - Select ports needed (RDP 3389 or SSH 22)
   - Set time range (typically 1-3 hours)
   - Provide business justification
   - Click "Open ports"
3. Wait for approval (if required by policy)
4. Connect to VM:
   - RDP: Use Remote Desktop Connection with VM public IP
   - SSH: `ssh username@vm-public-ip`
5. Perform required administrative tasks:
   - Restart services: `Restart-Service <service-name>` (Windows) or `sudo systemctl restart <service>` (Linux)
   - Restart VM agent: `Restart-Service WindowsAzureGuestAgent` (Windows) or `sudo systemctl restart walinuxagent` (Linux)
   - Review logs: Event Viewer (Windows) or `/var/log/` (Linux)
6. Document actions taken
7. Disconnect when complete (access auto-expires)

## Warnings
- JIT access is time-limited - complete work within window
- All admin actions are logged and audited
- Do not share admin credentials
- Follow principle of least privilege - request only necessary ports
- Coordinate with security team for production VM access
