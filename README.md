# AI Assurance & Agentic Verification Portfolio - Runnable Prototypes

This repository applies semiconductor verification ideas to AI assurance and applies AI-assisted workflows back to verification engineering. It combines three small, dependency-light prototypes:

1. **Verification Copilot V4** - a role-separated workflow with full-match requirement grammars, draft assertion/scenario generation, independent requirement and artifact review, provenance, and explicit SUPPORTED/FALLBACK status.
2. **Agent Trace Assurance Engine V4** - a deterministic policy monitor for ordered agent-event traces with transaction-scoped authorization/evidence, consumable and expiring grants, high-risk classification checks, independent approval checks, shutdown monitoring, and explicit PASS/FAIL/INCONCLUSIVE semantics.
3. **CloudGuard AI V3** - explainable cloud-threat scoring, explicit evidence-strength semantics, human decision capture for high-risk recommendations, and auditable decisions.

The prototypes demonstrate research ideas; they are not production security, alignment, EDA, or autonomous-agent systems.

## Run

Python 3.10 or newer is required.

```bash
python -m pip install -e .
assurance-demo copilot examples/requirements.json
assurance-demo trace examples/agent_trace.json
assurance-demo cloudguard examples/cloudguard_incident.json
```

## Test

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

GitHub Actions runs the unit suite and CLI smoke tests on Python 3.10, 3.11, and 3.12.

## Verification Copilot V4

The Verification Copilot is a role-separated reference workflow for turning natural-language requirements into reviewable verification artifacts.

```text
Requirement
   |\
   | +--> RequirementReviewer --> specification findings
   |
   +----> ArtifactGenerator ----> draft assertion + scenarios + coverage
                                      |
                                      v
                              ArtifactReviewer
                                      |
                                      v
                             VerificationArtifact
```

V4 makes a deliberately conservative change: generation is marked **SUPPORTED** only when the **complete normalized requirement** matches an explicit grammar. A recognizable substring followed by an unsupported clause does not count as success. For example, `grant shall assert within 4 cycles after request unless reset or abort` falls back rather than silently dropping the reset/abort condition.

Supported draft patterns currently include:

- bounded response: `grant shall assert within 4 cycles after request`
- alternate bounded phrasing: `grant shall be asserted no later than 4 cycles following request`
- conditional bounded response: `if request, grant shall assert within 3 cycles`
- prohibition: `grant shall never assert while reset`
- immediate implication: `if request is high, busy shall be high`
- persistence: `busy shall remain asserted until done`

Each supported pattern now produces pattern-specific nominal/boundary-or-transition/violation scenarios and a pattern-specific coverage goal. Translation parameters are retained in the artifact for inspection.

Example bounded translation:

```systemverilog
assert property (@(posedge clk) request |-> ##[1:4] grant);
```

Generated assertions remain **drafts for expert review**. The prototype does not yet parse RTL, elaborate SVA in a simulator/formal tool, infer clock/reset domains, or claim general natural-language-to-SVA correctness.

Implementation: [`verification_copilot.py`](src/assurance_portfolio/verification_copilot.py)  
Example input: [`requirements.json`](examples/requirements.json)

## Agent Trace Assurance V4

Agent Trace Assurance is a deterministic assurance engine for tool-using and autonomous AI systems. It treats each execution as an ordered event trace, evaluates explicit safety properties at relevant steps, and identifies the exact event where a violation occurs. The design adapts pre-silicon verification ideas—properties, monitors, counterexamples, lifecycle state, and property-exercise coverage—to agent behavior.

V4 includes:

- normalized action identifiers,
- transaction/action IDs for authorization and evidence,
- single-use authorization and evidence consumption,
- optional event-count expiry through `expires_after_events`,
- strict scoped matching so unscoped grants do not silently approve scoped actions,
- explicit rejection of `high_risk=true` actions that are not also classified sensitive,
- continued evaluation of high-risk authorization/evidence controls even when classification is wrong,
- explicit violations for missing proposer or approver identity,
- independent proposer/approver checking,
- shutdown compliance with audit/status exceptions, and
- three-state assurance results: **PASS**, **FAIL**, or **INCONCLUSIVE**.

A result is **INCONCLUSIVE** when no violation was observed but one or more required properties were not exercised. The current coverage metric should be understood as **property-exercise coverage**, not full functional/assertion/vacuity coverage.

The engine still assumes that authorization/evidence events are trustworthy observations. It does not yet verify whether the actor issuing an authorization has policy authority, assess evidence provenance/quality, or protect trace integrity.

Implementation: [`trace_assurance.py`](src/assurance_portfolio/trace_assurance.py)  
Example input: [`agent_trace.json`](examples/agent_trace.json)

## CloudGuard AI V3

CloudGuard is derived from the Responsible AI and Explainability workshop project developed by Kenneth Amanchukwu, John Nova, and Srinivasa Dinakar. The reference scenario uses five human-readable signals with additive contributions: impossible travel, privilege escalation, failed logins, malicious IP, and time anomaly.

The prototype deliberately separates:

- a transparent risk recommendation,
- a heuristic **evidence strength** value rather than claiming calibrated statistical confidence,
- the top three non-zero contributing signals,
- capture of a named human decision and rationale for high-risk recommendations, and
- a recommendation hash in the audit record for detecting changes to the recommendation object.

The human decision API is an audit/demo mechanism, not a production execution gate: callers are not technically prevented from ignoring the decision step. It calls its explanations **SHAP-style** because it reproduces additive feature attribution without claiming to run SHAP against a trained production model. The current audit hash is not claimed to make the full audit history tamper-proof.

Implementation: [`cloudguard.py`](src/assurance_portfolio/cloudguard.py)  
Example input: [`cloudguard_incident.json`](examples/cloudguard_incident.json)

## Research portfolio

- [Multi-Agent Verification Copilot](projects/multi-agent-verification-copilot.md)
- [Alignment Assurance Lab](projects/alignment-assurance-lab.md)
- [Pre-Silicon-Inspired Assurance Architecture](projects/pre-silicon-inspired-agentic-ai-assurance.md)
- [Responsible AI and DBA Research Agenda](projects/responsible-ai-dba-research.md)
- [CloudGuard AI](projects/cloudguard-ai.md)

## Papers and research artifacts

- [Artifact catalog](papers/README.md)
- [Multi-Agent Verification Copilot working paper](papers/multi-agent-verification-copilot-working-paper.md)
- [Alignment Assurance Lab working paper](papers/alignment-assurance-lab-working-paper.md)
- [CloudGuard AI course report - repository edition](papers/cloudguard-ai-course-report.md)
- [CloudGuard AI research presentation notes](papers/cloudguard-ai-research-presentation.md)

These documents are course materials, presentation notes, or working papers. None is presented as an accepted or peer-reviewed publication.

## Scope and next milestones

All current runnable results are deterministic and reproducible, and the code is intentionally small enough to audit. V4 improves fail-safe parsing, pattern-specific verification artifacts, and trace-policy bypass resistance, but it does not claim production-grade policy enforcement, general natural-language-to-SVA synthesis, calibrated risk prediction, or empirical alignment guarantees.

The next substantive milestone is intentionally separate from this deterministic baseline:

1. add model-backed generator and reviewer roles behind explicit interfaces,
2. add parser/simulator/formal validation for generated assertions,
3. use a small open RTL/control target with seeded defects and reference properties,
4. compare single-agent, unconstrained multi-agent, and role-separated workflows, and
5. report assertion validity, defect detection, vacuity, false positives, coverage, human review time, and cost.
