"""
Generate diagnostic output schema with 7 required fields.

This module creates a JSON Schema that defines:
- decision (enum: diagnose, diagnose_low_confidence, abstain_request_next_check)
- diagnosis (string)
- confidence_score (number, 0.0-1.0)
- evidence (array of strings)
- evidence_gap (array of strings)
- next_check (string, nullable)
- explanation (string)
"""

import json
import os
from typing import Dict


def generate_output_schema() -> Dict:
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
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "Azure VM Diagnostic Output",
        "description": "Schema for diagnostic output with 7 required fields",
        "type": "object",
        "required": [
            "decision",
            "diagnosis",
            "confidence_score",
            "evidence",
            "evidence_gap",
            "next_check",
            "explanation"
        ],
        "properties": {
            "decision": {
                "type": "string",
                "enum": [
                    "diagnose",
                    "diagnose_low_confidence",
                    "abstain_request_next_check"
                ],
                "description": "Decision state indicating diagnostic confidence level"
            },
            "diagnosis": {
                "type": "string",
                "description": "Human-readable description of the identified issue or healthy state"
            },
            "confidence_score": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Confidence score from 0.0 to 1.0 indicating diagnostic certainty"
            },
            "evidence": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of telemetry signals that support the diagnosis"
            },
            "evidence_gap": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of missing or incomplete telemetry signals needed for higher confidence"
            },
            "next_check": {
                "type": ["string", "null"],
                "description": "Specific diagnostic action to gather more information (required for abstain decisions)"
            },
            "explanation": {
                "type": "string",
                "description": "Multi-sentence reasoning describing why this decision was made"
            }
        },
        "additionalProperties": False
    }
    
    return schema


def write_output_schema_file(schema: Dict, output_path: str = "schemas/output_schema.json"):
    """
    Writes output schema to file if it doesn't already exist (idempotent).
    
    Args:
        schema: Schema dictionary
        output_path: Target file path
    """
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Check if file already exists
    if os.path.exists(output_path):
        print(f"  File already exists, skipping: {output_path}")
        return
    
    # Write schema to file
    with open(output_path, 'w') as f:
        json.dump(schema, f, indent=2)
    
    print(f"  Created: {output_path}")


if __name__ == "__main__":
    schema = generate_output_schema()
    write_output_schema_file(schema)
    print("Output schema generated successfully!")
