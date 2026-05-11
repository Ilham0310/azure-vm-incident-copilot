"""
Property-based tests for safety rules (Properties 11-16).

This module tests:
- Property 11: Boot Failure Safety
- Property 12: Low Confidence Destructive Action Safety
- Property 13: Network Security Safety
- Property 14: Platform Event Triggers Abstain
- Property 15: Failed State Safety
- Property 16: Missing Critical Signals Trigger Abstain
"""

import json
from hypothesis import given, settings
import hypothesis.strategies as st
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.decision_engine import DecisionEngine
from src.confidence_scorer import ConfidenceScorer
from src.models import TelemetryInput, DecisionState, PowerState, ProvisioningState, ResourceHealthStatus, BootDiagnosticsStatus
from tests.property.strategies import (
    valid_telemetry_strategy,
    platform_event_strategy,
    boot_failure_strategy
)


# ============================================================================
# Property 16: Missing Critical Signals Trigger Abstain
# ============================================================================

@given(critical_signal=st.sampled_from(["power_state", "provisioning_state", "resource_health_status"]))
@settings(max_examples=100)
def test_property_16_missing_critical_signals_trigger_abstain(critical_signal):
    """
    # Feature: azure-vm-incident-copilot, Property 16: Missing Critical Signals Trigger Abstain
    
    FOR ALL telemetry with critical signals missing or unknown:
        Decision engine SHALL return abstain_request_next_check
    
    Validates Requirement 3.5:
    - Requirement 3.5: WHEN critical signals are missing or unknown, Decision_Policy SHALL return abstain
    
    Test Strategy:
    1. Create minimal telemetry with one critical signal set to Unknown
    2. Parse into TelemetryInput model
    3. Calculate confidence and completeness
    4. Run decision engine
    5. Assert decision state is abstain_request_next_check
    """
    engine = DecisionEngine()
    scorer = ConfidenceScorer()
    
    # Create minimal telemetry with one critical signal set to Unknown
    telemetry_dict = {
        "power_state": "Unknown" if critical_signal == "power_state" else "Running",
        "provisioning_state": "Unknown" if critical_signal == "provisioning_state" else "Succeeded",
        "resource_health_status": "Unknown" if critical_signal == "resource_health_status" else "Available"
    }
    
    # Parse telemetry
    telemetry = TelemetryInput(**telemetry_dict)
    
    # Verify that the critical signal is actually Unknown
    if critical_signal == "power_state":
        assert telemetry.power_state == PowerState.UNKNOWN, f"Expected UNKNOWN, got {telemetry.power_state}"
    elif critical_signal == "provisioning_state":
        assert telemetry.provisioning_state == ProvisioningState.UNKNOWN, f"Expected UNKNOWN, got {telemetry.provisioning_state}"
    else:
        assert telemetry.resource_health_status == ResourceHealthStatus.UNKNOWN, f"Expected UNKNOWN, got {telemetry.resource_health_status}"
    
    # Calculate scores
    completeness, confidence_score, conflicts = scorer.score_telemetry(telemetry, pattern_match=None)
    
    # Run decision engine
    decision = engine.decide(telemetry, confidence_score, completeness)
    
    # Assert abstain decision
    assert decision.state == DecisionState.ABSTAIN_REQUEST_NEXT_CHECK, \
        f"Expected abstain for missing critical signals, got {decision.state.value}"
    
    # Assert next_check mentions critical signals
    assert decision.next_check is not None and "critical" in decision.next_check.lower(), \
        "next_check should mention critical signals"


# ============================================================================
# Property 14: Platform Event Triggers Abstain
# ============================================================================

