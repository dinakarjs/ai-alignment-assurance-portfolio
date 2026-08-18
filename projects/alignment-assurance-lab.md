# Alignment Assurance Lab

**Status:** Runnable research prototype with deterministic trace monitoring, pre-action runtime gating, evaluation-integrity checks, CI/CD privilege controls, versioned governance artifacts, result attestation, and auditable field-feedback history  
**Theme:** Verification-driven runtime assurance and governance for agentic AI systems

## Motivation

Tool-using and multi-agent AI systems can fail even when their final answer looks acceptable. A model can hallucinate, follow malicious tool content, overreach its authority, reuse stale evidence, amplify privilege through delegation, drift over long horizons, contaminate its own evaluation by receiving answer/scoring information, or turn attacker-controlled CI/CD input into privileged repository/cloud actions. A separate risk is that assurance evidence itself can be omitted, downgraded, rewritten, or selectively reported.

The design therefore treats the AI model as an **untrusted planner** and moves security and assurance boundaries into deterministic infrastructure around actions, evaluation, execution environments, and result evidence.

## Architecture

```text
External/user/tool data
        |
        v
Trust classification
        |
        v
AI planner / multi-agent system      [untrusted planner]
        |
        +------------------------------+
        |                              |
        v                              v
Proposed effectful action        Prediction / experiment
        |                              |
        v                              v
Runtime Assurance Gate          Evaluation Integrity Gate
 authority/capability            ground-truth isolation
 evidence/provenance             provenance taint
 parameter scope                 commit-before-label-release
 trust-domain approval           scorer independence
        |                              |
 ALLOW/BLOCK/ESCALATE             VALID / INVALID
        |                              |
        v                              v
Least-privilege Tool Broker      Independent Evaluator
        |                              |
        +---------------+--------------+
                        |
                        v
                 Versioned causal trace
                        |
          +-------------+--------------+
          |             |              |
          v             v              v
   schema/causal    result         CI/CD integrity
    validation     attestation     trusted refs/secrets/
                                   promotion boundary
          |             |              |
          +-------------+--------------+
                        |
                        v
                  Audit evidence
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

`REWRITE` remains reserved in the runtime decision enum; V6 currently implements `ALLOW`, `BLOCK`, and `ESCALATE`.

## V4 deterministic monitor — retained baseline

[`trace_assurance.py`](../src/assurance_portfolio/trace_assurance.py) remains the compact deterministic compatibility baseline. It checks authorization before sensitive actions, evidence before high-risk actions, high-risk classification consistency, independent proposer/approver identity, and shutdown compliance. Grants are transaction-scoped, consumable, and optionally expiring.

## V5 auditable history

V5 introduced [`trace_audit.py`](../src/assurance_portfolio/trace_audit.py), preserving evaluation results and check/schema/policy changes in a hash-linked JSONL history.

## V6 runtime assurance and integrity layers

### 1. Pre-action runtime gateway

[`runtime_assurance.py`](../src/assurance_portfolio/runtime_assurance.py) requires parameter-bound capabilities for sensitive/high-risk actions and verified transaction-bound evidence plus independent oversight for high-risk actions. Untrusted tool/external content may inform reasoning but cannot create authority by itself.

### 2. Versioned event/schema/policy control

[`schemas/agent-trace/2.0.0.json`](../schemas/agent-trace/2.0.0.json) uses JSON Schema Draft 2020-12. [`schema_registry.py`](../src/assurance_portfolio/schema_registry.py) validates schema documents and trace instances, classifies compatibility, and separates proposal from independent activation.

### 3. Causal/delegation validation

[`causal_trace.py`](../src/assurance_portfolio/causal_trace.py) checks parent-event references, capability ancestry, and simple privilege amplification where a delegated child broadens its parent's action or constraints.

### 4. Result integrity

[`result_integrity.py`](../src/assurance_portfolio/result_integrity.py) separates system verdict from attestation integrity: `VERIFIED`, `UNVERIFIED`, or `INVALID`. Trustworthy evidence binds the exact trace/result/checker/check manifest/schema/policy/configuration/environment and optional Git identity, enforces required checks and anti-rollback, supports deterministic replay, and can be Ed25519-signed.

A human disposition is appended separately and cannot rewrite the original machine verdict.

### 5. Closed-loop operational feedback

[`field_issue.py`](../src/assurance_portfolio/field_issue.py) replays incidents and classifies false-negative, coverage-gap, enforcement-gap, false-positive, or weak-check/review-needed cases. Check updates are auditable; security-sensitive weakening/removal requires an additional independent approver.

### 6. Evaluation Collusion & Leakage Protection

[`evaluation_integrity.py`](../src/assurance_portfolio/evaluation_integrity.py) addresses the failure mode where one module appears to improve a pipeline by leaking answer keys, scoring signals, evaluator feedback, or equivalent privileged information to another module.

Evaluation artifacts carry provenance labels such as `MODEL_INPUT`, `MODEL_DERIVED`, `GROUND_TRUTH`, `ANSWER_KEY`, `EVALUATOR_ONLY`, `SCORING_SIGNAL`, `POST_COMMIT_FEEDBACK`, and `EVALUATION_CANARY`. Restricted labels propagate transitively through artifact ancestry.

A valid evaluation requires:

- no ground-truth/evaluator-only ancestry in the prediction,
- prediction commit before ground-truth release,
- no pre-commit scoring feedback to the system under test,
- scorer identity outside the system-under-test trust domain,
- evaluation-only canaries never reaching model modules.

The attribution helper measures how much claimed improvement disappears when privileged channels are isolated. It is descriptive evidence, not an automatic cheating verdict.

### 7. CI/CD & Privileged Execution Integrity

[`cicd_integrity.py`](../src/assurance_portfolio/cicd_integrity.py) addresses AI agents operating inside privileged CI/CD runners. The key principle is:

`agent capability != runner capability != production promotion capability`

Controls include:

- untrusted triggers cannot enter privileged write-capable workflows,
- privileged control must come from the trusted reference,
- an agent cannot modify the workflow/policy that governs itself,
- secrets require explicit capability and cannot enter untrusted-trigger agent context,
- requested permissions cannot exceed runner permissions,
- production effects require independent approval,
- promoted artifact digest must match the independently reviewed artifact.

## Immutable check evolution

The original [`6.0.0`](../checks/agent-trace-checks/6.0.0.json) check manifest is retained unchanged. New evaluation- and CI/CD-integrity controls are introduced in [`6.1.0`](../checks/agent-trace-checks/6.1.0.json), preserving the project's own version-governance principle rather than silently editing an existing version.

## Protecting the assurance system itself

V6 includes checker/schema/policy/config/environment digests, check-manifest binding, anti-rollback, deterministic replay, optional signatures, immutable human dispositions, seeded assurance canaries, hash-chain verification, and local Merkle checkpoints. Local hashes do not replace external WORM/object-lock, independent transparency logging, trusted hardware, or remote attestation.

## CLI examples

```bash
# Action/runtime boundary
assurance-runtime examples/runtime_assurance_request.json

