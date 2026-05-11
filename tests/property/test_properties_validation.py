"""
Property-based tests for schema validation (Properties 1-4).

This module tests:
- Property 1: Schema Validation Accepts All Valid Fields
- Property 2: Schema Validation Reports Detailed Errors
- Property 3: Malformed JSON Error Reporting
- Property 4: Unknown Fields Ignored
"""

import json
from hypothesis import given, settings, assume
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.validator import SchemaValidator
from tests.property.strategies import (
    valid_telemetry_strategy,
    invalid_enum_strategy,
    out_of_range_numeric_strategy
)


# ============================================================================
# Property 1: Schema Validation Accepts All Valid Fields
# ============================================================================

@given(telemetry_dict=valid_telemetry_strategy())
@settings(max_examples=100)
def test_property_1_schema_validation_accepts_all_valid_fields(telemetry_dict):
    """
    # Feature: azure-vm-incident-copilot, Property 1: Schema Validation Accepts All Valid Fields
    
    FOR ALL valid telemetry with any combination of valid field values:
        Schema validation SHALL accept the input
    
    Validates Requirements 1.1, 1.3-1.28, 2.1, 2.3:
    - Requirement 1.1: Accept Telemetry_Input in JSON format
    - Requirements 1.3-1.28: Accept all 30+ telemetry signal fields
    - Requirement 2.1: Validate Telemetry_Input against Triage_Schema
    - Requirement 2.3: Proceed to policy evaluation when validation passes
    
    Test Strategy:
    1. Generate valid telemetry with random field combinations
    2. Convert to JSON string
    3. Validate using SchemaValidator
    4. Assert validation passes (valid=True)
    5. Assert telemetry object is returned
    6. Assert no errors are reported
    """
    validator = SchemaValidator()
    
    # Convert dictionary to JSON string
    json_input = json.dumps(telemetry_dict)
    
    # Validate
    result = validator.validate(json_input)
    
    # Assert validation passes
    assert result.valid, f"Validation failed for valid telemetry: {result.errors}"
    assert result.telemetry is not None, "Telemetry object not returned for valid input"
    assert len(result.errors) == 0, f"Errors reported for valid input: {result.errors}"
    
    # Assert all required fields are present in parsed telemetry
    assert result.telemetry.power_state is not None
    assert result.telemetry.provisioning_state is not None
    assert result.telemetry.resource_health_status is not None


# ============================================================================
# Property 2: Schema Validation Reports Detailed Errors
# ============================================================================

@given(telemetry_dict=invalid_enum_strategy())
@settings(max_examples=100)
def test_property_2_schema_validation_reports_detailed_errors_enum(telemetry_dict):
    """
    # Feature: azure-vm-incident-copilot, Property 2: Schema Validation Reports Detailed Errors (Enum)
    
    FOR ALL telemetry with invalid enum values:
        Schema validation SHALL report detailed errors with field names and constraint violations
    
    Validates Requirements 2.2, 2.8, 2.9:
    - Requirement 2.2: Return validation errors with field names and constraint violations
    - Requirement 2.8: Return schema validation error for invalid enum values
    - Requirement 2.9: Return schema validation error for out-of-range numeric values
    
    Test Strategy:
    1. Generate telemetry with invalid enum value
    2. Convert to JSON string
    3. Validate using SchemaValidator
    4. Assert validation fails (valid=False)
    5. Assert errors list is not empty
    6. Assert error contains field name
    7. Assert error contains constraint violation message
    """
    validator = SchemaValidator()
    
    # Convert dictionary to JSON string
    json_input = json.dumps(telemetry_dict)
    
    # Validate
    result = validator.validate(json_input)
    
    # Assert validation fails
    assert not result.valid, "Validation passed for invalid enum value"
    assert result.telemetry is None, "Telemetry object returned for invalid input"
    assert len(result.errors) > 0, "No errors reported for invalid enum value"
    
    # Assert error details are present
    error = result.errors[0]
    assert error.field is not None and error.field != "", "Error missing field name"
    assert error.message is not None and error.message != "", "Error missing message"


