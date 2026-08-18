# Alignment Assurance Lab V6 Integrity Addendum

## Evaluation Leakage, Privileged CI/CD Execution, and Assurance Evidence

**Author:** Srinivasa J. Dinakar  
**Date:** August 18, 2026  
**Status:** Working-paper addendum; not peer reviewed

## Purpose

This addendum records two additional threat classes incorporated after the initial V6 architecture was drafted:

1. **evaluation contamination/collusion**, where a module under evaluation receives answer keys, scoring signals, evaluator feedback, or equivalent privileged information and thereby inflates measured performance; and
2. **privileged CI/CD execution**, where an AI agent processes untrusted PR/comment/tool content while running in a workflow that holds repository-write, secret, cloud, OIDC, or production-promotion authority.

These threats are distinct from post-hoc result tampering. A cryptographically authentic result can still be misleading if the experiment was contaminated, and an audit log can accurately describe an unsafe CI/CD action after the privileged effect has already occurred.

## 1. Evaluation-information-flow integrity

The new `evaluation_integrity.py` layer treats ground truth and evaluator state as privileged control-plane information. Evaluation artifacts are modeled as provenance nodes with producers, parent artifacts, labels, optional content digests, and access records.

Labels include:

- `PUBLIC_INPUT`
- `MODEL_INPUT`
- `MODEL_DERIVED`
- `GROUND_TRUTH`
- `ANSWER_KEY`
- `EVALUATOR_ONLY`
- `SCORING_SIGNAL`
- `POST_COMMIT_FEEDBACK`
- `EVALUATION_CANARY`

Restricted labels propagate transitively through artifact ancestry. A prediction is invalid if it is derived, directly or indirectly, from privileged evaluation data.

The design also requires the prediction to be committed before ground truth is released. This creates a commit-before-label-release temporal boundary and prevents evaluation feedback from becoming an iterative hidden hint channel.

The scorer must be outside the system-under-test principal set and inside the evaluator trust boundary. This does not prove the evaluator is incorruptible; it prevents the architecture from treating the same module as both contestant and authoritative scorer.

## 2. Evaluation canaries

Evaluation-only canaries provide a verification-style leakage test. A sentinel artifact labeled `EVALUATION_CANARY` should never be read by or become an ancestor of a system-under-test artifact. Detection indicates a broken isolation boundary or untrustworthy instrumentation.

Canaries do not prove the absence of all hidden channels. They provide active evidence that the tested information-flow path is monitored.

## 3. Attribution through channel isolation

A high aggregate score does not establish which module caused the improvement. The attribution helper therefore compares:

- baseline score,
- full-pipeline score,
- score with the privileged information channel isolated.

The difference between full and isolated score is reported as **privileged-channel-dependent gain**. The fraction of claimed gain dependent on that channel is descriptive evidence, not an automatic finding of intentional cheating or collusion.

A controlled research evaluation should extend this to module disablement, output shuffling/randomization, cross-model swaps, hidden-label isolation, and repeatable seeds.

## 4. CI/CD privilege integrity

The new `cicd_integrity.py` layer treats the AI agent as less trusted than the CI runner/control plane. The central invariant is:

`agent capability != runner capability != production promotion capability`

A safe read-only PR analysis workflow can accept untrusted code/content. A workflow with repository-write, secret, cloud, OIDC, registry, or deployment authority requires a stronger trust boundary.

The reference validator detects or escalates:

- untrusted triggers entering privileged runners,
- privileged control executed from an untrusted source ref,
- an agent changing its own workflow/policy guardrails,
- secrets in an untrusted-trigger agent context,
- secret use without explicit secret capability,
- requested permissions broader than the runner permits,
- privileged action requests from untrusted triggers,
- production deployment without independent approval,
- same-trust-domain production approval,
- promoted artifact digest differing from the independently reviewed artifact.

## 5. Connection to result integrity

The V6 architecture now distinguishes four integrity boundaries:

1. **Action integrity** — whether the proposed effect is authorized.
2. **Evaluation integrity** — whether performance was measured without privileged-answer/scoring leakage.
3. **Result integrity** — whether required checks, versions, artifacts, and reported results are authentic and complete.
4. **Execution-environment integrity** — whether untrusted AI/input can exploit CI/CD identity, secrets, or production authority.

A valid design must avoid collapsing these into one `PASS`. For example, a signed result can be `VERIFIED` at the result-integrity layer while the evaluation-integrity layer is invalid because the prediction depended on an answer-key-derived artifact.

## 6. Check-set evolution

The existing `agent-trace-checks/6.0.0` artifact is intentionally left unchanged. New controls are introduced as `agent-trace-checks/6.1.0`.

This is important: a system that claims immutable/versioned governance should not silently rewrite an old version when new threats are discovered. The update itself must be visible and attributable.

## 7. Research implications

These additions sharpen the project’s research contribution. The aim is not merely to add more guardrails. It is to test whether verification concepts can provide measurable assurance across multiple independent trust boundaries:

- prevent unauthorized effects,
- detect contaminated evaluation paths,
- constrain privileged execution environments,
- preserve trustworthy evidence about what was checked,
- convert operational failures into governed versioned improvements.

The next controlled evaluation should explicitly include leakage and CI/CD attack scenarios rather than only action-policy violations.

## 8. Limitations

The reference implementation does not prove that provenance/access logs are truthful. A compromised instrumentation layer could omit an access or mislabel an artifact. Likewise, CI/CD context is currently supplied as structured input rather than obtained from a remotely attested runner/control plane.

Stronger deployment would require independently trusted instrumentation, immutable event capture, managed identities/short-lived credentials, sandbox/tool brokering, artifact signing, protected promotion gates, remote attestation where justified, and external audit anchoring.

These are future integration requirements, not current prototype claims.
