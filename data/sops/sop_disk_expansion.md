# SOP: Azure VM Disk Expansion

## ID
sop_disk_expansion

## Description
Procedure for expanding Azure VM disk capacity when cleanup is insufficient.

## Triggers
- os_disk_percent_full > 90% after cleanup
- Persistent disk space warnings
- Application requires more storage

## Steps
1. Take snapshot of disk before expansion (Azure Portal > Disks > Create snapshot)
2. Stop/deallocate the VM: `az vm deallocate --resource-group <rg> --name <vm-name>`
3. Expand disk in Azure Portal:
   - Navigate to VM > Disks > OS disk
   - Click "Size + performance"
   - Select larger disk size
   - Click "Resize"
4. Start the VM: `az vm start --resource-group <rg> --name <vm-name>`
5. Connect to VM and extend partition:
   - Windows: Disk Management > Extend Volume
   - Linux: `sudo growpart /dev/sda 1` then `sudo resize2fs /dev/sda1`
6. Verify new disk size: `df -h` (Linux) or Disk Management (Windows)
7. Monitor for 24 hours to ensure stability

## Warnings
- Disk expansion requires VM downtime (5-10 minutes)
- Cannot shrink disks after expansion
- Verify cost impact before expanding (larger disks cost more)
- Coordinate with application owners for maintenance window
- Ensure adequate budget approval for production VMs
