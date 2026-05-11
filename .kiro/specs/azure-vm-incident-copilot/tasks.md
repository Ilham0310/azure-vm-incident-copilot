# Implementation Plan: Azure VM Incident Copilot

## Overview

This implementation plan creates a read-only diagnostic system for Azure VM incidents. The system validates structured telemetry against a schema with 30+ fields, applies a decision policy with three states (diagnose, diagnose_low_confidence, abstain_request_next_check), enforces 6 safety rules, and returns structured diagnostic output. The implementation follows a setup-first approach where configuration files are generated before the main pipeline components are built.

## Tasks

- [x] 1. Setup project structure and dependencies
  - Create directory structure (setup/, schemas/, policy/, data/, src/, tests/, docs/)
  - Create src/__init__.py (empty package marker)
  - Create tests/__init__.py (empty package marker)
  - Create tests/unit/__init__.py (empty package marker)
  - Create tests/property/__init__.py (empty package marker)
  - Create setup/__init__.py (empty package marker)
  - Create requirements.txt with runtime dependencies (jsonschema, pydantic, pandas, click)
  - Create requirements-test.txt with test dependencies (pytest, hypothesis, pytest-cov)
  - Create README.md with project overview and usage instructions
  - _Requirements: 11.1, 11.2, 11.3, 11.10_

- [x] 2. Implement setup phase generators
  - [x] 2.0 Create setup/run_setup.py as a standalone setup runner
    - Implements the same 4-step setup sequence as main.py --setup
    - Calls generate_schema.py, generate_output_schema.py, generate_policy.py, generate_benchmark.py in sequence
    - Can be run directly: python setup/run_setup.py
    - Does NOT depend on main.py or any src/ components
    - Logs which files were created vs skipped (idempotency)
    - _Requirements: 11.1_

  - [x] 2.1 Create setup/generate_schema.py for triage schema generation
    - Generate JSON Schema with all 30+ telemetry field definitions
    - Include 8 enum types with value constraints (PowerState, ProvisioningState, ResourceHealthStatus, BootDiagnosticsStatus, AzureVMAgentStatus, AppHealthStatus, ConnectionTroubleshootResult, MonitorAgentStatus)
    - Include numeric range constraints (0-100 for percentages, >=0 for latencies)
    - Define required fields: power_state, provisioning_state, resource_health_status
    - Write to schemas/azure_vm_triage_schema.json with idempotency check
    - _Requirements: 1.3-1.28, 2.4, 2.5, 2.6_

  - [x] 2.2 Create setup/generate_output_schema.py for output schema generation
    - Generate JSON Schema with 7 required output fields
    - Define decision enum (diagnose, diagnose_low_confidence, abstain_request_next_check)
    - Define confidence_score range (0.0-1.0)
    - Write to schemas/output_schema.json with idempotency check
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8_

  - [x] 2.3 Create setup/generate_policy.py for decision policy generation
    - Generate decision rules A, B, C with exact thresholds
    - Generate 6 safety rules with conditions and actions
    - Generate confidence scoring weights (40% completeness, 30% pattern, 30% consistency)
    - Write to policy/decision_policy.json with idempotency check
    - _Requirements: 3.2, 3.3, 6.1-6.5, 7.1-7.5_

  - [x] 2.4 Create setup/generate_benchmark.py for benchmark dataset generation
    - Generate 35 benchmark cases: 20 pattern cases + 5 clean + 5 missing-telemetry + 5 conflicting-signal
    - Include all 20 known incident patterns with representative telemetry
    - Include expected_decision and expected_diagnosis for each case
    - Write to data/benchmark_cases.csv with idempotency check
    - _Requirements: 9.0.1, 9.0.2, 9.0.3, 9.0.4, 9.0.5, 9.0.6, 9.0.7_

