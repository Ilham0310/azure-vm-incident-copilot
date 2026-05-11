# SOP: Azure Firewall/NSG Whitelisting

## ID
sop_firewall_whitelist

## Description
Procedure for configuring Network Security Group (NSG) rules to allow RDP/SSH access.

## Triggers
- Connection troubleshoot shows NSG blocking RDP (port 3389) or SSH (port 22)
- nsg_allow_rdp_3389 or nsg_allow_ssh_22 is False
- Connection troubleshoot verdict indicates firewall block

## Steps
1. Identify the NSG attached to the VM's network interface
2. Navigate to Azure Portal > Network Security Groups > Select NSG
3. Go to Inbound security rules
4. Click "Add" to create new rule
5. Configure rule:
   - Source: Your IP address or IP range
   - Source port ranges: *
   - Destination: Any
   - Destination port ranges: 3389 (RDP) or 22 (SSH)
   - Protocol: TCP
   - Action: Allow
   - Priority: 100-200 (higher priority than deny rules)
   - Name: Allow-RDP-MyIP or Allow-SSH-MyIP
6. Save the rule
7. Wait 1-2 minutes for rule to propagate
8. Test connection using RDP or SSH client

## Warnings
- NEVER use 0.0.0.0/0 (any source) for production VMs
- Always restrict source to specific IP addresses or ranges
- Review and remove temporary rules after troubleshooting
- Coordinate with security team for production changes
- Do not disable NSG entirely - modify rules instead
