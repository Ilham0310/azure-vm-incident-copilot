#!/usr/bin/env python3
"""Run all LLM configs (B, C, D) sequentially with resume support.

Clears stale partial results that were contaminated by rule_engine_fallback
before re-running. Config A (rule engine) is already complete.
"""
import csv
import os
import sys

RESULTS_DIR = "experiments/results"

def count_genuine_llm(path):
    """Count rows with genuine LLM responses (not rule_engine_fallback)."""
    if not os.path.exists(path):
        return 0, 0
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    genuine = sum(1 for r in rows
                  if r.get("provider", "") not in
                  ("rule_engine_fallback", "rule_engine", "?", ""))
    return len(rows), genuine

def should_reset(config_key):
    """Return True if the existing results are too contaminated to keep."""
    path = os.path.join(RESULTS_DIR, f"exp1_{config_key}_detail.csv")
    total, genuine = count_genuine_llm(path)
    if total == 0:
        return False  # nothing to reset
    fallback_pct = (total - genuine) / total * 100
    print(f"  {config_key}: {total} rows, {genuine} genuine LLM, "
          f"{total-genuine} fallback ({fallback_pct:.0f}%)")
    # Reset if more than 50% fell back to rule engine
    return fallback_pct > 50

# Check and optionally reset contaminated configs
print("Checking existing results...")
for cfg in ["config_B", "config_C", "config_D"]:
    path = os.path.join(RESULTS_DIR, f"exp1_{cfg}_detail.csv")
    if should_reset(cfg):
        print(f"  -> Resetting {cfg} (too many fallbacks, will re-run from scratch)")
        os.remove(path)
    else:
        total, genuine = count_genuine_llm(path)
        if total > 0:
            print(f"  -> Keeping {cfg} ({genuine}/{total} genuine, resuming)")

print()

# Now run each config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Import and run the runner
exec(open("experiments/run_llm_configs.py").read().replace(
    'if __name__ == "__main__":', 'if True:'))
