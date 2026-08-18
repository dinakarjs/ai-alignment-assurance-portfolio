# Alignment Assurance Lab

**Status:** Runnable research prototype with deterministic trace monitoring, pre-action runtime gating, versioned governance artifacts, result attestation, and auditable field-feedback history  
**Theme:** Verification-driven runtime assurance and governance for agentic AI systems

## Motivation

Tool-using and multi-agent AI systems can fail even when their final answer looks acceptable. A model can hallucinate, follow malicious tool content, overreach its authority, reuse stale evidence, amplify privilege through delegation, drift over long horizons, or produce a superficially plausible result that should not be trusted. The design therefore treats the AI model as an **untrusted planner** and moves the security/assurance boundary into deterministic controls around effectful actions and evaluation evidence.

## Architecture

```text
User / environment
        |
        v
Trust-labelled inputs
        |
        v
AI planner / multi-agent system   [untrusted planner]
        |
        v
Proposed effectful action
        |
        v
Runtime Assurance Gateway
  | authority / capability
  | evidence provenance
  | trust-domain oversight
  | parameter constraints
        |
  +-----+---------+---------+
  |               |         |
ALLOW           BLOCK    ESCALATE
  |
  v
Tool broker / effect
  |
  v
Versioned causal trace
  |
  +--> schema + causal/delegation validation
  +--> deterministic trace properties
  +--> counterexample / coverage
  +--> result attestation
  +--> hash-linked audit history
                         |
                         v
                    Field issue
                         |
                         v
          replay / gap classification
                         |
                         v
           check/schema/policy proposal
                         |
                         v
        independent review + regression
```

`REWRITE` is reserved in the runtime decision enum, but V6 does not yet implement automatic argument rewriting.

## V4 deterministic monitor — retained baseline

[`trace_assurance.py`](../src/assurance_portfolio/trace_assurance.py) remains the small deterministic compatibility baseline. It checks:

- authorization before sensitive action,
- evidence before high-risk action,
- high-risk classification consistency,
- named and independent proposer/approver identities,
- shutdown compliance.

Authorization and evidence grants remain transaction-scoped, consumable, and optionally expiring. The V4 report returns `PASS`, `FAIL`, or `INCONCLUSIVE` and retains property-exercise coverage semantics.

## V5 auditable history

V5 introduced [`trace_audit.py`](../src/assurance_portfolio/trace_audit.py), which preserves evaluation results and check/schema/policy updates in a hash-linked JSONL history. This created the first closed-loop provenance path from a field issue or failing evaluation to a later check update.

## V6 runtime assurance and result integrity

V6 adds five layers around the V4 baseline.

### 1. Pre-action runtime gateway

[`runtime_assurance.py`](../src/assurance_portfolio/runtime_assurance.py) treats the model as an untrusted planner. Sensitive/high-risk actions require a parameter-bound capability. High-risk actions additionally require verified transaction-bound evidence and independent oversight. Same-principal approval is blocked; same trust-domain approval escalates.

Untrusted external/tool content may inform reasoning but does not create authority by itself.

### 2. Versioned event/schema/policy control

[`schemas/agent-trace/2.0.0.json`](../schemas/agent-trace/2.0.0.json) is a JSON Schema Draft 2020-12 event schema with optional causal, delegation, trust-domain, parameter, and provenance fields.

[`schema_registry.py`](../src/assurance_portfolio/schema_registry.py) validates schema documents and trace instances, classifies updates as `BACKWARD_COMPATIBLE`, `MIGRATION_REQUIRED`, `BREAKING`, or `SECURITY_SENSITIVE`, and requires a separate approver for activation.

The V6 policy and required-check manifests are versioned under [`policies/`](../policies/) and [`checks/`](../checks/).

### 3. Causal and delegation validation

[`causal_trace.py`](../src/assurance_portfolio/causal_trace.py) checks parent-event references and delegation ancestry and rejects simple privilege amplification where a child capability broadens its parent's action or constraints.

This is a compact reference validator, not a complete distributed partial-order model.

### 4. Result integrity

[`result_integrity.py`](../src/assurance_portfolio/result_integrity.py) separates the machine/system verdict from **attestation integrity**:

- `VERIFIED`
- `UNVERIFIED`
- `INVALID`

A result can only become `VERIFIED` when required checks are present, the check version meets the anti-rollback floor, replay is consistent, concrete checker/schema/policy artifacts are bound, and the supplied Ed25519 signature verifies. Unsigned or version-label-only provenance remains `UNVERIFIED`.