@given(telemetry_dict=platform_event_strategy())
@settings(max_examples=100)
def test_property_14_platform_event_triggers_abstain(telemetry_dict):
    """
    # Feature: azure-vm-incident-copilot, Property 14: Platform Event Triggers Abstain
    
    FOR ALL telemetry with platform event annotation:
        Decision engine SHALL return abstain_request_next_check
        AND next_check SHALL NOT suggest VM restart
    
    Validates Requirements 3.7, 6.1, 6.2:
    - Requirement 3.7: WHEN resource_health_annotation indicates platform event, return abstain
    - Requirement 6.1: SHALL NOT suggest VM restart during platform events
    - Requirement 6.2: SHALL return abstain_request_next_check for platform events
    
    Test Strategy:
    1. Generate telemetry with platform event annotation
    2. Parse into TelemetryInput model
    3. Calculate confidence and completeness
    4. Run decision engine
    5. Assert decision state is abstain_request_next_check
    6. Assert next_check does NOT suggest restart
    """
    engine = DecisionEngine()
    scorer = ConfidenceScorer()
    
    # Parse telemetry
    telemetry = TelemetryInput(**telemetry_dict)
    
    # Verify platform event annotation is present
    assert telemetry.resource_health_annotation is not None, "Platform event annotation missing"
    
    # Calculate scores
    completeness, confidence_score, conflicts = scorer.score_telemetry(telemetry, pattern_match=None)
    
    # Run decision engine
    decision = engine.decide(telemetry, confidence_score, completeness)
    
    # Assert abstain decision
    assert decision.state == DecisionState.ABSTAIN_REQUEST_NEXT_CHECK, \
        f"Expected abstain for platform event, got {decision.state.value}"
    
    # Assert next_check does NOT suggest restart
    if decision.next_check:
        next_check_lower = decision.next_check.lower()
        assert "restart" not in next_check_lower or "do not restart" in next_check_lower, \
            f"next_check should not suggest restart during platform event: {decision.next_check}"


# ============================================================================
# Property 11: Boot Failure Safety
# ============================================================================

@given(telemetry_dict=boot_failure_strategy())
@settings(max_examples=100)
def test_property_11_boot_failure_safety(telemetry_dict):
    """
    # Feature: azure-vm-incident-copilot, Property 11: Boot Failure Safety
    
    FOR ALL telemetry with BSOD or KernelPanic:
        next_check SHALL NOT suggest VM restart
    
    Validates Requirements 6.3, 6.4:
    - Requirement 6.3: WHEN boot_diagnostics_status is BSOD, SHALL NOT suggest restart
    - Requirement 6.4: WHEN boot_diagnostics_status is KernelPanic, SHALL NOT suggest restart
    
    Test Strategy:
    1. Generate telemetry with BSOD or KernelPanic
    2. Parse into TelemetryInput model
    3. Calculate confidence and completeness
    4. Run decision engine
    5. Assert next_check does NOT suggest restart
    """
    engine = DecisionEngine()
    scorer = ConfidenceScorer()
    
    # Parse telemetry
    telemetry = TelemetryInput(**telemetry_dict)
    
    # Verify boot failure status
    assert telemetry.boot_diagnostics_status is not None, "Boot diagnostics status missing"
    assert telemetry.boot_diagnostics_status in [BootDiagnosticsStatus.BSOD, BootDiagnosticsStatus.KERNEL_PANIC], \
        f"Expected BSOD or KernelPanic, got {telemetry.boot_diagnostics_status}"
    
    # Calculate scores
    completeness, confidence_score, conflicts = scorer.score_telemetry(telemetry, pattern_match="exact")
    
    # Run decision engine
    decision = engine.decide(telemetry, confidence_score, completeness)
    
    # Assert next_check does NOT suggest restart
    if decision.next_check:
        next_check_lower = decision.next_check.lower()
        # Should not suggest restart, or should explicitly say "do not restart"
        if "restart" in next_check_lower:
            assert "do not restart" in next_check_lower or "not restart" in next_check_lower, \
                f"next_check should not suggest restart for boot failure: {decision.next_check}"


# ============================================================================
# Property 12: Low Confidence Destructive Action Safety
# ============================================================================

@given(telemetry_dict=valid_telemetry_strategy())
@settings(max_examples=100)
def test_property_12_low_confidence_destructive_action_safety(telemetry_dict):
    """
    # Feature: azure-vm-incident-copilot, Property 12: Low Confidence Destructive Action Safety
    
    FOR ALL telemetry with confidence < 0.9:
        next_check SHALL NOT suggest destructive actions
    
    Validates Requirements 6.5, 7.3, 7.4:
    - Requirement 6.5: WHEN confidence < 0.9 AND destructive actions, SHALL NOT include in next_check
    - Requirement 7.3: WHEN confidence < 0.9, SHALL NOT suggest disk deletion
    - Requirement 7.4: WHEN confidence < 0.9, SHALL NOT suggest OS reset
    
    Test Strategy:
    1. Generate valid telemetry
    2. Parse into TelemetryInput model
    3. Set confidence score to < 0.9
    4. Run decision engine
    5. Assert next_check does NOT suggest destructive actions
    """
    engine = DecisionEngine()
    scorer = ConfidenceScorer()
    
    # Parse telemetry
    telemetry = TelemetryInput(**telemetry_dict)
    
    # Calculate scores with low confidence
    completeness, _, conflicts = scorer.score_telemetry(telemetry, pattern_match=None)
    low_confidence = 0.5  # Force low confidence
    
    # Run decision engine
    decision = engine.decide(telemetry, low_confidence, completeness)
    
    # Assert next_check does NOT suggest destructive actions
    if decision.next_check:
        next_check_lower = decision.next_check.lower()
        destructive_keywords = ["delete disk", "reset os", "delete vm", "reset configuration"]
        for keyword in destructive_keywords:
            if keyword in next_check_lower:
                # If destructive keyword found, should be in a warning context
                assert "do not" in next_check_lower or "confidence too low" in next_check_lower, \
                    f"next_check should not suggest {keyword} with low confidence: {decision.next_check}"


