# AI Alignment Assurance Portfolio - Runnable Prototypes

This repository combines three small, dependency-light prototypes:

1. **CloudGuard AI** - explainable cloud-threat scoring, human approval for high-risk actions, and auditable decisions.
2. **Agent Trace Assurance** - executable checks for authorization, evidence, independent approval, and shutdown compliance.
3. **Multi-Agent Verification Copilot** - traceable draft assertions, scenarios, coverage goals, and independent ambiguity review.

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

## Research portfolio

- [Alignment Assurance Lab](projects/alignment-assurance-lab.md)
- [Multi-Agent Verification Copilot](projects/multi-agent-verification-copilot.md)
- [Pre-Silicon-Inspired Assurance Architecture](projects/pre-silicon-inspired-agentic-ai-assurance.md)
- [Responsible AI and DBA Research Agenda](projects/responsible-ai-dba-research.md)
- [CloudGuard AI](projects/cloudguard-ai.md)

## Scope

All results are deterministic and reproducible. The code is intentionally small enough to audit. Future work should replace synthetic weights and scenarios with calibrated models, real-world datasets, threat-model validation, and user studies with SOC analysts.
