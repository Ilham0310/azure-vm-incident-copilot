# Design Document: Azure VM Incident Copilot

## Overview

The Azure VM Incident Copilot is a read-only diagnostic system that automates triage for Azure VM incidents including server down, SSH/RDP failures, performance degradation, network issues, and boot failures. The system accepts structured Azure VM telemetry in JSON format, validates it against a comprehensive triage schema with 30+ telemetry fields, applies a deterministic decision policy with three possible outcomes, and returns structured diagnostic output with diagnosis, evidence, gaps, and next steps.

The system is designed with strict safety constraints: it never executes remediation operations, never modifies Azure resources, and enforces six safety rules to prevent unsafe suggestions during platform events, boot failures, or low-confidence scenarios. The system is tested against a benchmark of 25-50 Azure VM incident cases covering 20 known failure patterns.

### Key Design Principles

1. **Read-Only Operation**: No write operations or remediation actions are executed
2. **Deterministic Decision Logic**: Identical inputs produce identical outputs
3. **Safety-First**: Six safety rules prevent unsafe suggestions in all scenarios
4. **Modular Architecture**: Clear separation of concerns across seven components
5. **Comprehensive Validation**: 30+ telemetry fields with strict type and range constraints
6. **Testability**: Property-based testing with 100+ iterations per property

### System Boundaries

**In Scope:**
- JSON telemetry parsing with detailed error reporting (line/column)
- Schema-based validation for 30+ telemetry fields
- Decision policy evaluation with three states (diagnose, diagnose_low_confidence, abstain_request_next_check)
- Confidence scoring algorithm (40% completeness, 30% pattern, 30% consistency)
- Pattern matching for 20 known incident types
- Six safety rule enforcement
- Structured diagnostic output with seven required fields
- CLI interface for local execution
- Benchmark testing harness for 25-50 cases

**Out of Scope:**
- Azure API integration or cloud connectivity
- Remediation execution or write operations
- Real-time monitoring or alerting
- Multi-VM analysis or fleet management
- Historical trend analysis or ML-based prediction


## Architecture

The system follows a pipeline architecture with a setup phase, an optional agent layer for continuous monitoring, and seven modular components for the main triage pipeline:

### Agent Layer (Optional - Continuous Monitoring)

The agent layer provides automated telemetry collection from Azure:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Telemetry Collector Agent                     │
│                  (python main.py --agent)                        │
│                                                                  │
│  Step 1: Azure Resource Graph (1 KQL query, ~200ms)             │
│  → power_state, provisioning_state, azure_vm_agent_status       │
│  → boot_diagnostics_status, boot_diagnostics_error              │
│  → resource_health_status, resource_health_annotation           │
│  → nsg_allow_rdp_3389, nsg_allow_ssh_22                         │
│                                                                  │
│  Step 2: Azure Monitor MetricsQueryClient (1 batch, ~500ms)     │
│  → cpu_percent, memory_percent, memory_available_mb             │
│  → os_disk_latency_ms, data_disk_latency_ms                     │
│  → os_disk_percent_full                                         │
│                                                                  │
│  Step 3: Azure Monitor LogsQueryClient (1 KQL query, ~300ms)    │
│  → heartbeat_present, heartbeat_last_received                   │
│  → monitor_agent_status, app_health_status, app_error_message   │
│                                                                  │
│  Step 4: Auto-calculate data_completeness_percent + missing_signals│
└──────────────────────────┬──────────────────────────────────────┘
                           │ TelemetryInput JSON
                           ▼
```

### Setup Phase

Before the main triage pipeline can run, a setup phase generates required configuration files:

```
┌─────────────────────────────────────────────────────────────────┐
│                         Setup Phase                              │
│                  (python main.py --setup)                        │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  setup/generate_schema.py                                 │  │
│  │  → schemas/azure_vm_triage_schema.json                    │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  setup/generate_output_schema.py                          │  │
│  │  → schemas/output_schema.json                             │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  setup/generate_policy.py                                 │  │
│  │  → policy/decision_policy.json                            │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  setup/generate_benchmark.py                              │  │
│  │  → data/benchmark_cases.csv (35 cases)                    │  │
│  │     - All 20 patterns                                     │  │
│  │     - 5 clean cases                                       │  │
│  │     - 5 missing-telemetry cases                           │  │
│  │     - 5 conflicting-signal cases                          │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                             │
                             ▼
                    Setup Complete
                             │
                             ▼
```

### Main Triage Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLI Interface                            │
│                  (main.py, click-based CLI)                      │
│              Accepts --input and --output flags                  │
└────────────────────────────┬────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────┐
│                      Diagnostic Output                           │
│                    (JSON with 7 fields)                          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
                    ┌──────────────────────┐
                    │   Results Sink       │
                    │  (agent mode only)   │
                    │  results/output.jsonl│
                    └──────────────────────┘

                    ┌──────────────────────┐
                    │   Benchmark Loader   │
                    │  (loads 25-50 cases) │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │    Test Harness      │
                    │  (batch processing)  │
                    └──────────────────────┘
```                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Decision Engine                             │
│    Applies rules A, B, C + 6 safety rules + 20 pattern matchers  │
│    Returns: diagnose | diagnose_low_confidence | abstain         │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Explanation Formatter                          │
│         Generates structured output with 7 required fields       │
│         Formats evidence, gaps, and next_check                   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Diagnostic Output                           │
│                    (JSON with 7 fields)                          │
└─────────────────────────────────────────────────────────────────┘

                    ┌──────────────────────┐
                    │   Benchmark Loader   │
                    │  (loads 25-50 cases) │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │    Test Harness      │
                    │  (batch processing)  │
                    └──────────────────────┘
```

### Setup Phase Rules

1. **Setup must run before any triage logic**: The `--setup` command must be executed before the first triage operation
2. **Setup is idempotent**: Running setup multiple times does not overwrite existing files (checks for file existence first)
3. **Setup command**: `python main.py --setup`
4. **Generated files**:
   - `schemas/azure_vm_triage_schema.json`: Complete JSON Schema with 30+ field definitions
   - `schemas/output_schema.json`: Output schema with 7 required fields
   - `policy/decision_policy.json`: Decision policy rules (A, B, C) and 6 safety rules in JSON format
   - `data/benchmark_cases.csv`: 35 benchmark cases (20 patterns + 5 clean + 5 missing + 5 conflicting)

### Component Interaction Flow

1. **Setup Phase** (one-time): Generate schemas, policy, and benchmark data
2. **CLI Interface** receives input file path via `--input` flag and optional `--output` flag
3. **Schema Validator** parses JSON and validates all 30+ fields against triage schema with type/range constraints
4. **Confidence Scorer** calculates data completeness percentage and confidence score using weighted algorithm
5. **Decision Engine** applies decision policy rules (A, B, C), enforces 6 safety rules, matches against 20 patterns
6. **Explanation Formatter** generates structured diagnostic output with all 7 required fields
7. **Test Harness** (optional) processes 25-50 benchmark cases in batch mode for validation


## Components and Interfaces

### 0. Setup Generators

**Responsibility:** Generate required configuration files before the main pipeline can run.

**Interface:**
```python
# setup/generate_schema.py
def generate_triage_schema() -> dict:
    """
    Generates the Azure VM triage schema with 30+ field definitions.
    
    Returns:
        Dictionary representing JSON Schema with:
        - All 30+ telemetry field definitions
        - Enum constraints for 8 enum types
        - Numeric range constraints
        - Required fields: power_state, provisioning_state, resource_health_status
    """
    pass

def write_schema_file(schema: dict, output_path: str = "schemas/azure_vm_triage_schema.json"):
    """
    Writes schema to file if it doesn't already exist (idempotent).
    
    Args:
        schema: Schema dictionary
        output_path: Target file path
    """
    pass

# setup/generate_output_schema.py
def generate_output_schema() -> dict:
    """
    Generates the diagnostic output schema with 7 required fields.
    
    Returns:
        Dictionary representing JSON Schema with:
        - decision (enum: diagnose, diagnose_low_confidence, abstain_request_next_check)
        - diagnosis (string)
        - confidence_score (number, 0.0-1.0)
        - evidence (array of strings)
        - evidence_gap (array of strings)
        - next_check (string, nullable)
        - explanation (string)
    """
    pass

def write_output_schema_file(schema: dict, output_path: str = "schemas/output_schema.json"):
    """
    Writes output schema to file if it doesn't already exist (idempotent).
    
    Args:
        schema: Schema dictionary
        output_path: Target file path
    """
    pass

# setup/generate_policy.py
def generate_decision_policy() -> dict:
    """
    Generates the decision policy with rules A, B, C and 6 safety rules.
    
    Returns:
        Dictionary with:
        - rules: {A: {...}, B: {...}, C: {...}}
        - safety_rules: [{name, condition, action}, ...]
        - thresholds: {diagnose_confidence: 0.7, ...}
    """
    pass

def write_policy_file(policy: dict, output_path: str = "policy/decision_policy.json"):
    """
    Writes policy to file if it doesn't already exist (idempotent).
    
    Args:
        policy: Policy dictionary
        output_path: Target file path
    """
    pass

# setup/generate_benchmark.py
def generate_benchmark_cases() -> List[dict]:
    """
    Generates 35 benchmark cases covering:
    - 20 cases: All 20 known incident patterns (one per pattern)
    - 5 cases: Clean/healthy VM cases (no issues, all signals green)
    - 5 cases: Missing telemetry cases (low completeness < 60%)
    - 5 cases: Conflicting signal cases (minor and major conflicts)
    
    Returns:
        List of 35 benchmark case dictionaries
    """
    pass

def write_benchmark_file(cases: List[dict], output_path: str = "data/benchmark_cases.csv"):
    """
    Writes benchmark cases to CSV if it doesn't already exist (idempotent).
    
    Args:
        cases: List of benchmark case dictionaries
        output_path: Target file path
    """
    pass
