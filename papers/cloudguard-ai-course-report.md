# CloudGuard AI: AI-Powered Autonomous Security Analyst

**Authors:** Amanchukwu Kenneth, John Nova, Dinakar J. Srinivasa  
**Institution:** Golden Gate University  
**Course:** DBA 808 - Emerging Digital Technologies, Generative AI: Pretrained Models  
**Cohort:** Cohort 8, Group 1  
**Original submission:** March 27, 2026  
**Artifact status:** Condensed repository edition of an academic course report; not peer reviewed

## Abstract

Enterprise cloud environments have increased the scale and complexity of cybersecurity operations, contributing to alert overload, delayed response, and elevated breach costs. Traditional security information and event management systems aggregate threat data effectively but remain limited in contextual reasoning and autonomous response. CloudGuard AI proposes a hybrid system that combines machine-learning anomaly detection, large-language-model reasoning, retrieval-augmented generation, and policy-driven response automation. The design targets faster detection and explanation while preserving graduated autonomy, human escalation, and an auditable trail.

**Keywords:** generative AI, cloud security, autonomous threat detection, SIEM, retrieval-augmented generation, large language models, anomaly detection, mid-market security

## Problem

Cloud-security systems generate more events than human analysts can manually triage. The report identifies five interacting challenges:

- high-volume log and alert streams,
- evolving attacks that evade static rules,
- false positives and analyst fatigue,
- a shortage of security professionals, and
- slow investigation and containment.

Effective response requires correlation across identity, network, resource, and threat-intelligence data. At the same time, an incorrect automated action can disrupt legitimate services. The problem therefore needs both machine-scale analysis and explicit controls on autonomy.

## Proposed architecture

CloudGuard AI uses four sequential layers.

### 1. Collect

Cloud audit logs, identity events, network traffic, firewall data, and external threat-intelligence feeds enter a common event pipeline. The source report proposes Kafka for streaming and Elasticsearch for indexed retrieval.

### 2. Detect

Complementary anomaly-detection approaches operate on the event stream:

- Isolation Forest for statistical outliers,
- sequence models such as LSTMs for multi-step behavior, and
- autoencoders for deviations from learned baselines.

The objective is to combine detection of known suspicious patterns with discovery of behavioral anomalies.

### 3. Analyse

A retrieval-augmented generation pipeline retrieves relevant historical incidents and supporting evidence. An LLM then produces a structured result containing:

1. threat type,
2. plain-language root-cause explanation,
3. risk-severity classification, and
4. remediation recommendation.

Evidence grounding and confidence thresholds are intended to reduce unsupported recommendations and determine when human review is required.

### 4. Respond

The decision layer considers risk, confidence, asset criticality, and policy. High-confidence routine cases may invoke predefined cloud-security actions; medium-confidence or high-impact cases are escalated; low-confidence anomalies are logged for continued monitoring. All recommendations and actions are recorded for audit.

The runnable prototype in this repository deliberately uses a more conservative control: disabling an account requires a named human analyst's decision and rationale.

## Evaluation plan

The report proposes four primary measures:

- precision and recall for threat detection,
- false-positive reduction relative to a SIEM baseline,
- average response time, and
- reduction in manual analyst-triage effort.

A credible evaluation would also measure calibration, override rates, explanation usefulness, recovery from incorrect actions, and performance under prompt injection or poisoned retrieval data. The current repository prototype uses synthetic inputs and deterministic scoring; it does not claim production validation.

## Implementation roadmap

| Phase | Timeline | Focus |
| --- | --- | --- |
| Prototype | 0-6 months | Event ingestion, baseline anomaly model, LLM incident reporting, and core cloud infrastructure |
| Beta | 6-18 months | Monitoring dashboard, controlled response actions, multi-cloud integration, pilot users, and operational retrieval |
| Commercialization | 18-36 months | Predictive detection, cross-cloud monitoring, SOC integration, and product hardening |

Each phase should have evidence-based exit criteria. Examples include recall targets on a stated dataset, bounded false-positive rates, security review, human-override analysis, and recovery tests.

## Responsible-AI and assurance considerations

The architecture creates safety obligations because an incorrect recommendation may lock out users, interrupt services, or conceal a real incident. The project therefore emphasizes:

- evidence-linked explanations,
- graduated autonomy,
- human approval for high-impact actions,
- clear approve, reject, and investigate controls,
- tamper-evident audit records, and
- explicit limitations on what synthetic demonstrations establish.

The companion explainability work uses human-readable additive contributions to show why a risk score was produced. These are described as **SHAP-style** contributions because the reference prototype does not run SHAP against a trained production model.

## Relationship to the runnable prototype

The repository implementation focuses on a narrow, reproducible assurance slice of the larger architecture:

- five normalized cloud-risk signals,
- transparent additive scoring,
- ranked feature contributions,
- a mandatory human decision for account disablement,
- analyst identity and rationale, and
- a SHA-256 recommendation hash.

See [cloudguard.py](../src/assurance_portfolio/cloudguard.py), the [CloudGuard project page](../projects/cloudguard-ai.md), and [cloudguard_incident.json](../examples/cloudguard_incident.json).

## Limitations

This artifact is a design proposal and course report. It does not demonstrate a trained security model, benchmark results, field deployment, market validation, or patentability. External statistics and market claims from the original submission should be rechecked against their primary sources before reuse. The implementation uses synthetic weights and scenarios and must not be treated as a production security control.

## References from the source report

- Fortune Business Insights. (2025). *Cloud Security Market Size, Share and Forecast Report, 2034*.
- IBM Security. (2024). *Cost of a Data Breach Report 2024*.
- ISC2. (2024). *Cybersecurity Workforce Study 2024*.
- Microsoft. (2024). *Microsoft Sentinel documentation*.
- OWASP. (2025). *Top 10 for Large Language Model Applications 2025*.
- Palo Alto Networks. (2025). *Predictions for Autonomous AI*.
- Stellar Cyber. (2026). *Agentic SOC platform overview*.

## Suggested citation

Amanchukwu, K., Nova, J., & Srinivasa, D. J. (2026). *CloudGuard AI: AI-Powered Autonomous Security Analyst*. Golden Gate University, DBA 808 course report, repository edition.
