# AI Assurance & Agentic Verification Portfolio — Runnable Prototypes

This repository applies semiconductor-verification discipline to AI assurance and applies AI/agent workflows back to pre-silicon verification engineering. It deliberately separates proposal, enforcement, deterministic checking, behavioral evidence, human oversight, and evidence integrity.

The two primary technical pillars are:

1. **Verification Copilot V9** — deterministic and model-backed requirement-to-verification workflows, tool validation, behavioral RTL mutation testing, controlled comparison, repeated trials, usage telemetry, and reproducible experiment bundles.
2. **Agent Trace Assurance V6** — deterministic trace properties, pre-action capability/evidence gating, versioned schemas and policies, causal/delegation validation, field-issue feedback, result attestations, anti-rollback, immutable waivers, assurance canaries, and auditable check evolution.

A smaller **CloudGuard AI V3** Responsible-AI demonstration remains in the repository as supporting coursework/research material.

These are research prototypes. They are not production EDA sign-off, production IAM/security enforcement, alignment guarantees, or regulatory compliance claims.

## Quick start

Python 3.10 or newer is required.

```bash
python -m pip install -e .
assurance-demo copilot examples/requirements.json
assurance-demo trace examples/agent_trace.json
assurance-runtime examples/runtime_assurance_request.json
assurance-demo cloudguard examples/cloudguard_incident.json
```

Run the full test suite:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

---

# Agent Trace Assurance V6

## Design principle: the model is not the security boundary

V6 treats an LLM/agent as an **untrusted planner**. Model-generated reasoning may propose a tool action, but deterministic infrastructure decides whether an effectful operation may proceed and whether the later assurance result is trustworthy.

```text
Trust-labelled inputs
        |
        v
AI planner / multi-agent system
        |
        v
Proposed action
        |
        v
Runtime Assurance Gateway
  - parameter-bound capability
  - evidence provenance
  - transaction/action scope
  - proposer/approver oversight
  - trust-domain separation
        |
   +----+---------+
   |              |
 ALLOW          BLOCK / ESCALATE
   |
   v
Tool / external effect
   |
   v
Versioned causal trace
   |
   +--> JSON-Schema validation
   +--> delegation/privilege validation
   +--> deterministic V4 properties
   +--> replay + canaries
   +--> result attestation
   +--> hash-linked audit history
                       |
                       v
                  Field issue
                       |
                       v
          replay -> gap -> check update
                       |
                       v
             independent review
```

`REWRITE` is reserved in the runtime decision enum for future constrained rewriting; V6 currently implements `ALLOW`, `BLOCK`, and `ESCALATE` behavior.

## Runtime gateway

[`runtime_assurance.py`](src/assurance_portfolio/runtime_assurance.py) adds a pre-action reference gate.

Sensitive/high-risk actions require a matching capability bound to the action, principal, transaction, and security-relevant parameters. Constraints support allowed values, nested values, and scalar min/max limits. High-risk actions additionally require verified transaction-bound evidence and named oversight. Self-approval is blocked; same-trust-domain approval escalates.

Untrusted tool/external content may influence reasoning but cannot create authority simply by appearing in context.

Example:

```bash
assurance-runtime examples/runtime_assurance_request.json
```

This is a reference gate, not yet an interceptor integrated into a production tool broker, operating system, cloud IAM system, or network enforcement point.

## V4 deterministic monitor retained for compatibility

[`trace_assurance.py`](src/assurance_portfolio/trace_assurance.py) remains the compact deterministic monitor for:

- authorization before sensitive actions,
- evidence before high-risk actions,
- high-risk classification consistency,
- independent proposer/approver identity,
- shutdown compliance.

Authorization/evidence grants are transaction-scoped, consumable, and optionally expiring. The base report remains `PASS`, `FAIL`, or `INCONCLUSIVE`, with property-exercise coverage semantics.

V6 does not silently reinterpret this legacy result. Audited runs expose the **base monitor result** separately from the broader **system result** and **attestation integrity**.

## Versioned event schema and governance artifacts

V6 includes concrete versioned artifacts:

- [`schemas/agent-trace/2.0.0.json`](schemas/agent-trace/2.0.0.json)
- [`checks/agent-trace-checks/6.0.0.json`](checks/agent-trace-checks/6.0.0.json)
- [`policies/agent-trace-policy/2.0.0.json`](policies/agent-trace-policy/2.0.0.json)

The event schema uses JSON Schema Draft 2020-12 and includes optional causal/delegation/provenance fields. [`schema_registry.py`](src/assurance_portfolio/schema_registry.py) supports immutable proposals, actual instance validation, compatibility classification, and independently approved activation.

Compatibility states are:

- `BACKWARD_COMPATIBLE`
- `MIGRATION_REQUIRED`
- `BREAKING`
- `SECURITY_SENSITIVE`

Schema proposal/activation are also written to the audit history when invoked through `assurance-trace-audit`.

## Causal/delegation protection

[`causal_trace.py`](src/assurance_portfolio/causal_trace.py) checks event parentage and delegation ancestry. It rejects missing parents, duplicate IDs, unknown parent capabilities, action changes during delegation, and simple privilege amplification where a child capability broadens the parent's scope.

This is a deliberately small reference model, not a complete semantics for distributed concurrency or arbitrary multi-agent collusion.

## Protecting check results from being fudged

A V6 evaluation distinguishes three concepts:

1. **base monitor result** — V4 property verdict;
2. **system result** — additionally fails schema or causal/delegation invalidity;
3. **attestation integrity** — `VERIFIED`, `UNVERIFIED`, or `INVALID`.

[`result_integrity.py`](src/assurance_portfolio/result_integrity.py) binds a result to the exact:

- trace digest,
- raw-result digest,
- checker source digest,
- check-manifest digest,
- schema digest,
- policy digest,
- configuration digest,
- runtime-environment digest,
- Git commit SHA when supplied,
- required and executed checks,
- check version and minimum permitted version.

A run is `INVALID` if required checks are omitted or the checker is below the configured minimum version. Deterministic replay disagreement, invalid causal structure, or invalid concrete schema also invalidates V6 assurance evidence.

Optional Ed25519 signatures are supported. `VERIFIED` requires a valid signature **and** concrete checker/check-manifest/schema/policy artifact binding. Unsigned evidence, or a signed record that only contains declared version labels, remains `UNVERIFIED`.

Generate a local demonstration keypair:

```bash
assurance-trace-audit keygen \
  --private-key /tmp/ata-private.pem \
  --public-key /tmp/ata-public.pem
```

Never commit private keys.

A fully artifact-bound audited evaluation can be run with:

```bash
assurance-trace-audit --audit-log artifacts/trace-audit/audit.jsonl \
  evaluate examples/agent_trace.json \
  --check-version agent-trace-checks/6.0.0 \
  --minimum-check-version agent-trace-checks/6.0.0 \
  --check-manifest-file checks/agent-trace-checks/6.0.0.json \
  --schema-version agent-trace/2.0.0 \
  --schema-file schemas/agent-trace/2.0.0.json \
  --policy-version agent-trace-policy/2.0.0 \
  --policy-file policies/agent-trace-policy/2.0.0.json
```

Without `--signing-key`, this produces artifact-bound but unsigned evidence and is therefore `UNVERIFIED`, not falsely labelled verified.

## Immutable human dispositions

A reviewer cannot rewrite a machine `FAIL` as `PASS`. Human decisions are separate audit records:

```bash
assurance-trace-audit --audit-log artifacts/trace-audit/audit.jsonl \
  waiver examples/waiver.json
```

Supported dispositions include `WAIVED`, `FALSE_POSITIVE`, `REQUIRES_INVESTIGATION`, and `ACCEPTED`. The original machine result is retained.

## Assurance self-tests

[`assurance_selftest.py`](src/assurance_portfolio/assurance_selftest.py) tests the assurance system itself with known seeded failures:

- missing authorization,
- self-approval,
- expired authorization,
- post-shutdown action.

```bash
assurance-trace-audit self-test
```

A failed canary is evidence that the assurance infrastructure itself needs investigation.

## Audit history and checkpoints

`TraceAuditStore` uses canonical JSONL records with sequence numbers, previous hashes, and SHA-256 record hashes. V6 also supports local Merkle checkpoints:

```bash
assurance-trace-audit --audit-log artifacts/trace-audit/audit.jsonl \
  anchor --external-reference external-ticket-or-checkpoint-id
```

The local chain is **tamper-evident, not tamper-proof**. A privileged actor able to replace the full local history and recompute hashes can defeat it. Production use should anchor roots in a separate trust domain such as WORM/object-lock storage or an independent transparency/audit service.

## Field-issue feedback and check evolution

[`field_issue.py`](src/assurance_portfolio/field_issue.py) replays incidents and conservatively classifies outcomes such as false negative, coverage gap, enforcement gap, false positive, or weak-check/review-needed.

```bash
assurance-trace-audit --audit-log artifacts/trace-audit/audit.jsonl \
  field-issue examples/field_issue.json
```

The analysis and its reviewable check-update suggestion are appended to the audit history.

Approved check/schema/policy changes require an independent approver. Security-sensitive control removal or policy weakening requires an additional independent approver. Update records can retain regression-evidence references.