```

**Setup Execution:**
- All setup scripts are invoked via `python main.py --setup`
- Each generator checks if target file exists before writing (idempotent)
- Creates directories if they don't exist (schemas/, policy/, data/)
- Logs which files were created vs skipped (already exist)

**Idempotency Rules:**
- If `schemas/azure_vm_triage_schema.json` exists → skip generation
- If `schemas/output_schema.json` exists → skip generation
- If `policy/decision_policy.json` exists → skip generation
- If `data/benchmark_cases.csv` exists → skip generation
- Log message: "File already exists, skipping: {path}"

### 1. Schema Validator

**Responsibility:** Parse JSON input and validate against the triage schema with 30+ telemetry fields.

**Interface:**
```python
class SchemaValidator:
    def validate(self, json_input: str) -> ValidationResult:
        """
        Validates JSON input against triage schema.
        
        Args:
            json_input: Raw JSON string
            
        Returns:
            ValidationResult with parsed TelemetryInput or validation errors
            
        Raises:
            JSONParseError: If JSON is malformed (includes line/column details)
            SchemaValidationError: If validation fails (includes field names and constraints)
        """
        pass
```

**Key Functions:**
- Parse JSON with detailed error reporting (line number, column number, error description)
- Validate data types for all 30+ telemetry fields
- Validate enum constraints: power_state (5 values), provisioning_state (4 values), resource_health_status (4 values), boot_diagnostics_status (5 values), azure_vm_agent_status (5 values), app_health_status (4 values), connection_troubleshoot (5 values), monitor_agent_status (5 values)
- Validate numeric ranges: percentages (0-100), latencies (>=0), memory (>=0)
- Ignore unknown fields (forward compatibility)
- Return detailed validation errors with field names, constraint violations, and actual values

**Dependencies:**
- `jsonschema` for schema validation
- `json` for parsing with error details


### 2. Confidence Scorer

**Responsibility:** Calculate data completeness percentage and confidence score using weighted algorithm.

**Interface:**
```python
class ConfidenceScorer:
    def calculate_completeness(self, telemetry: TelemetryInput) -> float:
        """
        Calculates data completeness percentage (0-100).
        
        Counts non-null optional fields and calculates percentage.
        Required fields: power_state, provisioning_state, resource_health_status
        Optional fields: All other 27+ fields
        
        Args:
            telemetry: Validated telemetry input
            
        Returns:
            Completeness percentage (0.0-100.0)
        """
        pass
    
    def calculate_confidence(self, telemetry: TelemetryInput, 
                            completeness: float,
                            pattern_match: Optional[str],
                            signal_conflicts: str) -> float:
        """
        Calculates confidence score (0.0-1.0) using weighted algorithm.
        
        Formula: (completeness_weight * 0.4) + (pattern_weight * 0.3) + (consistency_weight * 0.3)
        
        Args:
            telemetry: Validated telemetry input
            completeness: Data completeness percentage (0-100)
            pattern_match: "exact", "partial", or None
            signal_conflicts: "none", "minor", or "major"
            
        Returns:
            Confidence score (0.0-1.0)
        """
        pass
```


**Confidence Scoring Algorithm:**

The confidence score is calculated using three weighted components:

1. **Data Completeness Weight (40%)**
   - Formula: `(completeness_percent / 100.0) * 0.4`
   - 100% completeness → 0.4 contribution
   - 90% completeness → 0.36 contribution
   - 60% completeness → 0.24 contribution
   - 0% completeness → 0.0 contribution

2. **Pattern Match Weight (30%)**
   - Exact pattern match → 0.3 contribution
   - Partial pattern match → 0.15 contribution
   - No pattern match → 0.0 contribution

3. **Signal Consistency Weight (30%)**
   - No conflicts → 0.3 contribution
   - Minor conflicts (explainable) → 0.15 contribution
   - Major conflicts (unresolvable) → 0.0 contribution

**Final Formula:**
```
confidence_score = (completeness / 100.0 * 0.4) + 
                   (pattern_match_weight * 0.3) + 
                   (signal_consistency_weight * 0.3)
```

**Signal Conflict Detection:**

Minor conflicts (explainable):
- power_state=Running + heartbeat_present=false (VM running but agent not reporting)
- nsg_allow_rdp_3389=false + connection_troubleshoot_rdp=Allow (NSG vs troubleshoot mismatch)

Major conflicts (unresolvable):
- power_state=Running + resource_health_status=Unavailable + all metrics normal
- power_state=Stopped + cpu_percent=95 (stopped VM with high CPU)


### 3. Decision Engine

**Responsibility:** Apply decision policy rules, safety rules, and pattern matching to determine final decision state.

**Interface:**
```python
class DecisionEngine:
    def decide(self, telemetry: TelemetryInput, 
               confidence_score: float,
               completeness: float) -> Decision:
        """
        Applies decision policy to return one of three states.
        
        Evaluation order:
        1. Safety rule checks (highest priority)
        2. Data completeness checks
        3. Signal conflict checks
        4. Pattern matching (20 patterns)
        5. Decision selection (rules A, B, C)
        
        Args:
            telemetry: Validated telemetry input
            confidence_score: Calculated confidence score (0.0-1.0)
            completeness: Data completeness percentage (0-100)
            
        Returns:
            Decision object with state, diagnosis, evidence, gaps, next_check
        """
        pass
```


**Decision Policy Rules:**

Decision is driven by confidence_score (not raw completeness):

**Rule A: diagnose**
- Confidence score ≥ 0.70
- Data completeness ≥ 90%
- No conflicting signals (or conflicts fully explained)
- Root cause maps to one known incident pattern
- Remediation is safe and reversible (if suggested)
- No safety rule violations

**Rule B: diagnose_low_confidence**
- Confidence score ≥ 0.40 and < 0.70
- Data completeness 60-89%
- Minor signal conflicts that can be partially explained
- Root cause is probable but not certain
- No safety rule violations

**Rule C: abstain_request_next_check**
- Confidence score < 0.40, OR
- Data completeness < 60%, OR
- Critical signals missing or unknown (power_state, provisioning_state, resource_health_status), OR
- Severe unresolvable signal conflict, OR
- Platform-initiated event detected (resource_health_annotation contains keywords), OR
- Any safety rule violation detected


**Safety Rules (Hard Constraints):**

1. **Platform Event Safety:**
   - IF resource_health_annotation contains platform event keywords ("platform", "maintenance", "host update", "planned maintenance") → abstain_request_next_check
   - Never suggest VM restart in next_check during platform events

2. **Boot Failure Safety:**
   - IF boot_diagnostics_status = BSOD → Never suggest restart in next_check
   - IF boot_diagnostics_status = KernelPanic → Never suggest restart in next_check
   - These indicate OS-level failures requiring investigation, not restart

3. **Low Confidence Destructive Action Safety:**
   - IF confidence_score < 0.9 AND diagnosis suggests destructive actions → Remove destructive actions from next_check
   - Destructive actions: disk deletion, OS reset, VM deletion, configuration reset

4. **Network Security Safety:**
   - Never suggest disabling NSG rules in next_check
   - Never suggest disabling firewall rules in next_check
   - Network security changes require manual review

5. **Disk Safety:**
   - IF confidence_score < 0.9 → Never suggest disk deletion in next_check
   - IF confidence_score < 0.9 → Never suggest OS reset in next_check
   - Data integrity requires high confidence

6. **Failed State Safety:**
   - IF power_state = Failed AND provisioning_state = Failed → Never suggest auto-remediation in next_check
   - Failed states require manual investigation and Azure support


**Pattern Matching (20 Known Incident Patterns):**

1. **VM Stopped by User**: power_state=Stopped, provisioning_state=Succeeded
2. **NSG Blocks RDP**: nsg_allow_rdp_3389=false, connection_troubleshoot_rdp=Deny
3. **NSG Blocks SSH**: nsg_allow_ssh_22=false, connection_troubleshoot_ssh=Deny
4. **High CPU Saturation**: cpu_percent > 95
5. **OS Disk Full**: os_disk_percent_full > 95
6. **Memory Exhaustion**: memory_percent > 95
7. **Boot BSOD**: boot_diagnostics_status=BSOD
8. **Boot Kernel Panic**: boot_diagnostics_status=KernelPanic
9. **VM Running No Heartbeat**: power_state=Running, heartbeat_present=false
10. **Resource Health Unavailable**: resource_health_status=Unavailable, cpu_percent and memory_percent normal
11. **Conflicting NSG Signals**: nsg_allow_rdp_3389=false, connection_troubleshoot_rdp=Allow
12. **App Unhealthy VM Healthy**: app_health_status=Unhealthy, azure_vm_agent_status=Healthy
13. **Disk IO Saturation**: os_disk_latency_ms > 100 OR data_disk_latency_ms > 100
14. **VM Deallocated**: power_state=Deallocated
15. **Provisioning Failed**: provisioning_state=Failed
16. **Failed State Insufficient Data**: power_state=Failed, data_completeness < 30%
17. **Platform Degradation**: resource_health_annotation contains platform degradation keywords
18. **Boot Stuck**: boot_diagnostics_status=Stuck
19. **VM Agent Failed**: azure_vm_agent_status=Failed
20. **Monitor Agent Failed**: monitor_agent_status=Failed

Each pattern includes:
- Matching conditions (telemetry field values)
- Diagnosis text
- Evidence list (supporting signals)
- Suggested next_check (if applicable)


### 4. Explanation Formatter

**Responsibility:** Generate human-readable explanations and format structured output with 7 required fields.

**Interface:**
```python
class ExplanationFormatter:
    def format_output(self, decision: Decision, 
                     telemetry: TelemetryInput,
                     confidence_score: float) -> DiagnosticOutput:
        """
        Formats decision into structured diagnostic output.
        
        Args:
            decision: Decision from decision engine
            telemetry: Original telemetry input
            confidence_score: Calculated confidence score
            
        Returns:
            DiagnosticOutput with all 7 required fields:
            - decision: diagnose | diagnose_low_confidence | abstain_request_next_check
            - diagnosis: Human-readable description
            - confidence_score: Float 0.0-1.0
            - evidence: List of supporting signals
            - evidence_gap: List of missing/incomplete signals
            - next_check: Specific diagnostic action (required for abstain)
            - explanation: Reasoning for the decision
        """
        pass
