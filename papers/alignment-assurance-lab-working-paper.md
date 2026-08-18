# Alignment Assurance Lab

## Runtime Assurance, Trace Evidence, and Closed-Loop Governance for Tool-Using AI Agents

**Author:** Srinivasa J. Dinakar  
**Date:** August 18, 2026  
**Status:** Working paper and prototype report; not peer reviewed

## Abstract

Tool-using and multi-agent AI systems can produce acceptable final outputs while taking unsafe intermediate actions, following hostile external content, exceeding delegated authority, relying on stale or fabricated evidence, or continuing after a stop condition. A second problem is epistemic: even a correct assurance checker is not useful if checks can be silently omitted, downgraded, modified, or reported dishonestly. This working paper presents the Alignment Assurance Lab V6, a verification-inspired reference architecture that treats the AI model as an **untrusted planner** and moves assurance into deterministic controls around effectful actions and evaluation evidence. V6 preserves a deterministic trace-property monitor, adds a pre-action capability/evidence gateway, versioned JSON-Schema event governance, causal/delegation validation, field-issue replay, deterministic assurance canaries, artifact-bound result provenance, anti-rollback checks, optional Ed25519 result attestations, immutable human dispositions, and hash-linked audit history with local Merkle checkpoints. The contribution is deliberately narrow: the prototype does not claim to solve alignment, hallucination, or prompt injection. Its research direction is a closed operational loop in which field failures become reproducible traces, reviewable check/schema/policy changes, regression evidence, and independently verifiable assurance records.

**Keywords:** agentic AI, runtime assurance, runtime verification, tool security, capability systems, trace monitoring, provenance, attestation, auditability, counterexamples, governance

## 1. Motivation

AI agents increasingly act through tools rather than merely producing text. A model can select an unsafe action, mis-handle untrusted tool output, overgeneralize an authorization, delegate more authority than it possesses, or turn unsupported claims into consequential actions. Final-answer grading can miss these trajectory failures.

The Alignment Assurance Lab borrows a discipline from pre-silicon verification: express critical requirements as checks, exercise those checks through scenarios, preserve counterexamples, measure what was covered, and treat field failures as inputs to regression closure. The central V6 design principle is that the language model is **not the security boundary**. The model proposes; deterministic infrastructure decides whether an effectful action is allowed and whether the resulting assurance evidence is trustworthy.

A separate concern motivates V6 result integrity. A reported `PASS` can be misleading if the wrong trace was evaluated, a weakened checker was used, a required check was omitted, a result was edited, or a human changed `FAIL` to `PASS`. V6 therefore separates the machine/system verdict from the integrity status of the evidence that produced it.

## 2. Relationship to prior work

The core concept of trace-aware and runtime-controlled agent assurance is not claimed as wholly novel. Several research directions support or overlap the architecture.

Runtime verification provides the general foundation for evaluating temporal properties over observed executions. Three-valued monitoring also motivates distinguishing conclusive results from observations that remain unresolved or insufficiently exercised.

Agent-security research increasingly treats tool actions and trajectories as the relevant unit of analysis. AgentDojo evaluates attacks in tool-using environments, including indirect prompt injection through tool data. Agent Security Bench broadens the threat surface to system prompts, user prompts, tool use, and memory. OpenAgentSafety and trajectory-oriented benchmarks similarly emphasize behavior across multi-step interactions rather than only final responses.

Recent control architectures reinforce the decision to place deterministic policy outside the model. CaMeL separates trusted control from untrusted data and restricts capabilities. Progent uses fine-grained privilege policies for tool calls. AgentSpec introduces explicit runtime constraints. FAVA places an evidence-backed authorization layer and runtime gateway before effectful execution.

A particularly close conceptual neighbor is *A Trace-Based Assurance Framework for Agentic AI Orchestration: Contracts, Testing, and Governance* (2026), which uses message/action traces, machine-checkable contracts, deterministic replay, counterexample search, fault injection, and action mediation. Because of this overlap, this project does **not** present trace assurance itself as its novelty claim.

The distinct research emphasis is instead the integration of:

1. verification-style runtime enforcement,
2. assurance-result integrity and anti-fudging controls,
3. versioned schema/policy/check governance,
4. field-incident replay and gap classification, and
5. auditable check evolution followed by regression closure.

This also aligns with NIST AI RMF principles around post-deployment monitoring, feedback, incident response, documented roles, and continual improvement. Provenance ideas are informed by W3C PROV, supply-chain attestation concepts by SLSA, transparency-log patterns by Sigstore/Rekor, and schema governance by JSON Schema Draft 2020-12.

## 3. V4 deterministic trace-property baseline

