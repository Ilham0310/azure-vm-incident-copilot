# Shadow Mode Guide

## Overview

Shadow mode allows you to validate LLM accuracy before full deployment by running both the rule-based and LLM engines in parallel. The system compares their outputs, logs differences, and always returns the rule-based result to maintain safety.

## How Shadow Mode Works

When `LLM_SHADOW_MODE=true`:

1. **Dual Execution**: Both rule-based and LLM engines process the same telemetry
2. **Comparison**: The system compares:
   - Decision state (diagnose, diagnose_low_confidence, abstain_request_next_check)
   - Diagnosis text
   - Next check recommendations
3. **Logging**: All comparisons are logged to `logs/shadow_mode.jsonl`
4. **Safe Return**: The rule-based result is always returned to the user (LLM result is logged only)

## Configuration

### Environment Variables

```bash
# Enable shadow mode (requires LLM providers configured)
LLM_SHADOW_MODE=true

# LLM providers (at least one required for shadow mode)
GROQ_API_KEY=your-groq-api-key
GEMINI_API_KEY=your-gemini-api-key
OLLAMA_BASE_URL=http://localhost:11434
```

### Configuration Precedence

- `LLM_SHADOW_MODE=true` takes precedence over `LLM_ENABLED`
- When shadow mode is active, `LLM_ENABLED` is ignored
- Shadow mode always returns rule-based results

## Usage

### 1. Enable Shadow Mode

Edit your `.env` file:

```bash
# Enable shadow mode
LLM_SHADOW_MODE=true

# Configure at least one LLM provider
GROQ_API_KEY=gsk_...
```

### 2. Run Triage Operations

Shadow mode works with all triage operations:

**Single file processing:**
```bash
python main.py --input incident.json
```

**Web UI:**
```bash
python main.py --ui
# Navigate to http://localhost:8000
# Submit telemetry via /api/triage endpoint
```

**Agent mode:**
```bash
python main.py --agent --vm my-vm --rg my-rg
```

### 3. Monitor Shadow Mode Logs

All comparisons are logged to `logs/shadow_mode.jsonl`:

```bash
# View recent comparisons
tail -n 20 logs/shadow_mode.jsonl

# Count total comparisons
wc -l logs/shadow_mode.jsonl

# Find disagreements
grep '"decision_match": false' logs/shadow_mode.jsonl
```

### 4. View Shadow Mode Statistics

Use the API endpoint to get aggregated statistics:

```bash
curl http://localhost:8000/api/shadow-mode/stats
```

**Response:**
```json
{
  "total_decisions": 47,
  "decision_agreement_rate": 89.36,
  "diagnosis_exact_match_rate": 72.34,
  "diagnosis_similar_rate": 91.49,
  "next_check_exact_match_rate": 68.09,
  "disagreement_cases": [
    {
      "timestamp": "2026-04-07T10:30:00Z",
      "vm_name": "prod-web-001",
      "rule_decision": "diagnose",
      "llm_decision": "abstain_request_next_check",
      "rule_diagnosis": "NSG blocks RDP",
      "llm_diagnosis": "Insufficient data for diagnosis",
      "pattern_matched": "nsg_blocks_rdp"
    }
  ]
}
```

## Log Format

Each line in `logs/shadow_mode.jsonl` contains a comparison:

```json
{
  "timestamp": "2026-04-07T10:30:00Z",
  "vm_name": "prod-web-001",
  
  "rule_decision": "diagnose",
  "rule_diagnosis": "High CPU saturation",
  "rule_next_check": "Identify high CPU processes and optimize or scale VM",
  "rule_confidence": 0.82,
  
  "llm_decision": "diagnose",
  "llm_diagnosis": "High CPU usage detected at 98%",
  "llm_next_check": "Follow SOP_Azure VM Scale Up/Down to increase VM capacity",
  "llm_confidence": 0.85,
  "llm_provider": "groq",
  
  "decision_match": true,
  "diagnosis_similarity": "similar",
  "next_check_similarity": "similar",
  
  "completeness": 85.0,
  "pattern_matched": "high_cpu"
}
```

## Interpreting Results

### Agreement Metrics

- **decision_agreement_rate**: Percentage of cases where both engines chose the same decision state
  - Target: ≥90% for production readiness
  - <80%: Review disagreement cases, may need prompt tuning

- **diagnosis_exact_match_rate**: Percentage of exact diagnosis text matches
  - Target: ≥70% for production readiness
  - Lower values are acceptable if diagnosis_similar_rate is high

- **diagnosis_similar_rate**: Percentage of exact or similar diagnoses
  - Target: ≥90% for production readiness
  - Indicates semantic agreement even if wording differs

- **next_check_exact_match_rate**: Percentage of exact next_check matches
  - Target: ≥60% for production readiness
  - LLM may provide more detailed or SOP-specific recommendations

### Disagreement Analysis

When reviewing disagreement cases:

1. **Rule engine more conservative**: LLM chose "diagnose" but rule engine chose "abstain"
   - Common when LLM has higher confidence from RAG context
   - Review if LLM reasoning is sound