```

**Output Field Generation:**
- `decision`: One of three enum values
- `diagnosis`: Pattern-based or generic description
- `confidence_score`: From confidence scorer
- `evidence`: List of telemetry fields that support diagnosis (e.g., ["power_state=Stopped", "provisioning_state=Succeeded"])
- `evidence_gap`: List of missing fields (e.g., ["heartbeat_last_received", "boot_diagnostics_status"])
- `next_check`: Specific action (e.g., "Check boot diagnostics logs", "Verify NSG rules for port 3389")
- `explanation`: Multi-sentence reasoning (e.g., "VM is stopped with successful provisioning. This indicates user-initiated deallocation. No remediation needed.")


### 5. CLI Interface

**Responsibility:** Provide command-line interface for local execution without Azure connectivity.

**Interface:**
```python
@click.command()
@click.option('--setup', is_flag=True,
              help='Run setup to generate schemas, policy, and benchmark data')
@click.option('--input', type=click.Path(exists=True), 
              help='Path to input JSON file containing telemetry')
@click.option('--output', type=click.Path(), 
              help='Path to output JSON file (default: stdout)')
@click.option('--benchmark', type=click.Path(exists=True),
              help='Path to benchmark cases file for batch processing')
def main(setup: bool, input: Optional[str], output: Optional[str], benchmark: Optional[str]):
    """
    Azure VM Incident Copilot CLI.
    
    Processes Azure VM telemetry and returns diagnostic output.
    Runs entirely locally without Azure connectivity.
    
    Setup mode: python main.py --setup
    Triage mode: python main.py --input incident.json
    Benchmark mode: python main.py --benchmark data/benchmark_cases.csv
    """
    pass
```

**CLI Behavior:**

**Setup Mode (`--setup` flag):**
- Run all setup generators in sequence:
  1. `setup/generate_schema.py` → `schemas/azure_vm_triage_schema.json`
  2. `setup/generate_output_schema.py` → `schemas/output_schema.json`
  3. `setup/generate_policy.py` → `policy/decision_policy.json`
  4. `setup/generate_benchmark.py` → `data/benchmark_cases.csv`
- Create directories if they don't exist
- Skip files that already exist (idempotent)
- Log which files were created vs skipped
- Return exit code 0 on success

**Triage Mode (`--input` flag):**
- Read telemetry from `--input` file (required)
- Process through pipeline: validate → score → decide → format
- Write diagnostic output to stdout (default) or `--output` file
- Return exit code 0 on success
- Return non-zero exit codes on error:
  - 1: JSON parse error
  - 2: Schema validation error
  - 3: File not found
  - 4: File read error
  - 5: Decision engine error
  - 99: Unexpected internal error

**Benchmark Mode (`--benchmark` flag):**
- Support `--benchmark` flag for batch processing mode
- No Azure SDK dependencies or network calls


### 6. Benchmark Loader

**Responsibility:** Load and parse benchmark test cases from JSON or CSV files.

**Interface:**
```python
class BenchmarkLoader:
    def load_cases(self, benchmark_file: str) -> List[BenchmarkCase]:
        """
        Loads benchmark cases from file.
        
        Supports JSON and CSV formats.
        Validates benchmark case structure.
        
        Args:
            benchmark_file: Path to benchmark data file (.json or .csv)
            
        Returns:
            List of 25-50 benchmark cases
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format is invalid
        """
        pass
```

**Benchmark Case Structure:**
- `case_id`: Unique identifier (e.g., "001", "002")
- `case_name`: Descriptive name (e.g., "VM Stopped by User")
- `incident_pattern`: One of 20 known patterns
- `telemetry_input`: Full telemetry JSON object
- `expected_decision`: Expected decision state (diagnose | diagnose_low_confidence | abstain_request_next_check)
- `expected_diagnosis`: Expected diagnosis text (optional, for validation)
- `notes`: Additional context (optional)

**Benchmark Dataset Requirements:**
- 25-50 total cases
- Coverage of all 20 known incident patterns
- Clean cases with no issues (healthy VMs)
- Cases with missing telemetry (low completeness)
- Cases with conflicting signals
- Edge cases (boundary values, extreme conditions)


### 7. Test Harness

**Responsibility:** Batch process benchmark cases and generate test results.

**Interface:**
```python
class TestHarness:
    def run_benchmark(self, cases: List[BenchmarkCase]) -> BenchmarkResults:
        """
        Processes all benchmark cases and returns results.
        
        For each case:
        1. Extract telemetry_input
        2. Process through pipeline
        3. Compare actual vs expected decision
        4. Record pass/fail status
        
        Args:
            cases: List of 25-50 benchmark cases
            
        Returns:
            BenchmarkResults with:
            - total_cases: Total number processed
            - passed: Number of cases where actual == expected
            - failed: Number of cases where actual != expected
            - case_results: Per-case details with actual vs expected
            - summary_by_pattern: Statistics grouped by incident pattern
        """
        pass
```

**Test Harness Output:**
- Total cases processed
- Pass/fail count and percentage
- Per-case results with actual vs expected decision
- Diagnosis text comparison (optional)
- Summary statistics by incident pattern
- Execution time per case
- Overall benchmark score


### 8. Agent Configuration

**Responsibility:** Load and validate agent configuration from JSON files or environment variables.

**Interface:**
```python
class AgentConfig(BaseModel):
    """
    Configuration for TelemetryCollectorAgent.
    
    Can be loaded from:
    - JSON config file (--config agent_config.json)
    - Environment variables (AZURE_SUBSCRIPTION_ID, AZURE_RESOURCE_GROUP, etc.)
    """
    subscription_id: str
    resource_group: str
    vm_name: str
    log_analytics_workspace_id: Optional[str] = None
    app_insights_connection_string: Optional[str] = None
    interval_seconds: int = 300  # Default: 5 minutes
    output_dir: str = "results/"
    alert_on_diagnose: bool = True
    alert_on_low_confidence: bool = True
    
    @classmethod
    def from_file(cls, config_path: str) -> 'AgentConfig':
        """Load configuration from JSON file."""
        pass
    
    @classmethod
    def from_env(cls) -> 'AgentConfig':
        """Load configuration from environment variables."""
        pass
```

**Configuration Sources:**
- JSON file: `{"subscription_id": "...", "resource_group": "...", "vm_name": "..."}`
- Environment variables: `AZURE_SUBSCRIPTION_ID`, `AZURE_RESOURCE_GROUP`, `AZURE_VM_NAME`, `AZURE_WORKSPACE_ID`, `AGENT_INTERVAL_SECONDS`


### 9. Telemetry Collector Agent

**Responsibility:** Collect all 30+ telemetry fields from Azure using Resource Graph, Metrics, and Logs APIs.

**Interface:**
```python
class TelemetryCollectorAgent:
    def __init__(self, config: AgentConfig):
        """
        Initialize agent with Azure clients.
        
        Uses DefaultAzureCredential for authentication (read-only).
        """
        self.config = config
        self.credential = DefaultAzureCredential()
        self.arg_client = ResourceGraphClient(self.credential)
        self.metrics_client = MetricsQueryClient(self.credential)
        self.logs_client = LogsQueryClient(self.credential)
    
    def collect(self) -> TelemetryInput:
        """
        Runs all 3 collection steps and returns TelemetryInput.
        
        Steps:
        1. Azure Resource Graph (9 fields, ~200ms)
        2. Azure Monitor Metrics (6 fields, ~500ms)
        3. Azure Monitor Logs (5 fields, ~300ms)
        4. Auto-calculate completeness and missing signals
        
        Returns:
            TelemetryInput with all collected fields
        """
        pass
    
    def _collect_from_arg(self) -> dict:
        """
        Step 1: Single ARG KQL query for 9 fields.
        
        Collects:
        - power_state, provisioning_state, azure_vm_agent_status
        - boot_diagnostics_status, boot_diagnostics_error
        - resource_health_status, resource_health_annotation
        - nsg_allow_rdp_3389, nsg_allow_ssh_22
        
        Returns:
            Dictionary with collected fields
        """
        pass
    
    def _collect_metrics(self) -> dict:
        """
        Step 2: Azure Monitor MetricsQueryClient for 6 fields.
        
        Collects (last 5 minutes, average aggregation):
        - cpu_percent, memory_percent, memory_available_mb
        - os_disk_latency_ms, data_disk_latency_ms
        - os_disk_percent_full
        
        Returns:
            Dictionary with collected fields
        """
        pass
    
    def _collect_logs(self) -> dict:
        """
        Step 3: Azure Monitor LogsQueryClient for 5 fields.
        
        Collects (from Heartbeat table):
        - heartbeat_present, heartbeat_last_received
        - monitor_agent_status, app_health_status, app_error_message
        
        Returns:
            Dictionary with collected fields
        """
        pass
    
    def _calculate_completeness(self, telemetry: dict) -> tuple[float, list]:
        """
        Calculate data_completeness_percent and missing_signals.
        
        Args:
            telemetry: Dictionary with collected fields
        
        Returns:
            Tuple of (completeness_percent, missing_signals_list)
        """
        pass
