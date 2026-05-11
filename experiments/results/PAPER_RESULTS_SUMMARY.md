# Evaluation Results — Azure VM Incident Copilot

Generated: 2026-04-24 (audited re-run with corrected pattern hints)

## Status

| Config | Status | Cases | Provider |
|---|---|---|---|
| Config A (Rule Engine + Safety) | ✅ Complete | 100/100 | rule_engine |
| Config A-noSafety (ablation) | ✅ Complete | 100/100 | rule_engine |
| Config B (LLM Only) | ⏳ Pending | 0/100 | Requires fresh Groq quota |
| Config C (LLM + SOP RAG) | ⏳ Pending | 0/100 | Requires fresh Groq quota |
| Config D (Full System) | ⏳ Pending | 0/100 | Requires fresh Groq quota |

**To complete B/C/D**: Run `python experiments/run_llm_configs.py all` after Groq daily quota resets (~midnight UTC). Requires ~100k tokens/day free tier.

---

## Table 1: Accuracy Comparison (Experiment 1)

| Configuration | Overall | Known (n=95) | Novel (n=5) | FP (n=5) | Abstain |
|---|---|---|---|---|---|
| Rule Engine + Safety (A) | 88/100 (88.0%) | 87/95 (91.6%) | 1/5 (20.0%) | 0/5 (0.0%) | 0 |
| Rule Engine, no Safety (A-noSafety) | 82/100 (82.0%) | 81/95 (85.3%) | 1/5 (20.0%) | 0/5 (0.0%) | 0 |
| LLM Only (B) | PENDING | PENDING | PENDING | PENDING | PENDING |
| LLM + SOP RAG (C) | PENDING | PENDING | PENDING | PENDING | PENDING |
| Full System (D) | PENDING | PENDING | PENDING | PENDING | PENDING |

**Key finding**: Safety guard adds +6 pp (82→88%) by correctly forcing abstention on 6 platform-event cases.

**Paired contingency (A-noSafety vs A)**:
- both_correct = 82
- A_only_correct (safety guard helps) = 6
- noSafety_only_correct = 0
- both_wrong = 12

---

## Table 2: Feedback-Driven Memory Improvement (Experiment 2)

| Feedback Cycle | Cases in Memory | Test Cases | Accuracy | Known Acc | Novel Acc |
|---|---|---|---|---|---|
| Cycle 0 | 0 | 20 | 80.0% | 100.0% | 20.0% |
| Cycle 1 | 10 | 20 | 80.0% | 100.0% | 20.0% |
| Cycle 2 | 25 | 20 | 85.0% | 100.0% | 40.0% |
| Cycle 3 | 50 | 20 | 90.0% | 100.0% | 60.0% |
| Cycle 4 | 75 | 20 | 95.0% | 100.0% | 80.0% |
| Cycle 5 | 80 | 20 | 95.0% | 100.0% | 80.0% |

Note: Each 20pp step in novel accuracy = 1 case (n=5). Confidence intervals are wide.

---

## Table 3: Safety Guard Precision and Recall (Experiment 3)

| Safety Rule | Cases Tested | Unsafe Prevented | Prevention Rate |
|---|---|---|---|
| SR-1 Platform | 5 | 5 | 100% |
| SR-2 BSOD | 5 | 5 | 100% |
| SR-3 Destructive | 5 | 5 | 100% |
| SR-4 Network | 5 | 5 | 100% |
| SR-5 Disk | 5 | 5 | 100% |
| SR-6 Failed | 5 | 5 | 100% |
| **Total** | **30** | **30** | **100%** |

False-block rate on 100-case benchmark: 0/100 (0.0%)
False-block rate on 5 healthy VMs: 0/5 (0.0%)
Accuracy contribution (ablation): +6 pp (82→88%)

---

## Reproducibility

All deterministic experiments (Config A, safety ablation, Exp 2, Exp 3) are fully reproducible:

```bash
python experiments/run_config_a_only.py          # Config A: ~5 seconds
python experiments/run_no_safety_ablation.py     # Safety ablation: ~5 seconds
python experiments/evaluation_runner.py          # Exp 2 + Exp 3: ~15 seconds
python experiments/generate_charts_v2.py         # Updated figures
```

LLM configs require fresh API quota:
```bash
# After Groq quota resets:
python experiments/run_llm_configs.py config_B
python experiments/run_llm_configs.py config_C
python experiments/run_llm_configs.py config_D
python experiments/analyze_available_data.py     # Compute final Table 1
```
