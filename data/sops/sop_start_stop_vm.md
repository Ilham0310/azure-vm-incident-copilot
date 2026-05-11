# SOP: Start/Stop Azure VMs

## ID
sop_start_stop_vm

## Description
Procedure for safely starting or stopping Azure Virtual Machines.

## Triggers
- VM is in Stopped or Deallocated state and needs to be started
- VM needs to be stopped for maintenance or cost savings
- Power state is Failed and restart is required

## Steps
1. Verify VM current power state via Azure Portal or CLI
2. For starting: Use Azure Portal > VM > Start button, or CLI: `az vm start --resource-group <rg> --name <vm-name>`
3. For stopping: Use Azure Portal > VM > Stop button, or CLI: `az vm stop --resource-group <rg> --name <vm-name>`
4. For deallocating (to save costs): Use Azure Portal > VM > Stop (deallocate), or CLI: `az vm deallocate --resource-group <rg> --name <vm-name>`
5. Wait 2-5 minutes for operation to complete
6. Verify new power state
7. Test connectivity if starting VM (RDP/SSH)

## Warnings
- Stopping a VM will interrupt all running applications
- Deallocating releases the VM's IP address unless it's static
- Do not stop VMs during platform maintenance events
- Ensure backups are current before stopping production VMs