```

**ARG KQL Query Template:**
```kql
Resources
| where type =~ 'microsoft.compute/virtualmachines'
| where name =~ '<vm_name>'
| where resourceGroup =~ '<resource_group>'
| project
    power_state = tostring(properties.extended.instanceView.powerState.code),
    prov_state = tostring(properties.extended.instanceView.statuses[0].code),
    vm_agent = tostring(properties.extended.instanceView.vmAgent.statuses[0].code),
    boot_diag = tostring(properties.extended.instanceView.bootDiagnostics.status),
    boot_error = tostring(properties.extended.instanceView.bootDiagnostics.consoleScreenshotBlobUri),
    resourceId = tolower(id)
| join kind=leftouter (
    HealthResources
    | where type =~ 'microsoft.resourcehealth/availabilitystatuses'
    | project
        resourceId = tolower(tostring(properties.targetResourceId)),
        health_status = tostring(properties.availabilityState),
        health_note = tostring(properties.summary)
) on resourceId
| join kind=leftouter (
    Resources
    | where type =~ 'microsoft.network/networksecuritygroups'
    | mv-expand rule = properties.securityRules
    | where rule.properties.destinationPortRange contains "3389" or rule.properties.destinationPortRange contains "22"
    | project
        nsg_allow_rdp = rule.properties.destinationPortRange contains "3389" and rule.properties.access =~ "Allow",
        nsg_allow_ssh = rule.properties.destinationPortRange contains "22" and rule.properties.access =~ "Allow"
) on $left.resourceId == $right.resourceId
```

**Azure Monitor Metrics List:**
- `Percentage CPU` (aggregation: average, timespan: last 5 minutes)
- `Available Memory Bytes` (aggregation: average)
- `OS Disk Read Latency` (aggregation: average)
- `OS Disk Write Latency` (aggregation: average)
- `Data Disk Read Latency` (aggregation: average)
- `Data Disk Write Latency` (aggregation: average)
- `OS Disk Used Burst BPS Credits Percentage` (aggregation: average)

**Logs KQL Query Template:**
```kql
Heartbeat
| where Computer =~ '<vm_name>'
| summarize 
    LastHeartbeat = max(TimeGenerated),
    Count = count()
| extend 
    heartbeat_present = Count > 0,
    minutes_since = datetime_diff('minute', now(), LastHeartbeat)
| join kind=leftouter (
    AppInsights
    | where Computer =~ '<vm_name>'
    | summarize 
        app_status = max(HealthStatus),
        app_error = max(ErrorMessage)
) on Computer
```


### 10. Incident Copilot Scheduler

**Responsibility:** Schedule periodic telemetry collection and triage pipeline execution.

**Interface:**
```python
class IncidentCopilotScheduler:
    def __init__(self, config: AgentConfig, collector: TelemetryCollectorAgent, pipeline: TriagePipeline):
        """
        Initialize scheduler with APScheduler.
        
        Args:
            config: Agent configuration
            collector: TelemetryCollectorAgent instance
            pipeline: Main triage pipeline (validator → scorer → engine → formatter)
        """
        self.config = config
        self.collector = collector
        self.pipeline = pipeline
        self.scheduler = BackgroundScheduler()
    
    def run(self):
        """
        Runs APScheduler with interval_seconds. Blocking call.
        
        Schedules _on_tick() to run every config.interval_seconds.
        Runs until interrupted (Ctrl+C).
        """
        pass
    
    def run_once(self) -> DiagnosticOutput:
        """
        Single collection + triage cycle. Returns DiagnosticOutput.
        
        Used for --once flag (single-run mode).
        """
        pass
    
    def _on_tick(self):
        """
        Called every interval_seconds:
        
        1. collector.collect() → TelemetryInput
        2. pipeline.run(telemetry) → DiagnosticOutput
        3. Append to results/output.jsonl
        4. Log: [timestamp] VM=<name> decision=<state> confidence=<score>
        
        Handles exceptions and logs errors without crashing scheduler.
        """
        pass
    
    def _append_result(self, output: DiagnosticOutput, cycle_duration_ms: float):
        """
        Append diagnostic output to results/output.jsonl.
        
        Format (one JSON object per line):
        {
          "timestamp": "2026-03-30T12:00:00Z",
          "vm_name": "my-vm",
          "resource_group": "my-rg",
          "cycle_duration_ms": 1240,
          "diagnostic_output": { ...DiagnosticOutput fields... }
        }
        """
        pass
```

**Output Format for results/output.jsonl:**
```json
{"timestamp": "2026-03-30T12:00:00Z", "vm_name": "my-vm", "resource_group": "my-rg", "cycle_duration_ms": 1240, "diagnostic_output": {"decision": "diagnose", "diagnosis": "VM is stopped", "confidence_score": 0.85, "evidence": ["power_state=Stopped"], "evidence_gap": [], "next_check": null, "explanation": "VM is stopped due to user deallocation"}}
{"timestamp": "2026-03-30T12:05:00Z", "vm_name": "my-vm", "resource_group": "my-rg", "cycle_duration_ms": 1180, "diagnostic_output": {"decision": "abstain_request_next_check", "diagnosis": "Insufficient data", "confidence_score": 0.35, "evidence": [], "evidence_gap": ["heartbeat_present", "cpu_percent"], "next_check": "Collect heartbeat and CPU metrics", "explanation": "Data completeness is 45%, below threshold"}}
```

**Console Log Format:**
```
[2026-03-30 12:00:00] VM=my-vm decision=diagnose confidence=0.85 duration=1240ms
[2026-03-30 12:05:00] VM=my-vm decision=abstain_request_next_check confidence=0.35 duration=1180ms
```


## Agent Layer Architecture

The agent layer sits above the main triage pipeline and provides continuous monitoring:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Telemetry Collector Agent                     │
│                  (python main.py --agent)                        │
│                                                                  │
│  Step 1: Azure Resource Graph (1 KQL query, ~200ms)             │
│  → power_state, provisioning_state, azure_vm_agent_status       │
│  → boot_diagnostics_status, boot_diagnostics_error              │
│  → resource_health_status, resource_health_annotation           │
│  → nsg_allow_rdp_3389, nsg_allow_ssh_22                         │
│                                                                  │
│  Step 2: Azure Monitor MetricsQueryClient (1 batch, ~500ms)     │
│  → cpu_percent, memory_percent, memory_available_mb             │
│  → os_disk_latency_ms, data_disk_latency_ms                     │
│  → os_disk_percent_full                                         │
│                                                                  │
│  Step 3: Azure Monitor LogsQueryClient (1 KQL query, ~300ms)    │
│  → heartbeat_present, heartbeat_last_received                   │
│  → monitor_agent_status, app_health_status, app_error_message   │
│                                                                  │
│  Step 4: Auto-calculate data_completeness_percent + missing_signals│
└──────────────────────────┬──────────────────────────────────────┘
                           │ TelemetryInput JSON
                           ▼
              [Existing Triage Pipeline]
           (Validator → Scorer → Engine → Formatter)
                           │ DiagnosticOutput JSON
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Results Sink                                │
│  Appends to results/output.jsonl (one line per cycle)           │
│  Logs decision + confidence_score to console                    │
└─────────────────────────────────────────────────────────────────┘
```

**Agent Execution Modes:**

1. **Continuous Mode** (default): `python main.py --agent --vm my-vm --rg my-rg`
   - Runs indefinitely with configurable interval (default 300 seconds)
   - Appends results to `results/output.jsonl`
   - Logs to console on every cycle

2. **Single-Run Mode**: `python main.py --agent --vm my-vm --rg my-rg --once`
   - Runs one collection + triage cycle
   - Outputs diagnostic result to stdout
   - Exits with code 0 on success

3. **Config File Mode**: `python main.py --agent --config agent_config.json`
   - Loads configuration from JSON file
   - Supports all agent settings (subscription, resource group, VM name, interval, etc.)


## Data Modelsry Collector Agent

**Responsibility:** Automatically collect Azure VM telemetry from Azure APIs on a scheduled interval and run the triage pipeline.

**Interface:**
```python
class TelemetryCollectorAgent:
    def __init__(self, config: AgentConfig):
        """
        Initialize the telemetry collector agent.
        
        Args:
            config: Agent configuration with Azure credentials, VM resource ID, and interval
        """
        pass
    
    def collect_telemetry(self, vm_resource_id

```python
from enum import Enum

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
    """Monitor agent status (5 values)"""
    HEALTHY = "Healthy"
    DEGRADED = "Degraded"
    FAILED = "Failed"
    NOT_INSTALLED = "NotInstalled"
    UNKNOWN = "Unknown"

class DecisionState(str, Enum):
    """Decision policy output (3 values)"""
    DIAGNOSE = "diagnose"
    DIAGNOSE_LOW_CONFIDENCE = "diagnose_low_confidence"
    ABSTAIN_REQUEST_NEXT_CHECK = "abstain_request_next_check"