Detailed protocol: [`benchmarks/TRACE_ASSURANCE_V6.md`](benchmarks/TRACE_ASSURANCE_V6.md)  
Architecture/research note: [`projects/alignment-assurance-lab.md`](projects/alignment-assurance-lab.md)  
Working paper: [`papers/alignment-assurance-lab-working-paper.md`](papers/alignment-assurance-lab-working-paper.md)

---

# Verification Copilot V9

## Deterministic and model-backed roles

[`verification_copilot.py`](src/assurance_portfolio/verification_copilot.py) provides a conservative complete-match deterministic requirement baseline with reviewable SVA-style drafts, scenarios, coverage goals, and explicit fallback.

[`agentic_verification.py`](src/assurance_portfolio/agentic_verification.py) adds separate model-backed generator and adversarial reviewer roles. The reviewer can return `ACCEPT_FOR_TOOL_CHECK`, `REVISE`, or `ABSTAIN`. Reviewer acceptance is not sign-off; deterministic validation and human review remain distinct.

The optional OpenAI Responses backend records request/token telemetry when the provider exposes it. Scripted backends support credential-free deterministic CI.

## Tool and behavioral evidence

[`sva_validation.py`](src/assurance_portfolio/sva_validation.py) includes structural and Verilator-backed validation.

Behavioral milestones include:

- **V6** — Icarus execution against known-good request/grant RTL and a seeded late-grant mutation;
- **V7** — four-condition deterministic / single-model / generator-reviewer / generator-reviewer-tool comparison;
- **V8** — three temporal families with good/mutated RTL and repeated trials;
- **V9** — model usage telemetry and reproducible JSON/CSV/Markdown experiment bundles.

The V8 corpus includes bounded response, prohibition, and immediate implication. Mutation detection is not counted as fully correct if a candidate also rejects known-good RTL.

Run the offline corpus:

```bash
assurance-demo corpus-eval --rtl-root benchmarks/rtl --trials 3
```

With Icarus Verilog installed, the real behavioral runners are used. Live model calls are not required by CI.

For experiment bundles:

```bash
assurance-demo corpus-eval \
  --rtl-root benchmarks/rtl \
  --trials 3 \
  --output-root artifacts/experiments
```

See [`benchmarks/V8_CORPUS.md`](benchmarks/V8_CORPUS.md) and [`benchmarks/V9_EXPERIMENT_ARTIFACTS.md`](benchmarks/V9_EXPERIMENT_ARTIFACTS.md).

---

# CI

GitHub Actions runs:

- Python 3.10 / 3.11 / 3.12 unit tests;
- Agent Trace Assurance V6 runtime-gateway, artifact-bound audit, Merkle-chain, canary, and field-issue CLI exercises;
- real Verilator assertion validation;
- V6 RTL behavioral mutation proof;
- V7 controlled comparison;
- V8 repeated multi-family Icarus corpus;
- V9 experiment-bundle generation/shape checks.

CI remains credential-free for model APIs. It does not use a production signing key; signature behavior is covered by local ephemeral-key unit tests.

---

# Research positioning and claim boundary

Trace monitoring and runtime guardrails for tool-using agents are active research areas. This repository does **not** claim that trace-based assurance itself is wholly novel. The stronger research direction is the verification-style operational loop:

**field issue → historical replay → assurance gap → versioned check/schema/policy change → independent approval → regression/adversarial closure → attested audit evidence.**

Agent Trace Assurance V6 does not prove broad prompt-injection resistance, complete hallucination detection, production tool isolation, trusted hardware execution, universal multi-agent correctness, or empirical safety improvement across real agent frameworks. Verification Copilot V9 does not prove model superiority, general natural-language-to-SVA correctness, production EDA equivalence, or SoC-scale transfer.

Those claims require larger independently designed benchmarks, real integrations, repeated trials, and expert review.

## Research portfolio

- [Multi-Agent Verification Copilot](projects/multi-agent-verification-copilot.md)
- [Alignment Assurance Lab](projects/alignment-assurance-lab.md)
- [Pre-Silicon-Inspired Assurance Architecture](projects/pre-silicon-inspired-agentic-ai-assurance.md)
- [Responsible AI and DBA Research Agenda](projects/responsible-ai-dba-research.md)
- [CloudGuard AI](projects/cloudguard-ai.md)

## Papers and artifacts

- [Artifact catalog](papers/README.md)
- [Multi-Agent Verification Copilot working paper](papers/multi-agent-verification-copilot-working-paper.md)
- [Alignment Assurance Lab working paper](papers/alignment-assurance-lab-working-paper.md)
- [CloudGuard AI course report — repository edition](papers/cloudguard-ai-course-report.md)
- [CloudGuard AI research presentation notes](papers/cloudguard-ai-research-presentation.md)

These are prototypes, course materials, presentation notes, or working papers. None is presented as an accepted or peer-reviewed publication.
