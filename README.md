# AI Assurance & Agentic Verification Portfolio — Runnable Prototypes

This repository applies semiconductor-verification discipline to AI assurance and applies AI/agent workflows back to pre-silicon verification engineering. It deliberately separates proposal, enforcement, deterministic checking, behavioral evidence, human oversight, evaluation integrity, execution-environment integrity, and evidence integrity.

The two primary technical pillars are:

1. **Verification Copilot V9** — deterministic and model-backed requirement-to-verification workflows, tool validation, behavioral RTL mutation testing, controlled comparison, repeated trials, usage telemetry, and reproducible experiment bundles.
2. **Agent Trace Assurance V6.1** — deterministic trace properties, pre-action capability/evidence gating, versioned schemas/policies/checks, causal/delegation validation, evaluation-leakage protection, privileged CI/CD controls, field-issue feedback, result attestations, anti-rollback, immutable waivers, assurance canaries, and auditable check evolution.

A smaller **CloudGuard AI V3** Responsible-AI demonstration remains as supporting coursework/research material.

These are research prototypes. They are not production EDA sign-off, production IAM/security enforcement, alignment guarantees, or regulatory compliance claims.

## Quick start

Python 3.10 or newer is required.

```bash
python -m pip install -e .
assurance-demo copilot examples/requirements.json
assurance-demo trace examples/agent_trace.json
assurance-runtime examples/runtime_assurance_request.json
assurance-integrity evaluation examples/evaluation_integrity_clean.json
assurance-integrity cicd examples/cicd_integrity_clean.json
assurance-demo cloudguard examples/cloudguard_incident.json
```

Run the full test suite:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

---

# Agent Trace Assurance V6.1

## Design principle: the model is not the security boundary

V6.1 treats an LLM/agent as an **untrusted planner**. Deterministic infrastructure decides whether an effectful operation may proceed, whether an experiment is contaminated, whether a privileged CI/CD environment is being misused, and whether the resulting assurance record is trustworthy.

The architecture now separates four integrity boundaries:

1. **Action integrity** — is the AI authorized to perform the proposed effect?
2. **Evaluation integrity** — was performance measured without answer/scoring leakage or evaluator conflict?
3. **Result integrity** — were required checks, versions, artifacts, and reported results authentic and complete?
4. **Execution-environment integrity** — can untrusted AI/input exploit CI/CD identity, secrets, or production authority?

A system may pass one boundary while failing another; a bare aggregate `PASS` is therefore insufficient assurance evidence.

## Runtime gateway

[`runtime_assurance.py`](src/assurance_portfolio/runtime_assurance.py) implements a pre-action reference gate. Sensitive/high-risk actions require a capability bound to the action, principal, transaction, and security-relevant parameters. High-risk actions additionally require verified transaction-bound evidence and named oversight. Self-approval is blocked; same-trust-domain approval escalates.

Untrusted tool/external content may influence reasoning but cannot create authority merely by appearing in context.

```bash
assurance-runtime examples/runtime_assurance_request.json
```

This remains a reference gate, not yet a production OS/cloud/tool-broker interceptor.

## Evaluation Collusion & Leakage Protection

[`evaluation_integrity.py`](src/assurance_portfolio/evaluation_integrity.py) addresses contaminated evaluation pipelines where a model/module receives answer keys, ground truth, scoring signals, evaluator feedback, or equivalent privileged information.

Artifacts carry producers, parent relationships, labels, optional digests, and access records. Restricted labels propagate transitively through artifact ancestry. The implemented labels include:

- `MODEL_INPUT`
- `MODEL_DERIVED`
- `GROUND_TRUTH`
- `ANSWER_KEY`
- `EVALUATOR_ONLY`
- `SCORING_SIGNAL`
- `POST_COMMIT_FEEDBACK`
- `EVALUATION_CANARY`

A valid evaluation requires the prediction to be committed before ground truth is released, prohibits privileged evaluation data from becoming an ancestor of the prediction, prevents pre-commit scoring feedback from reaching the system under test, and requires scorer identity outside the system-under-test principal set.

```bash
assurance-integrity evaluation examples/evaluation_integrity_clean.json
```

Attribution can also be measured under privileged-channel isolation:

```bash
assurance-integrity attribution --baseline 0.50 --full 0.85 --isolated 0.55
```

The reported privileged-channel-dependent gain is descriptive evidence, not an automatic cheating/collusion verdict.

## CI/CD & Privileged Execution Integrity

[`cicd_integrity.py`](src/assurance_portfolio/cicd_integrity.py) addresses AI agents running inside potentially privileged CI/CD jobs. The key invariant is:

`agent capability != runner capability != production promotion capability`

The reference validator checks untrusted triggers against privileged runners, trusted-control refs, self-modification of workflow/policy guardrails, secret exposure, permission escalation, independent production approval, and reviewed-artifact digest matching.

```bash
assurance-integrity cicd examples/cicd_integrity_clean.json
```

A read-only sandbox may accept untrusted PR content. A secret-bearing/write-capable runner is a different trust domain and requires stronger controls.

## V4 deterministic monitor retained for compatibility

[`trace_assurance.py`](src/assurance_portfolio/trace_assurance.py) remains the compact deterministic monitor for authorization, evidence, high-risk classification, independent approval, and shutdown compliance. Base results remain `PASS`, `FAIL`, or `INCONCLUSIVE` with property-exercise coverage semantics.

## Versioned artifacts and immutable evolution

Concrete governance artifacts include:

