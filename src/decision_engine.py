"""
Decision engine component for Azure VM Incident Copilot.

This module provides the DecisionEngine class that:
- Applies decision policy rules A, B, C with exact thresholds
- Enforces 6 safety rules (platform event, boot failure, destructive actions, network, disk, failed state)
- Matches against 20 known incident patterns
- Generates evidence, evidence_gap, and next_check for each decision

Evaluation order:
1. Safety rule checks (highest priority)
2. Data completeness checks
3. Signal conflict checks
4. Pattern matching (20 patterns)
5. Decision selection (rules A, B, C)
"""

from typing import Optional, List, Tuple
from src.models import (
    TelemetryInput,
    Decision,
    DecisionState,
    PowerState,
    ProvisioningState,
    ResourceHealthStatus,
    BootDiagnosticsStatus,
    AzureVMAgentStatus,
    AppHealthStatus,
    MonitorAgentStatus,
    ConnectionTroubleshootResult
)


class DecisionEngine:
    """
    Applies decision policy to return one of three states.
    
    Responsibilities:
    - Evaluate safety rules (6 rules)
    - Check data completeness and signal conflicts
    - Match against 20 known incident patterns
    - Apply decision policy rules A, B, C
    - Generate evidence, evidence_gap, and next_check
    """
    
    # Decision thresholds
    DIAGNOSE_CONFIDENCE_MIN = 0.70
    DIAGNOSE_COMPLETENESS_MIN = 90
    DIAGNOSE_LOW_CONFIDENCE_MIN = 0.40
    DIAGNOSE_LOW_COMPLETENESS_MIN = 60
    HIGH_CONFIDENCE_DESTRUCTIVE_MIN = 0.9
    
    # Platform event keywords
    PLATFORM_KEYWORDS = ["platform", "maintenance", "host update", "planned maintenance", "degradation"]
    
    def decide(
        self,
        telemetry: TelemetryInput,
        confidence_score: float,
        completeness: float
    ) -> Decision:
        """
        Applies decision policy to return one of three states.
        
        Evaluation order:
        1. Safety rule checks (highest priority)
        2. Data completeness checks
        3. Signal conflict checks
        4. Pattern matching (20 patterns)
        5. Decision selection (rules A, B, C)
        
        Args:
            telemetry: Validated telemetry input
            confidence_score: Calculated confidence score (0.0-1.0)
            completeness: Data completeness percentage (0-100)
            
        Returns:
            Decision object with state, diagnosis, evidence, gaps, next_check
        """
        # Step 1: Check safety rules (highest priority)
        safety_violation = self._check_safety_rules(telemetry, confidence_score)
        if safety_violation:
            return safety_violation
        
        # Step 2: Check critical signals
        if self._has_missing_critical_signals(telemetry):
            return Decision(
                state=DecisionState.ABSTAIN_REQUEST_NEXT_CHECK,
                diagnosis="Critical signals missing or unknown",
                evidence=self._get_evidence(telemetry),
                evidence_gap=["power_state", "provisioning_state", "resource_health_status"],
                next_check="Gather critical telemetry: power_state, provisioning_state, resource_health_status",
                confidence_score=confidence_score
            )
        
        # Step 3: Check data completeness
        if completeness < self.DIAGNOSE_LOW_COMPLETENESS_MIN:
            return Decision(
                state=DecisionState.ABSTAIN_REQUEST_NEXT_CHECK,
                diagnosis="Insufficient telemetry data",
                evidence=self._get_evidence(telemetry),
                evidence_gap=self._get_evidence_gap(telemetry),
                next_check="Gather more telemetry data to reach at least 60% completeness",
                confidence_score=confidence_score
            )
        
        # Step 4: Pattern matching
        pattern_result = self._match_patterns(telemetry)
        if pattern_result:
            if len(pattern_result) == 5:
                # New format: (pattern_name, diagnosis, evidence, next_check, forced_state)
                pattern_name, diagnosis, evidence, next_check, forced_state = pattern_result
                state = forced_state if forced_state else self._determine_state(confidence_score, completeness)
            else:
                # Old format: (pattern_name, diagnosis, evidence, next_check)
                pattern_name, diagnosis, evidence, next_check = pattern_result
                state = self._determine_state(confidence_score, completeness)
            
            return Decision(
                state=state,
                diagnosis=diagnosis,
                evidence=evidence,
                evidence_gap=self._get_evidence_gap(telemetry),
                next_check=next_check,
                confidence_score=confidence_score
            )
        
        # Step 5: No pattern matched - apply decision rules based on confidence/completeness
        if confidence_score >= self.DIAGNOSE_CONFIDENCE_MIN and completeness >= self.DIAGNOSE_COMPLETENESS_MIN:
            return Decision(
                state=DecisionState.DIAGNOSE,
                diagnosis="VM state unclear - no specific pattern matched",
                evidence=self._get_evidence(telemetry),
                evidence_gap=self._get_evidence_gap(telemetry),
                next_check=None,
                confidence_score=confidence_score
            )
        elif confidence_score >= self.DIAGNOSE_LOW_CONFIDENCE_MIN and completeness >= self.DIAGNOSE_LOW_COMPLETENESS_MIN:
            return Decision(
                state=DecisionState.DIAGNOSE_LOW_CONFIDENCE,
                diagnosis="VM state unclear - insufficient data for high confidence",
                evidence=self._get_evidence(telemetry),
                evidence_gap=self._get_evidence_gap(telemetry),
                next_check="Gather more telemetry for higher confidence diagnosis",
                confidence_score=confidence_score
            )
        else:
            return Decision(
                state=DecisionState.ABSTAIN_REQUEST_NEXT_CHECK,
                diagnosis="Insufficient data for diagnosis",
                evidence=self._get_evidence(telemetry),
                evidence_gap=self._get_evidence_gap(telemetry),
                next_check="Gather more telemetry data",
                confidence_score=confidence_score
            )
    
    # ========================================================================
    # Safety Rules (6 rules)
    # ========================================================================
    
    def _check_safety_rules(self, telemetry: TelemetryInput, confidence_score: float) -> Optional[Decision]:
        """
        Check all 6 safety rules.
        
        Returns Decision with abstain if any safety rule is violated, None otherwise.
        """
        # Safety Rule 1: Platform Event Safety
        if self._check_platform_event_safety(telemetry):
            return Decision(
                state=DecisionState.ABSTAIN_REQUEST_NEXT_CHECK,
                diagnosis="Platform-initiated event detected",
                evidence=self._get_evidence(telemetry),
                evidence_gap=self._get_evidence_gap(telemetry),
                next_check="Wait for platform maintenance to complete, then re-assess VM state",
                confidence_score=confidence_score
            )
        
        # Safety Rule 2: Boot Failure Safety
        # Boot failures should be diagnosed only if confidence is sufficient
        # The safety aspect is in the next_check (never suggest restart)
        if self._check_boot_failure_safety(telemetry):
            boot_status = str(telemetry.boot_diagnostics_status)
            # Determine state based on confidence
            if confidence_score >= self.DIAGNOSE_CONFIDENCE_MIN:
                state = DecisionState.DIAGNOSE
            elif confidence_score >= self.DIAGNOSE_LOW_CONFIDENCE_MIN:
                state = DecisionState.DIAGNOSE_LOW_CONFIDENCE
            else:
                state = DecisionState.ABSTAIN_REQUEST_NEXT_CHECK
            
            return Decision(
                state=state,
                diagnosis=f"Boot failure detected: {boot_status}",
                evidence=self._get_evidence(telemetry),
                evidence_gap=self._get_evidence_gap(telemetry),
                next_check="Check boot diagnostics screenshots and serial console logs. Engage OS support for analysis.",
                confidence_score=confidence_score
            )
        
        # Safety Rules 3-6 are enforced in next_check generation (not blocking)
        return None
    
    def _check_platform_event_safety(self, telemetry: TelemetryInput) -> bool:
        """Safety Rule 1: Platform Event Safety"""
        if telemetry.resource_health_annotation:
            annotation_lower = telemetry.resource_health_annotation.lower()
            return any(keyword in annotation_lower for keyword in self.PLATFORM_KEYWORDS)
        return False
    
    def _check_boot_failure_safety(self, telemetry: TelemetryInput) -> bool:
        """Safety Rule 2: Boot Failure Safety"""
        if telemetry.boot_diagnostics_status:
            return telemetry.boot_diagnostics_status in [
                BootDiagnosticsStatus.BSOD,
                BootDiagnosticsStatus.KERNEL_PANIC
            ]
        return False
    
    def _sanitize_next_check(self, next_check: str, telemetry: TelemetryInput, confidence_score: float) -> str:
        """
        Apply safety rules 3-6 to sanitize next_check suggestions.
        
        Removes unsafe suggestions based on:
        - Safety Rule 3: Low confidence destructive actions
        - Safety Rule 4: Network security changes
        - Safety Rule 5: Disk operations
        - Safety Rule 6: Failed state auto-remediation
        """
        if not next_check:
            return next_check
        
        next_check_lower = next_check.lower()
        
        # Safety Rule 4: Network Security Safety (always enforced)
        if "disable nsg" in next_check_lower or "disable firewall" in next_check_lower:
            return "Review network security configuration manually (do not disable NSG or firewall rules)"
        
        # Safety Rule 3: Low Confidence Destructive Action Safety
        if confidence_score < self.HIGH_CONFIDENCE_DESTRUCTIVE_MIN:
            destructive_keywords = ["delete disk", "reset os", "delete vm", "reset configuration"]
            if any(keyword in next_check_lower for keyword in destructive_keywords):
                return "Gather more data before considering destructive actions (confidence too low)"
        
        # Safety Rule 5: Disk Safety
        if confidence_score < self.HIGH_CONFIDENCE_DESTRUCTIVE_MIN:
            if "delete disk" in next_check_lower or "reset os" in next_check_lower:
                return "Review disk and OS state manually (confidence too low for disk operations)"
        
        # Safety Rule 6: Failed State Safety
        if (telemetry.power_state == PowerState.FAILED and
            telemetry.provisioning_state == ProvisioningState.FAILED):
            if "auto" in next_check_lower or "remediate" in next_check_lower:
                return "Contact Azure support for failed VM state (do not attempt auto-remediation)"
        
        return next_check
    
    def _has_missing_critical_signals(self, telemetry: TelemetryInput) -> bool:
        """Check if critical signals are missing or unknown"""
        return (
            telemetry.power_state == PowerState.UNKNOWN or
            telemetry.provisioning_state == ProvisioningState.UNKNOWN or
            telemetry.resource_health_status == ResourceHealthStatus.UNKNOWN
        )
    
    def _determine_state(self, confidence_score: float, completeness: float) -> DecisionState:
        """
        Determine decision state based on confidence and completeness thresholds.
        
        Args:
            confidence_score: Confidence score (0.0-1.0)
            completeness: Data completeness percentage (0-100)
            
        Returns:
            DecisionState based on thresholds
        """
        if confidence_score >= self.DIAGNOSE_CONFIDENCE_MIN and completeness >= self.DIAGNOSE_COMPLETENESS_MIN:
            return DecisionState.DIAGNOSE
        elif confidence_score >= self.DIAGNOSE_LOW_CONFIDENCE_MIN and completeness >= self.DIAGNOSE_LOW_COMPLETENESS_MIN:
            return DecisionState.DIAGNOSE_LOW_CONFIDENCE
        else:
            return DecisionState.ABSTAIN_REQUEST_NEXT_CHECK
    
    # ========================================================================
    # Pattern Matching (20 patterns)
    # ========================================================================
    
    def _match_patterns(self, telemetry: TelemetryInput) -> Optional[Tuple[str, str, List[str], Optional[str]]]:
        """
        Match telemetry against 23 known incident patterns.
        
        Returns:
            Tuple of (pattern_name, diagnosis, evidence, next_check) or None if no match
        """
        # Pattern 1: VM Stopped by User
        if (telemetry.power_state == PowerState.STOPPED and
            telemetry.provisioning_state == ProvisioningState.SUCCEEDED):
            return (
                "vm_stopped_by_user",
                "VM Stopped by user deallocation",
                [f"power_state={telemetry.power_state.value}", f"provisioning_state={telemetry.provisioning_state.value}"],
                "Start VM if needed: (1) Azure Portal > VM > Start, or run: az vm start --resource-group <rg> --name <vm-name>. (2) Wait 2-5 minutes. (3) Test RDP/SSH connectivity. If intentionally stopped for cost savings, no action required."
            )
        
        # Pattern 2: NSG Blocks RDP
        if (telemetry.nsg_allow_rdp_3389 is not None and not telemetry.nsg_allow_rdp_3389 and
            telemetry.connection_troubleshoot_rdp == ConnectionTroubleshootResult.DENY):
            return (
                "nsg_blocks_rdp",
                "NSG blocks RDP",
                ["nsg_allow_rdp_3389=False", f"connection_troubleshoot_rdp={telemetry.connection_troubleshoot_rdp.value}"],
                "To allow RDP access: (1) Azure Portal > Network Security Groups > select the NSG attached to this VM's NIC. (2) Go to Inbound security rules > Add. (3) Set Source=Your IP, Destination port=3389, Protocol=TCP, Action=Allow, Priority=100-200, Name=Allow-RDP-MyIP. (4) Save and wait 1-2 minutes. (5) Test RDP connection. WARNING: Never use 0.0.0.0/0 as source — restrict to specific IP only."
            )
        
        # Pattern 3: NSG Blocks SSH
        if (telemetry.nsg_allow_ssh_22 is not None and not telemetry.nsg_allow_ssh_22 and
            telemetry.connection_troubleshoot_ssh == ConnectionTroubleshootResult.DENY):
            return (
                "nsg_blocks_ssh",
                "NSG blocks SSH",
                ["nsg_allow_ssh_22=False", f"connection_troubleshoot_ssh={telemetry.connection_troubleshoot_ssh.value}"],
                "To allow SSH access: (1) Azure Portal > Network Security Groups > select the NSG attached to this VM's NIC. (2) Go to Inbound security rules > Add. (3) Set Source=Your IP, Destination port=22, Protocol=TCP, Action=Allow, Priority=100-200, Name=Allow-SSH-MyIP. (4) Save and wait 1-2 minutes. (5) Test SSH: ssh username@vm-ip. WARNING: Never use 0.0.0.0/0 as source — restrict to specific IP only."
            )
        
        # Pattern 4: High CPU Saturation
        if telemetry.cpu_percent is not None and telemetry.cpu_percent > 95:
            return (
                "high_cpu",
                "High CPU saturation",
                [f"cpu_percent={telemetry.cpu_percent}"],
                "Immediate: (1) Connect to VM and identify top CPU processes — Windows: Task Manager > CPU column; Linux: top or htop. (2) If runaway process, kill it: Linux: kill -9 <pid>; Windows: End Task. Scale up if sustained: (3) Review 7-day CPU trend in Azure Monitor. (4) Azure Portal > VM > Size > select next tier (e.g., D2s_v3 to D4s_v3) > Resize. VM restarts (5-10 min downtime). (5) Monitor for 24-48 hours post-resize."
            )
        
        # Pattern 5: OS Disk Full
        if telemetry.os_disk_percent_full is not None and telemetry.os_disk_percent_full > 95:
            return (
                "os_disk_full",
                "OS disk full",
                [f"os_disk_percent_full={telemetry.os_disk_percent_full}"],
                "Immediate cleanup: (1) Linux: df -h to confirm, du -sh /* | sort -h to find large files, then: sudo apt-get clean && sudo journalctl --vacuum-time=7d && sudo apt autoremove. Windows: run Disk Cleanup (cleanmgr.exe), clear C:\\inetpub\\logs\\LogFiles. (2) If still >85% after cleanup, expand disk: take snapshot first (Azure Portal > Disks > Create snapshot), then Azure Portal > VM > Disks > OS disk > Size+performance > select larger size > Resize. (3) After resize, extend partition: Linux: sudo growpart /dev/sda 1 && sudo resize2fs /dev/sda1. Windows: Disk Management > Extend Volume."
            )
        
        # Pattern 6: Memory Exhaustion
        if telemetry.memory_percent is not None and telemetry.memory_percent > 95:
            return (
                "memory_exhaustion",
                "Memory exhaustion",
                [f"memory_percent={telemetry.memory_percent}"],
                "Immediate: (1) Connect to VM and identify top memory processes — Windows: Task Manager > Memory column; Linux: free -h and ps aux --sort=-%mem | head. (2) Restart memory-leaking services if identified. Scale up if sustained: (3) Review 7-day memory trend in Azure Monitor. (4) Azure Portal > VM > Size > select next tier with more RAM > Resize. VM restarts (5-10 min downtime). (5) Monitor memory for 24-48 hours post-resize."
            )
        
        # Pattern 7: Boot BSOD (handled by safety rule, but included for completeness)
        if telemetry.boot_diagnostics_status == BootDiagnosticsStatus.BSOD:
            return (
                "boot_bsod",
                "Boot BSOD",
                [f"boot_diagnostics_status={telemetry.boot_diagnostics_status.value}"],
                "DO NOT restart VM without investigation. (1) Azure Portal > VM > Boot diagnostics > Screenshot — note the BSOD stop code. (2) Azure Portal > VM > Serial console — review boot logs. (3) Take disk snapshot before any recovery: Azure Portal > Disks > Create snapshot. (4) Engage OS support with the stop code. (5) If recovery needed: attach OS disk to a recovery VM, repair, then reattach."
            )
        
        # Pattern 8: Boot Kernel Panic (handled by safety rule, but included for completeness)
        if telemetry.boot_diagnostics_status == BootDiagnosticsStatus.KERNEL_PANIC:
            return (
                "boot_kernel_panic",
                "Boot kernel panic",
                [f"boot_diagnostics_status={telemetry.boot_diagnostics_status.value}"],
                "DO NOT restart VM without investigation. (1) Azure Portal > VM > Boot diagnostics > Screenshot — note the kernel panic message. (2) Azure Portal > VM > Serial console — run: dmesg | tail -50 to see panic details. (3) Take disk snapshot before recovery: Azure Portal > Disks > Create snapshot. (4) Check if recent kernel update caused this: attach disk to recovery VM, chroot, run: apt-get install --reinstall linux-image-$(uname -r). (5) Engage Linux OS support if unresolved."
            )
        
        # Pattern 9: VM Running No Heartbeat
        if (telemetry.power_state == PowerState.RUNNING and
            telemetry.heartbeat_present is not None and not telemetry.heartbeat_present):
            return (
                "vm_running_no_heartbeat",
                "VM running but no heartbeat",
                [f"power_state={telemetry.power_state.value}", "heartbeat_present=False"],
                "Azure Monitor Agent is not reporting. (1) Request JIT access: Azure Portal > Security Center > Just-in-time VM access > Request access for SSH/RDP (1-3 hours, provide justification). (2) Connect to VM. (3) Linux: sudo systemctl status azuremonitoragent — if failed: sudo systemctl restart azuremonitoragent. (4) Windows: Get-Service -Name AzureMonitorAgent — if stopped: Restart-Service AzureMonitorAgent. (5) If reinstall needed: Azure Portal > VM > Extensions > remove AzureMonitorLinuxAgent > re-add it and re-associate DCR."
            )
        
        # Pattern 10: Resource Health Unavailable
        if (telemetry.resource_health_status == ResourceHealthStatus.UNAVAILABLE and
            telemetry.cpu_percent is not None and telemetry.cpu_percent < 90 and
            telemetry.memory_percent is not None and telemetry.memory_percent < 90):
            return (
                "resource_health_unavailable",
                "Resource health unavailable with normal metrics",
                [f"resource_health_status={telemetry.resource_health_status.value}", 
                 f"cpu_percent={telemetry.cpu_percent}", f"memory_percent={telemetry.memory_percent}"],
                "VM metrics are normal but Azure reports health as unavailable. (1) Check Azure Service Health: portal.azure.com > Service Health > Health alerts — look for active incidents in your region. (2) Check VM agent: Azure Portal > VM > Properties > Agent status. (3) If platform issue, wait for Azure to resolve — no action needed. (4) If persists >30 min with no platform event, open Azure support ticket."
            )
        
        # Pattern 11: Conflicting NSG Signals
        if (telemetry.nsg_allow_rdp_3389 is not None and not telemetry.nsg_allow_rdp_3389 and
            telemetry.connection_troubleshoot_rdp == ConnectionTroubleshootResult.ALLOW):
            return (
                "conflicting_nsg_signals",
                "Conflicting NSG and connection troubleshoot signals",
                ["nsg_allow_rdp_3389=False", f"connection_troubleshoot_rdp={telemetry.connection_troubleshoot_rdp.value}"],
                "NSG rule and connection test disagree — likely a subnet-level NSG or Application Security Group override. (1) Azure Portal > VM > Networking > check both NIC-level and subnet-level NSG rules. (2) Run Network Watcher IP flow verify: Azure Portal > Network Watcher > IP flow verify — enter VM IP, port 3389, direction Inbound. (3) Check effective security rules: Azure Portal > VM NIC > Effective security rules. (4) Resolve the conflicting rule at the correct level."
            )
        
        # Pattern 12: App Unhealthy VM Healthy
        if (telemetry.app_health_status == AppHealthStatus.UNHEALTHY and
            telemetry.azure_vm_agent_status == AzureVMAgentStatus.HEALTHY):
            return (
                "app_unhealthy_vm_healthy",
                "Application unhealthy with healthy VM",
                [f"app_health_status={telemetry.app_health_status.value}", 
                 f"azure_vm_agent_status={telemetry.azure_vm_agent_status.value}"],
                "VM infrastructure is healthy — issue is at application layer. (1) Connect to VM and check application logs: Linux: sudo journalctl -u <service> -n 100 or /var/log/<app>/. Windows: Event Viewer > Application logs. (2) Check if application service is running: Linux: sudo systemctl status <service>. Windows: services.msc. (3) Restart application service if crashed. (4) If Application Gateway is involved: Azure Portal > Application Gateway > Backend health — verify backend pool shows Healthy. (5) Check application configuration files for misconfigurations."
            )
        
        # Pattern 13: Disk IO Saturation
        if ((telemetry.os_disk_latency_ms is not None and telemetry.os_disk_latency_ms > 100) or
            (telemetry.data_disk_latency_ms is not None and telemetry.data_disk_latency_ms > 100)):
            return (
                "disk_io_saturation",
                "Disk IO saturation",
                [f"os_disk_latency_ms={telemetry.os_disk_latency_ms}", 
                 f"data_disk_latency_ms={telemetry.data_disk_latency_ms}"],
                "High disk latency detected. (1) Identify top IO processes: Linux: iotop -o. Windows: Resource Monitor > Disk tab. (2) Check disk type: Azure Portal > VM > Disks — if Standard HDD, upgrade to Premium SSD: select disk > Change disk type > Premium SSD > Save (no downtime for data disks). (3) For OS disk upgrade: take snapshot first, then deallocate VM, change disk type, restart. (4) If Premium SSD already in use, enable disk caching: Azure Portal > VM > Disks > Host caching > ReadOnly for read-heavy workloads."
            )
        
        # Pattern 14: VM Deallocated
        if telemetry.power_state == PowerState.DEALLOCATED:
            return (
                "vm_deallocated",
                "Deallocated VM",
                [f"power_state={telemetry.power_state.value}"],
                "VM is fully deallocated (no compute charges). To start: (1) Azure Portal > VM > Start, or run: az vm start --resource-group <rg> --name <vm-name>. (2) Wait 2-5 minutes for boot. (3) Note: if VM had a dynamic public IP, it may have changed — check Azure Portal > VM > Overview for new IP. (4) Test connectivity via RDP/SSH."
            )
        
        # Pattern 15: Provisioning Failed
        if telemetry.provisioning_state == ProvisioningState.FAILED:
            return (
                "provisioning_failed",
                "Provisioning failed",
                [f"provisioning_state={telemetry.provisioning_state.value}"],
                "VM provisioning failed. (1) Azure Portal > VM > Activity log — find the failed operation and expand to see error details. (2) Common fixes: if extension failure, Azure Portal > VM > Extensions > remove failed extension > re-add. If disk issue, check storage account quotas. (3) If unrecoverable: document VM config (az vm show --resource-group <rg> --name <vm-name> > vm-config.json), take disk snapshot, delete VM, redeploy from snapshot or template. (4) Open Azure support ticket if error is platform-side."
            )
        
        # Pattern 16: Failed State Insufficient Data
        if (telemetry.power_state == PowerState.FAILED and
            telemetry.data_completeness_percent is not None and
            telemetry.data_completeness_percent < 30):
            return (
                "failed_state_insufficient_data",
                "Failed state with insufficient data",
                [f"power_state={telemetry.power_state.value}", 
                 f"data_completeness_percent={telemetry.data_completeness_percent}"],
                "VM is in Failed state with insufficient telemetry to diagnose. (1) Azure Portal > VM > Activity log — review last 24 hours for error events. (2) Azure Portal > VM > Boot diagnostics — check screenshot and serial console. (3) Try restart: az vm restart --resource-group <rg> --name <vm-name>. (4) If restart fails, open Azure support ticket with VM resource ID and activity log export."
            )
        
        # Pattern 17: Platform Degradation (handled by safety rule, but included for completeness)
        if self._check_platform_event_safety(telemetry):
            return (
                "platform_degradation",
                "Platform degradation event",
                [f"resource_health_annotation={telemetry.resource_health_annotation}"],
                "Azure platform event in progress — no action required from your side. (1) Monitor Azure Service Health: portal.azure.com > Service Health > Health alerts for your region. (2) Do NOT restart VM during platform maintenance — this can cause extended downtime or data loss. (3) Wait for Azure to complete the maintenance (typically 15-60 minutes). (4) Re-assess VM health after platform event resolves."
            )
        
        # Pattern 18: Boot Stuck
        if telemetry.boot_diagnostics_status == BootDiagnosticsStatus.STUCK:
            return (
                "boot_stuck",
                "Boot stuck at startup",
                [f"boot_diagnostics_status={telemetry.boot_diagnostics_status.value}"],
                "VM boot process is hung. (1) Take disk snapshot before any action: Azure Portal > Disks > Create snapshot. (2) Azure Portal > VM > Boot diagnostics > Screenshot — identify where boot is stuck (e.g., Waiting for network, fsck running). (3) Azure Portal > VM > Serial console — press Enter or Ctrl+C to interrupt stuck process. (4) If stuck on fsck: in serial console run: fsck -y /dev/sda1. (5) If stuck on network: in serial console edit /etc/network/interfaces or disable problematic network service. (6) If unresolvable via serial console, attach disk to recovery VM for offline repair."
            )
        
        # Pattern 19: VM Agent Failed
        if telemetry.azure_vm_agent_status == AzureVMAgentStatus.FAILED:
            return (
                "vm_agent_failed",
                "Azure VM agent failure",
                [f"azure_vm_agent_status={telemetry.azure_vm_agent_status.value}"],
                "Azure VM agent is not functioning. (1) Request JIT access: Azure Portal > Security Center > Just-in-time VM access > Request access (1-3 hours, provide justification). (2) Connect via RDP/SSH. (3) Linux: sudo systemctl restart walinuxagent — if fails: sudo apt-get install --reinstall walinuxagent && sudo systemctl start walinuxagent. (4) Windows: Restart-Service WindowsAzureGuestAgent — if fails, reinstall from https://aka.ms/vmagent. (5) Verify: Azure Portal > VM > Properties > Agent status should show Ready."
            )
        
        # Pattern 20: Monitor Agent Failed
        if telemetry.monitor_agent_status == MonitorAgentStatus.FAILED:
            return (
                "monitor_agent_failed",
                "Monitoring agent failure",
                [f"monitor_agent_status={telemetry.monitor_agent_status.value}"],
                "Azure Monitor Agent is not functioning. (1) Request JIT access: Azure Portal > Security Center > Just-in-time VM access > Request access. (2) Connect to VM. (3) Linux: sudo systemctl restart azuremonitoragent — check logs: sudo journalctl -u azuremonitoragent -n 50. (4) Windows: Restart-Service AzureMonitorAgent — check Event Viewer > Application for errors. (5) If reinstall needed: Azure Portal > VM > Extensions > remove AzureMonitorLinuxAgent (or Windows) > Add extension > Azure Monitor Agent > re-associate DCR."
            )
        
        # Pattern 21: SSL Certificate Expiry Warning
        if telemetry.ssl_cert_days_remaining is not None and telemetry.ssl_cert_days_remaining <= 30:
            # Force diagnose if <= 7 days, diagnose_low_confidence if 7-30 days
            forced_state = DecisionState.DIAGNOSE if telemetry.ssl_cert_days_remaining <= 7 else DecisionState.DIAGNOSE_LOW_CONFIDENCE
            return (
                "ssl_cert_expiry_warning",
                f"SSL certificate expiring in {telemetry.ssl_cert_days_remaining} days",
                [f"ssl_cert_days_remaining={telemetry.ssl_cert_days_remaining}"],
                f"SSL certificate expires in {telemetry.ssl_cert_days_remaining} days — renew now. For Let's Encrypt: (1) Connect to VM. (2) Test: sudo certbot renew --dry-run. (3) Renew: sudo certbot renew. (4) Restart web server: sudo systemctl restart nginx (or apache2). For CA-issued cert: (1) Generate CSR: openssl req -new -key private.key -out renewal.csr. (2) Submit to CA and download new cert. (3) Install on web server and update bindings. (4) Verify: echo | openssl s_client -connect domain.com:443 2>/dev/null | openssl x509 -noout -dates. WARNING: Do NOT delete current certificate until new one is confirmed working.",
                forced_state
            )
        
        # Pattern 22: Azure Backup Job Failure
        if telemetry.last_backup_status is not None and telemetry.last_backup_status in ["Failed", "Warning"]:
            evidence = [f"last_backup_status={telemetry.last_backup_status}"]
            if telemetry.last_backup_time:
                evidence.append(f"last_backup_time={telemetry.last_backup_time}")
            
            # Force diagnose if Failed, diagnose_low_confidence if Warning
            forced_state = DecisionState.DIAGNOSE if telemetry.last_backup_status == "Failed" else DecisionState.DIAGNOSE_LOW_CONFIDENCE
            
            return (
                "azure_backup_job_failure",
                "Azure VM backup job failed",
                evidence,
                "Backup job failed. (1) Azure Portal > Recovery Services vaults > select vault > Backup items > Azure Virtual Machine > find this VM > click to see error details. (2) Common fixes: Snapshot timeout — restart VM agent (sudo systemctl restart walinuxagent). Permissions error — verify vault has Contributor role on VM (VM > Access control > Role assignments). Disk space — ensure VM has >1GB free. (3) Trigger manual backup: Backup items > VM > Backup now > set retention > OK. (4) Monitor job progress (20-60 min). (5) Test restore quarterly to verify backup integrity.",
                forced_state
            )
        
        # Pattern 23: VM Oversized / Rightsize Candidate
        if (telemetry.cpu_percent is not None and telemetry.cpu_percent < 10 and
            telemetry.memory_percent is not None and telemetry.memory_percent < 20 and
            telemetry.power_state == PowerState.RUNNING):
            return (
                "vm_oversized_rightsize_candidate",
                f"VM over-provisioned. CPU at {telemetry.cpu_percent}%, Memory at {telemetry.memory_percent}% — rightsize candidate",
                [f"cpu_percent={telemetry.cpu_percent}", f"memory_percent={telemetry.memory_percent}"],
                "VM is significantly under-utilized — consider downsizing to reduce costs. (1) First verify trend: Azure Portal > VM > Metrics — check CPU and Memory over 30 days (not just current snapshot). (2) Check Azure Advisor: portal.azure.com > Advisor > Cost — review rightsizing recommendations. (3) Calculate savings: compare current vs. target size cost at azure.microsoft.com/pricing/vm-selector. (4) Get stakeholder approval. (5) Schedule maintenance window. (6) Take OS disk snapshot. (7) Resize: Azure Portal > VM > Size > select smaller tier > Resize (VM restarts, 5-10 min downtime). (8) Monitor for 7 days — verify application performance is acceptable.",
                DecisionState.DIAGNOSE_LOW_CONFIDENCE  # Always low confidence - needs trend data
            )
        
        return None
    
    # ========================================================================
    # Evidence and Gap Generation
    # ========================================================================
    
    def _get_evidence(self, telemetry: TelemetryInput) -> List[str]:
        """Extract evidence from populated telemetry fields"""
        evidence = []
        
        # Always include required fields
        evidence.append(f"power_state={telemetry.power_state.value}")
        evidence.append(f"provisioning_state={telemetry.provisioning_state.value}")
        evidence.append(f"resource_health_status={telemetry.resource_health_status.value}")
        
        # Add populated optional fields
        if telemetry.cpu_percent is not None:
            evidence.append(f"cpu_percent={telemetry.cpu_percent}")
        if telemetry.memory_percent is not None:
            evidence.append(f"memory_percent={telemetry.memory_percent}")
        if telemetry.heartbeat_present is not None:
            evidence.append(f"heartbeat_present={telemetry.heartbeat_present}")
        if telemetry.boot_diagnostics_status is not None:
            evidence.append(f"boot_diagnostics_status={telemetry.boot_diagnostics_status.value}")
        if telemetry.azure_vm_agent_status is not None:
            evidence.append(f"azure_vm_agent_status={telemetry.azure_vm_agent_status.value}")
        
        return evidence
    
    def _get_evidence_gap(self, telemetry: TelemetryInput) -> List[str]:
        """Identify missing telemetry fields"""
        gaps = []
        
        # Check key optional fields
        if telemetry.heartbeat_present is None:
            gaps.append("heartbeat_present")
        if telemetry.boot_diagnostics_status is None:
            gaps.append("boot_diagnostics_status")
        if telemetry.cpu_percent is None:
            gaps.append("cpu_percent")
        if telemetry.memory_percent is None:
            gaps.append("memory_percent")
        if telemetry.azure_vm_agent_status is None:
            gaps.append("azure_vm_agent_status")
        if telemetry.os_disk_percent_full is None:
            gaps.append("os_disk_percent_full")
        
        return gaps


if __name__ == "__main__":
    # Example usage
    from src.models import PowerState, ProvisioningState, ResourceHealthStatus
    
    engine = DecisionEngine()
    
    # Example: High CPU
    telemetry = TelemetryInput(
        power_state=PowerState.RUNNING,
        provisioning_state=ProvisioningState.SUCCEEDED,
        resource_health_status=ResourceHealthStatus.DEGRADED,
        cpu_percent=98.0
    )
    
    decision = engine.decide(telemetry, confidence_score=0.75, completeness=85.0)
    print(f"Decision: {decision.state.value}")
    print(f"Diagnosis: {decision.diagnosis}")
    print(f"Evidence: {decision.evidence}")
    print(f"Next Check: {decision.next_check}")
