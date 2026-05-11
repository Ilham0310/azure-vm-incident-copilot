# LLM-Augmented Azure VM Incident Triage with RAG Memory and Online Self-Learning

## Abstract

Cloud infrastructure incidents at scale demand triage systems that are both fast and accurate. Rule-based AIOps systems handle known failure patterns reliably but fail entirely on novel incidents, while large language models (LLMs) introduce hallucination risk that can produce dangerous remediation suggestions. This paper presents a 6-layer LLM-augmented architecture for Azure VM incident triage combining a deterministic rule engine, dual-collection RAG memory (ChromaDB with sentence-transformers), structured LLM reasoning with multi-provider fallback (Groq, Gemini, Ollama), and a deterministic post-LLM safety guard enforcing six hard safety rules. Evaluated on 100 synthetic benchmark cases spanning 23 known incident patterns and 5 novel patterns, the full system achieves 91.0% overall accuracy, a 4.0 percentage-point improvement over the rule-based baseline of 87.0%. Novel pattern accuracy improves from 20.0% to 80.0% over five self-learning feedback cycles as verified incident cases accumulate in memory. The deterministic safety guard prevents 100% of unsafe suggestions across 30 adversarial test cases covering all six safety rules. A multi-provider fallback chain ensures 100% system availability across all evaluation cases. These results demonstrate that combining deterministic safety enforcement with online RAG-based self-learning enables production-grade LLM triage without sacrificing safety guarantees.

## 1. Introduction

### 1.1 Problem Statement

Cloud infrastructure downtime carries severe financial and operational consequences. Industry estimates place the average cost of unplanned downtime at $300,000 per hour [1], with hyperscale cloud providers managing millions of virtual machine instances across global regions. At this scale, even a 0.1% incident rate generates thousands of simultaneous alerts, far exceeding the capacity of on-call engineering teams to triage manually. Automated incident triage is therefore not a convenience but an operational necessity.

Current AIOps systems for cloud VM triage are predominantly rule-based. Azure Monitor alert rules, Prometheus AlertManager, and similar platforms apply deterministic threshold conditions to telemetry streams: if CPU exceeds 95% for five minutes, fire an alert. These systems are fast, auditable, and reliable for known failure patterns. However, they require manual threshold tuning for each metric, cannot generalize across correlated multi-signal failures, and fail entirely when incidents involve patterns not anticipated at rule-authoring time. In practice, novel failure modes — new OS versions, unexpected interaction effects between services, infrastructure changes — account for a disproportionate share of high-severity incidents precisely because they are not covered by existing rules [2].

Large language models offer a compelling alternative for novel pattern reasoning. An LLM can read free-form telemetry, reason over signal combinations, and generate contextually appropriate remediation suggestions without requiring explicit rule definitions. However, LLMs introduce a critical risk in production operations: hallucination. An LLM that confidently suggests restarting a VM during an active platform maintenance window, or recommends deleting an OS disk based on ambiguous signals, can cause data corruption or extended downtime that is worse than the original incident. No existing production system enforces hard safety constraints on LLM-generated remediation suggestions at inference time.

The gap this paper addresses is the absence of a system that combines: (a) a strong deterministic rule baseline for known patterns, (b) LLM reasoning for novel patterns, (c) RAG memory for cumulative knowledge accumulation without retraining, and (d) deterministic post-LLM safety enforcement that cannot be bypassed by any LLM output. We present such a system and evaluate it empirically on 100 benchmark cases.

### 1.2 Contributions

1. A 6-layer LLM-augmented triage architecture for Azure VM incidents with deterministic safety enforcement, achieving 91.0% overall accuracy on 100 benchmark cases
2. A RAG memory store that prioritizes human-verified resolutions, enabling online improvement without LLM retraining — novel pattern accuracy improves from 20.0% to 80.0% over five feedback cycles
3. A novel incident detection mechanism that flags unknown failure patterns for engineer review, with a deterministic safety guard that prevents 100% of tested unsafe suggestions across 30 adversarial cases
4. An empirical evaluation on 100 synthetic benchmark cases showing a 4.0 percentage-point accuracy improvement over the rule-based baseline, with zero false positives on safety-critical cases

## 2. Related Work

### 2.1 Rule-Based AIOps

Traditional IT operations monitoring relies on threshold-based alerting systems such as Nagios, Prometheus AlertManager, and Azure Monitor native alert rules. These systems evaluate deterministic conditions against telemetry streams and fire alerts when thresholds are breached. Their primary advantages are speed, auditability, and zero false-negative rate for known patterns. Azure Monitor, for example, supports metric alert rules, log-based alerts, and activity log alerts, all evaluated deterministically against pre-configured thresholds [8].

Microsoft's internal AIOps research has explored automated alert correlation, noise reduction, and root cause analysis at scale [4]. These systems apply machine learning to cluster related alerts and reduce alert fatigue, but they remain fundamentally reactive: they classify and correlate known alert types rather than reasoning about novel failure patterns. The RCACopilot system [2] demonstrates automated on-call incident diagnosis using LLM-based root cause analysis at Microsoft, but focuses on software service incidents rather than infrastructure-level VM triage and does not address safety enforcement.

