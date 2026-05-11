# Requirements Document

## Introduction

This document specifies requirements for upgrading the Azure VM Incident Copilot decision engine from a rule-based system to an LLM-based system with Retrieval-Augmented Generation (RAG) and self-learning capabilities. The current system uses 20 hardcoded incident patterns and 6 safety rules. The upgraded system will maintain all existing safety guarantees while adding the ability to detect novel incidents, learn from past cases, and consult a Standard Operating Procedure (SOP) knowledge base for recommendations.

The upgrade maintains backward compatibility by preserving the existing interface: `decide(telemetry, confidence_score, completeness) → Decision`. All existing safety rules remain deterministic and override any LLM output.

## Glossary

- **LLM_Engine**: The language model reasoning component that replaces rule-based pattern matching
- **RAG_Memory**: Vector database storing past incident cases as embeddings for similarity search
- **SOP_Knowledge_Base**: Vector database storing 12+ Standard Operating Procedures for next_check recommendations
- **Safety_Guard**: Deterministic layer that enforces 6 safety rules and overrides LLM output
- **Feedback_Loop**: Human-in-the-loop mechanism for correcting and improving LLM decisions
- **Decision_Engine**: The main component that orchestrates LLM reasoning, RAG retrieval, and safety enforcement
- **Novel_Incident**: An incident that does not match any of the 20 predefined patterns
- **Embedding_Model**: Local sentence-transformer model for converting text to vector embeddings
- **Provider_Fallback**: Automatic switching between LLM providers (Groq → Gemini → Ollama) on failure
- **Confidence_Score**: Numerical value (0.0-1.0) indicating diagnostic confidence
- **Telemetry_Input**: Structured data containing 30+ VM health signals

## Requirements

### Requirement 1: LLM Provider Integration

**User Story:** As a system operator, I want the decision engine to use multiple LLM providers with automatic fallback, so that the system remains operational even if one provider fails.

#### Acceptance Criteria

1. THE LLM_Engine SHALL support three LLM providers: Groq, Gemini, and Ollama
2. WHEN Groq API fails or times out, THE LLM_Engine SHALL automatically fallback to Gemini
3. WHEN Gemini API fails or times out, THE LLM_Engine SHALL automatically fallback to Ollama
4. WHERE Ollama is configured, THE LLM_Engine SHALL use local Ollama instance without requiring API keys
5. THE LLM_Engine SHALL load provider API keys from environment variables or configuration file
6. WHEN all providers fail, THE LLM_Engine SHALL return a Decision with state=abstain_request_next_check and diagnosis indicating provider unavailability

### Requirement 2: RAG Memory Store

**User Story:** As a system operator, I want past incidents stored in a vector database, so that the LLM can retrieve similar cases to improve diagnostic accuracy.

#### Acceptance Criteria

1. THE RAG_Memory SHALL store incident cases as vector embeddings using ChromaDB
2. WHEN a Decision is generated, THE RAG_Memory SHALL store the telemetry, decision, diagnosis, and confidence_score as a new case
3. WHEN the LLM processes new telemetry, THE RAG_Memory SHALL retrieve the top 5 most similar past incidents using cosine similarity
4. THE RAG_Memory SHALL use a local sentence-transformer model for embeddings (no API keys required)
5. THE RAG_Memory SHALL persist embeddings to disk in the `data/chroma_memory/` directory
6. THE RAG_Memory SHALL include metadata filters for querying by decision state, confidence range, or time period

### Requirement 3: SOP Knowledge Base

**User Story:** As a system operator, I want the LLM to consult Standard Operating Procedures, so that next_check recommendations follow established organizational processes.

#### Acceptance Criteria

