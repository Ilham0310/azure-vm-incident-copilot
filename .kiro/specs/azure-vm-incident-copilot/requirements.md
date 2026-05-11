# Requirements Document

## Introduction

The Azure VM Incident Copilot is a read-only diagnostic system that automates triage for Azure VM incidents including server down, SSH/RDP failures, performance degradation, network issues, and boot failures. The system accepts structured Azure VM telemetry in JSON format, validates it against a triage schema, applies a decision policy to determine diagnostic confidence, and returns structured output with diagnosis, evidence, gaps, and next steps. The system never executes remediation operations and is tested against a benchmark of 25-50 Azure VM incident cases.

## Glossary

- **Incident_Copilot**: The diagnostic system that analyzes Azure VM incidents and returns triage decisions
- **Triage_Schema**: The JSON schema defining valid telemetry input structure with 30+ signal fields
- **Decision_Policy**: The rule-based logic that returns exactly one of three decisions: diagnose, diagnose_low_confidence, or abstain_request_next_check
- **Telemetry_Input**: Structured JSON data containing Azure VM signals including power state, resource health, metrics, and network connectivity
- **Diagnostic_Output**: Structured JSON response containing decision, diagnosis, confidence_score, evidence, evidence_gap, next_check, and explanation
- **Confidence_Score**: Numerical value from 0.0 to 1.0 indicating diagnostic certainty
- **Data_Completeness**: Percentage of required telemetry signals present in input (0-100%)
- **Evidence**: List of telemetry signals that support the diagnosis
- **Evidence_Gap**: List of missing or incomplete telemetry signals needed for higher confidence
- **Next_Check**: Specific diagnostic action requested when data is insufficient
- **Benchmark_Case**: One of 25-50 test cases representing known Azure VM incident patterns
- **Safety_Rule**: Hard constraint preventing unsafe remediation suggestions
- **Incident_Pattern**: One of 20 known failure modes used for benchmark testing
- **TelemetryCollectorAgent**: Automated agent that collects Azure VM telemetry on a scheduled interval and runs triage pipeline

## Requirements

### Requirement 1: Accept Structured Azure VM Telemetry Input

**User Story:** As a cloud orchestration engineer, I want to submit Azure VM telemetry in JSON format, so that the system can analyze incidents consistently.

#### Acceptance Criteria

1. THE Incident_Copilot SHALL accept Telemetry_Input in JSON format
2. WHEN Telemetry_Input is malformed JSON, THE Incident_Copilot SHALL return a parsing error with line and column details
3. THE Incident_Copilot SHALL accept all 30+ telemetry signal fields defined in the Triage_Schema
4. THE Incident_Copilot SHALL accept power_state values: Running, Stopped, Deallocated, Failed, Unknown
5. THE Incident_Copilot SHALL accept provisioning_state values: Succeeded, Failed, In Progress, Unknown
6. THE Incident_Copilot SHALL accept resource_health_status values: Available, Degraded, Unavailable, Unknown
7. THE Incident_Copilot SHALL accept resource_health_annotation as a string field
8. THE Incident_Copilot SHALL accept heartbeat_present as a boolean field
9. THE Incident_Copilot SHALL accept heartbeat_last_received as a datetime field
10. THE Incident_Copilot SHALL accept boot_diagnostics_status values: Normal, BSOD, KernelPanic, Stuck, Unknown
11. THE Incident_Copilot SHALL accept boot_diagnostics_error as a string field
12. THE Incident_Copilot SHALL accept azure_vm_agent_status values: Healthy, Degraded, NotReporting, Failed, Unknown
13. THE Incident_Copilot SHALL accept cpu_percent as a float from 0 to 100
14. THE Incident_Copilot SHALL accept memory_available_mb as a float
15. THE Incident_Copilot SHALL accept memory_percent as a float from 0 to 100
16. THE Incident_Copilot SHALL accept os_disk_latency_ms as a float
17. THE Incident_Copilot SHALL accept data_disk_latency_ms as a float
18. THE Incident_Copilot SHALL accept os_disk_percent_full as a float from 0 to 100
19. THE Incident_Copilot SHALL accept app_health_status values: Healthy, Degraded, Unhealthy, Unknown
20. THE Incident_Copilot SHALL accept app_error_message as a string field
21. THE Incident_Copilot SHALL accept nsg_allow_rdp_3389 as a boolean field
22. THE Incident_Copilot SHALL accept nsg_allow_ssh_22 as a boolean field
23. THE Incident_Copilot SHALL accept connection_troubleshoot_rdp values: Allow, Deny, Inconclusive, Timeout, Unknown
24. THE Incident_Copilot SHALL accept connection_troubleshoot_ssh values: Allow, Deny, Inconclusive, Timeout, Unknown
25. THE Incident_Copilot SHALL accept connection_troubleshoot_verdict as a string field
26. THE Incident_Copilot SHALL accept monitor_agent_status values: Healthy, Degraded, Failed, NotInstalled, Unknown
27. THE Incident_Copilot SHALL accept data_completeness_percent as a float from 0 to 100
28. THE Incident_Copilot SHALL accept missing_signals as a list of strings

