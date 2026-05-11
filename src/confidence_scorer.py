"""
Confidence scoring component for Azure VM Incident Copilot.

This module provides the ConfidenceScorer class that:
- Calculates data completeness percentage (0-100)
- Calculates confidence score (0.0-1.0) using weighted algorithm
- Detects signal conflicts (none, minor, major)
- Weights pattern matches (exact, partial, none)

Confidence Formula:
    confidence_score = (completeness_weight * 0.4) + 
                       (pattern_weight * 0.3) + 
                       (consistency_weight * 0.3)
"""

from typing import Optional, Tuple
from src.models import TelemetryInput, PowerState, ResourceHealthStatus


class ConfidenceScorer:
    """
    Calculates data completeness and confidence scores.
    
    Responsibilities:
    - Calculate completeness percentage by counting non-null optional fields
    - Calculate confidence score using weighted algorithm (40% completeness, 30% pattern, 30% consistency)
    - Detect signal conflicts (none, minor, major)
    - Weight pattern matches (exact, partial, none)
    """
    
    # Required fields (always present, not counted in completeness)
    REQUIRED_FIELDS = ["power_state", "provisioning_state", "resource_health_status"]
    
    # Optional fields (counted for completeness calculation)
    # Note: Error message fields (resource_health_annotation, boot_diagnostics_error, app_error_message)
    #       are only present when there's an error, so they're not counted in completeness
    # Note: data_completeness_percent and missing_signals are metadata fields, not counted
    OPTIONAL_FIELDS = [
        "heartbeat_present",
        "heartbeat_last_received",
        "boot_diagnostics_status",
        "azure_vm_agent_status",
        "cpu_percent",
        "memory_available_mb",
        "memory_percent",
        "os_disk_latency_ms",
        "data_disk_latency_ms",
        "os_disk_percent_full",
        "app_health_status",
        "nsg_allow_rdp_3389",
        "nsg_allow_ssh_22",
        "connection_troubleshoot_rdp",
        "connection_troubleshoot_ssh",
        "connection_troubleshoot_verdict",
        "monitor_agent_status",
        "ssl_cert_days_remaining",
        "last_backup_status",
        "last_backup_time"
    ]
    
    TOTAL_OPTIONAL = 20  # Updated from 17 to 20
    
    def calculate_completeness(self, telemetry: TelemetryInput) -> float:
        """
        Calculates data completeness percentage (0-100).
        
        Counts non-null optional fields and calculates percentage.
        Required fields: power_state, provisioning_state, resource_health_status (not counted)
        Optional fields: All other 17 fields
        
        Args:
            telemetry: Validated telemetry input
            
        Returns:
            Completeness percentage (0.0-100.0)
        """
        # Count non-null optional fields
        populated_count = 0
        
        for field_name in self.OPTIONAL_FIELDS:
            value = getattr(telemetry, field_name, None)
            if value is not None:
                populated_count += 1
        
        # Calculate percentage
        if self.TOTAL_OPTIONAL == 0:
            return 100.0
        
        completeness = (populated_count / self.TOTAL_OPTIONAL) * 100.0
        return round(completeness, 2)
    
    def calculate_confidence(
        self,
        telemetry: TelemetryInput,
        completeness: float,
        pattern_match: Optional[str],
        signal_conflicts: str
    ) -> float:
        """
        Calculates confidence score (0.0-1.0) using weighted algorithm.

        Formula:
            s = 0.4 * (completeness / 100)
              + 0.3 * p
              + 0.3 * q

        where p and q are sub-scores in [0, 1]:
            p = 1.0 (exact pattern match) | 0.5 (partial) | 0.0 (none)
            q = 1.0 (no conflicts)        | 0.5 (minor)   | 0.0 (major)

        Max attainable score is 1.0 (completeness=100%, p=q=1.0).
        The 0.9 threshold used by safety rules SR-3/SR-5 is reachable only
        when completeness >= ~87.5% with exact pattern and no conflicts.

        Args:
            telemetry: Validated telemetry input
            completeness: Data completeness percentage (0-100)
            pattern_match: "exact", "partial", or None
            signal_conflicts: "none", "minor", or "major"

        Returns:
            Confidence score in [0.0, 1.0]
        """
        # Component 1: Data completeness, weighted 0.4
        completeness_term = (completeness / 100.0) * 0.4

        # Component 2: Pattern-match sub-score p in [0, 1], weighted 0.3
        if pattern_match == "exact":
            p = 1.0
        elif pattern_match == "partial":
            p = 0.5
        else:  # None
            p = 0.0
        pattern_term = 0.3 * p

        # Component 3: Signal-consistency sub-score q in [0, 1], weighted 0.3
        if signal_conflicts == "none":
            q = 1.0
        elif signal_conflicts == "minor":
            q = 0.5
        else:  # "major"
            q = 0.0
        consistency_term = 0.3 * q

        # Weighted sum, clamped to [0, 1] defensively
        confidence_score = completeness_term + pattern_term + consistency_term
        confidence_score = max(0.0, min(1.0, confidence_score))

        return round(confidence_score, 2)
    
    def detect_signal_conflicts(self, telemetry: TelemetryInput) -> str:
        """
        Detects signal conflicts in telemetry data.
        
        Returns "none", "minor", or "major" based on conflict severity.
        
        Minor conflicts (explainable):
        - power_state=Running + heartbeat_present=false (VM running but agent not reporting)
        - nsg_allow_rdp_3389=false + connection_troubleshoot_rdp=Allow (NSG vs troubleshoot mismatch)
        - nsg_allow_ssh_22=false + connection_troubleshoot_ssh=Allow (NSG vs troubleshoot mismatch)
        
        Major conflicts (unresolvable):
        - power_state=Running + resource_health_status=Unavailable + all metrics normal
        - power_state=Stopped + cpu_percent > 90 (stopped VM with high CPU)
        - power_state=Deallocated + cpu_percent > 0 (deallocated VM with CPU usage)
        
        Args:
            telemetry: Validated telemetry input
            
        Returns:
            "none", "minor", or "major"
        """
        conflicts = []
        
        # Check for major conflicts first
        
        # Major conflict 1: Stopped/Deallocated VM with high CPU
        if telemetry.power_state in [PowerState.STOPPED, PowerState.DEALLOCATED]:
            if telemetry.cpu_percent is not None and telemetry.cpu_percent > 90:
                return "major"
        
        # Major conflict 2: Running VM + Unavailable health + all metrics normal
        if (telemetry.power_state == PowerState.RUNNING and
            telemetry.resource_health_status == ResourceHealthStatus.UNAVAILABLE):
            # Check if metrics are normal (all present and in healthy range)
            metrics_normal = True
            if telemetry.cpu_percent is not None and telemetry.cpu_percent > 90:
                metrics_normal = False
            if telemetry.memory_percent is not None and telemetry.memory_percent > 90:
                metrics_normal = False
            if telemetry.os_disk_latency_ms is not None and telemetry.os_disk_latency_ms > 100:
                metrics_normal = False
            
            # If all metrics are normal but health is unavailable, it's a major conflict
            if metrics_normal and telemetry.cpu_percent is not None and telemetry.memory_percent is not None:
                return "major"
        
        # Check for minor conflicts
        
        # Minor conflict 1: Running VM but no heartbeat
        if (telemetry.power_state == PowerState.RUNNING and
            telemetry.heartbeat_present is not None and
            not telemetry.heartbeat_present):
            conflicts.append("running_no_heartbeat")
        
        # Minor conflict 2: NSG denies RDP but troubleshoot allows
        if (telemetry.nsg_allow_rdp_3389 is not None and
            not telemetry.nsg_allow_rdp_3389 and
            telemetry.connection_troubleshoot_rdp is not None and
            str(telemetry.connection_troubleshoot_rdp) == "Allow"):
            conflicts.append("nsg_rdp_mismatch")
        
        # Minor conflict 3: NSG denies SSH but troubleshoot allows
        if (telemetry.nsg_allow_ssh_22 is not None and
            not telemetry.nsg_allow_ssh_22 and
            telemetry.connection_troubleshoot_ssh is not None and
            str(telemetry.connection_troubleshoot_ssh) == "Allow"):
            conflicts.append("nsg_ssh_mismatch")
        
        # Minor conflict 4: NSG allows but troubleshoot denies
        if (telemetry.nsg_allow_rdp_3389 is not None and
            telemetry.nsg_allow_rdp_3389 and
            telemetry.connection_troubleshoot_rdp is not None and
            str(telemetry.connection_troubleshoot_rdp) == "Deny"):
            conflicts.append("nsg_rdp_reverse_mismatch")
        
        if (telemetry.nsg_allow_ssh_22 is not None and
            telemetry.nsg_allow_ssh_22 and
            telemetry.connection_troubleshoot_ssh is not None and
            str(telemetry.connection_troubleshoot_ssh) == "Deny"):
            conflicts.append("nsg_ssh_reverse_mismatch")
        
        # Return conflict level
        if len(conflicts) > 0:
            return "minor"
        
        return "none"
    
    def score_telemetry(
        self,
        telemetry: TelemetryInput,
        pattern_match: Optional[str] = None
    ) -> Tuple[float, float, str]:
        """
        Convenience method to calculate all scores at once.
        
        Args:
            telemetry: Validated telemetry input
            pattern_match: "exact", "partial", or None (default: None)
            
        Returns:
            Tuple of (completeness, confidence_score, signal_conflicts)
        """
        completeness = self.calculate_completeness(telemetry)
        signal_conflicts = self.detect_signal_conflicts(telemetry)
        confidence_score = self.calculate_confidence(
            telemetry,
            completeness,
            pattern_match,
            signal_conflicts
        )
        
        return completeness, confidence_score, signal_conflicts