# ============================================================================
# Property 13: Network Security Safety
# ============================================================================

@given(telemetry_dict=valid_telemetry_strategy())
@settings(max_examples=100)
def test_property_13_network_security_safety(telemetry_dict):
    """
    # Feature: azure-vm-incident-copilot, Property 13: Network Security Safety
    
    FOR ALL telemetry:
        next_check SHALL NEVER suggest disabling NSG or firewall rules
    
    Validates Requirements 7.1, 7.2:
    - Requirement 7.1: SHALL NOT suggest disabling NSG rules
    - Requirement 7.2: SHALL NOT suggest disabling firewall rules
    
    Test Strategy:
    1. Generate valid telemetry
    2. Parse into TelemetryInput model
    3. Calculate confidence and completeness
    4. Run decision engine
    5. Assert next_check does NOT suggest disabling NSG or firewall
    """
    engine = DecisionEngine()
    scorer = ConfidenceScorer()
    
    # Parse telemetry
    telemetry = TelemetryInput(**telemetry_dict)
    
    # Calculate scores
    completeness, confidence_score, conflicts = scorer.score_telemetry(telemetry, pattern_match="exact")
    
    # Run decision engine
    decision = engine.decide(telemetry, confidence_score, completeness)
    
    # Assert next_check does NOT suggest disabling NSG or firewall
    if decision.next_check:
        next_check_lower = decision.next_check.lower()
        unsafe_keywords = ["disable nsg", "disable firewall", "turn off nsg", "turn off firewall"]
        for keyword in unsafe_keywords:
            assert keyword not in next_check_lower, \
                f"next_check should not suggest '{keyword}': {decision.next_check}"


# ============================================================================
# Property 15: Failed State Safety
# ============================================================================

@given(telemetry_dict=valid_telemetry_strategy())
@settings(max_examples=100)
def test_property_15_failed_state_safety(telemetry_dict):
    """
    # Feature: azure-vm-incident-copilot, Property 15: Failed State Safety
    
    FOR ALL telemetry with power_state=Failed AND provisioning_state=Failed:
        next_check SHALL NOT suggest auto-remediation
    
    Validates Requirement 7.5:
    - Requirement 7.5: WHEN power_state=Failed AND provisioning_state=Failed, SHALL NOT suggest auto-remediation
    
    Test Strategy:
    1. Generate valid telemetry
    2. Set power_state=Failed and provisioning_state=Failed
    3. Parse into TelemetryInput model
    4. Calculate confidence and completeness
    5. Run decision engine
    6. Assert next_check does NOT suggest auto-remediation
    """
    engine = DecisionEngine()
    scorer = ConfidenceScorer()
    
    # Modify telemetry to have failed states
    telemetry_dict["power_state"] = "Failed"
    telemetry_dict["provisioning_state"] = "Failed"
    
    # Parse telemetry
    telemetry = TelemetryInput(**telemetry_dict)
    
    # Calculate scores
    completeness, confidence_score, conflicts = scorer.score_telemetry(telemetry, pattern_match=None)
    
    # Run decision engine
    decision = engine.decide(telemetry, confidence_score, completeness)
    
    # Assert next_check does NOT suggest auto-remediation
    if decision.next_check:
        next_check_lower = decision.next_check.lower()
        unsafe_keywords = ["auto-remediate", "auto remediate", "automatically fix", "automatic remediation"]
        for keyword in unsafe_keywords:
            if keyword in next_check_lower:
                # If auto-remediation mentioned, should be in a warning context
                assert "do not" in next_check_lower or "contact" in next_check_lower, \
                    f"next_check should not suggest auto-remediation for failed state: {decision.next_check}"


if __name__ == "__main__":
    # Run the tests manually for debugging
    import pytest
    pytest.main([__file__, "-v", "-s"])
