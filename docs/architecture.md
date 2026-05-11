# Architecture Documentation: Azure VM Incident Copilot

## Overview

The Azure VM Incident Copilot is a read-only diagnostic system that automates triage for Azure VM incidents. The system accepts structured Azure VM telemetry in JSON format, validates it against a comprehensive schema with 30+ telemetry fields, applies a deterministic decision policy with three possible outcomes, and returns structured diagnostic output with diagnosis, evidence, gaps, and next steps.

### Key Design Principles

1. **Read-Only Operation**: No write operations or remediation actions are executed
2. **Deterministic Decision Logic**: Identical inputs produce identical outputs
3. **Safety-First**: Six safety rules prevent unsafe suggestions in all scenarios
4. **Modular Architecture**: Clear separation of concerns across seven components
5. **Comprehensive Validation**: 30+ telemetry fields with strict type and range constraints
6. **Local Execution**: No Azure connectivity required - runs entirely locally
7. **Testability**: Property-based testing with 100+ iterations per property

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

## High-Level Architecture

The system follows a pipeline architecture with two main phases:

1. **Setup Phase** (one-time): Generates configuration files required for operation
2. **Main Triage Pipeline**: Processes telemetry through validation → scoring → decision → formatting


## Setup Phase

Before the main triage pipeline can run, a setup phase generates required configuration files. This is a one-time operation that must be executed before the first triage.

### Setup Command

```bash
python main.py --setup
```

Or using the standalone setup runner:

```bash
python setup/run_setup.py
```

### Setup Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                         Setup Phase                              │
│                  (python main.py --setup)                        │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Step 1: setup/generate_schema.py                         │  │
│  │  → schemas/azure_vm_triage_schema.json                    │  │
│  │     - 30+ telemetry field definitions                     │  │
│  │     - 8 enum types with value constraints                 │  │
│  │     - Numeric range constraints                           │  │
│  │     - Required fields: power_state, provisioning_state,   │  │
│  │       resource_health_status                              │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Step 2: setup/generate_output_schema.py                  │  │
│  │  → schemas/output_schema.json                             │  │
│  │     - 7 required output fields                            │  │
│  │     - Decision enum (3 values)                            │  │
│  │     - Confidence score range (0.0-1.0)                    │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Step 3: setup/generate_policy.py                         │  │
│  │  → policy/decision_policy.json                            │  │
│  │     - Decision rules A, B, C with thresholds              │  │
│  │     - 6 safety rules with conditions and actions          │  │
│  │     - Confidence scoring weights                          │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Step 4: setup/generate_benchmark.py                      │  │
│  │  → data/benchmark_cases.csv (35 cases)                    │  │
│  │     - 20 cases: All 20 known patterns                     │  │
│  │     - 5 cases: Clean/healthy VMs                          │  │
│  │     - 5 cases: Missing telemetry (low completeness)       │  │
│  │     - 5 cases: Conflicting signals                        │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                             │
                             ▼
                    Setup Complete
                             │
                             ▼
              Ready for Triage Operations
```

### Setup Idempotency

The setup phase is idempotent - running it multiple times will not overwrite existing files:

- Each generator checks if the target file exists before writing
- If file exists → skip generation and log "File already exists, skipping: {path}"
- If file doesn't exist → generate and write file
- Creates directories (schemas/, policy/, data/) if they don't exist

This allows safe re-runs without losing custom modifications to generated files.


## Main Triage Pipeline

After setup is complete, the system can process telemetry through a five-step pipeline.

### Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLI Interface                            │
│                  (main.py, click-based CLI)                      │
│              Accepts --input and --output flags                  │
│                                                                  │
│              python main.py --input incident.json                │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Step 1: Schema Validator                       │
│                    (src/validator.py)                            │
│                                                                  │
│  • Parse JSON with detailed error reporting (line/column)        │
│  • Validate 30+ telemetry fields against schema                  │
│  • Check enum constraints (8 enum types)                         │
│  • Check numeric ranges (percentages 0-100, latencies ≥0)        │
│  • Ignore unknown fields (forward compatibility)                 │
│  • Return ValidationResult with TelemetryInput or errors         │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Step 2: Confidence Scorer                       │
│                 (src/confidence_scorer.py)                       │
│                                                                  │
│  • Calculate completeness (0-100%) by counting non-null fields   │
│  • Detect signal conflicts (none, minor, major)                  │
│  • Calculate confidence score using weighted algorithm:          │
│    - 40% completeness weight                                     │
│    - 30% pattern match weight                                    │
│    - 30% signal consistency weight                               │
│  • Return (completeness, confidence_score, conflicts)            │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Step 3: Decision Engine                        │
│                  (src/decision_engine.py)                        │
│                                                                  │
│  Evaluation order:                                               │
│  1. Safety rule checks (6 rules, highest priority)               │
│  2. Critical signal checks (power, provisioning, health)         │
│  3. Data completeness checks (<60% → abstain)                    │
│  4. Pattern matching (20 known incident patterns)                │
│  5. Decision selection (rules A, B, C)                           │
│                                                                  │
│  Returns: Decision with state, diagnosis, evidence, gaps,        │
│           next_check, confidence_score                           │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                 Step 4: Explanation Formatter                    │
│               (src/explanation_formatter.py)                     │
│                                                                  │
│  • Generate human-readable explanation text                      │
│  • Format evidence list from telemetry signals                   │
│  • Identify evidence gaps from missing fields                    │
│  • Add safety context if applicable                              │
│  • Ensure next_check is populated for abstain decisions          │
│  • Return DiagnosticOutput with all 7 required fields            │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Diagnostic Output                           │
│                    (JSON with 7 fields)                          │
│                                                                  │
│  • decision: diagnose | diagnose_low_confidence |                │
│              abstain_request_next_check                          │
│  • diagnosis: Human-readable description                         │
│  • confidence_score: Float 0.0-1.0                               │
│  • evidence: List of supporting signals                          │
│  • evidence_gap: List of missing signals                         │
│  • next_check: Specific diagnostic action                        │
│  • explanation: Multi-sentence reasoning                         │
└─────────────────────────────────────────────────────────────────┘
```

