# LLM-Augmented Azure VM Incident Triage with RAG Memory and Deterministic Safety Enforcement

## Abstract

Cloud infrastructure incidents require triage systems that are both accurate and safe. Rule-based AIOps systems are reliable for known failure patterns but do not generalize to unseen signal combinations, while large language models can reason over novel incidents but may generate unsafe remediation suggestions. This paper presents a six-layer read-only architecture for Azure VM incident triage that combines a deterministic rule engine, dual-collection retrieval-augmented generation (RAG) memory, structured LLM reasoning with provider fallback, and a deterministic post-LLM safety guard enforcing six hard safety rules. We evaluate the system on a 100-case synthetic benchmark spanning 23 known incident patterns and 5 novel patterns, constructed from Azure documentation and public SRE runbooks. The rule engine with safety guard achieves 88.0% accuracy (88/100), while removing the safety guard reduces accuracy to 82.0%, primarily because platform-event cases are no longer correctly forced to abstention. LLM-only triage achieves lower overall accuracy (73.0%) but higher novel-pattern accuracy than the rule baseline (60.0% vs 20.0%), indicating potential value for unseen incidents. LLM+SOP RAG and the full system each achieve 86.0% accuracy in the static benchmark, suggesting that incident memory provides limited benefit in one-pass evaluation. In a separate 20-case longitudinal experiment, novel-pattern accuracy improves from 20.0% to 80.0% over five feedback-driven memory-update cycles, though the small novel subset (n=5) makes this result directional rather than conclusive. The safety guard intercepts all 30 hand-crafted unsafe suggestions in the adversarial test set and produces no false blocks on healthy benchmark VMs. These results suggest that deterministic post-generation safety checks and feedback-driven retrieval memory are feasible design patterns for LLM-assisted cloud triage, but real incident validation and independent expert labeling remain necessary.

## 1. Introduction

### 1.1 Problem Statement

Cloud infrastructure downtime carries severe financial and operational consequences. Industry surveys place the average cost of high-impact unplanned data-center outages in the hundreds of thousands of dollars per hour, with the most disruptive events reaching seven-figure totals [10]. Hyperscale cloud providers manage millions of virtual machine instances across global regions, and at this scale even a 0.1% incident rate generates thousands of simultaneous alerts — far beyond what on-call engineering teams can triage manually. Automated incident triage is therefore not a convenience but an operational necessity.

Current AIOps systems for cloud VM triage are predominantly rule-based. Azure Monitor alert rules, Prometheus AlertManager, and similar platforms apply deterministic threshold conditions to telemetry streams: if CPU exceeds 95% for five minutes, fire an alert. These systems are fast, auditable, and reliable for known failure patterns. However, they require manual threshold tuning for each metric, cannot generalize across correlated multi-signal failures, and fail entirely when incidents involve patterns not anticipated at rule-authoring time. In practice, novel failure modes — new OS versions, unexpected interaction effects between services, infrastructure changes — account for a disproportionate share of high-severity incidents precisely because they are not covered by existing rules [2].

Large language models offer a compelling alternative for novel pattern reasoning. An LLM can read free-form telemetry, reason over signal combinations, and generate contextually appropriate remediation suggestions without requiring explicit rule definitions. However, LLMs introduce a critical risk in production operations: hallucination. An LLM that confidently suggests restarting a VM during an active platform maintenance window, or recommends deleting an OS disk based on ambiguous signals, can cause data corruption or extended downtime that is worse than the original incident. Few published systems describe a deterministic post-generation safety layer for LLM-generated cloud remediation suggestions in sufficient detail to evaluate its effect on triage safety.

The gap this paper addresses is the absence of a system that combines: (a) a strong deterministic rule baseline for known patterns, (b) LLM reasoning for novel patterns, (c) RAG memory for cumulative knowledge accumulation without retraining, and (d) deterministic post-LLM safety enforcement that cannot be bypassed by any LLM output. We present such a system and evaluate it empirically on 100 benchmark cases.

### 1.2 Contributions

1. A 6-layer architecture for LLM-assisted Azure VM incident triage that combines a deterministic rule baseline, dual-collection RAG memory, structured LLM reasoning, and a deterministic post-LLM safety guard. On a 100-case synthetic benchmark the rule engine with safety guard reaches 88.0% overall accuracy; a safety-guard ablation shows a 6-percentage-point improvement (82.0% → 88.0%).
2. A dual-collection RAG design that separates static SOP knowledge from a growing incident memory of human-verified resolutions, enabling *feedback-driven memory updates* without any LLM retraining. In a longitudinal evaluation on a 20-case held-out set, novel-pattern accuracy rises from 20.0% to 80.0% over five cycles of memory growth; we deliberately avoid calling this "learning" because no model weights change.
3. A deterministic, post-LLM safety guard that applies six hard safety rules as an unconditional override. Against 30 hand-crafted adversarial suggestions spanning all six rules the guard intercepts every one; on the 100-case benchmark it produces no false blocks on healthy VMs. We position this as an *important* architectural component under the evaluated conditions, rather than a necessary one in the absolute sense — establishing necessity requires head-to-head comparison with alternative safety mechanisms that we leave to future work.
4. A fully-reproducible synthetic benchmark of 100 cases spanning 23 known patterns and 5 novel patterns, together with evaluation scripts, per-case detail records, and safety-ablation results, so that the claims in Section 4 can be independently re-verified.

## 2. Related Work

### 2.1 Rule-Based AIOps

Traditional IT operations monitoring relies on threshold-based alerting systems such as Nagios, Prometheus AlertManager, and Azure Monitor native alert rules. These systems evaluate deterministic conditions against telemetry streams and fire alerts when thresholds are breached. Their primary advantages are speed, auditability, and zero false-negative rate for known patterns. Azure Monitor, for example, supports metric alert rules, log-based alerts, and activity log alerts, all evaluated deterministically against pre-configured thresholds [8]. A broader survey of AIOps failure-management techniques [11] distinguishes detection, localization, and remediation stages, and observes that most production deployments remain detection- and correlation-oriented, with remediation still largely operator-driven. Multivariate anomaly-detection methods on service-level time series [12] further illustrate the state of practice before LLM-based reasoning was introduced.