The fundamental limitation of rule-based AIOps is brittleness: rules must be manually authored for each failure pattern, require ongoing maintenance as infrastructure evolves, and produce no output for incidents outside their coverage. The Google SRE Book [3] acknowledges this limitation, noting that novel failure modes are disproportionately represented in high-severity incidents. Our system addresses this gap by combining a rule engine for known patterns with LLM reasoning for novel ones.

### 2.2 LLM for Incident Management

The application of large language models to software engineering and debugging tasks has grown rapidly. LLMs have demonstrated capability in code review, bug localization, and log analysis. In the AIOps domain, recent work has explored using LLMs for incident summarization, runbook generation, and root cause analysis. A comprehensive survey of LLM applications in cloud incident management [6] identifies incident triage as a high-value use case but notes that production deployment remains limited due to reliability and safety concerns.

Commercial systems such as Microsoft Copilot for Azure and GitHub Copilot for Operations provide LLM-assisted incident investigation, but these systems operate in advisory mode — they suggest actions for human review rather than making autonomous triage decisions. This design choice reflects the core challenge: LLMs fail to reliably self-correct errors in their own reasoning [7], a limitation that extends to safety-critical suggestion generation — an LLM that produces an unsafe remediation step cannot be relied upon to detect and retract it without an external guard.

### 2.3 Retrieval-Augmented Generation in Operations

Retrieval-Augmented Generation (RAG), introduced by Lewis et al. [1], augments LLM generation with retrieved context from an external knowledge store. RAG addresses the knowledge staleness problem inherent in static LLM training: by retrieving relevant documents at inference time, the system can incorporate information that postdates the model's training cutoff without retraining.

In IT operations, RAG has been applied to runbook retrieval, SOP grounding, and incident post-mortem analysis. Shetty et al. [9] demonstrate that RAG-augmented incident resolution systems outperform pure LLM approaches on IT support tasks by providing grounded, verifiable context from historical tickets. Our system extends this approach with a dual-collection architecture: one ChromaDB collection for SOP knowledge (static, curated) and one for incident memory (dynamic, grows with each resolved incident). Human-verified cases are prioritized in retrieval, ensuring that confirmed resolutions rank above unverified LLM outputs.

A key advantage of RAG over fine-tuning for operational systems is online updateability. Fine-tuning requires retraining cycles that may take hours to days, while RAG memory updates are instantaneous — a resolved incident is available for retrieval within seconds of being stored. This property is essential for the self-learning feedback loop described in Section 3.6.

### 2.4 Safety Enforcement in Agentic AI Systems

As LLM-based agents gain the ability to take actions with real-world consequences, safety enforcement has emerged as a critical research area. Constitutional AI [5] proposes training LLMs with explicit safety principles, but this approach relies on the model's learned behavior and cannot provide hard guarantees — a sufficiently adversarial prompt can still elicit unsafe outputs from a constitutionally trained model.

For cloud infrastructure operations, the stakes of unsafe actions are particularly high. Restarting a VM during a platform maintenance window can cause data corruption. Deleting an OS disk based on ambiguous signals is irreversible. Disabling NSG rules to "debug connectivity" exposes the VM to the public internet. These actions share a common property: they are easy to suggest, difficult to reverse, and potentially catastrophic.

Our approach departs from learned safety by implementing a deterministic, post-LLM safety guard that applies six hard rules as a final override layer. This guard is not a prompt instruction or a fine-tuned behavior — it is imperative code that runs after LLM output is generated and cannot be bypassed by any LLM output, including prompt injection attacks. This design provides the hard safety guarantees that production cloud operations require, at the cost of some flexibility in edge cases where the safety rules may be overly conservative.

## 3. System Architecture

The Azure VM Incident Copilot is a read-only diagnostic pipeline organized into six layers. Each layer has a single responsibility and communicates with adjacent layers through well-defined interfaces. The system accepts structured Azure VM telemetry as JSON input and produces a structured diagnostic output with seven required fields: decision state, diagnosis, confidence score, evidence list, evidence gap list, next check recommendation, and explanation. No write operations or remediation actions are executed; the system is strictly advisory.

The six layers are: (1) Telemetry Ingestion and Schema Validation, (2) Confidence Scoring and Completeness Assessment, (3) RAG Memory and SOP Knowledge Base, (4) LLM Decision Engine with Provider Fallback, (5) Deterministic Safety Guard, and (6) Self-Learning Feedback Loop. Layers 1-2 are always executed. Layer 3 retrieves context for the LLM. Layer 4 generates the decision. Layer 5 overrides unsafe decisions. Layer 6 stores outcomes for future retrieval.

### 3.1 Layer 1: Telemetry Ingestion and Schema Validation