### Benchmark Testing Flow

For batch processing of benchmark cases:

```
┌─────────────────────────────────────────────────────────────────┐
│                   Benchmark Loader                               │
│                (src/benchmark_loader.py)                         │
│                                                                  │
│  • Load cases from CSV or JSON file                              │
│  • Validate case structure (case_id, telemetry, expected)        │
│  • Return list of BenchmarkCase objects                          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Test Harness                                │
│                  (src/test_harness.py)                           │
│                                                                  │
│  For each benchmark case:                                        │
│  1. Extract telemetry_input                                      │
│  2. Process through main pipeline (validate → score → decide)    │
│  3. Compare actual vs expected decision                          │
│  4. Record pass/fail status and execution time                   │
│                                                                  │
│  Returns: BenchmarkResults with statistics and per-case results  │
└─────────────────────────────────────────────────────────────────┘
```


## Component Details

### Component 1: Schema Validator (src/validator.py)

**Responsibility:** Parse JSON input and validate against the triage schema with 30+ telemetry fields.

**Key Classes:**
- `SchemaValidator`: Main validation class
- `JSONParseError`: Exception for malformed JSON with line/column details
- `SchemaValidationError`: Exception for schema validation failures

**Key Methods:**
```python
def validate(self, json_input: str) -> ValidationResult:
    """
    Validates JSON input against triage schema.
    
    Process:
    1. Parse JSON with detailed error reporting
    2. Validate against JSON schema (type/range/enum constraints)
    3. Parse into TelemetryInput Pydantic model
    4. Return ValidationResult
    """
```

**Validation Rules:**
- Required fields: `power_state`, `provisioning_state`, `resource_health_status`
- 8 enum types with value constraints (PowerState, ProvisioningState, etc.)
- Numeric ranges: percentages (0-100), latencies (≥0), memory (≥0)
- Unknown fields are ignored (forward compatibility)
- Detailed error reporting with field names, constraints, and actual values

**Dependencies:**
- `jsonschema` for schema validation
- `pydantic` for data modeling
- `src/models.py` for TelemetryInput model

---

### Component 2: Confidence Scorer (src/confidence_scorer.py)

**Responsibility:** Calculate data completeness percentage and confidence score using weighted algorithm.

**Key Classes:**
- `ConfidenceScorer`: Main scoring class

**Key Methods:**
```python
def calculate_completeness(self, telemetry: TelemetryInput) -> float:
    """
    Calculates data completeness percentage (0-100).
    
    Counts non-null optional fields (27+ fields).
    Required fields are not counted (always present).
    """

def calculate_confidence(
    self, telemetry: TelemetryInput,
    completeness: float,
    pattern_match: Optional[str],
    signal_conflicts: str
) -> float:
    """
    Calculates confidence score (0.0-1.0) using weighted algorithm.
    
    Formula: (completeness_weight * 0.4) + 
             (pattern_weight * 0.3) + 
             (consistency_weight * 0.3)
    """

def detect_signal_conflicts(self, telemetry: TelemetryInput) -> str:
    """
    Detects signal conflicts in telemetry data.
    
    Returns "none", "minor", or "major" based on conflict severity.
    """
```

**Confidence Scoring Algorithm:**

1. **Data Completeness Weight (40%)**
   - Formula: `(completeness_percent / 100.0) * 0.4`
   - 100% completeness → 0.4 contribution
   - 60% completeness → 0.24 contribution

2. **Pattern Match Weight (30%)**
   - Exact pattern match → 0.3 contribution
   - Partial pattern match → 0.15 contribution
   - No pattern match → 0.0 contribution

3. **Signal Consistency Weight (30%)**
   - No conflicts → 0.3 contribution
   - Minor conflicts (explainable) → 0.15 contribution
   - Major conflicts (unresolvable) → 0.0 contribution

**Signal Conflict Detection:**

Minor conflicts (explainable):
- `power_state=Running` + `heartbeat_present=false` (VM running but agent not reporting)
- `nsg_allow_rdp_3389=false` + `connection_troubleshoot_rdp=Allow` (NSG vs troubleshoot mismatch)

Major conflicts (unresolvable):
- `power_state=Running` + `resource_health_status=Unavailable` + all metrics normal
- `power_state=Stopped` + `cpu_percent > 90` (stopped VM with high CPU)

**Dependencies:**
- `src/models.py` for TelemetryInput model


---

### Component 3: Decision Engine (src/decision_engine.py)

**Responsibility:** Apply decision policy rules, safety rules, and pattern matching to determine final decision state.

**Key Classes:**
- `DecisionEngine`: Main decision logic class

**Key Methods:**
```python
def decide(
    self, telemetry: TelemetryInput,
    confidence_score: float,
    completeness: float
) -> Decision:
    """
    Applies decision policy to return one of three states.
    
    Evaluation order:
    1. Safety rule checks (highest priority)
    2. Critical signal checks
    3. Data completeness checks
    4. Pattern matching (20 patterns)
    5. Decision selection (rules A, B, C)
    """
```