Microsoft's internal AIOps research has explored automated alert correlation, noise reduction, and root cause analysis at scale [4]. These systems apply machine learning to cluster related alerts and reduce alert fatigue, but they remain fundamentally reactive: they classify and correlate known alert types rather than reasoning about novel failure patterns. The RCACopilot system [2] demonstrates automated on-call incident diagnosis using LLM-based root cause analysis at Microsoft, but focuses on software service incidents rather than infrastructure-level VM triage and does not address safety enforcement.

The fundamental limitation of rule-based AIOps is brittleness: rules must be manually authored for each failure pattern, require ongoing maintenance as infrastructure evolves, and produce no output for incidents outside their coverage. The Google SRE Book [3] acknowledges this limitation, noting that novel failure modes are disproportionately represented in high-severity incidents. Our system addresses this gap by combining a rule engine for known patterns with LLM reasoning for novel ones.

### 2.2 LLM for Incident Management

The application of large language models to software engineering and debugging tasks has grown rapidly, enabled by transformer architectures [16], pre-trained bidirectional encoders [17], and instruction-tuned generative models [13]. LLMs have demonstrated capability in code review, bug localization, and log analysis. In the AIOps domain, recent work has explored using LLMs for incident summarization, runbook generation, and root cause analysis. A comprehensive survey of LLM applications in cloud incident management [6] identifies incident triage as a high-value use case but notes that production deployment remains limited due to reliability and safety concerns.

Commercial systems such as Microsoft Copilot for Azure and GitHub Copilot for Operations provide LLM-assisted incident investigation, but these systems operate in advisory mode — they suggest actions for human review rather than making autonomous triage decisions. This design choice reflects the core challenge: LLMs fail to reliably self-correct errors in their own reasoning [7], a limitation that extends to safety-critical suggestion generation. An LLM that produces an unsafe remediation step cannot be relied upon to detect and retract it without an external guard.

### 2.3 Retrieval-Augmented Generation in Operations

Retrieval-Augmented Generation (RAG), introduced by Lewis et al. [1], augments LLM generation with retrieved context from an external knowledge store. RAG relies on dense sentence embeddings such as those produced by the Sentence-BERT family [15], which our implementation uses via the `all-MiniLM-L6-v2` checkpoint. It addresses the knowledge staleness problem inherent in static LLM training: by retrieving relevant documents at inference time, the system can incorporate information that postdates the model's training cutoff without retraining.

In IT operations, RAG has been applied to runbook retrieval, SOP grounding, and incident post-mortem analysis. Shetty et al. [9] demonstrate that RAG-augmented incident resolution systems outperform pure LLM approaches on IT support tasks by providing grounded, verifiable context from historical tickets. Our system extends this approach with a dual-collection architecture: one ChromaDB collection for SOP knowledge (static, curated) and one for incident memory (dynamic, grows with each resolved incident). Human-verified cases are prioritized in retrieval, ensuring that confirmed resolutions rank above unverified LLM outputs.

A key advantage of RAG over fine-tuning for operational systems is online updateability. Fine-tuning requires retraining cycles that may take hours to days, while RAG memory updates are instantaneous — a resolved incident is available for retrieval within seconds of being stored. This property is what enables the feedback-driven memory-update loop described in Section 3.6; we deliberately avoid the term "learning" for this loop because no model weights are updated.

**Positioning against nearest-neighbor case retrieval.** A simpler alternative to our RAG+LLM design is pure nearest-neighbor (NN) case retrieval: given a new incident, find the most similar past case and return its resolution. NN retrieval is fast and interpretable, but it has two limitations for our setting. First, it cannot generalize to novel incidents that have no close neighbors in memory — it can only interpolate, not reason. Second, it cannot apply safety constraints: a NN system that retrieves a case whose resolution was "restart the VM" will return that resolution regardless of whether the current incident involves a platform maintenance event. Our design uses NN retrieval (via ChromaDB cosine similarity) as a *context source* for the LLM, not as the decision mechanism itself, combining the interpretability of case-based reasoning with the generalization and safety-enforcement capabilities of the LLM+guard pipeline.

### 2.4 Safety Enforcement in Agentic AI Systems

As LLM-based agents gain the ability to take actions with real-world consequences, safety enforcement has emerged as a critical research area. Constitutional AI [5] proposes training LLMs with explicit safety principles, but this approach relies on the model's learned behavior and cannot provide hard guarantees — red-teaming studies [18] and automated adversarial-suffix attacks [19] have shown that sufficiently adversarial prompts can still elicit unsafe outputs from constitutionally trained models.

For cloud infrastructure operations, the stakes of unsafe actions are particularly high. Restarting a VM during a platform maintenance window can cause data corruption. Deleting an OS disk based on ambiguous signals is irreversible. Disabling NSG rules to "debug connectivity" exposes the VM to the public internet. These actions share a common property: they are easy to suggest, difficult to reverse, and potentially catastrophic.

Our approach complements learned safety with a deterministic, post-LLM safety guard that applies six hard rules as a final override layer. The guard is not a prompt instruction or a fine-tuned behavior; it is imperative code that runs after LLM output is generated and cannot be bypassed by any LLM output, including prompt-injection or suffix attacks. This design provides the hard safety guarantees that production cloud operations require, at the cost of some flexibility in edge cases where the safety rules may be overly conservative. We position the guard as an important architectural component for the settings we evaluate, rather than as a universally necessary one; establishing necessity in a stricter sense would require head-to-head comparison with prompt-only, constrained-decoding, and classifier-validator alternatives, which we leave to future work.

## 3. System Architecture

The Azure VM Incident Copilot is a read-only diagnostic pipeline organized into six layers. Each layer has a single responsibility and communicates with adjacent layers through well-defined interfaces. The system accepts structured Azure VM telemetry as JSON input and produces a structured diagnostic output with seven required fields: decision state, diagnosis, confidence score, evidence list, evidence gap list, next check recommendation, and explanation. No write operations or remediation actions are executed; the system is strictly advisory.