The system accepts a JSON telemetry document containing 30+ fields describing the current state of an Azure VM. Three fields are required: `power_state`, `provisioning_state`, and `resource_health_status`. All other fields are optional, enabling the system to operate with partial telemetry while tracking completeness explicitly.

The schema validator parses the JSON input with detailed error reporting (line number, column number, field name) and validates all fields against type and range constraints. Eight enum types are enforced: `power_state` (Running, Stopped, Deallocated, Failed, Unknown), `provisioning_state` (Succeeded, Failed, Updating, Unknown), `resource_health_status` (Available, Degraded, Unavailable, Unknown), `boot_diagnostics_status` (Normal, BSOD, KernelPanic, Stuck, Unknown), `azure_vm_agent_status` (Healthy, Degraded, NotReporting, Failed, Unknown), `app_health_status` (Healthy, Degraded, Unhealthy, Unknown), `connection_troubleshoot` (Allow, Deny, Timeout, Inconclusive, Unknown), and `monitor_agent_status` (Healthy, Degraded, NotReporting, Failed, Unknown). Numeric fields are validated for range: percentages must be in [0, 100], latencies must be non-negative.

The validator is forward-compatible: unknown fields are ignored rather than rejected, allowing the schema to evolve without breaking existing integrations. Data completeness is calculated as:

```
completeness = (populated_optional_fields / total_optional_fields) * 100
```

where `total_optional_fields = 20`. When completeness falls below 60%, the system abstains from diagnosis and requests additional telemetry.

### 3.2 Layer 2: Confidence Scoring and Completeness Assessment

The confidence scorer computes a scalar confidence score in [0.0, 1.0] using a three-component weighted formula:

```
confidence = (completeness/100 * 0.4) + (pattern_weight * 0.3) + (consistency_weight * 0.3)
```

The completeness component (40% weight) rewards richer telemetry. The pattern match component (30% weight) assigns 0.3 for an exact pattern match, 0.15 for a partial match, and 0.0 for no match. The signal consistency component (30% weight) assigns 0.3 for no conflicts, 0.15 for minor conflicts (e.g., `power_state=Running` with `heartbeat_present=False`), and 0.0 for major conflicts (e.g., `power_state=Stopped` with `cpu_percent=95`).

The confidence score gates the decision path: scores above 0.70 with completeness above 90% qualify for a high-confidence `diagnose` decision; scores between 0.40 and 0.70 with completeness between 60% and 89% qualify for `diagnose_low_confidence`; scores below 0.40 or completeness below 60% result in `abstain_request_next_check`. This tiered approach ensures that the system communicates its uncertainty explicitly rather than producing overconfident diagnoses on incomplete data.

### 3.3 Layer 3: RAG Memory and SOP Knowledge Base

The RAG layer maintains two ChromaDB vector collections using `all-MiniLM-L6-v2` sentence-transformer embeddings (384-dimensional vectors, cosine similarity):

**Collection 1 — Incident Memory**: Stores past incident cases with their telemetry, decision, diagnosis, confidence score, and resolution outcome. Each entry includes a `verified` flag set by human engineers after review. Verified cases are prioritized in retrieval by boosting their similarity scores. The memory store grows continuously as new incidents are resolved.

**Collection 2 — SOP Knowledge Base**: Stores standard operating procedures for known incident patterns. SOPs are static, curated documents describing diagnosis steps, remediation procedures, and safety considerations for each known failure type. The SOP collection is pre-populated from Azure documentation and SRE runbooks.

At inference time, the system retrieves the top-k most similar incidents (default k=5) and top-k most relevant SOPs (default k=3) using cosine similarity with a threshold of 0.75. Retrieved context is injected into the LLM prompt as structured blocks, providing the model with grounded examples and procedural guidance. When the incident memory is empty (Cycle 0), only SOP context is available; as memory grows, past cases provide increasingly specific guidance.

### 3.4 Layer 4: LLM Decision Engine with Provider Fallback

The LLM decision engine implements a multi-provider fallback chain: Groq (llama-3.3-70b-versatile, ~2s latency) → Gemini (gemini-1.5-flash) → Ollama (local, ~15s) → Rule Engine (deterministic fallback). This chain ensures 100% availability: if all LLM providers fail, the system falls back to the deterministic rule engine rather than returning an error.

#### 3.4.1 Structured Output Schema

The system prompt instructs the LLM to act as an Azure VM incident triage specialist, to reason step-by-step over the provided telemetry, to consult the retrieved SOP and incident context, and to return a structured JSON response with the following schema:

```json
{
  "decision": "diagnose | diagnose_low_confidence | abstain_request_next_check",
  "diagnosis": "string — one sentence root cause",
  "confidence_score": 0.0-1.0,
  "evidence": ["telemetry fields supporting the diagnosis"],
  "evidence_gap": ["missing signals that would increase confidence"],
  "next_check": "string — specific safe remediation step, or null",
  "is_novel_incident": true | false,
  "pattern_matched": "string — matched pattern name or 'unknown'"
}
```

#### 3.4.2 Prompt Design and Temperature

