# SOP: Azure VM Scale Up/Down

## ID
sop_vm_scale

## Description
Procedure for resizing Azure VMs to adjust compute capacity.

## Triggers
- cpu_percent consistently > 80% (scale up)
- memory_percent consistently > 85% (scale up)
- cpu_percent consistently < 20% for cost optimization (scale down)
- Application performance degradation

## Steps
1. Review performance metrics over 7-day period to confirm trend
2. Identify target VM size:
   - For scale up: Choose next tier (e.g., D2s_v3 → D4s_v3)
   - For scale down: Choose smaller tier with adequate capacity
   - Use Azure VM size selector: https://azure.microsoft.com/pricing/vm-selector/
3. Verify VM size availability in region: `az vm list-sizes --location <region>`
4. Schedule maintenance window (requires VM restart)
5. Take snapshot of OS disk before resizing
6. Resize VM:
   - Azure Portal: VM > Size > Select new size > Resize
   - CLI: `az vm resize --resource-group <rg> --name <vm-name> --size <new-size>`
7. VM will automatically restart (5-10 minutes downtime)
8. Verify new size: `az vm show --resource-group <rg> --name <vm-name> --query hardwareProfile.vmSize`
9. Monitor performance for 24-48 hours
10. Verify application functionality

## Warnings
- VM resizing requires restart (plan for downtime)
- Not all VM sizes are available in all regions
- Scaling up increases costs - verify budget approval
- Some VM families cannot be resized to other families (may require migration)
- Verify licensing implications (e.g., SQL Server, Windows Server)
