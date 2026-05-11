"""
Core data models for Azure VM Incident Copilot.

This module defines all Pydantic models and enums used throughout the system:
- 8 enum classes for telemetry field values
- TelemetryInput model with 30+ fields and validation constraints
- DiagnosticOutput model with 7 required fields and next_check validator
- ValidationResult, ValidationError, Decision models
- BenchmarkCase, CaseResult, PatternSummary, BenchmarkResults models
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator


# ============================================================================
# Enumerations (8 enum types)
# ============================================================================

class PowerState(str, Enum):
    """VM power state (5 values)"""
    RUNNING = "Running"
    STOPPED = "Stopped"
    DEALLOCATED = "Deallocated"
    FAILED = "Failed"
    UNKNOWN = "Unknown"


class ProvisioningState(str, Enum):
    """VM provisioning state (4 values)"""
    SUCCEEDED = "Succeeded"
    FAILED = "Failed"
    IN_PROGRESS = "In Progress"
    UNKNOWN = "Unknown"


class ResourceHealthStatus(str, Enum):
    """Azure resource health status (4 values)"""
    AVAILABLE = "Available"
    DEGRADED = "Degraded"
    UNAVAILABLE = "Unavailable"
    UNKNOWN = "Unknown"


class BootDiagnosticsStatus(str, Enum):
    """Boot diagnostics status (5 values)"""
    NORMAL = "Normal"
    BSOD = "BSOD"
    KERNEL_PANIC = "KernelPanic"
    STUCK = "Stuck"
    UNKNOWN = "Unknown"


class AzureVMAgentStatus(str, Enum):
    """Azure VM agent status (5 values)"""
    HEALTHY = "Healthy"
    DEGRADED = "Degraded"
    NOT_REPORTING = "NotReporting"
    FAILED = "Failed"
    UNKNOWN = "Unknown"


class AppHealthStatus(str, Enum):
    """Application health status (4 values)"""
    HEALTHY = "Healthy"
    DEGRADED = "Degraded"
    UNHEALTHY = "Unhealthy"
    UNKNOWN = "Unknown"


class ConnectionTroubleshootResult(str, Enum):
    """Connection troubleshoot result (5 values)"""
    ALLOW = "Allow"
    DENY = "Deny"
    INCONCLUSIVE = "Inconclusive"
    TIMEOUT = "Timeout"
    UNKNOWN = "Unknown"


class MonitorAgentStatus(str, Enum):
    """Monitoring agent status (5 values)"""
    HEALTHY = "Healthy"
    DEGRADED = "Degraded"
    FAILED = "Failed"
    NOT_INSTALLED = "NotInstalled"
    UNKNOWN = "Unknown"


class DecisionState(str, Enum):
    """Decision state (3 values)"""
    DIAGNOSE = "diagnose"
    DIAGNOSE_LOW_CONFIDENCE = "diagnose_low_confidence"
    ABSTAIN_REQUEST_NEXT_CHECK = "abstain_request_next_check"


# ============================================================================
# Telemetry Input Model (30+ fields)
# ============================================================================

class TelemetryInput(BaseModel):
    """
    Azure VM telemetry input with 30+ signal fields.
    
    Required fields: power_state, provisioning_state, resource_health_status
    Optional fields: All other 27+ fields
    """
    
    # Required fields (3)
    power_state: PowerState = Field(..., description="VM power state")
    provisioning_state: ProvisioningState = Field(..., description="VM provisioning state")
    resource_health_status: ResourceHealthStatus = Field(..., description="Azure resource health status")
    
    # Resource health annotation
    resource_health_annotation: Optional[str] = Field(None, description="Resource health annotation text")
    
    # Heartbeat signals
    heartbeat_present: Optional[bool] = Field(None, description="Whether VM heartbeat is present")
    heartbeat_last_received: Optional[datetime] = Field(None, description="Timestamp of last heartbeat")
    
    # Boot diagnostics
    boot_diagnostics_status: Optional[BootDiagnosticsStatus] = Field(None, description="Boot diagnostics status")
    boot_diagnostics_error: Optional[str] = Field(None, description="Boot diagnostics error message")
    
    # Azure VM agent
    azure_vm_agent_status: Optional[AzureVMAgentStatus] = Field(None, description="Azure VM agent status")
    
    # CPU metrics
    cpu_percent: Optional[float] = Field(None, ge=0, le=100, description="CPU utilization percentage")
    
    # Memory metrics
    memory_available_mb: Optional[float] = Field(None, ge=0, description="Available memory in megabytes")
    memory_percent: Optional[float] = Field(None, ge=0, le=100, description="Memory utilization percentage")
    
    # Disk metrics
    os_disk_latency_ms: Optional[float] = Field(None, ge=0, description="OS disk latency in milliseconds")
    data_disk_latency_ms: Optional[float] = Field(None, ge=0, description="Data disk latency in milliseconds")
    os_disk_percent_full: Optional[float] = Field(None, ge=0, le=100, description="OS disk usage percentage")
    
    # Application health
    app_health_status: Optional[AppHealthStatus] = Field(None, description="Application health status")
    app_error_message: Optional[str] = Field(None, description="Application error message")
    
    # Network Security Group (NSG) rules
    nsg_allow_rdp_3389: Optional[bool] = Field(None, description="Whether NSG allows RDP on port 3389")
    nsg_allow_ssh_22: Optional[bool] = Field(None, description="Whether NSG allows SSH on port 22")
    
    # Connection troubleshoot results
    connection_troubleshoot_rdp: Optional[ConnectionTroubleshootResult] = Field(None, description="Connection troubleshoot result for RDP")
    connection_troubleshoot_ssh: Optional[ConnectionTroubleshootResult] = Field(None, description="Connection troubleshoot result for SSH")
    connection_troubleshoot_verdict: Optional[str] = Field(None, description="Connection troubleshoot verdict text")
    
    # Monitor agent
    monitor_agent_status: Optional[MonitorAgentStatus] = Field(None, description="Monitoring agent status")
    
    # SSL certificate monitoring
    ssl_cert_days_remaining: Optional[int] = Field(None, ge=0, description="Days remaining until SSL certificate expiry")
    
    # Backup monitoring
    last_backup_status: Optional[str] = Field(None, description="Last backup job status: Completed, Failed, Warning, InProgress, Unknown")
    last_backup_time: Optional[datetime] = Field(None, description="Timestamp of last backup job")
    
    # Data completeness metadata
    data_completeness_percent: Optional[float] = Field(None, ge=0, le=100, description="Percentage of telemetry fields populated")
    missing_signals: Optional[List[str]] = Field(None, description="List of missing telemetry signal names")
    
    class Config:
        # Allow extra fields for forward compatibility
        extra = "allow"
        # Use enum values for serialization
        use_enum_values = False


# ============================================================================
# Diagnostic Output Model (7 required fields)
# ============================================================================

class DiagnosticOutput(BaseModel):
    """
    Diagnostic output with 7 required fields + LLM metadata (v2.0).
    
    Includes validator to ensure next_check is populated when decision is abstain.
    """
    
    # Core outputs (7 original fields)
    decision: DecisionState = Field(..., description="Decision state indicating diagnostic confidence level")
    diagnosis: str = Field(..., description="Human-readable description of the identified issue or healthy state")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0")
    evidence: List[str] = Field(..., description="List of telemetry signals that support the diagnosis")
    evidence_gap: List[str] = Field(..., description="List of missing or incomplete telemetry signals")
    next_check: Optional[str] = Field(..., description="Specific diagnostic action to gather more information")
    explanation: str = Field(..., description="Multi-sentence reasoning describing why this decision was made")
    
    # LLM metadata (new in v2.0)
    incident_id: Optional[str] = Field(None, description="Incident ID for feedback tracking")
    pattern_matched: Optional[str] = Field(None, description="Pattern name matched by LLM")
    is_novel_incident: bool = Field(False, description="Whether this is a novel incident pattern")
    novel_incident_description: str = Field("", description="Description of novel pattern if detected")
    llm_provider: str = Field("unknown", description="LLM provider used (groq, gemini, ollama, rule_engine)")
    similar_incidents_used: int = Field(0, description="Number of similar past incidents retrieved")
    sops_consulted: List[str] = Field(default_factory=list, description="List of SOP titles consulted")
    safety_rules_applied: List[str] = Field(default_factory=list, description="List of safety rules applied")
    
    @model_validator(mode='after')
    def validate_next_check(self):
        """
        Validates that next_check is populated (non-null, non-empty) when decision is abstain_request_next_check.
        
        This enforces Property 9: Abstain Populates Next Check
        """
        if self.decision == DecisionState.ABSTAIN_REQUEST_NEXT_CHECK:
            if not self.next_check or self.next_check.strip() == "":
                raise ValueError("next_check must be populated when decision is abstain_request_next_check")
        return self
    
    class Config:
        # Allow arbitrary types for flexibility
        arbitrary_types_allowed = True


# ============================================================================
# Validation Models
# ============================================================================

class ValidationError(BaseModel):
    """Validation error with field name and constraint violation details"""
    field: str = Field(..., description="Field name that failed validation")
    message: str = Field(..., description="Error message describing the constraint violation")
    value: Optional[str] = Field(None, description="Actual value that failed validation")


class ValidationResult(BaseModel):
    """Result of schema validation"""
    valid: bool = Field(..., description="Whether validation passed")
    telemetry: Optional[TelemetryInput] = Field(None, description="Parsed telemetry input if validation passed")
    errors: List[ValidationError] = Field(default_factory=list, description="List of validation errors if validation failed")


# ============================================================================
# Decision Models
# ============================================================================

class Decision(BaseModel):
    """
    Internal decision object used by decision engine (v2.0 with LLM metadata).
    
    Contains decision state, diagnosis, evidence, gaps, next_check, and LLM metadata.
    """
    state: DecisionState = Field(..., description="Decision state")
    diagnosis: str = Field(..., description="Diagnosis text")
    evidence: List[str] = Field(default_factory=list, description="Supporting evidence signals")
    evidence_gap: List[str] = Field(default_factory=list, description="Missing signals")
    next_check: Optional[str] = Field(None, description="Next diagnostic action")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    
    # LLM metadata (new in v2.0)
    pattern_matched: Optional[str] = Field(None, description="Pattern name matched")
    is_novel_incident: bool = Field(False, description="Whether this is a novel incident")
    novel_incident_description: str = Field("", description="Description of novel pattern")
    llm_provider: str = Field("unknown", description="LLM provider used")
    similar_incidents_used: int = Field(0, description="Number of similar incidents retrieved")
    sops_consulted: List[str] = Field(default_factory=list, description="SOPs consulted")
    safety_rules_applied: List[str] = Field(default_factory=list, description="Safety rules applied")
    
    @property
    def decision(self) -> DecisionState:
        """
        Alias for state — allows tests to use either .state or .decision.
        
        This provides backward compatibility for code that expects .decision attribute.
        """
        return self.state


# ============================================================================
# Benchmark Models
# ============================================================================

class BenchmarkCase(BaseModel):
    """Single benchmark test case"""
    case_id: str = Field(..., description="Unique case identifier")
    case_name: str = Field(..., description="Descriptive case name")
    incident_pattern: str = Field(..., description="Incident pattern identifier")
    telemetry_input: TelemetryInput = Field(..., description="Input telemetry for this case")
    expected_decision: DecisionState = Field(..., description="Expected decision state")
    expected_diagnosis: Optional[str] = Field(None, description="Expected diagnosis text")
    notes: Optional[str] = Field(None, description="Additional context or notes")


class CaseResult(BaseModel):
    """Result of processing a single benchmark case"""
    case_id: str = Field(..., description="Case identifier")
    case_name: str = Field(..., description="Case name")
    incident_pattern: str = Field(..., description="Incident pattern")
    expected_decision: DecisionState = Field(..., description="Expected decision")
    actual_decision: DecisionState = Field(..., description="Actual decision returned by system")
    passed: bool = Field(..., description="Whether actual matches expected")
    confidence_score: float = Field(..., description="Confidence score from system")
    execution_time_ms: float = Field(..., description="Execution time in milliseconds")
    notes: Optional[str] = Field(None, description="Additional notes")


class PatternSummary(BaseModel):
    """Summary statistics for a specific incident pattern"""
    pattern: str = Field(..., description="Incident pattern identifier")
    total_cases: int = Field(..., description="Total cases for this pattern")
    passed: int = Field(..., description="Number of cases that passed")
    failed: int = Field(..., description="Number of cases that failed")
    pass_rate: float = Field(..., ge=0.0, le=100.0, description="Pass rate percentage")


class BenchmarkResults(BaseModel):
    """Complete benchmark test results"""
    total_cases: int = Field(..., description="Total number of cases processed")
    passed: int = Field(..., description="Number of cases that passed")
    failed: int = Field(..., description="Number of cases that failed")
    pass_rate: float = Field(..., ge=0.0, le=100.0, description="Overall pass rate percentage")
    case_results: List[CaseResult] = Field(..., description="Per-case results")
    summary_by_pattern: List[PatternSummary] = Field(..., description="Summary statistics grouped by pattern")
    total_execution_time_ms: float = Field(..., description="Total execution time in milliseconds")
