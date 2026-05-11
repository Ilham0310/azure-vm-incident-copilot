#!/usr/bin/env python3
"""Compute McNemar's test from per-case detail CSVs.

Reads config_A and config_D detail CSVs, builds the paired 2x2
contingency table, and reports exact and asymptotic McNemar statistics.
"""
import csv
import json
import os
import sys
from math import factorial
from typing import Dict

RESULTS_DIR = "experiments/results"


def load_config_results(config_key: str) -> Dict[str, bool]:
    """Load case_id -> is_correct mapping from a config's detail CSV."""
    path = os.path.join(RESULTS_DIR, f"exp1_{config_key}_detail.csv")
    if not os.path.exists(path):
        print(f"ERROR: {path} not found")
        sys.exit(1)
    results = {}
    with open(path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            results[row["case_id"]] = row["correct"] == "True"
    return results


def build_contingency(a_results, d_results):
    """Build 2x2 contingency table for McNemar's test.

    Returns (both_correct, d_only_correct, a_only_correct, both_wrong).
    """
    both_correct = d_only = a_only = both_wrong = 0
    for cid in a_results:
        a_ok = a_results[cid]
        d_ok = d_results.get(cid, False)
        if a_ok and d_ok:
            both_correct += 1
        elif d_ok and not a_ok:
            d_only += 1
        elif a_ok and not d_ok:
            a_only += 1
        else:
            both_wrong += 1
    return both_correct, d_only, a_only, both_wrong


def mcnemar_asymptotic(b, c):
    """Asymptotic McNemar chi-squared (with continuity correction)."""
    if b + c == 0:
        return 0.0, 1.0
    chi2 = (abs(b - c) - 1) ** 2 / (b + c)
    # Approximate p-value from chi-squared(1) using survival function
    # For small values, use a simple lookup or scipy if available
    try:
        from scipy.stats import chi2 as chi2_dist
        p = chi2_dist.sf(chi2, df=1)
    except ImportError:
        # Rough approximation for common values
        p = _approx_chi2_p(chi2)
    return chi2, p


def mcnemar_exact(b, c):
    """Exact McNemar test (two-sided binomial test on discordant pairs).

    Under H0, b ~ Binomial(b+c, 0.5).
    Two-sided p = 2 * min(P(X <= min(b,c)), 0.5).
    """
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    try:
        from scipy.stats import binom_test
        p = binom_test(k, n, 0.5)
    except ImportError:
        # Manual computation
        p = 0.0
        for i in range(k + 1):
            p += _binom_pmf(i, n, 0.5)
        p = min(2 * p, 1.0)
    return p


def _binom_pmf(k, n, p):
    """Binomial PMF without scipy."""
    from math import comb
    return comb(n, k) * (p ** k) * ((1 - p) ** (n - k))


def _approx_chi2_p(chi2_val):
    """Very rough chi-squared(1) p-value approximation."""
    # Common thresholds
    if chi2_val >= 10.83:
        return 0.001
    elif chi2_val >= 6.63:
        return 0.01
    elif chi2_val >= 3.84:
        return 0.05
    elif chi2_val >= 2.71:
        return 0.10
    elif chi2_val >= 1.64:
        return 0.20
    else:
        return 0.50


def wilson_ci(correct, total, z=1.96):
    """Wilson score confidence interval for a proportion."""
    if total == 0:
        return 0.0, 0.0
    p_hat = correct / total
    denom = 1 + z ** 2 / total
    centre = (p_hat + z ** 2 / (2 * total)) / denom
    spread = z * ((p_hat * (1 - p_hat) / total + z ** 2 / (4 * total ** 2)) ** 0.5) / denom
    return max(0, centre - spread), min(1, centre + spread)


def main():
    a_results = load_config_results("config_A")
    d_results = load_config_results("config_D")

    print(f"Config A: {len(a_results)} cases, {sum(a_results.values())} correct")
    print(f"Config D: {len(d_results)} cases, {sum(d_results.values())} correct")

    both_correct, d_only, a_only, both_wrong = build_contingency(a_results, d_results)
    n = both_correct + d_only + a_only + both_wrong

    print(f"\nPaired contingency table (n={n}):")
    print(f"  Both correct:       {both_correct}")
    print(f"  D correct, A wrong: {d_only}  (b)")
    print(f"  A correct, D wrong: {a_only}  (c)")
    print(f"  Both wrong:         {both_wrong}")
    print(f"  Discordant pairs:   {d_only + a_only}")

    chi2, p_asymp = mcnemar_asymptotic(d_only, a_only)
    p_exact = mcnemar_exact(d_only, a_only)

    print(f"\nMcNemar's test (D vs A):")
    print(f"  Asymptotic chi2 (continuity-corrected): {chi2:.4f}")
    print(f"  Asymptotic p-value: {p_asymp:.4f}")
    print(f"  Exact p-value (two-sided binomial): {p_exact:.4f}")

    a_correct = sum(a_results.values())
    d_correct = sum(d_results.values())
    a_lo, a_hi = wilson_ci(a_correct, n)
    d_lo, d_hi = wilson_ci(d_correct, n)

    print(f"\n95% Wilson CIs:")
    print(f"  Config A: {a_correct/n*100:.1f}% [{a_lo*100:.1f}%, {a_hi*100:.1f}%]")
    print(f"  Config D: {d_correct/n*100:.1f}% [{d_lo*100:.1f}%, {d_hi*100:.1f}%]")

    # Save results
    output = {
        "contingency": {
            "both_correct": both_correct,
            "D_only_correct_b": d_only,
            "A_only_correct_c": a_only,
            "both_wrong": both_wrong,
            "n": n,
        },
        "mcnemar_asymptotic": {"chi2": round(chi2, 4), "p_value": round(p_asymp, 4)},
        "mcnemar_exact": {"p_value": round(p_exact, 4)},
        "wilson_ci_95": {
            "config_A": {"accuracy": round(a_correct / n * 100, 1),
                         "lower": round(a_lo * 100, 1), "upper": round(a_hi * 100, 1)},
            "config_D": {"accuracy": round(d_correct / n * 100, 1),
                         "lower": round(d_lo * 100, 1), "upper": round(d_hi * 100, 1)},
        },
    }
    out_path = os.path.join(RESULTS_DIR, "mcnemar_results.json")
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
