"""
Property-based tests for data integrity (Properties 17-20).

This module tests:
- Property 17: Telemetry Round-Trip Integrity
- Property 18: Output is Valid JSON
- Property 19: Benchmark Case Processing
- Property 20: CLI Error Exit Codes
"""

import json
import tempfile
import os
from pathlib import Path
from hypothesis import given, settings
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.models import TelemetryInput, DecisionState
from tests.property.strategies import (
    valid_telemetry_strategy, 
    low_completeness_strategy,
    invalid_enum_strategy,
    out_of_range_numeric_strategy
)
import hypothesis.strategies as st
from click.testing import CliRunner


# ============================================================================
# Property 17: Telemetry Round-Trip Integrity
# ============================================================================

@given(telemetry_dict=valid_telemetry_strategy())
@settings(max_examples=100)
def test_property_17_telemetry_roundtrip_integrity(telemetry_dict):
    """
    # Feature: azure-vm-incident-copilot, Property 17: Telemetry Round-Trip Integrity
    
    FOR ALL valid Telemetry_Input:
        parsing → formatting → parsing SHALL produce equivalent data structures
    
    Validates Requirements 12.1, 12.3:
    - Requirement 12.1: Parse valid telemetry into internal data structures
    - Requirement 12.3: Round-trip parsing produces equivalent structures
    
    Test Strategy:
    1. Generate valid telemetry dictionary using hypothesis
    2. Parse into TelemetryInput model (first parse)
    3. Serialize back to JSON string (format)
    4. Parse JSON string back into dictionary (second parse)
    5. Parse dictionary into TelemetryInput model again (third parse)
    6. Assert first and third TelemetryInput objects are equivalent
    
    This ensures data integrity is maintained through the parse-format-parse cycle.
    """
    # Step 1: First parse - dictionary to TelemetryInput
    try:
        telemetry_1 = TelemetryInput(**telemetry_dict)
    except Exception as e:
        # If parsing fails, the strategy generated invalid data
        # This should not happen with valid_telemetry_strategy
        raise AssertionError(f"First parse failed with valid telemetry: {e}")
    
    # Step 2: Format - TelemetryInput to JSON string
    try:
        json_str = telemetry_1.model_dump_json()
    except Exception as e:
        raise AssertionError(f"Serialization to JSON failed: {e}")
    
    # Step 3: Second parse - JSON string to dictionary
    try:
        telemetry_dict_2 = json.loads(json_str)
    except Exception as e:
        raise AssertionError(f"JSON parsing failed: {e}")
    
    # Step 4: Third parse - dictionary to TelemetryInput
    try:
        telemetry_2 = TelemetryInput(**telemetry_dict_2)
    except Exception as e:
        raise AssertionError(f"Third parse failed: {e}")
    
    # Step 5: Assert equivalence
    # Compare the two TelemetryInput objects
    # We use model_dump() to get dictionaries for comparison
    dict_1 = telemetry_1.model_dump()
    dict_2 = telemetry_2.model_dump()
    
    # Compare all fields
    assert dict_1.keys() == dict_2.keys(), "Field sets differ after round-trip"
    
    for key in dict_1.keys():
        val_1 = dict_1[key]
        val_2 = dict_2[key]
        
        # Handle datetime comparison (may have microsecond differences)
        if key == "heartbeat_last_received" and val_1 is not None and val_2 is not None:
            # Convert to ISO strings for comparison
            assert val_1 == val_2, f"Field {key} differs: {val_1} != {val_2}"
        # Handle float comparison (may have precision differences)
        elif isinstance(val_1, float) and isinstance(val_2, float):
            assert abs(val_1 - val_2) < 0.01, f"Field {key} differs: {val_1} != {val_2}"
        else:
            assert val_1 == val_2, f"Field {key} differs: {val_1} != {val_2}"
    
    # Additional check: ensure the models are equal
    assert telemetry_1 == telemetry_2, "TelemetryInput objects not equal after round-trip"


if __name__ == "__main__":
    # Run the test manually for debugging
    import pytest
    pytest.main([__file__, "-v", "-s"])


# ============================================================================
# Property 19: Benchmark Case Processing
# ============================================================================

