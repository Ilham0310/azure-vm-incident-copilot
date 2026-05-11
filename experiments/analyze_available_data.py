#!/usr/bin/env python3
"""Analyze all available per-case data and build honest Table 1.

Reports:
- Config A: full 100 cases (rule engine, corrected pattern hints)
- Config B: split into genuine-LLM vs fallback subsets
- Config C: split into genuine-LLM vs fallback subsets
- Paired contingency tables for McNemar where possible
"""
import csv
import json
import os
import sys
from collections import Counter

RESULTS_DIR = "experiments/results"
BENCH_CSV = "data/benchmark_cases_v2.csv"


def load_bench():
    with open(BENCH_CSV, encoding="utf-8") as f:
        return {r["case_id"]: r for r in csv.DictReader(f)}


def load_config(name):
    if name == "config_A":
        path = os.path.join(RESULTS_DIR, "exp1_config_a_corrected.csv")
    else:
        path = os.path.join(RESULTS_DIR, f"exp1_{name}_detail.csv")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def summarize(rows, bench, label=""):
    total = len(rows)
    if total == 0:
        print(f"  {label}: no data")
        return {}
    correct = sum(1 for r in rows if r["correct"] == "True")
    novel = [r for r in rows if bench.get(r["case_id"], {}).get("is_novel", "").strip().lower() == "true"]
    known = [r for r in rows if bench.get(r["case_id"], {}).get("is_novel", "").strip().lower() != "true"]
    correct_known = sum(1 for r in known if r["correct"] == "True")
    correct_novel = sum(1 for r in novel if r["correct"] == "True")
    abstain = sum(1 for r in rows
                  if r["actual"] == "abstain_request_next_check"
                  and r["expected"] != "abstain_request_next_check")
    healthy = [r for r in rows if bench.get(r["case_id"], {}).get("incident_pattern") == "clean"]
    fp = sum(1 for r in healthy
             if r["actual"] != r["expected"]
             and r["actual"] in ("diagnose", "diagnose_low_confidence"))

    print(f"  {label}: {correct}/{total} = {correct/total*100:.1f}% overall")
    if known:
        print(f"    known: {correct_known}/{len(known)} = {correct_known/len(known)*100:.1f}%")
    if novel:
        print(f"    novel: {correct_novel}/{len(novel)} = {correct_novel/len(novel)*100:.1f}%")
    print(f"    abstain: {abstain}, FP: {fp}/{len(healthy)}")
    providers = Counter(r.get("provider", "?") for r in rows)
    print(f"    providers: {dict(providers)}")

    return {
        "total": total,
        "correct": correct,
        "total_known": len(known),
        "correct_known": correct_known,
        "total_novel": len(novel),
        "correct_novel": correct_novel,
        "abstain": abstain,
        "fp": fp,
        "total_healthy": len(healthy),
    }


def paired_mcnemar(rows_a, rows_b, label=""):
    """Compute McNemar's test from two sets of per-case results."""
    a_map = {r["case_id"]: r["correct"] == "True" for r in rows_a}
    b_map = {r["case_id"]: r["correct"] == "True" for r in rows_b}
    common = set(a_map.keys()) & set(b_map.keys())
    if not common:
        print(f"  {label}: no common cases")
        return

    both_ok = sum(1 for c in common if a_map[c] and b_map[c])
    b_only = sum(1 for c in common if b_map[c] and not a_map[c])
    a_only = sum(1 for c in common if a_map[c] and not b_map[c])
    both_wrong = sum(1 for c in common if not a_map[c] and not b_map[c])

    print(f"\n  {label} (n={len(common)} paired cases):")
    print(f"    both_correct={both_ok}, B_only_correct(b)={b_only}, "
          f"A_only_correct(c)={a_only}, both_wrong={both_wrong}")
    print(f"    b-c = {b_only - a_only}")

    discordant = b_only + a_only
    if discordant > 0:
        chi2 = (b_only - a_only) ** 2 / discordant
        chi2_cc = (abs(b_only - a_only) - 1) ** 2 / discordant if abs(b_only - a_only) > 1 else 0
        print(f"    McNemar chi2 (no correction) = {chi2:.3f}")
        print(f"    McNemar chi2 (continuity corr) = {chi2_cc:.3f}")
        # p-value from chi-squared with 1 df
        try:
            from scipy.stats import chi2 as chi2_dist
            p_no_cc = 1 - chi2_dist.cdf(chi2, 1)
            p_cc = 1 - chi2_dist.cdf(chi2_cc, 1)
            print(f"    p (no correction) = {p_no_cc:.4f}")
            print(f"    p (continuity corr) = {p_cc:.4f}")
        except ImportError:
            print("    (scipy not available for p-value)")
        # Exact McNemar (binomial test)
        try:
            from scipy.stats import binom_test
            p_exact = binom_test(b_only, discordant, 0.5)
            print(f"    Exact McNemar p = {p_exact:.4f}")
        except (ImportError, Exception):
            try:
                from scipy.stats import binomtest
                result = binomtest(b_only, discordant, 0.5)
                print(f"    Exact McNemar p = {result.pvalue:.4f}")
            except (ImportError, Exception):
                print("    (scipy binomtest not available)")
    else:
        print("    No discordant pairs — McNemar not applicable")

    return {
        "n": len(common),
        "both_correct": both_ok,
        "b_only_correct": b_only,
        "a_only_correct": a_only,
        "both_wrong": both_wrong,
    }


def main():
    bench = load_bench()

    configs = {}
    for name in ["config_A", "config_B", "config_C", "config_D"]:
        rows = load_config(name)
        if rows:
            configs[name] = rows
            print(f"\n{'='*60}")
            print(f"{name} ({len(rows)} rows)")
            print(f"{'='*60}")
            summarize(rows, bench, f"{name} (all)")

            # Split by provider for LLM configs
            if name != "config_A":
                llm_rows = [r for r in rows if r.get("provider", "") not in ("rule_engine_fallback", "rule_engine", "?", "")]
                fb_rows = [r for r in rows if r.get("provider", "") in ("rule_engine_fallback", "rule_engine", "?", "")]
                if llm_rows:
                    summarize(llm_rows, bench, f"{name} (genuine LLM only)")
                if fb_rows:
                    summarize(fb_rows, bench, f"{name} (fallback only)")
        else:
            print(f"\n{name}: NOT FOUND")

    # Paired McNemar comparisons
    if "config_A" in configs:
        for other in ["config_B", "config_C", "config_D"]:
            if other in configs:
                paired_mcnemar(configs["config_A"], configs[other],
                               f"McNemar: {other} vs config_A")

    # Write consolidated summary
    summary = {}
    for name, rows in configs.items():
        s = summarize(rows, bench, name)
        summary[name] = s
    with open(os.path.join(RESULTS_DIR, "table1_audited_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nAudited summary written to {RESULTS_DIR}/table1_audited_summary.json")


if __name__ == "__main__":
    main()
