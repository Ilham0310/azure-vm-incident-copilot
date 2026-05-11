# SOP: Azure VM Disk Cleanup

## ID
sop_disk_cleanup

## Description
Procedure for cleaning up disk space on Azure VMs when OS disk is near capacity.

## Triggers
- os_disk_percent_full > 90%
- Application errors related to insufficient disk space
- Backup failures due to disk space

## Steps
1. Connect to VM via RDP (Windows) or SSH (Linux)
2. For Windows:
   - Run Disk Cleanup utility (cleanmgr.exe)
   - Select OS drive (usually C:)
   - Check: Temporary files, Windows Update cleanup, Recycle Bin
   - Click OK and confirm deletion
   - Clear IIS logs if applicable: C:\inetpub\logs\LogFiles
   - Clear application logs if safe to do so
3. For Linux:
   - Check disk usage: `df -h`
   - Find large files: `du -sh /* | sort -h`
   - Clear package cache: `sudo apt-get clean` or `sudo yum clean all`
   - Clear old logs: `sudo journalctl --vacuum-time=7d`
   - Remove old kernels: `sudo apt autoremove` (Ubuntu)
4. Verify disk space freed: Check os_disk_percent_full metric
5. If still > 85%, consider disk expansion (see sop_disk_expansion)

## Warnings
- Do not delete system files or application binaries
- Verify log retention policies before deleting logs
- Take snapshot before major cleanup operations
- Coordinate with application owners before deleting app-specific files