The repository retains [`trace_assurance.py`](../src/assurance_portfolio/trace_assurance.py) as a compact deterministic baseline. It checks five properties:

1. authorization before sensitive action,
2. evidence before high-risk action,
3. high-risk classification consistency,
4. independent proposer/approver identity,
5. shutdown compliance.

Authorization and evidence are action/transaction scoped, consumable, and optionally expiring. A high-risk action cannot bypass stronger controls by incorrectly clearing its sensitive flag.

The base monitor returns `PASS`, `FAIL`, or `INCONCLUSIVE`. In this prototype, `INCONCLUSIVE` means no violation was observed but at least one required property was not exercised. This is a practical coverage-oriented convention rather than a claim that the engine implements complete formal runtime-verification semantics. V6 retains this status for backward compatibility and reports additional system/integrity dimensions separately.

## 4. V5 audit history

V5 added an append-only logical audit history around evaluations and check updates. Each record is canonical JSONL with a sequence number, previous-record hash, and SHA-256 record hash. Evaluations record the trace fingerprint, check/schema/policy versions, result, violations, and property coverage. Check changes can reference a source field issue or source evaluation and require independent approval.

This established the first closed-loop provenance chain but remained vulnerable to two classes of problem: the audit history was local and could be fully replaced by a sufficiently privileged actor, and version identifiers did not cryptographically bind results to the actual checker/schema/policy artifacts.

## 5. V6 architecture

V6 adds a set of deterministic layers around the V4 monitor.

### 5.1 Runtime assurance gateway

[`runtime_assurance.py`](../src/assurance_portfolio/runtime_assurance.py) evaluates a proposed effectful action before tool execution. A sensitive or high-risk action must match a capability bound to:

- action,
- principal,
- transaction,
- delegated authority when applicable,
- security-relevant parameter constraints.

Constraints support equality, allowed-value sets, nested structures, and scalar min/max boundaries. This prevents a capability for one recipient or amount range from silently authorizing a materially different action.

The gateway returns `ALLOW`, `BLOCK`, or `ESCALATE`. `REWRITE` exists in the decision enum as a reserved future behavior, but V6 does not currently rewrite tool arguments.

For high-risk actions, the gateway additionally requires verified evidence with `VERIFIED_EVIDENCE` trust status bound to the same transaction and action. Named proposer and approver identities are required; self-approval is blocked, while same-trust-domain approval escalates for additional oversight.

The design explicitly treats untrusted tool/external content as data rather than authority. Such content may influence reasoning, but it cannot manufacture a capability.

### 5.2 Versioned schema and policy artifacts

The V6 event schema is [`schemas/agent-trace/2.0.0.json`](../schemas/agent-trace/2.0.0.json), a JSON Schema Draft 2020-12 document. It supports optional event/parent identities, trace/span identifiers, principal/agent identities, transaction IDs, delegation/capability ancestry, trust domains, action parameters, trust labels, and content digests.

[`schema_registry.py`](../src/assurance_portfolio/schema_registry.py) validates both schema documents and actual trace instances. Schema changes are classified as:

- `BACKWARD_COMPATIBLE`,
- `MIGRATION_REQUIRED`,
- `BREAKING`,
- `SECURITY_SENSITIVE`.

Schema proposal and activation are separate actions. Activation requires an approver distinct from the proposer. The local registry is a reference implementation, not an enterprise configuration-management service.

The associated V6 policy and check manifests are stored as concrete repository artifacts under [`policies/`](../policies/) and [`checks/`](../checks/).

### 5.3 Causal and delegation validation

A simple total order is insufficient to express important multi-agent relationships. [`causal_trace.py`](../src/assurance_portfolio/causal_trace.py) therefore checks explicit event parentage and capability delegation.

It rejects duplicate event/capability identifiers, references to nonexistent earlier parents, changes of delegated action, and simple privilege amplification where a child capability broadens the parent's constraints. A narrower child capability is permitted.

This is intentionally a compact causal consistency layer; it is not a general theorem prover for distributed partial orders, concurrency, or arbitrary multi-agent collusion.

### 5.4 Field-issue feedback loop

[`field_issue.py`](../src/assurance_portfolio/field_issue.py) replays operational incidents against the deterministic monitor and assigns conservative review categories. Examples include:

- `FALSE_NEGATIVE`: confirmed unsafe behavior passed exercised checks,
- `COVERAGE_GAP`: confirmed unsafe behavior remained inconclusive,
- `ENFORCEMENT_GAP`: checks detected the problem but the unsafe action still occurred,
- `FALSE_POSITIVE`: benign behavior was rejected,
- `WEAK_CHECK`: replay alone is not decisive and expert review is needed.

