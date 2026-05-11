# End-to-End Test Suite

## Overview

This directory contains comprehensive end-to-end tests for the Azure VM Incident Copilot system. The tests cover the complete system from agent collection through triage pipeline to results output, with all Azure API calls mocked for local execution.

## Test File

- `test_e2e_complete.py` - Comprehensive E2E test suite with 60+ test scenarios

## Test Sections

### Section 1: Agent Collection Edge Cases (10 scenarios)
Tests agent telemetry collection with mocked Azure APIs:
- Happy path with full data from all 3 APIs
- Azure API timeouts and rate limits
- VM not found (404) and permission denied (403)
- Metrics unavailable scenarios
- Log Analytics workspace not configured
- Partial collection (some APIs fail)
- All APIs return unknown/null values

**Note**: These tests require Azure SDK (`requirements-agent.txt`). They are automatically skipped if not installed.

### Section 2: Schema Validation Edge Cases (12 scenarios)
Tests schema validation with various input scenarios:
- All 30+ valid fields provided
- Only 3 required fields (minimum valid input)
- Missing required fields
- Invalid enum values
- Out of range numeric values
- Negative numeric values
- Malformed JSON with syntax errors
- Unknown extra fields (should be ignored)
- Empty strings for enum fields
- Boundary numeric values (0.0 and 100.0)
- Invalid datetime formats
- Type mismatches

### Section 3: Confidence Scorer Edge Cases (7 scenarios)
Tests confidence scoring algorithm:
- Maximum confidence (100% completeness + exact match + no conflicts)
- Minimum confidence (low completeness + no pattern + major conflict)
- Completeness boundaries at 60%, 89%, 90%
- Minor conflict detection
- Major conflict detection
- Partial pattern matches

### Section 4: Decision Engine Edge Cases (28 scenarios)
Tests decision engine with all patterns and safety rules:
- All 20 incident patterns (one test per pattern)
- Multiple patterns matching simultaneously
- Safety rules overriding high confidence
- Platform event overriding all decisions
- Failed state safety
- Network security safety
- Low confidence blocking destructive actions
- All critical signals unknown
- Decision determinism (same input, 100 runs)

### Section 5: Full Pipeline End-to-End Scenarios (18 scenarios)
Tests complete pipeline from collection to output:
- Happy path: agent → diagnose
- Agent collects partial data → abstain
- Agent collects conflicting signals → low confidence
- Safety rule intercepts high-confidence case
- Platform event detected
- Output written to results/output.jsonl
- Scheduler runs multiple cycles
- API fails mid-cycle, scheduler continues
- CLI --input with valid/invalid JSON
- CLI --benchmark runs all 35 cases
- UI API endpoints (/api/triage, /api/feed, etc.)
- Round-trip integrity (50 iterations)

### Section 6: Setup Phase Edge Cases (4 scenarios)
Tests setup phase generators:
- First time setup (no files exist)
- Idempotency (run setup twice)
- Partial setup (only some files missing)
- Output directories do not exist

## Running Tests

### Run all E2E tests:
```bash
python -m pytest tests/e2e/test_e2e_complete.py -v
```

### Run specific section:
```bash
# Schema validation tests
python -m pytest tests/e2e/test_e2e_complete.py::TestSchemaValidationEdgeCases -v

# Confidence scorer tests
python -m pytest tests/e2e/test_e2e_complete.py::TestConfidenceScorerEdgeCases -v

# Decision engine tests
python -m pytest tests/e2e/test_e2e_complete.py::TestDecisionEngineEdgeCases -v

# Setup phase tests
python -m pytest tests/e2e/test_e2e_complete.py::TestSetupPhase -v
```

### Run without agent tests (no Azure SDK required):
```bash
python -m pytest tests/e2e/test_e2e_complete.py -v -k "not Agent and not Pipeline"
```

### Run with coverage:
```bash
python -m pytest tests/e2e/test_e2e_complete.py -v --cov=src --cov=agent --cov-report=term
```

## Test Fixtures

The `conftest.py` file provides reusable fixtures:

- `full_telemetry_fixture` - Complete valid TelemetryInput with all fields
- `minimal_telemetry_fixture` - Only 3 required fields
- `pattern_telemetry_factory` - Factory for generating telemetry for any of 20 patterns
- `mock_arg_response_factory` - Factory for mock Azure Resource Graph responses
- `mock_metrics_response_factory` - Factory for mock Azure Monitor Metrics responses
- `mock_logs_response_factory` - Factory for mock Azure Monitor Logs responses
- `temp_output_dir` - Temporary results directory with automatic cleanup

## Coverage Expectation

This test suite alone should bring coverage to 90%+ across all `src/` and `agent/` modules when run with Azure SDK installed.

## Test Status

Current status: **30/60 tests passing** (50%)

Passing sections:
- Schema Validation: 10/10 ✓
- Confidence Scorer: 3/7 (partial)
- Decision Engine: 0/28 (needs fixes)
- Setup Phase: 0/4 (needs fixes)

Known issues to fix:
1. Decision model uses `state` attribute, not `decision`
2. Setup tests need correct import path
3. Some completeness calculations need adjustment

## Notes

- All Azure API calls are mocked using `unittest.mock.patch`
- Tests run locally without Azure connectivity
- Agent tests are automatically skipped if Azure SDK not installed
- Tests use temporary directories for file I/O
- All tests are deterministic and repeatable
