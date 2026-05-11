# SOP: Decommission Azure VM

## ID
sop_decommission

## Description
Procedure for safely decommissioning Azure VMs that are no longer needed.

## Triggers
- VM in permanent Failed state with no recovery path
- Application migrated to new infrastructure
- Project or environment no longer needed
- Cost optimization initiative

## Steps
1. Verify VM is approved for decommissioning:
   - Confirm with application owner
   - Check for dependencies (load balancers, app gateways, etc.)
   - Verify no active users or connections
2. Document VM configuration:
   - Export VM configuration: `az vm show --resource-group <rg> --name <vm-name> > vm-config.json`
   - Document network configuration, NSG rules, disk configuration
   - Take screenshots of Azure Portal settings
3. Create final backup:
   - Take snapshot of all disks
   - Export backup to separate storage account
   - Verify backup integrity
4. Remove from monitoring and alerting:
   - Disable Azure Monitor alerts
   - Remove from monitoring dashboards
   - Update documentation
5. Stop VM: `az vm stop --resource-group <rg> --name <vm-name>`
6. Wait 7-14 days (grace period for rollback)
7. Delete VM (keeps disks): `az vm delete --resource-group <rg> --name <vm-name> --yes`
8. After 30 days, delete associated resources:
   - Disks: `az disk delete --resource-group <rg> --name <disk-name> --yes`
   - Network interfaces
   - Public IP addresses
   - NSG (if not shared)
9. Update CMDB and asset inventory
10. Document decommissioning in change log

## Warnings
- Verify no other VMs depend on this VM's resources
- Ensure backups are retained per compliance requirements
- Do not delete resources during grace period
- Coordinate with networking team before deleting shared resources
- Verify cost savings are realized after decommissioning