**Decision Policy Rules:**

**Rule A: diagnose**
- Confidence score ≥ 0.70
- Data completeness ≥ 90%
- No conflicting signals (or conflicts fully explained)
- Root cause maps to one known incident pattern
- No safety rule violations

**Rule B: diagnose_low_confidence**
- Confidence score ≥ 0.40 and < 0.70
- Data completeness 60-89%
- Minor signal conflicts that can be partially explained
- No safety rule violations

**Rule C: abstain_request_next_check**
- Confidence score < 0.40, OR
- Data completeness < 60%, OR
- Critical signals missing or unknown, OR
- Severe unresolvable signal conflict, OR
- Platform-initiated event detected, OR
- Any safety rule violation detected

**Safety Rules (6 rules):**

1. **Platform Event Safety:** If `resource_health_annotation` contains platform event keywords → abstain, never suggest restart
2. **Boot Failure Safety:** If `boot_diagnostics_status` = BSOD or KernelPanic → never suggest restart
3. **Low Confidence Destructive Action Safety:** If confidence < 0.9 → remove destructive actions from next_check
4. **Network Security Safety:** Never suggest disabling NSG or firewall rules
5. **Disk Safety:** If confidence < 0.9 → never suggest disk deletion or OS reset
6. **Failed State Safety:** If `power_state=Failed` AND `provisioning_state=Failed` → never suggest auto-remediation

**Pattern Matching (20 known patterns):**

1. VM Stopped by User
2. NSG Blocks RDP
3. NSG Blocks SSH
4. High CPU Saturation
5. OS Disk Full
6. Memory Exhaustion
7. Boot BSOD
8. Boot Kernel Panic
9. VM Running No Heartbeat
10. Resource Health Unavailable
11. Conflicting NSG Signals
12. App Unhealthy VM Healthy
13. Disk IO Saturation
14. VM Deallocated
15. Provisioning Failed
16. Failed State Insufficient Data
17. Platform Degradation
18. Boot Stuck
19. VM Agent Failed
20. Monitor Agent Failed

Each pattern includes:
- Matching conditions (telemetry field values)
- Diagnosis text
- Evidence list (supporting signals)
- Suggested next_check (if applicable)

**Dependencies:**
- `src/models.py` for data models


---

### Component 4: Explanation Formatter (src/explanation_formatter.py)

**Responsibility:** Generate human-readable explanations and format structured output with 7 required fields.

**Key Classes:**
- `ExplanationFormatter`: Main formatting class

**Key Methods:**
```python
def format_output(
    self, decision: Decision,
    telemetry: TelemetryInput,
    confidence_score: float
) -> DiagnosticOutput:
    """
    Formats decision into structured diagnostic output.
    
    Returns DiagnosticOutput with all 7 required fields:
    - decision: diagnose | diagnose_low_confidence | abstain_request_next_check
    - diagnosis: Human-readable description
    - confidence_score: Float 0.0-1.0
    - evidence: List of supporting signals
    - evidence_gap: List of missing/incomplete signals
    - next_check: Specific diagnostic action (required for abstain)
    - explanation: Reasoning for the decision
    """
```

**Output Field Generation:**

- `decision`: One of three enum values from Decision object
- `diagnosis`: Pattern-based or generic description
- `confidence_score`: From confidence scorer
- `evidence`: List of telemetry fields that support diagnosis (e.g., `["power_state=Stopped", "provisioning_state=Succeeded"]`)
- `evidence_gap`: List of missing fields (e.g., `["heartbeat_last_received", "boot_diagnostics_status"]`)
- `next_check`: Specific action (e.g., "Check boot diagnostics logs", "Verify NSG rules for port 3389")
- `explanation`: Multi-sentence reasoning with:
  - Decision and diagnosis statement
  - Evidence summary
  - Gap summary
  - Next steps
  - Safety context (if applicable)

**Explanation Generation:**

The explanation text is structured in 5 parts:

1. **Decision Statement:** State the decision type and diagnosis with confidence score
2. **Evidence Summary:** Summarize supporting signals (first 3 + count of remaining)
3. **Gap Summary:** Summarize missing signals (first 3 + count of remaining)
4. **Next Steps:** Include next_check recommendation
5. **Safety Context:** Add safety warnings if applicable (platform events, boot failures, failed states)

**Dependencies:**
- `src/models.py` for data models

---

### Component 5: CLI Interface (main.py)

**Responsibility:** Provide command-line interface for local execution without Azure connectivity.

**Key Functions:**
```python
@click.command()
def main(ctx, setup, input_file, output_file, benchmark_file):
    """
    Azure VM Incident Copilot CLI.
    
    Modes:
    1. Setup mode (--setup): Generate configuration files
    2. Single file mode (--input): Process one telemetry file
    3. Benchmark mode (--benchmark): Process batch benchmark cases
    4. Output mode (--output): Write results to file instead of stdout
    """
```

**CLI Modes:**

**Setup Mode:**
```bash
python main.py --setup
```
- Runs all 4 setup generators in sequence
- Creates schemas/, policy/, data/ directories
- Generates all configuration files
- Logs which files were created vs skipped

**Triage Mode:**
```bash
python main.py --input incident.json
python main.py --input incident.json --output result.json
```
- Reads telemetry from input file
- Processes through pipeline: validate → score → decide → format
- Writes diagnostic output to stdout (default) or file

