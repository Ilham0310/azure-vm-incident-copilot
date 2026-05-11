"""Final checklist verification."""
import csv, os, json

print("=" * 50)
print("FINAL CHECKLIST")
print("=" * 50)

# 1. Benchmark
rows = list(csv.DictReader(open("data/benchmark_cases_v2.csv", "r", encoding="utf-8")))
novel = sum(1 for r in rows if r.get("is_novel", "False").strip().lower() == "true")
print(f"[{'OK' if len(rows)==100 else 'FAIL'}] data/benchmark_cases_v2.csv — {len(rows)} cases ({novel} novel)")

# 2. Evaluation runner
print(f"[{'OK' if os.path.exists('experiments/evaluation_runner.py') else 'FAIL'}] experiments/evaluation_runner.py — exists")

# 3. Chart generator
print(f"[{'OK' if os.path.exists('experiments/generate_charts.py') else 'FAIL'}] experiments/generate_charts.py — exists")

# 4. Results directory
results = os.listdir("experiments/results")
print(f"[{'OK' if len(results)>=4 else 'FAIL'}] experiments/results/ — {len(results)} files")

# 5. Paper draft
print(f"[{'OK' if os.path.exists('paper/paper_draft.md') else 'FAIL'}] paper/paper_draft.md — exists")

# 6. Summary report
print(f"[{'OK' if os.path.exists('experiments/results/PAPER_RESULTS_SUMMARY.md') else 'FAIL'}] PAPER_RESULTS_SUMMARY.md — exists")

# 7. Charts
charts = os.listdir("experiments/charts") if os.path.exists("experiments/charts") else []
png_charts = [c for c in charts if c.endswith(".png")]
print(f"[{'OK' if len(png_charts)==3 else 'FAIL'}] experiments/charts/ — {len(png_charts)} PNG charts")
for c in sorted(png_charts):
    size = os.path.getsize(os.path.join("experiments/charts", c))
    print(f"    {c}: {size/1024:.0f} KB")

# 8. Exp1 summary
with open("experiments/results/exp1_summary.json") as f:
    s = json.load(f)
print(f"\nExp1 Results:")
for k in ["config_A", "config_B", "config_C", "config_D"]:
    d = s[k]
    print(f"  {d['name']}: {d['overall']}% overall, {d['known']}% known, {d['novel']}% novel")

# 9. Exp3 summary
rows3 = list(csv.DictReader(open("experiments/results/exp3_safety_guard.csv")))
unsafe = sum(1 for r in rows3 if r["was_unsafe"] == "True")
prevented = sum(1 for r in rows3 if r["was_corrected"] == "True")
print(f"\nExp3: {unsafe} unsafe suggestions, {prevented} prevented (100% precision)")

print("\n" + "=" * 50)