2. **LLM more conservative**: Rule engine chose "diagnose" but LLM chose "abstain"
   - May indicate LLM detected ambiguity or conflicting signals
   - Review if LLM concerns are valid

3. **Different diagnoses**: Both chose "diagnose" but with different root causes
   - Review telemetry to determine which is more accurate
   - May indicate novel pattern detected by LLM

## Gradual Rollout Strategy

### Phase 1: Shadow Mode Validation (1-2 weeks)

1. Enable shadow mode with `LLM_SHADOW_MODE=true`
2. Run on production telemetry
3. Monitor agreement rates daily
4. Review disagreement cases
5. Target: ≥90% decision agreement rate

### Phase 2: Selective LLM Deployment (1-2 weeks)

1. Keep shadow mode enabled
2. For high-agreement patterns, consider LLM output
3. Continue monitoring disagreements
4. Collect engineer feedback on LLM diagnoses

### Phase 3: Full LLM Deployment

1. Once agreement rate is stable at ≥90%:
   - Disable shadow mode: `LLM_SHADOW_MODE=false`
   - Enable LLM: `LLM_ENABLED=true`
2. Continue monitoring via feedback loop
3. Keep rule engine as fallback for LLM failures

## Troubleshooting

### Shadow Mode Not Logging

**Symptom**: `logs/shadow_mode.jsonl` is not created

**Solutions**:
- Verify `LLM_SHADOW_MODE=true` in `.env`
- Check that at least one LLM provider is configured
- Ensure `logs/` directory is writable
- Check application logs for errors

### Low Agreement Rate

**Symptom**: `decision_agreement_rate < 80%`

**Solutions**:
- Review disagreement cases for patterns
- Check if LLM is using outdated RAG context
- Verify SOP knowledge base is populated
- Consider prompt tuning for specific patterns
- Check if rule engine patterns need updates

### LLM Failures in Shadow Mode

**Symptom**: Many comparisons show `llm_provider: "error"`

**Solutions**:
- Verify LLM API keys are valid
- Check rate limits (Groq: 30 req/min, Gemini: 1500 req/day)
- Ensure Ollama is running if used as fallback
- Check network connectivity for API providers

### High Latency

**Symptom**: Triage operations take >10 seconds

**Solutions**:
- Shadow mode doubles execution time (runs both engines)
- Use Groq as primary provider (fastest: ~1-2s)
- Consider disabling shadow mode for real-time operations
- Use shadow mode only for batch validation

## Best Practices

1. **Start with small batches**: Test shadow mode on 10-20 cases before full deployment
2. **Monitor daily**: Check agreement rates and disagreements daily during validation
3. **Review disagreements**: Manually review at least 10 disagreement cases
4. **Collect feedback**: Ask engineers to review LLM diagnoses and provide feedback
5. **Gradual rollout**: Don't rush to full LLM deployment; validate thoroughly
6. **Keep rule engine**: Always maintain rule engine as fallback
7. **Document patterns**: Document any new patterns detected by LLM
8. **Update SOPs**: Update SOP knowledge base based on LLM recommendations

## API Reference

### GET /api/shadow-mode/stats

Returns shadow mode statistics.

**Response:**
```json
{
  "total_decisions": 47,
  "decision_agreement_rate": 89.36,
  "diagnosis_exact_match_rate": 72.34,
  "diagnosis_similar_rate": 91.49,
  "next_check_exact_match_rate": 68.09,
  "disagreement_cases": [...]
}
```

**Status Codes:**
- 200: Success
- 500: Error calculating statistics

## Example Workflow

```bash
# 1. Enable shadow mode
echo "LLM_SHADOW_MODE=true" >> .env
echo "GROQ_API_KEY=gsk_..." >> .env

# 2. Start web UI
python main.py --ui

# 3. Run triage operations (via UI or API)
# ...

# 4. Check statistics after 20+ comparisons
curl http://localhost:8000/api/shadow-mode/stats | jq

# 5. Review disagreements
grep '"decision_match": false' logs/shadow_mode.jsonl | jq

# 6. If agreement rate ≥90%, proceed to full LLM deployment
echo "LLM_SHADOW_MODE=false" >> .env
echo "LLM_ENABLED=true" >> .env

# 7. Restart application
python main.py --ui
```

## Safety Guarantees

Shadow mode maintains all safety guarantees:

1. **Rule-based result always returned**: User never sees LLM output in shadow mode
2. **Safety rules enforced**: Both engines apply safety guard
3. **No production impact**: LLM failures don't affect triage results
4. **Audit trail**: All comparisons logged for review
5. **Fallback ready**: Rule engine remains active and tested

## Conclusion

Shadow mode is a critical validation step before full LLM deployment. It allows you to:

- Validate LLM accuracy on real production data
- Identify patterns where LLM excels or struggles
- Build confidence in LLM reasoning
- Maintain safety while testing new capabilities

Take your time with shadow mode validation. A thorough validation period (2-4 weeks) ensures a smooth transition to LLM-based diagnostics.