**Benchmark Mode:**
```bash
python main.py --benchmark data/benchmark_cases.csv
```
- Loads benchmark cases from CSV or JSON
- Processes all cases through pipeline
- Compares actual vs expected decisions
- Prints summary statistics

**Exit Codes:**
- 0: Success
- 1: JSON parse error
- 2: Schema validation error
- 3: File not found
- 4: File I/O error
- 5: Benchmark processing error
- 99: Unexpected internal error

**Dependencies:**
- `click` for CLI argument parsing
- All pipeline components (validator, scorer, engine, formatter)
- Benchmark components (loader, harness)


---

### Component 6: Benchmark Loader (src/benchmark_loader.py)

**Responsibility:** Load and parse benchmark test cases from JSON or CSV files.

**Key Classes:**
- `BenchmarkLoader`: Main loading class

**Key Methods:**
```python
def load_cases(self, benchmark_file: str) -> List[BenchmarkCase]:
    """
    Loads benchmark cases from file.
    
    Supports JSON and CSV formats.
    Validates benchmark case structure.
    
    Returns list of 25-50 benchmark cases.
    """
```

**Benchmark Case Structure:**
- `case_id`: Unique identifier (e.g., "001", "002")
- `case_name`: Descriptive name (e.g., "VM Stopped by User")
- `incident_pattern`: One of 20 known patterns
- `telemetry_input`: Full telemetry JSON object (TelemetryInput)
- `expected_decision`: Expected decision state
- `expected_diagnosis`: Expected diagnosis text (optional)
- `notes`: Additional context (optional)

**Benchmark Dataset Requirements:**
- 25-50 total cases
- Coverage of all 20 known incident patterns
- Clean cases with no issues (healthy VMs)
- Cases with missing telemetry (low completeness)
- Cases with conflicting signals
- Edge cases (boundary values, extreme conditions)

**Dependencies:**
- `pandas` for CSV loading
- `src/models.py` for BenchmarkCase model

---

### Component 7: Test Harness (src/test_harness.py)

**Responsibility:** Batch process benchmark cases and generate test results.

**Key Classes:**
- `TestHarness`: Main testing class

**Key Methods:**
```python
def run_benchmark(self, cases: List[BenchmarkCase]) -> BenchmarkResults:
    """
    Processes all benchmark cases and returns results.
    
    For each case:
    1. Extract telemetry_input
    2. Process through pipeline (validate → score → decide → format)
    3. Compare actual vs expected decision
    4. Record pass/fail status and execution time
    
    Returns BenchmarkResults with statistics and per-case details.
    """

def print_results(self, results: BenchmarkResults):
    """
    Prints formatted benchmark results to console.
    
    Includes:
    - Overall pass/fail statistics
    - Per-pattern summary
    - Failed case details
    - Execution time statistics
    """
```

**Test Harness Output:**
- Total cases processed
- Pass/fail count and percentage
- Per-case results with actual vs expected decision
- Diagnosis text comparison (optional)
- Summary statistics by incident pattern
- Execution time per case
- Overall benchmark score

**Dependencies:**
- All pipeline components (validator, scorer, engine, formatter)
- `src/models.py` for result models


## Data Models and Interfaces

### Core Enumerations (8 types)

All enum types are defined in `src/models.py`:

```python
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
    """Decision state (3 values)"""
    DIAGNOSE = "diagnose"
    DIAGNOSE_LOW_CONFIDENCE = "diagnose_low_confidence"
    ABSTAIN_REQUEST_NEXT_CHECK = "abstain_request_next_check"
```

### TelemetryInput Model

Complete input model with 30+ fields (3 required, 27+ optional):

```python
class TelemetryInput(BaseModel):
    """Azure VM telemetry input with 30+ signal fields."""
    
    # Required fields (3)
    power_state: PowerState
    provisioning_state: ProvisioningState
    resource_health_status: ResourceHealthStatus
    
    # Optional fields (27+)
    resource_health_annotation: Optional[str] = None
    heartbeat_present: Optional[bool] = None
    heartbeat_last_received: Optional[datetime] = None
    boot_diagnostics_status: Optional[BootDiagnosticsStatus] = None
    boot_diagnostics_error: Optional[str] = None
    azure_vm_agent_status: Optional[AzureVMAgentStatus] = None
    cpu_percent: Optional[float] = Field(None, ge=0, le=100)
    memory_available_mb: Optional[float] = Field(None, ge=0)
    memory_percent: Optional[float] = Field(None, ge=0, le=100)
    os_disk_latency_ms: Optional[float] = Field(None, ge=0)
    data_disk_latency_ms: Optional[float] = Field(None, ge=0)
    os_disk_percent_full: Optional[float] = Field(None, ge=0, le=100)
    app_health_status: Optional[AppHealthStatus] = None
    app_error_message: Optional[str] = None
    nsg_allow_rdp_3389: Optional[bool] = None
    nsg_allow_ssh_22: Optional[bool] = None
    connection_troubleshoot_rdp: Optional[ConnectionTroubleshootResult] = None
    connection_troubleshoot_ssh: Optional[ConnectionTroubleshootResult] = None
    connection_troubleshoot_verdict: Optional[str] = None
    monitor_agent_status: Optional[MonitorAgentStatus] = None
    data_completeness_percent: Optional[float] = Field(None, ge=0, le=100)
    missing_signals: Optional[List[str]] = None
    
    class Config:
        extra = "allow"  # Forward compatibility
```

### DiagnosticOutput Model

Complete output model with 7 required fields:

