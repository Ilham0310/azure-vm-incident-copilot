#!/usr/bin/env python3
"""Run Config A with safety guard disabled (ablation).

This isolates the safety guard's effect on accuracy by comparing
Config A (with safety) vs Config A-noSafety (without safety).
"""
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

from src.models import TelemetryInput, DecisionState, BenchmarkCase, Decision
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


class DecisionEngineNoSafety(DecisionEngine):
    """Decision engine with safety rules disabled."""
    def _check_safety_rules(self, telemetry, confidence_score):
        return None  # Skip all safety rules


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    loader = BenchmarkLoader()
    cases = loader.load_cases(BENCHMARK_FILE)
    with open(BENCHMARK_FILE, "r", encoding="utf-8") as f:
        raw_rows = {r["case_id"]: r for r in csv.DictReader(f)}

    scorer = ConfidenceScorer()
    engine_safe = DecisionEngine()
    engine_nosafe = DecisionEngineNoSafety()

    configs = [
        ("config_A_safe", "Rule Engine (with safety)", engine_safe),
        ("config_A_nosafe", "Rule Engine (no safety)", engine_nosafe),
    ]

    all_detail = []
    summaries = {}

    for config_key, config_name, engine in configs:
        detail_rows = []
        correct = correct_known = correct_novel = 0
        total_known = total_novel = total_healthy = false_positives = abstain_count = 0

        for case in cases:
            hint = determine_pattern_hint(case.telemetry_input, engine_safe)
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

            if is_correct: correct += 1
            if is_novel:
                total_novel += 1
                if is_correct: correct_novel += 1
            else:
                total_known += 1
                if is_correct: correct_known += 1
            if is_healthy:
                total_healthy += 1
                if actual != expected and actual in ("diagnose", "diagnose_low_confidence"):
                    false_positives += 1
            if actual == "abstain_request_next_check" and expected != "abstain_request_next_check":
                abstain_count += 1

            detail_rows.append({
                "config": config_key,
                "case_id": case.case_id,
                "case_name": case.case_name,
                "expected": expected,
                "actual": actual,
                "correct": str(is_correct),
                "is_novel": str(is_novel),
                "is_healthy": str(is_healthy),
                "confidence": round(confidence, 3),
            })

        total = len(cases)
        summaries[config_key] = {
            "name": config_name,
            "correct": correct,
            "total": total,
            "overall": round(correct / total * 100, 1),
            "correct_known": correct_known,
            "total_known": total_known,
            "known": round(correct_known / total_known * 100, 1) if total_known else 0,
            "correct_novel": correct_novel,
            "total_novel": total_novel,
            "novel": round(correct_novel / total_novel * 100, 1) if total_novel else 0,
            "fp": false_positives,
            "total_healthy": total_healthy,
            "abstain": abstain_count,
        }
        all_detail.extend(detail_rows)

        print(f"{config_name}:")
        print(f"  Overall: {correct}/{total} = {correct/total*100:.1f}%")
        print(f"  Known:   {correct_known}/{total_known} = {correct_known/total_known*100:.1f}%")
        print(f"  Novel:   {correct_novel}/{total_novel} = {correct_novel/total_novel*100:.1f}%")
        print(f"  FP:      {false_positives}/{total_healthy}")
        print(f"  Abstain: {abstain_count}")

    # Paired comparison
    safe_map = {r["case_id"]: r["correct"] == "True"
                for r in all_detail if r["config"] == "config_A_safe"}
    nosafe_map = {r["case_id"]: r["correct"] == "True"
                  for r in all_detail if r["config"] == "config_A_nosafe"}

    b = c = both_ok = both_wrong = 0
    diff_cases = []
    for cid in safe_map:
        s_ok = safe_map[cid]
        n_ok = nosafe_map.get(cid, False)
        if s_ok and n_ok: both_ok += 1
        elif s_ok and not n_ok: c += 1  # safe-only correct
        elif not s_ok and n_ok:
            b += 1  # nosafe-only correct
            diff_cases.append((cid, "nosafe_better"))
        else:
            both_wrong += 1
            diff_cases.append((cid, "both_wrong"))

    print(f"\nPaired comparison (safe vs no-safety):")
    print(f"  both_correct={both_ok}, safe_only={c}, nosafe_only={b}, both_wrong={both_wrong}")
    print(f"  Cases where safety guard changes outcome:")
    for cid, note in diff_cases:
        safe_row = next(r for r in all_detail if r["config"] == "config_A_safe" and r["case_id"] == cid)
        nosafe_row = next(r for r in all_detail if r["config"] == "config_A_nosafe" and r["case_id"] == cid)
        print(f"    {cid}: safe={safe_row['actual']} nosafe={nosafe_row['actual']} expected={safe_row['expected']}")

    # Write results
    with open(os.path.join(RESULTS_DIR, "safety_ablation.json"), "w") as f:
        json.dump(summaries, f, indent=2)
    out_path = os.path.join(RESULTS_DIR, "safety_ablation_detail.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(all_detail[0].keys()))
        writer.writeheader()
        writer.writerows(all_detail)
    print(f"\nResults written to {RESULTS_DIR}/safety_ablation*")


if __name__ == "__main__":
    main()