### Requirement 2: Validate Input Against Triage Schema

**User Story:** As a cloud orchestration engineer, I want telemetry validated against a schema, so that invalid data is rejected before analysis.

#### Acceptance Criteria

1. THE Incident_Copilot SHALL validate Telemetry_Input against the Triage_Schema before policy evaluation
2. WHEN Telemetry_Input fails schema validation, THE Incident_Copilot SHALL return validation errors with field names and constraint violations
3. WHEN Telemetry_Input passes schema validation, THE Incident_Copilot SHALL proceed to Decision_Policy evaluation
4. THE Triage_Schema SHALL define data types for all 30+ telemetry signal fields
5. THE Triage_Schema SHALL define value constraints for enumerated fields
6. THE Triage_Schema SHALL define numeric ranges for percentage and metric fields
7. WHEN Telemetry_Input contains unknown fields, THE Incident_Copilot SHALL ignore them and continue processing
8. WHEN Telemetry_Input contains invalid enum values, THE Incident_Copilot SHALL return a schema validation error
9. WHEN Telemetry_Input contains out-of-range numeric values, THE Incident_Copilot SHALL return a schema validation error

### Requirement 3: Apply Decision Policy with Three-State Output

**User Story:** As a cloud orchestration engineer, I want the system to return exactly one decision state, so that I know whether to act, validate, or gather more data.

#### Acceptance Criteria

1. THE Decision_Policy SHALL evaluate validated Telemetry_Input and return exactly one decision: diagnose, diagnose_low_confidence, or abstain_request_next_check
2. WHEN confidence_score is greater than or equal to 0.70 AND Data_Completeness is greater than or equal to 90 percent AND no conflicting signals exist AND root cause maps to one known Incident_Pattern AND remediation is safe and reversible, THE Decision_Policy SHALL return diagnose
3. WHEN confidence_score is between 0.40 and 0.69 AND Data_Completeness is between 60 and 89 percent AND minor signal conflicts exist, THE Decision_Policy SHALL return diagnose_low_confidence
4. WHEN Data_Completeness is less than 60 percent, THE Decision_Policy SHALL return abstain_request_next_check
5. WHEN critical signals are missing or unknown, THE Decision_Policy SHALL return abstain_request_next_check
6. WHEN severe unresolvable signal conflict exists, THE Decision_Policy SHALL return abstain_request_next_check
7. WHEN resource_health_annotation indicates a platform-initiated event, THE Decision_Policy SHALL return abstain_request_next_check
8. THE Decision_Policy SHALL be deterministic for identical Telemetry_Input

### Requirement 4: Return Structured Diagnostic Output

**User Story:** As a cloud orchestration engineer, I want structured diagnostic results, so that I can programmatically process recommendations.

