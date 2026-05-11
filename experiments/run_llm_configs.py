#!/usr/bin/env python3
"""Run LLM configs (B, C, D) one at a time with robust error handling.

Writes per-case detail to separate CSVs so partial runs are preserved.
Uses 3-second delays between calls to respect Groq free-tier limits.
"""
import csv
import json
import os
import ssl
import sys
import time
import urllib3

os.environ["CURL_CA_BUNDLE"] = ""
os.environ["REQUESTS_CA_BUNDLE"] = ""
os.environ["SSL_CERT_FILE"] = ""
ssl._create_default_https_context = ssl._create_unverified_context
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

from src.models import TelemetryInput, DecisionState, BenchmarkCase
from src.confidence_scorer import ConfidenceScorer
from src.decision_engine import DecisionEngine
from src.benchmark_loader import BenchmarkLoader

BENCHMARK_FILE = "data/benchmark_cases_v2.csv"
RESULTS_DIR = "experiments/results"
DELAY_BETWEEN_CALLS = 5.0


def determine_pattern_hint(telemetry, rule_engine):
    try:
        match = rule_engine._match_patterns(telemetry)
        return "exact" if match else None
    except Exception:
        return None


def run_single_config(config_key, config_name, cases, raw_rows, scorer,
                      rule_engine, rag_top_k, sop_top_k):
    """Run one LLM config across all cases, writing results incrementally."""
    out_path = os.path.join(RESULTS_DIR, f"exp1_{config_key}_detail.csv")

    # Check for existing partial results to resume
    done_ids = set()
    existing_rows = []
    if os.path.exists(out_path):
        with open(out_path, encoding="utf-8") as f:
            existing_rows = list(csv.DictReader(f))
            done_ids = {r["case_id"] for r in existing_rows}
        print(f"  Resuming {config_key}: {len(done_ids)} cases already done")

    detail_rows = list(existing_rows)
    fieldnames = [
        "config", "case_id", "case_name", "expected", "actual", "correct",
        "provider", "confidence", "is_novel", "is_healthy", "pattern_hint",
    ]

    remaining = [c for c in cases if c.case_id not in done_ids]
    print(f"  {config_name}: {len(remaining)} cases remaining")

    for i, case in enumerate(remaining):
        hint = determine_pattern_hint(case.telemetry_input, rule_engine)
        completeness, confidence, _ = scorer.score_telemetry(
            case.telemetry_input, pattern_match=hint
        )

        bench_row = raw_rows[case.case_id]
        is_novel = bench_row["is_novel"].strip().lower() == "true"
        is_healthy = bench_row["incident_pattern"] == "clean"

        try:
            from src.llm.llm_engine import LLMDecisionEngine
            engine = LLMDecisionEngine()
            engine._rag_top_k = rag_top_k
            engine._sop_top_k = sop_top_k
            decision = engine.decide(case.telemetry_input, confidence, completeness)
            actual = decision.state.value
            provider = getattr(decision, "llm_provider", "llm")
        except Exception as e:
            print(f"    LLM failed for {case.case_id}: {e}. Falling back to rule engine.")
            decision = rule_engine.decide(case.telemetry_input, confidence, completeness)
            actual = decision.state.value
            provider = "rule_engine_fallback"

        expected = case.expected_decision.value
        is_correct = actual == expected

        row = {
            "config": config_key,
            "case_id": case.case_id,
            "case_name": case.case_name,
            "expected": expected,
            "actual": actual,
            "correct": str(is_correct),
            "provider": provider,
            "confidence": round(confidence, 3),
            "is_novel": str(is_novel),
            "is_healthy": str(is_healthy),
            "pattern_hint": hint or "none",
        }
        detail_rows.append(row)

        # Write incrementally after each case
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(detail_rows)

        status = "OK" if is_correct else "WRONG"
        print(f"    [{i+1+len(done_ids)}/{len(cases)}] {case.case_id} "
              f"{status} expected={expected} got={actual} provider={provider}")

        time.sleep(DELAY_BETWEEN_CALLS)

    # Summary
    correct = sum(1 for r in detail_rows if r["correct"] == "True")
    total = len(detail_rows)
    print(f"\n  {config_name} DONE: {correct}/{total} = {correct/total*100:.1f}%")
    return detail_rows


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    loader = BenchmarkLoader()
    cases = loader.load_cases(BENCHMARK_FILE)
    with open(BENCHMARK_FILE, "r", encoding="utf-8") as f:
        raw_rows = {r["case_id"]: r for r in csv.DictReader(f)}

    scorer = ConfidenceScorer()
    rule_engine = DecisionEngine()

    # Which config to run (pass as CLI arg, or run all)
    target = sys.argv[1] if len(sys.argv) > 1 else "all"

    configs = {
        "config_B": ("LLM Only", 0, 0),
        "config_C": ("LLM + SOP RAG", 0, 3),
        "config_D": ("Full System", 5, 3),
    }

    if target != "all":
        if target not in configs:
            print(f"Unknown config: {target}. Use config_B, config_C, config_D, or all")
            sys.exit(1)
        configs = {target: configs[target]}

    for config_key, (name, rag_k, sop_k) in configs.items():
        print(f"\n{'='*60}")
        print(f"Running {name} ({config_key})")
        print(f"  rag_top_k={rag_k}, sop_top_k={sop_k}")
        print(f"{'='*60}")
        run_single_config(config_key, name, cases, raw_rows, scorer,
                          rule_engine, rag_k, sop_k)


if __name__ == "__main__":
    main()
