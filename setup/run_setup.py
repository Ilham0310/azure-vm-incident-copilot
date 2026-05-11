#!/usr/bin/env python3
"""
Standalone setup runner for Azure VM Incident Copilot.

This script generates all required configuration files:
- schemas/azure_vm_triage_schema.json
- schemas/output_schema.json
- policy/decision_policy.json
- data/benchmark_cases.csv

Can be run directly: python setup/run_setup.py
Does NOT depend on main.py or any src/ components.
"""

import os
import sys


def run_setup():
    """
    Run all setup generators in sequence.
    
    Creates directories if they don't exist.
    Logs which files were created vs skipped (idempotency).
    """
    print("=" * 60)
    print("Azure VM Incident Copilot - Setup")
    print("=" * 60)
    print()
    
    # Import generators (they are in the same directory)
    try:
        from generate_schema import generate_triage_schema, write_schema_file
        from generate_output_schema import generate_output_schema, write_output_schema_file
        from generate_policy import generate_decision_policy, write_policy_file
        from generate_benchmark import generate_benchmark_cases, write_benchmark_file
    except ImportError as e:
        print(f"ERROR: Failed to import setup generators: {e}")
        print("Make sure all generator scripts exist in the setup/ directory.")
        return 1
    
    # Step 1: Generate triage schema
    print("Step 1/4: Generating triage schema...")
    try:
        schema = generate_triage_schema()
        write_schema_file(schema)
        print()
    except Exception as e:
        print(f"ERROR: Failed to generate triage schema: {e}")
        return 1
    
    # Step 2: Generate output schema
    print("Step 2/4: Generating output schema...")
    try:
        output_schema = generate_output_schema()
        write_output_schema_file(output_schema)
        print()
    except Exception as e:
        print(f"ERROR: Failed to generate output schema: {e}")
        return 1
    
    # Step 3: Generate decision policy
    print("Step 3/4: Generating decision policy...")
    try:
        policy = generate_decision_policy()
        write_policy_file(policy)
        print()
    except Exception as e:
        print(f"ERROR: Failed to generate decision policy: {e}")
        return 1
    
    # Step 4: Generate benchmark cases
    print("Step 4/4: Generating benchmark cases...")
    try:
        cases = generate_benchmark_cases()
        write_benchmark_file(cases)
        print()
    except Exception as e:
        print(f"ERROR: Failed to generate benchmark cases: {e}")
        return 1
    
    print("=" * 60)
    print("Setup complete!")
    print("=" * 60)
    print()
    print("Generated files:")
    print("  - schemas/azure_vm_triage_schema.json")
    print("  - schemas/output_schema.json")
    print("  - policy/decision_policy.json")
    print("  - data/benchmark_cases.csv")
    print()
    print("You can now run the system:")
    print("  python main.py --input incident.json")
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(run_setup())