#### Acceptance Criteria

1. THE Incident_Copilot SHALL return Diagnostic_Output in JSON format
2. THE Diagnostic_Output SHALL include a decision field with exactly one value: diagnose, diagnose_low_confidence, or abstain_request_next_check
3. THE Diagnostic_Output SHALL include a diagnosis field describing the identified issue or healthy state
4. THE Diagnostic_Output SHALL include a confidence_score field with a float value from 0.0 to 1.0
5. THE Diagnostic_Output SHALL include an evidence field containing a list of telemetry signals supporting the diagnosis
6. THE Diagnostic_Output SHALL include an evidence_gap field containing a list of missing or incomplete telemetry signals
7. THE Diagnostic_Output SHALL include a next_check field with a specific diagnostic action to gather more information
8. THE Diagnostic_Output SHALL include an explanation field describing the reasoning for the decision
9. WHEN decision is abstain_request_next_check, THE Diagnostic_Output SHALL populate next_check with a specific requested signal or check
10. WHEN decision is diagnose, THE Diagnostic_Output SHALL set confidence_score to a value greater than or equal to 0.70

### Requirement 5: Enforce Read-Only Operation

**User Story:** As a cloud orchestration engineer, I want to ensure no remediation is executed, so that the system remains safe for automated triage.

#### Acceptance Criteria

1. THE Incident_Copilot SHALL NOT execute any write operations on Azure VMs
2. THE Incident_Copilot SHALL NOT execute any remediation actions on Azure VMs
3. THE Incident_Copilot SHALL NOT invoke Azure management APIs for state modification
4. THE Incident_Copilot SHALL NOT modify VM configuration, disks, network settings, or resource groups
5. THE Diagnostic_Output SHALL contain only analysis, diagnosis, and recommendations
6. THE next_check field SHALL contain only safe read-only diagnostic actions

### Requirement 6: Apply Safety Rules for Restart Suggestions

**User Story:** As a cloud orchestration engineer, I want the system to avoid unsafe restart suggestions, so that platform events are not interrupted.

#### Acceptance Criteria

1. WHEN resource_health_annotation indicates a platform-initiated event, THE Decision_Policy SHALL NOT suggest VM restart in next_check
2. WHEN resource_health_annotation indicates a platform-initiated event, THE Decision_Policy SHALL return abstain_request_next_check
3. WHEN boot_diagnostics_status is BSOD, THE Decision_Policy SHALL NOT suggest VM restart in next_check
4. WHEN boot_diagnostics_status is KernelPanic, THE Decision_Policy SHALL NOT suggest VM restart in next_check
5. WHEN confidence_score is less than 0.9 AND diagnosis suggests destructive actions, THE Decision_Policy SHALL NOT include destructive actions in next_check

### Requirement 7: Apply Safety Rules for Network and Disk Operations

**User Story:** As a cloud orchestration engineer, I want the system to avoid unsafe network and disk suggestions, so that security and data integrity are preserved.

#### Acceptance Criteria

1. THE Decision_Policy SHALL NOT suggest disabling NSG rules in next_check
2. THE Decision_Policy SHALL NOT suggest disabling firewall rules in next_check
3. WHEN confidence_score is less than 0.9, THE Decision_Policy SHALL NOT suggest disk deletion in next_check
4. WHEN confidence_score is less than 0.9, THE Decision_Policy SHALL NOT suggest OS reset in next_check
5. WHEN power_state is Failed AND provisioning_state is Failed, THE Decision_Policy SHALL NOT suggest auto-remediation in next_check

### Requirement 8: Recognize Known Incident Patterns

**User Story:** As a cloud orchestration engineer, I want the system to recognize 20 known incident patterns, so that common issues are diagnosed accurately.

#### Acceptance Criteria

