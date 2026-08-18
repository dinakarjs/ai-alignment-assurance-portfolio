# AI Assurance & Agentic Verification Portfolio - Runnable Prototypes

This repository applies semiconductor verification ideas to AI assurance and applies AI-assisted workflows back to verification engineering. It combines three small, dependency-light prototypes:

1. **CloudGuard AI** - explainable cloud-threat scoring, human approval for high-risk actions, and auditable decisions.
2. **Agent Trace Assurance Engine V2** - a deterministic policy monitor for ordered agent-event traces with transaction-scoped authorization/evidence, consumable and expiring grants, independent approval checks, shutdown monitoring, and explicit PASS/FAIL/INCONCLUSIVE coverage semantics.
3. **Verification Copilot V2** - a role-separated workflow in which an artifact-generation component creates traceable draft assertions/scenarios/coverage goals and an independent requirement-review component flags ambiguity before acceptance.

The prototypes demonstrate research ideas; they are not production security or alignment systems.

## Run

Python 3.10 or newer is required.

```bash
python -m pip install -e .
assurance-demo cloudguard examples/cloudguard_incident.json
assurance-demo trace examples/agent_trace.json
assurance-demo copilot examples/requirements.json
```

## Test

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

The test suite includes negative and boundary cases for stale/consumed authorization, transaction mismatch, missing approval, action normalization, shutdown behavior, coverage gaps, and bounded temporal requirement translation.

## CloudGuard AI

CloudGuard is derived from the Responsible AI and Explainability workshop project developed by Kenneth Amanchukwu, John Nova, and Srinivasa Dinakar. The reference scenario uses five human-readable signals with additive contributions: impossible travel, privilege escalation, failed logins, malicious IP, and time anomaly.

The prototype deliberately separates:

- a transparent risk recommendation,
- a mandatory human decision for account disablement, and
- a recommendation hash in the audit record for detecting changes to the recommendation object.

It calls its explanations **SHAP-style** because it reproduces additive feature attribution without claiming to run SHAP against a trained production model. The current audit hash is not claimed to make the full audit history tamper-proof.

## Agent Trace Assurance V2

Agent Trace Assurance is a deterministic assurance engine for tool-using and autonomous AI systems. It treats each execution as an ordered event trace, evaluates explicit safety properties at relevant steps, and identifies the exact event where a violation occurs. The design adapts pre-silicon verification ideas—properties, monitors, counterexamples, lifecycle state, and coverage—to agent behavior in a compact, auditable form.

V2 hardens the first prototype by adding:

- normalized action identifiers,
- transaction/action IDs for authorization and evidence,
- single-use authorization and evidence consumption,
- optional event-count expiry through `expires_after_events`,
- explicit violations when a high-risk action has no recorded approver,
- independent proposer/approver checking,
- shutdown compliance with audit/status exceptions, and
- three-state assurance results: **PASS**, **FAIL**, or **INCONCLUSIVE**.

A result is **INCONCLUSIVE** when no violation was observed but one or more required properties were not exercised. This deliberately distinguishes "no counterexample observed" from "the assurance case was adequately covered."

Implementation: [`trace_assurance.py`](src/assurance_portfolio/trace_assurance.py)  
Example input: [`agent_trace.json`](examples/agent_trace.json)

```bash
assurance-demo trace examples/agent_trace.json
```

### Trace event model

Authorization/evidence events can be tied to a specific action instance:

```json
{"type":"authorize","action":"disable_account","transaction_id":"tx-42","expires_after_events":3}
{"type":"evidence","action":"disable_account","transaction_id":"tx-42","expires_after_events":3}
{"type":"action","action":"disable_account","transaction_id":"tx-42","sensitive":true,"high_risk":true,"proposer":"agent","approver":"analyst"}
```

The matching grants are consumed when used, preventing one early authorization/evidence event from silently pre-clearing every later action.

## Multi-Agent Verification Copilot V2

The Verification Copilot is a role-separated reference workflow for turning natural-language safety requirements into reviewable verification artifacts.

```text
Requirement
    |
    +--> ArtifactGenerator --> draft assertion + scenarios + coverage goal
    |
    +--> RequirementReviewer --> ambiguity/specification findings
                                |
                                v
                       VerificationArtifact
```

The two responsibilities are implemented as separate components and orchestrated by `VerificationCopilot`. This is intentionally dependency-light today; the interfaces are suitable for later replacement with separate LLM/agent calls and EDA-tool integrations.

The independent review step identifies weak specifications including:

- missing normative terms such as “must” or “shall,”
- non-numeric timing bounds, and
- ambiguous words such as “quickly,” “appropriate,” “secure,” or “soon.”

The prototype preserves the requirement identifier throughout the output. Generated assertions remain **drafts for expert review**, not claims of generally correct SystemVerilog Assertion synthesis.

For a constrained requirement such as:

```text
grant shall assert within 4 cycles after request
```

V2 can produce the structured draft:

```systemverilog
assert property (@(posedge clk) request |-> ##[1:4] grant);
```

and derives nominal, boundary, and violation scenarios linked to the same requirement ID. Requirements outside the supported pattern fall back to an explicitly marked expert-review draft rather than pretending to be valid SVA.

Implementation: [`verification_copilot.py`](src/assurance_portfolio/verification_copilot.py)  
Example input: [`requirements.json`](examples/requirements.json)

```bash
assurance-demo copilot examples/requirements.json
```

## Research portfolio

- [Alignment Assurance Lab](projects/alignment-assurance-lab.md)
- [Multi-Agent Verification Copilot](projects/multi-agent-verification-copilot.md)
- [Pre-Silicon-Inspired Assurance Architecture](projects/pre-silicon-inspired-agentic-ai-assurance.md)
- [Responsible AI and DBA Research Agenda](projects/responsible-ai-dba-research.md)
- [CloudGuard AI](projects/cloudguard-ai.md)

## Papers and research artifacts

- [Artifact catalog](papers/README.md)
- [CloudGuard AI course report - repository edition](papers/cloudguard-ai-course-report.md)
- [CloudGuard AI research presentation notes](papers/cloudguard-ai-research-presentation.md)
- [Multi-Agent Verification Copilot working paper](papers/multi-agent-verification-copilot-working-paper.md)
- [Alignment Assurance Lab working paper](papers/alignment-assurance-lab-working-paper.md)

These documents are course materials, presentation notes, or working papers. None is presented as an accepted or peer-reviewed publication.

## Scope and next steps

All current results are deterministic and reproducible, and the code is intentionally small enough to audit. V2 strengthens lifecycle and coverage semantics but does not claim production-grade policy enforcement, general natural-language-to-SVA synthesis, calibrated risk prediction, or empirical alignment guarantees.

Planned extensions include constrained-random/adversarial trace generation, coverage dashboards, counterexample minimization, calibrated/real-world datasets, separate model-backed generator/reviewer agents, EDA tool orchestration, and evaluation across models and agent scaffolds.