```python
class DiagnosticOutput(BaseModel):
    """Diagnostic output with 7 required fields."""
    
    decision: DecisionState
    diagnosis: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    evidence: List[str]
    evidence_gap: List[str]
    next_check: Optional[str]
    explanation: str
    
    @model_validator(mode='after')
    def validate_next_check(self):
        """Ensure next_check is populated when decision is abstain."""
        if self.decision == DecisionState.ABSTAIN_REQUEST_NEXT_CHECK:
            if not self.next_check or self.next_check.strip() == "":
                raise ValueError("next_check must be populated when decision is abstain")
        return self
```

### Internal Models

**ValidationResult:**
```python
class ValidationResult(BaseModel):
    """Result of schema validation."""
    valid: bool
    telemetry: Optional[TelemetryInput] = None
    errors: List[ValidationError] = []
```

**Decision:**
```python
class Decision(BaseModel):
    """Internal decision object from decision engine."""
    state: DecisionState
    diagnosis: str
    evidence: List[str]
    evidence_gap: List[str]
    next_check: Optional[str]
    confidence_score: float
```

**BenchmarkCase:**
```python
class BenchmarkCase(BaseModel):
    """Single benchmark test case."""
    case_id: str
    case_name: str
    incident_pattern: str
    telemetry_input: TelemetryInput
    expected_decision: DecisionState
    expected_diagnosis: Optional[str] = None
    notes: Optional[str] = None
```

**BenchmarkResults:**
```python
class BenchmarkResults(BaseModel):
    """Complete benchmark test results."""
    total_cases: int
    passed: int
    failed: int
    pass_rate: float
    case_results: List[CaseResult]
    summary_by_pattern: List[PatternSummary]
    total_execution_time_ms: float
```


## Component Interaction Flow

### Single File Processing Flow

```
User Input: python main.py --input incident.json
                    │
                    ▼
┌───────────────────────────────────────────────────────────┐
│ main.py: process_single_file()                            │
│                                                            │
│ 1. Read JSON file                                         │
│    with open(input_file, 'r') as f:                       │
│        json_input = f.read()                              │
└────────────────────┬──────────────────────────────────────┘
                     │
                     ▼
┌───────────────────────────────────────────────────────────┐
│ SchemaValidator.validate(json_input)                      │
│                                                            │
│ • Parse JSON → dict                                       │
│ • Validate against schema → check types, enums, ranges   │
│ • Convert to TelemetryInput model                         │
│ • Return ValidationResult                                 │
│                                                            │
│ If invalid → return error with exit code 1 or 2           │
└────────────────────┬──────────────────────────────────────┘
                     │ ValidationResult(valid=True, telemetry=...)
                     ▼
┌───────────────────────────────────────────────────────────┐
│ ConfidenceScorer.score_telemetry(telemetry)              │
│                                                            │
│ • Calculate completeness (count non-null fields)          │
│ • Detect signal conflicts (none/minor/major)              │
│ • Calculate confidence score (weighted algorithm)         │
│ • Return (completeness, confidence_score, conflicts)      │
└────────────────────┬──────────────────────────────────────┘
                     │ (completeness=85.0, confidence=0.75, conflicts="none")
                     ▼
┌───────────────────────────────────────────────────────────┐
│ DecisionEngine.decide(telemetry, confidence, completeness)│
│                                                            │
│ • Check safety rules (6 rules)                            │
│ • Check critical signals                                  │
│ • Check completeness thresholds                           │
│ • Match patterns (20 patterns)                            │
│ • Apply decision rules (A, B, C)                          │
│ • Generate evidence, gaps, next_check                     │
│ • Return Decision                                         │
└────────────────────┬──────────────────────────────────────┘
                     │ Decision(state=DIAGNOSE, diagnosis="...", ...)
                     ▼
┌───────────────────────────────────────────────────────────┐
│ ExplanationFormatter.format_output(decision, telemetry,   │
│                                     confidence_score)      │
│                                                            │
│ • Generate explanation text (5 parts)                     │
│ • Format evidence list                                    │
│ • Identify evidence gaps                                  │
│ • Add safety context                                      │
│ • Return DiagnosticOutput (7 fields)                      │
└────────────────────┬──────────────────────────────────────┘
                     │ DiagnosticOutput(decision="diagnose", ...)
                     ▼
┌───────────────────────────────────────────────────────────┐
│ main.py: Write output                                     │
│                                                            │
│ • Serialize to JSON                                       │
│ • Write to stdout or file                                 │
│ • Return exit code 0                                      │
└───────────────────────────────────────────────────────────┘
```

### Benchmark Processing Flow

```
User Input: python main.py --benchmark data/benchmark_cases.csv
                    │
                    ▼
┌───────────────────────────────────────────────────────────┐
│ BenchmarkLoader.load_cases(benchmark_file)               │
│                                                            │
│ • Read CSV or JSON file                                   │
│ • Parse each case                                         │
│ • Validate case structure                                 │
│ • Return List[BenchmarkCase]                              │
└────────────────────┬──────────────────────────────────────┘
                     │ [BenchmarkCase(...), BenchmarkCase(...), ...]
                     ▼
┌───────────────────────────────────────────────────────────┐
│ TestHarness.run_benchmark(cases)                          │
│                                                            │
│ For each case:                                            │
│   1. Extract telemetry_input                              │
│   2. Process through pipeline:                            │
│      • SchemaValidator.validate_dict(telemetry)           │
│      • ConfidenceScorer.score_telemetry(telemetry)        │
│      • DecisionEngine.decide(...)                         │
│      • ExplanationFormatter.format_output(...)            │
│   3. Compare actual vs expected decision                  │
│   4. Record CaseResult (pass/fail, execution time)        │
│                                                            │
│ Aggregate results:                                        │
│   • Calculate pass/fail counts                            │
│   • Group by incident pattern                             │
│   • Calculate statistics                                  │
│   • Return BenchmarkResults                               │
└────────────────────┬──────────────────────────────────────┘
                     │ BenchmarkResults(total=35, passed=34, ...)
                     ▼
┌───────────────────────────────────────────────────────────┐
│ TestHarness.print_results(results)                        │
│                                                            │
│ • Print overall statistics                                │
│ • Print per-pattern summary                               │
│ • Print failed case details                               │
│ • Print execution time statistics                         │
└───────────────────────────────────────────────────────────┘
```

