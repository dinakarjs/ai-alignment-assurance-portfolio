# AI Assurance & Agentic Verification Portfolio - Runnable Prototypes

This repository applies semiconductor verification ideas to AI assurance and applies AI-assisted workflows back to verification engineering. It combines three small, dependency-light prototypes:

1. **CloudGuard AI V3** - explainable cloud-threat scoring, explicit evidence-strength semantics, mandatory human approval for high-risk actions, and auditable decisions.
2. **Agent Trace Assurance Engine V2** - a deterministic policy monitor for ordered agent-event traces with transaction-scoped authorization/evidence, consumable and expiring grants, independent approval checks, shutdown monitoring, and explicit PASS/FAIL/INCONCLUSIVE coverage semantics.
3. **Verification Copilot V3** - a role-separated workflow with requirement review, draft assertion/scenario generation, independent artifact review, generation provenance, and explicit SUPPORTED/FALLBACK status.

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

GitHub Actions runs the unit suite and CLI smoke tests on Python 3.10, 3.11, and 3.12.

## CloudGuard AI V3

CloudGuard is derived from the Responsible AI and Explainability workshop project developed by Kenneth Amanchukwu, John Nova, and Srinivasa Dinakar. The reference scenario uses five human-readable signals with additive contributions: impossible travel, privilege escalation, failed logins, malicious IP, and time anomaly.

The prototype deliberately separates:

- a transparent risk recommendation,
- a heuristic **evidence strength** value rather than claiming calibrated statistical confidence,
- the top three non-zero contributing signals,
- a mandatory human decision for account disablement, and
- a recommendation hash in the audit record for detecting changes to the recommendation object.

It calls its explanations **SHAP-style** because it reproduces additive feature attribution without claiming to run SHAP against a trained production model. The current audit hash is not claimed to make the full audit history tamper-proof.

The CLI example now exercises the complete workflow:

```text
Incident -> Recommendation -> Human decision + rationale -> AuditRecord
```

Implementation: [`cloudguard.py`](src/assurance_portfolio/cloudguard.py)  
Example input: [`cloudguard_incident.json`](examples/cloudguard_incident.json)

## Agent Trace Assurance V2

Agent Trace Assurance is a deterministic assurance engine for tool-using and autonomous AI systems. It treats each execution as an ordered event trace, evaluates explicit safety properties at relevant steps, and identifies the exact event where a violation occurs. The design adapts pre-silicon verification ideas—properties, monitors, counterexamples, lifecycle state, and coverage—to agent behavior.

V2 includes:

- normalized action identifiers,
- transaction/action IDs for authorization and evidence,
- single-use authorization and evidence consumption,
- optional event-count expiry through `expires_after_events`,
- strict scoped matching so unscoped grants do not silently approve scoped actions,
- explicit violations when a high-risk action has no recorded approver,
- independent proposer/approver checking,
- shutdown compliance with audit/status exceptions, and
- three-state assurance results: **PASS**, **FAIL**, or **INCONCLUSIVE**.

A result is **INCONCLUSIVE** when no violation was observed but one or more required properties were not exercised. This distinguishes "no counterexample observed" from "the assurance case was adequately covered."

Implementation: [`trace_assurance.py`](src/assurance_portfolio/trace_assurance.py)  
Example input: [`agent_trace.json`](examples/agent_trace.json)

## Verification Copilot V3

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

V3 exposes whether generation was **SUPPORTED** by an explicit grammar or used **FALLBACK**. The artifact reviewer independently flags fallback output and expert-review requirements, so unsupported phrasing does not silently look like successful assertion synthesis.

Supported draft patterns currently include:

- bounded response: `grant shall assert within 4 cycles after request`
- alternate bounded phrasing: `grant shall be asserted no later than 4 cycles following request`
- conditional bounded response: `if request, grant shall assert within 3 cycles`
- prohibition: `grant shall never assert while reset`
- immediate implication: `if request is high, busy shall be high`
- persistence: `busy shall remain asserted until done`

Example bounded translation:

```systemverilog
assert property (@(posedge clk) request |-> ##[1:4] grant);
```

Requirements outside the supported grammar produce an explicitly marked fallback draft and an artifact-review finding. Generated assertions remain **drafts for expert review**, not claims of generally correct SystemVerilog Assertion synthesis.

Implementation: [`verification_copilot.py`](src/assurance_portfolio/verification_copilot.py)  
Example input: [`requirements.json`](examples/requirements.json)

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

All current results are deterministic and reproducible, and the code is intentionally small enough to audit. V3 strengthens artifact-review transparency and the human-oversight demo but does not claim production-grade policy enforcement, general natural-language-to-SVA synthesis, calibrated risk prediction, or empirical alignment guarantees.

Planned extensions include constrained-random/adversarial trace generation, coverage dashboards, counterexample minimization, model-backed generator/reviewer agents, richer grammar or structured requirement parsing, EDA tool orchestration, and evaluation across models and agent scaffolds.