1. WHEN power_state is Stopped AND provisioning_state is Succeeded, THE Decision_Policy SHALL diagnose VM Stopped by user deallocation
2. WHEN nsg_allow_rdp_3389 is false AND connection_troubleshoot_rdp is Deny, THE Decision_Policy SHALL diagnose NSG blocks RDP
3. WHEN cpu_percent is greater than 95 for the reported period, THE Decision_Policy SHALL diagnose high CPU saturation
4. WHEN os_disk_percent_full is greater than 95, THE Decision_Policy SHALL diagnose OS disk full
5. WHEN memory_percent is greater than 95, THE Decision_Policy SHALL diagnose memory exhaustion
6. WHEN boot_diagnostics_status is BSOD, THE Decision_Policy SHALL diagnose boot BSOD
7. WHEN power_state is Running AND heartbeat_present is false, THE Decision_Policy SHALL diagnose VM running but no heartbeat
8. WHEN resource_health_status is Unavailable AND cpu_percent and memory_percent are normal, THE Decision_Policy SHALL diagnose resource health unavailable with normal metrics
9. WHEN nsg_allow_rdp_3389 is false AND connection_troubleshoot_rdp is Allow, THE Decision_Policy SHALL diagnose conflicting NSG and connection troubleshoot signals
10. WHEN app_health_status is Unhealthy AND azure_vm_agent_status is Healthy, THE Decision_Policy SHALL diagnose application unhealthy with healthy VM
11. WHEN os_disk_latency_ms is greater than 100 OR data_disk_latency_ms is greater than 100, THE Decision_Policy SHALL diagnose disk IO saturation
12. WHEN power_state is Deallocated, THE Decision_Policy SHALL diagnose deallocated VM
13. WHEN provisioning_state is Failed, THE Decision_Policy SHALL diagnose provisioning failed
14. WHEN power_state is Failed AND Data_Completeness is less than 30 percent, THE Decision_Policy SHALL diagnose failed state with insufficient data
15. WHEN resource_health_annotation contains platform degradation keywords, THE Decision_Policy SHALL diagnose platform degradation event
16. WHEN boot_diagnostics_status is KernelPanic, THE Decision_Policy SHALL diagnose boot kernel panic
17. WHEN boot_diagnostics_status is Stuck, THE Decision_Policy SHALL diagnose boot stuck at startup
18. WHEN azure_vm_agent_status is Failed, THE Decision_Policy SHALL diagnose Azure VM agent failure
19. WHEN monitor_agent_status is Failed, THE Decision_Policy SHALL diagnose monitoring agent failure
20. WHEN nsg_allow_ssh_22 is false AND connection_troubleshoot_ssh is Deny, THE Decision_Policy SHALL diagnose NSG blocks SSH

### Requirement 9: Test Against Benchmark Cases

**User Story:** As a cloud orchestration engineer, I want the system tested against 25-50 benchmark cases, so that diagnostic accuracy is validated.

#### Requirement 9.0: Generate Benchmark Dataset

THE Incident_Copilot SHALL generate the benchmark dataset if it does not exist.

##### Acceptance Criteria

1. THE setup script SHALL generate data/benchmark_cases.csv with 25-50 cases
2. THE benchmark SHALL include cases for all 20 known incident patterns
3. THE benchmark SHALL include at least 5 clean/healthy cases
4. THE benchmark SHALL include at least 5 missing-telemetry cases
5. THE benchmark SHALL include at least 5 conflicting-signal cases
6. Each benchmark case SHALL include: case_id, case_name, incident_pattern, telemetry_input (JSON), expected_decision, expected_diagnosis, notes
7. THE setup script SHALL NOT overwrite an existing benchmark file

#### Acceptance Criteria