1. THE SOP_Knowledge_Base SHALL store 12+ Standard Operating Procedures as vector embeddings
2. WHEN generating next_check recommendations, THE LLM_Engine SHALL retrieve the top 3 most relevant SOPs using semantic search
3. THE SOP_Knowledge_Base SHALL include the following SOPs: "Azure Start/Stop VMs", "Azure Firewall Whitelisting", "Azure VM Scale Up/Down", "Azure Disk Cleanup", "Azure VM Disk Expansion/Addition", "Azure System Backup on VM", "Azure Request Admin Access", "Azure Request Cloud Resource Access", "Azure URL Onboarding in ARP", "Azure FinOps - Rightsize a Resource in Cloud", "Azure SSL Certificate Renewal", "Azure Decommission VM"
4. THE SOP_Knowledge_Base SHALL use the same embedding model as RAG_Memory for consistency
5. THE SOP_Knowledge_Base SHALL persist embeddings to disk in the `data/chroma_sops/` directory
6. WHERE an SOP is referenced in next_check, THE LLM_Engine SHALL include the SOP name in the format "Follow SOP_<name>"

### Requirement 4: LLM-Based Reasoning

**User Story:** As a system operator, I want the LLM to diagnose incidents using retrieved context, so that the system can handle novel incidents beyond the 20 predefined patterns.

#### Acceptance Criteria

1. WHEN processing telemetry, THE LLM_Engine SHALL construct a prompt containing: telemetry signals, top 5 similar past incidents, top 3 relevant SOPs, and the 20 known patterns
2. THE LLM_Engine SHALL generate a Decision with fields: state, diagnosis, evidence, evidence_gap, next_check, confidence_score
3. THE LLM_Engine SHALL output structured JSON matching the Decision model schema
4. WHEN the LLM detects a novel incident (not matching any of the 20 patterns), THE LLM_Engine SHALL set a flag `novel_incident=true` in the Decision metadata
5. THE LLM_Engine SHALL include reasoning in the prompt that explains how similar past cases inform the current diagnosis
6. WHEN the LLM fails to generate valid JSON, THE LLM_Engine SHALL retry up to 3 times before falling back to the next provider

### Requirement 5: Safety Guard Override

**User Story:** As a system operator, I want all 6 safety rules enforced deterministically, so that the LLM cannot suggest unsafe actions regardless of its reasoning.

#### Acceptance Criteria

1. THE Safety_Guard SHALL enforce all 6 safety rules after LLM output generation
2. WHEN the LLM output violates Safety Rule 1 (Platform Event), THE Safety_Guard SHALL override the decision to abstain_request_next_check
3. WHEN the LLM output violates Safety Rule 2 (Boot Failure), THE Safety_Guard SHALL remove any "restart" suggestions from next_check
4. WHEN the LLM output violates Safety Rule 3 (Low Confidence Destructive Action), THE Safety_Guard SHALL remove destructive action keywords from next_check
5. WHEN the LLM output violates Safety Rule 4 (Network Security), THE Safety_Guard SHALL replace next_check with manual review instructions
6. WHEN the LLM output violates Safety Rule 5 (Disk Safety), THE Safety_Guard SHALL replace next_check with manual review instructions
7. WHEN the LLM output violates Safety Rule 6 (Failed State), THE Safety_Guard SHALL remove auto-remediation suggestions from next_check
8. THE Safety_Guard SHALL log all overrides with the original LLM output and the sanitized output

### Requirement 6: Novel Incident Detection

**User Story:** As a system operator, I want the system to detect incidents that don't match the 20 predefined patterns, so that I can identify new failure modes.

#### Acceptance Criteria

1. WHEN the LLM processes telemetry, THE LLM_Engine SHALL compare the incident against the 20 known patterns
2. WHEN no pattern matches with confidence ≥ 0.7, THE LLM_Engine SHALL flag the incident as novel
3. THE Decision SHALL include a metadata field `novel_incident: bool` indicating whether the incident is novel
4. WHEN a novel incident is detected, THE LLM_Engine SHALL include "Novel incident detected" in the explanation field
5. THE RAG_Memory SHALL tag novel incidents with `is_novel=true` metadata for future retrieval
6. THE System SHALL provide an API endpoint `/api/novel-incidents` to retrieve all flagged novel incidents

### Requirement 7: Human Feedback Loop

**User Story:** As a system operator, I want to mark LLM decisions as correct or incorrect, so that the system learns from mistakes and improves over time.

