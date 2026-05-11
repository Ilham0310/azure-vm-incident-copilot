"""
Generate decision policy with rules A, B, C and 6 safety rules.

This module creates a JSON file containing:
- Decision rules A, B, C with exact thresholds
- 6 safety rules with conditions and actions
- Confidence scoring weights (40% completeness, 30% pattern, 30% consistency)
"""

import json
import os
from typing import Dict


def generate_decision_policy() -> Dict:
    """
    Generates the decision policy with rules A, B, C and 6 safety rules.
    
    Returns:
        Dictionary with:
        - rules: {A: {...}, B: {...}, C: {...}}
        - safety_rules: [{name, condition, action}, ...]
        - thresholds: {diagnose_confidence: 0.7, ...}
    """
    policy = {
        "version": "1.0",
        "description": "Decision policy for Azure VM incident triage",
        
        # Decision thresholds
        "thresholds": {
            "diagnose_confidence_min": 0.70,
            "diagnose_completeness_min": 90,
            "diagnose_low_confidence_min": 0.40,
            "diagnose_low_confidence_max": 0.69,
            "diagnose_low_completeness_min": 60,
            "diagnose_low_completeness_max": 89,
            "abstain_completeness_max": 59,
            "high_confidence_destructive_min": 0.9
        },
        
        # Confidence scoring weights
        "confidence_weights": {
            "completeness": 0.4,
            "pattern_match": 0.3,
            "signal_consistency": 0.3
        },
        
        # Pattern match weights
        "pattern_match_weights": {
            "exact": 0.3,
            "partial": 0.15,
            "none": 0.0
        },
        
        # Signal consistency weights
        "signal_consistency_weights": {
            "no_conflicts": 0.3,
            "minor_conflicts": 0.15,
            "major_conflicts": 0.0
        },
        
        # Decision rules
        "rules": {
            "A": {
                "name": "diagnose",
                "description": "High confidence diagnosis with complete data",
                "conditions": [
                    "confidence_score >= 0.70",
                    "data_completeness >= 90%",
                    "no conflicting signals (or conflicts fully explained)",
                    "root cause maps to one known incident pattern",
                    "remediation is safe and reversible (if suggested)",
                    "no safety rule violations"
                ]
            },
            "B": {
                "name": "diagnose_low_confidence",
                "description": "Low confidence diagnosis with partial data",
                "conditions": [
                    "confidence_score >= 0.40 and < 0.70",
                    "data_completeness 60-89%",
                    "minor signal conflicts that can be partially explained",
                    "root cause is probable but not certain",
                    "no safety rule violations"
                ]
            },
            "C": {
                "name": "abstain_request_next_check",
                "description": "Insufficient data or safety rule violation",
                "conditions": [
                    "confidence_score < 0.40, OR",
                    "data_completeness < 60%, OR",
                    "critical signals missing or unknown, OR",
                    "severe unresolvable signal conflict, OR",
                    "platform-initiated event detected, OR",
                    "any safety rule violation detected"
                ]
            }
        },
        
        # Safety rules (hard constraints)
        "safety_rules": [
            {
                "id": 1,
                "name": "Platform Event Safety",
                "condition": "resource_health_annotation contains platform event keywords",
                "keywords": ["platform", "maintenance", "host update", "planned maintenance"],
                "action": "abstain_request_next_check",
                "restrictions": [
                    "Never suggest VM restart in next_check during platform events"
                ]
            },
            {
                "id": 2,
                "name": "Boot Failure Safety",
                "condition": "boot_diagnostics_status in [BSOD, KernelPanic]",
                "action": "Never suggest restart in next_check",
                "restrictions": [
                    "Never suggest VM restart for BSOD",
                    "Never suggest VM restart for KernelPanic",
                    "These indicate OS-level failures requiring investigation"
                ]
            },
            {
                "id": 3,
                "name": "Low Confidence Destructive Action Safety",
                "condition": "confidence_score < 0.9 AND diagnosis suggests destructive actions",
                "action": "Remove destructive actions from next_check",
                "destructive_actions": [
                    "disk deletion",
                    "OS reset",
                    "VM deletion",
                    "configuration reset"
                ]
            },
            {
                "id": 4,
                "name": "Network Security Safety",
                "condition": "Always enforced",
                "action": "Never suggest in next_check",
                "restrictions": [
                    "Never suggest disabling NSG rules",
                    "Never suggest disabling firewall rules",
                    "Network security changes require manual review"
                ]
            },
            {
                "id": 5,
                "name": "Disk Safety",
                "condition": "confidence_score < 0.9",
                "action": "Never suggest in next_check",
                "restrictions": [
                    "Never suggest disk deletion when confidence < 0.9",
                    "Never suggest OS reset when confidence < 0.9",
                    "Data integrity requires high confidence"
                ]
            },
            {
                "id": 6,
                "name": "Failed State Safety",
                "condition": "power_state = Failed AND provisioning_state = Failed",
                "action": "Never suggest auto-remediation in next_check",
                "restrictions": [
                    "Failed states require manual investigation",
                    "Failed states require Azure support"
                ]
            }
        ],
        
        # Critical signals (must be present for high confidence)
        "critical_signals": [
            "power_state",
            "provisioning_state",
            "resource_health_status"
        ]
    }
    
    return policy


def write_policy_file(policy: Dict, output_path: str = "policy/decision_policy.json"):
    """
    Writes policy to file if it doesn't already exist (idempotent).
    
    Args:
        policy: Policy dictionary
        output_path: Target file path
    """
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Check if file already exists
    if os.path.exists(output_path):
        print(f"  File already exists, skipping: {output_path}")
        return
    
    # Write policy to file
    with open(output_path, 'w') as f:
        json.dump(policy, f, indent=2)
    
    print(f"  Created: {output_path}")


if __name__ == "__main__":
    policy = generate_decision_policy()
    write_policy_file(policy)
    print("Decision policy generated successfully!")