### Error Handling Flow

```
Error occurs at any stage
         │
         ▼
┌─────────────────────────────────────────────────────┐
│ Catch exception and determine error type            │
└────────────┬────────────────────────────────────────┘
             │
             ├─ JSONParseError → Exit code 1
             │  (malformed JSON with line/column)
             │
             ├─ SchemaValidationError → Exit code 2
             │  (invalid enum, out-of-range, missing required)
             │
             ├─ FileNotFoundError → Exit code 3
             │  (input file or schema file not found)
             │
             ├─ IOError → Exit code 4
             │  (file read/write error)
             │
             ├─ Benchmark error → Exit code 5
             │  (benchmark loading or processing error)
             │
             └─ Unexpected error → Exit code 99
                (internal error with stack trace)
```


## File Structure

The project follows a modular structure with clear separation of concerns:

```
azure-vm-incident-copilot/
├── README.md                          # Project overview and usage
├── requirements.txt                   # Runtime dependencies
├── requirements-test.txt              # Test dependencies
├── main.py                           # CLI entry point
│
├── setup/                            # Setup generators (one-time)
│   ├── __init__.py
│   ├── run_setup.py                  # Standalone setup runner
│   ├── generate_schema.py            # Generate triage schema
│   ├── generate_output_schema.py     # Generate output schema
│   ├── generate_policy.py            # Generate decision policy
│   └── generate_benchmark.py         # Generate benchmark cases
│
├── schemas/                          # Generated schemas
│   ├── azure_vm_triage_schema.json   # Input validation schema (30+ fields)
│   └── output_schema.json            # Output validation schema (7 fields)
│
├── policy/                           # Generated policy
│   └── decision_policy.json          # Decision rules + safety rules
│
├── data/                             # Generated benchmark data
│   └── benchmark_cases.csv           # 35 benchmark test cases
│
├── src/                              # Source code
│   ├── __init__.py
│   ├── models.py                     # Pydantic models and enums
│   ├── validator.py                  # Schema validation component
│   ├── confidence_scorer.py          # Confidence scoring component
│   ├── decision_engine.py            # Decision policy component
│   ├── explanation_formatter.py      # Output formatting component
│   ├── benchmark_loader.py           # Benchmark loading component
│   └── test_harness.py               # Benchmark testing component
│
├── tests/                            # Test suite
│   ├── __init__.py
│   ├── unit/                         # Unit tests
│   │   └── __init__.py
│   └── property/                     # Property-based tests
│       ├── __init__.py
│       ├── strategies.py             # Hypothesis strategies
│       ├── test_properties_validation.py    # Properties 1-4
│       ├── test_properties_decision.py      # Properties 5-10
│       ├── test_properties_safety.py        # Properties 11-16
│       └── test_properties_integrity.py     # Properties 17-20
│
└── docs/                             # Documentation
    ├── architecture.md               # This file
    ├── decision_policy.md            # Decision rules documentation
    ├── safety_rules.md               # Safety rules documentation
    └── incident_patterns.md          # Incident patterns documentation
```

### Key Files Description

**Setup Scripts (setup/):**
- `run_setup.py`: Standalone setup runner that calls all generators
- `generate_schema.py`: Generates triage schema with 30+ field definitions
- `generate_output_schema.py`: Generates output schema with 7 required fields
- `generate_policy.py`: Generates decision policy with rules A, B, C and 6 safety rules
- `generate_benchmark.py`: Generates 35 benchmark cases (20 patterns + 5 clean + 5 missing + 5 conflicting)

**Generated Files:**
- `schemas/azure_vm_triage_schema.json`: Complete JSON Schema for input validation
- `schemas/output_schema.json`: JSON Schema for output validation
- `policy/decision_policy.json`: Decision rules and safety rules in JSON format
- `data/benchmark_cases.csv`: 35 benchmark test cases in CSV format

**Core Components (src/):**
- `models.py`: All Pydantic models (8 enums, TelemetryInput, DiagnosticOutput, etc.)
- `validator.py`: JSON parsing and schema validation
- `confidence_scorer.py`: Completeness and confidence calculation
- `decision_engine.py`: Decision policy, safety rules, pattern matching
- `explanation_formatter.py`: Output formatting and explanation generation
- `benchmark_loader.py`: Benchmark case loading from CSV/JSON
- `test_harness.py`: Batch benchmark processing and result reporting

**CLI Interface:**
- `main.py`: Command-line interface with 4 modes (setup, input, benchmark, output)

**Tests (tests/):**
- `property/strategies.py`: Hypothesis strategies for generating test data
- `property/test_properties_*.py`: 20 property-based tests (100+ iterations each)
- `unit/`: Unit tests for specific examples and edge cases