#### Acceptance Criteria

1. THE System SHALL provide an API endpoint `/api/feedback` accepting POST requests with fields: incident_id, feedback_type (correct/incorrect), corrected_diagnosis (optional), corrected_next_check (optional)
2. WHEN feedback is submitted, THE Feedback_Loop SHALL update the RAG_Memory entry with feedback metadata
3. WHEN retrieving similar incidents, THE RAG_Memory SHALL prioritize incidents marked as "correct" over those marked as "incorrect"
4. THE Feedback_Loop SHALL store corrected diagnosis and next_check as alternative versions in the RAG_Memory
5. WHEN an incident similar to a previously corrected case is detected, THE LLM_Engine SHALL include the corrected version in the prompt context
6. THE System SHALL provide a UI component in the dashboard for submitting feedback on each decision

### Requirement 8: Backward Compatibility

**User Story:** As a developer, I want the LLM-based engine to maintain the same interface as the rule-based engine, so that existing code continues to work without modification.

#### Acceptance Criteria

1. THE Decision_Engine SHALL maintain the method signature: `decide(telemetry: TelemetryInput, confidence_score: float, completeness: float) → Decision`
2. THE Decision model SHALL maintain all existing fields: state, diagnosis, evidence, evidence_gap, next_check, confidence_score
3. THE Decision_Engine SHALL return one of three states: diagnose, diagnose_low_confidence, abstain_request_next_check
4. THE Decision_Engine SHALL enforce the same confidence and completeness thresholds: diagnose (≥0.70, ≥90%), diagnose_low_confidence (≥0.40, ≥60%)
5. THE Decision_Engine SHALL populate next_check when state=abstain_request_next_check (Property 9 validation)
6. THE System SHALL pass all existing property-based tests without modification

### Requirement 9: Embedding Model Management

**User Story:** As a system operator, I want embeddings generated locally without API calls, so that the system operates without external dependencies for vector generation.

#### Acceptance Criteria

1. THE Embedding_Model SHALL use sentence-transformers library with the "all-MiniLM-L6-v2" model
2. THE Embedding_Model SHALL download model weights on first run and cache them locally
3. THE Embedding_Model SHALL generate embeddings for telemetry, decisions, and SOPs without requiring API keys
4. THE Embedding_Model SHALL produce 384-dimensional vectors for all text inputs
5. THE Embedding_Model SHALL handle text inputs up to 512 tokens in length
6. WHEN the model fails to load, THE System SHALL log an error and fallback to rule-based decision engine

### Requirement 10: Memory Growth and Pruning

**User Story:** As a system operator, I want the RAG memory to grow over time but avoid unbounded storage, so that the system remains performant as it learns.

#### Acceptance Criteria

1. THE RAG_Memory SHALL store all incidents without automatic deletion
2. WHEN the RAG_Memory exceeds 10,000 incidents, THE System SHALL log a warning recommending manual review
3. THE System SHALL provide an API endpoint `/api/memory/prune` to remove incidents older than a specified date
4. THE System SHALL provide an API endpoint `/api/memory/stats` returning: total incidents, novel incidents count, average confidence score, feedback distribution
5. WHEN retrieving similar incidents, THE RAG_Memory SHALL limit results to the top 5 most similar cases
6. THE RAG_Memory SHALL support filtering by minimum confidence score to exclude low-quality cases from retrieval

### Requirement 11: LLM Prompt Engineering

**User Story:** As a system operator, I want the LLM prompt to include all necessary context, so that the LLM generates accurate and actionable diagnoses.

#### Acceptance Criteria

1. THE LLM_Engine SHALL construct prompts with the following sections: System Role, Telemetry Input, Similar Past Incidents, Relevant SOPs, Known Patterns, Output Format
2. THE LLM_Engine SHALL include the 6 safety rules in the System Role section with explicit instructions to avoid unsafe suggestions
3. THE LLM_Engine SHALL format telemetry as key-value pairs with only non-null fields included
4. THE LLM_Engine SHALL format similar incidents with: diagnosis, confidence_score, evidence, next_check, and similarity score
5. THE LLM_Engine SHALL format SOPs with: SOP name, description, and relevance score
6. THE LLM_Engine SHALL instruct the LLM to output valid JSON matching the Decision schema exactly

