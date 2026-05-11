#!/usr/bin/env python3
"""Run Configs B, C, D incrementally with per-case checkpointing.

Each config writes results to its own CSV as it goes, so partial runs
are recoverable.  Skips cases that already have a result row.
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


def _is_novel(raw_rows, case_id):
    for row in raw_rows:
        if row["case_id"] == case_id:
            return row.get("is_novel", "False").strip().lower() == "true"
    return False


def _is_healthy(raw_rows, case_id):
    for row in raw_rows:
        if row["case_id"] == case_id:
            return row.get("incident_pattern", "") == "clean"
    return False


def _determine_pattern_hint(telemetry, rule_engine):
    try:
        match = rule_engine._match_patterns(telemetry)
        return "exact" if match else None
    except Exception:
        return None


def _load_existing(csv_path):
    """Load already-completed case IDs from a checkpoint CSV."""
    done = set()
    if os.path.exists(csv_path):
        with open(csv_path, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                done.add(row["case_id"])
    return done


def _append_row(csv_path, row, fieldnames):
    """Append a single row to the checkpoint CSV (create header if new)."""
    write_header = not os.path.exists(csv_path)
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


FIELDNAMES = [
    "config", "case_id", "case_name", "expected", "actual", "correct",
    "provider", "confidence", "is_novel", "is_healthy", "pattern_hint",
]


def run_config(config_key, config_name, cases, raw_rows, scorer, rule_engine,
               make_engine_fn, rag_top_k, sop_top_k):
    csv_path = os.path.join(RESULTS_DIR, f"exp1_{config_key}_detail.csv")
    done = _load_existing(csv_path)
    print(f"\n{'='*60}")
    print(f"{config_name}: {len(done)} already done, {len(cases)-len(done)} remaining")
    print(f"{'='*60}")

    for i, case in enumerate(cases):
        if case.case_id in done:
            continue
        hint = _determine_pattern_hint(case.telemetry_input, rule_engine)
        completeness, confidence, _ = scorer.score_telemetry(
            case.telemetry_input, pattern_match=hint
        )
        try:
            engine = make_engine_fn()
            engine._rag_top_k = rag_top_k
            engine._sop_top_k = sop_top_k
            time.sleep(2.5)
            decision = engine.decide(case.telemetry_input, confidence, completeness)
            actual = decision.state.value
            provider = getattr(decision, "llm_provider", "llm")
        except Exception as e:
            print(f"  [FALLBACK] {case.case_id}: {type(e).__name__}: {e}")
            decision = rule_engine.decide(case.telemetry_input, confidence, completeness)
            actual = decision.state.value
            provider = "rule_engine_fallback"

        expected = case.expected_decision.value
        is_correct = actual == expected
        is_novel = _is_novel(raw_rows, case.case_id)
        is_healthy = _is_healthy(raw_rows, case.case_id)

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
        _append_row(csv_path, row, FIELDNAMES)
        status = "OK" if is_correct else "WRONG"
        print(f"  [{status}] {i+1}/100 {case.case_id} {case.case_name}: "
              f"expected={expected} got={actual} provider={provider}")

    # Summarise
    with open(csv_path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    total = len(rows)
    correct = sum(1 for r in rows if r["correct"] == "True")
    novel_rows = [r for r in rows if r["is_novel"] == "True"]
    known_rows = [r for r in rows if r["is_novel"] == "False"]
    correct_known = sum(1 for r in known_rows if r["correct"] == "True")
    correct_novel = sum(1 for r in novel_rows if r["correct"] == "True")
    healthy_rows = [r for r in rows if r["is_healthy"] == "True"]
    fp = sum(1 for r in healthy_rows
             if r["correct"] == "False" and r["actual"] in ("diagnose", "diagnose_low_confidence"))
    abstain = sum(1 for r in rows
                  if r["actual"] == "abstain_request_next_check" and r["expected"] != "abstain_request_next_check")
    fallback = sum(1 for r in rows if r["provider"] == "rule_engine_fallback")

    print(f"\n--- {config_name} Summary ---")
    print(f"Overall: {correct}/{total} = {correct/total*100:.1f}%")
    print(f"Known:   {correct_known}/{len(known_rows)} = {correct_known/len(known_rows)*100:.1f}%")
    print(f"Novel:   {correct_novel}/{len(novel_rows)} = {correct_novel/len(novel_rows)*100:.1f}%")
    print(f"FP rate: {fp}/{len(healthy_rows)} = {fp/len(healthy_rows)*100:.1f}%")
    print(f"Abstain: {abstain}/{total} = {abstain/total*100:.1f}%")
    print(f"Fallback to rule engine: {fallback}/{total}")

    summary = {
        config_key: {
            "name": config_name,
            "total_cases": total, "correct": correct,
            "correct_known": correct_known, "total_known": len(known_rows),
            "correct_novel": correct_novel, "total_novel": len(novel_rows),
            "total_healthy": len(healthy_rows), "false_positives": fp,
            "abstain_count": abstain, "fallback_count": fallback,
            "overall": round(correct / total * 100, 1),
            "known": round(correct_known / len(known_rows) * 100, 1) if known_rows else 0,
            "novel": round(correct_novel / len(novel_rows) * 100, 1) if novel_rows else 0,
            "false_positive_rate": round(fp / len(healthy_rows) * 100, 1) if healthy_rows else 0,
            "abstain_rate": round(abstain / total * 100, 1),
        }
    }
    with open(os.path.join(RESULTS_DIR, f"exp1_{config_key}_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    return summary[config_key]


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    loader = BenchmarkLoader()
    cases = loader.load_cases(BENCHMARK_FILE)
    with open(BENCHMARK_FILE, "r", encoding="utf-8") as f:
        raw_rows = list(csv.DictReader(f))

    scorer = ConfidenceScorer()
    rule_engine = DecisionEngine()

    from src.llm.llm_engine import LLMDecisionEngine

    # Config B: LLM only (no RAG, no SOP)
    run_config("config_B", "LLM Only", cases, raw_rows, scorer, rule_engine,
               LLMDecisionEngine, rag_top_k=0, sop_top_k=0)

    # Config C: LLM + SOP RAG (no incident memory)
    run_config("config_C", "LLM + SOP RAG", cases, raw_rows, scorer, rule_engine,
               LLMDecisionEngine, rag_top_k=0, sop_top_k=3)

    # Config D: Full System
    run_config("config_D", "Full System", cases, raw_rows, scorer, rule_engine,
               LLMDecisionEngine, rag_top_k=5, sop_top_k=3)

    print("\n" + "=" * 60)
    print("All configs complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