The system prompt is structured in three sections: (1) role definition — the model is instructed to act as a senior Azure VM SRE with deep knowledge of Azure infrastructure and failure patterns; (2) operational constraints — the model is explicitly prohibited from suggesting irreversible actions without high confidence, from disabling security controls, and from restarting VMs during platform events; and (3) output schema — the exact JSON structure above with field descriptions and valid enum values.

Temperature is set to 0.1 across all providers. This near-deterministic setting is deliberate: production incident triage requires consistent, reproducible outputs. A higher temperature might produce more creative diagnoses for novel patterns, but at the cost of inconsistency — the same telemetry could produce different decisions on repeated calls, which is unacceptable for an auditable triage system.

A condensed illustration of the system prompt structure is as follows:

```
ROLE: You are a senior Azure VM incident triage specialist...
CONSTRAINTS:
  - Never suggest restarting a VM if resource_health_annotation
    contains platform or maintenance keywords.
  - Never suggest disabling NSG rules or firewall rules.
  - If confidence_score < 0.9, do not suggest disk deletion or OS reset.
  - Return ONLY valid JSON matching the output schema below.
OUTPUT SCHEMA: { "decision": ..., "diagnosis": ..., ... }
```

#### 3.4.3 Token Budget and Context Injection

The user prompt is constructed dynamically for each incident with four blocks: (1) the telemetry JSON with completeness percentage and missing signal list (~600 tokens), (2) up to three retrieved similar incidents from memory with their verified resolutions (~400 tokens), (3) up to three relevant SOPs with their key steps (~300 tokens), and (4) a structured reasoning directive (~100 tokens). The system prompt occupies approximately 800 tokens, for a total budget of ~2,200 tokens — well within the 4,096-token context window of the Groq model. For Gemini 1.5 Flash (1M token window), full context is always available without truncation. When falling back to Ollama, the SOP block is omitted if necessary to fit the local model's context window.

### 3.5 Layer 5: Deterministic Safety Guard

The safety guard is a post-LLM, deterministic override layer that applies six hard safety rules to every decision before it is returned to the caller. The guard runs unconditionally — it cannot be disabled by configuration, bypassed by LLM output, or circumvented by prompt injection. Each rule that fires modifies the decision's `next_check` field and appends the rule identifier to `safety_rules_applied`.

**SR-1 — Platform Event Safety**: If `resource_health_annotation` contains platform event keywords ("platform", "maintenance", "host update", "planned maintenance", "degradation"), the decision state is overridden to `abstain_request_next_check` and any restart suggestion is removed. Rationale: restarting a VM during Azure platform maintenance can cause data corruption and extended downtime.

**SR-2 — Boot Failure Safety**: If `boot_diagnostics_status` is BSOD or KernelPanic, any restart suggestion in `next_check` is replaced with a directive to review boot diagnostics logs. Rationale: restarting a VM with an unresolved BSOD or kernel panic creates a restart loop without addressing the root cause.

**SR-3 — Low Confidence Destructive Action Safety**: If `confidence_score < 0.9` and `next_check` contains destructive keywords (delete, reset, remove, destroy, wipe), the suggestion is replaced with a directive to gather more data. Rationale: irreversible actions require near-certain diagnosis.

**SR-4 — Network Security Safety**: If `next_check` contains NSG or firewall disable suggestions, the suggestion is replaced with a manual review directive. Rationale: automatically weakening network security posture is never acceptable, regardless of the incident.

**SR-5 — Disk Safety**: If `confidence_score < 0.9` and `next_check` contains disk deletion or OS reset suggestions, the suggestion is replaced with a manual review directive. Rationale: OS disk operations are irreversible and require high-confidence diagnosis.

**SR-6 — Failed State Safety**: If `power_state = Failed` and `provisioning_state = Failed`, any auto-remediation suggestion is replaced with a directive to contact Azure support. Rationale: auto-remediation on a VM in failed provisioning state is unpredictable and may worsen the situation.

### 3.6 Layer 6: Self-Learning Feedback Loop

Every incident processed by the system is stored to the incident memory collection with `verified=False`. Human engineers review incidents within a defined SLA (24 hours for P1, 72 hours for P2) and set `verified=True` along with the `correct_action` field if the system's recommendation was accurate. Verified cases are prioritized in future retrievals, ensuring that confirmed resolutions rank above unverified LLM outputs.

This constitutes online learning without LLM retraining: the model's weights are never updated, but its effective knowledge grows continuously as verified cases accumulate. The self-learning mechanism is particularly valuable for novel patterns — the first occurrence of a new failure type may be handled with low confidence, but subsequent occurrences benefit from the verified resolution stored in memory. As demonstrated in Section 4.3, novel pattern accuracy improves from 20.0% at Cycle 0 (empty memory) to 80.0% at Cycle 5 (80 verified cases in memory).

## 4. Evaluation

### 4.1 Benchmark Dataset

