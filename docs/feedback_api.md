# Feedback API Documentation

## Overview

The Feedback API allows engineers to provide feedback on LLM-generated diagnoses, enabling the system to learn from corrections and improve over time. Feedback is stored in the ChromaDB memory store and prioritized in future similar incident retrievals.

## Endpoint

```
POST /api/feedback/{incident_id}
```

### Path Parameters

- `incident_id` (string, required): The 12-character hex identifier returned in the triage response

### Request Body

```json
{
  "correct": boolean,
  "corrected_diagnosis": string (optional),
  "corrected_next_check": string (optional),
  "outcome": string (default: "resolved")
}
```

#### Fields

- **correct** (boolean, required): Whether the LLM diagnosis was correct
  - `true`: The diagnosis and next_check were accurate
  - `false`: The diagnosis or next_check needs correction

- **corrected_diagnosis** (string, optional): The corrected diagnosis if `correct=false`
  - Provide the accurate root cause description
  - This will be stored and used in future similar incidents

- **corrected_next_check** (string, optional): The corrected next_check if `correct=false`
  - Provide the correct remediation steps
  - This will be stored and used in future similar incidents

- **outcome** (string, default: "resolved"): The outcome of the incident
  - `"resolved"`: Issue was successfully resolved
  - `"escalated"`: Issue required escalation to higher tier
  - `"false_positive"`: Not actually an incident

### Response

#### Success (200 OK)

```json
{
  "status": "ok",
  "message": "Feedback recorded. Future similar incidents will benefit from this correction.",
  "incident_id": "a3f7c9d2e1b4",
  "human_verified": true
}
```

#### Incident Not Found (404)

```json
{
  "error": "Incident not found",
  "incident_id": "nonexistent123"
}
```

#### Validation Error (422)

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "correct"],
      "msg": "Field required"
    }
  ]
}
```

#### Server Error (500)

```json
{
  "detail": "Internal server error message"
}
```

## Usage Examples

### Example 1: Marking Diagnosis as Correct

```bash
curl -X POST http://localhost:8000/api/feedback/a3f7c9d2e1b4 \
  -H "Content-Type: application/json" \
  -d '{
    "correct": true,
    "outcome": "resolved"
  }'
```

**Response:**
```json
{
  "status": "ok",
  "message": "Feedback recorded. Future similar incidents will benefit from this correction.",
  "incident_id": "a3f7c9d2e1b4",
  "human_verified": true
}
```

### Example 2: Providing Corrected Diagnosis

```bash
curl -X POST http://localhost:8000/api/feedback/b4e8d3f1a2c5 \
  -H "Content-Type: application/json" \
  -d '{
    "correct": false,
    "corrected_diagnosis": "The VM agent failed due to a corrupted extension, not a simple service stop.",
    "corrected_next_check": "Remove and reinstall the Microsoft.Azure.Monitor extension via portal > Extensions.",
    "outcome": "resolved"
  }'
```

**Response:**
```json
{
  "status": "ok",
  "message": "Feedback recorded. Future similar incidents will benefit from this correction.",
  "incident_id": "b4e8d3f1a2c5",
  "human_verified": true
}
```

### Example 3: Python Client

```python
import requests

def submit_feedback(incident_id, correct, corrected_diagnosis=None, corrected_next_check=None, outcome="resolved"):
    """Submit feedback for an incident."""
    response = requests.post(
        f"http://localhost:8000/api/feedback/{incident_id}",
        json={
            "correct": correct,
            "corrected_diagnosis": corrected_diagnosis,
            "corrected_next_check": corrected_next_check,
            "outcome": outcome
        }
    )
    return response.json()

# Mark as correct
result = submit_feedback("a3f7c9d2e1b4", correct=True)
print(result)

# Provide corrections
result = submit_feedback(
    "b4e8d3f1a2c5",
    correct=False,
    corrected_diagnosis="VM agent failed due to corrupted extension",
    corrected_next_check="Remove and reinstall the extension",
    outcome="resolved"
)
print(result)
```

## How Feedback Improves the System

### 1. Human Verification Flag

When feedback is submitted, the incident is marked with `human_verified=True` in the memory store. This flag is used to prioritize verified cases in future retrievals.

### 2. Corrected Versions Storage

If `correct=false`, the corrected diagnosis and next_check are stored as alternative versions:
- Original LLM output is preserved
- Corrected versions are stored in separate fields
- Both versions are available for future reference

### 3. Prioritized Retrieval

When the LLM processes a new incident:
1. RAG retrieves the top 5 most similar past incidents
2. Results are sorted by: `human_verified DESC, similarity DESC`
3. Verified cases appear first in the prompt context
4. LLM sees: "Past incident (similarity: 0.91, human_verified: True)"
5. LLM produces higher-confidence, more accurate diagnoses

### 4. Learning Loop

```
Cycle 1: New incident occurs
    → LLM makes initial diagnosis
    → Stored as pending

Cycle 2: Engineer reviews → marks ✓ Correct
    → outcome = "resolved", human_verified = True

Cycle 3: Similar incident occurs
    → RAG finds verified case (similarity 0.89)
    → LLM prompt includes verified diagnosis
    → LLM produces more accurate diagnosis
```

## Integration with UI Dashboard

The feedback API is designed to be integrated with the web dashboard:

1. Each decision card displays feedback buttons: "Correct" and "Incorrect"
2. Clicking "Incorrect" opens a modal for corrected diagnosis/next_check input
3. Feedback is submitted via the API
4. Confirmation message is displayed
5. Incident entry is updated with "✓ Verified" badge

## Testing

### Unit Tests

Run the unit tests:
```bash
python -m pytest tests/unit/test_feedback_api.py -v
```

### Manual Testing

1. Start the UI server:
```bash
python main.py --ui
```

2. Run the manual test script:
```bash
python test_feedback_manual.py
```

This will:
- Create test incidents in the memory store
- Submit feedback via the API
- Verify feedback was stored correctly
- Test error cases (non-existent incident)

## Requirements Validation

This implementation satisfies the following requirements:

- **Requirement 7.1**: API endpoint `/api/feedback` accepting POST requests ✓
- **Requirement 7.2**: Updates RAG_Memory entry with feedback metadata ✓
- **Requirement 7.3**: Prioritizes incidents marked as "correct" in retrieval ✓
- **Requirement 7.4**: Stores corrected diagnosis and next_check ✓
- **Requirement 17.3**: Feedback buttons in dashboard (API ready) ✓
- **Requirement 17.4**: Confirmation message after feedback (API ready) ✓

## Related Documentation

- [Memory Store Implementation](../src/rag/memory_store.py)
- [API Specifications](../docs/api_specs.md)
- [LLM Decision Engine Design](../.kiro/specs/llm-decision-engine-with-rag/design.md)
