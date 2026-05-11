#!/usr/bin/env python3
"""Audit Table 1 by recomputing accuracies from raw detail rows.

Compares recomputed values against the currently-saved summary JSON.
Emits a fresh, self-consistent summary to table1_ablation_audited.json.
"""
import csv
import json
import os
import sys
from collections import defaultdict

RESULTS_DIR = "experiments/results"
DETAIL_CSV = os.path.join(RESULTS_DIR, "exp1_accuracy_comparison.csv")
BENCH_CSV = "data/benchmark_cases_v2.csv"
CURRENT_SUMMARY = os.path.join(RESULTS_DIR, "table1_ablation.json")
AUDITED_OUT = os.path.join(RESULTS_DIR, "table1_ablation_audited.json")


def load_benchmark():
    with open(BENCH_CSV, encoding="utf-8") as f:
        return {r["case_id"]: r for r in csv.DictReader(f)}


def load_detail():
    with open(DETAIL_CSV, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def recompute(detail, bench):
    by_config = defaultdict(list)
    for r in detail:
        by_config[r["config"]].append(r)

    results = {}
    for cfg, cases in sorted(by_config.items()):
        total = len(cases)
        correct = 0
        correct_known = correct_novel = 0
        total_known = total_novel = 0
        total_healthy = false_positives = 0
        abstain_count = 0
        for r in cases:
            bench_row = bench[r["case_id"]]
            is_novel = bench_row["is_novel"].strip().lower() == "true"
            is_healthy = bench_row["incident_pattern"] == "clean"
            is_correct = r["correct"] == "True"
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
                if (r["actual"] != r["expected"]
                        and r["actual"] in ("diagnose", "diagnose_low_confidence")):
                    false_positives += 1
            if (r["actual"] == "abstain_request_next_check"
                    and r["expected"] != "abstain_request_next_check"):
                abstain_count += 1
        results[cfg] = {
            "total_cases": total,
            "correct": correct,
            "correct_known": correct_known,
            "total_known": total_known,
            "correct_novel": correct_novel,
            "total_novel": total_novel,
            "total_healthy": total_healthy,
            "false_positives": false_positives,
            "abstain_count": abstain_count,
            "overall": round(correct / total * 100, 1) if total else 0.0,
            "known": round(correct_known / total_known * 100, 1) if total_known else 0.0,
            "novel": round(correct_novel / total_novel * 100, 1) if total_novel else 0.0,
            "false_positive_rate": round(false_positives / total_healthy * 100, 1) if total_healthy else 0.0,
            "abstain_rate": round(abstain_count / total * 100, 1),
        }
    return results


def build_paired_contingency(detail):
    """Build paired contingency tables comparing Config D to each other config."""
    by_config = defaultdict(dict)
    for r in detail:
        by_config[r["config"]][r["case_id"]] = r["correct"] == "True"
    pairs = {}
    d_map = by_config["config_D"]
    for cfg in ("config_A", "config_B", "config_C"):
        other = by_config[cfg]
        b = c = both_correct = both_wrong = 0
        for cid in d_map:
            d_ok = d_map[cid]
            o_ok = other.get(cid, False)
            if d_ok and o_ok:
                both_correct += 1
            elif d_ok and not o_ok:
                b += 1  # D correct, other wrong
            elif not d_ok and o_ok:
                c += 1  # D wrong, other correct
            else:
                both_wrong += 1
        pairs[f"D_vs_{cfg}"] = {
            "both_correct": both_correct,
            "D_only_correct_b": b,
            "other_only_correct_c": c,
            "both_wrong": both_wrong,
            "n": both_correct + b + c + both_wrong,
        }
    return pairs


def main():
    bench = load_benchmark()
    detail = load_detail()
    if not detail:
        print("No detail rows found. Run experiments first.")
        sys.exit(1)

    print(f"Loaded {len(detail)} detail rows, {len(bench)} benchmark cases")
    print()

    audited = recompute(detail, bench)

    # Load currently-saved summary for comparison
    current = {}
    if os.path.exists(CURRENT_SUMMARY):
        with open(CURRENT_SUMMARY) as f:
            current = json.load(f)

    print("=" * 78)
    print("Audit: recomputed-from-details vs. currently-saved summary")
    print("=" * 78)
    header = f"{'config':10} | {'overall':>12} | {'known':>14} | {'novel':>12} | {'FP':>7} | {'abstain':>9}"
    print(header)
    print("-" * len(header))
    for cfg in ("config_A", "config_B", "config_C", "config_D"):
        a = audited[cfg]
        c = current.get(cfg, {})
        fmt = lambda new, old: (
            f"{new:>5.1f}%" if new == old else f"{new:>5.1f}%(was {old})"
        )
        print(
            f"{cfg:10} | "
            f"{a['correct']}/{a['total_cases']} {a['overall']:>5.1f}% (was {c.get('overall','?')}) | "
            f"{a['correct_known']}/{a['total_known']} {a['known']:>5.1f}% (was {c.get('known','?')}) | "
            f"{a['correct_novel']}/{a['total_novel']} {a['novel']:>5.1f}% (was {c.get('novel','?')}) | "
            f"{a['false_positive_rate']:>5.1f}% | "
            f"{a['abstain_rate']:>5.1f}%"
        )
    print()

    pairs = build_paired_contingency(detail)
    print("=" * 78)
    print("Paired contingency tables (D vs each other config)")
    print("=" * 78)
    for k, v in pairs.items():
        print(f"{k}:")
        print(f"  both_correct = {v['both_correct']}")
        print(f"  D_only_correct (b) = {v['D_only_correct_b']}")
        print(f"  other_only_correct (c) = {v['other_only_correct_c']}")
        print(f"  both_wrong = {v['both_wrong']}")
        print(f"  n = {v['n']}")
    print()

    # Write audited outputs
    with open(AUDITED_OUT, "w") as f:
        json.dump(audited, f, indent=2)
    pairs_out = os.path.join(RESULTS_DIR, "table1_paired_contingency.json")
    with open(pairs_out, "w") as f:
        json.dump(pairs, f, indent=2)
    print(f"Wrote audited summary to {AUDITED_OUT}")
    print(f"Wrote paired contingency to {pairs_out}")


if __name__ == "__main__":
    main()