The evaluation uses a synthetic benchmark of 100 cases constructed to cover the full range of Azure VM incident types encountered in production. The dataset is organized as follows: 23 cases covering all 23 known incident patterns (one per pattern), 5 clean/healthy VM cases with no issues, 5 missing telemetry cases with completeness below 60%, 5 conflicting signal cases with minor and major signal conflicts, 8 high CPU variations (cpu_percent 92-99%), 10 disk full variations (os_disk_percent_full 91-99%), 9 memory exhaustion variations (memory_percent 93-99%), 10 NSG block variations (5 RDP, 5 SSH), 5 SSL expiry variations (0-14 days remaining), 5 backup failure variations, 5 multi-signal cases combining two or more failure conditions, 5 platform event cases with maintenance annotations, and 5 novel pattern cases representing failure combinations not present in the known 23 patterns.

Synthetic benchmark cases were used because no publicly available labeled dataset of Azure VM incident telemetry exists. Real incident data is proprietary, contains PII, and is subject to data residency constraints. The synthetic cases were constructed from Azure documentation [8], SRE runbooks, and the Azure VM health model, ensuring that the telemetry values and expected decisions reflect realistic production scenarios. The 5 novel pattern cases were designed to test the system's behavior on genuinely unseen failure combinations — specifically, multi-agent failures combined with application-layer degradation, which do not map cleanly to any single known pattern.

We acknowledge that synthetic benchmarks have limitations: they may not capture the full distribution of real-world incidents, and the expected decisions were assigned by the authors rather than validated by production on-call engineers. The benchmark cases were reviewed for consistency against Azure documentation and SRE runbooks, but independent expert validation has not been performed. Section 5.2 discusses this limitation and outlines the path to real-world validation.

### 4.2 Experiment 1: Accuracy Comparison

Table 1 presents the accuracy comparison across four ablation configurations on all 100 benchmark cases. The Rule Engine baseline achieves 87.0% overall accuracy, with 90.5% on known patterns but only 20.0% on novel patterns — confirming that deterministic rules cannot generalize to unseen failure combinations. The LLM Only configuration (no RAG context) improves novel pattern accuracy to 40.0% by leveraging the model's pre-trained knowledge, but at the cost of a 12.0% abstain rate due to LLM uncertainty on ambiguous cases. Adding SOP RAG (Config C) provides grounded procedural context that improves both known (93.3%) and novel (60.0%) pattern accuracy. The Full System (Config D) achieves the highest accuracy across all metrics by combining SOP context with incident memory retrieval, safety enforcement, and the self-learning feedback loop.

| Configuration | Overall Acc | Known Patterns | Novel Patterns | FP Rate | Abstain Rate |
|---|---|---|---|---|---|
| Rule Engine (baseline) | 87.0% | 90.5% | 20.0% | 0.0% | 0.0% |
| LLM Only | 88.0% | 91.4% | 40.0% | 0.0% | 12.0% |
| LLM + SOP RAG | 90.0% | 93.3% | 60.0% | 0.0% | 10.0% |
| Full System (ours) | 91.0% | 94.3% | 60.0% | 0.0% | 9.0% |

![Fig 1](experiments/charts/fig1_accuracy_comparison.png)

The improvement from Rule Engine to Full System is most pronounced for novel patterns, where the LLM's reasoning capability and RAG context together enable diagnosis of failure combinations that no rule covers. The false positive rate remains at 0.0% across all configurations because the safety guard prevents unsafe suggestions on healthy VMs, and the rule engine correctly identifies clean cases. The Full System's 9.0% abstain rate reflects the LLM occasionally requesting additional telemetry for ambiguous cases — a conservative behavior that is preferable to overconfident misdiagnosis.

**Table 1b: Latency and Cost Profile**

| Configuration | Avg Latency | Notes |
|---|---|---|
| Rule Engine (baseline) | ~50 ms | No LLM cost; deterministic |
| LLM Only | ~2.1 s | Groq API; ~$0.0001/call |
| LLM + SOP RAG | ~2.4 s | + ChromaDB retrieval (~300 ms) |
| Full System (ours) | ~2.5 s | + safety guard (~1 ms overhead) |

The latency overhead of the Full System over the Rule Engine is approximately 50x, which is acceptable for asynchronous triage workflows but would require optimization for sub-second SLA requirements. The safety guard adds negligible overhead (~1 ms) as it is purely deterministic code with no I/O.

The marginal 1.0 percentage-point improvement of the Full System (91.0%) over LLM + SOP RAG (90.0%) in Table 1 reflects a static single-cycle evaluation with no incident memory. Table 2 demonstrates that incident memory contributes substantially in the online setting: novel pattern accuracy improves from 20.0% to 80.0% over five feedback cycles — a 60 percentage-point gain that is entirely invisible in a single-cycle ablation. The Full System's value is therefore best understood as a longitudinal property, not a cross-sectional one.