```


### TelemetryInput Model

Complete data model with all 30+ telemetry fields:

```python
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class TelemetryInput(BaseModel):
    """
    Azure VM telemetry input with 30+ signal fields.
    
    Required fields: power_state, provisioning_state, resource_health_status
    Optional fields: All others (27+ fields)
    """
    
    # Power and provisioning (required)
    power_state: PowerState
    provisioning_state: ProvisioningState
    
    # Resource health (required status, optional annotation)
    resource_health_status: ResourceHealthStatus
    resource_health_annotation: Optional[str] = None
    
    # Heartbeat signals
    heartbeat_present: Optional[bool] = None
    heartbeat_last_received: Optional[datetime] = None
    
    # Boot diagnostics
    boot_diagnostics_status: Optional[BootDiagnosticsStatus] = None
    boot_diagnostics_error: Optional[str] = None
    
    # VM agent
    azure_vm_agent_status: Optional[AzureVMAgentStatus] = None
    
    # Performance metrics (with range constraints)
    cpu_percent: Optional[float] = Field(None, ge=0, le=100)
    memory_available_mb: Optional[float] = Field(None, ge=0)
    memory_percent: Optional[float] = Field(None, ge=0, le=100)
    os_disk_latency_ms: Optional[float] = Field(None, ge=0)
    data_disk_latency_ms: Optional[float] = Field(None, ge=0)
    os_disk_percent_full: Optional[float] = Field(None, ge=0, le=100)
    
    # Application health
    app_health_status: Optional[AppHealthStatus] = None
    app_error_message: Optional[str] = None
    
    # Network security
    nsg_allow_rdp_3389: Optional[bool] = None
    nsg_allow_ssh_22: Optional[bool] = None
    connection_troubleshoot_rdp: Optional[ConnectionTroubleshootResult] = None
    connection_troubleshoot_ssh: Optional[ConnectionTroubleshootResult] = None
    connection_troubleshoot_verdict: Optional[str] = None
    
    # Monitoring
    monitor_agent_status: Optional[MonitorAgentStatus] = None
    
    # Data quality metadata
    data_completeness_percent: Optional[float] = Field(None, ge=0, le=100)
    missing_signals: Optional[List[str]] = None
    
    class Config:
        # Allow extra fields for forward compatibility
        extra = "ignore"
```


### DiagnosticOutput Model

Complete output model with all 7 required fields:

```python
class DiagnosticOutput(BaseModel):
    """
    Structured diagnostic output with 7 required fields.
    """
    decision: DecisionState
    diagnosis: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    evidence: List[str]
    evidence_gap: List[str]
    next_check: Optional[str] = None
    explanation: str
    
    @model_validator(mode='after')
    def validate_next_check(self):
        """Ensure next_check is populated when decision is abstain_request_next_check."""
        if self.decision == DecisionState.ABSTAIN_REQUEST_NEXT_CHECK:
            if not self.next_check or self.next_check.strip() == "":
                raise ValueError("next_check must be populated when decision is abstain_request_next_check")
        return self
```

### ValidationResult Model

```python
class ValidationError(BaseModel):
    """Single validation error with field details."""
    field: str
    message: str
    constraint: str
    actual_value: Optional[str] = None

class ValidationResult(BaseModel):
    """Result of schema validation."""
    valid: bool
    telemetry: Optional[TelemetryInput] = None
    errors: List[ValidationError] = []
```

### Decision Model

```python
class Decision(BaseModel):
    """Internal decision model from decision engine."""
    state: DecisionState
    diagnosis: str
    pattern_matched: Optional[str] = None
    evidence: List[str]
    evidence_gap: List[str]
    next_check: Optional[str] = None
    reasoning: str
```


### BenchmarkCase Model

```python
class BenchmarkCase(BaseModel):
    """Single benchmark test case."""
    case_id: str
    case_name: str
    incident_pattern: str  # One of 20 known patterns
    telemetry_input: dict  # Full telemetry JSON
    expected_decision: DecisionState
    expected_diagnosis: Optional[str] = None
    notes: Optional[str] = None
```

### BenchmarkResults Model

```python
class CaseResult(BaseModel):
    """Result for single benchmark case."""
    case_id: str
    case_name: str
    passed: bool
    expected_decision: DecisionState
    actual_decision: DecisionState
    expected_diagnosis: Optional[str] = None
    actual_diagnosis: str
    confidence_score: float
    execution_time_ms: float
    notes: Optional[str] = None

class PatternSummary(BaseModel):
    """Summary statistics for one incident pattern."""
    pattern_name: str
    total_cases: int
    passed: int
    failed: int
    pass_rate: float

class BenchmarkResults(BaseModel):
    """Complete benchmark test results."""
    total_cases: int
    passed: int
    failed: int
    pass_rate: float
    total_execution_time_ms: float
    case_results: List[CaseResult]
    summary_by_pattern: List[PatternSummary]
```


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property Reflection

After analyzing all acceptance criteria, the following redundancies were identified and consolidated:

- Criteria 1.3-1.28 (individual field acceptance) → Combined into Property 1 (schema validation)
- Criteria 2.8 and 2.9 (enum/numeric validation) → Combined into Property 2 (validation error reporting)
- Criteria 4.2-4.8 (individual output fields) → Combined into Property 8 (output structure completeness)
- Criteria 6.2 duplicates 3.7 → Removed duplicate
- Criteria 6.3 and 6.4 (BSOD/KernelPanic) → Combined into Property 11 (boot failure safety)
- Criteria 7.3 and 7.4 (disk/OS reset) → Combined into Property 12 (destructive action safety)
- Safety rules 7.1 and 7.2 → Combined into Property 13 (network security safety)

This consolidation reduces 60+ criteria to 20 unique, non-redundant properties.


### Property 1: Schema Validation Accepts All Valid Fields

*For any* valid telemetry input containing any combination of the 30+ defined telemetry fields with valid enum values and numeric ranges, the schema validator should successfully parse and validate the input.

**Validates: Requirements 1.1, 1.3-1.28, 2.1, 2.3**

### Property 2: Schema Validation Reports Detailed Errors

*For any* telemetry input with invalid enum values or out-of-range numeric values, the schema validator should return validation errors that include field names, constraint violations, and actual values.

**Validates: Requirements 2.2, 2.8, 2.9**

### Property 3: Malformed JSON Error Reporting

*For any* malformed JSON input, the system should return a parsing error that includes line number and column number details.

**Validates: Requirements 1.2**

### Property 4: Unknown Fields Ignored

*For any* valid telemetry input with additional unknown fields not in the schema, the system should ignore the unknown fields and successfully process the input.

**Validates: Requirements 2.7**

### Property 5: Decision Determinism

*For any* valid telemetry input, processing the same input multiple times should produce identical diagnostic output with the same decision, diagnosis, and confidence score.

**Validates: Requirements 3.8**


### Property 6: Exactly One Decision

*For any* valid telemetry input that is successfully processed, the diagnostic output should contain exactly one decision value from the set {diagnose, diagnose_low_confidence, abstain_request_next_check}.

**Validates: Requirements 3.1**

### Property 7: Low Completeness Triggers Abstain

*For any* valid telemetry input where data_completeness_percent is less than 60%, the decision should be abstain_request_next_check.

**Validates: Requirements 3.4**

### Property 8: Output Structure Completeness

*For any* valid telemetry input that is successfully processed, the diagnostic output should contain all 7 required fields: decision, diagnosis, confidence_score, evidence, evidence_gap, next_check, and explanation.

**Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8**

### Property 9: Abstain Populates Next Check

*For any* valid telemetry input where the decision is abstain_request_next_check, the next_check field must be a non-null, non-empty string — this is enforced at model level.

**Validates: Requirements 4.9**

### Property 10: Diagnose Requires High Confidence

*For any* valid telemetry input where the decision is diagnose, the confidence_score should be greater than or equal to 0.70.

**Validates: Requirements 4.10**


### Property 11: Boot Failure Safety

*For any* valid telemetry input where boot_diagnostics_status is BSOD or KernelPanic, the next_check field should not contain the word "restart" (case-insensitive).

**Validates: Requirements 6.3, 6.4**

### Property 12: Low Confidence Destructive Action Safety

*For any* valid telemetry input where confidence_score is less than 0.9, the next_check field should not contain destructive action keywords: "delete", "reset", "remove", "destroy", "wipe" (case-insensitive).

**Validates: Requirements 6.5, 7.3, 7.4**

### Property 13: Network Security Safety

*For any* valid telemetry input, the next_check field should never contain phrases suggesting disabling security: "disable NSG", "disable firewall", "remove NSG rule", "remove firewall rule" (case-insensitive).

**Validates: Requirements 7.1, 7.2**

### Property 14: Platform Event Triggers Abstain

*For any* valid telemetry input where resource_health_annotation contains platform event keywords ("platform", "maintenance", "host update", "planned maintenance"), the decision should be abstain_request_next_check and next_check should not suggest restart.

**Validates: Requirements 3.7, 6.1, 6.2**

### Property 15: Failed State Safety

*For any* valid telemetry input where power_state is Failed and provisioning_state is Failed, the next_check field should not contain "auto-remediation" or "automatic remediation" (case-insensitive).

**Validates: Requirements 7.5**


### Property 16: Missing Critical Signals Trigger Abstain

*For any* valid telemetry input where any critical signal (power_state, provisioning_state, or resource_health_status) is Unknown, the decision should be abstain_request_next_check.

**Validates: Requirements 3.5**

### Property 17: Telemetry Round-Trip Integrity

*For any* valid telemetry input, parsing the JSON, converting to TelemetryInput model, serializing back to JSON, and parsing again should produce an equivalent TelemetryInput object with all field values preserved.

**Validates: Requirements 12.1, 12.3**

### Property 18: Output is Valid JSON

*For any* valid telemetry input that is successfully processed, the diagnostic output should be valid JSON that can be parsed without errors and conforms to the output schema.

**Validates: Requirements 4.1, 12.2**

### Property 19: Benchmark Case Processing

*For any* valid benchmark case with properly formatted telemetry_input, the system should return a diagnostic output without raising exceptions.

**Validates: Requirements 9.1, 9.2**

### Property 20: CLI Error Exit Codes

*For any* CLI execution that encounters an error (malformed JSON, invalid file path, schema validation failure), the system should return a non-zero exit code.

**Validates: Requirements 10.6**


## Error Handling

### Input Validation Errors

**Malformed JSON:**
- Error type: `JSONParseError`
- Error message: Include line number, column number, and description
- Exit code: 1
- Example:
```json
{
  "error": "JSONParseError",
  "message": "Invalid JSON syntax at line 5, column 12: Expected ',' or '}' after property value"
}
```

**Schema Validation Errors:**
- Error type: `SchemaValidationError`
- Error message: Include field name, constraint violation, and actual value
- Exit code: 2
- Example:
```json
{
  "error": "SchemaValidationError",
  "message": "Validation failed for 2 field(s)",
  "details": [
    {
      "field": "cpu_percent",
      "constraint": "value must be between 0 and 100",
      "actual_value": "150.5"
    },
    {
      "field": "power_state",
      "constraint": "value must be one of: Running, Stopped, Deallocated, Failed, Unknown",
      "actual_value": "InvalidState"
    }
  ]
}
```


### File I/O Errors

**File Not Found:**
- Error type: `FileNotFoundError`
- Error message: Include file path
- Exit code: 3
- Example: `File not found: /path/to/incident.json`

**File Read Error:**
- Error type: `FileReadError`
- Error message: Include file path and OS error details
- Exit code: 4
- Example: `Failed to read file /path/to/incident.json: Permission denied`

### Internal Errors

**Decision Engine Error:**
- Error type: `DecisionEngineError`
- Error message: Include context about the failure
- Exit code: 5
- Example: `Decision engine failed: Unable to match any incident pattern`

**Unexpected Error:**
- Error type: `InternalError`
- Error message: Include stack trace in debug mode
- Exit code: 99
- Example: `Unexpected internal error: <exception details>`

### Error Handling Principles

1. **Fail Fast**: Validate input before processing (schema validation before decision logic)
2. **Clear Messages**: Provide actionable error messages with specific field names and constraints
3. **No Silent Failures**: Always report errors explicitly with appropriate exit codes
4. **Graceful Degradation**: Return low confidence diagnosis when data is incomplete rather than failing
5. **Structured Errors**: Return errors in JSON format matching the output schema structure
6. **Logging**: Log all errors with timestamps, context, and stack traces for debugging


## Testing Strategy

### Dual Testing Approach

The system will be tested using both unit tests and property-based tests to ensure comprehensive coverage:

**Unit Tests:**
- Specific examples of each of the 20 known incident patterns
- Edge cases (empty input, missing fields, boundary values like cpu_percent=95.0, os_disk_percent_full=100.0)
- Error conditions (malformed JSON, invalid enums, out-of-range values)
- CLI interface behavior (file I/O, exit codes, stdout vs file output)
- Integration between components (validator → scorer → engine → formatter)
- Safety rule enforcement for specific scenarios

**Property-Based Tests:**
- Universal properties that hold for all inputs (20 properties defined above)
- Comprehensive input coverage through randomization (100+ iterations per property)
- Shrinking to find minimal failing examples
- Each test tagged with reference to design property

**Balance:** Unit tests provide concrete examples and catch specific bugs. Property tests verify general correctness across all inputs. Together they provide comprehensive coverage without redundancy.


### Property-Based Testing Configuration

**Library:** `hypothesis` (Python property-based testing library)

**Configuration:**
- Minimum 100 iterations per property test (configured via `@settings(max_examples=100)`)
- Deterministic seed for reproducibility in CI/CD
- Shrinking enabled to find minimal failing examples
- Deadline of 1000ms per test case to catch performance issues

**Test Tagging Format:**

Each property-based test must include a comment tag referencing the design property:

```python
# Feature: azure-vm-incident-copilot, Property 1: Schema Validation Accepts All Valid Fields
@given(telemetry=valid_telemetry_strategy())
@settings(max_examples=100)
def test_schema_validation_accepts_valid_fields(telemetry):
    """Property 1: For any valid telemetry input, schema validation should succeed."""
    result = validator.validate(json.dumps(telemetry))
    assert result.valid is True
    assert result.telemetry is not None