1. THE Incident_Copilot SHALL process a benchmark dataset containing 25 to 50 Benchmark_Case records
2. WHEN a Benchmark_Case is processed, THE Incident_Copilot SHALL return Diagnostic_Output for that case
3. THE Incident_Copilot SHALL support batch processing of all Benchmark_Case records
4. THE Incident_Copilot SHALL output results for all Benchmark_Case records in a structured format for analysis
5. THE benchmark dataset SHALL include examples of all 20 known Incident_Pattern types
6. THE benchmark dataset SHALL include clean cases with no issues
7. THE benchmark dataset SHALL include cases with missing telemetry
8. THE benchmark dataset SHALL include cases with conflicting signals

### Requirement 10: Provide Command-Line Interface

**User Story:** As a cloud orchestration engineer, I want to run the system via CLI, so that I can test it locally without cloud dependencies.

#### Acceptance Criteria

1. THE Incident_Copilot SHALL provide a CLI accepting the command: python main.py --input incident.json
2. WHEN --input is provided with a file path, THE Incident_Copilot SHALL read Telemetry_Input from that file
3. WHEN Telemetry_Input is processed, THE Incident_Copilot SHALL write Diagnostic_Output to stdout
4. THE Incident_Copilot SHALL support a --output flag to write Diagnostic_Output to a specified file path
5. THE Incident_Copilot SHALL run entirely on the local machine without requiring Azure connectivity
6. WHEN CLI execution encounters an error, THE Incident_Copilot SHALL return a non-zero exit code

### Requirement 11: Implement in Python with Minimal Dependencies

**User Story:** As a cloud orchestration engineer, I want the system implemented in Python with minimal dependencies, so that deployment is simple.

#### Acceptance Criteria

1. THE Incident_Copilot SHALL be implemented using Python 3.8 or higher
2. THE Incident_Copilot SHALL include these runtime dependencies: jsonschema, pydantic, pandas, click
3. THE Incident_Copilot SHALL include these testing dependencies: pytest, hypothesis
4. THE Incident_Copilot SHALL use jsonschema for Triage_Schema validation
5. THE Incident_Copilot SHALL use pydantic for data structure modeling
6. THE Incident_Copilot SHALL use pandas for benchmark data processing
7. THE Incident_Copilot SHALL use click for CLI argument parsing
8. THE Incident_Copilot SHALL use pytest for unit testing
9. THE Incident_Copilot SHALL use hypothesis for property-based testing
10. THE Incident_Copilot SHALL include two dependency files:
   - requirements.txt for runtime dependencies
   - requirements-test.txt for test dependencies (includes -r requirements.txt)

**requirements.txt format:**
```
jsonschema>=4.0.0
pydantic>=2.0.0
pandas>=1.5.0
click>=8.0.0
```

**requirements-test.txt format:**
```
pytest>=7.0.0
hypothesis>=6.0.0
-r requirements.txt
```

### Requirement 12: Parse and Format Telemetry Data

**User Story:** As a cloud orchestration engineer, I want the system to parse and format telemetry correctly, so that data integrity is maintained.

#### Acceptance Criteria

1. WHEN valid Telemetry_Input is provided, THE Incident_Copilot SHALL parse it into internal data structures
2. THE Incident_Copilot SHALL format Diagnostic_Output as valid JSON conforming to the output schema
3. FOR ALL valid Telemetry_Input, parsing then formatting then parsing SHALL produce equivalent data structures
4. WHEN datetime fields are parsed, THE Incident_Copilot SHALL support ISO 8601 format
5. WHEN enum fields are parsed, THE Incident_Copilot SHALL preserve case sensitivity
6. WHEN numeric fields are parsed, THE Incident_Copilot SHALL preserve precision to two decimal places

### Requirement 13: Implement Telemetry Collector Agent

**User Story:** As a cloud orchestration engineer, I want an automated agent that collects Azure VM telemetry every 5-10 minutes, so that incidents are detected continuously without manual JSON input.

#### Acceptance Criteria