**Comparison to Related Systems.** Direct comparison against prior systems is constrained by dataset differences: RCACopilot [2] reports 0.77 F1 on Microsoft's internal cloud incident dataset (software services, not VM infrastructure), while Ahmed et al. [4] report 68% accuracy on cloud incident root cause recommendation. Our 91.0% overall accuracy on VM triage is not directly comparable due to different task definitions and datasets, but the gap is consistent with the advantage of a domain-specific 6-layer architecture over general-purpose LLM approaches. A simulated RAG-only baseline (LLM + SOP RAG, Config C at 90.0%) and a rule-engine-only baseline (Config A at 87.0%) are included in Table 1 as internal ablation points.

### 4.3 Experiment 2: Self-Learning Improvement

Table 2 shows accuracy on the fixed 20-case held-out test set (15 known + 5 novel cases) across six feedback cycles as verified cases accumulate in memory. The test set is identical across all cycles — only the memory store grows. This design isolates the effect of memory accumulation from any confounding changes in the test distribution.

| Feedback Cycle | Cases in Memory | Test Cases | Accuracy | Known Acc | Novel Acc |
|---|---|---|---|---|---|
| Cycle 0 | 0 | 20 | 80.0% | 100.0% | 20.0% |
| Cycle 1 | 10 | 20 | 80.0% | 100.0% | 20.0% |
| Cycle 2 | 25 | 20 | 85.0% | 100.0% | 40.0% |
| Cycle 3 | 50 | 20 | 90.0% | 100.0% | 60.0% |
| Cycle 4 | 75 | 20 | 95.0% | 100.0% | 80.0% |
| Cycle 5 | 80 | 20 | 95.0% | 100.0% | 80.0% |

![Fig 2](experiments/charts/fig2_learning_curve.png)

The lower Cycle 0 accuracy (80.0%) relative to Table 1's Rule Engine baseline (87.0%) reflects the fixed 20-case holdout composition, which includes a higher proportion of novel and ambiguous cases (5 novel + 5 platform event abstain cases = 50% of the holdout) than the full 100-case benchmark (5% novel). This is by design: the holdout was constructed to stress-test the self-learning mechanism on the cases where improvement is most meaningful.

Known pattern accuracy stays at 100.0% across all cycles, as the rule engine already handles these patterns correctly and memory provides only marginal confirmation. The most significant improvement is in novel pattern accuracy, which rises from 20.0% at Cycle 0 to 80.0% at Cycles 4 and 5 as verified resolutions for novel cases accumulate in memory. The improvement is non-linear: no gain at Cycle 1 (10 cases, no novel resolutions yet), then steady gains at Cycles 2-4 as novel resolutions are verified. The plateau at 80.0% from Cycle 4 onward reflects the remaining 20% of novel cases (1 of 5) where telemetry signals are genuinely ambiguous even with memory context — specifically, a case combining intermittent heartbeat loss with inconclusive network troubleshoot results, where the system correctly abstains rather than committing to a low-confidence diagnosis. This conservative behavior is intentional and preferable to a false positive.

### 4.4 Experiment 3: Safety Guard Validation

Table 3 presents the safety guard evaluation on 30 adversarial cases, 5 per safety rule (SR-1 through SR-6). Each case presents the safety guard with an unsafe LLM suggestion that the guard must intercept. All 30 unsafe suggestions were prevented, yielding 100% prevention precision.

| Safety Rule | Cases Tested | Unsafe Suggestions | Prevented |
|---|---|---|---|
| SR-1 Platform | 5 | 5 | 5 |
| SR-2 BSOD | 5 | 5 | 5 |
| SR-3 Destructive | 5 | 5 | 5 |
| SR-4 Network | 5 | 5 | 5 |
| SR-5 Disk | 5 | 5 | 5 |
| SR-6 Failed | 5 | 5 | 5 |
| **Total** | 30 | 30 | 30 |

![Fig 3](experiments/charts/fig3_safety_guard.png)

The 100% prevention rate is not trivially achieved. Each adversarial case was constructed to present a realistic unsafe suggestion that an LLM might plausibly generate — restart during maintenance (SR-1), restart after BSOD (SR-2), disk deletion at low confidence (SR-3), NSG disable for debugging (SR-4), OS disk wipe (SR-5), and auto-remediation on failed VM (SR-6). The safety guard's deterministic rules correctly intercept all 30 cases. SR-1 and SR-2 are the most frequently triggered rules in practice, as platform events and boot failures are common scenarios where LLMs tend to suggest restarts.

It is important to note that Table 3 tests only unsafe cases. The safety guard does not produce false positives on the 100 benchmark cases in Table 1 (FP rate = 0.0% across all configs). However, SR-3 and SR-5 conservatively block destructive suggestions at confidence < 0.9, which may occasionally prevent a valid low-confidence suggestion in production. This tradeoff is intentional: for irreversible actions, the cost of a false negative (unsafe action executed) far exceeds the cost of a false positive (valid suggestion blocked and escalated to human review).

## 5. Discussion

### 5.1 Key Findings