**Documentation (docs/):**
- `architecture.md`: System architecture and component design (this file)
- `decision_policy.md`: Decision rules A, B, C with examples
- `safety_rules.md`: 6 safety rules with violation examples
- `incident_patterns.md`: 20 known patterns with matching conditions


## Design Principles

### 1. Read-Only Operation

**Principle:** The system never executes write operations or remediation actions.

**Implementation:**
- No Azure SDK dependencies or API calls
- No VM state modification commands
- No resource group or network changes
- All operations are analysis and recommendation only
- `next_check` field contains only diagnostic actions, never remediation commands

**Enforcement:**
- Safety rules prevent unsafe suggestions (restart, delete, disable)
- CLI has no flags for remediation operations
- Code review ensures no write operations are added

---

### 2. Deterministic Decision Logic

**Principle:** Identical inputs produce identical outputs.

**Implementation:**
- No randomness in decision logic
- No external API calls that could vary
- No timestamps in decision logic (only in telemetry input)
- Fixed thresholds and weights
- Pattern matching uses exact conditions

**Verification:**
- Property test: "Decision Determinism" (Property 5)
- Unit tests verify same input → same output
- Benchmark tests are reproducible

---

### 3. Safety-First

**Principle:** Six safety rules prevent unsafe suggestions in all scenarios.

**Implementation:**
- Safety rules are checked first (highest priority)
- Safety rules can override pattern matches
- Safety rules sanitize `next_check` suggestions
- Safety context is added to explanations

**Safety Rules:**
1. Platform Event Safety: Never suggest restart during maintenance
2. Boot Failure Safety: Never suggest restart for BSOD/KernelPanic
3. Low Confidence Destructive Action Safety: Prevent destructive actions when confidence < 0.9
4. Network Security Safety: Never suggest disabling NSG/firewall
5. Disk Safety: Prevent disk operations when confidence < 0.9
6. Failed State Safety: Never suggest auto-remediation for failed VMs

**Enforcement:**
- `_check_safety_rules()` method in DecisionEngine
- `_sanitize_next_check()` method removes unsafe suggestions
- Property tests verify safety rules (Properties 11-16)

---

### 4. Modular Architecture

**Principle:** Clear separation of concerns across seven components.

**Benefits:**
- Each component has a single responsibility
- Components can be tested independently
- Easy to modify or replace individual components
- Clear interfaces between components

**Component Boundaries:**
- Validator: JSON parsing and schema validation only
- Scorer: Completeness and confidence calculation only
- Engine: Decision logic and pattern matching only
- Formatter: Output formatting and explanation generation only
- Loader: Benchmark loading only
- Harness: Benchmark testing only
- CLI: User interface and orchestration only

---

### 5. Comprehensive Validation

**Principle:** 30+ telemetry fields with strict type and range constraints.

**Implementation:**
- JSON Schema validation for all fields
- Pydantic model validation with constraints
- Enum validation for 8 enum types
- Numeric range validation (0-100 for percentages, ≥0 for latencies)
- Required field validation (3 required fields)
- Unknown field tolerance (forward compatibility)

**Error Reporting:**
- Detailed validation errors with field names
- Constraint violation descriptions
- Actual values that failed validation
- Line/column details for JSON parse errors

---

### 6. Local Execution

**Principle:** No Azure connectivity required - runs entirely locally.

**Implementation:**
- No Azure SDK dependencies
- No network calls or API requests
- All configuration files are local (schemas/, policy/, data/)
- All processing is in-memory
- No database or external storage

**Benefits:**
- Fast execution (no network latency)
- Works offline
- No authentication required
- No Azure subscription needed
- Easy to test and debug

---

### 7. Testability

**Principle:** Property-based testing with 100+ iterations per property.

**Implementation:**
- 20 correctness properties defined in design document
- Hypothesis library for property-based testing
- Custom strategies for generating test data
- 100+ iterations per property test
- Deterministic seed for reproducibility

**Test Coverage:**
- Property tests: Universal correctness properties (20 properties)
- Unit tests: Specific examples and edge cases
- Integration tests: End-to-end pipeline testing
- Benchmark tests: 35 real-world cases

**Property Examples:**
- Property 1: Schema validation accepts all valid fields
- Property 5: Decision determinism (same input → same output)
- Property 7: Low completeness triggers abstain
- Property 11: Boot failure safety (never suggest restart)


## Usage Examples

### Example 1: Setup and Single File Processing

```bash
# Step 1: Run setup (one-time)
python main.py --setup

# Output:
# ============================================================
# Azure VM Incident Copilot - Setup
# ============================================================
# 
# Step 1/4: Generating triage schema...
# Created: schemas/azure_vm_triage_schema.json
# 
# Step 2/4: Generating output schema...
# Created: schemas/output_schema.json
# 
# Step 3/4: Generating decision policy...
# Created: policy/decision_policy.json
# 
# Step 4/4: Generating benchmark cases...
# Created: data/benchmark_cases.csv
# 
# ============================================================
# Setup complete!
# ============================================================

# Step 2: Process a telemetry file
python main.py --input incident.json

# Output (JSON):
# {
#   "decision": "diagnose",
#   "diagnosis": "High CPU saturation",
#   "confidence_score": 0.85,
#   "evidence": [
#     "power_state=Running",
#     "provisioning_state=Succeeded",
#     "resource_health_status=Degraded",
#     "cpu_percent=98.0"
#   ],
#   "evidence_gap": [
#     "heartbeat_present",
#     "boot_diagnostics_status"
#   ],
#   "next_check": "Identify high CPU processes and optimize or scale VM",
#   "explanation": "High confidence diagnosis: High CPU saturation. Confidence score is 0.85, indicating strong evidence for this assessment. Supporting evidence includes: power_state=Running, provisioning_state=Succeeded, resource_health_status=Degraded, cpu_percent=98.0. Missing or incomplete data: heartbeat_present, boot_diagnostics_status. Recommended next step: Identify high CPU processes and optimize or scale VM"
# }
```

