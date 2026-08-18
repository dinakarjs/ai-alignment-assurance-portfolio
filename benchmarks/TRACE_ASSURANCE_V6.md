# Agent Trace Assurance V6 — Runtime Assurance and Result Integrity

V6 turns the earlier post-hoc trace monitor into a broader reference architecture for **pre-action control, trace validation, auditable evaluation, and closed-loop check improvement**. The AI agent is treated as an untrusted planner; deterministic controls around it decide whether an effectful action may proceed.

## Threat model

V6 is designed to make the following failure modes observable or harder to convert into effectful actions:

| Weakness / attack | V6 control |
|---|---|
| hallucinated or unsupported high-risk claim | verified, transaction-bound evidence requirement |
| prompt/tool injection creating authority | trust labels; untrusted content cannot create a capability |
| excessive privilege / parameter substitution | parameter-bound capabilities and min/max/list constraints |
| authorization replay | transaction-bound capability matching |
| self-approval / weak independence | identity separation; high-risk trust-domain independence |
| multi-agent privilege amplification | causal/delegation validator with child-scope subset rules |
| malformed or incompatible trace | Draft 2020-12 JSON Schema instance validation |
| stale/downgraded checker | minimum-version anti-rollback control |
| omitted checks | explicit required/executed check manifest |
| checker/result modification | checker/source, schema, policy, config, environment and result digests |
| result tampering | optional Ed25519 result attestation |
| machine FAIL rewritten as PASS | immutable machine result; human waiver/disposition is a separate record |
| audit-history editing | hash chain plus local Merkle checkpoints |
| full local-log replacement | not solved locally; external/WORM/transparency anchoring is recommended |
| assurance implementation regression | deterministic replay plus seeded canary self-tests |
| field issue escapes or is detected too late | field-issue replay, gap classification, and auditable check-update proposal |
| weakened check/policy update | independent approval; security-sensitive weakening/removal requires an additional independent approver |

## 1. Runtime gateway

`runtime_assurance.py` evaluates a proposed action before tool execution. It currently emits:

- `ALLOW`
- `BLOCK`
- `ESCALATE`

`REWRITE` is reserved in the decision enum for a future constrained-rewrite policy; V6 does **not** currently rewrite tool arguments.

A sensitive/high-risk action must match a parameter-bound capability. High-risk actions additionally require verified evidence bound to the same transaction/action and independent proposer/approver oversight. An action sourced from untrusted external/tool content does not gain authority merely because the model repeated that content.

Example:

```bash
assurance-runtime examples/runtime_assurance_request.json
```

This is a reference gateway. The repository does not yet intercept a production tool broker or OS/network capability system.

## 2. Event schema and causal/delegation model

The V6 event schema is `schemas/agent-trace/2.0.0.json`. It is a JSON Schema Draft 2020-12 document and includes optional causal/provenance fields such as event/parent IDs, trace/span IDs, agent/principal identities, delegation, trust domains, action parameters, capability ancestry, and trust labels.

`causal_trace.py` checks:

- duplicate event IDs,
- unknown parent-event references,
- duplicate/missing delegated capability IDs,
- unknown parent capabilities,
- delegated action changes, and
- child capability constraints broader than the parent capability.

The validator is intentionally conservative and is **not** a complete model of distributed partial-order semantics.

## 3. Schema lifecycle

`schema_registry.py` supports immutable local schema proposals and controlled activation. Compatibility is classified as:

- `BACKWARD_COMPATIBLE`
- `MIGRATION_REQUIRED`
- `BREAKING`
- `SECURITY_SENSITIVE`

Schema documents are themselves validated, and trace instances can be checked against an active schema. CLI operations:

```bash
assurance-trace-audit --schema-root /tmp/schemas \
  schema-propose candidate.json \
  --kind agent-trace --version 2.1.0 --proposer engineer-a \
  --previous-version 2.0.0

assurance-trace-audit --schema-root /tmp/schemas \
  schema-activate --kind agent-trace --version 2.1.0 --approver reviewer-b
```

The local registry is a reference implementation. Production activation should use an independently protected configuration/control plane.

## 4. Evaluation semantics

V6 preserves the V4 monitor for compatibility and reports three distinct concepts:

1. **base monitor result** — the original `PASS` / `FAIL` / `INCONCLUSIVE` property result;
2. **system result** — fails when schema or causal/delegation validation fails, otherwise retains the base result;
3. **attestation integrity** — `VERIFIED` / `UNVERIFIED` / `INVALID`.

A base `PASS` does not by itself imply trustworthy evidence.

`VERIFIED` requires, at minimum:

- all required checks represented in the manifest,
- the configured check version meeting the minimum version,
- deterministic replay consistency,
- valid schema/causal structure,
- concrete checker, schema, and policy artifact binding,
- a valid Ed25519 signature from the supplied runner identity/key.

Unsigned but structurally valid results are `UNVERIFIED`. Signed results that refer only to declared version strings rather than concrete schema/policy artifacts remain `UNVERIFIED`.

## 5. Result attestation

An attestation binds:

- trace digest,
- raw result digest,
- checker source digest,
- required/executed check manifest digest,
- schema digest,
- policy digest,
- configuration digest,
- execution-environment digest,
- Git commit SHA when supplied,
- check and minimum allowed versions,
- machine verdict,
- runner/signer identity.

Local key generation for demonstration:

```bash
assurance-trace-audit keygen \
  --private-key /tmp/ata-private.pem \
  --public-key /tmp/ata-public.pem
```

Private keys must not be committed to the repository.

## 6. Audit history and anchors

`TraceAuditStore` writes canonical JSONL records with sequence numbers, previous-record hashes, and record hashes. It can also append a Merkle checkpoint over all prior record hashes:

```bash
assurance-trace-audit --audit-log /tmp/audit.jsonl \
  anchor --external-reference ticket-or-transparency-reference
```

A local checkpoint does not by itself prevent a privileged actor from replacing the entire file and recomputing the chain. Production assurance should publish/checkpoint the root in independent WORM/object-lock storage, a transparency service, or an equivalent protected audit system.

## 7. Machine results and human dispositions

Human review cannot overwrite a machine verdict. A waiver/disposition is a separate audit record tied to the original run:

```bash
assurance-trace-audit --audit-log /tmp/audit.jsonl \
  waiver examples/waiver.json
```

Supported dispositions are `WAIVED`, `FALSE_POSITIVE`, `REQUIRES_INVESTIGATION`, and `ACCEPTED`. The original result remains unchanged.

## 8. Assurance self-tests

V6 continuously tests the assurance logic using known seeded violations:

- sensitive action without authorization,
- high-risk self-approval,
- expired authorization,
- action after shutdown.

```bash
assurance-trace-audit self-test
```

A failed canary means the assurance infrastructure itself should not be trusted until investigated.

## 9. Field-issue feedback loop

A confirmed field issue can be replayed against the deterministic monitor:

```bash
assurance-trace-audit --audit-log /tmp/audit.jsonl \
  field-issue examples/field_issue.json
```

The reference classifier distinguishes cases such as false negative, coverage gap, enforcement gap, false positive, and weak-check/review-required outcomes. It produces a reviewable check-update proposal and appends the analysis to the audit chain.

This is deliberately conservative: it does not claim to infer the true root cause of arbitrary incidents using AI.

## 10. Check-update governance

All approved updates require a distinct proposer and approver. A check removal, policy weakening, or explicitly security-sensitive change requires a second approver, yielding three distinct principals: proposer plus two approvers.

A production workflow should additionally require regression evidence before activation. V6 records `regression_evidence` in update records but does not yet implement an external release/approval service.

## 11. What V6 demonstrates

When its tests and CI pass, V6 demonstrates a runnable reference implementation of:

- pre-action capability/evidence gating,
- actual schema instance validation,
- causal/delegation privilege checks,
- field-issue replay and feedback records,
- source/artifact-bound evaluation metadata,
- omitted-check and rollback detection,
- deterministic replay,
- optional signed result attestations,
- immutable human dispositions,
- hash-linked audit history and local Merkle checkpoints,
- assurance canary tests.

It does **not** demonstrate production-grade prompt-injection resistance, complete hallucination detection, universal multi-agent correctness, trusted hardware execution, remote attestation, external transparency-log anchoring, or empirical safety improvement across real agent frameworks. Those require separate integration and controlled evaluation.
