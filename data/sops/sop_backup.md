# SOP: Azure VM System Backup

## ID
sop_backup

## Description
Procedure for configuring and troubleshooting Azure VM backups.

## Triggers
- last_backup_status is Failed or Warning
- Backup job has not run in > 24 hours
- Recovery Services vault alerts

## Steps
1. Navigate to Azure Portal > Recovery Services vaults
2. Select the vault containing the VM
3. Go to Backup items > Azure Virtual Machine
4. Locate the VM and check backup status
5. For failed backups:
   - Click on the VM to view error details
   - Common issues:
     - Snapshot extension timeout: Restart VM agent
     - Insufficient permissions: Verify vault has Contributor role on VM
     - Disk space: Ensure VM has adequate free space
     - Network connectivity: Check NSG rules allow backup traffic
6. To trigger manual backup:
   - Click "Backup now"
   - Set retention period
   - Click OK
7. Monitor backup job progress (typically 20-60 minutes)
8. Verify backup completion in Backup items list
9. Test restore capability quarterly (restore to test VM)

## Warnings
- Backup operations may cause brief performance impact
- Ensure backup retention meets compliance requirements
- Do not delete Recovery Services vault without migrating backups
- Verify backup encryption settings for sensitive data
- Test restore procedures regularly - backups are useless if restore fails