### Example 2: Benchmark Testing

```bash
# Run benchmark with all 35 cases
python main.py --benchmark data/benchmark_cases.csv

# Output:
# Loaded 35 benchmark cases from data/benchmark_cases.csv
# 
# Processing benchmark cases...
# [====================] 35/35 (100%)
# 
# ============================================================
# Benchmark Results
# ============================================================
# Total cases: 35
# Passed: 34
# Failed: 1
# Pass rate: 97.14%
# Total execution time: 1250.5 ms
# Average time per case: 35.7 ms
# 
# Summary by Pattern:
# - vm_stopped_by_user: 1/1 passed (100.0%)
# - nsg_blocks_rdp: 1/1 passed (100.0%)
# - high_cpu: 1/1 passed (100.0%)
# ...
# 
# Failed Cases:
# - Case 023 (conflicting_nsg_signals): Expected diagnose, got diagnose_low_confidence
```

### Example 3: Output to File

```bash
# Process telemetry and write output to file
python main.py --input incident.json --output result.json

# Output:
# Output written to: result.json

# View the result
cat result.json
```

### Example 4: Error Handling

```bash
# Invalid JSON
python main.py --input malformed.json

# Output (stderr):
# JSON parse error at line 5, column 12: Expecting ',' delimiter
# Exit code: 1

# Invalid enum value
python main.py --input invalid_enum.json

# Output (stderr):
# Schema validation failed:
#   Field: power_state
#   Error: value must be one of: Running, Stopped, Deallocated, Failed, Unknown
#   Value: InvalidState
# Exit code: 2

# File not found
python main.py --input nonexistent.json

# Output (stderr):
# Error: File not found: nonexistent.json
# Exit code: 3
```

## Performance Characteristics

### Execution Time

**Single File Processing:**
- JSON parsing: < 1 ms
- Schema validation: < 5 ms
- Confidence scoring: < 1 ms
- Decision engine: < 10 ms
- Output formatting: < 1 ms
- **Total: < 20 ms per case**

**Benchmark Processing:**
- 35 cases: ~1250 ms total
- Average: ~35 ms per case
- Includes file I/O and result aggregation

### Memory Usage

**Single File Processing:**
- Telemetry input: < 10 KB
- Parsed models: < 50 KB
- Total memory: < 100 KB per case

**Benchmark Processing:**
- 35 cases in memory: < 5 MB
- Results aggregation: < 1 MB
- Total memory: < 10 MB

### Scalability

**Current Design:**
- Optimized for single-case processing
- Benchmark mode processes cases sequentially
- No parallelization (deterministic execution)

**Future Enhancements:**
- Parallel benchmark processing (if determinism maintained)
- Streaming benchmark results (for large datasets)
- Caching of schema/policy files (already loaded once)

## Dependencies

### Runtime Dependencies (requirements.txt)

```
jsonschema>=4.0.0    # JSON Schema validation
pydantic>=2.0.0      # Data modeling and validation
pandas>=1.5.0        # CSV loading for benchmarks
click>=8.0.0         # CLI argument parsing
```

### Test Dependencies (requirements-test.txt)

```
pytest>=7.0.0        # Unit testing framework
hypothesis>=6.0.0    # Property-based testing
pytest-cov>=4.0.0    # Code coverage reporting
-r requirements.txt  # Include runtime dependencies
```

### Python Version

- **Minimum:** Python 3.8
- **Recommended:** Python 3.10 or higher
- **Tested on:** Python 3.10, 3.11, 3.12

## Future Enhancements

### Potential Improvements

1. **Additional Patterns:** Expand from 20 to 30+ known incident patterns
2. **Pattern Confidence:** Add per-pattern confidence scores
3. **Historical Context:** Track telemetry trends over time
4. **Multi-VM Analysis:** Analyze multiple VMs for correlated issues
5. **Custom Patterns:** Allow users to define custom incident patterns
6. **Interactive Mode:** CLI mode for interactive diagnosis
7. **Web Interface:** REST API and web UI for remote access
8. **Remediation Suggestions:** Add safe remediation suggestions (with user confirmation)
9. **Integration:** Azure Monitor integration for real-time telemetry
10. **Machine Learning:** ML-based pattern detection for unknown issues

### Backward Compatibility

All enhancements will maintain backward compatibility:
- Existing telemetry format will continue to work
- New optional fields will be added (not required)
- Existing decision policy will be preserved
- New patterns will be additive (not replacing existing)

## Conclusion

The Azure VM Incident Copilot provides a robust, safe, and deterministic system for diagnosing Azure VM incidents. The modular architecture, comprehensive validation, and safety-first design ensure reliable operation across a wide range of scenarios. The system is fully testable with property-based testing and can be extended with additional patterns and features while maintaining backward compatibility.

For more details, see:
- [Decision Policy Documentation](decision_policy.md)
- [Safety Rules Documentation](safety_rules.md)
- [Incident Patterns Documentation](incident_patterns.md)
- [README](../README.md)