```

**Hypothesis Strategies:**

Custom strategies for generating test data:
- `valid_telemetry_strategy()`: Generates valid telemetry with random field combinations
- `invalid_enum_strategy()`: Generates telemetry with invalid enum values
- `out_of_range_numeric_strategy()`: Generates telemetry with out-of-range numbers
- `low_completeness_strategy()`: Generates telemetry with <60% completeness
- `platform_event_strategy()`: Generates telemetry with platform event annotations
- `boot_failure_strategy()`: Generates telemetry with BSOD/KernelPanic status


### Test Organization

```
tests/
├── unit/
│   ├── test_schema_validator.py       # Schema validation unit tests
│   ├── test_confidence_scorer.py      # Confidence scoring unit tests
│   ├── test_decision_engine.py        # Decision engine unit tests (20 patterns)
│   ├── test_explanation_formatter.py  # Output formatting unit tests
│   ├── test_cli.py                    # CLI interface unit tests
│   └── test_benchmark_loader.py       # Benchmark loading unit tests
├── property/
│   ├── test_properties_validation.py  # Properties 1-4 (validation)
│   ├── test_properties_decision.py    # Properties 5-10 (decision logic)
│   ├── test_properties_safety.py      # Properties 11-16 (safety rules)
│   └── test_properties_integrity.py   # Properties 17-20 (data integrity)
├── integration/
│   ├── test_end_to_end.py            # Full pipeline integration tests
│   └── test_benchmark_harness.py     # Benchmark execution tests
└── fixtures/
    ├── valid_telemetry_samples.json   # 10+ valid telemetry examples
    ├── invalid_telemetry_samples.json # 10+ invalid telemetry examples
    └── benchmark_cases.json           # 25-50 benchmark cases
```


### Unit Test Coverage

**Schema Validator:**
- Valid JSON parsing for all 30+ fields
- Malformed JSON error reporting with line/column details
- Valid enum values for all 8 enum types
- Invalid enum values rejection
- Valid numeric ranges (0-100 for percentages, >=0 for latencies)
- Out-of-range numeric values rejection
- Unknown fields ignored
- Required fields missing

**Confidence Scorer:**
- Data completeness calculation (0%, 25%, 50%, 75%, 90%, 100%)
- Confidence score calculation with various combinations
- Signal consistency detection (no conflicts, minor conflicts, major conflicts)
- Pattern match weighting (exact, partial, none)

**Decision Engine:**
- Each of the 20 known incident patterns with specific examples
- Decision policy rule A (diagnose) with completeness ≥90%, confidence ≥0.7
- Decision policy rule B (diagnose_low_confidence) with completeness 60-89%, confidence 0.4-0.69
- Decision policy rule C (abstain_request_next_check) with completeness <60%
- Each of the 6 safety rules with specific violation scenarios
- Deterministic behavior (same input → same output)

**Explanation Formatter:**
- Output structure completeness (all 7 fields present)
- Evidence list generation from telemetry signals
- Evidence gap identification from missing fields
- Next check generation for abstain decisions
- Explanation text generation with reasoning

**CLI Interface:**
- Input file reading from --input flag
- Output file writing to --output flag
- Stdout output (default behavior)
- Error exit codes (1, 2, 3, 4, 5, 99)
- Missing file handling
- Benchmark mode with --benchmark flag

**Benchmark Loader:**
- JSON benchmark loading (25-50 cases)
- CSV benchmark loading (alternative format)
- Invalid benchmark format handling
- Case structure validation


### Property-Based Test Coverage

Each of the 20 correctness properties will have a corresponding property-based test with 100+ iterations:

1. **Property 1**: Schema validation accepts all valid field combinations
2. **Property 2**: Schema validation reports detailed errors for invalid inputs
3. **Property 3**: Malformed JSON produces line/column error details
4. **Property 4**: Unknown fields are ignored during processing
5. **Property 5**: Identical inputs produce identical outputs (determinism)
6. **Property 6**: Output always contains exactly one decision value
7. **Property 7**: Completeness <60% always triggers abstain
8. **Property 8**: Output always contains all 7 required fields
9. **Property 9**: Abstain decisions always populate next_check
10. **Property 10**: Diagnose decisions always have confidence ≥0.7
11. **Property 11**: BSOD/KernelPanic never suggests restart
12. **Property 12**: Low confidence (<0.9) never suggests destructive actions
13. **Property 13**: Never suggests disabling NSG/firewall
14. **Property 14**: Platform events trigger abstain and no restart
15. **Property 15**: Failed states never suggest auto-remediation
16. **Property 16**: Unknown critical signals trigger abstain
17. **Property 17**: Parse-serialize-parse preserves data (round-trip)
18. **Property 18**: Output is always valid JSON
19. **Property 19**: Benchmark cases process without exceptions
20. **Property 20**: Errors produce non-zero exit codes


### Benchmark Testing

**Benchmark Dataset Structure:**
- 25-50 test cases covering all 20 incident patterns
- Clean cases (no issues detected, healthy VMs)
- Cases with missing telemetry (low completeness scenarios)
- Cases with conflicting signals (minor and major conflicts)
- Edge cases (boundary values: cpu_percent=95.0, os_disk_percent_full=100.0, memory_percent=95.0)

**Benchmark Execution:**
```bash
# Run benchmark with default cases
python main.py --benchmark data/benchmark_cases.csv --output benchmark_results.json