- [x] 3. Checkpoint - Verify setup generators
  - Run python setup/run_setup.py to generate all configuration files
  - Verify schemas/azure_vm_triage_schema.json contains 30+ field definitions
  - Verify policy/decision_policy.json contains rules A, B, C and 6 safety rules
  - Verify data/benchmark_cases.csv contains 35 cases
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement core data models
  - [x] 4.1 Create src/models.py with all Pydantic models and enums
    - Define 8 enum classes (PowerState, ProvisioningState, ResourceHealthStatus, BootDiagnosticsStatus, AzureVMAgentStatus, AppHealthStatus, ConnectionTroubleshootResult, MonitorAgentStatus, DecisionState)
    - Define TelemetryInput model with 30+ fields and validation constraints
    - Define DiagnosticOutput model with 7 required fields and next_check validator
    - Define ValidationResult, ValidationError, Decision models
    - Define BenchmarkCase, CaseResult, PatternSummary, BenchmarkResults models
    - _Requirements: 1.3-1.28, 4.1-4.8, 12.5, 12.6_

  - [x] 4.2 Write property test for TelemetryInput round-trip integrity
    - **Property 17: Telemetry Round-Trip Integrity**
    - **Validates: Requirements 12.1, 12.3**

  - [x] 4.3 Create tests/property/strategies.py with hypothesis strategies
    - Implement valid_telemetry_strategy() for generating valid telemetry with random field combinations
    - Implement invalid_enum_strategy() for generating telemetry with invalid enum values
    - Implement out_of_range_numeric_strategy() for generating telemetry with out-of-range numbers
    - Implement low_completeness_strategy() for generating telemetry with <60% completeness
    - Implement platform_event_strategy() for generating telemetry with platform event annotations
    - Implement boot_failure_strategy() for generating telemetry with BSOD/KernelPanic status
    - Configure hypothesis with max_examples=100 and deterministic seed
    - _Requirements: 11.9_

- [x] 5. Implement schema validation component
  - [x] 5.1 Create src/validator.py with SchemaValidator class
    - Implement validate() method with JSON parsing and detailed error reporting
    - Parse JSON with line/column error details for malformed input
    - Validate against triage schema using jsonschema library
    - Return ValidationResult with parsed TelemetryInput or detailed errors
    - Ignore unknown fields for forward compatibility
    - _Requirements: 1.1, 1.2, 2.1, 2.2, 2.3, 2.7, 2.8, 2.9_

  - [x] 5.2 Write property test for schema validation accepts all valid fields
    - **Property 1: Schema Validation Accepts All Valid Fields**
    - **Validates: Requirements 1.1, 1.3-1.28, 2.1, 2.3**

  - [x] 5.3 Write property test for schema validation reports detailed errors
    - **Property 2: Schema Validation Reports Detailed Errors**
    - **Validates: Requirements 2.2, 2.8, 2.9**

  - [x] 5.4 Write property test for malformed JSON error reporting
    - **Property 3: Malformed JSON Error Reporting**
    - **Validates: Requirements 1.2**

  - [x] 5.5 Write property test for unknown fields ignored
    - **Property 4: Unknown Fields Ignored**
    - **Validates: Requirements 2.7**

- [x] 6. Implement confidence scoring component
  - [x] 6.1 Create src/confidence_scorer.py with ConfidenceScorer class
    - Implement calculate_completeness() method to count non-null optional fields
    - Implement calculate_confidence() method with weighted algorithm (40% completeness + 30% pattern + 30% consistency)
    - Implement signal conflict detection (none, minor, major)
    - Implement pattern match weighting (exact, partial, none)
    - _Requirements: 3.2, 3.3, 4.4_

  - [ ]* 6.2 Write unit tests for confidence scorer
    - Test completeness calculation at 0%, 25%, 50%, 75%, 90%, 100%
    - Test confidence score with various combinations of completeness, pattern match, and conflicts
    - Test signal conflict detection for minor and major conflicts
    - _Requirements: 3.2, 3.3_