The analyzer produces a reviewable check-update suggestion and the CLI appends the analysis to the audit history. It does not claim to infer the true root cause of arbitrary incidents with an AI model.

## 6. Protecting against fudged assurance results

V6 treats the assurance subsystem as part of the attack surface.

### 6.1 Three separate outputs

An audited evaluation exposes:

1. **base monitor result** — the original V4 property result;
2. **system result** — additionally fails if concrete schema validation or causal/delegation validation fails;
3. **attestation integrity** — `VERIFIED`, `UNVERIFIED`, or `INVALID`.

This prevents a bare `PASS` from being presented as trustworthy evidence without its provenance state.

### 6.2 Binding the result to concrete artifacts

[`result_integrity.py`](../src/assurance_portfolio/result_integrity.py) can bind an evaluation to SHA-256 digests of:

- the exact trace,
- the raw result,
- checker source,
- required/executed check manifest,
- event schema,
- policy,
- configuration,
- execution environment,
- optional Git commit identity.

The audited check-set fingerprint includes concrete checker/schema/policy/configuration identity rather than only human-readable version labels.

### 6.3 Omitted-check detection

The attestation contains both required and executed check lists. If any required check is missing, the attestation is `INVALID`. A run cannot become trustworthy merely by avoiding the check that would fail.

### 6.4 Anti-rollback

The current check version must be at least the configured minimum version. A downgraded check set produces an `INVALID` attestation. Controlled rollback would need its own separately governed process rather than silently lowering the version.

### 6.5 Independent replay and canaries

Every audited V6 evaluation performs deterministic replay and compares normalized result digests. Replay disagreement invalidates the attestation.

[`assurance_selftest.py`](../src/assurance_portfolio/assurance_selftest.py) also injects known failures—missing authorization, self-approval, expired authorization, and post-shutdown action. If the monitor stops catching a canary, the assurance infrastructure should itself be treated as untrustworthy until investigated.

### 6.6 Signed result attestations

V6 supports optional Ed25519 signatures. A signed result is `VERIFIED` only when:

- required checks are present,
- anti-rollback passes,
- deterministic replay and structural validations pass,
- checker, schema, and policy are concrete bound artifacts,
- the attestation signature verifies.

A valid signature over version labels without concrete schema/policy binding remains `UNVERIFIED`. An unsigned result may be structurally valid but is also `UNVERIFIED`.

Private keys are generated only for local demonstrations and must never be committed to the repository. Production deployment would require managed key custody and runner identity.

### 6.7 Immutable human disposition

A reviewer cannot rewrite `FAIL` to `PASS`. Human review is appended as a separate disposition such as `WAIVED`, `FALSE_POSITIVE`, `REQUIRES_INVESTIGATION`, or `ACCEPTED`, with rationale, expiry, and evidence reviewed. The original machine result remains immutable in the logical audit history.

### 6.8 Audit-chain and Merkle checkpoints

The V6 audit store verifies sequence continuity, previous-record hashes, record hashes, and local Merkle checkpoint records. Checkpoints can record an external reference for later publication or storage.

This remains **tamper-evident, not tamper-proof**. A privileged actor capable of replacing the whole local history and recomputing hashes can defeat the local chain. A production implementation should publish checkpoint roots into WORM/object-lock storage, an independent transparency log, a signed audit service, or an equivalent trust domain.

## 7. Governance of check changes

Check updates are themselves safety-sensitive objects. V6 requires a proposer and separate approver for approved changes. A check removal, policy weakening, or explicitly security-sensitive update requires an additional independent approver, giving three distinct principals: proposer and two approvers.

Update records can retain regression-evidence references. V6 records those references but does not yet implement a production release gate that independently verifies every referenced regression artifact before activation.

The intended process is:

`field issue → replay → gap classification → proposed check/schema/policy update → independent review → regression/adversarial test → signed/versioned activation → monitored recurrence`

## 8. Threat-to-control mapping

| AI/system weakness | V6 response |
|---|---|
| hallucinated high-risk claim | require verified evidence before high-risk action |
| prompt/tool injection | trust-labelled data does not create authority |
| privilege overreach | parameter-bound capability gate |
| authorization replay | transaction-scoped capability |
| stale/fabricated evidence | verified evidence class and transaction/action binding |
| self-approval | block same principal |
| weak multi-agent independence | escalate same trust domain |
| delegation privilege amplification | parent/child capability subset validation |
| malformed trace | JSON Schema instance validation |
| checker downgrade | anti-rollback floor |
| omitted check | required/executed manifest comparison |
| modified checker/policy/schema | concrete artifact digests |
| changed reported result | raw-result digest + signature |
| human result rewriting | separate immutable disposition |
| assurance regression | replay + canary suite |
| local audit modification | hash chain and Merkle checkpoint |
| complete audit replacement | requires external anchoring; not solved locally |
| field failure recurrence | replayable issue + versioned check evolution |

