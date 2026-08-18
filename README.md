# AI Assurance & Agentic Verification Portfolio — Runnable Prototypes

This repository applies semiconductor-verification discipline to AI assurance and applies AI/agent workflows back to pre-silicon verification engineering. It deliberately separates proposal, enforcement, deterministic checking, behavioral evidence, human oversight, evaluation integrity, execution-environment integrity, evidence integrity, and field feedback.

The three primary technical pillars are:

1. **Verification Copilot V9** — deterministic and model-backed requirement-to-verification workflows, tool validation, behavioral RTL mutation testing, controlled comparison, repeated trials, usage telemetry, and reproducible experiment bundles.
2. **Agent Trace Assurance V6.1** — deterministic trace properties, pre-action capability/evidence gating, versioned schemas/policies/checks, causal/delegation validation, evaluation-leakage protection, privileged CI/CD controls, field-issue feedback, result attestations, anti-rollback, immutable waivers, assurance canaries, and auditable check evolution.
3. **CloudGuard AI V4** — assurance-governed cloud incident response with source-labelled threat intelligence, immutable threat versions, detector/evidence provenance, impact-tier response policy, HITL/dual approval, threat-database regression gates, detected-threat audit records, response outcomes, rollback, and field-issue-driven security improvement.

These are research prototypes. They are not production EDA sign-off, production IAM/SOC enforcement, alignment guarantees, or regulatory compliance claims.

## Quick start

Python 3.10 or newer is required.

```bash
python -m pip install -e .

# Verification Copilot
assurance-demo copilot examples/requirements.json

# Agent Trace Assurance
assurance-demo trace examples/agent_trace.json
assurance-runtime examples/runtime_assurance_request.json
assurance-integrity evaluation examples/evaluation_integrity_clean.json
assurance-integrity cicd examples/cicd_integrity_clean.json

# CloudGuard V3 educational baseline
assurance-demo cloudguard examples/cloudguard_incident.json

# CloudGuard V4 governed workflows
assurance-cloudguard threat-update examples/cloudguard_v4_threat_update.json
assurance-cloudguard response examples/cloudguard_v4_response.json
```

Run the full test suite:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

---

# Agent Trace Assurance V6.1

## Design principle: the model is not the security boundary

V6.1 treats an LLM/agent as an **untrusted planner**. Deterministic infrastructure decides whether an effectful operation may proceed, whether an experiment is contaminated, whether a privileged CI/CD environment is being misused, and whether the resulting assurance record is trustworthy.

The architecture separates four integrity boundaries:

1. **Action integrity** — is the AI authorized to perform the proposed effect?
2. **Evaluation integrity** — was performance measured without answer/scoring leakage or evaluator conflict?
3. **Result integrity** — were required checks, versions, artifacts, and reported results authentic and complete?
4. **Execution-environment integrity** — can untrusted AI/input exploit CI/CD identity, secrets, or production authority?

A system may pass one boundary while failing another; a bare aggregate `PASS` is therefore insufficient assurance evidence.

[`runtime_assurance.py`](src/assurance_portfolio/runtime_assurance.py) implements the pre-action capability/evidence gate. [`evaluation_integrity.py`](src/assurance_portfolio/evaluation_integrity.py) detects evaluation-only information flowing into predictions. [`cicd_integrity.py`](src/assurance_portfolio/cicd_integrity.py) checks privileged-runner boundaries. [`result_integrity.py`](src/assurance_portfolio/result_integrity.py) binds assurance results to required artifacts and optional Ed25519 attestations.

Detailed protocol: [`benchmarks/TRACE_ASSURANCE_V6.md`](benchmarks/TRACE_ASSURANCE_V6.md)  
Architecture/research note: [`projects/alignment-assurance-lab.md`](projects/alignment-assurance-lab.md)  
Working paper: [`papers/alignment-assurance-lab-working-paper.md`](papers/alignment-assurance-lab-working-paper.md)  
V6.1 integrity addendum: [`papers/alignment-assurance-v6-integrity-addendum.md`](papers/alignment-assurance-v6-integrity-addendum.md)