# Run benchmark with custom cases
python main.py --benchmark custom_cases.json --output custom_results.json
```

**Success Criteria:**
- 100% of cases process without errors (no exceptions)
- 95%+ accuracy on expected decision states
- 90%+ accuracy on expected diagnosis text (fuzzy match)
- Average execution time <100ms per case

**Benchmark Results Format:**
```json
{
  "total_cases": 50,
  "passed": 48,
  "failed": 2,
  "pass_rate": 0.96,
  "total_execution_time_ms": 3250.5,
  "summary_by_pattern": [
    {
      "pattern_name": "VM Stopped by User",
      "total_cases": 3,
      "passed": 3,
      "failed": 0,
      "pass_rate": 1.0
    }
  ],
  "case_results": [...]
}
```


### Test Execution

**Run all tests:**
```bash
pytest tests/ -v
```

**Run unit tests only:**
```bash
pytest tests/unit/ -v
```

**Run property tests only:**
```bash
pytest tests/property/ -v
```

**Run with coverage:**
```bash
pytest tests/ --cov=src --cov-report=html --cov-report=term
```

**Run specific property test:**
```bash
pytest tests/property/test_properties_safety.py::test_boot_failure_safety -v
```

**Target Coverage:**
- Line coverage: 90%+
- Branch coverage: 85%+
- Critical paths (decision engine, safety rules): 100%
- All 20 incident patterns: 100% coverage


## File Structure

The deliverable will have the following structure with setup generators and core files:

```
azure-vm-incident-copilot/
├── README.md                          # Project overview, usage, and examples
├── requirements.txt                   # Runtime dependencies
├── requirements-test.txt              # Test dependencies (includes -r requirements.txt)
├── main.py                           # CLI entry point with --setup flag
├── setup/
│   ├── __init__.py
│   ├── generate_schema.py            # Generates azure_vm_triage_schema.json
│   ├── generate_output_schema.py     # Generates output_schema.json
│   ├── generate_policy.py            # Generates decision_policy.json
│   └── generate_benchmark.py         # Generates benchmark_cases.csv (35 cases)
├── schemas/
│   ├── azure_vm_triage_schema.json   # Input telemetry schema (30+ fields) [GENERATED]
│   └── output_schema.json            # Diagnostic output schema (7 fields) [GENERATED]
├── policy/
│   └── decision_policy.json          # Decision rules A, B, C + 6 safety rules [GENERATED]
├── data/
│   └── benchmark_cases.csv           # 25 benchmark test cases [GENERATED]
├── src/
│   ├── __init__.py
│   ├── models.py                     # Pydantic data models (all enums and models)
│   ├── validator.py                  # Schema validation component
│   ├── benchmark_loader.py           # Benchmark data loading
│   ├── confidence_scorer.py          # Confidence scoring component
│   ├── decision_engine.py            # Decision policy and pattern matching
│   ├── explanation_formatter.py      # Output formatting component
│   └── test_harness.py               # Benchmark test execution
├── tests/
│   ├── __init__.py
│   ├── unit/
│   │   ├── test_schema_validator.py
│   │   ├── test_confidence_scorer.py
│   │   ├── test_decision_engine.py
│   │   ├── test_explanation_formatter.py
│   │   ├── test_cli.py
│   │   ├── test_benchmark_loader.py
│   │   └── test_setup_generators.py  # Tests for setup scripts
│   ├── property/
│   │   ├── test_properties_validation.py
│   │   ├── test_properties_decision.py
│   │   ├── test_properties_safety.py
│   │   └── test_properties_integrity.py
│   ├── integration/
│   │   ├── test_end_to_end.py
│   │   ├── test_benchmark_harness.py
│   │   └── test_setup_idempotency.py  # Tests setup idempotency
│   └── fixtures/
│       ├── valid_telemetry_samples.json
│       ├── invalid_telemetry_samples.json
│       └── benchmark_cases.json
└── docs/
    ├── architecture.md               # Detailed architecture documentation
    ├── decision_policy.md            # Decision policy rules A, B, C
    ├── safety_rules.md               # 6 safety rules documentation
    └── incident_patterns.md          # 20 known patterns documentation
```


### Key Files Description

**Setup Scripts:**

**0a. setup/generate_schema.py:**
Generates the complete Azure VM triage schema with:
- All 30+ field definitions with data types
- Enum constraints for 8 enum types (power_state, provisioning_state, etc.)
- Numeric range constraints (0-100 for percentages, >=0 for latencies)
- Required fields: power_state, provisioning_state, resource_health_status
- Optional fields: All other 27+ fields
- Writes to: `schemas/azure_vm_triage_schema.json`
- Idempotent: Skips if file already exists

**0b. setup/generate_output_schema.py:**
Generates the diagnostic output schema with 7 required fields:
- decision (enum: diagnose, diagnose_low_confidence, abstain_request_next_check)
- diagnosis (string)
- confidence_score (number, 0.0-1.0)
- evidence (array of strings)
- evidence_gap (array of strings)
- next_check (string, nullable)
- explanation (string)
- Writes to: `schemas/output_schema.json`
- Idempotent: Skips if file already exists

**0c. setup/generate_policy.py:**
Generates the decision policy JSON with:
- Rules A, B, C with exact thresholds
- 6 safety rules with conditions and actions
- Pattern matching configuration
- Confidence scoring weights (40% completeness, 30% pattern, 30% consistency)
- Writes to: `policy/decision_policy.json`
- Idempotent: Skips if file already exists

**0d. setup/generate_benchmark.py:**
Generates 35 benchmark test cases covering:
- 20 cases: All 20 known incident patterns (one per pattern)
- 5 cases: Clean/healthy VM cases (no issues, all signals green)
- 5 cases: Missing telemetry cases (low completeness < 60%)
- 5 cases: Conflicting signal cases (minor and major conflicts)
- CSV format with columns: case_id, case_name, incident_pattern, telemetry_input, expected_decision, expected_diagnosis, notes
- Writes to: `data/benchmark_cases.csv`
- Idempotent: Skips if file already exists

**Core Files:**

**1. schemas/azure_vm_triage_schema.json:**
Complete JSON Schema definition for telemetry input with:
- All 30+ field definitions with data types
- Enum constraints for 8 enum types (power_state, provisioning_state, etc.)
- Numeric range constraints (0-100 for percentages, >=0 for latencies)
- Required fields: power_state, provisioning_state, resource_health_status
- Optional fields: All other 27+ fields
- Example:
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["power_state", "provisioning_state", "resource_health_status"],
  "properties": {
    "power_state": {
      "type": "string",
      "enum": ["Running", "Stopped", "Deallocated", "Failed", "Unknown"]
    },
    "cpu_percent": {
      "type": "number",
      "minimum": 0,
      "maximum": 100
    }
  }
}
```

**2. schemas/output_schema.json:**
JSON Schema definition for diagnostic output with 7 required fields:
- decision (enum: diagnose, diagnose_low_confidence, abstain_request_next_check)
- diagnosis (string)
- confidence_score (number, 0.0-1.0)
- evidence (array of strings)
- evidence_gap (array of strings)
- next_check (string, nullable)
- explanation (string)

**3. policy/decision_policy.json:**
Decision policy configuration in JSON format:
- Rules A, B, C with thresholds
- 6 safety rules with conditions
- Pattern matching rules for 20 patterns
- Confidence scoring algorithm parameters

**4. data/benchmark_cases.csv:**
25 benchmark test cases in CSV format with columns:
- case_id: Unique identifier (001, 002, ...)
- case_name: Descriptive name
- incident_pattern: One of 20 known patterns
- telemetry_input: JSON string with full telemetry
- expected_decision: Expected decision state
- expected_diagnosis: Expected diagnosis text (optional)
- notes: Additional context (optional)

Example rows:
```csv
case_id,case_name,incident_pattern,telemetry_input,expected_decision,expected_diagnosis,notes
001,VM Stopped by User,vm_stopped_by_user,"{""power_state"":""Stopped"",""provisioning_state"":""Succeeded""}",diagnose,VM is stopped due to user deallocation,Clean case
002,NSG Blocks RDP,nsg_blocks_rdp,"{""power_state"":""Running"",""nsg_allow_rdp_3389"":false,""connection_troubleshoot_rdp"":""Deny""}",diagnose,RDP connection blocked by NSG rule,Network issue
```

**5. src/models.py:**
All Pydantic models and enums:
- 8 enum classes (PowerState, ProvisioningState, ResourceHealthStatus, BootDiagnosticsStatus, AzureVMAgentStatus, AppHealthStatus, ConnectionTroubleshootResult, MonitorAgentStatus, DecisionState)
- TelemetryInput model with 30+ fields
- DiagnosticOutput model with 7 fields
- ValidationResult, ValidationError models
- Decision model (internal)
- BenchmarkCase, CaseResult, BenchmarkResults models


**6. src/validator.py:**
Schema validation component:
- `SchemaValidator` class with `validate(json_input: str) -> ValidationResult` method
- JSON parsing with detailed error reporting (line/column)
- Schema validation using jsonschema library
- Enum constraint validation
- Numeric range validation
- Unknown field handling (ignore)
- Detailed error messages with field names and constraints

**7. src/benchmark_loader.py:**
Benchmark data loading component:
- `BenchmarkLoader` class with `load_cases(benchmark_file: str) -> List[BenchmarkCase]` method
- Support for JSON and CSV formats
- Case structure validation
- Error handling for invalid formats

**8. src/confidence_scorer.py:**
Confidence scoring component:
- `ConfidenceScorer` class with two methods:
  - `calculate_completeness(telemetry: TelemetryInput) -> float`: Returns 0-100%
  - `calculate_confidence(telemetry, completeness, pattern_match, signal_conflicts) -> float`: Returns 0.0-1.0
- Implements weighted algorithm: 40% completeness + 30% pattern + 30% consistency
- Signal conflict detection (minor vs major)
- Pattern match weighting (exact vs partial)


**9. src/decision_engine.py:**
Decision policy and pattern matching component:
- `DecisionEngine` class with `decide(telemetry, confidence_score, completeness) -> Decision` method
- Implements decision policy rules A, B, C with exact thresholds
- Enforces 6 safety rules (platform event, boot failure, low confidence destructive, network security, disk, failed state)
- Matches against 20 known incident patterns with specific conditions
- Evidence and gap identification
- Next check generation
- Deterministic evaluation order:
  1. Safety rule checks (highest priority)
  2. Data completeness checks
  3. Signal conflict checks
  4. Pattern matching
  5. Decision selection

**10. src/explanation_formatter.py:**
Output formatting component:
- `ExplanationFormatter` class with `format_output(decision, telemetry, confidence_score) -> DiagnosticOutput` method
- Generates all 7 required output fields
- Formats evidence list from telemetry signals
- Identifies evidence gaps from missing fields
- Generates human-readable explanation text
- Ensures next_check is populated for abstain decisions


