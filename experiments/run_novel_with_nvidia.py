#!/usr/bin/env python3
"""
Evaluate 30 expanded novel cases using NVIDIA NIM API.
NVIDIA NIM provides OpenAI-compatible endpoints for LLM inference.
"""
import csv, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv; load_dotenv()

from src.models import TelemetryInput
from src.confidence_scorer import ConfidenceScorer
from src.decision_engine import DecisionEngine

INPUT = "data/expanded_novel_cases.csv"
OUTPUT = "experiments/results/expanded_novel_llm_results.json"

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
NVIDIA_MODEL = "meta/llama-3.1-70b-instruct"


def get_system_prompt():
    """Condensed system prompt for triage."""
    return """You are a senior Azure VM incident triage specialist. Analyze the telemetry and return a JSON response.

RULES:
- If signals are ambiguous or conflicting, use diagnose_low_confidence
- If data is insufficient (<60% completeness), use abstain_request_next_check
- Never suggest restarting during platform maintenance
- Never suggest disabling NSG/firewall rules
- Never suggest destructive actions (delete/wipe/reset) unless very high confidence

Return ONLY valid JSON:
{"decision": "diagnose|diagnose_low_confidence|abstain_request_next_check", "diagnosis": "one sentence", "next_check": "safe next step or null"}"""


def call_nvidia_llm(telemetry_json: str) -> dict:
    """Call NVIDIA NIM API with OpenAI-compatible format."""
    import requests
    
    headers = {
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": NVIDIA_MODEL,
        "messages": [
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": f"Analyze this Azure VM telemetry and provide triage:\n{telemetry_json}"}
        ],
        "temperature": 0.1,
        "max_tokens": 500,
    }
    
    resp = requests.post(
        f"{NVIDIA_BASE_URL}/chat/completions",
        headers=headers,
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    
    content = resp.json()["choices"][0]["message"]["content"]
    
    # Parse JSON from response
    try:
        # Try to extract JSON from the response
        if "{" in content:
            json_str = content[content.index("{"):content.rindex("}") + 1]
            return json.loads(json_str)
    except (json.JSONDecodeError, ValueError):
        pass
    
    # Default if parsing fails
    return {"decision": "diagnose_low_confidence", "diagnosis": "Unable to parse LLM response"}


def main():
    if not NVIDIA_API_KEY:
        print("ERROR: NVIDIA_API_KEY not set in .env")
        sys.exit(1)
    
    print(f"Using NVIDIA NIM API: {NVIDIA_MODEL}")
    print(f"Base URL: {NVIDIA_BASE_URL}")
    
    with open(INPUT, encoding="utf-8") as f:
        cases = list(csv.DictReader(f))
    
    scorer = ConfidenceScorer()
    engine = DecisionEngine()
    
    results = []
    correct = 0
    
    for i, case in enumerate(cases):
        print(f"  [{i+1}/{len(cases)}] {case['case_name']}...", end=" ")
        
        tel_data = json.loads(case["telemetry_json"])
        expected = case["expected_decision"]
        
        try:
            # Call NVIDIA LLM
            llm_response = call_nvidia_llm(case["telemetry_json"])
            actual = llm_response.get("decision", "diagnose_low_confidence")
            
            # Normalize decision
            valid_decisions = ["diagnose", "diagnose_low_confidence", "abstain_request_next_check"]
            if actual not in valid_decisions:
                actual = "diagnose_low_confidence"
            
            is_correct = actual == expected
            if is_correct:
                correct += 1
            
            status = "OK" if is_correct else "WRONG"
            print(f"{status} (expected={expected}, got={actual})")
            
            results.append({
                "case_id": case["case_id"],
                "case_name": case["case_name"],
                "category": case["category"],
                "expected": expected,
                "actual": actual,
                "correct": is_correct,
                "diagnosis": llm_response.get("diagnosis", ""),
                "provider": "NVIDIA NIM",
            })
            
            time.sleep(1.0)  # Rate limit
            
        except Exception as e:
            print(f"ERROR: {e}")
            results.append({
                "case_id": case["case_id"],
                "case_name": case["case_name"],
                "category": case["category"],
                "expected": expected,
                "actual": "error",
                "correct": False,
                "error": str(e),
                "provider": "NVIDIA NIM",
            })
            time.sleep(2.0)
    
    total = len(cases)
    summary = {
        "total": total,
        "correct": correct,
        "accuracy": round(correct / total * 100, 1),
        "provider": "NVIDIA NIM",
        "model": NVIDIA_MODEL,
    }
    
    print(f"\n{'='*60}")
    print(f"NVIDIA LLM Novel-Case Results:")
    print(f"  Correct: {correct}/{total} = {summary['accuracy']}%")
    print(f"  (Rule Engine was: 8/30 = 26.7%)")
    print(f"{'='*60}")
    
    # Per-category
    cats = {}
    for r in results:
        cat = r["category"]
        if cat not in cats: cats[cat] = {"total": 0, "correct": 0}
        cats[cat]["total"] += 1
        if r["correct"]: cats[cat]["correct"] += 1
    print("\n  Per-category:")
    for cat in sorted(cats):
        s = cats[cat]
        print(f"    {cat}: {s['correct']}/{s['total']}")
    
    output = {"results": results, "summary": summary, "per_category": cats}
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n  Saved to {OUTPUT}")


if __name__ == "__main__":
    main()
