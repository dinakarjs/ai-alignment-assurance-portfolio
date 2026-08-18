# CloudGuard AI — Assurance-Governed Cloud Incident Response

**Status:** Runnable V3 educational baseline plus V4 assurance-governed reference architecture  
**Theme:** Threat intelligence, explainable detection, policy-gated response, human oversight, auditability, and closed-loop security improvement

## Source and scope

CloudGuard AI originated in a Responsible AI and Explainability workshop project by Kenneth Amanchukwu, John Nova, and Srinivasa Dinakar. The original scenario follows a suspicious-account sequence involving impossible travel, privilege escalation, failed logins, malicious-IP evidence, and a high-risk response recommendation.

The repository now deliberately separates two implementations:

- **V3 compatibility baseline** — [`cloudguard.py`](../src/assurance_portfolio/cloudguard.py), a transparent five-signal synthetic scoring demo that reproduces the workshop result and demonstrates human approval.
- **V4 assurance architecture** — [`cloudguard_v4.py`](../src/assurance_portfolio/cloudguard_v4.py), which treats AI analysis as advisory and surrounds response and threat-database evolution with deterministic policy, versioning, HITL, regression evidence, and hash-linked audit history.

Neither implementation is a production SOC, trained threat detector, SIEM replacement, or autonomous-response product.

## Brutal review of V3

V3 is useful educationally but was not sufficient as an architecture for an autonomous security analyst:

1. The risk score is based on synthetic fixed weights rather than a trained or calibrated detector.
2. `evidence_strength` is heuristic; it must not be interpreted as calibrated model confidence.
3. A SHA-256 recommendation checksum is not, by itself, a tamper-evident audit system because recommendation, checksum, and decision can all be replaced together.
4. Human oversight is binary: only account disablement explicitly requires an analyst.
5. There is no threat-intelligence trust model, threat-database lifecycle, versioning, regression gate, or rollback mechanism.
6. There is no distinction between threat knowledge, detector evidence, model hypothesis, response policy, and authorization.
7. There is no field-issue loop for false negatives, false positives, telemetry gaps, policy gaps, ineffective response, or failed recovery.
8. The larger course-report architecture describes anomaly detection, RAG/LLM analysis, and controlled response, but the runnable V3 code intentionally implements only a narrow deterministic slice.

V4 addresses the architectural control gaps without pretending that a real anomaly detector, production RAG stack, SOAR integration, or cloud IAM enforcement has already been built.

## V4 design principle

> **The AI/SOC model may propose a threat hypothesis or response, but it is not the authorization boundary.**

Model probability, generated rationale, retrieved threat intelligence, or severity labels do not independently grant permission to revoke tokens, disable identities, isolate workloads, or perform destructive actions.

## V4 architecture

```text
Authoritative / verified / internal / untrusted CTI
                    |
                    v
             Threat Intake
      source identity / trust / digest
                    |
                    v
       Versioned Threat Knowledge
                    |
           coverage / gap analysis
                    |
                    v
Cloud telemetry -> Detection / correlation
                    |
                    v
              Evidence objects
        verified / freshness / digest
                    |
                    v
              AI SOC analyst
             [untrusted planner]
                    |
          hypothesis / response proposal
                    |
                    v
          Deterministic Policy Gate
     evidence / impact tier / oversight
                    |
          +---------+----------+
          |         |          |
        ALLOW     BLOCK     ESCALATE
          |                    |
          |                    v
          |                Human review
          |             / dual approval
          v
      SOAR / cloud action
          |
          v
       Outcome / Recovery
          |
          v
      Field Issue Analysis
          |
          +--> threat-db proposal
          +--> detector proposal
          +--> policy/playbook proposal
          +--> telemetry/recovery proposal
                    |
                    v
        Regression + independent review
                    |
                    v
          Versioned activation / rollback
```

## Five control planes

### 1. Threat knowledge plane

Threat records are immutable by `(threat_id, version)` and carry:

- source identity,
- source trust class,
- source reference/digest,
- severity,
- threat-change class,
- techniques,
- observables,
- affected assets,
- optional first/last-seen metadata,
- optional source confidence.

Trust classes are:

- `AUTHORITATIVE`
- `VERIFIED_CTI`
- `INTERNAL_CONFIRMED`
- `UNTRUSTED_DISCOVERY`

Untrusted intelligence may trigger analysis and a proposal, but it cannot activate a production threat update by itself.

### 2. Detection plane

A detected threat is represented separately from the threat database. Detection records bind:

- incident and asset,
- exact threat version,
- detector ID/version/digest,
- verified evidence objects,
- mapped techniques,
- optional model hypothesis/probability,
- evidence completeness,
- source agreement.

This intentionally separates **model assessment** from **evidence** and **authorization**.

### 3. Assurance plane

[`CloudGuardPolicyEngine`](../src/assurance_portfolio/cloudguard_v4.py) uses deterministic impact tiers rather than model confidence:

| Tier | Class | Default oversight |
| --- | --- | --- |
| 0 | Observe/read | autonomous reference action |
| 1 | Enrich/query | autonomous reference action |
| 2 | Temporary containment | policy/HITL review unless bounded emergency playbook applies |
| 3 | Account/privilege change | named human approval |
| 4 | Destructive/business-critical | two independent reviewers/trust domains |

Effectful responses cannot rely on unverified required evidence.

### 4. Human governance plane

Human review is a first-class object tied to the exact incident/action. Review records carry:

- reviewer identity,
- reviewer trust domain,
- disposition,
- rationale,
- evidence reviewed,
- optional second reviewer and trust domain.