Audited results bind trace, raw result, checker, check manifest, schema, policy, configuration, environment, and optional Git-commit identity through SHA-256 digests.

### 5. Closed-loop operational feedback

[`field_issue.py`](../src/assurance_portfolio/field_issue.py) replays field incidents and conservatively classifies outcomes such as false negative, coverage gap, enforcement gap, false positive, or weak-check/review-needed. The resulting check-improvement proposal is reviewable and the CLI appends the analysis to the audit chain.

Check updates require independent approval. Security-sensitive weakening/removal requires an additional independent approver. Human waivers are separate records and cannot rewrite the original machine verdict.

## Protecting the assurance system itself

V6 assumes that assurance outputs can also be attacked or accidentally misreported. It therefore adds:

- exact checker source hashing,
- schema/policy/configuration/environment digests,
- required-versus-executed check manifests,
- check-version anti-rollback,
- deterministic independent replay,
- optional Ed25519 signatures,
- immutable human dispositions,
- seeded assurance canaries,
- hash-chain verification,
- local Merkle checkpoints for later external anchoring.

A local hash chain or Merkle checkpoint is not a substitute for external WORM/object-lock storage, remote attestation, or an independent transparency service.

## CLI examples

Runtime gate:

```bash
assurance-runtime examples/runtime_assurance_request.json
```

Fully artifact-bound audited evaluation:

```bash
assurance-trace-audit --audit-log artifacts/trace-audit/audit.jsonl \
  evaluate examples/agent_trace.json \
  --check-version agent-trace-checks/6.0.0 \
  --minimum-check-version agent-trace-checks/6.0.0 \
  --schema-version agent-trace/2.0.0 \
  --schema-file schemas/agent-trace/2.0.0.json \
  --policy-version agent-trace-policy/2.0.0 \
  --policy-file policies/agent-trace-policy/2.0.0.json
```

Field issue:

```bash
assurance-trace-audit --audit-log artifacts/trace-audit/audit.jsonl \
  field-issue examples/field_issue.json
```

Assurance canaries:

```bash
assurance-trace-audit self-test
```

See [`TRACE_ASSURANCE_V6.md`](../benchmarks/TRACE_ASSURANCE_V6.md) for the detailed protocol and trust boundaries.

## Research positioning

Trace monitoring and runtime guardrails for agentic systems are an active research area and are not claimed here as wholly novel. The stronger research direction for this project is the **verification-style closed loop**: operational issue → historical replay → observable assurance gap → versioned check/schema/policy update → independent approval → regression/adversarial closure → attested audit evidence.

This is intended to connect runtime safety engineering with continual governance and field-quality feedback rather than presenting a static guardrail as an alignment guarantee.

## Research questions

1. Which agent-safety/governance claims can be represented as deterministic observable properties and pre-action capabilities?
2. How much unsafe behavior can a deterministic runtime gateway prevent without causing unacceptable false blocks?
3. Do parameter-bound capabilities and evidence provenance improve robustness against tool/prompt injection compared with model-only guardrails?
4. How should delegation and trust-domain independence be represented for multi-agent systems?
5. Can field incidents be converted into validated check/schema/policy improvements without introducing new false positives?
6. Can result attestations and independent replay meaningfully reduce the risk of omitted, downgraded, or manipulated assurance results?
7. What additional protection is gained by external transparency/WORM anchoring versus a local hash chain?

## Next controlled evaluation

The next empirical step should compare outcome-only evaluation, post-hoc trace monitoring, and pre-action runtime gating across benign and adversarial tool-use scenarios. It should freeze the schema/policy/check versions, retain raw traces, measure unsafe-action prevention and false blocks, exercise field-issue feedback, and independently verify the result attestations.

Useful metrics include violation recall/precision, unsafe-action prevention, false-block rate, escalation rate, property/hazard coverage, delegation-policy violations, replay consistency, attestation-verification rate, field-issue recurrence after check updates, runtime overhead, and reviewer agreement.

## Trust boundary

V6 is a reference implementation. It does not provide complete hallucination detection, complete prompt-injection resistance, production identity/authorization infrastructure, trusted hardware execution, remote attestation, external transparency logging, universal multi-agent semantics, or empirical proof that the architecture improves safety across real-world agents. Those are integration and evaluation targets, not current claims.

## Working paper

[Alignment Assurance Lab: Runtime Assurance, Trace Evidence, and Closed-Loop Governance for Tool-Using AI Agents](../papers/alignment-assurance-lab-working-paper.md)
