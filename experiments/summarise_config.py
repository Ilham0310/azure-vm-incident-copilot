#!/usr/bin/env python3
"""Summarise a single config's detail CSV."""
import csv
import sys
import os

cfg = sys.argv[1] if len(sys.argv) > 1 else "config_B"
p = f"experiments/results/exp1_{cfg}_detail.csv"
if not os.path.exists(p):
    print(f"{cfg}: file not found at {p}")
    sys.exit(1)

rows = list(csv.DictReader(open(p)))
total = len(rows)
correct = sum(1 for r in rows if r["correct"] == "True")
novel = [r for r in rows if r.get("is_novel") == "True"]
known = [r for r in rows if r.get("is_novel") == "False"]
correct_known = sum(1 for r in known if r["correct"] == "True")
correct_novel = sum(1 for r in novel if r["correct"] == "True")
healthy = [r for r in rows if r.get("is_healthy") == "True"]
fp = sum(1 for r in healthy
         if r["correct"] == "False" and r["actual"] in ("diagnose", "diagnose_low_confidence"))
abstain = sum(1 for r in rows
              if r["actual"] == "abstain_request_next_check" and r["expected"] != "abstain_request_next_check")
fallback = sum(1 for r in rows if r.get("provider") == "rule_engine_fallback")

print(f"{cfg}: {correct}/{total} = {correct/total*100:.1f}%")
print(f"  Known: {correct_known}/{len(known)} = {correct_known/len(known)*100:.1f}%")
print(f"  Novel: {correct_novel}/{len(novel)} = {correct_novel/len(novel)*100:.1f}%")
print(f"  FP: {fp}/{len(healthy)}")
print(f"  Abstain: {abstain}/{total}")
print(f"  Fallback: {fallback}/{total}")
print()
print("Wrong cases:")
for r in rows:
    if r["correct"] == "False":
        print(f"  {r['case_id']} {r['case_name']}: expected={r['expected']} got={r['actual']} provider={r['provider']}")