A human disposition is not allowed to silently rewrite the policy result. Production exceptions should remain explicit exception records.

Threat-database updates also require independent review. A proposer cannot approve their own update. Updates sourced from `UNTRUSTED_DISCOVERY`, or updates that weaken an existing control, require a second independent reviewer.

### 5. Audit and feedback plane

[`CloudGuardAuditStore`](../src/assurance_portfolio/cloudguard_v4.py) records canonical JSONL events with sequence number, previous-record hash, record hash, UTC timestamp, record type, and payload.

Supported audit categories include:

- threat-database update,
- threat detection,
- response policy decision,
- human review/decision when emitted by the integrating system,
- response outcome,
- field feedback.

The local chain is tamper-evident rather than tamper-proof. Production use should add protected key custody, signed records/checkpoints, WORM/object-lock storage, or an independent transparency/audit service.

## Threat-database update lifecycle

The reference lifecycle is:

```text
PROPOSED
  -> AUTOMATED_VALIDATION
  -> HIL_REVIEW_PENDING
  -> APPROVED
  -> REGRESSION_VALIDATED
  -> ACTIVE
  -> SUPERSEDED / ROLLED_BACK
```

The current in-memory registry enforces the security-critical subset:

- immutable version identity,
- named proposer and rationale,
- proposer/approver separation,
- extra reviewer for untrusted-source or weakening changes,
- passing regression evidence before activation,
- explicit authorized rollback.

A production implementation should persist lifecycle state in a protected configuration service and verify signed regression artifacts before activation.

## Threat feedback loop

A field incident is classified conservatively. V4 can distinguish:

- `THREAT_DB_GAP`
- `DETECTION_GAP`
- `TELEMETRY_GAP`
- `POLICY_GAP`
- `RESPONSE_GAP`
- `RECOVERY_GAP`
- `FALSE_POSITIVE`
- `REVIEW_REQUIRED`

The feedback engine **proposes** follow-up work and never activates a detector, policy, playbook, or threat entry automatically.

The intended loop is:

```text
new threat / field incident
  -> evidence and source validation
  -> ATT&CK / behavior mapping
  -> coverage gap
  -> threat/detection/policy/playbook proposal
  -> attack + benign + evasion regression
  -> independent human review
  -> versioned activation
  -> field outcome monitoring
  -> recurrence / false-positive feedback
```

This is the cybersecurity analogue of a verification flow: **field bug -> counterexample -> checker/test -> regression -> coverage closure**.

## Threat-intelligence interoperability target

V4 does not implement live network ingestion. The preferred integration direction is to normalize external cyber-threat intelligence using STIX 2.1 and exchange it through TAXII 2.1-compatible connectors where appropriate. CISA KEV and MITRE ATT&CK are examples of high-value structured sources; source-specific adapters must retain provenance rather than flattening every feed into the same trust level.

## Versioned artifacts

- [`schemas/cloudguard-threat/1.0.0.json`](../schemas/cloudguard-threat/1.0.0.json)
- [`policies/cloudguard-response/1.0.0.json`](../policies/cloudguard-response/1.0.0.json)
- [`checks/cloudguard-controls/4.0.0.json`](../checks/cloudguard-controls/4.0.0.json)

## Runnable workflows

Install:

```bash
python -m pip install -e .
```

Original workshop-compatible V3 demo:

```bash
assurance-demo cloudguard examples/cloudguard_incident.json
```

V4 threat update with independent review and regression evidence:

```bash
assurance-cloudguard --audit-log /tmp/cloudguard-audit.jsonl \
  threat-update examples/cloudguard_v4_threat_update.json
```

Record a threat detection:

```bash
assurance-cloudguard --audit-log /tmp/cloudguard-audit.jsonl \
  record-detection examples/cloudguard_v4_detection.json \
  --threat-db-digest 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
```

Policy-gated response with HITL:

```bash
assurance-cloudguard --audit-log /tmp/cloudguard-audit.jsonl \
  response examples/cloudguard_v4_response.json
```

Field feedback:

```bash
assurance-cloudguard --audit-log /tmp/cloudguard-audit.jsonl \
  feedback examples/cloudguard_v4_field_issue.json
```

Response outcome:

```bash
assurance-cloudguard --audit-log /tmp/cloudguard-audit.jsonl \
  record-outcome examples/cloudguard_v4_outcome.json
```

Audit-chain verification:

```bash
assurance-cloudguard --audit-log /tmp/cloudguard-audit.jsonl verify-audit
```

## Evidence/claim boundary

V4 demonstrates a **reference assurance control plane**, not production cybersecurity performance. It does not currently demonstrate:

- a trained anomaly detector,
- calibrated threat probabilities,
- live STIX/TAXII ingestion,
- live CISA/MITRE/vendor synchronization,
- prompt-injection-resistant RAG,
- production SOAR/cloud API interception,
- production IAM/capability issuance,
- cryptographically trusted telemetry instrumentation,
- signed remote attestation,
- empirical false-positive/false-negative improvements,
- deployed SOC productivity gains.

Those require separately designed integrations and controlled evaluation.

## Research artifacts

- [CloudGuard AI course report — repository edition](../papers/cloudguard-ai-course-report.md)
- [CloudGuard AI research presentation notes](../papers/cloudguard-ai-research-presentation.md)
- [CloudGuard V4 assurance addendum](../papers/cloudguard-v4-assurance-addendum.md)
- [CloudGuard V4 protocol](../benchmarks/CLOUDGUARD_V4.md)
