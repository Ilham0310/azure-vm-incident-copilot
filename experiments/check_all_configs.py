#!/usr/bin/env python3
"""Check status of all config detail CSVs."""
import csv
import os

RESULTS_DIR = "experiments/results"

for cfg in ["config_A", "config_B", "config_C", "config_D"]:
    path = os.path.join(RESULTS_DIR, f"exp1_{cfg}_detail.csv")
    if cfg == "config_A":
        path = os.path.join(RESULTS_DIR, "exp1_config_a_corrected.csv")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        correct = sum(1 for r in rows if r["correct"] == "True")
        novel = [r for r in rows if r.get("is_novel", "").strip() == "True"]
        novel_correct = sum(1 for r in novel if r["correct"] == "True")
        known = [r for r in rows if r.get("is_novel", "").strip() != "True"]
        known_correct = sum(1 for r in known if r["correct"] == "True")
        providers = {}
        for r in rows:
            p = r.get("provider", "?")
            providers[p] = providers.get(p, 0) + 1
        print(f"{cfg}: {len(rows)} rows, {correct}/{len(rows)} = {correct/len(rows)*100:.1f}%")
        if known:
            print(f"  known: {known_correct}/{len(known)} = {known_correct/len(known)*100:.1f}%")
        if novel:
            print(f"  novel: {novel_correct}/{len(novel)} = {novel_correct/len(novel)*100:.1f}%")
        print(f"  providers: {providers}")
    else:
        print(f"{cfg}: NOT FOUND at {path}")
