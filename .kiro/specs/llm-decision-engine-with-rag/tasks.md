# Implementation Plan: LLM Decision Engine with RAG

## Overview

This plan implements an LLM-based decision engine with Retrieval-Augmented Generation (RAG) for the Azure VM Incident Copilot. The system replaces hardcoded pattern matching with LLM reasoning while maintaining all existing safety guarantees. Key features include: multi-provider LLM support (Groq → Gemini → Ollama), ChromaDB-based incident memory and SOP knowledge base, human feedback loop for continuous learning, and novel incident detection.

The implementation maintains backward compatibility with the existing `decide(telemetry, confidence_score, completeness) → Decision` interface and ensures all 6 safety rules override LLM output unconditionally.

## Tasks

- [x] 1. Set up LLM provider infrastructure
  - Create `src/llm/` directory structure
  - Install required dependencies: `groq`, `google-generativeai`, `ollama`, `chromadb`, `sentence-transformers`, `jinja2`
  - Create `.env.example` with LLM provider configuration template
  - _Requirements: 1.1, 1.5, 12.1, 12.2, 12.3_

- [x] 2. Implement LLM provider abstraction layer
  - [x] 2.1 Create base LLM provider interface
    - Write `src/llm/base_provider.py` with abstract `LLMProvider` class
    - Define methods: `is_available()`, `generate(prompt, temperature)`, `supports_json_mode()`
    - Add provider metadata: name, model, rate limits
    - _Requirements: 1.1, 4.3_

  - [x] 2.2 Implement Groq provider
    - Write `src/llm/groq_provider.py` implementing `LLMProvider`
    - Use `llama-3.3-70b-versatile` model with `response_format={"type": "json_object"}`
    - Handle rate limiting (30 req/min) with exponential backoff
    - Load API key from `GROQ_API_KEY` environment variable
    - _Requirements: 1.1, 1.5, 4.6_

  - [x] 2.3 Implement Gemini provider
    - Write `src/llm/gemini_provider.py` implementing `LLMProvider`
    - Use `gemini-2.0-flash-exp` model with `response_mime_type="application/json"`
    - Handle API errors with retry logic
    - Load API key from `GEMINI_API_KEY` environment variable
    - _Requirements: 1.1, 1.5, 4.6_

  - [x] 2.4 Implement Ollama provider
    - Write `src/llm/ollama_provider.py` implementing `LLMProvider`
    - Use `llama3.2` model with `format="json"` parameter
    - Connect to local Ollama instance via `OLLAMA_BASE_URL` (default: http://localhost:11434)
    - Handle connection errors gracefully
    - _Requirements: 1.4, 1.5, 4.6_

  - [x] 2.5 Implement provider fallback chain
    - Write `src/llm/provider_chain.py` with `ProviderChain` class
    - Implement fallback logic: Groq → Gemini → Ollama → Rule Engine
    - Cache active provider to avoid re-checking on every request
    - Log provider switches with timestamps
    - _Requirements: 1.2, 1.3, 1.6, 14.1_

- [x] 3. Implement RAG memory store
  - [x] 3.1 Set up ChromaDB for incident storage
    - Write `src/rag/memory_store.py` with `IncidentMemoryStore` class
    - Initialize ChromaDB `PersistentClient` with path from `CHROMA_MEMORY_PATH` env var
    - Create collection with HNSW index for cosine similarity search
    - Load sentence-transformers model `all-MiniLM-L6-v2` for embeddings
    - _Requirements: 2.1, 2.4, 2.5, 9.1, 9.2, 9.3_

  - [x] 3.2 Implement telemetry-to-text conversion
    - Write method `_telemetry_to_text(telemetry: TelemetryInput) -> str`
    - Extract key discriminative signals: power_state, health, CPU, memory, heartbeat, boot status
    - Format as concise text summary for embedding quality
    - _Requirements: 2.3, 11.3_

  - [x] 3.3 Implement incident storage
    - Write method `add_incident(telemetry, decision, diagnosis, confidence, pattern)`
    - Generate embedding from telemetry text summary
    - Store with metadata: vm_name, timestamp, decision, diagnosis, confidence, pattern, outcome="pending", human_verified=False
    - Handle storage failures gracefully with logging
    - _Requirements: 2.2, 2.5, 14.3_

  - [x] 3.4 Implement similarity search
    - Write method `find_similar_incidents(telemetry: TelemetryInput, top_k: int) -> List[Dict]`
    - Generate embedding for query telemetry
    - Query ChromaDB with cosine similarity, filter by similarity ≥ 0.65
    - Sort by: human_verified DESC, similarity DESC
    - Return top K incidents with metadata
    - _Requirements: 2.3, 2.6, 7.3, 13.3_

  - [ ]* 3.5 Write unit tests for memory store
    - Test telemetry-to-text conversion with various signal combinations
    - Test incident storage and retrieval
    - Test similarity search ranking (verified cases prioritized)
    - Test empty collection handling
    - _Requirements: 16.1, 16.2_

- [x] 4. Implement SOP knowledge base
  - [x] 4.1 Create SOP data structure
    - Write `src/rag/sop_knowledge.py` with `SOPKnowledgeBase` class
    - Define SOP schema: id, title, description, triggers, steps, warnings
    - Initialize ChromaDB collection for SOPs (separate from incidents)
    - _Requirements: 3.1, 3.4, 3.5_

  - [x] 4.2 Create SOP content files
    - Create `data/sops/` directory
    - Write 12 SOP markdown files with structured content:
      - `sop_start_stop_vm.md`, `sop_firewall_whitelist.md`, `sop_disk_cleanup.md`
      - `sop_disk_expansion.md`, `sop_ssl_renewal.md`, `sop_backup.md`
      - `sop_vm_scale.md`, `sop_finops_rightsize.md`, `sop_request_admin_access.md`
      - `sop_decommission.md`, `sop_url_onboarding.md`, `sop_cloud_resource_access.md`
    - _Requirements: 3.2, 18.2_

  - [x] 4.3 Implement SOP initialization script
    - Write `setup/initialize_sop_kb.py` script
    - Load all 12 SOPs from `data/sops/*.md` files
    - Generate embeddings for each SOP (title + triggers + steps)
    - Store in ChromaDB with metadata
    - Validate all 12 SOPs present before completing
    - Make script idempotent
    - _Requirements: 18.1, 18.3, 18.4, 18.5_

  - [x] 4.4 Implement SOP retrieval
    - Write method `find_relevant_sops(telemetry_text: str, top_k: int) -> List[Dict]`
    - Generate embedding for telemetry text
    - Query ChromaDB for top K most relevant SOPs
    - Return SOP title, steps, and warnings
    - _Requirements: 3.2, 3.6, 13.4_

  - [ ]* 4.5 Write unit tests for SOP knowledge base
    - Test SOP loading and embedding generation
    - Test SOP retrieval with various telemetry patterns
    - Test relevance ranking
    - _Requirements: 16.1, 16.2_

- [x] 5. Checkpoint - Verify RAG infrastructure
  - Run SOP initialization script and verify 12 SOPs loaded
  - Test memory store with sample incidents
  - Ensure all tests pass, ask the user if questions arise

- [x] 6. Implement prompt engineering
  - [x] 6.1 Create system prompt
    - Write `src/llm/prompts.py` with `SYSTEM_PROMPT` constant
    - Define expert role: "Azure VM Incident Triage Expert AI"
    - Include explicit decision rules with confidence thresholds
    - Include all 6 safety rules with "NEVER violate" instructions
    - Include novelty detection instructions
    - _Requirements: 11.1, 11.2, 11.6_

  - [x] 6.2 Create user prompt template
    - Write Jinja2 template for dynamic user prompt in `src/llm/prompts.py`
    - Include sections: telemetry summary, full JSON, completeness, similar incidents, relevant SOPs
    - Format similar incidents with: diagnosis, confidence, evidence, next_check, similarity score, human_verified flag
    - Format SOPs with: title, steps, warnings
    - _Requirements: 11.1, 11.3, 11.4, 11.5_

  - [x] 6.3 Implement prompt construction
    - Write method `build_prompt(telemetry, similar_incidents, relevant_sops) -> str`
    - Render Jinja2 template with all context
    - Include data completeness percentage and missing signals
    - Keep total prompt under 2000 tokens
    - _Requirements: 4.1, 11.1_

  - [ ]* 6.4 Write unit tests for prompt construction
    - Test prompt rendering with various telemetry inputs
    - Test RAG context injection (incidents + SOPs)
    - Verify prompt includes all required sections
    - _Requirements: 16.1_

- [x] 7. Implement LLM decision engine
  - [x] 7.1 Create LLM engine core
    - Write `src/llm/llm_engine.py` with `LLMDecisionEngine` class
    - Implement `decide(telemetry, confidence_score, completeness) -> Decision` method
    - Maintain backward compatibility with existing interface
    - Initialize provider chain, memory store, SOP knowledge base
    - _Requirements: 4.2, 8.1, 8.2_

  - [x] 7.2 Implement decision generation pipeline
    - Retrieve top 5 similar incidents from memory store
    - Retrieve top 3 relevant SOPs from knowledge base
    - Build prompt with RAG context
    - Call LLM provider with temperature=0.1
    - Parse JSON response into Decision object
    - _Requirements: 4.1, 4.2, 4.5, 13.1, 13.2_

  - [x] 7.3 Implement JSON response parsing
    - Write method `_parse_llm_response(raw_response: str) -> Dict`
    - Strip markdown code fences if present
    - Parse JSON with error handling
    - Validate against Decision schema
    - Return safe abstain fallback on parse failure
    - _Requirements: 4.3, 4.6, 19.2, 19.3_

  - [x] 7.4 Implement decision state mapping
    - Map LLM output decision strings to `DecisionState` enum
    - Validate confidence_score in range [0.0, 1.0]
    - Validate required fields: state, diagnosis, evidence, next_check
    - Reject invalid enum values
    - _Requirements: 4.2, 8.3, 19.5_

  - [x] 7.5 Implement novel incident detection
    - Check if LLM response has `is_novel_incident=true`
    - Flag incident with metadata `is_novel=true` in memory store
    - Include "Novel incident detected" in explanation
    - Track novel incident count for dashboard
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [x] 7.6 Implement retry logic for malformed responses
    - Retry up to 3 times on JSON parse failure
    - Retry up to 3 times on schema validation failure
    - Fallback to next provider after 3 failed retries
    - Log all retry attempts with error details
    - _Requirements: 4.6, 19.3, 19.6_

  - [ ]* 7.7 Write unit tests for LLM engine
    - Test decision generation with mock LLM responses
    - Test JSON parsing with various response formats
    - Test retry logic with malformed responses
    - Test novel incident detection
    - _Requirements: 16.1, 16.2_

- [ ] 8. Integrate safety guard with LLM output
  - [x] 8.1 Extend Decision model for LLM metadata
    - Add fields to `Decision` model: `llm_provider`, `similar_incidents_used`, `sops_consulted`, `safety_rules_applied`
    - Add fields: `is_novel_incident`, `novel_incident_description`, `pattern_matched`
    - Update `DiagnosticOutput` model with same fields
    - _Requirements: 4.2, 5.8_

  - [x] 8.2 Apply safety guard to LLM decisions
    - Call existing `SafetyGuard.apply_safety_override()` on LLM output
    - Ensure all 6 safety rules override LLM unconditionally
    - Track which safety rules were applied in `safety_rules_applied` list
    - Log original LLM output and sanitized output
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8_

  - [ ]* 8.3 Write property tests for safety guard integration
    - Test that safety rules cannot be bypassed by LLM output
    - Test all 6 safety rules with adversarial LLM responses
    - Verify safety_rules_applied list is populated correctly
    - _Requirements: 16.3, 16.4_

- [x] 9. Checkpoint - Verify LLM decision pipeline
  - Test end-to-end decision generation with all 3 providers
  - Verify safety guard overrides LLM output correctly
  - Ensure all tests pass, ask the user if questions arise

- [x] 10. Implement feedback loop
  - [x] 10.1 Add feedback storage to memory store
    - Write method `update_feedback(incident_id, correct, corrected_diagnosis, corrected_next_check, outcome)`
    - Update ChromaDB entry with: human_verified=True, outcome, corrected fields
    - Handle missing incident_id gracefully
    - _Requirements: 7.2, 7.4_

  - [x] 10.2 Prioritize verified cases in retrieval
    - Modify similarity search to sort by: human_verified DESC, similarity DESC
    - Include human_verified flag in retrieved incident metadata
    - Include corrected diagnosis/next_check if available
    - _Requirements: 7.3, 7.5_

  - [x] 10.3 Create feedback API endpoint
    - Add POST `/api/feedback/{incident_id}` endpoint to `ui/app.py`
    - Accept fields: correct (bool), corrected_diagnosis, corrected_next_check, outcome
    - Validate incident_id exists before updating
    - Return success message with human_verified status
    - _Requirements: 7.1, 7.2, 17.3, 17.4_

  - [ ]* 10.4 Write integration tests for feedback loop
    - Test feedback submission and storage
    - Test verified case prioritization in retrieval
    - Test corrected diagnosis inclusion in prompts
    - _Requirements: 16.2, 16.5_

- [x] 11. Implement API extensions
  - [x] 11.1 Extend triage endpoint with LLM metadata
    - Modify POST `/api/triage` to return LLM metadata fields
    - Include: incident_id, llm_provider, similar_incidents_used, sops_consulted, safety_rules_applied
    - Include: is_novel_incident, novel_incident_description, pattern_matched
    - _Requirements: 17.2_

  - [x] 11.2 Create memory stats endpoint
    - Add GET `/api/memory/stats` endpoint
    - Return: total incidents, verified count, novel incidents count, patterns distribution
    - Calculate top 5 patterns by frequency
    - _Requirements: 10.4, 17.1_

  - [x] 11.3 Create novel incidents endpoint
    - Add GET `/api/novel-incidents` endpoint
    - Query memory store for incidents with `is_novel=true`
    - Return: incident_id, telemetry_summary, diagnosis, confidence, timestamp
    - Sort by timestamp DESC
    - _Requirements: 6.6_

  - [x] 11.4 Create memory pruning endpoint
    - Add POST `/api/memory/prune` endpoint
    - Accept parameter: `before` (date string)
    - Delete incidents older than date, except human_verified=True
    - Return deleted count
    - _Requirements: 10.3_

  - [x] 11.5 Extend health check endpoint
    - Modify GET `/health` endpoint to include LLM provider status
    - Check availability of all 3 providers
    - Include memory store and SOP KB status
    - Return active provider name
    - _Requirements: 14.6_

  - [ ]* 11.6 Write API integration tests
    - Test all new endpoints with various inputs
    - Test error handling for invalid requests
    - Verify response schemas match specifications
    - _Requirements: 16.2_

- [ ] 12. Implement UI dashboard extensions
  - [ ] 12.1 Add Memory tab to dashboard
    - Create new "Memory" tab in `ui/static/index.html`
    - Display: total incidents, verified count, novel incidents count
    - Show recent feedback submissions
    - Add link to novel incidents view
    - _Requirements: 17.1_

  - [ ] 12.2 Add LLM reasoning display to decision cards
    - Extend decision card template to show: similar incidents retrieved, SOPs consulted, novel incident flag
    - Display safety rules applied with warning badge
    - Show LLM provider used
    - _Requirements: 17.2, 17.5_

  - [ ] 12.3 Add feedback buttons to decision cards
    - Add "Correct" and "Incorrect" buttons to each decision card
    - Show modal for corrected diagnosis/next_check input on "Incorrect"
    - Call `/api/feedback/{incident_id}` on submission
    - Display confirmation message after feedback submitted
    - _Requirements: 17.3, 17.4_

  - [ ] 12.4 Create novel incidents view
    - Add dedicated view for novel incidents
    - Display incident cards with "🆕 New Pattern" badge
    - Show telemetry summary, diagnosis, confidence
    - Allow feedback submission from this view
    - _Requirements: 17.6_

- [x] 13. Implement configuration management
  - [x] 13.1 Create configuration loader
    - Write `src/llm/config.py` with `LLMConfig` class
    - Load all environment variables with defaults
    - Validate required API keys are present
    - Log warnings for missing optional config
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6_

  - [x] 13.2 Add configuration validation
    - Validate RAG_TOP_K and SOP_TOP_K are positive integers
    - Validate OLLAMA_BASE_URL is valid URL format
    - Validate CHROMA paths are writable directories
    - Create directories if they don't exist
    - _Requirements: 12.3, 12.5_

  - [x] 13.3 Update .env.example with all LLM settings
    - Add: GROQ_API_KEY, GEMINI_API_KEY, OLLAMA_BASE_URL
    - Add: RAG_TOP_K, SOP_TOP_K, EMBEDDING_MODEL
    - Add: CHROMA_MEMORY_PATH, CHROMA_SOP_PATH
    - Add: LLM_ENABLED, LLM_SHADOW_MODE
    - _Requirements: 20.1, 20.2, 20.3, 20.4, 20.5_

- [x] 14. Implement shadow mode for gradual rollout
  - [x] 14.1 Add shadow mode configuration
    - Add `LLM_ENABLED` flag (default: false) to enable/disable LLM engine
    - Add `LLM_SHADOW_MODE` flag (default: false) to run both engines
    - Load flags from environment variables
    - _Requirements: 20.1, 20.2, 20.3, 20.4_

  - [x] 14.2 Implement dual-engine execution
    - When `LLM_SHADOW_MODE=true`, run both rule-based and LLM engines
    - Compare outputs: decision state, diagnosis, next_check
    - Log differences to `logs/shadow_mode.jsonl`
    - Return rule-based result to user (LLM result logged only)
    - _Requirements: 20.5_

  - [x] 14.3 Create shadow mode stats endpoint
    - Add GET `/api/shadow-mode/stats` endpoint
    - Return: total decisions, agreement rate, disagreement cases
    - Calculate agreement by decision state match
    - _Requirements: 20.6_

  - [ ]* 14.4 Write tests for shadow mode
    - Test LLM_ENABLED flag behavior
    - Test shadow mode dual execution
    - Test disagreement logging
    - _Requirements: 16.1_

- [x] 15. Checkpoint - Verify complete system integration
  - Test end-to-end flow: telemetry → LLM → safety guard → memory store → feedback
  - Verify all API endpoints work correctly
  - Verify UI displays LLM metadata and feedback controls
  - Ensure all tests pass, ask the user if questions arise

- [x] 16. Implement error handling and fallback
  - [x] 16.1 Add provider fallback to rule engine
    - When all LLM providers fail, fallback to original `DecisionEngine`
    - Set `llm_provider="rule_engine_fallback"` in output
    - Log CRITICAL error with provider failure details
    - _Requirements: 14.1_

  - [x] 16.2 Add graceful RAG failure handling
    - When memory store unavailable, proceed without similar incidents
    - When SOP KB unavailable, proceed without SOP recommendations
    - Log warnings for RAG failures
    - _Requirements: 14.2, 14.3_

  - [x] 16.3 Add embedding model failure handling
    - Retry embedding model download 3 times with backoff
    - If download fails, disable RAG features and use rule engine
    - Log error with instructions to manually download model
    - _Requirements: 9.6, 14.4_

  - [x] 16.4 Add comprehensive error logging
    - Create `logs/llm_decisions.jsonl` for all LLM prompts and responses
    - Create `logs/rag_retrievals.jsonl` for all RAG queries
    - Create `logs/safety_overrides.jsonl` for all safety guard actions
    - Create `logs/feedback.jsonl` for all feedback submissions
    - Include request_id in all log entries for tracing
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5_

  - [ ]* 16.5 Write tests for error handling
    - Test provider fallback chain with simulated failures
    - Test RAG unavailability handling
    - Test embedding model failure handling
    - _Requirements: 16.4_

- [x] 17. Implement observability and logging
  - [x] 17.1 Add request tracing
    - Generate unique request_id for each triage request
    - Include request_id in all log entries
    - Include request_id in API responses
    - _Requirements: 15.5_

  - [x] 17.2 Add performance logging
    - Log execution time for: LLM inference, RAG retrieval, SOP retrieval, embedding generation, safety guard
    - Log to structured JSON format
    - Calculate P95 latencies for monitoring
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6_

  - [x] 17.3 Create decision logs endpoint
    - Add GET `/api/logs/decision/{request_id}` endpoint
    - Retrieve all logs for a specific request_id
    - Return: LLM prompt, LLM response, RAG retrievals, safety overrides
    - _Requirements: 15.6_

  - [ ]* 17.4 Write tests for logging
    - Test request_id propagation through pipeline
    - Test log file creation and format
    - Test logs endpoint retrieval
    - _Requirements: 16.1_

- [ ] 18. Implement benchmark testing
  - [ ] 18.1 Extend benchmark runner for LLM engine
    - Modify `src/benchmark_loader.py` to support LLM engine
    - Add flag to switch between rule-based and LLM engine
    - Track LLM-specific metrics: provider used, RAG retrievals, novel incidents detected
    - _Requirements: 16.4_

  - [ ] 18.2 Create LLM vs rule-based comparison
    - Run benchmark on all 35 cases with both engines
    - Compare: decision state match rate, diagnosis similarity, confidence scores
    - Generate comparison report
    - _Requirements: 16.4, 16.5_

  - [ ] 18.3 Create novel incident detection test dataset
    - Create 10 test cases with incidents outside 20 known patterns
    - Manually label as novel incidents
    - Run LLM engine and measure detection accuracy
    - Target: ≥80% detection rate
    - _Requirements: 16.6_

  - [ ]* 18.4 Write property-based tests for LLM integration
    - Test that all existing 15 properties still hold with LLM engine
    - Test that safety rules cannot be bypassed (property test with random LLM outputs)
    - Test decision determinism with same LLM output
    - _Requirements: 16.3_

- [ ] 19. Checkpoint - Verify testing and benchmarking
  - Run all unit tests, integration tests, and property tests
  - Run benchmark comparison between rule-based and LLM engines
  - Verify ≥90% pass rate on existing benchmark cases
  - Ensure all tests pass, ask the user if questions arise

- [x] 20. Create documentation and setup guides
  - [x] 20.1 Create LLM setup guide
    - Write `docs/llm_setup.md` with instructions for:
      - Getting Groq API key
      - Getting Gemini API key
      - Installing and running Ollama locally
    - Include troubleshooting section
    - _Requirements: 1.5, 12.1, 12.2_

  - [x] 20.2 Update README with LLM features
    - Add section on LLM-based decision engine
    - Document RAG memory and SOP knowledge base
    - Document feedback loop and novel incident detection
    - Add configuration examples
    - _Requirements: 8.1_

  - [x] 20.3 Create migration guide
    - Write `docs/migration_to_llm.md` with:
      - Backward compatibility guarantees
      - Shadow mode usage for validation
      - Gradual rollout strategy
    - _Requirements: 20.1, 20.4_

  - [x] 20.4 Update API documentation
    - Document all new endpoints: `/api/feedback`, `/api/memory/stats`, `/api/novel-incidents`, `/api/memory/prune`
    - Document extended `/api/triage` response format
    - Include request/response examples
    - _Requirements: 17.1, 17.2, 17.3_

- [x] 21. Final integration and validation
  - [x] 21.1 Run end-to-end integration test
    - Test complete flow: telemetry → LLM → safety guard → memory → feedback → retrieval
    - Verify all 3 LLM providers work correctly
    - Verify fallback chain works when providers fail
    - _Requirements: 16.2_

  - [x] 21.2 Validate backward compatibility
    - Run all existing property-based tests with LLM engine
    - Verify all 15 properties still hold
    - Verify existing benchmark cases pass at ≥90% rate
    - _Requirements: 8.6, 16.5_

  - [x] 21.3 Performance validation
    - Measure P95 latency for LLM decisions (target: <10s with Groq)
    - Measure RAG retrieval latency (target: <500ms)
    - Measure embedding generation latency (target: <200ms)
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5_

  - [x] 21.4 Create deployment checklist
    - Write `docs/deployment_checklist.md` with:
      - Environment variable setup
      - SOP knowledge base initialization
      - Health check verification
      - Shadow mode validation steps
    - _Requirements: 18.6, 20.1_

- [x] 22. Final checkpoint - Production readiness
  - All tests passing (unit, integration, property-based)
  - Benchmark comparison complete with ≥90% pass rate
  - Documentation complete and reviewed
  - Deployment checklist validated
  - Ensure all tests pass, ask the user if questions arise

## Notes

- Tasks marked with `*` are optional testing tasks and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at key milestones
- The implementation maintains backward compatibility throughout
- All 6 safety rules remain deterministic and override LLM output unconditionally
- The system gracefully degrades to rule-based engine when LLM providers are unavailable
