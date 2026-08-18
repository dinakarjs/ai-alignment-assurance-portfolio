# CloudGuard AI V4 — Assurance-Governed Threat Intelligence and Response

**Status:** Working-paper addendum; not peer reviewed  
**Date:** August 18, 2026

## Abstract

The original CloudGuard AI coursework proposed a hybrid cloud-security architecture combining anomaly detection, retrieval-augmented/LLM analysis, graduated autonomy, human escalation, and auditability. The runnable prototype intentionally implemented only a transparent five-signal scoring demonstration. A 2026 architecture review found that this narrow implementation was useful for explainability teaching but insufficient as a security architecture: its evidence-strength value was heuristic rather than calibrated, the SHA-256 recommendation checksum was not a complete tamper-evident audit trail, response authorization was too coarsely tied to a single high-risk action, and there was no governed lifecycle for threat intelligence, detector changes, recovery, or field feedback.

CloudGuard V4 therefore reframes the system as an **assurance-governed agentic SOC reference architecture**. The AI/SOC model is treated as an untrusted analyst/planner. Threat intelligence is source-labelled and versioned; effectful response requires verified evidence and deterministic impact-tier policy; high-impact actions require human review; destructive/business-critical actions require dual independent review; threat-database updates require independent approval and passing regression evidence; detected threats, response policy, outcomes, and field feedback are written into a hash-linked audit history; and operational failures generate reviewable update proposals rather than autonomous self-modification.

## 1. Literature and standards context

NIST SP 800-61 Rev. 3 (2025) integrates incident response into broader cybersecurity risk management and emphasizes improving incident detection, response, and recovery. This motivates extending CloudGuard beyond a Detect/Analyse/Respond narrative to explicit outcome, recovery, and continual-improvement records.

MITRE ATT&CK v19.x (April 2026) maintains a versioned corpus of techniques, software, groups, campaigns, data components, Detection Strategies, and Analytics. CloudGuard V4 therefore treats behavior/technique coverage as a first-class dimension rather than relying only on malware names or IOC lists.

OASIS STIX 2.1 provides a standard language for cyber-threat and observable information, while TAXII 2.1 defines a REST-based protocol for exchanging cyber-threat intelligence. CloudGuard V4 does not implement live STIX/TAXII ingestion yet, but those standards are the preferred interoperability target instead of inventing a proprietary external CTI representation.

CISA's Known Exploited Vulnerabilities catalog is an authoritative source of vulnerabilities known to be exploited in the wild and is available in JSON and JSON Schema formats. V4 therefore includes an `AUTHORITATIVE` source class while still requiring controlled review/regression before a threat-intelligence update activates in the reference implementation.

## 2. Architectural correction: confidence is not authority

The V3 engine computes a transparent risk score and a heuristic `evidence_strength`. V4 preserves V3 for demonstration compatibility but explicitly separates:

- detector/model probability,
- evidence completeness,
- evidence source agreement,
- deterministic policy decision,
- human disposition.

A high model probability does not grant response capability. Authorization depends on verified evidence, response impact, and required oversight.

## 3. Threat-intelligence feedback without autonomous policy mutation

The central V4 feedback rule is:

> **New malware, vulnerability, IOC, TTP, or field intelligence may automatically trigger analysis and testing, but may not automatically rewrite active threat knowledge, detection policy, or response authorization.**

Threat updates carry immutable version identity, source trust, provenance, rationale, affected detections/playbooks, regression evidence, and independent review. Untrusted-source changes and security-control weakening require an additional independent reviewer.

## 4. Human-in-the-loop as a risk-tier control

V4 replaces the V3 binary rule ('disable account requires analyst') with impact tiers:

1. Observe/read — no human approval by default.
2. Enrich/query — no human approval by default.
3. Temporary containment — review unless a bounded emergency playbook applies.
4. Account/privilege change — named human approval.
5. Destructive/business-critical — dual independent approval.

This is a reference policy model; a production system would bind these decisions to real IAM/SOAR permissions and protected identity/trust-domain infrastructure.

## 5. Auditability

V3's recommendation hash remains useful as a checksum, but a checksum alone does not prove the integrity of the complete decision history. V4 adds canonical hash-linked JSONL records for:

- threat-database updates,
- threat detections,
- response policy decisions,
- field feedback,
- response outcomes.

The local chain is tamper-evident, not tamper-proof. A privileged party that can replace the full log can recompute the local history. The production direction is signed records/checkpoints plus independently protected WORM/object-lock or transparency storage.

## 6. Field issues and assurance closure

V4 classifies operational feedback conservatively into threat-database, detection, telemetry, policy, response, recovery, false-positive, or review-required gaps. The result is a review workflow, not an automatically deployed fix.

The target lifecycle is:

`field incident -> evidence/provenance -> gap classification -> update proposal -> attack/benign/evasion regression -> independent review -> versioned activation -> monitored outcome -> recurrence analysis`

This deliberately mirrors verification closure: `field bug -> counterexample -> check/test -> regression -> coverage closure`.

## 7. Research questions

1. Does a deterministic response-policy boundary reduce unsafe cloud actions compared with confidence-threshold automation?
2. How much analyst workload can be reduced while preserving acceptable false-block and escalation rates?
3. Does source-labelled threat intelligence plus independent activation reduce the risk of poisoning-induced detector/policy changes?
4. Can ATT&CK-oriented behavior coverage predict detection gaps better than IOC-only coverage?
5. Does field-issue-driven regression reduce recurrence without materially increasing false positives?
6. How much audit/provenance infrastructure is necessary before a SOC can independently reproduce why an action or threat-database update occurred?

## 8. Claim boundary

CloudGuard V4 is a runnable assurance/governance reference implementation. It does not claim production detection accuracy, calibrated threat probabilities, live CTI integration, prompt-injection-proof RAG, production SOAR enforcement, cryptographically trusted telemetry, or measured SOC productivity improvement. Those are future controlled-evaluation targets.

## References

- NIST. *SP 800-61 Rev. 3: Incident Response Recommendations and Considerations for Cybersecurity Risk Management: A CSF 2.0 Community Profile*. April 2025. https://csrc.nist.gov/pubs/sp/800/61/r3/final
- MITRE ATT&CK. *Updates — April 2026 / ATT&CK v19*. https://attack.mitre.org/resources/updates/updates-april-2026/
- MITRE ATT&CK. *Version History*. https://attack.mitre.org/resources/versions/
- OASIS. *STIX Version 2.1*. https://www.oasis-open.org/standard/stix-version-2-1/
- OASIS. *TAXII Version 2.1*. https://www.oasis-open.org/standard/taxii-version-2-1/
- CISA. *Known Exploited Vulnerabilities Catalog*. https://www.cisa.gov/known-exploited-vulnerabilities-catalog
