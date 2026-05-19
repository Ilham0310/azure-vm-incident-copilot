# Independent Label Review Instructions

## Purpose
Review the expected decision labels for the 100-case synthetic benchmark to reduce author-label bias.

## Reviewer
- Name: Prof. Smriti Srivastava
- Role: Independent reviewer (did not create the benchmark cases)
- Qualification: Associate Professor, CSE, R.V. College of Engineering

## Files to Review
1. `data/benchmark_cases_v2.csv` — 100 main benchmark cases
2. `data/expanded_novel_cases.csv` — 30 expanded novel cases

## Decision Options
For each case, the expected decision should be one of:
- `diagnose` — clear incident pattern, high confidence, unambiguous signals
- `diagnose_low_confidence` — incident detected but signals are ambiguous, conflicting, or incomplete
- `abstain_request_next_check` — insufficient data, platform event requiring wait, or critical signals missing

## Review Process
1. For each case, read the telemetry signals
2. Decide what the correct triage decision should be
3. Record agreement (Yes/No) with the expected_decision
4. If disagreeing, note the reason

## Output Format
Fill in `docs/label_review_results.csv`:
```
case_id,expected_decision,reviewer_decision,agree,reason_if_disagree
001,diagnose,diagnose,Yes,
002,diagnose,diagnose,Yes,
009,diagnose_low_confidence,diagnose,No,Signals are clear enough for full diagnose
...
```

## After Review
Report:
- Total cases reviewed
- Agreement count and percentage
- List of disagreements with reasons
- Resolution method (discussion between authors)

## Estimated Time
- 100 main cases: ~2 hours
- 30 novel cases: ~45 minutes
- Total: ~3 hours
