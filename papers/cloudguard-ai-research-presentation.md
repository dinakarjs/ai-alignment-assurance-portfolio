# AI-Powered Autonomous Cloud Security Analyst

**Authors:** Kenneth Amanchukwu, John Nova, Srinivasa J. Dinakar  
**Year:** 2026  
**Artifact status:** Repository notes for a companion research presentation; not peer reviewed

## Presentation purpose

The presentation introduces CloudGuard AI as a hybrid cloud-security concept that combines anomaly detection, generative-AI explanation, and controlled response. It is a companion artifact to the [course report](cloudguard-ai-course-report.md) and the [runnable CloudGuard prototype](../projects/cloudguard-ai.md).

## Core narrative

### Problem

Enterprise cloud environments generate more security telemetry than analysts can review manually. Existing tools often aggregate and flag events but still require substantial human effort to connect evidence, explain the incident, prioritize risk, and choose a remediation.

### Vision

CloudGuard AI is framed as an always-available security analyst that can:

- monitor cloud activity continuously,
- detect abnormal behavior,
- explain incidents in plain language,
- recommend a response, and
- execute only those actions allowed by policy and oversight controls.

### Architecture

The proposed flow contains four stages:

1. **Continuous monitoring** of logs, identity events, network activity, and threat intelligence.
2. **AI threat detection** using anomaly and behavioral models.
3. **Generative analysis** that produces evidence-grounded explanations and remediation recommendations.
4. **Controlled response** through cloud APIs, human escalation, and an audit trail.

### Explainability and oversight

The later workshop extension focuses on a suspicious-account scenario: impossible travel, privilege escalation, failed logins, malicious-IP evidence, and an abnormal login time. The analyst view presents a 95/100 risk score with additive factor contributions and requires human approval before disabling the account.

The reference implementation preserves this control pattern but describes the contributions as **SHAP-style**, not actual SHAP output from a trained production model.

## Evidence in this repository

- [CloudGuard project description](../projects/cloudguard-ai.md)
- [CloudGuard implementation](../src/assurance_portfolio/cloudguard.py)
- [Example incident](../examples/cloudguard_incident.json)
- [Automated tests](../tests/test_prototypes.py)
- [Course-report repository edition](cloudguard-ai-course-report.md)

## Limitations

The presentation is a solution concept, not evidence of a deployed autonomous SOC or validated threat-detection model. Architecture, performance, cost, market, and intellectual-property claims require independent validation before external reuse.

## Suggested citation

Amanchukwu, K., Nova, J., & Dinakar, S. J. (2026). *AI-Powered Autonomous Cloud Security Analyst*. CloudGuard AI research presentation.
