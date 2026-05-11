"""
Pytest configuration and fixtures for E2E tests.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock
from typing import Dict, Any

from src.models import (
    TelemetryInput, PowerState, ProvisioningState, 
    ResourceHealthStatus, BootDiagnosticsStatus,
    AzureVMAgentStatus, MonitorAgentStatus
)


@pytest.fixture
def full_telemetry_fixture():
    """Complete valid TelemetryInput with all fields."""
    return TelemetryInput(
        power_state=PowerState.RUNNING.value,
        provisioning_state=ProvisioningState.SUCCEEDED.value,
        resource_health_status=ResourceHealthStatus.AVAILABLE.value,
        resource_health_annotation=None,
        heartbeat_present=True,
        heartbeat_last_received="2026-03-31T10:00:00Z",
        boot_diagnostics_status=BootDiagnosticsStatus.NORMAL.value,
        boot_diagnostics_error=None,
        azure_vm_agent_status=AzureVMAgentStatus.HEALTHY.value,
        cpu_percent=45.5,
        memory_available_mb=4096.0,
        memory_percent=55.0,
        os_disk_latency_ms=5.2,
        data_disk_latency_ms=3.8,
        os_disk_percent_full=65.0,
        app_health_status="Healthy",
        app_error_message=None,
        nsg_allow_rdp_3389=True,
        nsg_allow_ssh_22=True,
        monitor_agent_status=MonitorAgentStatus.HEALTHY.value,
        ssl_cert_days_remaining=90,
        last_backup_status="Completed",
        last_backup_time="2026-03-31T02:00:00Z",
        data_completeness_percent=95.0,
        missing_signals=[]
    )


@pytest.fixture
def minimal_telemetry_fixture():
    """Only 3 required fields."""
    return TelemetryInput(
        power_state=PowerState.RUNNING.value,
        provisioning_state=ProvisioningState.SUCCEEDED.value,
        resource_health_status=ResourceHealthStatus.AVAILABLE.value
    )


@pytest.fixture
def pattern_telemetry_factory():
    """
    Factory function that returns full-fidelity telemetry for any of 23 patterns.
    All 20 optional fields populated at healthy baseline (100% completeness).
    Only the pattern trigger field(s) set to abnormal value.
    """
    def _factory(pattern_name: str) -> TelemetryInput:
        # Full baseline — all fields populated (100% completeness)
        base = {
            "power_state": PowerState.RUNNING.value,
            "provisioning_state": ProvisioningState.SUCCEEDED.value,
            "resource_health_status": ResourceHealthStatus.AVAILABLE.value,
            "resource_health_annotation": None,
            "heartbeat_present": True,
            "heartbeat_last_received": "2026-03-30T12:00:00Z",
            "boot_diagnostics_status": BootDiagnosticsStatus.NORMAL.value,
            "boot_diagnostics_error": None,
            "azure_vm_agent_status": AzureVMAgentStatus.HEALTHY.value,
            "cpu_percent": 35.0,
            "memory_available_mb": 3200.0,
            "memory_percent": 42.0,
            "os_disk_latency_ms": 8.5,
            "data_disk_latency_ms": 6.2,
            "os_disk_percent_full": 45.0,
            "app_health_status": "Healthy",
            "app_error_message": None,
            "nsg_allow_rdp_3389": True,
            "nsg_allow_ssh_22": True,
            "connection_troubleshoot_rdp": "Allow",
            "connection_troubleshoot_ssh": "Allow",
            "connection_troubleshoot_verdict": "Reachable",
            "monitor_agent_status": MonitorAgentStatus.HEALTHY.value,
            "ssl_cert_days_remaining": 90,
            "last_backup_status": "Completed",
            "last_backup_time": "2026-03-30T02:00:00Z",
            "data_completeness_percent": 100.0,
            "missing_signals": []
        }
        
        # Override only trigger fields per pattern
        overrides = {
            "vm_stopped_by_user": {
                "power_state": PowerState.STOPPED.value
            },
            "nsg_blocks_rdp": {
                "nsg_allow_rdp_3389": False,
                "connection_troubleshoot_rdp": "Deny"
            },
            "nsg_blocks_ssh": {
                "nsg_allow_ssh_22": False,
                "connection_troubleshoot_ssh": "Deny"
            },
            "high_cpu": {
                "cpu_percent": 97.5
            },
            "os_disk_full": {
                "os_disk_percent_full": 96.0
            },
            "memory_exhaustion": {
                "memory_percent": 96.0,
                "memory_available_mb": 128.0
            },
            "boot_bsod": {
                "boot_diagnostics_status": BootDiagnosticsStatus.BSOD.value
            },
            "boot_kernel_panic": {
                "boot_diagnostics_status": BootDiagnosticsStatus.KERNEL_PANIC.value
            },
            "vm_running_no_heartbeat": {
                "heartbeat_present": False
            },
            "resource_health_unavailable": {
                "resource_health_status": ResourceHealthStatus.UNAVAILABLE.value
            },
            "conflicting_nsg_signals": {
                "nsg_allow_rdp_3389": False,
                "connection_troubleshoot_rdp": "Allow"
            },
            "app_unhealthy_vm_healthy": {
                "app_health_status": "Unhealthy",
                "app_error_message": "Connection refused"
            },
            "disk_io_saturation": {
                "os_disk_latency_ms": 120.0
            },
            "vm_deallocated": {
                "power_state": PowerState.DEALLOCATED.value
            },
            "provisioning_failed": {
                "provisioning_state": ProvisioningState.FAILED.value
            },
            "failed_state_insufficient": {
                "power_state": PowerState.FAILED.value,
                "data_completeness_percent": 20.0,
                "missing_signals": ["cpu_percent", "memory_percent"]
            },
            "platform_degradation": {
                "resource_health_annotation": "Platform degradation detected"
            },
            "boot_stuck": {
                "boot_diagnostics_status": BootDiagnosticsStatus.STUCK.value
            },
            "vm_agent_failed": {
                "azure_vm_agent_status": AzureVMAgentStatus.FAILED.value
            },
            "monitor_agent_failed": {
                "monitor_agent_status": MonitorAgentStatus.FAILED.value
            },
            "ssl_cert_expiry_warning": {
                "ssl_cert_days_remaining": 5
            },
            "azure_backup_job_failure": {
                "last_backup_status": "Failed",
                "last_backup_time": "2024-01-15T02:00:00Z"
            },
            "vm_oversized_rightsize_candidate": {
                "cpu_percent": 5.0,
                "memory_percent": 15.0
            },
        }
        
        # Apply pattern-specific overrides
        if pattern_name in overrides:
            base.update(overrides[pattern_name])
        
        return TelemetryInput(**base)
    
    return _factory


@pytest.fixture
def mock_arg_response_factory():
    """Factory function that returns mock ARG query result."""
    def _factory(vm_state: str = "running") -> Mock:
        state_map = {
            "running": "PowerState/running",
            "stopped": "PowerState/stopped",
            "deallocated": "PowerState/deallocated",
            "failed": "PowerState/failed"
        }
        
        return Mock(
            data=[{
                'power_state': state_map.get(vm_state, "PowerState/running"),
                'prov_state': 'Succeeded',
                'vm_agent': 'Ready',
                'boot_diag': 'Normal',
                'boot_error': None,
                'health_status': 'Available',
                'health_note': None,
                'nsg_allow_rdp': True,
                'nsg_allow_ssh': True
            }]
        )
    
    return _factory


@pytest.fixture
def mock_metrics_response_factory():
    """Factory function that returns mock metrics result."""
    def _factory(cpu: float = 45.0, memory: float = 55.0) -> Dict[str, Mock]:
        def create_metric_response(value):
            metric = Mock()
            metric.timeseries = [Mock()]
            metric.timeseries[0].data = [Mock()]
            metric.timeseries[0].data[0].average = value
            return Mock(metrics=[metric])
        
        return {
            'Percentage CPU': create_metric_response(cpu),
            'Available Memory Bytes': create_metric_response(4294967296),
            'Memory\\% Committed Bytes In Use': create_metric_response(memory),
            'OS Disk Read Latency': create_metric_response(5.2),
            'Data Disk Read Latency': create_metric_response(3.8),
            'OS Disk Used Percent': create_metric_response(65.0)
        }
    
    return _factory


@pytest.fixture
def mock_logs_response_factory():
    """Factory function that returns mock logs result."""
    def _factory(heartbeat: bool = True) -> Mock:
        if heartbeat:
            return Mock(
                tables=[Mock(
                    rows=[[
                        "2026-03-31T10:00:00Z",
                        5,
                        True,
                        2
                    ]]
                )]
            )
        else:
            return Mock(tables=[])
    
    return _factory


@pytest.fixture
def temp_output_dir(tmp_path):
    """Creates and cleans up temp results/ directory."""
    output_dir = tmp_path / "results"
    output_dir.mkdir()
    yield str(output_dir) + "/"
    # Cleanup happens automatically with tmp_path