The six layers are: (1) Telemetry Ingestion and Schema Validation, (2) Confidence Scoring and Completeness Assessment, (3) RAG Memory and SOP Knowledge Base, (4) LLM Decision Engine with Provider Fallback, (5) Deterministic Safety Guard, and (6) Feedback-Driven Memory Update Loop. Layers 1-2 are always executed. Layer 3 retrieves context for the LLM. Layer 4 generates the decision. Layer 5 overrides unsafe decisions. Layer 6 stores outcomes for future retrieval.

### 3.1 Layer 1: Telemetry Ingestion and Schema Validation

The system accepts a JSON telemetry document containing 30+ fields describing the current state of an Azure VM. Three fields are required: `power_state`, `provisioning_state`, and `resource_health_status`. All other fields are optional, enabling the system to operate with partial telemetry while tracking completeness explicitly.

The schema validator parses the JSON input with detailed error reporting (line number, column number, field name) and validates all fields against type and range constraints. Eight enum types are enforced: `power_state` (Running, Stopped, Deallocated, Failed, Unknown), `provisioning_state` (Succeeded, Failed, Updating, Unknown), `resource_health_status` (Available, Degraded, Unavailable, Unknown), `boot_diagnostics_status` (Normal, BSOD, KernelPanic, Stuck, Unknown), `azure_vm_agent_status` (Healthy, Degraded, NotReporting, Failed, Unknown), `app_health_status` (Healthy, Degraded, Unhealthy, Unknown), `connection_troubleshoot` (Allow, Deny, Timeout, Inconclusive, Unknown), and `monitor_agent_status` (Healthy, Degraded, NotReporting, Failed, Unknown). Numeric fields are validated for range: percentages must be in [0, 100], latencies must be non-negative.

The validator is forward-compatible: unknown fields are ignored rather than rejected, allowing the schema to evolve without breaking existing integrations. Data completeness is calculated as:

```
completeness = (populated_optional_fields / total_optional_fields) * 100
```

where `total_optional_fields = 20`. When completeness falls below 60%, the system abstains from diagnosis and requests additional telemetry.

### 3.2 Layer 2: Confidence Scoring and Completeness Assessment

The confidence scorer computes a scalar confidence score $s \in [0, 1]$ as a weighted sum of three sub-scores, each itself normalized to $[0, 1]$:

$$s \;=\; 0.4 \cdot \frac{\mathrm{completeness}}{100} \;+\; 0.3 \cdot p \;+\; 0.3 \cdot q$$

where $p$ is the pattern-match sub-score and $q$ is the signal-consistency sub-score. The completeness component (weight 0.4) rewards richer telemetry. The pattern-match sub-score takes $p = 1.0$ for an exact pattern match, $p = 0.5$ for a partial match, and $p = 0.0$ for no match. The signal-consistency sub-score takes $q = 1.0$ for no conflicts, $q = 0.5$ for minor conflicts (e.g., `power_state=Running` with `heartbeat_present=false`), and $q = 0.0$ for major conflicts (e.g., `power_state=Stopped` with `cpu_percent=95`). Under this formulation the score is bounded in $[0, 1]$ and attains its maximum $s = 1.0$ when telemetry is fully populated, the pattern is an exact match, and there are no signal conflicts.

The confidence score gates the decision path: $s \geq 0.70$ with completeness $\geq 90\%$ qualifies for a high-confidence `diagnose` decision; $0.40 \leq s < 0.70$ with completeness in $[60\%, 90\%)$ qualifies for `diagnose_low_confidence`; $s < 0.40$ or completeness $< 60\%$ results in `abstain_request_next_check`. For safety rules SR-3 and SR-5 we additionally require $s \geq 0.9$ before allowing destructive actions, a threshold reachable only when $C \geq 75\%$ with an exact pattern match and no conflicts.

The threshold $s \geq 0.70$ alone is intentionally permissive: with exact pattern match ($p=1$) and no conflicts ($q=1$), $s = 0.4(C/100) + 0.6$, so the score reaches 0.70 at $C = 25\%$. However, the additional $C \geq 90\%$ gate prevents high-confidence diagnosis under sparse telemetry. Similarly, the destructive-action threshold $s \geq 0.90$ is reached at $C \geq 75\%$ under exact match and no conflicts, but remains unreachable under partial matches or major conflicts. The $s < 0.40$ abstention threshold triggers when completeness is low and no pattern is matched. These thresholds are heuristic and require calibration against real incident data.

**Formal definition of novel incident.** We define a *novel incident* operationally as a telemetry case for which the rule engine's `_match_patterns()` method returns no match — i.e., the signal combination does not correspond to any of the 23 hand-coded known patterns. This is a system-relative definition: a case is novel with respect to the current rule set, not in any absolute sense. In the benchmark, 5 of 100 cases are labelled novel by this criterion. In practice, the `is_novel_incident` flag in the LLM output schema provides a second signal: the LLM may flag a case as novel even when the rule engine finds a partial match, if the LLM's reasoning identifies a combination of signals that doesn't fit the matched pattern cleanly. The two signals are complementary and both are stored in the incident memory for engineer review.

### 3.3 Layer 3: RAG Memory and SOP Knowledge Base

The RAG layer maintains two ChromaDB vector collections using `all-MiniLM-L6-v2` sentence-transformer embeddings (384-dimensional vectors, cosine similarity):

**Collection 1 — Incident Memory**: Stores past incident cases with their telemetry, decision, diagnosis, confidence score, and resolution outcome. Each entry includes a `verified` flag set by human engineers after review. Verified cases are prioritized in retrieval by boosting their similarity scores. The memory store grows continuously as new incidents are resolved.

**Collection 2 — SOP Knowledge Base**: Stores standard operating procedures for known incident patterns. SOPs are static, curated documents describing diagnosis steps, remediation procedures, and safety considerations for each known failure type. The SOP collection is pre-populated from Azure documentation and SRE runbooks.