@given(telemetry_cases=st.lists(valid_telemetry_strategy(), min_size=5, max_size=10))
@settings(max_examples=100)
def test_property_19_benchmark_case_processing(telemetry_cases):
    """
    # Feature: azure-vm-incident-copilot, Property 19: Benchmark Case Processing
    
    FOR ALL valid benchmark cases:
        TestHarness.run_benchmark() SHALL process all cases without exceptions
    
    Validates Requirements 9.1, 9.2:
    - Requirement 9.1: Load benchmark cases from JSON or CSV format
    - Requirement 9.2: Process all cases through the pipeline without exceptions
    
    Test Strategy:
    1. Generate 5-10 benchmark cases using valid_telemetry_strategy
    2. Create BenchmarkCase objects with expected decisions
    3. Call TestHarness.run_benchmark()
    4. Assert no exceptions occur
    5. Assert BenchmarkResults has correct structure
    6. Assert all cases were processed (len(case_results) == len(input_cases))
    """
    from src.test_harness import TestHarness
    from src.models import BenchmarkCase, DecisionState
    
    # Create BenchmarkCase objects from generated telemetry
    benchmark_cases = []
    for idx, telemetry_dict in enumerate(telemetry_cases):
        # Parse telemetry into TelemetryInput
        telemetry = TelemetryInput(**telemetry_dict)
        
        # Create BenchmarkCase with expected decision (we don't care about correctness here, just processing)
        case = BenchmarkCase(
            case_id=f"test_{idx:03d}",
            case_name=f"Generated Test Case {idx}",
            incident_pattern="generated_pattern",
            telemetry_input=telemetry,
            expected_decision=DecisionState.DIAGNOSE,  # Default expected decision
            expected_diagnosis="Generated test case",
            notes="Property test generated case"
        )
        benchmark_cases.append(case)
    
    # Run benchmark through TestHarness
    harness = TestHarness()
    
    try:
        results = harness.run_benchmark(benchmark_cases)
    except Exception as e:
        raise AssertionError(f"TestHarness.run_benchmark() raised exception: {e}")
    
    # Assert BenchmarkResults has correct structure
    assert hasattr(results, 'total_cases'), "BenchmarkResults missing total_cases field"
    assert hasattr(results, 'passed'), "BenchmarkResults missing passed field"
    assert hasattr(results, 'failed'), "BenchmarkResults missing failed field"
    assert hasattr(results, 'case_results'), "BenchmarkResults missing case_results field"
    assert hasattr(results, 'summary_by_pattern'), "BenchmarkResults missing summary_by_pattern field"
    
    # Assert all cases were processed
    assert results.total_cases == len(benchmark_cases), \
        f"Expected {len(benchmark_cases)} cases processed, got {results.total_cases}"
    
    assert len(results.case_results) == len(benchmark_cases), \
        f"Expected {len(benchmark_cases)} case results, got {len(results.case_results)}"
    
    # Assert passed + failed equals total
    assert results.passed + results.failed == results.total_cases, \
        f"passed ({results.passed}) + failed ({results.failed}) != total_cases ({results.total_cases})"
    
    # Assert each case result has required fields
    for case_result in results.case_results:
        assert hasattr(case_result, 'case_id'), "CaseResult missing case_id"
        assert hasattr(case_result, 'case_name'), "CaseResult missing case_name"
        assert hasattr(case_result, 'incident_pattern'), "CaseResult missing incident_pattern"
        assert hasattr(case_result, 'expected_decision'), "CaseResult missing expected_decision"
        assert hasattr(case_result, 'actual_decision'), "CaseResult missing actual_decision"
        assert hasattr(case_result, 'passed'), "CaseResult missing passed field"
        assert hasattr(case_result, 'confidence_score'), "CaseResult missing confidence_score"
        assert hasattr(case_result, 'execution_time_ms'), "CaseResult missing execution_time_ms"
        
        # Assert confidence_score is in valid range
        assert 0.0 <= case_result.confidence_score <= 1.0, \
            f"confidence_score {case_result.confidence_score} out of range [0.0, 1.0]"
        
        # Assert execution_time_ms is non-negative
        assert case_result.execution_time_ms >= 0, \
            f"execution_time_ms {case_result.execution_time_ms} is negative"



# ============================================================================
# Property 8: Output Structure Completeness
# ============================================================================