# Clean evaluation-isolation example
assurance-integrity evaluation examples/evaluation_integrity_clean.json

# Clean least-privilege CI/CD example
assurance-integrity cicd examples/cicd_integrity_clean.json

# Quantify apparent gain dependent on a privileged information channel
assurance-integrity attribution --baseline 0.50 --full 0.85 --isolated 0.55

# Artifact-bound audited trace evaluation
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

## Four integrity boundaries

The architecture now treats four questions independently:

1. **Action integrity** — is the AI authorized to perform the proposed effect?
2. **Evaluation integrity** — was performance measured without answer/scoring leakage or scorer collusion?
3. **Result integrity** — were required checks, versions, artifacts, and reported results authentic and complete?
4. **Execution-environment integrity** — can untrusted AI/input exploit privileged CI/CD identity, secrets, or promotion authority?

A system can pass one boundary while failing another; a bare aggregate `PASS` is therefore insufficient assurance evidence.

## Research positioning

Trace monitoring and runtime agent guardrails are active research areas and are not claimed as wholly novel. The stronger contribution is the verification-style closed loop combined with independent integrity boundaries:

`field issue -> replay -> assurance gap -> versioned check/schema/policy change -> independent approval -> regression/adversarial closure -> attested evidence`.

The recent failure reports motivating evaluation leakage and privileged CI/CD isolation are treated as threat-model inputs, not as proof that this prototype prevents all such attacks.

## Next controlled evaluation

The next empirical study should compare outcome-only evaluation, post-hoc trace monitoring, runtime gating, and runtime gating plus closed-loop feedback. It should also include adversarial variants for answer leakage, scoring feedback, evaluator-canary exposure, untrusted CI triggers, secret exposure, workflow self-modification, and artifact substitution.

Metrics should include unsafe-action prevention, false-block/escalation rate, violation recall/precision, property/hazard coverage, replay consistency, attestation-verification rate, evaluation-leakage detection, privileged-channel-dependent gain, CI privilege violations, field-issue recurrence, runtime overhead, and reviewer agreement.

## Trust boundary

V6 is a reference implementation. It does not provide complete hallucination or prompt-injection detection, production IAM/tool interception, semantic validation of arbitrary evidence, universal distributed-agent semantics, cryptographic enforcement of every provenance label, trusted hardware execution, remote attestation, or external transparency anchoring by default. Evaluation integrity depends on trustworthy instrumentation of artifact ancestry/access and CI/CD integrity depends on truthful workflow-context inputs unless integrated with a real runner/control plane.

## Detailed protocol

See [`TRACE_ASSURANCE_V6.md`](../benchmarks/TRACE_ASSURANCE_V6.md).

## Working paper

[Alignment Assurance Lab: Runtime Assurance, Trace Evidence, and Closed-Loop Governance for Tool-Using AI Agents](../papers/alignment-assurance-lab-working-paper.md)