**11. src/test_harness.py:**
Benchmark test execution component:
- `TestHarness` class with `run_benchmark(cases: List[BenchmarkCase]) -> BenchmarkResults` method
- Batch processes all benchmark cases
- Compares actual vs expected decision for each case
- Records pass/fail status
- Calculates summary statistics by incident pattern
- Measures execution time per case
- Generates comprehensive benchmark results

**12. main.py:**
CLI entry point using click:
- Supports `--setup` flag to run all setup generators
- Orchestrates the pipeline: validate → score → decide → format
- Handles file I/O (--input, --output flags)
- Supports benchmark mode (--benchmark flag)
- Error handling with appropriate exit codes (0, 1, 2, 3, 4, 5, 99)
- No Azure connectivity required
- Example usage:
```bash
# Setup (first time)
python main.py --setup

# Single case processing
python main.py --input incident.json --output result.json

# Benchmark processing
python main.py --benchmark data/benchmark_cases.csv --output benchmark_results.json
```


**13. tests/test_decision_engine.py:**
Unit tests for decision engine:
- Test each of the 20 known incident patterns with specific examples
- Test decision policy rules A, B, C with boundary conditions
- Test each of the 6 safety rules with violation scenarios
- Test deterministic behavior (same input → same output)
- Test evidence and gap identification
- Test next check generation
- Example test:
```python
def test_vm_stopped_by_user_pattern():
    """Test pattern 1: VM Stopped by User"""
    telemetry = TelemetryInput(
        power_state=PowerState.STOPPED,
        provisioning_state=ProvisioningState.SUCCEEDED,
        resource_health_status=ResourceHealthStatus.AVAILABLE,
        data_completeness_percent=95.0
    )
    decision = engine.decide(telemetry, confidence_score=0.85, completeness=95.0)
    assert decision.state == DecisionState.DIAGNOSE
    assert "stopped" in decision.diagnosis.lower()
    assert "user" in decision.diagnosis.lower()
```


**13. requirements.txt:**
Runtime dependencies with version constraints:
```
jsonschema>=4.17.0,<5.0.0
pydantic>=2.0.0,<3.0.0
pandas>=2.0.0,<3.0.0
click>=8.1.0,<9.0.0
```

**14. requirements-test.txt:**
Test dependencies with version constraints:
```
pytest>=7.4.0,<8.0.0
hypothesis>=6.82.0,<7.0.0
pytest-cov>=4.1.0,<5.0.0
-r requirements.txt
```

Dependencies rationale:
- `jsonschema`: Schema validation for 30+ telemetry fields
- `pydantic`: Data structure modeling with validation
- `pandas`: Benchmark data processing (CSV/JSON)
- `click`: CLI argument parsing
- `hypothesis`: Property-based testing (100+ iterations per property)
- `pytest`: Test framework
- `pytest-cov`: Code coverage reporting


## Implementation Notes

### Decision Policy Implementation

The decision engine should implement the policy as a series of checks in strict order:

1. **Safety Rule Checks** (highest priority, evaluated first)
   - Check for platform events in resource_health_annotation → abstain
   - Check for boot failures (BSOD, KernelPanic) → abstain, remove restart from next_check
   - Check for failed state (power_state=Failed AND provisioning_state=Failed) → abstain, no auto-remediation
   - Check for low confidence + destructive actions → remove destructive actions from next_check
   - Check for NSG/firewall suggestions → never suggest disabling

2. **Data Completeness Checks**
   - If completeness < 60% → abstain
   - If critical signals missing (power_state, provisioning_state, resource_health_status are Unknown) → abstain

3. **Signal Conflict Checks**
   - If severe unresolvable conflicts detected → abstain
   - If minor explainable conflicts detected → diagnose_low_confidence

4. **Pattern Matching**
   - Match against 20 known patterns in order
   - Calculate confidence based on match quality (exact vs partial)
   - Identify evidence and gaps

5. **Decision Selection**
   - If confidence >= 0.7 AND completeness >= 90% AND no conflicts → diagnose
   - If confidence 0.4-0.69 AND completeness 60-89% AND minor conflicts → diagnose_low_confidence
   - Otherwise → abstain


### Confidence Scoring Implementation

```python
def calculate_confidence(telemetry, completeness, pattern_match, conflicts):
    """
    Calculate confidence score using weighted algorithm.
    
    Args:
        telemetry: TelemetryInput object
        completeness: Data completeness percentage (0-100)
        pattern_match: "exact", "partial", or None
        conflicts: "none", "minor", or "major"
    
    Returns:
        Confidence score (0.0-1.0)
    """
    # Completeness weight (40%)
    completeness_weight = (completeness / 100.0) * 0.4
    
    # Pattern match weight (30%)
    if pattern_match == "exact":
        pattern_weight = 0.3
    elif pattern_match == "partial":
        pattern_weight = 0.15
    else:
        pattern_weight = 0.0
    
    # Signal consistency weight (30%)
    if conflicts == "none":
        consistency_weight = 0.3
    elif conflicts == "minor":
        consistency_weight = 0.15
    else:  # major conflicts
        consistency_weight = 0.0
    
    return completeness_weight + pattern_weight + consistency_weight
```


### Pattern Matching Implementation

Each pattern should be implemented as a function that returns a match result:

```python
def match_vm_stopped_by_user(telemetry: TelemetryInput) -> Optional[PatternMatch]:
    """Pattern 1: VM Stopped by User"""
    if (telemetry.power_state == PowerState.STOPPED and 
        telemetry.provisioning_state == ProvisioningState.SUCCEEDED):
        return PatternMatch(
            pattern="VM Stopped by User",
            match_type="exact",
            diagnosis="VM is stopped due to user deallocation",
            evidence=["power_state=Stopped", "provisioning_state=Succeeded"],
            next_check="Verify if VM should be started"
        )
    return None

def match_nsg_blocks_rdp(telemetry: TelemetryInput) -> Optional[PatternMatch]:
    """Pattern 2: NSG Blocks RDP"""
    if (telemetry.nsg_allow_rdp_3389 == False and 
        telemetry.connection_troubleshoot_rdp == ConnectionTroubleshootResult.DENY):
        return PatternMatch(
            pattern="NSG Blocks RDP",
            match_type="exact",
            diagnosis="RDP connection blocked by NSG rule",
            evidence=["nsg_allow_rdp_3389=false", "connection_troubleshoot_rdp=Deny"],
            next_check="Review NSG rules for port 3389"
        )
    return None

# Implement all 20 patterns similarly...
```


### Safety Rule Implementation

Each safety rule should be implemented as a validator:

```python
def validate_no_restart_on_platform_event(telemetry: TelemetryInput, next_check: str) -> bool:
    """Safety Rule 1: Platform Event Safety"""
    if telemetry.resource_health_annotation:
        platform_keywords = ["platform", "maintenance", "host update", "planned maintenance"]
        if any(keyword in telemetry.resource_health_annotation.lower() 
               for keyword in platform_keywords):
            if "restart" in next_check.lower():
                return False  # Violation detected
    return True  # No violation

def validate_no_restart_on_boot_failure(telemetry: TelemetryInput, next_check: str) -> bool:
    """Safety Rule 2: Boot Failure Safety"""
    if telemetry.boot_diagnostics_status in [BootDiagnosticsStatus.BSOD, 
                                              BootDiagnosticsStatus.KERNEL_PANIC]:
        if "restart" in next_check.lower():
            return False  # Violation detected
    return True  # No violation

def validate_no_destructive_actions_low_confidence(confidence_score: float, next_check: str) -> bool:
    """Safety Rule 3: Low Confidence Destructive Action Safety"""
    if confidence_score < 0.9:
        destructive_keywords = ["delete", "reset", "remove", "destroy", "wipe"]
        if any(keyword in next_check.lower() for keyword in destructive_keywords):
            return False  # Violation detected
    return True  # No violation

# Implement all 6 safety rules similarly...
```


### Benchmark Case Format

Example benchmark cases in JSON format:

```json
{
  "cases": [
    {
      "case_id": "001",
      "case_name": "VM Stopped by User",
      "incident_pattern": "vm_stopped_by_user",
      "telemetry_input": {
        "power_state": "Stopped",
        "provisioning_state": "Succeeded",
        "resource_health_status": "Available",
        "data_completeness_percent": 95.0
      },
      "expected_decision": "diagnose",
      "expected_diagnosis": "VM is stopped due to user deallocation",
      "notes": "Clean case with high completeness"
    },
    {
      "case_id": "002",
      "case_name": "NSG Blocks RDP",
      "incident_pattern": "nsg_blocks_rdp",
      "telemetry_input": {
        "power_state": "Running",
        "provisioning_state": "Succeeded",
        "resource_health_status": "Available",
        "nsg_allow_rdp_3389": false,
        "connection_troubleshoot_rdp": "Deny",
        "data_completeness_percent": 90.0
      },
      "expected_decision": "diagnose",
      "expected_diagnosis": "RDP connection blocked by NSG rule",
      "notes": "Network connectivity issue"
    },
    {
      "case_id": "003",
      "case_name": "Low Completeness Abstain",
      "incident_pattern": "insufficient_data",
      "telemetry_input": {
        "power_state": "Running",
        "provisioning_state": "Succeeded",
        "resource_health_status": "Available",
        "data_completeness_percent": 45.0
      },
      "expected_decision": "abstain_request_next_check",
      "expected_diagnosis": null,
      "notes": "Insufficient data for diagnosis"
    }
  ]
}
```

This design provides a complete, modular, and testable architecture for the Azure VM Incident Copilot with comprehensive specifications for all components, data models, decision logic, safety rules, and deliverable files.

