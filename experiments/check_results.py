#!/usr/bin/env python3
"""Check what experiment results were saved."""
import csv
import json
import os
from collections import Counter, defaultdict

RESULTS_DIR = "experiments/results"
DETAIL_CSV = os.path.join(RESULTS_DIR, "exp1_accuracy_comparison.csv")
BENCH_CSV = "data/benchmark_cases_v2.csv"

# Load detail rows
with open(DETAIL_CSV, encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

print(f"Total detail rows: {len(rows)}")
print(f"Columns: {list(rows[0].keys()) if rows else 'N/A'}")
configs = Counter(r["config"] for r in rows)
print(f"By config: {dict(configs)}")

# Load benchmark for is_novel
with open(BENCH_CSV, encoding="utf-8") as f:
    bench = {r["case_id"]: r for r in csv.DictReader(f)}

for cfg in sorted(configs.keys()):
    cfg_rows = [r for r in rows if r["config"] == cfg]
    correct = sum(1 for r in cfg_rows if r["correct"] == "True")
    total = len(cfg_rows)

    # Known vs novel breakdown
    novel_rows = [r for r in cfg_rows if bench.get(r["case_id"], {}).get("is_novel", "").strip().lower() == "true"]
    known_rows = [r for r in cfg_rows if bench.get(r["case_id"], {}).get("is_novel", "").strip().lower() != "true"]
    correct_known = sum(1 for r in known_rows if r["correct"] == "True")
    correct_novel = sum(1 for r in novel_rows if r["correct"] == "True")

    # Provider breakdown if available
    providers = Counter(r.get("provider", "?") for r in cfg_rows)

    print(f"\n  {cfg}: {correct}/{total} = {correct/total*100:.1f}% overall")
    print(f"    known: {correct_known}/{len(known_rows)} = {correct_known/len(known_rows)*100:.1f}%" if known_rows else "    known: N/A")
    print(f"    novel: {correct_novel}/{len(novel_rows)} = {correct_novel/len(novel_rows)*100:.1f}%" if novel_rows else "    novel: N/A")
    print(f"    providers: {dict(providers)}")

    # Abstain count
    abstain = sum(1 for r in cfg_rows
                  if r["actual"] == "abstain_request_next_check"
                  and r["expected"] != "abstain_request_next_check")
    print(f"    false abstains: {abstain}")

# Check if summary JSON was written
summary_path = os.path.join(RESULTS_DIR, "table1_ablation.json")
if os.path.exists(summary_path):
    with open(summary_path) as f:
        summary = json.load(f)
    print(f"\nSummary JSON has configs: {list(summary.keys())}")
else:
    print("\nNo summary JSON found")

# Build paired contingency D vs A if both exist
if "config_A" in configs and "config_D" in configs:
    a_map = {r["case_id"]: r["correct"] == "True" for r in rows if r["config"] == "config_A"}
    d_map = {r["case_id"]: r["correct"] == "True" for r in rows if r["config"] == "config_D"}
    b = c = both_ok = both_wrong = 0
    for cid in a_map:
        a_ok = a_map[cid]
        d_ok = d_map.get(cid, False)
        if a_ok and d_ok: both_ok += 1
        elif d_ok and not a_ok: b += 1
        elif not d_ok and a_ok: c += 1
        else: both_wrong += 1
    print(f"\nPaired contingency D vs A:")
    print(f"  both_correct={both_ok}, D_only={b}, A_only={c}, both_wrong={both_wrong}")
    print(f"  b-c = {b-c}")
    if b + c > 0:
        # McNemar without continuity correction
        chi2 = (b - c) ** 2 / (b + c)
        print(f"  McNemar chi2 (no correction) = {chi2:.3f}")
        # With continuity correction
        chi2_cc = (abs(b - c) - 1) ** 2 / (b + c) if abs(b-c) > 1 else 0
        print(f"  McNemar chi2 (continuity) = {chi2_cc:.3f}")