### Requirement 12: Configuration Management

**User Story:** As a system operator, I want LLM and RAG settings configurable via environment variables, so that I can adjust behavior without code changes.

#### Acceptance Criteria

1. THE System SHALL load LLM provider API keys from environment variables: GROQ_API_KEY, GEMINI_API_KEY
2. THE System SHALL load Ollama configuration from environment variable: OLLAMA_BASE_URL (default: http://localhost:11434)
3. THE System SHALL load RAG settings from environment variables: RAG_TOP_K (default: 5), SOP_TOP_K (default: 3)
4. THE System SHALL load embedding model name from environment variable: EMBEDDING_MODEL (default: "all-MiniLM-L6-v2")
5. THE System SHALL load ChromaDB persistence paths from environment variables: CHROMA_MEMORY_PATH (default: "data/chroma_memory"), CHROMA_SOP_PATH (default: "data/chroma_sops")
6. WHEN an environment variable is missing, THE System SHALL use the default value and log a warning

### Requirement 13: Performance and Latency

**User Story:** As a system operator, I want LLM-based decisions to complete within reasonable time, so that the system remains responsive for real-time diagnostics.

#### Acceptance Criteria

1. THE LLM_Engine SHALL complete decision generation within 10 seconds for 95% of requests
2. WHEN an LLM provider times out after 5 seconds, THE LLM_Engine SHALL fallback to the next provider
3. THE RAG_Memory SHALL complete similarity search within 500ms for 95% of queries
4. THE SOP_Knowledge_Base SHALL complete similarity search within 500ms for 95% of queries
5. THE Embedding_Model SHALL generate embeddings within 200ms for 95% of inputs
6. THE System SHALL log execution time for each component: LLM inference, RAG retrieval, SOP retrieval, embedding generation, safety guard enforcement

### Requirement 14: Error Handling and Fallback

**User Story:** As a system operator, I want the system to gracefully handle LLM failures, so that diagnostics continue even when LLM providers are unavailable.

#### Acceptance Criteria

1. WHEN all LLM providers fail, THE Decision_Engine SHALL fallback to the original rule-based pattern matching
2. WHEN the RAG_Memory is unavailable, THE LLM_Engine SHALL proceed without similar incident context
3. WHEN the SOP_Knowledge_Base is unavailable, THE LLM_Engine SHALL proceed without SOP recommendations
4. WHEN the Embedding_Model fails to load, THE System SHALL disable RAG features and use rule-based engine
5. THE System SHALL log all fallback events with error details and timestamp
6. THE System SHALL expose a health check endpoint `/api/health` indicating: LLM provider status, RAG memory status, SOP knowledge base status, embedding model status

### Requirement 15: Observability and Logging

**User Story:** As a system operator, I want detailed logs of LLM reasoning and RAG retrieval, so that I can debug incorrect diagnoses and improve the system.

#### Acceptance Criteria

1. THE System SHALL log all LLM prompts and responses to `logs/llm_decisions.jsonl`
2. THE System SHALL log all RAG retrievals with similarity scores to `logs/rag_retrievals.jsonl`
3. THE System SHALL log all safety guard overrides to `logs/safety_overrides.jsonl`
4. THE System SHALL log all human feedback submissions to `logs/feedback.jsonl`
5. THE System SHALL include request_id in all log entries for tracing a single decision across components
6. THE System SHALL provide an API endpoint `/api/logs/decision/{request_id}` to retrieve all logs for a specific decision

### Requirement 16: Testing and Validation

**User Story:** As a developer, I want comprehensive tests for the LLM-based engine, so that I can verify correctness and prevent regressions.

#### Acceptance Criteria

1. THE System SHALL include unit tests for: LLM provider fallback, RAG retrieval, SOP retrieval, safety guard overrides, feedback loop
2. THE System SHALL include integration tests for: end-to-end decision generation with LLM, RAG memory persistence, SOP knowledge base queries
3. THE System SHALL include property-based tests validating: all 15 existing properties still hold, safety rules cannot be bypassed by LLM, decision determinism with same LLM output
4. THE System SHALL include benchmark tests comparing: LLM-based engine vs rule-based engine on 35 benchmark cases, novel incident detection accuracy
5. THE System SHALL achieve ≥90% pass rate on existing benchmark cases
6. THE System SHALL detect ≥80% of manually labeled novel incidents in a test dataset

### Requirement 17: UI Dashboard Integration

**User Story:** As a system operator, I want the web dashboard to display LLM reasoning and feedback controls, so that I can monitor and correct LLM decisions.

#### Acceptance Criteria

1. THE Dashboard SHALL display a "Memory" tab showing: total incidents stored, novel incidents count, recent feedback submissions
2. THE Dashboard SHALL display LLM reasoning for each decision including: similar incidents retrieved, SOPs consulted, novel incident flag
3. THE Dashboard SHALL provide feedback buttons (Correct/Incorrect) on each decision in the feed
4. WHEN feedback is submitted, THE Dashboard SHALL display a confirmation message and update the incident entry
5. THE Dashboard SHALL display safety guard overrides with: original LLM output, sanitized output, safety rule violated
6. THE Dashboard SHALL provide a search interface for querying past incidents by: diagnosis keywords, confidence range, date range, novel incident flag

### Requirement 18: SOP Knowledge Base Initialization

**User Story:** As a system operator, I want the SOP knowledge base pre-populated with 12 SOPs, so that the system provides actionable recommendations from the start.

#### Acceptance Criteria

1. THE System SHALL include a setup script `setup/initialize_sop_kb.py` that populates the SOP_Knowledge_Base
2. THE Setup script SHALL load SOP content from `data/sops/*.md` files
3. THE Setup script SHALL generate embeddings for each SOP and store them in ChromaDB
4. THE Setup script SHALL validate that all 12 required SOPs are present before completing
5. THE Setup script SHALL be idempotent (running multiple times produces the same result)
6. THE System SHALL log an error on startup if the SOP_Knowledge_Base is empty and provide instructions to run the setup script

### Requirement 19: Round-Trip Property for LLM Output

**User Story:** As a developer, I want to validate that LLM output can be parsed and serialized correctly, so that the system handles structured data reliably.

#### Acceptance Criteria

1. FOR ALL valid Decision objects generated by the LLM, parsing the JSON output then serializing it SHALL produce an equivalent Decision object
2. THE LLM_Engine SHALL validate LLM output against the Decision schema before returning
3. WHEN the LLM output fails schema validation, THE LLM_Engine SHALL log the validation errors and retry with a corrected prompt
4. THE System SHALL include a property-based test validating the round-trip property for LLM-generated decisions
5. THE LLM_Engine SHALL reject decisions with: missing required fields, invalid enum values, confidence_score outside [0.0, 1.0], empty next_check when state=abstain_request_next_check
6. WHEN validation fails after 3 retries, THE LLM_Engine SHALL fallback to the next provider

### Requirement 20: Incremental Rollout Support

**User Story:** As a system operator, I want to enable LLM-based decisions gradually, so that I can validate correctness before full deployment.

#### Acceptance Criteria

1. THE System SHALL support a configuration flag `LLM_ENABLED` (default: false) to enable/disable LLM-based decisions
2. WHEN LLM_ENABLED=false, THE Decision_Engine SHALL use the original rule-based pattern matching
3. WHEN LLM_ENABLED=true, THE Decision_Engine SHALL use LLM-based reasoning with RAG
4. THE System SHALL support a configuration flag `LLM_SHADOW_MODE` (default: false) to run both engines and compare outputs
5. WHEN LLM_SHADOW_MODE=true, THE System SHALL log differences between rule-based and LLM-based decisions to `logs/shadow_mode.jsonl`
6. THE System SHALL provide an API endpoint `/api/shadow-mode/stats` returning: total decisions, agreement rate, disagreement cases