At inference time, the system retrieves the top-k most similar incidents (default k=5) and top-k most relevant SOPs (default k=3) using cosine similarity with a threshold of 0.75. Retrieved context is injected into the LLM prompt as structured blocks, providing the model with grounded examples and procedural guidance. When the incident memory is empty (Cycle 0), only SOP context is available; as memory grows, past cases provide increasingly specific guidance.

### 3.4 Layer 4: LLM Decision Engine with Provider Fallback

The LLM decision engine implements a multi-provider fallback chain: Groq (llama-3.3-70b-versatile, ~2s latency) → Gemini (gemini-1.5-flash) → Ollama (local, ~15s) → Rule Engine (deterministic fallback). This chain is designed so that if all LLM providers fail, the system falls back to the deterministic rule engine rather than returning an error.

#### 3.4.1 Structured Output Schema

The system prompt instructs the LLM to act as an Azure VM incident triage specialist, to reason step-by-step over the provided telemetry, to consult the retrieved SOP and incident context, and to return a structured JSON response with seven required fields (`decision`, `diagnosis`, `confidence_score`, `evidence`, `evidence_gap`, `next_check`, `explanation`) together with two optional LLM-metadata fields used by the feedback-driven memory-update loop:

```json
{
  "decision": "diagnose | diagnose_low_confidence | abstain_request_next_check",
  "diagnosis": "string — one sentence root cause",
  "confidence_score": 0.0-1.0,
  "evidence": ["telemetry fields supporting the diagnosis"],
  "evidence_gap": ["missing signals that would increase confidence"],
  "next_check": "string — specific safe remediation step, or null",
  "explanation": "string — multi-sentence reasoning describing why this decision was made",
  "pattern_matched": "string — matched pattern name, 'unknown', or null",
  "is_novel_incident": true | false
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

### 3.6 Layer 6: Feedback-Driven Memory Update Loop

Every incident processed by the system is stored to the incident memory collection with `verified=False`. Human engineers review incidents within a defined SLA (24 hours for P1, 72 hours for P2) and set `verified=True` along with the `correct_action` field if the system's recommendation was accurate. Verified cases are prioritized in future retrievals so that confirmed resolutions rank above unverified LLM outputs.

We deliberately call this a *feedback-driven memory-update loop* rather than "online learning" or "self-learning." No model parameters are updated — neither the LLM nor the embedding model is retrained. What grows instead is the retrieval corpus: verified cases provide additional grounded context that later LLM calls can draw on. As demonstrated in Section 4.3, held-out novel-pattern accuracy improves from 20.0% at Cycle 0 (empty memory) to 80.0% at Cycle 5 (80 verified cases in memory), and this improvement is attributable to retrieval quality rather than to any change in the underlying models.

## 4. Evaluation

### 4.1 Benchmark Dataset

The evaluation uses a synthetic benchmark of 100 cases constructed to cover the full range of Azure VM incident types encountered in production. The dataset is organized as follows: 23 cases covering all 23 known incident patterns (one per pattern), 5 clean/healthy VM cases with no issues, 5 missing telemetry cases with completeness below 60%, 5 conflicting signal cases with minor and major signal conflicts, 8 high CPU variations (cpu_percent 92-99%), 10 disk full variations (os_disk_percent_full 91-99%), 9 memory exhaustion variations (memory_percent 93-99%), 10 NSG block variations (5 RDP, 5 SSH), 5 SSL expiry variations (0-14 days remaining), 5 backup failure variations, 5 multi-signal cases combining two or more failure conditions, 5 platform event cases with maintenance annotations, and 5 novel pattern cases representing failure combinations not present in the known 23 patterns.

Synthetic benchmark cases were used because no publicly available labeled dataset of Azure VM incident telemetry exists. Real incident data is proprietary, contains PII, and is subject to data residency constraints. The synthetic cases were constructed from Azure documentation [8], SRE runbooks, and the Azure VM health model, ensuring that the telemetry values and expected decisions reflect realistic production scenarios. The 5 novel pattern cases were designed to test the system's behavior on genuinely unseen failure combinations — specifically, multi-agent failures combined with application-layer degradation, which do not map cleanly to any single known pattern.

We acknowledge that synthetic benchmarks have limitations: they may not capture the full distribution of real-world incidents, and the expected decisions were assigned by the authors rather than validated by production on-call engineers. The benchmark cases were reviewed for consistency against Azure documentation and SRE runbooks, but independent expert validation has not been performed. Section 5.2 discusses this limitation and outlines the path to real-world validation.

### 4.2 Experiment 1: Accuracy Comparison and Safety-Guard Ablation

Table 1 presents the accuracy comparison across configurations on all 100 benchmark cases (95 known-pattern + 5 novel-pattern). Per-case detail records with case IDs, expected/actual decisions, confidence scores, and provider labels are in `experiments/results/`.

**Config A — Rule Engine with Safety Guard (baseline).** The rule engine with the deterministic safety guard achieves 88.0% overall accuracy (88/100), with 91.6% on known patterns (87/95) and 20.0% on novel patterns (1/5). The safety guard contributes 6 of those 88 correct decisions: platform-event cases where the guard correctly forces abstention. Without the safety guard (Config A-noSafety), accuracy drops to 82.0% (82/100). This 6-percentage-point difference is the clearest ablation result in the study and demonstrates that the deterministic safety guard is not merely a safety mechanism but also an accuracy-improving component.

**Config B — LLM Only (no RAG, no SOP).** Evaluated on all 100 cases (51 Groq + 48 Ollama + 1 rule-engine fallback). Overall accuracy is 73.0% (73/100), with 73.7% on known patterns (70/95) and 60.0% on novel patterns (3/5). The LLM without RAG context scores lower than the rule engine on known patterns but substantially better on novel patterns (60% vs 20%). A McNemar test on all 100 paired cases (b=4, c=19, exact p=0.0026) confirms Config A is significantly better than Config B on known patterns (p<0.01). This is consistent with the expectation that the LLM without domain-specific RAG context lacks the pattern-matching precision of the rule engine, but its pre-trained knowledge enables it to reason about novel failure combinations.

**Config C — LLM + SOP RAG (100/100 cases complete).** Evaluated on all 100 cases (60 Groq + 40 Ollama). Overall accuracy is 86.0% (86/100), with 89.5% on known patterns (85/95) and 20.0% on novel patterns (1/5). A McNemar test on all 100 paired cases (b=6, c=8, exact p=0.79) shows no significant difference between Config C and Config A. SOP RAG context brings the LLM to near-parity with the rule engine on known patterns, with a 2.1-percentage-point gap (89.5% vs 91.6%) that is not statistically significant.

**Config D — Full System (LLM + SOP RAG + Incident Memory + Safety Guard, 100/100 cases complete).** Evaluated on all 100 cases (62 Groq + 34 Ollama + 4 rule-engine fallback). Overall accuracy is 86.0% (86/100), with 89.5% on known patterns (85/95) and 20.0% on novel patterns (1/5). A McNemar test on all 100 paired cases (b=3, c=1, exact p=0.625) shows no significant difference from Config A. Config D achieves the same accuracy as Config C (86.0%), suggesting that incident memory does not provide additional benefit in a single-cycle static evaluation — its value is longitudinal, as demonstrated in Experiment 2.

| Configuration | Overall | Known (n=95) | Novel (n=5) | FP (n=5 healthy) | Abstain | Status |
|---|---|---|---|---|---|---|
| Rule Engine + Safety (A) | 88/100 (88.0%) | 87/95 (91.6%) | 1/5 (20.0%) | 0/5 (0.0%) | 0 | ✅ Complete |
| Rule Engine, no Safety (A-noSafety) | 82/100 (82.0%) | 81/95 (85.3%) | 1/5 (20.0%) | 0/5 (0.0%) | 0 | ✅ Complete |
| LLM Only (B) | 73/100 (73.0%) | 70/95 (73.7%) | 3/5 (60.0%) | 0/5 (0.0%) | 0 | ✅ Complete |
| LLM + SOP RAG (C) | 86/100 (86.0%) | 85/95 (89.5%) | 1/5 (20.0%) | 0/5 (0.0%) | 0 | ✅ Complete |
| Full System (D) | 86/100 (86.0%) | 85/95 (89.5%) | 1/5 (20.0%) | 0/5 (0.0%) | 0 | ✅ Complete |

**McNemar significance tests (paired comparisons vs Config A, all on n=100):**

| Comparison | n | b | c | Exact p | Interpretation |
|---|---|---|---|---|---|
| B vs A | 100 | 4 | 19 | **0.0026** | A significantly better (p<0.01) |
| C vs A | 100 | 6 | 8 | 0.79 | No significant difference |
| D vs A | 100 | 3 | 1 | 0.625 | No significant difference |

*Note: McNemar tests are computed on all 100 paired cases.*

The safety-guard ablation (A vs A-noSafety) is the most interpretable result because both configurations run deterministically on all 100 cases with no API dependencies. The 6 cases where the safety guard changes the outcome are all platform-event cases where the guard correctly forces `abstain_request_next_check`.

**McNemar analysis.** Config B is significantly worse than Config A overall (b=4, c=19, exact p=0.0026, n=100), confirming that the LLM without RAG context underperforms the rule engine. Config C is statistically indistinguishable from Config A (b=6, c=8, exact p=0.79, n=100), suggesting RAG context compensates for the LLM's lack of domain-specific rules. Config D is also statistically indistinguishable from Config A (b=3, c=1, exact p=0.625, n=100), matching Config C's accuracy exactly.

**Table 1b: Latency and Cost Profile**

| Configuration | Avg Latency | Notes |
|---|---|---|
| Rule Engine (baseline) | ~50 ms | No LLM cost; deterministic |
| LLM Only | ~2.1 s | Groq API; ~$0.0001/call |
| LLM + SOP RAG | ~2.4 s | + ChromaDB retrieval (~300 ms) |
| Full System (ours) | ~2.5 s | + safety guard (~1 ms overhead) |

*Latency figures are approximate means from pilot runs and are not accompanied by standard deviations.*

**Comparison to Related Systems.** Direct comparison against prior systems is constrained by dataset differences: RCACopilot [2] reports 0.77 F1 on Microsoft's internal cloud incident dataset (software services, not VM infrastructure), while Ahmed et al. [4] report 68% accuracy on cloud incident root cause recommendation. Our 88.0% rule-engine accuracy on VM triage is not directly comparable due to different task definitions and datasets.

### 4.3 Experiment 2: Feedback-Driven Memory Improvement

Table 2 shows accuracy on the fixed 20-case held-out test set (15 known + 5 novel cases) across six feedback-driven memory-update cycles as verified cases accumulate in memory. The test set is identical across all cycles — only the memory store grows. This design isolates the effect of memory accumulation from any confounding changes in the test distribution. This experiment uses the rule engine with memory-boosted confidence scores (no LLM API calls), so it is fully deterministic and reproducible.

| Feedback Cycle | Cases in Memory | Test Cases | Accuracy | Known Acc | Novel Acc |
|---|---|---|---|---|---|
| Cycle 0 | 0 | 20 | 80.0% | 100.0% | 20.0% |
| Cycle 1 | 10 | 20 | 80.0% | 100.0% | 20.0% |
| Cycle 2 | 25 | 20 | 85.0% | 100.0% | 40.0% |
| Cycle 3 | 50 | 20 | 90.0% | 100.0% | 60.0% |
| Cycle 4 | 75 | 20 | 95.0% | 100.0% | 80.0% |
| Cycle 5 | 80 | 20 | 95.0% | 100.0% | 80.0% |

![Fig 2](experiments/charts/fig2_learning_curve.png)

The lower Cycle 0 accuracy (80.0%) relative to Table 1's Rule Engine baseline (88.0%) reflects the fixed 20-case holdout composition, which includes a higher proportion of novel and ambiguous cases (5 novel + 5 platform event abstain cases = 50% of the holdout) than the full 100-case benchmark (5% novel). This is by design: the holdout was constructed to stress-test the feedback-driven memory mechanism on the cases where improvement is most meaningful.

Known-pattern accuracy stays at 100.0% across all cycles, as the rule engine already handles these patterns correctly and memory provides only marginal confirmation. The most significant improvement is in novel-pattern accuracy, which rises from 20.0% at Cycle 0 to 80.0% at Cycles 4 and 5 as verified resolutions for novel cases accumulate in memory. The improvement is non-linear: no gain at Cycle 1 (10 cases, no novel resolutions yet), then steady gains at Cycles 2–4 as novel resolutions are verified. The plateau at 80.0% from Cycle 4 onward reflects the remaining 20% of novel cases (1 of 5) where telemetry signals are genuinely ambiguous even with memory context. We emphasize that each 20-percentage-point step corresponds to a single novel case changing from incorrect to correct; with n=5 novel cases, confidence intervals on these estimates are wide and the trend should be interpreted as indicative rather than definitive.

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

**Safety guard precision and recall.** We report safety performance using two complementary metrics:

| Metric | Value | Denominator |
|---|---|---|
| Unsafe-suggestion recall | 30/30 (100%) | 30 hand-crafted adversarial cases |
| False-block rate on benchmark | 0/100 (0.0%) | 100 benchmark cases (all configs) |
| False-block rate on healthy VMs | 0/5 (0.0%) | 5 clean/healthy benchmark cases |
| Accuracy contribution (ablation) | +6 pp (82→88%) | 100 benchmark cases, Config A |

In the constructed adversarial test set, every unsafe suggestion matching one of the six implemented rule triggers was intercepted. The 0% false-block rate on the benchmark reflects that the 100 benchmark cases were constructed to avoid triggering safety rules on non-adversarial inputs. We acknowledge that real production traffic may contain edge cases where the safety rules are overly conservative — for example, a legitimate disk-resize operation on a VM with confidence just below 0.9. Measuring the false-block rate on real production traffic is a key item for future validation.

### 4.5 Qualitative Case Analysis

To illustrate system behavior concretely, we present three representative cases: one correct diagnosis, one correct abstention, and one incorrect diagnosis.

**Case 1 — Correct diagnosis (case 004, High CPU Saturation).** Telemetry: `power_state=Running`, `cpu_percent=98.5`, `memory_percent=42.0`, `resource_health_status=Degraded`, all other signals normal, completeness=96.7%. The rule engine matches the `high_cpu` pattern (exact match, $s=1.0$), returns `diagnose` with diagnosis "High CPU saturation" and next_check "Identify and terminate high-CPU processes; consider VM resize if sustained." The safety guard finds no violations. Expected: `diagnose`. Result: correct.

**Case 2 — Correct abstention (case 085, Platform Maintenance).** Telemetry: `power_state=Running`, `resource_health_status=Degraded`, `resource_health_annotation="Planned maintenance: memory-preserving update"`, all metrics normal. The rule engine matches the `platform_event` pattern and returns `diagnose`. The safety guard (SR-1) detects the maintenance annotation and overrides to `abstain_request_next_check` with next_check "Wait for platform maintenance to complete, then re-assess VM state." Expected: `abstain_request_next_check`. Result: correct. This case illustrates the safety guard's accuracy contribution — without it, the system would incorrectly diagnose a platform-managed event as a VM fault.

**Case 3 — Incorrect diagnosis (case 009, VM Running No Heartbeat).** Telemetry: `power_state=Running`, `heartbeat_present=False`, `azure_vm_agent_status=Healthy`, `resource_health_status=Available`, completeness=96.7%. The rule engine detects a minor conflict (running VM with no heartbeat) and returns `diagnose` with $s=0.85$. Expected: `diagnose_low_confidence` (the conflicting signals warrant lower confidence). The system over-diagnoses — it produces `diagnose` instead of `diagnose_low_confidence`. This is a threshold calibration issue: the minor-conflict penalty ($q=0.5$) is not sufficient to push $s$ below 0.70 when completeness is high. Fixing this would require either a lower `diagnose` threshold or a stronger conflict penalty, both of which require calibration against real incident data.

## 5. Discussion

### 5.1 Key Findings

- The rule engine with the deterministic safety guard reaches 88.0% overall accuracy on the synthetic benchmark. The safety-guard ablation shows a 6-percentage-point improvement (82.0% → 88.0%) attributable to the guard correctly forcing abstention on platform-event cases. This is the most interpretable result in the study because both configurations are fully deterministic with no API dependencies.
- The LLM-only configuration (Config B, 100 cases complete) achieves 73.0% overall — lower than the rule engine on known patterns (73.7% vs 91.6%), but substantially better on novel patterns (60.0% vs 20.0%). A McNemar test (b=4, c=19, exact p=0.0026) confirms Config A is significantly better than Config B on known patterns (p<0.01). This confirms the expected pattern: the LLM without RAG context lacks domain-specific precision but adds value for novel incidents.
- The LLM+SOP RAG configuration (Config C, 100/100 cases complete) achieves 86.0% overall and 89.5% on known patterns — statistically equivalent to Config A (McNemar p=0.79 on n=100). SOP RAG context compensates for the LLM's lack of domain-specific rules, bringing it to near-parity with the rule engine.
- The full system (Config D, 100/100 cases complete) achieves 86.0% overall — identical to Config C. This indicates that incident memory does not improve single-cycle static evaluation; its value is longitudinal, as shown in Experiment 2's feedback-driven improvement from 20% to 80% novel accuracy over five cycles.
- Held-out novel-pattern accuracy improves from 20.0% to 80.0% over five feedback-driven memory-update cycles — a 60.0 percentage-point gain driven by RAG retrieval of verified resolutions. No model weights are updated. We caution that each 20-percentage-point step corresponds to a single novel case (n=5), so confidence intervals are wide.
- The deterministic safety guard intercepts all 30 hand-crafted adversarial suggestions covering all six safety rules. On the 100-case benchmark it triggers zero false blocks on healthy VMs.
- The provider fallback chain returns an answer on every evaluation case, including when upstream LLM APIs are unavailable. We report this as an operational property of the fallback design rather than as a formal availability guarantee.

### 5.2 Limitations and Threats to Validity

| Threat | Description | Mitigation / Status |
|---|---|---|
| Synthetic benchmark | All 100 cases constructed from Azure docs/runbooks, not real incidents | Acknowledged; real-world validation is the primary next step |
| Knowledge leakage | Benchmark and SOP corpus share the same source documents | Acknowledged; future work should enforce strict corpus separation |
| Author-assigned labels | Expected decisions assigned by authors, not independent SREs | Acknowledged; independent expert labeling needed |
| Small novel subset | n=5 novel cases; each 20pp step = 1 case | Acknowledged; confidence intervals are wide; results are indicative |
| Single-run LLM evaluation | Limited repeated trials | Acknowledged; results are indicative single-run values |
| Safety guard not compared | No head-to-head vs prompt-only, constrained decoding, or classifier | Acknowledged; necessity claim softened to "important under conditions" |
| No human-expert evaluation | No blinded SRE review of diagnosis usefulness or abstention quality | Acknowledged; human-factor study is future work |
| Single-VM scope | Fleet-level correlation not addressed | Acknowledged; multi-VM analysis is future work |
| Threshold heuristics | Confidence thresholds (0.40, 0.70, 0.90) not calibrated on real data | Acknowledged; calibration requires real incident dataset |

The primary threat to validity is the synthetic nature of the benchmark. All 100 cases were constructed from Azure documentation and SRE runbooks rather than real production incident logs. Real incidents may exhibit signal combinations, noise patterns, and failure modes not represented in our benchmark. Expected decisions were assigned by the authors rather than validated by production on-call engineers, introducing potential labeling bias. This is the single largest weakness of the current study.

A related concern is potential knowledge leakage. The benchmark cases were constructed from Azure documentation and SRE runbooks, while the SOP collection is also pre-populated from Azure documentation and runbooks. This overlap means the evaluation may overstate the system's ability to generalize to genuinely unseen incidents. Future work should enforce strict separation between the corpus used for benchmark construction and the corpus available to the system at inference time.

The novel-pattern evaluation is too small to support strong claims. With only 5 novel cases, each 20-percentage-point step in Table 2 corresponds to a single case changing from incorrect to correct. Confidence intervals on these estimates are wide.

Additional limitations:
- LLM latency (Groq ~2s vs rule engine ~50ms) makes the full system unsuitable for sub-second SLA requirements without further optimization such as caching or a fine-tuned smaller model.
- Memory store grows without automatic pruning; long-running deployments may require eviction policies to maintain retrieval quality.
- Single-VM analysis; fleet-level correlation across multiple VMs is not addressed and may reveal additional failure patterns.
- Safety rules are manually defined; automated rule discovery from incident post-mortems is future work.
- The safety guard has not been compared against alternative safety mechanisms (prompt-only constraints, constrained decoding, classifier-based validators). We therefore position it as an *important* component under the evaluated conditions rather than a *necessary* one in the absolute sense.
- No human-expert evaluation has been performed. There is no blinded review by actual SREs or on-call engineers judging diagnosis usefulness, action safety, or abstention quality.

### 5.3 Future Work

- Multi-VM fleet analysis with cross-VM correlation
- Automatic SOP generation from novel incidents
- Fine-tuned smaller LLM for lower latency
- Automated safety rule discovery from incident post-mortems
- Integration with Azure Monitor alerts for real-time triage

## 6. Conclusion

Cloud VM incident triage at scale requires systems that handle both known and novel failure patterns while enforcing hard safety constraints on remediation suggestions. This paper presented a 6-layer architecture combining a deterministic rule engine, dual-collection RAG memory with sentence-transformer embeddings, structured LLM reasoning with multi-provider fallback, and a deterministic post-LLM safety guard enforcing six hard safety rules. On a 100-case synthetic benchmark the rule engine with safety guard reaches 88.0% overall accuracy; a safety-guard ablation shows a 6-percentage-point improvement attributable to the guard. In a longitudinal experiment on a 20-case held-out set, novel-pattern accuracy rises from 20.0% to 80.0% over five feedback-driven memory-update cycles. The safety guard intercepts all 30 hand-crafted adversarial suggestions while producing no false blocks on the benchmark's healthy-VM cases.

These results are promising but preliminary. The evaluation is entirely synthetic, the novel-pattern subset contains only five cases, and the benchmark was constructed from the same documentation sources that populate the SOP knowledge base — creating a leakage risk that limits generalizability claims. We have not yet validated the system against real production incidents, obtained independent expert labeling, or compared the deterministic safety guard against alternative safety mechanisms such as prompt-only constraints, constrained decoding, or classifier-based validators.

The primary contribution is therefore architectural rather than empirical: we show that combining deterministic post-LLM safety enforcement with feedback-driven retrieval memory is a feasible design pattern for safe LLM-assisted cloud incident triage. Beyond the Azure-specific implementation, three system-design lessons generalize to any LLM-assisted operations system: (1) *deterministic post-generation guards provide an auditable safety boundary that does not depend on LLM compliance with prompt instructions*; (2) *separating static knowledge (SOPs) from dynamic memory (verified cases)* allows the retrieval corpus to grow without contaminating curated knowledge; and (3) *honest confidence scoring with explicit abstention* is preferable to overconfident diagnosis — the system's 0% false-positive rate on healthy VMs comes from its willingness to abstain rather than from perfect accuracy. The concrete next steps are (1) shadow-mode validation against real Azure incident logs with ground-truth resolutions from production SRE teams, (2) a larger and independently constructed benchmark with strict leakage controls, (3) ablation isolating the safety guard against alternative safety mechanisms, (4) independent expert labeling of benchmark cases, and (5) fleet-level multi-VM correlation analysis. The telemetry schema and decision policy are not inherently Azure-specific; adapting the system to AWS CloudWatch or GCP Cloud Monitoring would require replacing the Azure-specific field definitions while retaining the pipeline structure, though we have not yet demonstrated this.

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

[10] Uptime Institute, "Annual Outage Analysis 2023," Uptime Institute Intelligence Report, 2023. [Online]. Available: https://uptimeinstitute.com/resources/research-and-reports (Reports that over 60% of high-impact outages cost at least $100,000 and roughly 15% exceed $1,000,000.)

[11] P. Notaro, J. Cardoso, and M. Gerndt, "A Survey of AIOps Methods for Failure Management," *ACM Transactions on Intelligent Systems and Technology*, vol. 12, no. 6, pp. 1–45, 2021.

[12] M. Ma, S. Zhang, J. Chen, J. Xu, H. Li, Y. Lin, X. Nie, B. Zhou, Y. Wang, and D. Pei, "Jump-Starting Multivariate Time Series Anomaly Detection for Online Service Systems," in *Proc. USENIX Annual Technical Conference (ATC)*, pp. 413–426, 2021.

[13] OpenAI, "GPT-4 Technical Report," arXiv:2303.08774, 2023. [Online]. Available: https://arxiv.org/abs/2303.08774

[14] X. Amatriain, A. Sankar, J. Bing, P. K. Bodigutla, T. J. Hazen, and M. Kazi, "Transformer Models: An Introduction and Catalog," arXiv:2302.07730, 2023. [Online]. Available: https://arxiv.org/abs/2302.07730

[15] N. Reimers and I. Gurevych, "Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks," in *Proc. Conference on Empirical Methods in Natural Language Processing (EMNLP)*, pp. 3982–3992, 2019.

[16] A. Vaswani, N. Shazeer, N. Parmar, J. Uszkoreit, L. Jones, A. N. Gomez, Ł. Kaiser, and I. Polosukhin, "Attention Is All You Need," in *Advances in Neural Information Processing Systems (NeurIPS)*, vol. 30, pp. 5998–6008, 2017.

[17] J. Devlin, M.-W. Chang, K. Lee, and K. Toutanova, "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding," in *Proc. NAACL-HLT*, pp. 4171–4186, 2019.

[18] E. Perez, S. Huang, F. Song, T. Cai, R. Ring, J. Aslanides, A. Glaese, N. McAleese, and G. Irving, "Red Teaming Language Models with Language Models," in *Proc. EMNLP*, pp. 3419–3448, 2022. [Online]. Available: https://arxiv.org/abs/2202.03286

[19] A. Zou, Z. Wang, J. Z. Kolter, and M. Fredrikson, "Universal and Transferable Adversarial Attacks on Aligned Language Models," arXiv:2307.15043, 2023. [Online]. Available: https://arxiv.org/abs/2307.15043

---

## Reproducibility Details

All experiments were conducted on a Windows 11 workstation (Intel Core i7-12th Gen, 32 GB RAM, no GPU required). The deterministic experiments (Config A, safety ablation, Experiment 2, Experiment 3) are fully reproducible and complete in under 60 seconds total. The LLM-dependent configurations (B, C, D) require either a Groq API key with sufficient daily token quota (~100k tokens/day free tier, sufficient for ~25 cases per day at the prompt sizes used) or a GPU-accelerated Ollama instance. CPU-only inference with llama3.1:8b was found to be impractically slow (>10 minutes per call) on the evaluation hardware. Researchers with GPU hardware or paid API access can reproduce the full evaluation by running:

```bash
# Restore API keys in .env, then:
python experiments/run_llm_configs.py config_B  # ~8 min with Groq
python experiments/run_llm_configs.py config_C  # ~8 min with Groq
python experiments/run_llm_configs.py config_D  # ~8 min with Groq
python experiments/analyze_available_data.py    # compute Table 1
```

The runner supports resumption — it skips already-completed cases, so interrupted runs can be continued. ChromaDB version 1.5.6 was used with the `sentence-transformers/all-MiniLM-L6-v2` checkpoint. Groq API latency varied between 1.8s and 3.2s per call.

## Data and Code Availability

The 100-case synthetic benchmark dataset (`data/benchmark_cases_v2.csv`), all experiment scripts (`experiments/`), figure generation code (`experiments/generate_charts.py`), and the complete system source code are available at:

> **TODO before submission**: Replace with actual GitHub URL, e.g. `https://github.com/[username]/azure-vm-incident-copilot`

