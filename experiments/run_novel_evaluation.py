#!/usr/bin/env python3
"""Evaluate all configs on the 30 expanded novel cases."""
import csv, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv; load_dotenv()
from src.models import TelemetryInput
from src.confidence_scorer import ConfidenceScorer
from src.decision_engine import DecisionEngine

INPUT = "data/expanded_novel_cases.csv"
OUTPUT = "experiments/results/expanded_novel_results.json"

def main():
    scorer = ConfidenceScorer()
    engine = DecisionEngine()
    
    with open(INPUT, encoding="utf-8") as f:
        cases = list(csv.DictReader(f))
    
    results = {"config_A": [], "summary": {}}
    correct = 0
    
    for case in cases:
        tel_data = json.loads(case["telemetry_json"])
        try:
            telemetry = TelemetryInput(**tel_data)
        except Exception as e:
            results["config_A"].append({"case_id": case["case_id"], "error": str(e)})
            continue
        
        # Use honest pattern hint
        match = engine._match_patterns(telemetry)
        hint = "exact" if match else None
        
        completeness, confidence, conflicts = scorer.score_telemetry(telemetry, pattern_match=hint)
        decision = engine.decide(telemetry, confidence, completeness)
        
        expected = case["expected_decision"]
        actual = decision.state.value
        is_correct = actual == expected
        if is_correct:
            correct += 1
        
        results["config_A"].append({
            "case_id": case["case_id"],
            "case_name": case["case_name"],
            "category": case["category"],
            "expected": expected,
            "actual": actual,
            "correct": is_correct,
            "confidence": confidence,
            "pattern_hint": hint or "none",
        })
    
    total = len(cases)
    results["summary"] = {
        "total": total,
        "correct": correct,
        "accuracy": round(correct / total * 100, 1) if total else 0,
        "config": "Rule Engine + Safety Guard (Config A)",
    }
    
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"Expanded Novel Cases - Config A (Rule Engine + Safety):")
    print(f"  Correct: {correct}/{total} = {results['summary']['accuracy']}%")
    
    # Per-category breakdown
    cats = {}
    for r in results["config_A"]:
        if "error" in r: continue
        cat = r["category"]
        if cat not in cats: cats[cat] = {"total": 0, "correct": 0}
        cats[cat]["total"] += 1
        if r["correct"]: cats[cat]["correct"] += 1
    
    print(f"\n  Per-category:")
    for cat in sorted(cats):
        s = cats[cat]
        print(f"    {cat}: {s['correct']}/{s['total']}")
    
    print(f"\n  Results saved to {OUTPUT}")

if __name__ == "__main__":
    main()
