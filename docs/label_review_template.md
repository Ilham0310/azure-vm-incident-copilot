# Independent Label Review Template

## Purpose
This document provides instructions for an independent reviewer to validate
the expected decision labels assigned to the 100-case synthetic benchmark
and the 30 expanded novel cases.

## Reviewer Requirements
- The reviewer should NOT be the same person who created the benchmark cases.
- Ideally: a faculty member, senior student, or cloud practitioner with
  Azure/cloud operations experience.
- Minimum: someone who understands VM incident triage concepts.

## Instructions for Reviewer

For each case in `data/benchmark_cases_v2.csv` and `data/expanded_novel_cases.csv`:

1. Read the telemetry JSON input.
2. Based on the telemetry signals, decide what the correct triage decision should be:
   - `diagnose` — clear incident pattern, high confidence
   - `diagnose_low_confidence` — incident detected but signals are ambiguous or conflicting
   - `abstain_request_next_check` — insufficient data or platform event requiring wait

3. Record your decision in the "reviewer_decision" column.
4. If your decision differs from the "expected_decision" column, note why in "disagreement_reason".

## Review Spreadsheet Format

| case_id | case_name | expected_decision | reviewer_decision | agree? | disagreement_reason |
|---|---|---|---|---|---|
| 001 | VM Stopped by User | diagnose | | | |
| 002 | NSG Blocks RDP | diagnose | | | |
| ... | ... | ... | | | |

## After Review

Report:
- Total cases reviewed: ___
- Cases where reviewer agrees with expected label: ___ / ___
- Agreement rate: ___%
- Cases with disagreement: list case_ids
- Resolution: how disagreements were resolved (discussion, majority vote, etc.)

## For the Paper

Add this text to Section 4.1 (Benchmark Dataset):

"To reduce author-label bias, an independent reviewer with [cloud/system
administration] experience reviewed all expected decisions for the 100
benchmark cases [and 30 expanded novel cases]. Agreement with the original
labels was X/Y cases (Z%). Disagreements on [N] cases were resolved by
discussion between the authors and reviewer; the final adjudicated labels
are released in the dataset."

## Who Should Do This

- **Prof. Smriti Srivastava** (co-author) can serve as the independent reviewer
  since she did not create the benchmark cases.
- Alternatively, a senior student or lab colleague with cloud experience.

## Timeline
- Estimated time: 2-3 hours for 130 cases
- Should be completed before final IEEE Access submission