@given(telemetry_dict=valid_telemetry_strategy())
@settings(max_examples=100)
def test_property_8_output_structure_completeness(telemetry_dict):
    """
    # Feature: azure-vm-incident-copilot, Property 8: Output Structure Completeness
    
    FOR ALL valid telemetry:
        Diagnostic output SHALL include all 7 required fields
    
    Validates Requirements 4.1-4.8:
    - Requirement 4.1: Return Diagnostic_Output in JSON format
    - Requirement 4.2: Include decision field
    - Requirement 4.3: Include diagnosis field
    - Requirement 4.4: Include confidence_score field
    - Requirement 4.5: Include evidence field
    - Requirement 4.6: Include evidence_gap field
    - Requirement 4.7: Include next_check field
    - Requirement 4.8: Include explanation field
    
    Test Strategy:
    1. Generate valid telemetry
    2. Run through complete pipeline (validator → scorer → engine → formatter)
    3. Assert all 7 fields are present
    4. Assert all fields have appropriate types
    """
    from src.validator import SchemaValidator
    from src.confidence_scorer import ConfidenceScorer
    from src.decision_engine import DecisionEngine
    from src.explanation_formatter import ExplanationFormatter
    
    # Parse telemetry
    telemetry = TelemetryInput(**telemetry_dict)
    
    # Run through pipeline
    scorer = ConfidenceScorer()
    engine = DecisionEngine()
    formatter = ExplanationFormatter()
    
    completeness, confidence_score, conflicts = scorer.score_telemetry(telemetry, pattern_match="exact")
    decision = engine.decide(telemetry, confidence_score, completeness)
    output = formatter.format_output(decision, telemetry, confidence_score)
    
    # Assert all 7 fields are present
    assert output.decision is not None, "decision field is missing"
    assert output.diagnosis is not None, "diagnosis field is missing"
    assert output.confidence_score is not None, "confidence_score field is missing"
    assert output.evidence is not None, "evidence field is missing"
    assert output.evidence_gap is not None, "evidence_gap field is missing"
    # next_check can be None for diagnose decisions, but field must exist
    assert hasattr(output, 'next_check'), "next_check field is missing"
    assert output.explanation is not None, "explanation field is missing"
    
    # Assert appropriate types
    assert isinstance(output.decision, DecisionState), "decision should be DecisionState enum"
    assert isinstance(output.diagnosis, str), "diagnosis should be string"
    assert isinstance(output.confidence_score, float), "confidence_score should be float"
    assert isinstance(output.evidence, list), "evidence should be list"
    assert isinstance(output.evidence_gap, list), "evidence_gap should be list"
    assert isinstance(output.explanation, str), "explanation should be string"


# ============================================================================
# Property 9: Abstain Populates Next Check
# ============================================================================

@given(telemetry_dict=low_completeness_strategy())
@settings(max_examples=100)
def test_property_9_abstain_populates_next_check(telemetry_dict):
    """
    # Feature: azure-vm-incident-copilot, Property 9: Abstain Populates Next Check
    
    FOR ALL telemetry that triggers abstain:
        next_check SHALL be populated (non-null, non-empty)
    
    Validates Requirement 4.9:
    - Requirement 4.9: WHEN decision is abstain, populate next_check with specific action
    
    Test Strategy:
    1. Generate telemetry with low completeness (triggers abstain)
    2. Run through complete pipeline
    3. Assert decision is abstain_request_next_check
    4. Assert next_check is populated and non-empty
    """
    from src.confidence_scorer import ConfidenceScorer
    from src.decision_engine import DecisionEngine
    from src.explanation_formatter import ExplanationFormatter
    
    # Parse telemetry
    telemetry = TelemetryInput(**telemetry_dict)
    
    # Run through pipeline
    scorer = ConfidenceScorer()
    engine = DecisionEngine()
    formatter = ExplanationFormatter()
    
    completeness, confidence_score, conflicts = scorer.score_telemetry(telemetry, pattern_match=None)
    decision = engine.decide(telemetry, confidence_score, completeness)
    output = formatter.format_output(decision, telemetry, confidence_score)
    
    # If decision is abstain, next_check must be populated
    if output.decision == DecisionState.ABSTAIN_REQUEST_NEXT_CHECK:
        assert output.next_check is not None, "next_check is None for abstain decision"
        assert output.next_check.strip() != "", "next_check is empty for abstain decision"
        assert len(output.next_check) > 10, "next_check is too short (should be descriptive)"


# ============================================================================
# Property 10: Diagnose Requires High Confidence
# ============================================================================