1. THE Incident_Copilot SHALL provide a TelemetryCollectorAgent that collects all 30+ telemetry fields from Azure automatically
2. THE TelemetryCollectorAgent SHALL use Azure Resource Graph to collect: power_state, provisioning_state, azure_vm_agent_status, boot_diagnostics_status, boot_diagnostics_error, resource_health_status, resource_health_annotation, nsg_allow_rdp_3389, nsg_allow_ssh_22 in a single KQL query
3. THE TelemetryCollectorAgent SHALL use Azure Monitor MetricsQueryClient to collect: cpu_percent, memory_percent, memory_available_mb, os_disk_latency_ms, data_disk_latency_ms, os_disk_percent_full
4. THE TelemetryCollectorAgent SHALL use Azure Monitor LogsQueryClient to collect: heartbeat_present, heartbeat_last_received, monitor_agent_status, app_health_status, app_error_message
5. THE TelemetryCollectorAgent SHALL auto-calculate data_completeness_percent and missing_signals from collected fields
6. THE TelemetryCollectorAgent SHALL use DefaultAzureCredential for authentication (read-only, no write operations)
7. THE TelemetryCollectorAgent SHALL run on a configurable interval (default 300 seconds / 5 minutes)
8. THE TelemetryCollectorAgent SHALL support a --once flag for single-run mode
9. WHEN a collection cycle completes, THE agent SHALL pass the telemetry through the full triage pipeline and append the DiagnosticOutput to results/output.jsonl
10. THE agent SHALL log the decision state and confidence_score to console on every cycle
11. THE agent SHALL NOT execute any write or remediation operations on Azure
12. THE AgentConfig SHALL be loadable from a JSON config file and environment variables
13. THE Incident_Copilot SHALL provide a requirements-agent.txt with: azure-identity>=1.15.0, azure-mgmt-resourcegraph>=8.0.0, azure-monitor-query>=1.3.0, apscheduler>=3.10.0, -r requirements.txt

### Requirement 14: Provide Web Dashboard UI

**User Story:** As a cloud orchestration engineer, I want a web dashboard to monitor VM health and run triage operations, so that I can use the system without CLI commands.

#### Acceptance Criteria

1. THE Incident_Copilot SHALL provide a web dashboard accessible at http://localhost:8000 when started with --ui flag
2. THE web dashboard SHALL use FastAPI for the backend and a single HTML file with vanilla JavaScript for the frontend
3. THE web dashboard SHALL provide a Dashboard page showing: VM status card with power_state, resource_health_status, last triage decision, confidence score, last scan time, and color-coded decision badges (Green=diagnose, Yellow=diagnose_low_confidence, Red=abstain_request_next_check)
4. THE Dashboard page SHALL provide a "Scan Now" button that triggers one agent collection cycle immediately
5. THE Dashboard page SHALL provide an auto-refresh toggle that refreshes the dashboard every 30 seconds
6. THE web dashboard SHALL provide a Live Feed page showing the last 50 rows from results/output.jsonl with columns: Timestamp, VM Name, Decision, Confidence Score, Diagnosis, Next Check, Duration(ms)
7. THE Live Feed page SHALL support filtering by decision state and exporting to CSV
8. THE web dashboard SHALL provide a Manual Triage page with a JSON text area for pasting telemetry and a "Run Triage" button that displays the DiagnosticOutput result
9. THE web dashboard SHALL provide an Agent Control page with form fields for VM Name, Resource Group, Subscription ID, Workspace ID, and Interval, plus Start/Stop Agent buttons
10. THE web dashboard SHALL provide a Benchmark page with a "Run Benchmark" button that displays results table and summary statistics
11. THE Incident_Copilot SHALL provide FastAPI routes: GET /api/status, GET /api/feed, POST /api/triage, POST /api/agent/start, POST /api/agent/stop, GET /api/agent/status, POST /api/agent/scan-now, GET /api/benchmark, GET /api/logs
12. THE Incident_Copilot SHALL provide a requirements-ui.txt with: fastapi>=0.110.0, uvicorn>=0.27.0, -r requirements.txt
13. THE web dashboard SHALL NOT execute any write or remediation operations on Azure VMs