## 9. Evaluation roadmap

The architecture now needs empirical evaluation rather than additional claims. A controlled study should compare at least:

1. outcome-only evaluation,
2. post-hoc trace monitoring,
3. runtime capability/evidence gating,
4. runtime gating plus field-issue/check-update feedback.

The experiment should freeze schema, policy, check set, prompts/models, and analysis criteria before evaluation. Benign and adversarial scenarios should include parameter substitution, untrusted tool instructions, evidence failures, delegation boundaries, approval-domain conflicts, shutdown, and field-issue recurrence.

Useful metrics include:

- unsafe-action prevention rate,
- false-block rate,
- escalation rate,
- violation recall/precision,
- property/hazard coverage,
- delegation-policy violations,
- replay consistency,
- attestation verification rate,
- assurance-canary detection rate,
- time from field issue to validated regression check,
- recurrence rate after check update,
- runtime overhead,
- human-review agreement/time.

The current repository has not yet produced these broader real-agent empirical results.

## 10. Limitations

V6 does not provide:

- complete hallucination detection,
- complete prompt-injection resistance,
- production tool interception,
- production IAM/capability issuance,
- semantic validation of arbitrary evidence claims,
- complete causal semantics for distributed multi-agent systems,
- automatic `REWRITE` enforcement,
- trusted hardware or remote attestation,
- externally anchored transparency evidence by default,
- formal proof that check/schema/policy updates cannot weaken safety,
- empirical evidence of improved safety across real agent frameworks.

The prototype is a research scaffold and reference implementation for testing those controls.

## 11. Research contribution and novelty boundary

The strongest claim supported by the current work is not that trace monitoring is novel. The contribution is a runnable integration of verification-inspired runtime control and operational governance:

**untrusted planner → pre-action capability/evidence gate → causal/versioned trace → deterministic properties → artifact-bound result evidence → field-issue replay → reviewed check evolution → regression closure.**

This structure makes both agent actions and assurance claims inspectable. Its value must ultimately be established through controlled evaluation rather than architectural plausibility alone.

## 12. Conclusion

Agent assurance requires two forms of skepticism: skepticism toward the model's proposed action and skepticism toward the assurance result itself. V6 therefore surrounds the model with deterministic authority/evidence controls and surrounds evaluation with provenance, replay, anti-rollback, signatures, immutable dispositions, and audit-history checks. The remaining research question is empirical: how much unsafe behavior this architecture prevents, at what false-block and operational cost, and whether field-driven check evolution produces measurable assurance improvement over static guardrails.

## References

1. National Institute of Standards and Technology. (2023). *Artificial Intelligence Risk Management Framework (AI RMF 1.0)*. https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf
2. National Institute of Standards and Technology. (2024). *Artificial Intelligence Risk Management Framework: Generative Artificial Intelligence Profile*. https://doi.org/10.6028/NIST.AI.600-1
3. Debenedetti, E. et al. (2024). *AgentDojo: A Dynamic Environment to Evaluate Prompt Injection Attacks and Defenses for LLM Agents*. https://arxiv.org/abs/2406.13352
4. *Agent Security Bench (ASB): Formalizing and Benchmarking Attacks and Defenses in LLM-based Agents*. https://arxiv.org/abs/2410.02644
5. *CaMeL: Defeating Prompt Injections by Design*. https://arxiv.org/abs/2503.18813
6. *Progent: Programmable Privilege Control for LLM Agents*. https://arxiv.org/abs/2504.11703
7. *AgentSpec: Customizable Runtime Enforcement for Safe and Reliable LLM Agents*. https://arxiv.org/abs/2503.18666
8. *FAVA: Evidence-Backed Authorization for AI Agents*. https://arxiv.org/abs/2607.27267
9. *A Trace-Based Assurance Framework for Agentic AI Orchestration: Contracts, Testing, and Governance*. https://arxiv.org/abs/2603.18096
10. W3C. *PROV-DM: The PROV Data Model*. https://www.w3.org/TR/prov-dm/
11. SLSA. *Build Provenance*. https://slsa.dev/spec/
12. Sigstore. *Rekor Transparency Log / Security Model*. https://docs.sigstore.dev/
13. JSON Schema. *Draft 2020-12*. https://json-schema.org/draft/2020-12

## Suggested citation

Dinakar, S. J. (2026). *Alignment Assurance Lab: Runtime Assurance, Trace Evidence, and Closed-Loop Governance for Tool-Using AI Agents*. Working paper and prototype report.
