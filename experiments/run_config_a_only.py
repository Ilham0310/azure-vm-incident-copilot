#!/usr/bin/env python3
"""Run ONLY Config A (rule engine) with corrected pattern hints.

This is fast (~5 seconds) and produces per-case detail with honest
pattern_match hints (None for novel cases instead of hardcoded 'exact').
"""
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

from src.models import TelemetryInput, DecisionState, BenchmarkCase
from src.confidence_scorer import ConfidenceScorer
from src.decision_engine import DecisionEngine
from src.benchmark_loader import BenchmarkLoader

BENCHMARK_FILE = "data/benchmark_cases_v2.csv"
RESULTS_DIR = "experiments/results"


def determine_pattern_hint(telemetry, rule_engine):
    try:
        match = rule_engine._match_patterns(telemetry)
        return "exact" if match else None
    except Exception:
        return None


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    loader = BenchmarkLoader()
    cases = loader.load_cases(BENCHMARK_FILE)
    with open(BENCHMARK_FILE, "r", encoding="utf-8") as f:
        raw_rows = {r["case_id"]: r for r in csv.DictReader(f)}

    scorer = ConfidenceScorer()
    engine = DecisionEngine()

    detail_rows = []
    correct = correct_known = correct_novel = 0
    total_known = total_novel = total_healthy = false_positives = abstain_count = 0

    for case in cases:
        hint = determine_pattern_hint(case.telemetry_input, engine)
        completeness, confidence, conflicts = scorer.score_telemetry(
            case.telemetry_input, pattern_match=hint
        )
        decision = engine.decide(case.telemetry_input, confidence, completeness)
        actual = decision.state.value
        expected = case.expected_decision.value
        is_correct = actual == expected

        bench_row = raw_rows[case.case_id]
        is_novel = bench_row["is_novel"].strip().lower() == "true"
        is_healthy = bench_row["incident_pattern"] == "clean"

        if is_correct:
            correct += 1
        if is_novel:
            total_novel += 1
            if is_correct:
                correct_novel += 1
        else:
            total_known += 1
            if is_correct:
                correct_known += 1
        if is_healthy:
            total_healthy += 1
            if actual != expected and actual in ("diagnose", "diagnose_low_confidence"):
                false_positives += 1
        if actual == "abstain_request_next_check" and expected != "abstain_request_next_check":
            abstain_count += 1

        detail_rows.append({
            "config": "config_A",
            "case_id": case.case_id,
            "case_name": case.case_name,
            "expected": expected,
            "actual": actual,
            "correct": str(is_correct),
            "provider": "rule_engine",
            "confidence": round(confidence, 3),
            "is_novel": str(is_novel),
            "is_healthy": str(is_healthy),
            "pattern_hint": hint or "none",
            "completeness": round(completeness, 1),
            "conflicts": conflicts,
        })

    total = len(cases)
    print(f"Config A (corrected pattern hints):")
    print(f"  Overall: {correct}/{total} = {correct/total*100:.1f}%")
    print(f"  Known:   {correct_known}/{total_known} = {correct_known/total_known*100:.1f}%")
    print(f"  Novel:   {correct_novel}/{total_novel} = {correct_novel/total_novel*100:.1f}%")
    print(f"  FP rate: {false_positives}/{total_healthy} = {false_positives/total_healthy*100:.1f}%")
    print(f"  Abstain: {abstain_count}")

    # Show novel cases in detail
    print(f"\nNovel case detail:")
    for r in detail_rows:
        if r["is_novel"] == "True":
            print(f"  {r['case_id']} {r['case_name']}: "
                  f"expected={r['expected']} actual={r['actual']} "
                  f"hint={r['pattern_hint']} conf={r['confidence']} "
                  f"correct={r['correct']}")

    # Show incorrect cases
    incorrect = [r for r in detail_rows if r["correct"] == "False"]
    print(f"\nIncorrect cases ({len(incorrect)}):")
    for r in incorrect:
        print(f"  {r['case_id']} {r['case_name']}: "
              f"expected={r['expected']} actual={r['actual']} "
              f"hint={r['pattern_hint']} conf={r['confidence']} "
              f"novel={r['is_novel']}")

    # Write detail CSV
    out_path = os.path.join(RESULTS_DIR, "exp1_config_a_corrected.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(detail_rows[0].keys()))
        writer.writeheader()
        writer.writerows(detail_rows)
    print(f"\nDetail written to {out_path}")


if __name__ == "__main__":
    main()