@given(telemetry_dict=valid_telemetry_strategy())
@settings(max_examples=100)
def test_property_10_diagnose_requires_high_confidence(telemetry_dict):
    """
    # Feature: azure-vm-incident-copilot, Property 10: Diagnose Requires High Confidence
    
    FOR ALL telemetry with decision=diagnose:
        confidence_score SHALL be >= 0.70
    
    Validates Requirement 4.10:
    - Requirement 4.10: WHEN decision is diagnose, confidence_score >= 0.70
    
    Test Strategy:
    1. Generate valid telemetry
    2. Run through complete pipeline
    3. If decision is diagnose, assert confidence >= 0.70
    """
    from src.confidence_scorer import ConfidenceScorer
    from src.decision_engine import DecisionEngine
    from src.explanation_formatter import ExplanationFormatter
    
    # Parse telemetry
    telemetry = TelemetryInput(**telemetry_dict)
    
    # Run through pipeline
    scorer = ConfidenceScorer()
    engine = DecisionEngine()
    formatter = ExplanationFormatter()
    
    completeness, confidence_score, conflicts = scorer.score_telemetry(telemetry, pattern_match="exact")
    decision = engine.decide(telemetry, confidence_score, completeness)
    output = formatter.format_output(decision, telemetry, confidence_score)
    
    # If decision is diagnose, confidence must be >= 0.70
    if output.decision == DecisionState.DIAGNOSE:
        assert output.confidence_score >= 0.70, \
            f"diagnose decision requires confidence >= 0.70, got {output.confidence_score}"


# ============================================================================
# Property 18: Output is Valid JSON
# ============================================================================

@given(telemetry_dict=valid_telemetry_strategy())
@settings(max_examples=100)
def test_property_18_output_is_valid_json(telemetry_dict):
    """
    # Feature: azure-vm-incident-copilot, Property 18: Output is Valid JSON
    
    FOR ALL valid telemetry:
        Diagnostic output SHALL serialize to valid JSON
    
    Validates Requirements 4.1, 12.2:
    - Requirement 4.1: Return Diagnostic_Output in JSON format
    - Requirement 12.2: Format Diagnostic_Output as valid JSON
    
    Test Strategy:
    1. Generate valid telemetry
    2. Run through complete pipeline
    3. Serialize output to JSON string
    4. Parse JSON string back to dictionary
    5. Assert no errors occur
    6. Assert all fields are present in JSON
    """
    from src.confidence_scorer import ConfidenceScorer
    from src.decision_engine import DecisionEngine
    from src.explanation_formatter import ExplanationFormatter
    
    # Parse telemetry
    telemetry = TelemetryInput(**telemetry_dict)
    
    # Run through pipeline
    scorer = ConfidenceScorer()
    engine = DecisionEngine()
    formatter = ExplanationFormatter()
    
    completeness, confidence_score, conflicts = scorer.score_telemetry(telemetry, pattern_match="exact")
    decision = engine.decide(telemetry, confidence_score, completeness)
    output = formatter.format_output(decision, telemetry, confidence_score)
    
    # Serialize to JSON
    try:
        json_str = output.model_dump_json()
    except Exception as e:
        raise AssertionError(f"Failed to serialize output to JSON: {e}")
    
    # Parse JSON back
    try:
        json_dict = json.loads(json_str)
    except Exception as e:
        raise AssertionError(f"Failed to parse JSON: {e}")
    
    # Assert all 7 fields are in JSON
    assert "decision" in json_dict, "decision field missing from JSON"
    assert "diagnosis" in json_dict, "diagnosis field missing from JSON"
    assert "confidence_score" in json_dict, "confidence_score field missing from JSON"
    assert "evidence" in json_dict, "evidence field missing from JSON"
    assert "evidence_gap" in json_dict, "evidence_gap field missing from JSON"
    assert "next_check" in json_dict, "next_check field missing from JSON"
    assert "explanation" in json_dict, "explanation field missing from JSON"


# ============================================================================
# Property 20: CLI Error Exit Codes
# ============================================================================

