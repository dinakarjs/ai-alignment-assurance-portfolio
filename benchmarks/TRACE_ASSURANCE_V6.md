# Agent Trace Assurance V6 — Runtime, Evaluation, CI/CD, and Result Integrity

V6 treats the AI model as an **untrusted planner** and surrounds it with deterministic controls for pre-action authorization, trustworthy evaluation, least-privilege execution, trace validation, result attestation, and closed-loop check improvement.

## Threat model

| Weakness / attack | V6 control |
|---|---|
| hallucinated/unsupported high-risk claim | verified transaction-bound evidence |
| prompt/tool injection creating authority | untrusted content cannot create capability |
| excessive privilege / parameter substitution | parameter-bound capabilities |
| authorization replay | transaction/action scope |
| self-approval | principal separation |
| weak multi-agent independence | trust-domain escalation |
| delegation privilege amplification | parent/child capability subset checks |
| malformed/incompatible trace | JSON Schema validation |
| ground-truth/answer leakage | evaluation provenance taint + ground-truth isolation |
| scoring feedback before prediction freeze | commit-before-label-release + feedback isolation |
| evaluator/model collusion | scorer independence and evaluator trust boundary |
| hidden evaluation channel | evaluation canary noninterference |
| apparent gain dependent on privileged information | controlled isolation/ablation attribution |
| untrusted PR/comment reaches write-capable AI runner | CI/CD trigger/permission boundary |
| agent edits its own workflow/policy | self-governance modification block |
| secrets exposed to untrusted agent context | secret/capability isolation |
| privilege escalation from agent to runner | requested-permission subset check |
| artifact changed after review | reviewed-artifact digest match |
| stale/downgraded checker | anti-rollback |
| omitted checks | required/executed manifest |
| checker/schema/policy/result modification | concrete artifact digests |
| human rewrites FAIL to PASS | immutable machine result + separate disposition |
| local audit editing | hash chain + Merkle checkpoint |
| whole-log replacement | requires external anchor; not solved locally |
| assurance regression | replay + canary self-tests |
| field issue escapes | replay/gap classification/check-update proposal |

## 1. Runtime action integrity

`runtime_assurance.py` emits `ALLOW`, `BLOCK`, or `ESCALATE` before an effectful tool operation. Sensitive/high-risk actions must match parameter-bound capabilities. High-risk actions additionally require verified evidence and independent oversight. `REWRITE` is reserved but not implemented.

```bash
assurance-runtime examples/runtime_assurance_request.json
```

## 2. Evaluation Collusion & Leakage Protection

`evaluation_integrity.py` treats ground truth, answer keys, evaluator-only data, scoring signals, post-commit feedback, and evaluation canaries as privileged evaluation-plane information.

Artifacts have producers, parent artifacts, labels, optional digests, and access records. Restricted labels propagate transitively through provenance ancestry. The prediction is invalid if privileged evaluation data becomes an ancestor of the prediction or is accessed by a system-under-test principal.

Required checks include:

- `evaluation_ground_truth_isolation`
- `prediction_before_label_release`
- `prediction_commit_integrity`
- `evaluation_feedback_isolation`
- `transitive_provenance_taint`
- `module_capability_separation`
- `scorer_independence`
- `evaluation_canary_noninterference`

A prediction must be committed before ground truth is released. The scorer must be outside the system-under-test principal set and inside the evaluator trust boundary.

```bash
assurance-integrity evaluation examples/evaluation_integrity_clean.json
```

### Attribution / isolation experiment

The helper compares baseline score, full-pipeline score, and score after privileged channels are isolated:

```bash
assurance-integrity attribution --baseline 0.50 --full 0.85 --isolated 0.55
```

It reports the fraction of apparent gain dependent on the privileged channel. This is descriptive evidence and **not an automatic cheating/collusion verdict**.

## 3. CI/CD & Privileged Execution Integrity

`cicd_integrity.py` assumes an AI agent inside CI is less trusted than the runner/control plane. The core invariant is:

`agent capability != runner capability != production promotion capability`

Checks cover:

- untrusted triggers reaching privileged runners,
- workflow/policy control coming from an untrusted ref,
- AI modification of its own workflow/policy,
- secret exposure without explicit capability,
- requested permissions exceeding runner permissions,
- privileged execution from untrusted triggers,
- independent approval for production effects,
- production artifact digest matching the reviewed artifact.

```bash
assurance-integrity cicd examples/cicd_integrity_clean.json
```

A read-only sandbox can accept untrusted PR input. A write-capable or secret-bearing runner cannot be treated equivalently.

## 4. Versioned schema and check lifecycle

The V6 event schema is `schemas/agent-trace/2.0.0.json` and is validated using JSON Schema Draft 2020-12. `schema_registry.py` supports immutable proposal, compatibility classification, and independently approved activation.