if __name__ == "__main__":
    # Example usage
    from src.models import PowerState, ProvisioningState, ResourceHealthStatus
    
    scorer = ConfidenceScorer()
    
    # Example 1: High completeness, exact pattern match, no conflicts
    telemetry1 = TelemetryInput(
        power_state=PowerState.RUNNING,
        provisioning_state=ProvisioningState.SUCCEEDED,
        resource_health_status=ResourceHealthStatus.AVAILABLE,
        cpu_percent=45.0,
        memory_percent=60.0,
        heartbeat_present=True,
        os_disk_percent_full=50.0
    )
    
    completeness1, confidence1, conflicts1 = scorer.score_telemetry(telemetry1, pattern_match="exact")
    print(f"Example 1:")
    print(f"  Completeness: {completeness1}%")
    print(f"  Confidence: {confidence1}")
    print(f"  Conflicts: {conflicts1}")
    print()
    
    # Example 2: Low completeness, no pattern match, no conflicts
    telemetry2 = TelemetryInput(
        power_state=PowerState.RUNNING,
        provisioning_state=ProvisioningState.SUCCEEDED,
        resource_health_status=ResourceHealthStatus.AVAILABLE
    )
    
    completeness2, confidence2, conflicts2 = scorer.score_telemetry(telemetry2, pattern_match=None)
    print(f"Example 2:")
    print(f"  Completeness: {completeness2}%")
    print(f"  Confidence: {confidence2}")
    print(f"  Conflicts: {conflicts2}")
    print()
    
    # Example 3: High completeness, exact pattern, minor conflict
    telemetry3 = TelemetryInput(
        power_state=PowerState.RUNNING,
        provisioning_state=ProvisioningState.SUCCEEDED,
        resource_health_status=ResourceHealthStatus.AVAILABLE,
        heartbeat_present=False,  # Minor conflict: running but no heartbeat
        cpu_percent=45.0,
        memory_percent=60.0
    )
    
    completeness3, confidence3, conflicts3 = scorer.score_telemetry(telemetry3, pattern_match="exact")
    print(f"Example 3:")
    print(f"  Completeness: {completeness3}%")
    print(f"  Confidence: {confidence3}")
    print(f"  Conflicts: {conflicts3}")
