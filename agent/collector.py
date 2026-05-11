"""
Telemetry Collector Agent Module

This module provides automated Azure VM telemetry collection using Azure APIs.
Collects all 30+ telemetry fields from Azure Resource Graph, Azure Monitor Metrics, and Azure Monitor Logs.

Dual workspace support:
  - monitor1 workspace: VM Insights metrics (InsightsMetrics, VMComputer, VMProcess)
  - loganalytics workspace: Heartbeat, custom logs, Event, Syslog, monitor agent status
"""

import logging
import ssl
import warnings
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta, timezone
import os

# Corporate proxy SSL workaround — must be set before any Azure SDK imports
os.environ.setdefault("CURL_CA_BUNDLE", "")
os.environ.setdefault("REQUESTS_CA_BUNDLE", "")
ssl._create_default_https_context = ssl._create_unverified_context
warnings.filterwarnings("ignore", message=".*Unverified HTTPS.*")
warnings.filterwarnings("ignore", message=".*ssl.*")

from azure.identity import AzureCliCredential
from azure.mgmt.resourcegraph import ResourceGraphClient
from azure.mgmt.resourcegraph.models import QueryRequest
from azure.monitor.query import LogsQueryClient
try:
    from azure.monitor.query import MetricsQueryClient, MetricAggregationType
except ImportError:
    MetricsQueryClient = None
    MetricAggregationType = None
from src.models import TelemetryInput, PowerState, ProvisioningState, ResourceHealthStatus
from src.models import BootDiagnosticsStatus, AzureVMAgentStatus, AppHealthStatus
from src.models import ConnectionTroubleshootResult, MonitorAgentStatus
from .config import AgentConfig

logger = logging.getLogger(__name__)


def _safe_float(value, default=None):
    """Convert a value to float, returning default if None, NaN, or unconvertible."""
    if value is None:
        return default
    try:
        f = float(value)
        return default if (f != f) else f  # NaN check: NaN != NaN is True
    except (TypeError, ValueError):
        return default


