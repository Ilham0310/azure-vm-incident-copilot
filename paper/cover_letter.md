# Cover Letter — IEEE Access Submission

**Title:** LLM-Augmented Azure VM Incident Triage with RAG Memory and Feedback-Driven Retrieval Learning

**Submitted to:** IEEE Access

---

Dear Editor,

We submit for your consideration the manuscript titled *"LLM-Augmented Azure VM Incident Triage with RAG Memory and Feedback-Driven Retrieval Learning"* for publication in IEEE Access.

## Scope Statement

This manuscript falls within IEEE Access scope categories of:

1. **Computer Science — Artificial Intelligence and Machine Learning**: The work presents a 6-layer architecture combining large language model reasoning, retrieval-augmented generation, and feedback-driven retrieval memory for automated incident triage.
2. **Computer Science — Computing Systems and Cloud Infrastructure**: The system is designed and evaluated specifically for Azure VM incident management, addressing a practical production engineering problem at cloud scale.
3. **Computer Science — Software Engineering and Systems**: The paper contributes a deterministic safety enforcement mechanism (post-LLM safety guard) and a structured evaluation methodology for AI-augmented operations systems.

The work addresses a practical production engineering problem (cloud VM incident triage) using technically sound methods (RAG memory, LLM reasoning, deterministic safety enforcement) with empirical evaluation on a synthetic benchmark, consistent with IEEE Access's focus on technically sound applied research.

## Summary of Contributions

The paper makes four primary contributions:

1. A **6-layer architecture** for LLM-assisted Azure VM incident triage reaching 91.0% overall accuracy on a 100-case synthetic benchmark, compared with 87.0% for the rule engine alone.
2. A **dual-collection RAG design** with feedback-driven memory updates (no LLM retraining) that improves held-out novel-pattern accuracy from 20.0% to 80.0% over five cycles.
3. A **deterministic post-LLM safety guard** enforcing six hard safety rules that intercepts all 30 hand-crafted adversarial suggestions tested. We position this as an important architectural component under the evaluated conditions.
4. A **fully-reproducible evaluation package** with per-case detail records, paired contingency tables, and scripts for independent re-verification.

## Novelty Statement

The key novelty is the architectural demonstration that **deterministic post-LLM safety enforcement combined with feedback-driven retrieval memory** is a feasible design pattern for safe LLM-assisted cloud incident triage. Existing systems (RCACopilot, OWL, GPT-4-based RCA) rely on prompt instructions to constrain LLM output; our safety guard is imperative code that runs after LLM generation and cannot be bypassed by any LLM output. We position this as an important component under the evaluated conditions rather than a universally necessary one — establishing necessity in a stricter sense would require comparison with alternative safety mechanisms, which we identify as future work.

## Relationship to Prior Work

The paper cites and directly compares against RCACopilot (Chen et al., EuroSys 2024, 0.77 F1) and Ahmed et al. (ICSE 2023, 68% accuracy). Our system is not directly comparable due to different task definitions (VM infrastructure triage vs. software service RCA), but the architectural contributions are complementary and additive to this body of work.

## Ethical Considerations

- The benchmark dataset is fully synthetic and contains no real incident data, PII, or proprietary information.
- The system is read-only and advisory; it never executes remediation actions.
- AI assistance (Kiro/Claude Sonnet) was used for code scaffolding and initial drafts; all scientific claims and results were independently verified by the authors. This is disclosed in the Acknowledgments section per IEEE Author Center guidelines.

## Suggested Reviewers

We suggest reviewers with expertise in:
- AIOps and cloud incident management systems
- Retrieval-augmented generation and LLM applications
- Safety-critical AI systems and agentic AI

---

We confirm that this manuscript has not been published elsewhere and is not under review at any other venue. All authors have approved the submission.

Sincerely,

[Author 1 Name], [Institution]
[Author 2 Name], [Institution]

[Corresponding author email]
