# AI Alignment Assurance Portfolio - Runnable Prototypes

This repository combines three small, dependency-light prototypes:

1. **CloudGuard AI** - explainable cloud-threat scoring, human approval for high-risk actions, and auditable decisions.
2. **Agent Trace Assurance Engine** - a deterministic policy monitor that evaluates ordered agent-event traces, pinpoints violations of authorization, evidence, independent-approval, and shutdown rules, and reports coverage gaps.
3. **Verification Copilot** - a role-separated workflow that converts natural-language requirements into traceable draft assertions, nominal/boundary/adversarial scenarios, and coverage goals, followed by an independent ambiguity review.

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

## CloudGuard AI

CloudGuard is derived from the Responsible AI and Explainability workshop project developed by Kenneth Amanchukwu, John Nova, and Srinivasa Dinakar. The reference scenario uses five human-readable signals with additive contributions: impossible travel, privilege escalation, failed logins, malicious IP, and time anomaly.

The prototype deliberately separates:

- a transparent risk recommendation,
- a mandatory human decision for account disablement, and
- a tamper-evident recommendation hash in the audit record.

It calls its explanations **SHAP-style** because it reproduces additive feature attribution without claiming to run SHAP against a trained production model.

## Agent Trace Assurance

Agent Trace Assurance is a deterministic assurance engine for tool-using and autonomous AI systems. It treats each execution as an ordered event trace, evaluates explicit safety properties at every relevant step, and identifies the exact event where a violation occurs. The design adapts pre-silicon verification ideas—properties, monitors, counterexamples, and coverage—to agent behavior in a compact, auditable form.

The current monitor checks:

- authorization before sensitive actions,
- recorded evidence before high-risk actions,
- separation between the action proposer and approver, and
- compliance with shutdown commands.

Its output is an assurance report containing the overall pass/fail result, property violations with exact event positions, covered properties, and uncovered properties. This makes both failures and gaps in the evaluation visible.

Implementation: [`trace_assurance.py`](src/assurance_portfolio/trace_assurance.py)  
Example input: [`agent_trace.json`](examples/agent_trace.json)

```bash
assurance-demo trace examples/agent_trace.json
```

## Multi-Agent Verification Copilot

The Verification Copilot is a role-separated reference workflow for turning natural-language safety requirements into reviewable verification artifacts. A generation role creates a draft assertion, nominal/boundary/adversarial scenarios, and a requirement-linked coverage goal; an independent review role then flags ambiguity and specification weaknesses before the artifacts are accepted.

A separate review step identifies weak specifications, including:

- missing normative terms such as “must” or “shall,”
- non-numeric timing bounds, and
- ambiguous words such as “quickly,” “appropriate,” or “secure.”

The prototype preserves the requirement identifier throughout the output, demonstrating requirements-to-verification traceability. Its generated assertions are intentionally drafts for expert review rather than claims of formally correct SystemVerilog Assertions.

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

## Scope

All results are deterministic and reproducible. The code is intentionally small enough to audit. Future work should replace synthetic weights and scenarios with calibrated models, real-world datasets, threat-model validation, and user studies with SOC analysts.