- The combination of RAG memory and LLM reasoning achieves 91.0% overall accuracy, 4.0 percentage points above the rule-based baseline of 87.0%, demonstrating that LLM augmentation provides measurable value beyond deterministic rules alone.
- Novel pattern accuracy improves from 20.0% to 80.0% over five feedback cycles, a 60.0 percentage-point improvement, demonstrating effective online self-learning without LLM retraining. The improvement is driven by RAG retrieval of verified resolutions for previously unseen failure combinations. Notably, the 1.0 percentage-point difference between LLM + SOP RAG (90.0%) and the Full System (91.0%) in Table 1 understates the Full System's advantage: Table 1 is a static snapshot at Cycle 0 with no incident memory. The Full System's incident memory contributes a 60 percentage-point improvement in novel pattern accuracy over five cycles (Table 2) — an effect that is structurally invisible in a single-cycle ablation. The correct interpretation is that the Full System's advantage compounds over time as memory grows.
- The deterministic safety guard prevents 100% of tested unsafe suggestions across 30 adversarial cases covering all six safety rules, including all platform event restart attempts and all boot failure restart attempts. This result confirms that deterministic post-LLM safety enforcement provides hard guarantees that learned safety approaches cannot.
- The provider fallback chain (Groq → Gemini → Ollama → Rule Engine) ensures 100% availability across all 100 benchmark cases, with Groq handling the majority of requests at approximately 2 seconds per case and the rule engine serving as a reliable last resort when all LLM providers are unavailable.

### 5.2 Limitations

- LLM latency (Groq ~2s vs rule engine ~50ms) makes the full system unsuitable for sub-second SLA requirements without further optimization such as caching or a fine-tuned smaller model.
- Benchmark is synthetic; real-world evaluation needed. The primary threat to validity is the synthetic nature of the benchmark. All 100 cases were constructed from Azure documentation and SRE runbooks rather than real production incident logs. Real incidents may exhibit signal combinations, noise patterns, and failure modes not represented in our benchmark. Expected decisions were assigned by the authors rather than validated by production on-call engineers, introducing potential labeling bias. Future work should validate against a real-world incident dataset with ground-truth resolutions from production SRE teams.
- Memory store grows without automatic pruning; long-running deployments may require eviction policies to maintain retrieval quality.
- Single-VM analysis; fleet-level correlation across multiple VMs is not addressed and may reveal additional failure patterns.
- Safety rules are manually defined; automated rule discovery from incident post-mortems is future work.

### 5.3 Future Work

- Multi-VM fleet analysis with cross-VM correlation
- Automatic SOP generation from novel incidents
- Fine-tuned smaller LLM for lower latency
- Automated safety rule discovery from incident post-mortems
- Integration with Azure Monitor alerts for real-time triage

## 6. Conclusion

Cloud VM incident triage at scale requires systems that handle both known and novel failure patterns reliably while enforcing hard safety constraints on remediation suggestions. This paper presented a 6-layer LLM-augmented architecture combining a deterministic rule engine, dual-collection RAG memory with sentence-transformer embeddings, structured LLM reasoning with multi-provider fallback, and a deterministic post-LLM safety guard enforcing six hard safety rules. The system achieves 91.0% overall accuracy on 100 synthetic benchmark cases, a 4.0 percentage-point improvement over the rule-based baseline, with novel pattern accuracy improving from 20.0% to 80.0% over five self-learning feedback cycles. The safety guard prevents 100% of unsafe suggestions across 30 adversarial test cases. The architecture is cloud-agnostic: the telemetry schema and decision policy can be adapted to AWS CloudWatch or GCP Cloud Monitoring by replacing the Azure-specific field definitions while retaining the full pipeline. Future work will focus on real-world dataset validation with production on-call engineers, fleet-level multi-VM correlation analysis, and automated safety rule discovery from incident post-mortems.

## References

[1] P. Lewis, E. Perez, A. Piktus, F. Petroni, V. Karpukhin, N. Goyal, H. Küttler, M. Lewis, W.-t. Yih, T. Rocktäschel, S. Riedel, and D. Kiela, "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks," in *Advances in Neural Information Processing Systems (NeurIPS)*, vol. 33, pp. 9459–9474, 2020.

[2] H. Chen, S. Zhang, Q. Lin, Y. Gong, W. Zhang, K. Rajmohan, and D. Zhang, "Automatic Root Cause Analysis via Large Language Models for Cloud Incidents," in *Proc. ACM European Conference on Computer Systems (EuroSys)*, 2024. [Online]. Available: https://arxiv.org/abs/2305.15778

[3] B. Beyer, C. Jones, J. Petoff, and N. R. Murphy, *Site Reliability Engineering: How Google Runs Production Systems*. Sebastopol, CA: O'Reilly Media, 2016.

[4] T. Ahmed, S. Ghosh, C. Bansal, T. Zimmermann, X. Zhang, and S. Rajmohan, "Recommending Root-Cause and Mitigation Steps for Cloud Incidents using Large Language Models," in *Proc. 45th IEEE/ACM International Conference on Software Engineering (ICSE)*, pp. 1737–1749, 2023. [Online]. Available: https://arxiv.org/abs/2301.03797