The benchmark dataset is fully synthetic and contains no proprietary or personally identifiable information. The SOP knowledge base documents (`data/sops/`) are derived from publicly available Azure documentation and are included in the repository. Researchers wishing to reproduce the LLM-based configurations (Configs B, C, D) require either a Groq API key (free tier sufficient for ~100 calls/day) or a locally running Ollama instance with `llama3.1:8b` installed (`ollama pull llama3.1:8b`). A `requirements.txt` and `setup/run_setup.py` are provided for environment setup.

## Acknowledgments

The authors used Kiro (Amazon Web Services, 2025), an AI-assisted development environment powered by Claude Sonnet (Anthropic), to assist with drafting and editing portions of this manuscript, including sections of the Related Work, System Architecture, and Evaluation discussions. All experimental results, system design decisions, and technical claims were verified and validated by the authors. The use of AI assistance is disclosed in accordance with IEEE Author Center guidelines on AI-generated content.

---

## Author Biographies

> **TODO before submission**: Replace all placeholder text below with actual author details. IEEE Access requires 3–5 sentences per author covering education, current affiliation, and research interests. Submissions with placeholder biographies will be returned to draft.

**[Author 1 Name]** [TODO: degree, field, university, year]. Currently [TODO: role] at [TODO: institution]. Research interests include cloud infrastructure reliability, AIOps, and applied machine learning for systems operations.

**[Author 2 Name]** [TODO: degree, field, university, year]. Currently [TODO: role] at [TODO: institution]. Research interests include large language models, retrieval-augmented generation, and safety-critical AI systems.

**[Author 3 Name]** (Member, IEEE) [TODO: degree, field, university, year]. Currently [TODO: role] at [TODO: institution]. Research interests include distributed systems, cloud-native architectures, and AI-assisted operations.