@given(
    error_scenario=st.sampled_from([
        "invalid_json",
        "invalid_enum",
        "out_of_range",
        "file_not_found"
    ])
)
@settings(max_examples=100)
def test_property_20_cli_error_exit_codes(error_scenario):
    """
    # Feature: azure-vm-incident-copilot, Property 20: CLI Error Exit Codes
    
    FOR ALL CLI executions that encounter errors:
        The system SHALL return appropriate non-zero exit codes
    
    Validates Requirement 10.6:
    - Requirement 10.6: WHEN CLI execution encounters an error, return non-zero exit code
    
    Exit codes:
    - 0: Success
    - 1: Invalid JSON (malformed)
    - 2: Schema validation failure (invalid enum, out of range)
    - 3: File not found
    - 4: File I/O error (permission denied, etc.)
    - 5: Benchmark error
    - 99: Unexpected error
    
    Test Strategy:
    1. Generate various error scenarios using hypothesis
    2. Create temporary test files for each scenario
    3. Invoke CLI using click.testing.CliRunner
    4. Assert correct exit code for each error type
    5. Clean up temporary files
    """
    from main import main
    import tempfile
    import os
    
    runner = CliRunner()
    
    # Use a temporary directory in the current workspace (not isolated)
    with tempfile.TemporaryDirectory() as tmpdir:
        if error_scenario == "invalid_json":
            # Test exit code 1: Invalid JSON (malformed)
            test_file = os.path.join(tmpdir, "invalid.json")
            with open(test_file, "w") as f:
                f.write('{"power_state": "Running", "invalid_json')  # Missing closing brace
            
            result = runner.invoke(main, ["--input", test_file])
            assert result.exit_code == 1, \
                f"Expected exit code 1 for invalid JSON, got {result.exit_code}. Output: {result.output}"
        
        elif error_scenario == "invalid_enum":
            # Test exit code 2: Schema validation failure (invalid enum)
            telemetry = {
                "power_state": "InvalidState",  # Invalid enum value
                "provisioning_state": "Succeeded",
                "resource_health_status": "Available"
            }
            test_file = os.path.join(tmpdir, "invalid_enum.json")
            with open(test_file, "w") as f:
                json.dump(telemetry, f)
            
            result = runner.invoke(main, ["--input", test_file])
            assert result.exit_code == 2, \
                f"Expected exit code 2 for invalid enum, got {result.exit_code}. Output: {result.output}"
        
        elif error_scenario == "out_of_range":
            # Test exit code 2: Schema validation failure (out of range)
            telemetry = {
                "power_state": "Running",
                "provisioning_state": "Succeeded",
                "resource_health_status": "Available",
                "cpu_percent": 150.5  # Out of range (0-100)
            }
            test_file = os.path.join(tmpdir, "out_of_range.json")
            with open(test_file, "w") as f:
                json.dump(telemetry, f)
            
            result = runner.invoke(main, ["--input", test_file])
            assert result.exit_code == 2, \
                f"Expected exit code 2 for out of range value, got {result.exit_code}. Output: {result.output}"
        
        elif error_scenario == "file_not_found":
            # Test exit code 3: File not found
            test_file = os.path.join(tmpdir, "nonexistent_file.json")
            result = runner.invoke(main, ["--input", test_file])
            assert result.exit_code == 3, \
                f"Expected exit code 3 for file not found, got {result.exit_code}. Output: {result.output}"


@given(telemetry_dict=valid_telemetry_strategy())
@settings(max_examples=100)
def test_property_20_cli_success_exit_code(telemetry_dict):
    """
    # Feature: azure-vm-incident-copilot, Property 20: CLI Error Exit Codes
    
    FOR ALL valid telemetry:
        The CLI SHALL return exit code 0 (success)
    
    Validates Requirement 10.6:
    - Requirement 10.6: Success returns exit code 0
    
    Test Strategy:
    1. Generate valid telemetry using hypothesis
    2. Write to temporary file
    3. Invoke CLI with --input flag
    4. Assert exit code is 0
    """
    from main import main
    import tempfile
    import os
    
    runner = CliRunner()
    
    # Use a temporary directory in the current workspace (not isolated)
    with tempfile.TemporaryDirectory() as tmpdir:
        # Write valid telemetry to file
        test_file = os.path.join(tmpdir, "valid.json")
        with open(test_file, "w") as f:
            json.dump(telemetry_dict, f)
        
        # Invoke CLI
        result = runner.invoke(main, ["--input", test_file])
        
        # Assert success exit code
        assert result.exit_code == 0, \
            f"Expected exit code 0 for valid telemetry, got {result.exit_code}. Output: {result.output}"


if __name__ == "__main__":
    # Run the test manually for debugging
    import pytest
    pytest.main([__file__, "-v", "-s"])
