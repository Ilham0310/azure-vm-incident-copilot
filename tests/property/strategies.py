"""
Hypothesis strategies for property-based testing.

This module provides strategies for generating test data:
- valid_telemetry_strategy(): Generates valid telemetry with random field combinations
- invalid_enum_strategy(): Generates telemetry with invalid enum values
- out_of_range_numeric_strategy(): Generates telemetry with out-of-range numbers
- low_completeness_strategy(): Generates telemetry with <60% completeness
- platform_event_strategy(): Generates telemetry with platform event annotations
- boot_failure_strategy(): Generates telemetry with BSOD/KernelPanic status

Configured with max_examples=100 and deterministic seed for reproducibility.
"""

from datetime import datetime, timedelta
from hypothesis import strategies as st
from hypothesis import settings, Phase
from typing import Dict, Any

# Import enums from models
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.models import (
    PowerState,
    ProvisioningState,
    ResourceHealthStatus,
    BootDiagnosticsStatus,
    AzureVMAgentStatus,
    AppHealthStatus,
    ConnectionTroubleshootResult,
    MonitorAgentStatus
)


# ============================================================================
# Configure Hypothesis Settings
# ============================================================================

# Register custom profile for property-based tests
settings.register_profile(
    "pbt_profile",
    max_examples=100,
    deadline=None,
    phases=[Phase.explicit, Phase.reuse, Phase.generate, Phase.target]
)
settings.load_profile("pbt_profile")


# ============================================================================
# Basic Strategies for Enum Types
# ============================================================================

power_state_strategy = st.sampled_from([e.value for e in PowerState])
provisioning_state_strategy = st.sampled_from([e.value for e in ProvisioningState])
resource_health_status_strategy = st.sampled_from([e.value for e in ResourceHealthStatus])
boot_diagnostics_status_strategy = st.sampled_from([e.value for e in BootDiagnosticsStatus])
azure_vm_agent_status_strategy = st.sampled_from([e.value for e in AzureVMAgentStatus])
app_health_status_strategy = st.sampled_from([e.value for e in AppHealthStatus])
connection_troubleshoot_strategy = st.sampled_from([e.value for e in ConnectionTroubleshootResult])
monitor_agent_status_strategy = st.sampled_from([e.value for e in MonitorAgentStatus])


# ============================================================================
# Basic Strategies for Numeric Fields
# ============================================================================

percentage_strategy = st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
latency_strategy = st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False)
memory_mb_strategy = st.floats(min_value=0.0, max_value=65536.0, allow_nan=False, allow_infinity=False)


# ============================================================================
# Basic Strategies for Other Fields
# ============================================================================

datetime_strategy = st.datetimes(
    min_value=datetime(2020, 1, 1),
    max_value=datetime(2030, 12, 31)
)

text_strategy = st.text(min_size=1, max_size=200)
signal_list_strategy = st.lists(st.text(min_size=1, max_size=50), min_size=0, max_size=10)


# ============================================================================
# Strategy 1: Valid Telemetry with Random Field Combinations
# ============================================================================

