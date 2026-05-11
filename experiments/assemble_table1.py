#!/usr/bin/env python3
"""Assemble final Table 1 from per-config detail CSVs.

Reads exp1_config_{A,B,C,D}_detail.csv, computes honest per-group
accuracies with explicit denominators, and writes:
  - table1_ablation.json (audited summary)
  - exp1_accuracy_comparison.csv (merged detail)
  - PAPER_RESULTS_SUMMARY.md (updated)
"""
import csv
import json
import os
import sys
from collections import defaultdict

RESULTS_DIR = "experiments/results"
CONFIGS = ["config_A", "config_B", "config_C", "config_D"]
LABELS = {
    "config_A": "Rule Engine (baseline)",
    "config_B": "LLM Only",
    "config_C": "LLM + SOP RAG",
    "config_D": "Full System (ours)",
}


def load_detail(config_key):
    path = os.path.join(RESULTS_DIR, f"exp1_{config_key}_detail.csv")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def summarise(rows, config_key):
    total = len(rows)
    correct = sum(1 for r in rows if r["correct"] == "True")
    novel = [r for r in rows if r.get("is_novel") == "True"]
    known = [r for r in rows if r.get("is_novel") == "False"]
    healthy = [r for r in rows if r.get("is_healthy") == "True"]
    correct_known = sum(1 for r in known if r["correct"] == "True")
    correct_novel = sum(1 for r in novel if r["correct"] == "True")
    fp = sum(1 for r in healthy
             if r["correct"] == "False" and r["actual"] in ("diagnose", "diagnose_low_confidence"))
    abstain = sum(1 for r in rows
                  if r["actual"] == "abstain_request_next_check" and r["expected"] != "abstain_request_next_check")
    fallback = sum(1 for r in rows if r.get("provider") == "rule_engine_fallback")
    return {
        "name": LABELS[config_key],
        "total_cases": total,
        "correct": correct,
        "correct_known": correct_known,
        "total_known": len(known),
        "correct_novel": correct_novel,
        "total_novel": len(novel),
        "total_healthy": len(healthy),
        "false_positives": fp,
        "abstain_count": abstain,
        "fallback_count": fallback,
        "overall": round(correct / total * 100, 1) if total else 0,
        "known": round(correct_known / len(known) * 100, 1) if known else 0,
        "novel": round(correct_novel / len(novel) * 100, 1) if novel else 0,
        "false_positive_rate": round(fp / len(healthy) * 100, 1) if healthy else 0,
        "abstain_rate": round(abstain / total * 100, 1) if total else 0,
    }


def main():
    all_detail = []
    summary = {}
    missing = []

    for cfg in CONFIGS:
        rows = load_detail(cfg)
        if rows is None or len(rows) < 100:
            count = len(rows) if rows else 0
            missing.append(f"{cfg} ({count}/100)")
            continue
        all_detail.extend(rows)
        s = summarise(rows, cfg)
        summary[cfg] = s
        print(f"{LABELS[cfg]:25s}: {s['correct']}/{s['total_cases']} = {s['overall']}% overall, "
              f"known {s['correct_known']}/{s['total_known']} = {s['known']}%, "
              f"novel {s['correct_novel']}/{s['total_novel']} = {s['novel']}%, "
              f"FP {s['false_positives']}/{s['total_healthy']}, "
              f"abstain {s['abstain_count']}, fallback {s['fallback_count']}")

    if missing:
        print(f"\nWARNING: incomplete configs: {', '.join(missing)}")
        print("Table 1 will be partial. Re-run after all configs complete.")

    # Write merged detail CSV
    if all_detail:
        merged_path = os.path.join(RESULTS_DIR, "exp1_accuracy_comparison.csv")
        fieldnames = list(all_detail[0].keys())
        with open(merged_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_detail)
        print(f"\nMerged detail CSV: {merged_path} ({len(all_detail)} rows)")

    # Write summary JSON
    for fname in ["table1_ablation.json", "exp1_summary.json"]:
        with open(os.path.join(RESULTS_DIR, fname), "w") as f:
            json.dump(summary, f, indent=2)

    # Write markdown summary
    lines = [
        "# Evaluation Results — Azure VM Incident Copilot (Audited)",
        "",
        "## Table 1: Accuracy Comparison (Experiment 1)",
        "",
        "| Configuration | Overall | Known (n) | Novel (n) | FP Rate | Abstain | Fallback |",
        "|---|---|---|---|---|---|---|",
    ]
    for cfg in CONFIGS:
        if cfg in summary:
            s = summary[cfg]
            lines.append(
                f"| {LABELS[cfg]} | {s['correct']}/{s['total_cases']} ({s['overall']}%) "
                f"| {s['correct_known']}/{s['total_known']} ({s['known']}%) "
                f"| {s['correct_novel']}/{s['total_novel']} ({s['novel']}%) "
                f"| {s['false_positives']}/{s['total_healthy']} ({s['false_positive_rate']}%) "
                f"| {s['abstain_count']} ({s['abstain_rate']}%) "
                f"| {s['fallback_count']} |"
            )
        else:
            lines.append(f"| {LABELS[cfg]} | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING |")

    report_path = os.path.join(RESULTS_DIR, "PAPER_RESULTS_SUMMARY.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Summary report: {report_path}")


if __name__ == "__main__":
    main()