---

# CloudGuard AI V4

## V3 stays as the transparent educational baseline

[`cloudguard.py`](src/assurance_portfolio/cloudguard.py) intentionally remains the small workshop-compatible model: five synthetic normalized risk signals, additive SHAP-style contributions, a heuristic evidence-strength value, a named analyst for account disablement, and a recommendation checksum.

V3 is useful for explainability teaching but is **not** treated as a production security architecture. In particular, its heuristic evidence strength is not calibrated confidence, and its single SHA-256 recommendation hash is not a complete tamper-evident audit history.

## V4 design principle: threat intelligence and AI recommendations are inputs, not authority

[`cloudguard_v4.py`](src/assurance_portfolio/cloudguard_v4.py) adds five explicit control planes:

1. **Threat knowledge** — immutable threat versions, source trust/provenance, controlled activation and rollback.
2. **Detection** — detector ID/version/digest plus verified evidence and exact threat version.
3. **Assurance** — deterministic response impact tiers; model confidence is excluded from authorization.
4. **Human governance** — named analyst approval for account/privilege change and dual independent approval for destructive/business-critical action.
5. **Audit & feedback** — hash-linked threat-update/detection/policy/outcome records plus field-gap classification.

```text
Threat intelligence / field incident
            |
            v
   source trust + provenance
            |
            v
   versioned threat knowledge
            |
            v
 telemetry -> detection -> evidence
            |
            v
        AI SOC analyst
       [untrusted planner]
            |
            v
    proposed response
            |
            v
 deterministic policy gate
      /      |       \
   ALLOW   BLOCK   ESCALATE
                      |
                      v
                 HITL / dual review
                      |
                      v
                  response action
                      |
                      v
                outcome / recovery
                      |
                      v
                 field feedback
                      |
                      v
 threat/detector/policy/playbook proposal
                      |
                      v
      regression + independent review
                      |
                      v
             versioned activation
```

## Governed threat database updates

Threat-update activation requires:

- immutable `(threat_id, version)`,
- named proposer and rationale,
- proposer/approver separation,
- passing regression evidence,
- an additional independent reviewer when the source is untrusted or the update weakens an existing control.

The feedback engine may propose a threat, detector, policy, telemetry, playbook, or recovery change. It **never auto-activates** the change.

## HITL and response impact tiers

| Tier | Response class | Reference oversight |
| --- | --- | --- |
| 0 | Observe/read | no human approval by default |
| 1 | Enrich/query | no human approval by default |
| 2 | Temporary containment | policy/HITL review unless bounded emergency policy applies |
| 3 | Account/privilege change | one named human approval |
| 4 | Destructive/business-critical | two independent reviewers/trust domains |

Verified required evidence is checked before effectful response. A high model probability does not create response authority.

## Threat detection and audit trail

Detected threats are audit objects that bind the exact threat version, detector version/digest, mapped techniques, evidence objects, and active threat-database digest. Response-policy decisions, field feedback, and outcomes are separate audit records.

`CloudGuardAuditStore` uses canonical hash-linked JSONL records. The local chain is tamper-evident rather than tamper-proof; production use should add protected signatures/checkpoints and independent WORM/transparency anchoring.

## Continuous security feedback

V4 classifies operational feedback into threat-database, detection, telemetry, policy, response, recovery, false-positive, or review-required gaps. The target loop is:

**new threat / field incident → provenance → coverage gap → controlled update proposal → attack/benign/evasion regression → independent review → versioned activation → monitored outcome → recurrence feedback**

This is the cybersecurity analogue of **field bug → counterexample → check/test → regression → coverage closure**.

Versioned artifacts:

- [`schemas/cloudguard-threat/1.0.0.json`](schemas/cloudguard-threat/1.0.0.json)
- [`policies/cloudguard-response/1.0.0.json`](policies/cloudguard-response/1.0.0.json)
- [`checks/cloudguard-controls/4.0.0.json`](checks/cloudguard-controls/4.0.0.json)