@st.composite
def valid_telemetry_strategy(draw):
    """
    Generates valid telemetry with random field combinations.
    
    Always includes required fields (power_state, provisioning_state, resource_health_status).
    Randomly includes optional fields to vary completeness.
    
    Returns:
        Dictionary representing valid telemetry input
    """
    telemetry = {
        # Required fields (always present)
        "power_state": draw(power_state_strategy),
        "provisioning_state": draw(provisioning_state_strategy),
        "resource_health_status": draw(resource_health_status_strategy),
    }
    
    # Optional fields (randomly included)
    if draw(st.booleans()):
        telemetry["resource_health_annotation"] = draw(st.one_of(st.none(), text_strategy))
    
    if draw(st.booleans()):
        telemetry["heartbeat_present"] = draw(st.booleans())
    
    if draw(st.booleans()):
        dt = draw(st.one_of(st.none(), datetime_strategy))
        telemetry["heartbeat_last_received"] = dt.isoformat() if dt else None
    
    if draw(st.booleans()):
        telemetry["boot_diagnostics_status"] = draw(st.one_of(st.none(), boot_diagnostics_status_strategy))
    
    if draw(st.booleans()):
        telemetry["boot_diagnostics_error"] = draw(st.one_of(st.none(), text_strategy))
    
    if draw(st.booleans()):
        telemetry["azure_vm_agent_status"] = draw(st.one_of(st.none(), azure_vm_agent_status_strategy))
    
    if draw(st.booleans()):
        telemetry["cpu_percent"] = draw(st.one_of(st.none(), percentage_strategy))
    
    if draw(st.booleans()):
        telemetry["memory_available_mb"] = draw(st.one_of(st.none(), memory_mb_strategy))
    
    if draw(st.booleans()):
        telemetry["memory_percent"] = draw(st.one_of(st.none(), percentage_strategy))
    
    if draw(st.booleans()):
        telemetry["os_disk_latency_ms"] = draw(st.one_of(st.none(), latency_strategy))
    
    if draw(st.booleans()):
        telemetry["data_disk_latency_ms"] = draw(st.one_of(st.none(), latency_strategy))
    
    if draw(st.booleans()):
        telemetry["os_disk_percent_full"] = draw(st.one_of(st.none(), percentage_strategy))
    
    if draw(st.booleans()):
        telemetry["app_health_status"] = draw(st.one_of(st.none(), app_health_status_strategy))
    
    if draw(st.booleans()):
        telemetry["app_error_message"] = draw(st.one_of(st.none(), text_strategy))
    
    if draw(st.booleans()):
        telemetry["nsg_allow_rdp_3389"] = draw(st.one_of(st.none(), st.booleans()))
    
    if draw(st.booleans()):
        telemetry["nsg_allow_ssh_22"] = draw(st.one_of(st.none(), st.booleans()))
    
    if draw(st.booleans()):
        telemetry["connection_troubleshoot_rdp"] = draw(st.one_of(st.none(), connection_troubleshoot_strategy))
    
    if draw(st.booleans()):
        telemetry["connection_troubleshoot_ssh"] = draw(st.one_of(st.none(), connection_troubleshoot_strategy))
    
    if draw(st.booleans()):
        telemetry["connection_troubleshoot_verdict"] = draw(st.one_of(st.none(), text_strategy))
    
    if draw(st.booleans()):
        telemetry["monitor_agent_status"] = draw(st.one_of(st.none(), monitor_agent_status_strategy))
    
    if draw(st.booleans()):
        telemetry["data_completeness_percent"] = draw(st.one_of(st.none(), percentage_strategy))
    
    if draw(st.booleans()):
        telemetry["missing_signals"] = draw(st.one_of(st.none(), signal_list_strategy))
    
    return telemetry


# ============================================================================
# Strategy 2: Invalid Enum Values
# ============================================================================

@st.composite
def invalid_enum_strategy(draw):
    """
    Generates telemetry with invalid enum values.
    
    Includes required fields but with at least one invalid enum value.
    
    Returns:
        Dictionary with invalid enum value(s)
    """
    # Start with valid required fields
    telemetry = {
        "power_state": draw(power_state_strategy),
        "provisioning_state": draw(provisioning_state_strategy),
        "resource_health_status": draw(resource_health_status_strategy),
    }
    
    # Pick a random enum field to make invalid
    invalid_field = draw(st.sampled_from([
        "power_state",
        "provisioning_state",
        "resource_health_status",
        "boot_diagnostics_status",
        "azure_vm_agent_status",
        "app_health_status",
        "connection_troubleshoot_rdp",
        "connection_troubleshoot_ssh",
        "monitor_agent_status"
    ]))
    
    # Generate invalid enum value (not in valid set)
    invalid_value = draw(st.text(min_size=1, max_size=50).filter(
        lambda x: x not in ["Running", "Stopped", "Deallocated", "Failed", "Unknown",
                           "Succeeded", "In Progress",
                           "Available", "Degraded", "Unavailable",
                           "Normal", "BSOD", "KernelPanic", "Stuck",
                           "Healthy", "NotReporting", "NotInstalled", "Unhealthy",
                           "Allow", "Deny", "Inconclusive", "Timeout"]
    ))
    
    telemetry[invalid_field] = invalid_value
    
    return telemetry


# ============================================================================
# Strategy 3: Out-of-Range Numeric Values
# ============================================================================

@st.composite
def out_of_range_numeric_strategy(draw):
    """
    Generates telemetry with out-of-range numeric values.
    
    Includes required fields but with at least one numeric field outside valid range.
    
    Returns:
        Dictionary with out-of-range numeric value(s)
    """
    telemetry = {
        "power_state": draw(power_state_strategy),
        "provisioning_state": draw(provisioning_state_strategy),
        "resource_health_status": draw(resource_health_status_strategy),
    }
    
    # Pick a random numeric field to make out-of-range
    invalid_field = draw(st.sampled_from([
        "cpu_percent",
        "memory_percent",
        "os_disk_percent_full",
        "data_completeness_percent",
        "os_disk_latency_ms",
        "data_disk_latency_ms",
        "memory_available_mb"
    ]))
    
    # Generate out-of-range value
    if "percent" in invalid_field:
        # Percentage fields: valid range 0-100, generate outside this
        invalid_value = draw(st.one_of(
            st.floats(min_value=-1000.0, max_value=-0.1),
            st.floats(min_value=100.1, max_value=1000.0)
        ))
    else:
        # Other numeric fields: valid range >= 0, generate negative
        invalid_value = draw(st.floats(min_value=-1000.0, max_value=-0.1))
    
    telemetry[invalid_field] = invalid_value
    
    return telemetry