@given(telemetry_dict=out_of_range_numeric_strategy())
@settings(max_examples=100)
def test_property_2_schema_validation_reports_detailed_errors_numeric(telemetry_dict):
    """
    # Feature: azure-vm-incident-copilot, Property 2: Schema Validation Reports Detailed Errors (Numeric)
    
    FOR ALL telemetry with out-of-range numeric values:
        Schema validation SHALL report detailed errors with field names and constraint violations
    
    Validates Requirements 2.2, 2.8, 2.9:
    - Requirement 2.2: Return validation errors with field names and constraint violations
    - Requirement 2.8: Return schema validation error for invalid enum values
    - Requirement 2.9: Return schema validation error for out-of-range numeric values
    
    Test Strategy:
    1. Generate telemetry with out-of-range numeric value
    2. Convert to JSON string
    3. Validate using SchemaValidator
    4. Assert validation fails (valid=False)
    5. Assert errors list is not empty
    6. Assert error contains field name
    7. Assert error contains constraint violation message
    """
    validator = SchemaValidator()
    
    # Convert dictionary to JSON string
    json_input = json.dumps(telemetry_dict)
    
    # Validate
    result = validator.validate(json_input)
    
    # Assert validation fails
    assert not result.valid, "Validation passed for out-of-range numeric value"
    assert result.telemetry is None, "Telemetry object returned for invalid input"
    assert len(result.errors) > 0, "No errors reported for out-of-range numeric value"
    
    # Assert error details are present
    error = result.errors[0]
    assert error.field is not None and error.field != "", "Error missing field name"
    assert error.message is not None and error.message != "", "Error missing message"


# ============================================================================
# Property 3: Malformed JSON Error Reporting
# ============================================================================

@settings(max_examples=100)
@given(valid_json=valid_telemetry_strategy())
def test_property_3_malformed_json_error_reporting(valid_json):
    """
    # Feature: azure-vm-incident-copilot, Property 3: Malformed JSON Error Reporting
    
    FOR ALL malformed JSON strings:
        Validator SHALL raise JSONParseError with line and column details
    
    Validates Requirement 1.2:
    - Requirement 1.2: Return parsing error with line and column details for malformed JSON
    
    Test Strategy:
    1. Generate valid telemetry dictionary
    2. Convert to JSON string
    3. Corrupt the JSON (remove a closing brace or add syntax error)
    4. Validate using SchemaValidator
    5. Assert JSONParseError is raised
    6. Assert error message mentions JSON parse error
    7. Assert error contains line/column information (when available)
    """
    from src.validator import JSONParseError
    validator = SchemaValidator()
    
    # Convert to valid JSON first
    valid_json_str = json.dumps(valid_json)
    
    # Corrupt the JSON by removing last closing brace
    if valid_json_str.endswith('}'):
        malformed_json = valid_json_str[:-1]  # Remove last }
    else:
        # Fallback: add invalid syntax
        malformed_json = valid_json_str + '{'
    
    # Validate - should raise JSONParseError
    try:
        result = validator.validate(malformed_json)
        assert False, "Expected JSONParseError for malformed JSON, but validation succeeded"
    except JSONParseError as e:
        # Assert error mentions JSON parsing
        assert "parse" in e.message.lower() or "json" in str(e).lower(), \
            f"Error message should mention JSON parsing: {e.message}"
        # Assert line and column are present
        assert e.line is not None, "Line number should be present in JSONParseError"
        assert e.column is not None, "Column number should be present in JSONParseError"


# ============================================================================
# Property 4: Unknown Fields Ignored
# ============================================================================

@given(telemetry_dict=valid_telemetry_strategy())
@settings(max_examples=100)
def test_property_4_unknown_fields_ignored(telemetry_dict):
    """
    # Feature: azure-vm-incident-copilot, Property 4: Unknown Fields Ignored
    
    FOR ALL valid telemetry with additional unknown fields:
        Schema validation SHALL ignore unknown fields and continue processing
    
    Validates Requirement 2.7:
    - Requirement 2.7: Ignore unknown fields and continue processing
    
    Test Strategy:
    1. Generate valid telemetry dictionary
    2. Add unknown fields (not in schema)
    3. Convert to JSON string
    4. Validate using SchemaValidator
    5. Assert validation passes (valid=True)
    6. Assert telemetry object is returned
    7. Assert no errors are reported
    
    This ensures forward compatibility - new fields added in future won't break validation.
    """
    validator = SchemaValidator()
    
    # Add unknown fields
    telemetry_with_unknown = telemetry_dict.copy()
    telemetry_with_unknown["unknown_field_1"] = "some_value"
    telemetry_with_unknown["unknown_field_2"] = 12345
    telemetry_with_unknown["future_feature_flag"] = True
    
    # Convert to JSON string
    json_input = json.dumps(telemetry_with_unknown)
    
    # Validate
    result = validator.validate(json_input)
    
    # Assert validation passes (unknown fields ignored)
    assert result.valid, f"Validation failed with unknown fields: {result.errors}"
    assert result.telemetry is not None, "Telemetry object not returned with unknown fields"
    assert len(result.errors) == 0, f"Errors reported for unknown fields: {result.errors}"
    
    # Assert required fields are still present
    assert result.telemetry.power_state is not None
    assert result.telemetry.provisioning_state is not None
    assert result.telemetry.resource_health_status is not None


if __name__ == "__main__":
    # Run the tests manually for debugging
    import pytest
    pytest.main([__file__, "-v", "-s"])
