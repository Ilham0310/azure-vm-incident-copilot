"""
Property-based tests for decision logic (Properties 5-10).

This module tests:
- Property 5: Decision Determinism
- Property 6: Exactly One Decision
- Property 7: Low Completeness Triggers Abstain
- Property 8: Output Structure Completeness (in test_properties_integrity.py)
- Property 9: Abstain Populates Next Check (in test_properties_integrity.py)
- Property 10: Diagnose Requires High Confidence (in test_properties_integrity.py)
"""

import json
from hypothesis import given, settings
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.decision_engine import DecisionEngine
from src.confidence_scorer import ConfidenceScorer
from src.models import TelemetryInput, DecisionState
from tests.property.strategies import (
    valid_telemetry_strategy,
    low_completeness_strategy
)


# ============================================================================
# Property 5: Decision Determinism
# ============================================================================

@given(telemetry_dict=valid_telemetry_strategy())
@settings(max_examples=100)
def test_property_5_decision_determinism(telemetry_dict):
    """
    # Feature: azure-vm-incident-copilot, Property 5: Decision Determinism
    
    FOR ALL valid telemetry:
        Identical inputs SHALL produce identical outputs
    
    Validates Requirement 3.8:
    - Requirement 3.8: Decision_Policy SHALL be deterministic for identical Telemetry_Input
    
    Test Strategy:
    1. Generate valid telemetry
    2. Parse into TelemetryInput model
    3. Calculate confidence and completeness
    4. Run decision engine twice with same inputs
    5. Assert both decisions are identical (state, diagnosis, evidence, next_check)
    """
    engine = DecisionEngine()
    scorer = ConfidenceScorer()
    
    # Parse telemetry
    telemetry = TelemetryInput(**telemetry_dict)
    
    # Calculate scores
    completeness, confidence_score, conflicts = scorer.score_telemetry(telemetry, pattern_match="exact")
    
    # Run decision engine twice
    decision1 = engine.decide(telemetry, confidence_score, completeness)
    decision2 = engine.decide(telemetry, confidence_score, completeness)
    
    # Assert determinism
    assert decision1.state == decision2.state, "Decision state differs between runs"
    assert decision1.diagnosis == decision2.diagnosis, "Diagnosis differs between runs"
    assert decision1.evidence == decision2.evidence, "Evidence differs between runs"
    assert decision1.evidence_gap == decision2.evidence_gap, "Evidence gap differs between runs"
    assert decision1.next_check == decision2.next_check, "Next check differs between runs"
    assert decision1.confidence_score == decision2.confidence_score, "Confidence score differs between runs"


# ============================================================================
# Property 6: Exactly One Decision
# ============================================================================

@given(telemetry_dict=valid_telemetry_strategy())
@settings(max_examples=100)
def test_property_6_exactly_one_decision(telemetry_dict):
    """
    # Feature: azure-vm-incident-copilot, Property 6: Exactly One Decision
    
    FOR ALL valid telemetry:
        Decision engine SHALL return exactly one decision state
    
    Validates Requirement 3.1:
    - Requirement 3.1: Decision_Policy SHALL return exactly one decision
    
    Test Strategy:
    1. Generate valid telemetry
    2. Parse into TelemetryInput model
    3. Calculate confidence and completeness
    4. Run decision engine
    5. Assert decision state is one of the three valid states
    6. Assert decision object is complete (no None values for required fields)
    """
    engine = DecisionEngine()
    scorer = ConfidenceScorer()
    
    # Parse telemetry
    telemetry = TelemetryInput(**telemetry_dict)
    
    # Calculate scores
    completeness, confidence_score, conflicts = scorer.score_telemetry(telemetry, pattern_match="exact")
    
    # Run decision engine
    decision = engine.decide(telemetry, confidence_score, completeness)
    
    # Assert exactly one decision state
    valid_states = [
        DecisionState.DIAGNOSE,
        DecisionState.DIAGNOSE_LOW_CONFIDENCE,
        DecisionState.ABSTAIN_REQUEST_NEXT_CHECK
    ]
    assert decision.state in valid_states, f"Invalid decision state: {decision.state}"
    
    # Assert decision object is complete
    assert decision.diagnosis is not None and decision.diagnosis != "", "Diagnosis is empty"
    assert decision.evidence is not None, "Evidence is None"
    assert decision.evidence_gap is not None, "Evidence gap is None"
    assert decision.confidence_score is not None, "Confidence score is None"
    # next_check can be None for diagnose decisions


# ============================================================================
# Property 7: Low Completeness Triggers Abstain
# ============================================================================

@given(telemetry_dict=low_completeness_strategy())
@settings(max_examples=100)
def test_property_7_low_completeness_triggers_abstain(telemetry_dict):
    """
    # Feature: azure-vm-incident-copilot, Property 7: Low Completeness Triggers Abstain
    
    FOR ALL telemetry with completeness < 60%:
        Decision engine SHALL return abstain_request_next_check
    
    Validates Requirement 3.4:
    - Requirement 3.4: WHEN Data_Completeness < 60%, Decision_Policy SHALL return abstain_request_next_check
    
    Test Strategy:
    1. Generate telemetry with low completeness (<60%)
    2. Parse into TelemetryInput model
    3. Calculate confidence and completeness
    4. Verify completeness is < 60%
    5. Run decision engine
    6. Assert decision state is abstain_request_next_check
    7. Assert next_check is populated
    """
    engine = DecisionEngine()
    scorer = ConfidenceScorer()
    
    # Parse telemetry
    telemetry = TelemetryInput(**telemetry_dict)
    
    # Calculate scores
    completeness, confidence_score, conflicts = scorer.score_telemetry(telemetry, pattern_match=None)
    
    # Verify completeness is low
    assert completeness < 60.0, f"Completeness should be < 60%, got {completeness}%"
    
    # Run decision engine
    decision = engine.decide(telemetry, confidence_score, completeness)
    
    # Assert abstain decision
    assert decision.state == DecisionState.ABSTAIN_REQUEST_NEXT_CHECK, \
        f"Expected abstain for low completeness, got {decision.state.value}"
    
    # Assert next_check is populated
    assert decision.next_check is not None and decision.next_check != "", \
        "next_check should be populated for abstain decision"


if __name__ == "__main__":
    # Run the tests manually for debugging
    import pytest
    pytest.main([__file__, "-v", "-s"])