# ============================================================================
# Strategy 4: Low Completeness (<60%)
# ============================================================================

@st.composite
def low_completeness_strategy(draw):
    """
    Generates telemetry with <60% completeness.
    
    Includes only required fields and a few optional fields to ensure low completeness.
    
    Returns:
        Dictionary with low completeness
    """
    telemetry = {
        "power_state": draw(power_state_strategy),
        "provisioning_state": draw(provisioning_state_strategy),
        "resource_health_status": draw(resource_health_status_strategy),
    }
    
    # Add only 0-3 optional fields to keep completeness low
    num_optional = draw(st.integers(min_value=0, max_value=3))
    
    optional_fields = [
        ("cpu_percent", percentage_strategy),
        ("memory_percent", percentage_strategy),
        ("heartbeat_present", st.booleans()),
    ]
    
    selected_fields = draw(st.lists(
        st.sampled_from(optional_fields),
        min_size=0,
        max_size=min(num_optional, len(optional_fields)),
        unique=True
    ))
    
    for field_name, strategy in selected_fields:
        telemetry[field_name] = draw(strategy)
    
    # Explicitly set low completeness
    telemetry["data_completeness_percent"] = draw(st.floats(min_value=0.0, max_value=59.9))
    
    return telemetry


# ============================================================================
# Strategy 5: Platform Event Annotations
# ============================================================================

@st.composite
def platform_event_strategy(draw):
    """
    Generates telemetry with platform event annotations.
    
    Includes resource_health_annotation with platform event keywords.
    
    Returns:
        Dictionary with platform event annotation
    """
    telemetry = {
        "power_state": draw(power_state_strategy),
        "provisioning_state": draw(provisioning_state_strategy),
        "resource_health_status": draw(st.sampled_from([
            ResourceHealthStatus.DEGRADED.value,
            ResourceHealthStatus.UNAVAILABLE.value
        ])),
    }
    
    # Add platform event keyword to annotation
    platform_keywords = [
        "platform maintenance in progress",
        "host update scheduled",
        "planned maintenance window",
        "platform degradation detected",
        "Azure platform event"
    ]
    
    telemetry["resource_health_annotation"] = draw(st.sampled_from(platform_keywords))
    
    # Add some optional fields
    if draw(st.booleans()):
        telemetry["cpu_percent"] = draw(percentage_strategy)
    if draw(st.booleans()):
        telemetry["memory_percent"] = draw(percentage_strategy)
    
    return telemetry


# ============================================================================
# Strategy 6: Boot Failure (BSOD/KernelPanic)
# ============================================================================

@st.composite
def boot_failure_strategy(draw):
    """
    Generates telemetry with BSOD or KernelPanic boot diagnostics status.
    
    Returns:
        Dictionary with boot failure status
    """
    telemetry = {
        "power_state": draw(st.sampled_from([
            PowerState.RUNNING.value,
            PowerState.FAILED.value
        ])),
        "provisioning_state": draw(provisioning_state_strategy),
        "resource_health_status": draw(st.sampled_from([
            ResourceHealthStatus.UNAVAILABLE.value,
            ResourceHealthStatus.DEGRADED.value
        ])),
    }
    
    # Set boot failure status
    telemetry["boot_diagnostics_status"] = draw(st.sampled_from([
        BootDiagnosticsStatus.BSOD.value,
        BootDiagnosticsStatus.KERNEL_PANIC.value
    ]))
    
    # Add boot error message
    boot_errors = [
        "CRITICAL_PROCESS_DIED",
        "SYSTEM_SERVICE_EXCEPTION",
        "Kernel panic - not syncing",
        "Unable to mount root fs",
        "IRQL_NOT_LESS_OR_EQUAL"
    ]
    telemetry["boot_diagnostics_error"] = draw(st.sampled_from(boot_errors))
    
    # Add some optional fields
    if draw(st.booleans()):
        telemetry["heartbeat_present"] = False
    if draw(st.booleans()):
        telemetry["azure_vm_agent_status"] = AzureVMAgentStatus.NOT_REPORTING.value
    
    return telemetry