Compatibility states:

- `BACKWARD_COMPATIBLE`
- `MIGRATION_REQUIRED`
- `BREAKING`
- `SECURITY_SENSITIVE`

The original `checks/agent-trace-checks/6.0.0.json` remains immutable. The new evaluation- and CI/CD-integrity controls are introduced in `checks/agent-trace-checks/6.1.0.json`.

## 5. Causal and delegation integrity

`causal_trace.py` checks unique IDs, earlier parent references, capability ancestry, delegated action consistency, and simple constraint narrowing. It is not a complete distributed partial-order verifier.

## 6. Three result dimensions

Audited evaluation distinguishes:

1. **base monitor result** — `PASS` / `FAIL` / `INCONCLUSIVE` from the original trace monitor;
2. **system result** — additionally fails structural/schema/causal validation;
3. **attestation integrity** — `VERIFIED` / `UNVERIFIED` / `INVALID`.

A bare `PASS` is not sufficient assurance evidence.

## 7. Anti-fudging result attestation

`result_integrity.py` binds the result to SHA-256 digests of trace, raw result, checker, required-check manifest, schema, policy, configuration, environment, and optional Git identity. It enforces required-check completeness and minimum check version, performs deterministic replay, and optionally signs the attestation with Ed25519.

`VERIFIED` requires concrete artifact binding plus a valid signature. Unsigned or version-label-only provenance remains `UNVERIFIED`. Omitted checks or rollback below the floor are `INVALID`.

## 8. Immutable human disposition

Humans may append `WAIVED`, `FALSE_POSITIVE`, `REQUIRES_INVESTIGATION`, or `ACCEPTED` dispositions, but cannot mutate the original machine verdict.

## 9. Audit chain and anchors

`TraceAuditStore` records sequence numbers, previous-record hashes, canonical record hashes, and optional Merkle checkpoints. Local checkpoints are tamper-evident only; production requires a separate trust domain such as WORM/object-lock storage or an independent transparency service.

## 10. Assurance self-tests

Known violations test the checker itself:

- missing authorization,
- self-approval,
- expired grant,
- post-shutdown action.

```bash
assurance-trace-audit self-test
```

Failure of a canary means assurance evidence should not be trusted until investigated.

## 11. Field-issue feedback

Operational incidents can be replayed and classified as false negative, coverage gap, enforcement gap, false positive, or weak-check/review-needed. Analyses and proposed improvements enter the audit chain.

```bash
assurance-trace-audit --audit-log /tmp/audit.jsonl field-issue examples/field_issue.json
```

## 12. Check-update governance

Normal approved changes require separate proposer and approver. Check removal, policy weakening, or explicitly security-sensitive updates require a second independent approver. Existing versioned artifacts must not be overwritten; a new version is created instead.

## 13. CI reliability hardening

The GitHub Actions workflow now separates Python package installation from Verilator/Icarus installation. EDA-tool installation uses package-manager retries, 30-second network timeouts, `--no-install-recommends`, a 5-minute step timeout, and a 10-minute job timeout. This prevents a mirror/network stall from looking like a hung V6 test.

## 14. Four integrity boundaries

V6 evaluates four different questions:

1. **Action integrity** — is the proposed effect authorized and supported?
2. **Evaluation integrity** — was performance measured without answer/scoring leakage or evaluator conflict?
3. **Result integrity** — were all required checks/artifacts/results authentic and complete?
4. **Execution-environment integrity** — can untrusted AI/input exploit CI/CD identity, secrets, or production authority?

Passing one boundary does not imply passing the others.

## 15. Controlled evaluation roadmap

The next empirical study should include benign and adversarial scenarios for:

- prompt/tool injection,
- parameter substitution,
- stale or unverified evidence,
- delegation amplification,
- answer-key leakage through intermediate modules,
- pre-commit scoring feedback,
- evaluation-canary exposure,
- scorer/system identity overlap,
- untrusted PR/comment triggers on privileged CI runners,
- secret exposure,
- workflow/policy self-modification,
- reviewed-artifact substitution,
- check downgrade/omission,
- field-issue recurrence after check updates.

Metrics should include unsafe-action prevention, false-block/escalation rate, violation recall/precision, property/hazard coverage, evaluation-leakage detection, privileged-channel-dependent gain, CI privilege violations, attestation verification, canary detection, recurrence after check update, runtime overhead, and reviewer agreement.

## 16. Trust boundary

This is a reference implementation. It does not provide complete hallucination/prompt-injection detection, production IAM/tool interception, cryptographically trustworthy evaluation instrumentation, universal multi-agent semantics, trusted CI attestation, hardware roots of trust, or external transparency anchoring by default. Evaluation labels/provenance and CI workflow context must ultimately come from independently trustworthy instrumentation for strong claims.