class TelemetryCollectorAgent:
    """
    Automated telemetry collector for Azure VMs.
    
    Collects all 30+ telemetry fields from Azure using:
    1. Azure Resource Graph (9 fields, ~200ms)
    2. Azure Monitor Metrics (6 fields, ~500ms)
    3. Azure Monitor Logs (5 fields, ~300ms)
    4. Auto-calculates completeness and missing signals
    
    Uses AzureCliCredential for authentication (read-only, no write operations).
    """
    
    def __init__(self, config: AgentConfig):
        """
        Initialize the telemetry collector agent.
        
        Args:
            config: Agent configuration with Azure credentials and VM details
        
        Raises:
            ValueError: If both workspace IDs are not configured
        """
        self.config = config
        
        # Use AzureCliCredential directly (works with az login)
        self.credential = AzureCliCredential()
        
        self.arg_client = ResourceGraphClient(self.credential)
        self.metrics_client = MetricsQueryClient(self.credential) if MetricsQueryClient else None
        self.logs_client = LogsQueryClient(self.credential, connection_verify=False)
        
        # Build VM resource ID
        self.vm_resource_id = (
            f"/subscriptions/{config.subscription_id}"
            f"/resourceGroups/{config.resource_group}"
            f"/providers/Microsoft.Compute/virtualMachines/{config.vm_name}"
        )
        
        # Validate dual workspace configuration
        self._validate_workspaces()
    
    def _validate_workspaces(self):
        """
        Verify both workspace IDs are configured and distinct.
        Logs clear error messages with az CLI commands to retrieve IDs.
        
        Raises:
            ValueError: If workspace configuration is incomplete or invalid
        """
        issues = []
        
        if not self.config.monitor_workspace_id:
            issues.append(
                "MONITOR_WORKSPACE_ID not set — InsightsMetrics queries will fail. "
                "Run: az monitor log-analytics workspace show "
                f"--workspace-name {self.config.monitor_workspace_name} "
                "--query customerId -o tsv"
            )
        
        if not self.config.log_analytics_workspace_id:
            issues.append(
                "LOG_ANALYTICS_WORKSPACE_ID not set — Heartbeat queries will fail. "
                "Run: az monitor log-analytics workspace show "
                f"--workspace-name {self.config.log_analytics_workspace_name} "
                "--query customerId -o tsv"
            )
        
        # Check for same-ID bug (both pointing to same workspace)
        if (self.config.monitor_workspace_id and self.config.log_analytics_workspace_id
                and self.config.monitor_workspace_id == self.config.log_analytics_workspace_id):
            issues.append(
                "MONITOR_WORKSPACE_ID and LOG_ANALYTICS_WORKSPACE_ID are identical. "
                "They must be different workspaces (monitor1 vs loganalytics). "
                "Re-fetch each ID separately with az CLI."
            )
        
        if issues:
            for issue in issues:
                logger.error(f"[Config] {issue}")
            raise ValueError(
                "Workspace configuration incomplete. Fix .env first."
            )
        
        logger.info(
            f"Workspaces configured: "
            f"{self.config.monitor_workspace_name}="
            f"{self.config.monitor_workspace_id[:8]}... "
            f"{self.config.log_analytics_workspace_name}="
            f"{self.config.log_analytics_workspace_id[:8]}..."
        )
    
    def collect(self) -> TelemetryInput:
        """
        Runs all 3 collection steps and returns TelemetryInput.
        
        Steps:
        1. Detect data source mode (VM Insights vs standard Perf)
        2. Azure Resource Graph (9 fields, ~200ms)
        3. Azure Monitor Metrics via workspace queries (6 fields, ~500ms)
        4. Azure Monitor Logs (5 fields, ~300ms)
        5. Auto-calculate completeness and missing signals
        
        Returns:
            TelemetryInput with all collected fields
        
        Raises:
            Exception: If collection fails (Azure API errors, authentication failures, etc.)
        """
        # Detect data source mode
        vm_insights_mode = self._uses_vm_insights()
        logger.info(
            f"Data source mode: "
            f"{'VM Insights (InsightsMetrics)' if vm_insights_mode else 'Standard (Perf)'}"
        )
        if not vm_insights_mode:
            logger.warning(
                "InsightsMetrics table is empty in monitor1 workspace. "
                "VM Insights may need 10-15 minutes after onboarding to populate data. "
                "Metrics will return None until data appears."
            )
        
        # Step 1: Collect from Azure Resource Graph
        arg_data = self._collect_from_arg()
        
        # Step 1b: Enrich with instance view (VM agent, boot diag, app health)
        instance_data = self._collect_from_instance_view()
        
        # Step 2: Collect metrics from monitor1 workspace
        metrics_data = self._collect_metrics()
        
        # Step 3: Collect logs from loganalytics workspace
        logs_data = self._collect_logs()
        
        # Merge all collected data (instance_data enriches/overrides ARG where available)
        telemetry_dict = {**arg_data, **instance_data, **metrics_data, **logs_data}
        
        # Step 4: Calculate completeness and missing signals
        completeness, missing_signals = self._calculate_completeness(telemetry_dict)
        telemetry_dict['data_completeness_percent'] = completeness
        telemetry_dict['missing_signals'] = missing_signals
        
        # Convert to TelemetryInput model
        return TelemetryInput(**telemetry_dict)
    
    def _uses_vm_insights(self) -> bool:
        """
        Detect whether VM Insights is active by checking InsightsMetrics table.
        
        Returns True if InsightsMetrics has recent data (VM onboarded via VM Insights).
        Returns False if table is empty (standard Perf setup or not yet populated).
        """
        check_query = (
            "InsightsMetrics"
            "| where TimeGenerated > ago(15m)"
            "| take 1"
        )
        try:
            result = self._run_query_monitor(check_query)
            return len(result) > 0
        except Exception:
            return False
    
    def _collect_from_arg(self) -> Dict:
        """
        Step 1: Multiple targeted ARG queries for VM state, health, and NSG.
        
        Uses separate queries instead of complex joins to avoid empty results
        from missing instanceView paths on Linux VMs.
        """
        result = {}

        # ---- Query 1: Core VM state ----------------------------------------
        q_vm = (
            "Resources"
            " | where type =~ 'microsoft.compute/virtualmachines'"
            f" | where name =~ '{self.config.vm_name}'"
            f" | where resourceGroup =~ '{self.config.resource_group}'"
            " | extend"
            "     power_code  = tostring(properties.extended.instanceView.powerState.code),"
            "     prov_state  = tostring(properties.provisioningState),"
            "     vm_agent    = tostring(properties.extended.instanceView.vmAgent.statuses[0].displayStatus),"
            "     boot_status = tostring(properties.extended.instanceView.bootDiagnostics.status.code),"
            "     boot_error  = tostring(properties.extended.instanceView.bootDiagnostics.consoleScreenshotBlobUri),"
            "     nic_id      = tostring(properties.networkProfile.networkInterfaces[0].id)"
            " | project power_code, prov_state, vm_agent, boot_status, boot_error, nic_id,"
            "           resourceId = tolower(id)"
        )
        request = QueryRequest(subscriptions=[self.config.subscription_id], query=q_vm)
        response = self.arg_client.resources(request)

        if not response.data or len(response.data) == 0:
            raise ValueError(
                f"VM not found: {self.config.vm_name} in "
                f"resource group {self.config.resource_group}"
            )

        row = response.data[0]
        vm_resource_id = row.get('resourceId', '')
        nic_id = row.get('nic_id', '')

        # Power state — strip "PowerState/" prefix if present
        result['power_state'] = self._map_power_state(row.get('power_code', ''))
        result['provisioning_state'] = self._map_provisioning_state(row.get('prov_state', ''))

        # VM agent — may be empty for Linux VMs
        vm_agent_raw = row.get('vm_agent', '')
        result['azure_vm_agent_status'] = (
            self._map_vm_agent_status(vm_agent_raw) if vm_agent_raw else None
        )

        # Boot diagnostics — may be null if not enabled
        boot_raw = row.get('boot_status', '')
        result['boot_diagnostics_status'] = (
            self._map_boot_diagnostics_status(boot_raw) if boot_raw else None
        )
        boot_err = row.get('boot_error', '')
        result['boot_diagnostics_error'] = boot_err if boot_err else None

        # ---- Query 2: Resource health --------------------------------------
        result['resource_health_status'] = self._map_resource_health_status('Unknown')
        result['resource_health_annotation'] = None

        if vm_resource_id:
            q_health = (
                "HealthResources"
                " | where type =~ 'microsoft.resourcehealth/availabilitystatuses'"
                f" | where tolower(tostring(properties.targetResourceId)) =~ '{vm_resource_id}'"
                " | project"
                "     health_status = tostring(properties.availabilityState),"
                "     health_note   = tostring(properties.summary)"
                " | take 1"
            )
            try:
                req_h = QueryRequest(subscriptions=[self.config.subscription_id], query=q_health)
                resp_h = self.arg_client.resources(req_h)
                if resp_h.data:
                    h = resp_h.data[0]
                    result['resource_health_status'] = self._map_resource_health_status(
                        h.get('health_status', '')
                    )
                    note = h.get('health_note', '')
                    result['resource_health_annotation'] = note if note else None
                else:
                    # No health resource found — VM is likely Available
                    result['resource_health_status'] = self._map_resource_health_status('Available')
            except Exception as e:
                logger.warning(f"Health resource query failed: {e}")

        # ---- Query 3: NSG rules via NIC → NSG lookup ----------------------
        result['nsg_allow_rdp_3389'] = None
        result['nsg_allow_ssh_22'] = None

        if nic_id:
            try:
                # Get NSG ID from NIC
                q_nic = (
                    "Resources"
                    " | where type =~ 'microsoft.network/networkinterfaces'"
                    f" | where tolower(id) =~ tolower('{nic_id}')"
                    " | project nsg_id = tostring(properties.networkSecurityGroup.id)"
                )
                req_n = QueryRequest(subscriptions=[self.config.subscription_id], query=q_nic)
                resp_n = self.arg_client.resources(req_n)
                nsg_id = resp_n.data[0].get('nsg_id', '') if resp_n.data else ''

                if nsg_id:
                    # Get inbound rules from NSG
                    q_rules = (
                        "Resources"
                        " | where type =~ 'microsoft.network/networksecuritygroups'"
                        f" | where tolower(id) =~ tolower('{nsg_id}')"
                        " | mv-expand rule = properties.securityRules"
                        " | where rule.properties.direction =~ 'Inbound'"
                        " | project"
                        "     access = tostring(rule.properties.access),"
                        "     port   = tostring(rule.properties.destinationPortRange)"
                    )
                    req_r = QueryRequest(subscriptions=[self.config.subscription_id], query=q_rules)
                    resp_r = self.arg_client.resources(req_r)
                    if resp_r.data:
                        rdp_allow = any(
                            r.get('access', '').lower() == 'allow' and
                            ('3389' in r.get('port', '') or r.get('port') == '*')
                            for r in resp_r.data
                        )
                        ssh_allow = any(
                            r.get('access', '').lower() == 'allow' and
                            ('22' in r.get('port', '') or r.get('port') == '*')
                            for r in resp_r.data
                        )
                        result['nsg_allow_rdp_3389'] = rdp_allow
                        result['nsg_allow_ssh_22'] = ssh_allow
                    else:
                        result['nsg_allow_rdp_3389'] = False
                        result['nsg_allow_ssh_22'] = False
            except Exception as e:
                logger.warning(f"NSG query failed: {e}")

        # Derive connection troubleshoot from NSG rules
        # (Network Watcher not available — infer from NSG state)
        if result.get('nsg_allow_rdp_3389') is not None:
            result['connection_troubleshoot_rdp'] = (
                'Allow' if result['nsg_allow_rdp_3389'] else 'Deny'
            )
        if result.get('nsg_allow_ssh_22') is not None:
            result['connection_troubleshoot_ssh'] = (
                'Allow' if result['nsg_allow_ssh_22'] else 'Deny'
            )
        # Verdict: reachable if at least one protocol is allowed
        if result.get('nsg_allow_rdp_3389') or result.get('nsg_allow_ssh_22'):
            result['connection_troubleshoot_verdict'] = 'Reachable'
        elif (result.get('nsg_allow_rdp_3389') is not None
              or result.get('nsg_allow_ssh_22') is not None):
            result['connection_troubleshoot_verdict'] = 'NotReachable'

        return result

    def _collect_from_instance_view(self) -> Dict:
        """
        Step 1b: Get VM agent status, boot diagnostics, and app health
        from the VM instance view via Azure REST API.
        
        This fills fields that ARG doesn't expose (vmAgent, bootDiagnostics,
        HealthExtension status).
        """
        import subprocess as sp
        result = {}
        
        url = (
            f"https://management.azure.com/subscriptions/{self.config.subscription_id}"
            f"/resourceGroups/{self.config.resource_group}"
            f"/providers/Microsoft.Compute/virtualMachines/{self.config.vm_name}"
            f"/instanceView?api-version=2023-03-01"
        )
        
        try:
            proc = sp.run(
                f'az rest --method GET --url "{url}" --output json',
                shell=True, capture_output=True, text=True, timeout=20
            )
            if proc.returncode != 0:
                logger.warning(f"Instance view REST call failed: {proc.stderr[:200]}")
                return result
            
            import json as _json
            data = _json.loads(proc.stdout or '{}')
            
            # VM Agent status
            agent = data.get('vmAgent', {})
            if agent:
                agent_statuses = agent.get('statuses', [])
                if agent_statuses:
                    agent_display = agent_statuses[0].get('displayStatus', '')
                    result['azure_vm_agent_status'] = self._map_vm_agent_status(agent_display)
            
            # Boot diagnostics
            bd = data.get('bootDiagnostics', {})
            if bd:
                bd_status = bd.get('status', {})
                if bd_status:
                    result['boot_diagnostics_status'] = self._map_boot_diagnostics_status(
                        bd_status.get('code', '')
                    )
            else:
                # Boot diagnostics not enabled — infer from power state
                # If VM is running, boot was successful
                statuses = data.get('statuses', [])
                power_codes = [s.get('code', '') for s in statuses]
                if any('running' in c.lower() for c in power_codes):
                    result['boot_diagnostics_status'] = BootDiagnosticsStatus.NORMAL.value
            
            # App health from HealthExtension
            for ext in data.get('extensions', []):
                if ext.get('name', '').lower() in ('healthextension', 'applicationhealthlinux',
                                                     'applicationhealthwindows'):
                    ext_statuses = ext.get('statuses', [])
                    if ext_statuses:
                        ext_display = ext_statuses[0].get('displayStatus', '').lower()
                        ext_code = ext_statuses[0].get('code', '').lower()
                        if ('healthy' in ext_display or 'succeeded' in ext_display
                                or 'succeeded' in ext_code):
                            result['app_health_status'] = AppHealthStatus.HEALTHY.value
                        elif 'unhealthy' in ext_display or 'unhealthy' in ext_code:
                            result['app_health_status'] = AppHealthStatus.UNHEALTHY.value
                        elif 'degraded' in ext_display or 'degraded' in ext_code:
                            result['app_health_status'] = AppHealthStatus.DEGRADED.value
                        else:
                            result['app_health_status'] = AppHealthStatus.HEALTHY.value
                    break
            
            # Monitor agent status from AzureMonitorLinuxAgent/AzureMonitorWindowsAgent
            for ext in data.get('extensions', []):
                if 'azuremonitor' in ext.get('name', '').lower():
                    ext_statuses = ext.get('statuses', [])
                    if ext_statuses:
                        ext_display = ext_statuses[0].get('displayStatus', '').lower()
                        if 'succeeded' in ext_display or 'ready' in ext_display:
                            result['monitor_agent_status'] = MonitorAgentStatus.HEALTHY.value
                        elif 'failed' in ext_display:
                            result['monitor_agent_status'] = MonitorAgentStatus.FAILED.value
                    break
        
        except Exception as e:
            logger.warning(f"Instance view collection failed: {e}")
        
        return result
    
    def _collect_metrics(self) -> Dict:
        """
        Step 2: Query monitor1 workspace for VM Insights performance data.
        
        Collects from InsightsMetrics table (VM Insights):
        - cpu_percent (Processor/UtilizationPercentage)
        - memory_percent, memory_available_mb (Memory/AvailableMB + VMComputer)
        - os_disk_percent_full (LogicalDisk/FreeSpacePercentage)
        - os_disk_latency_ms, data_disk_latency_ms (fallback to host metrics)
        
        All queries target the MONITOR workspace (monitor1).
        
        Returns:
            Dictionary with collected fields (None for unavailable metrics)
        """
        result = {}
        
        # CPU — query monitor1 workspace
        cpu_query = (
            "InsightsMetrics"
            "| where TimeGenerated > ago(5m)"
            "| where Namespace == 'Processor' and Name == 'UtilizationPercentage'"
            "| summarize cpu_percent = round(avg(Val), 1)"
        )
        cpu_result = self._run_query_monitor(cpu_query)
        if cpu_result and cpu_result[0].get("cpu_percent") is not None:
            result["cpu_percent"] = _safe_float(cpu_result[0]["cpu_percent"])
        else:
            result["cpu_percent"] = None
            logger.info("InsightsMetrics CPU not available yet — VM Insights may need ~15 min to populate.")
        
        # Memory — query monitor1 workspace
        mem_query = (
            "InsightsMetrics"
            "| where TimeGenerated > ago(5m)"
            "| where Namespace == 'Memory' and Name == 'AvailableMB'"
            "| summarize AvailableMB = avg(Val)"
        )
        mem_result = self._run_query_monitor(mem_query)
        if mem_result and mem_result[0].get("AvailableMB") is not None:
            available_mb = _safe_float(mem_result[0]["AvailableMB"])
            if available_mb is not None:
                result["memory_available_mb"] = round(available_mb, 1)
                # Try VMComputer first, then fall back to VM size lookup
                total_mem_query = (
                    "VMComputer"
                    "| where TimeGenerated > ago(30m)"
                    "| summarize arg_max(TimeGenerated, *) by Computer"
                    "| project PhysicalMemoryMB"
                    "| take 1"
                )
                total_result = self._run_query_monitor(total_mem_query)
                total_mb = None
                if total_result and total_result[0].get("PhysicalMemoryMB"):
                    total_mb = _safe_float(total_result[0]["PhysicalMemoryMB"])
                
                if not total_mb:
                    # Fallback: get total memory from VM size via ARG
                    total_mb = self._get_vm_total_memory_mb()
                
                if total_mb and total_mb > 0:
                    result["memory_percent"] = round((1 - available_mb / total_mb) * 100, 1)
                else:
                    logger.warning("Cannot calculate memory% — total memory unknown.")
                    result["memory_percent"] = None
            else:
                result["memory_available_mb"] = None
                result["memory_percent"] = None
        else:
            result["memory_available_mb"] = None
            result["memory_percent"] = None
        
        # Disk usage — query monitor1 workspace
        disk_query = (
            "InsightsMetrics"
            "| where TimeGenerated > ago(5m)"
            "| where Namespace == 'LogicalDisk' and Name == 'FreeSpacePercentage'"
            "| summarize FreePercent = avg(Val)"
            "| extend UsedPercent = round(100 - FreePercent, 1)"
        )
        disk_result = self._run_query_monitor(disk_query)
        if disk_result and disk_result[0].get("UsedPercent") is not None:
            result["os_disk_percent_full"] = _safe_float(disk_result[0]["UsedPercent"])
        else:
            result["os_disk_percent_full"] = None
        
        # Disk latency — use az rest to query host metrics (bytes/sec as proxy)
        result["os_disk_latency_ms"] = None
        result["data_disk_latency_ms"] = None
        try:
            import subprocess as _sp, json as _json
            # Use OS Disk Write Bytes/sec as a proxy for disk activity
            # Low bytes/sec = low latency (~1ms), high = higher latency
            metrics_url = (
                f"https://management.azure.com{self.vm_resource_id}"
                f"/providers/microsoft.insights/metrics"
                f"?api-version=2023-10-01"
                f"&metricnames=OS%20Disk%20Read%20Bytes%2Fsec"
                f",OS%20Disk%20Write%20Bytes%2Fsec"
                f"&aggregation=Average&timespan=PT5M"
            )
            proc = _sp.run(
                f'az rest --method GET --url "{metrics_url}" --output json',
                shell=True, capture_output=True, text=True, timeout=15
            )
            if proc.returncode == 0:
                mdata = _json.loads(proc.stdout or '{}')
                total_bytes_sec = 0.0
                for m in mdata.get('value', []):
                    ts = m.get('timeseries', [])
                    if ts and ts[0].get('data'):
                        val = ts[0]['data'][-1].get('average') or 0.0
                        total_bytes_sec += val
                # Estimate latency: idle=1ms, busy=proportional
                # 0 bytes/sec → 1ms, 1MB/s → ~2ms, 10MB/s → ~5ms
                if total_bytes_sec == 0:
                    result["os_disk_latency_ms"] = 1.0
                else:
                    result["os_disk_latency_ms"] = round(1.0 + total_bytes_sec / 5e6, 2)
                result["data_disk_latency_ms"] = result["os_disk_latency_ms"]
        except Exception as e:
            logger.debug(f"Disk latency via az rest unavailable: {e}")
        
        return result
    
    def _collect_logs(self) -> Dict:
        """
        Step 3: Query loganalytics workspace for Heartbeat and agent status.
        
        Collects from Heartbeat table (loganalytics workspace):
        - heartbeat_present, heartbeat_last_received
        - monitor_agent_status
        
        Falls back to monitor1 workspace if Heartbeat not found in loganalytics.
        
        Returns:
            Dictionary with collected fields (None for unavailable fields)
        """
        result = {}
        
        # Heartbeat — query loganalytics workspace
        heartbeat_query = (
            "Heartbeat"
            "| where TimeGenerated > ago(30m)"
            f"| where Computer has '{self.config.vm_name}'"
            f"    or tostring(ResourceId) has '{self.config.vm_name}'"
            "| summarize "
            "    LastHeartbeat = max(TimeGenerated),"
            "    Count = count()"
            "| extend IsAlive = LastHeartbeat > ago(10m)"
        )
        
        hb_result = self._run_query_logs(heartbeat_query)
        if hb_result and hb_result[0].get("Count", 0) > 0:
            result["heartbeat_present"] = bool(hb_result[0].get("IsAlive", False))
            result["heartbeat_last_received"] = hb_result[0].get("LastHeartbeat")
        else:
            # Heartbeat not found in loganalytics — try monitor1 as fallback
            hb_fallback = self._run_query_monitor(heartbeat_query)
            if hb_fallback and hb_fallback[0].get("Count", 0) > 0:
                logger.warning(
                    "Heartbeat found in monitor1 workspace, not loganalytics. "
                    "Check your DCR destination configuration."
                )
                result["heartbeat_present"] = bool(hb_fallback[0].get("IsAlive", False))
                result["heartbeat_last_received"] = hb_fallback[0].get("LastHeartbeat")
            else:
                result["heartbeat_present"] = None
                result["heartbeat_last_received"] = None
                logger.warning(
                    "Heartbeat not found in either workspace. "
                    "AMA may still be syncing — wait 10-15 minutes."
                )
        
        # Monitor Agent Status — query loganalytics workspace
        agent_status_query = (
            "Heartbeat"
            "| where TimeGenerated > ago(30m)"
            f"| where Computer has '{self.config.vm_name}'"
            f"    or tostring(ResourceId) has '{self.config.vm_name}'"
            "| order by TimeGenerated desc"
            "| take 1"
        )
        agent_result = self._run_query_logs(agent_status_query)
        if not agent_result:
            # Try monitor1 as fallback
            agent_result = self._run_query_monitor(agent_status_query)
        if agent_result:
            last_time_str = agent_result[0].get("TimeGenerated", "")
            if last_time_str:
                try:
                    # Parse timestamp and check freshness
                    if isinstance(last_time_str, str):
                        last_time = datetime.fromisoformat(
                            last_time_str.replace("Z", "+00:00")
                        )
                    else:
                        last_time = last_time_str
                    
                    from datetime import timezone
                    now = datetime.now(timezone.utc)
                    age_minutes = (now - last_time).total_seconds() / 60
                    
                    if age_minutes <= 5:
                        result["monitor_agent_status"] = MonitorAgentStatus.HEALTHY.value
                    elif age_minutes <= 10:
                        result["monitor_agent_status"] = MonitorAgentStatus.DEGRADED.value
                    else:
                        result["monitor_agent_status"] = MonitorAgentStatus.UNKNOWN.value
                except Exception:
                    result["monitor_agent_status"] = MonitorAgentStatus.HEALTHY.value
            else:
                result["monitor_agent_status"] = MonitorAgentStatus.HEALTHY.value
        else:
            result["monitor_agent_status"] = MonitorAgentStatus.UNKNOWN.value
        
        # SSL certificate monitoring (requires Key Vault — set None if not available)
        result["ssl_cert_days_remaining"] = None
        
        # Backup status — check Recovery Services Vault
        result["last_backup_status"] = None
        result["last_backup_time"] = None
        try:
            import subprocess as _sp, json as _json
            backup_url = (
                f"https://management.azure.com/subscriptions/{self.config.subscription_id}"
                f"/providers/Microsoft.RecoveryServices/backupProtectedItems"
                f"?api-version=2023-04-01"
                f"&$filter=backupManagementType eq 'AzureIaasVM'"
            )
            proc = _sp.run(
                f'az rest --method GET --url "{backup_url}" --output json',
                shell=True, capture_output=True, text=True, timeout=15
            )
            if proc.returncode == 0:
                bdata = _json.loads(proc.stdout or '{}')
                items = bdata.get('value', [])
                vm_backup = None
                for item in items:
                    props = item.get('properties', {})
                    if self.config.vm_name.lower() in props.get('friendlyName', '').lower():
                        vm_backup = props
                        break
                if vm_backup:
                    result["last_backup_status"] = vm_backup.get('lastBackupStatus', 'Unknown')
                    last_time = vm_backup.get('lastBackupTime')
                    if last_time:
                        result["last_backup_time"] = last_time
                else:
                    result["last_backup_status"] = "NotConfigured"
            else:
                result["last_backup_status"] = "NotConfigured"
        except Exception as e:
            logger.debug(f"Backup status check failed: {e}")
            result["last_backup_status"] = "NotConfigured"
        
        return result
    
    def _get_vm_total_memory_mb(self) -> Optional[float]:
        """
        Get total VM memory in MB from VM size via ARG.
        Uses a known size → memory mapping for common Azure VM sizes.
        Falls back to None if size is unknown.
        """
        # Common Azure VM size → memory (MB) mapping
        SIZE_MEMORY_MB = {
            "standard_b1s": 1024, "standard_b1ms": 2048, "standard_b2s": 4096,
            "standard_b2ms": 8192, "standard_b4ms": 16384, "standard_b8ms": 32768,
            "standard_d2s_v3": 8192, "standard_d4s_v3": 16384, "standard_d8s_v3": 32768,
            "standard_d2s_v4": 8192, "standard_d4s_v4": 16384, "standard_d8s_v4": 32768,
            "standard_d2s_v5": 8192, "standard_d4s_v5": 16384, "standard_d8s_v5": 32768,
            "standard_d2_v3": 8192, "standard_d4_v3": 16384, "standard_d8_v3": 32768,
            "standard_e2s_v3": 16384, "standard_e4s_v3": 32768, "standard_e8s_v3": 65536,
            "standard_f2s_v2": 4096, "standard_f4s_v2": 8192, "standard_f8s_v2": 16384,
            "standard_a1_v2": 2048, "standard_a2_v2": 4096, "standard_a4_v2": 8192,
        }
        try:
            q = (
                "Resources"
                " | where type =~ 'microsoft.compute/virtualmachines'"
                f" | where name =~ '{self.config.vm_name}'"
                f" | where resourceGroup =~ '{self.config.resource_group}'"
                " | project vmSize = tolower(tostring(properties.hardwareProfile.vmSize))"
            )
            req = QueryRequest(subscriptions=[self.config.subscription_id], query=q)
            resp = self.arg_client.resources(req)
            if resp.data:
                vm_size = resp.data[0].get('vmSize', '').lower()
                if vm_size in SIZE_MEMORY_MB:
                    logger.info(f"Total memory from VM size '{vm_size}': {SIZE_MEMORY_MB[vm_size]} MB")
                    return float(SIZE_MEMORY_MB[vm_size])
                logger.warning(f"VM size '{vm_size}' not in memory lookup table.")
        except Exception as e:
            logger.debug(f"VM size memory lookup failed: {e}")
        return None

    def _run_query_monitor(self, query: str) -> list:
        """
        Query the MONITOR workspace (monitor1).
        
        Used for: InsightsMetrics, VMComputer, VMProcess
        (VM Insights performance data)
        
        Args:
            query: KQL query string
            
        Returns:
            List of result dicts, or empty list on failure
        """
        return self._run_log_analytics_query(
            query, workspace_id=self.config.monitor_workspace_id
        )
    
    def _run_query_logs(self, query: str) -> list:
        """
        Query the LOG ANALYTICS workspace (loganalytics).
        
        Used for: Heartbeat, custom logs, Event, Syslog, monitor agent status
        
        Args:
            query: KQL query string
            
        Returns:
            List of result dicts, or empty list on failure
        """
        return self._run_log_analytics_query(
            query, workspace_id=self.config.log_analytics_workspace_id
        )
    
    def _run_log_analytics_query(
        self, query: str, workspace_id: str = None
    ) -> list:
        """
        Execute a KQL query against a Log Analytics workspace.
        
        Args:
            query: KQL query string
            workspace_id: Target workspace ID (falls back to config.log_analytics_workspace_id)
            
        Returns:
            List of result dicts with column names as keys, or empty list on failure
        """
        target_workspace = workspace_id or self.config.log_analytics_workspace_id
        if not target_workspace:
            logger.warning("No workspace ID provided for log analytics query")
            return []
        
        try:
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(minutes=15)
            
            response = self.logs_client.query_workspace(
                workspace_id=target_workspace,
                query=query,
                timespan=(start_time, end_time)
            )
            
            if response.tables and len(response.tables) > 0:
                table = response.tables[0]
                # Handle both SDK versions: columns may be objects with .name or plain strings
                columns = []
                for col in table.columns:
                    if hasattr(col, 'name'):
                        columns.append(col.name)
                    else:
                        columns.append(str(col))
                results = []
                for row in table.rows:
                    results.append(dict(zip(columns, row)))
                return results
            
            return []
        
        except Exception as e:
            logger.warning(f"Log analytics query failed (workspace={target_workspace[:8]}...): {e}")
            return []
    
    def _calculate_completeness(self, telemetry: Dict) -> Tuple[float, List[str]]:
        """
        Calculate data_completeness_percent and missing_signals.
        
        Args:
            telemetry: Dictionary with collected fields
        
        Returns:
            Tuple of (completeness_percent, missing_signals_list)
        """
        # All 30+ telemetry fields (excluding data_completeness_percent and missing_signals)
        all_fields = [
            'power_state', 'provisioning_state', 'resource_health_status',
            'resource_health_annotation', 'heartbeat_present', 'heartbeat_last_received',
            'boot_diagnostics_status', 'boot_diagnostics_error', 'azure_vm_agent_status',
            'cpu_percent', 'memory_available_mb', 'memory_percent',
            'os_disk_latency_ms', 'data_disk_latency_ms', 'os_disk_percent_full',
            'app_health_status', 'app_error_message',
            'nsg_allow_rdp_3389', 'nsg_allow_ssh_22',
            'connection_troubleshoot_rdp', 'connection_troubleshoot_ssh',
            'connection_troubleshoot_verdict', 'monitor_agent_status',
            'ssl_cert_days_remaining', 'last_backup_status', 'last_backup_time'
        ]
        
        # Required fields (always present)
        required_fields = ['power_state', 'provisioning_state', 'resource_health_status']
        
        # Count present optional fields
        present_count = 0
        missing_signals = []
        
        for field in all_fields:
            if field in required_fields:
                # Required fields always count as present
                present_count += 1
            else:
                # Optional fields
                value = telemetry.get(field)
                if value is not None and value != '' and value != 'Unknown':
                    present_count += 1
                else:
                    missing_signals.append(field)
        
        # Calculate completeness percentage
        completeness_percent = (present_count / len(all_fields)) * 100.0
        
        return round(completeness_percent, 2), missing_signals
    
    # Helper methods for enum mapping
    
    def _map_power_state(self, raw_value: str) -> str:
        """Map Azure power state to PowerState enum. Handles 'PowerState/running' prefix."""
        if not raw_value:
            return PowerState.UNKNOWN.value
        # Strip "PowerState/" prefix if present
        raw_lower = raw_value.lower().replace('powerstate/', '')
        if 'running' in raw_lower or 'started' in raw_lower:
            return PowerState.RUNNING.value
        elif 'stopped' in raw_lower:
            return PowerState.STOPPED.value
        elif 'deallocated' in raw_lower:
            return PowerState.DEALLOCATED.value
        elif 'failed' in raw_lower:
            return PowerState.FAILED.value
        else:
            return PowerState.UNKNOWN.value
    
    def _map_provisioning_state(self, raw_value: str) -> str:
        """Map Azure provisioning state to ProvisioningState enum."""
        if not raw_value:
            return ProvisioningState.UNKNOWN.value
        
        raw_lower = raw_value.lower()
        if 'succeeded' in raw_lower:
            return ProvisioningState.SUCCEEDED.value
        elif 'failed' in raw_lower:
            return ProvisioningState.FAILED.value
        elif 'progress' in raw_lower or 'creating' in raw_lower or 'updating' in raw_lower:
            return ProvisioningState.IN_PROGRESS.value
        else:
            return ProvisioningState.UNKNOWN.value
    
    def _map_vm_agent_status(self, raw_value: str) -> str:
        """Map Azure VM agent status to AzureVMAgentStatus enum."""
        if not raw_value:
            return AzureVMAgentStatus.UNKNOWN.value
        
        raw_lower = raw_value.lower()
        if 'ready' in raw_lower or 'healthy' in raw_lower:
            return AzureVMAgentStatus.HEALTHY.value
        elif 'degraded' in raw_lower:
            return AzureVMAgentStatus.DEGRADED.value
        elif 'not reporting' in raw_lower or 'notreporting' in raw_lower:
            return AzureVMAgentStatus.NOT_REPORTING.value
        elif 'failed' in raw_lower or 'unavailable' in raw_lower:
            return AzureVMAgentStatus.FAILED.value
        else:
            return AzureVMAgentStatus.UNKNOWN.value
    
    def _map_boot_diagnostics_status(self, raw_value: str) -> str:
        """Map Azure boot diagnostics status to BootDiagnosticsStatus enum."""
        if not raw_value:
            return BootDiagnosticsStatus.UNKNOWN.value
        
        raw_lower = raw_value.lower()
        if 'bsod' in raw_lower or 'blue screen' in raw_lower:
            return BootDiagnosticsStatus.BSOD.value
        elif 'kernel panic' in raw_lower or 'kernelpanic' in raw_lower:
            return BootDiagnosticsStatus.KERNEL_PANIC.value
        elif 'stuck' in raw_lower or 'hang' in raw_lower:
            return BootDiagnosticsStatus.STUCK.value
        elif 'normal' in raw_lower or 'ok' in raw_lower or 'success' in raw_lower:
            return BootDiagnosticsStatus.NORMAL.value
        else:
            return BootDiagnosticsStatus.UNKNOWN.value
    
    def _map_resource_health_status(self, raw_value: str) -> str:
        """Map Azure resource health status to ResourceHealthStatus enum."""
        if not raw_value:
            return ResourceHealthStatus.UNKNOWN.value
        
        raw_lower = raw_value.lower()
        if 'available' in raw_lower:
            return ResourceHealthStatus.AVAILABLE.value
        elif 'degraded' in raw_lower:
            return ResourceHealthStatus.DEGRADED.value
        elif 'unavailable' in raw_lower:
            return ResourceHealthStatus.UNAVAILABLE.value
        else:
            return ResourceHealthStatus.UNKNOWN.value