- [`schemas/agent-trace/2.0.0.json`](schemas/agent-trace/2.0.0.json)
- [`policies/agent-trace-policy/2.0.0.json`](policies/agent-trace-policy/2.0.0.json)
- [`checks/agent-trace-checks/6.0.0.json`](checks/agent-trace-checks/6.0.0.json)
- [`checks/agent-trace-checks/6.1.0.json`](checks/agent-trace-checks/6.1.0.json)

The 6.0.0 manifest remains unchanged. New evaluation- and CI/CD-integrity controls are introduced in 6.1.0 rather than silently rewriting an older version.

[`schema_registry.py`](src/assurance_portfolio/schema_registry.py) supports immutable proposals, actual JSON-Schema Draft 2020-12 instance validation, compatibility classification, and independently approved activation.

## Causal/delegation protection

[`causal_trace.py`](src/assurance_portfolio/causal_trace.py) checks event parentage and delegation ancestry. It rejects missing parents, duplicate IDs, unknown parent capabilities, action changes during delegation, and simple privilege amplification where a child capability broadens its parent's scope.

## Protecting check results from being fudged

A V6.1 audited evaluation distinguishes:

1. **base monitor result** — V4 property verdict;
2. **system result** — additionally fails schema or causal/delegation invalidity;
3. **attestation integrity** — `VERIFIED`, `UNVERIFIED`, or `INVALID`.

[`result_integrity.py`](src/assurance_portfolio/result_integrity.py) binds a result to the trace, raw result, checker source, check manifest, schema, policy, configuration, runtime environment, optional Git commit, required/executed checks, and minimum/current check versions.

Omitted required checks or rollback below the minimum version are `INVALID`. Deterministic replay disagreement and invalid structure also invalidate assurance evidence. Optional Ed25519 signatures are supported; `VERIFIED` additionally requires concrete artifact binding.

```bash
assurance-trace-audit --audit-log artifacts/trace-audit/audit.jsonl \
  evaluate examples/agent_trace.json \
  --check-version agent-trace-checks/6.1.0 \
  --minimum-check-version agent-trace-checks/6.0.0 \
  --check-manifest-file checks/agent-trace-checks/6.1.0.json \
  --schema-version agent-trace/2.0.0 \
  --schema-file schemas/agent-trace/2.0.0.json \
  --policy-version agent-trace-policy/2.0.0 \
  --policy-file policies/agent-trace-policy/2.0.0.json
```

Unsigned but artifact-bound evidence remains `UNVERIFIED`, not falsely labelled verified.

## Immutable human dispositions, canaries, and audit anchors

A reviewer cannot rewrite a machine `FAIL` as `PASS`; review is appended as a separate disposition. `assurance_selftest.py` injects known assurance failures, and `TraceAuditStore` uses canonical hash-linked JSONL records plus optional Merkle checkpoints.

The local chain is tamper-evident, not tamper-proof. Production use should anchor roots in a separate trust domain such as WORM/object-lock storage or an independent transparency/audit service.

## Field-issue feedback and check evolution

[`field_issue.py`](src/assurance_portfolio/field_issue.py) replays incidents and classifies false negative, coverage gap, enforcement gap, false positive, or weak-check/review-needed outcomes. Approved changes require independent review; security-sensitive weakening/removal requires an additional independent approver.

Detailed protocol: [`benchmarks/TRACE_ASSURANCE_V6.md`](benchmarks/TRACE_ASSURANCE_V6.md)  
Architecture/research note: [`projects/alignment-assurance-lab.md`](projects/alignment-assurance-lab.md)  
Working paper: [`papers/alignment-assurance-lab-working-paper.md`](papers/alignment-assurance-lab-working-paper.md)  
V6.1 integrity addendum: [`papers/alignment-assurance-v6-integrity-addendum.md`](papers/alignment-assurance-v6-integrity-addendum.md)

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

Run the offline corpus:

```bash
assurance-demo corpus-eval --rtl-root benchmarks/rtl --trials 3
```

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
- Agent Trace Assurance runtime, evaluation-integrity, CI/CD-integrity, artifact-bound audit, Merkle-chain, canary, and field-issue exercises;
- real Verilator assertion validation;
- V6 RTL behavioral mutation proof;
- V7 controlled comparison;
- V8 repeated multi-family Icarus corpus;
- V9 experiment-bundle checks.

EDA-tool installation is isolated from Python installation, uses retries/network timeouts, and has explicit step/job time limits so an external Ubuntu mirror stall cannot masquerade as a hung assurance test.

CI remains credential-free for model APIs and does not use a production signing key; signature behavior is covered with ephemeral-key unit tests.

---

# Research positioning and claim boundary

Trace monitoring and runtime guardrails for tool-using agents are active research areas. This repository does **not** claim that trace-based assurance itself is wholly novel. The stronger research direction is the verification-style operational loop combined with independent integrity boundaries:

**field issue → historical replay → assurance gap → versioned check/schema/policy change → independent approval → regression/adversarial closure → attested audit evidence.**

Agent Trace Assurance V6.1 does not prove complete prompt-injection resistance, complete hallucination detection, trustworthy instrumentation, production CI/IAM isolation, universal multi-agent correctness, trusted hardware execution, or empirical safety improvement across real agent frameworks. Verification Copilot V9 does not prove model superiority, general natural-language-to-SVA correctness, production EDA equivalence, or SoC-scale transfer.

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
- [Alignment Assurance V6 integrity addendum](papers/alignment-assurance-v6-integrity-addendum.md)
- [CloudGuard AI course report — repository edition](papers/cloudguard-ai-course-report.md)
- [CloudGuard AI research presentation notes](papers/cloudguard-ai-research-presentation.md)

These are prototypes, course materials, presentation notes, or working papers. None is presented as an accepted or peer-reviewed publication.