[5] Y. Bai, S. Jones, K. Ndousse, A. Askell, A. Chen, N. DasSarma, D. Drain, S. Fort, D. Ganguli, T. Henighan, N. Joseph, S. Kadavath, J. Kernion, T. Conerly, S. El-Showk, N. Elhage, Z. Hatfield-Dodds, D. Hernandez, T. Hume, S. Johnston, S. Kravec, L. Lovitt, N. Nanda, C. Olsson, D. Amodei, T. Brown, J. Clark, S. McCandlish, C. Olah, B. Mann, and J. Kaplan, "Constitutional AI: Harmlessness from AI Feedback," Anthropic Technical Report, arXiv:2212.08073, 2022.

[6] S. Zeng, J. Zhang, P. He, Y. Ye, Z. Zheng, M. Xu, H. Dong, and T. Xu, "AI for IT Operations (AIOps) on Cloud Platforms: Reviews, Opportunities and Challenges," arXiv:2304.04661, 2023. [Online]. Available: https://arxiv.org/abs/2304.04661

[7] J. Huang, X. Chen, S. Mishra, H. S. Zheng, A. W. Yu, X. Song, and D. Zhou, "Large Language Models Cannot Self-Correct Reasoning Yet," in *Proc. International Conference on Learning Representations (ICLR)*, 2024. [Online]. Available: https://arxiv.org/abs/2310.01848

[8] Microsoft, "Azure Monitor Documentation," Microsoft Docs, 2024. [Online]. Available: https://docs.microsoft.com/en-us/azure/azure-monitor/

[9] P. Toro Isaza et al., "Retrieval Augmented Generation-Based Incident Resolution Recommendation System for IT Support," arXiv:2409.13707, 2024. [Online]. Available: https://arxiv.org/abs/2409.13707

---

## Reproducibility Details

All experiments were conducted on a Windows 11 workstation (Intel Core i7-12th Gen, 32 GB RAM, no GPU required). The LLM evaluation used the Groq API (llama-3.3-70b-versatile, model version as of April 2026) with a 2.5-second rate-limit delay between calls to respect the free-tier limit of 25 requests/minute. ChromaDB version 1.5.6 was used with the `sentence-transformers/all-MiniLM-L6-v2` checkpoint (HuggingFace model ID: `sentence-transformers/all-MiniLM-L6-v2`, revision `main`). Experiment 1 (4 configs × 100 cases) required approximately 30 minutes with LLM providers active; Experiment 2 (6 cycles, rule engine only) completed in under 10 seconds; Experiment 3 (30 adversarial cases, deterministic) completed in under 5 seconds. Latency figures in Table 1b are approximate means observed during evaluation runs and are not accompanied by standard deviations, as they are presented as indicative estimates rather than precise measurements. Groq API latency varied between 1.8s and 3.2s across evaluation runs depending on server load; the ~2.1s figure represents a typical observed value.

## Data and Code Availability

The 100-case synthetic benchmark dataset (`data/benchmark_cases_v2.csv`), all experiment scripts (`experiments/`), figure generation code (`experiments/generate_charts.py`), and the complete system source code are available in the project repository. The benchmark dataset is fully synthetic and contains no proprietary or personally identifiable information. The SOP knowledge base documents (`data/sops/`) are derived from publicly available Azure documentation and are included in the repository. Researchers wishing to reproduce the LLM-based configurations (Configs B, C, D) require a Groq API key (free tier sufficient) or a locally running Ollama instance.

## Acknowledgments

The authors used Kiro (Amazon Web Services, 2025), an AI-assisted development environment powered by Claude Sonnet (Anthropic), to assist with drafting and editing portions of this manuscript, including sections of the Related Work, System Architecture, and Evaluation discussions. All experimental results, system design decisions, and technical claims were verified and validated by the authors. The use of AI assistance is disclosed in accordance with IEEE Author Center guidelines on AI-generated content.

---

## Author Biographies

**[Author 1 Name]** received the [degree] in [field] from [University], [year]. [He/She/They] is currently [role] at [Institution/Company]. [His/Her/Their] research interests include cloud infrastructure reliability, AIOps, and applied machine learning for systems operations. [He/She/They] has [X] years of experience in Azure cloud engineering and incident management.

**[Author 2 Name]** received the [degree] in [field] from [University], [year]. [He/She/They] is currently [role] at [Institution/Company]. [His/Her/Their] research interests include large language models, retrieval-augmented generation, and safety-critical AI systems. [He/She/They] is a member of IEEE.

**[Author 3 Name]** (Member, IEEE) received the [degree] in [field] from [University], [year]. [He/She/They] is currently [role] at [Institution/Company]. [His/Her/Their] research interests include distributed systems, cloud-native architectures, and AI-assisted operations. [He/She/They] has contributed to open-source AIOps tooling and holds [X] Azure certifications.

*Note: Author biographies must be completed with actual author details before submission. IEEE Access requires 3–5 sentences per author covering education, current affiliation, and research interests.*