- [x] 7. Implement decision engine component
  - [x] 7.1 Create src/decision_engine.py with DecisionEngine class
    - Implement decide() method with evaluation order: safety rules → completeness → conflicts → patterns → decision
    - Implement 6 safety rule validators (platform event, boot failure, low confidence destructive, network security, disk, failed state)
    - Implement 20 pattern matchers as individual functions (vm_stopped_by_user, nsg_blocks_rdp, nsg_blocks_ssh, high_cpu, os_disk_full, memory_exhaustion, boot_bsod, boot_kernel_panic, vm_running_no_heartbeat, resource_health_unavailable, conflicting_nsg_signals, app_unhealthy_vm_healthy, disk_io_saturation, vm_deallocated, provisioning_failed, failed_state_insufficient_data, platform_degradation, boot_stuck, vm_agent_failed, monitor_agent_failed)
    - Implement decision policy rules A, B, C with exact thresholds
    - Generate evidence, evidence_gap, and next_check for each decision
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 6.1-6.5, 7.1-7.5, 8.1-8.20_

  - [x] 7.2 Write property test for decision determinism
    - **Property 5: Decision Determinism**
    - **Validates: Requirements 3.8**

  - [x] 7.3 Write property test for exactly one decision
    - **Property 6: Exactly One Decision**
    - **Validates: Requirements 3.1**

  - [x] 7.4 Write property test for low completeness triggers abstain
    - **Property 7: Low Completeness Triggers Abstain**
    - **Validates: Requirements 3.4**

  - [x] 7.5 Write property test for missing critical signals trigger abstain
    - **Property 16: Missing Critical Signals Trigger Abstain**
    - **Validates: Requirements 3.5**

  - [x] 7.6 Write property test for platform event triggers abstain
    - **Property 14: Platform Event Triggers Abstain**
    - **Validates: Requirements 3.7, 6.1, 6.2**

  - [x] 7.7 Write property test for boot failure safety
    - **Property 11: Boot Failure Safety**
    - **Validates: Requirements 6.3, 6.4**

  - [x] 7.8 Write property test for low confidence destructive action safety
    - **Property 12: Low Confidence Destructive Action Safety**
    - **Validates: Requirements 6.5, 7.3, 7.4**

  - [x] 7.9 Write property test for network security safety
    - **Property 13: Network Security Safety**
    - **Validates: Requirements 7.1, 7.2**

  - [x] 7.10 Write property test for failed state safety
    - **Property 15: Failed State Safety**
    - **Validates: Requirements 7.5**

  - [ ]* 7.11 Write unit tests for all 20 incident patterns
    - Test each pattern with specific telemetry examples
    - Verify diagnosis text, evidence, and next_check for each pattern
    - _Requirements: 8.1-8.20_

- [x] 8. Checkpoint - Verify decision engine
  - Test decision engine with sample telemetry for each of the 20 patterns
  - Verify all 6 safety rules prevent unsafe suggestions
  - Verify decision policy rules A, B, C work correctly
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Implement explanation formatter component
  - [x] 9.1 Create src/explanation_formatter.py with ExplanationFormatter class
    - Implement format_output() method to generate all 7 required output fields
    - Format evidence list from telemetry signals (e.g., "power_state=Stopped")
    - Identify evidence_gap from missing fields
    - Generate human-readable explanation text with reasoning
    - Ensure next_check is populated for abstain decisions
    - _Requirements: 4.1-4.10, 12.2_

  - [x] 9.2 Write property test for output structure completeness
    - **Property 8: Output Structure Completeness**
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8**

  - [x] 9.3 Write property test for abstain populates next check
    - **Property 9: Abstain Populates Next Check**
    - **Validates: Requirements 4.9**

  - [x] 9.4 Write property test for diagnose requires high confidence
    - **Property 10: Diagnose Requires High Confidence**
    - **Validates: Requirements 4.10**

  - [x] 9.5 Write property test for output is valid JSON
    - **Property 18: Output is Valid JSON**
    - **Validates: Requirements 4.1, 12.2**

- [x] 10. Implement benchmark loader component
  - [x] 10.1 Create src/benchmark_loader.py with BenchmarkLoader class
    - Implement load_cases() method supporting JSON and CSV formats
    - Validate benchmark case structure (case_id, case_name, incident_pattern, telemetry_input, expected_decision, expected_diagnosis, notes)
    - Handle file not found and invalid format errors
    - _Requirements: 9.1, 9.2, 9.5, 9.6, 9.7, 9.8_

  - [ ]* 10.2 Write unit tests for benchmark loader
    - Test JSON and CSV loading
    - Test invalid format handling
    - Test case structure validation
    - _Requirements: 9.1, 9.2_

- [x] 11. Implement test harness component
  - [x] 11.1 Create src/test_harness.py with TestHarness class
    - Implement run_benchmark() method for batch processing
    - Compare actual vs expected decision for each case
    - Record pass/fail status and execution time
    - Calculate summary statistics by incident pattern
    - Generate BenchmarkResults with all metrics
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

  - [x] 11.2 Write property test for benchmark case processing
    - **Property 19: Benchmark Case Processing**
    - **Validates: Requirements 9.1, 9.2**