Detailed architecture: [`projects/cloudguard-ai.md`](projects/cloudguard-ai.md)  
Protocol: [`benchmarks/CLOUDGUARD_V4.md`](benchmarks/CLOUDGUARD_V4.md)  
Research addendum: [`papers/cloudguard-v4-assurance-addendum.md`](papers/cloudguard-v4-assurance-addendum.md)

---

# Verification Copilot V9

[`verification_copilot.py`](src/assurance_portfolio/verification_copilot.py) provides a conservative complete-match deterministic requirement baseline. [`agentic_verification.py`](src/assurance_portfolio/agentic_verification.py) adds separate model-backed generator and adversarial reviewer roles. Reviewer acceptance is not sign-off; deterministic validation and human review remain distinct.

[`sva_validation.py`](src/assurance_portfolio/sva_validation.py) includes structural and Verilator-backed validation. Behavioral milestones include V6 Icarus mutation proof, V7 four-condition comparison, V8 multi-family repeated corpus, and V9 reproducible experiment bundles plus model-usage telemetry.

```bash
assurance-demo corpus-eval --rtl-root benchmarks/rtl --trials 3
```

See [`benchmarks/V8_CORPUS.md`](benchmarks/V8_CORPUS.md) and [`benchmarks/V9_EXPERIMENT_ARTIFACTS.md`](benchmarks/V9_EXPERIMENT_ARTIFACTS.md).

---

# CI

GitHub Actions runs:

- Python 3.10 / 3.11 / 3.12 unit tests;
- CloudGuard V3 compatibility tests;
- CloudGuard V4 threat-update, threat-detection, policy/HITL, field-feedback, response-outcome, and audit-chain exercises;
- Agent Trace Assurance runtime, evaluation-integrity, CI/CD-integrity, artifact-bound audit, canary, and field-issue exercises;
- real Verilator assertion validation;
- V6 RTL behavioral mutation proof;
- V7 controlled comparison;
- V8 repeated multi-family Icarus corpus;
- V9 experiment-bundle checks.

EDA-tool installation is isolated from Python installation, uses retries/network timeouts, and has explicit step/job time limits.

---

# Research positioning and claim boundary

The portfolio focuses on **verification-style assurance loops** rather than presenting model output as proof:

**field issue → replay/evidence → assurance gap → versioned check/schema/policy/detection change → independent approval → regression/adversarial closure → auditable evidence.**

Agent Trace Assurance V6.1 does not prove complete prompt-injection resistance, trustworthy instrumentation, production CI/IAM isolation, or universal multi-agent correctness. CloudGuard V4 does not prove production threat-detection accuracy, live CTI/RAG security, deployed SOAR enforcement, or measured SOC productivity gains. Verification Copilot V9 does not prove model superiority, general natural-language-to-SVA correctness, production EDA equivalence, or SoC-scale transfer.

Those claims require independently designed benchmarks, real integrations, repeated trials, and expert review.

## Research portfolio

- [Multi-Agent Verification Copilot](projects/multi-agent-verification-copilot.md)
- [Alignment Assurance Lab](projects/alignment-assurance-lab.md)
- [CloudGuard AI](projects/cloudguard-ai.md)
- [Pre-Silicon-Inspired Assurance Architecture](projects/pre-silicon-inspired-agentic-ai-assurance.md)
- [Responsible AI and DBA Research Agenda](projects/responsible-ai-dba-research.md)

## Papers and artifacts

- [Artifact catalog](papers/README.md)
- [Multi-Agent Verification Copilot working paper](papers/multi-agent-verification-copilot-working-paper.md)
- [Alignment Assurance Lab working paper](papers/alignment-assurance-lab-working-paper.md)
- [Alignment Assurance V6 integrity addendum](papers/alignment-assurance-v6-integrity-addendum.md)
- [CloudGuard AI course report — repository edition](papers/cloudguard-ai-course-report.md)
- [CloudGuard AI research presentation notes](papers/cloudguard-ai-research-presentation.md)
- [CloudGuard V4 assurance addendum](papers/cloudguard-v4-assurance-addendum.md)

These are prototypes, course materials, presentation notes, or working papers. None is presented as an accepted or peer-reviewed publication.