- [x] 12. Implement CLI interface
  - [x] 12.1 Create main.py with click-based CLI
    - Implement --setup flag to run all setup generators in sequence
    - Implement --input flag for single telemetry file processing
    - Implement --output flag for file output (default: stdout)
    - Implement --benchmark flag for batch benchmark processing
    - Orchestrate pipeline: validate → score → decide → format
    - Handle file I/O errors with appropriate exit codes (0, 1, 2, 3, 4, 5, 99)
    - Ensure no Azure connectivity required
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 11.1_

  - [x] 12.2 Write property test for CLI error exit codes
    - **Property 20: CLI Error Exit Codes**
    - **Validates: Requirements 10.6**

  - [ ]* 12.3 Write unit tests for CLI interface
    - Test --setup flag creates all configuration files
    - Test --input and --output flags for file I/O
    - Test --benchmark flag for batch processing
    - Test error exit codes for various failure scenarios
    - Test stdout output (default behavior)
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

  - [x] 12.4 Create agent/config.py with AgentConfig model
    - Define AgentConfig Pydantic model: subscription_id, resource_group, vm_name, log_analytics_workspace_id, app_insights_connection_string, interval_seconds (default 300), output_dir (default "results/"), alert_on_diagnose, alert_on_low_confidence
    - Implement load_from_file(path) classmethod for JSON config loading
    - Implement load_from_env() classmethod for environment variable loading (AZURE_SUBSCRIPTION_ID, AZURE_RESOURCE_GROUP, AZURE_VM_NAME, AZURE_WORKSPACE_ID)
    - _Requirements: 13.12_

  - [x] 12.5 Create agent/collector.py with TelemetryCollectorAgent
    - Implement __init__ with DefaultAzureCredential, ResourceGraphClient, MetricsQueryClient, LogsQueryClient
    - Implement _collect_from_arg() with single KQL query covering: power_state, provisioning_state, azure_vm_agent_status, boot_diagnostics_status, boot_diagnostics_error, resource_health_status, resource_health_annotation, nsg_allow_rdp_3389, nsg_allow_ssh_22
    - Implement _collect_metrics() with MetricsQueryClient batch query for: cpu_percent, memory_percent, memory_available_mb, os_disk_latency_ms, data_disk_latency_ms, os_disk_percent_full (last 5 minutes, average aggregation)
    - Implement _collect_logs() with LogsQueryClient KQL for: heartbeat_present, heartbeat_last_received, monitor_agent_status, app_health_status, app_error_message
    - Implement _calculate_completeness() returning (data_completeness_percent, missing_signals)
    - Implement collect() combining all steps into TelemetryInput
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 13.11_

  - [x] 12.6 Create agent/scheduler.py with IncidentCopilotScheduler
    - Implement run() using APScheduler BlockingScheduler with interval_seconds from AgentConfig
    - Implement run_once() for single-cycle execution
    - Implement _on_tick(): collect → validate → score → decide → format → append to results/output.jsonl
    - Output per line: timestamp, vm_name, resource_group, cycle_duration_ms, diagnostic_output
    - Log to console: [timestamp] VM=<name> decision=<state> confidence=<score> duration=<ms>ms
    - Create results/ directory if it does not exist
    - _Requirements: 13.7, 13.8, 13.9, 13.10_

  - [x] 12.7 Update main.py CLI with --agent mode
    - Add --agent flag (is_flag=True)
    - Add --vm, --rg, --interval, --once, --config options
    - Wire --agent + --once to scheduler.run_once()
    - Wire --agent (without --once) to scheduler.run()
    - Create requirements-agent.txt with: azure-identity>=1.15.0, azure-mgmt-resourcegraph>=8.0.0, azure-monitor-query>=1.3.0, apscheduler>=3.10.0, -r requirements.txt
    - _Requirements: 13.7, 13.8, 13.13_

  - [x] 12.8 Create ui/app.py with FastAPI web dashboard
    - Implement create_app() function returning FastAPI instance
    - Mount static files directory (ui/static)
    - Implement GET /api/status - returns latest row from results/output.jsonl
    - Implement GET /api/feed - returns last 50 rows with optional decision filter
    - Implement POST /api/triage - runs triage pipeline on posted telemetry JSON
    - Implement POST /api/agent/start - starts agent scheduler in background thread
    - Implement POST /api/agent/stop - stops running agent scheduler
    - Implement GET /api/agent/status - returns agent running status and config
    - Implement POST /api/agent/scan-now - triggers one collection cycle immediately
    - Implement GET /api/benchmark - runs benchmark and returns BenchmarkResults
    - Implement GET /api/logs - returns last 20 agent log lines
    - _Requirements: 14.1, 14.2, 14.11_

  - [x] 12.9 Create ui/static/index.html with dashboard frontend
    - Implement single HTML file with 5 pages as tabs (Dashboard, Live Feed, Manual Triage, Agent Control, Benchmark)
    - Use vanilla JavaScript + TailwindCSS CDN (no npm/node required)
    - Dashboard page: VM status card, Scan Now button, auto-refresh toggle (30s), agent status indicator
    - Live Feed page: Table of last 50 results, filter by decision, export to CSV, auto-refresh (10s)
    - Manual Triage page: JSON text area, Run Triage button, formatted DiagnosticOutput display with color-coded badges
    - Agent Control page: Config form (VM Name, Resource Group, Subscription ID, Workspace ID, Interval), Start/Stop buttons, log tail (20 lines, auto-refresh 5s)
    - Benchmark page: Run Benchmark button, results table, summary stats, bar chart (HTML canvas)
    - Color coding: Green (#10b981) = diagnose, Yellow (#f59e0b) = diagnose_low_confidence, Red (#ef4444) = abstain_request_next_check
    - _Requirements: 14.3, 14.4, 14.5, 14.6, 14.7, 14.8, 14.9, 14.10_

  - [x] 12.10 Update main.py CLI with --ui mode
    - Add --ui flag (is_flag=True)
    - When --ui flag is used: import uvicorn, from ui.app import create_app, uvicorn.run(app, host="0.0.0.0", port=8000)
    - Create requirements-ui.txt with: fastapi>=0.110.0, uvicorn>=0.27.0, -r requirements.txt
    - _Requirements: 14.1, 14.12_

- [x] 13. Checkpoint - End-to-end integration testing
  - Run python main.py --setup to generate configuration files
  - Test single case processing with python main.py --input sample.json
  - Test benchmark processing with python main.py --benchmark data/benchmark_cases.csv
  - Verify all 35 benchmark cases process without exceptions
  - Verify 95%+ accuracy on expected decision states
  - Run python main.py --agent --vm <vm> --rg <rg> --once (with mocked Azure APIs)
  - Verify results/output.jsonl contains one valid JSON line
  - Verify all 3 Azure API calls complete without error
  - Verify DiagnosticOutput is valid and pipeline ran end-to-end
  - Run python main.py --ui and verify dashboard loads at http://localhost:8000
  - Test Manual Triage page with sample telemetry JSON
  - Verify all API routes return valid responses
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 14. Implement all 20 property-based tests
  - [ ]* 14.1 Implement all 20 property-based tests
    - Create tests/property/test_properties_validation.py (Properties 1-4)
    - Create tests/property/test_properties_decision.py (Properties 5-10)
    - Create tests/property/test_properties_safety.py (Properties 11-16)
    - Create tests/property/test_properties_integrity.py (Properties 17-20)
    - Tag each test with feature name and property number
    - Run 100+ iterations per property test
    - _Requirements: 11.9_

- [x] 15. Create documentation
  - [x] 15.1 Create docs/architecture.md with detailed architecture documentation
    - Document setup phase and main triage pipeline
    - Document component interaction flow
    - Document data models and interfaces
    - _Requirements: 11.1_

  - [x] 15.2 Create docs/decision_policy.md with decision policy rules
    - Document rules A, B, C with exact thresholds
    - Document evaluation order and decision logic
    - Provide examples for each rule
    - _Requirements: 3.1, 3.2, 3.3_

  - [x] 15.3 Create docs/safety_rules.md with safety rules documentation
    - Document all 6 safety rules with conditions and actions
    - Provide examples of violations and correct behavior
    - _Requirements: 6.1-6.5, 7.1-7.5_

  - [x] 15.4 Create docs/incident_patterns.md with incident patterns documentation
    - Document all 20 known patterns with matching conditions
    - Provide telemetry examples for each pattern
    - Document expected diagnosis and next_check for each pattern
    - _Requirements: 8.1-8.20_

- [x] 16. Final checkpoint - Complete system validation
  - Run full test suite: pytest tests/ -v --cov=src --cov-report=term
  - Verify 90%+ line coverage and 85%+ branch coverage
  - Run all 20 property-based tests with 100+ iterations each
  - Run benchmark with all 35 cases and verify 95%+ accuracy
  - Verify all safety rules prevent unsafe suggestions
  - Verify read-only operation (no write operations or remediation actions)
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are unit tests that can be deferred for faster MVP. Property-based tests are required and must not be skipped.
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at key milestones
- Property tests validate universal correctness properties with 100+ iterations
- Unit tests validate specific examples and edge cases for all 20 incident patterns
- Setup phase must complete before main pipeline components can be tested
- All components are designed for local execution without Azure connectivity
