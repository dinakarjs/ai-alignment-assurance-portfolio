# CloudGuard V4 Assurance Protocol

CloudGuard V4 is a reference control plane for assurance-governed cloud incident response. It is designed to test whether threat-knowledge updates and effectful response proposals remain constrained by versioning, evidence, deterministic policy, human oversight, regression evidence, and audit history.

## 1. Safety claims tested by the reference implementation

V4 tests the following bounded claims:

1. An AI/model-generated hypothesis does not itself authorize an effectful action.
2. Required evidence for effectful actions must be present and verified.
3. Account/privilege changes require human approval.
4. Destructive or business-critical actions require two independent reviewers/trust domains.
5. Threat records are immutable by `(threat_id, version)`.
6. A threat-update proposer cannot approve their own change.
7. Untrusted-source and control-weakening threat updates require a second independent reviewer.
8. Threat updates cannot activate without passing regression evidence.
9. Detected-threat records bind threat version, detector version/digest, evidence, and active threat-database identity.
10. Field feedback can generate proposals but never auto-activate a detector, policy, playbook, or threat record.
11. Hash-linked audit history detects local record modification.
12. Authorized rollback is explicit rather than indistinguishable from silent downgrade.

These are reference-control claims, not claims of production compromise prevention.

## 2. Threat source classes

| Class | Intended use | Activation rule |
| --- | --- | --- |
| `AUTHORITATIVE` | CISA/MITRE/vendor authority-class sources after connector validation | independent review + regression |
| `VERIFIED_CTI` | vetted CTI provider/feed | independent review + regression |
| `INTERNAL_CONFIRMED` | confirmed internal SOC/IR evidence | independent review + regression |
| `UNTRUSTED_DISCOVERY` | web/community/model-discovered candidate intelligence | second independent reviewer + regression |

No source class bypasses regression before activation in the reference registry.

## 3. Response impact tiers

| Tier | Meaning | Reference decision pattern |
| --- | --- | --- |
| 0 | Observe | ALLOW when required evidence is valid |
| 1 | Enrich | ALLOW when required evidence is valid |
| 2 | Temporary containment | ESCALATE unless bounded emergency policy or reviewed action |
| 3 | Account/privilege change | one named human approval |
| 4 | Destructive/business-critical | two independent reviewers/trust domains |

Model probability and LLM reasoning are intentionally excluded from authorization logic.

## 4. Threat update regression evidence

Activation requires a `RegressionEvidence` record with:

- regression ID,
- at least one passing attack case,
- benign-case results,
- zero unexpected failures,
- false-positive delta,
- optional coverage additions.

A future production gate should additionally verify the cryptographic identity and provenance of each regression artifact rather than trusting declared counts.

## 5. Field feedback classifications

The deterministic classifier supports:

- `THREAT_DB_GAP`
- `DETECTION_GAP`
- `TELEMETRY_GAP`
- `POLICY_GAP`
- `RESPONSE_GAP`
- `RECOVERY_GAP`
- `FALSE_POSITIVE`
- `REVIEW_REQUIRED`

The classifier does not claim to infer complete incident root cause. Its output is a conservative workflow-routing suggestion.

## 6. Audit evidence

`CloudGuardAuditStore` emits canonical JSONL records containing:

- audit schema version,
- sequence,
- record type,
- UTC recording time,
- previous-record hash,
- payload,
- record hash.

Current CI exercises:

1. `THREAT_DB_UPDATE`
2. `THREAT_DETECTION`
3. `RESPONSE_POLICY_DECISION`
4. `FIELD_FEEDBACK`
5. `RESPONSE_OUTCOME`
6. complete hash-chain verification

Production extension should add signer identity, key-managed digital signatures, periodic Merkle checkpoints, and an independently protected external/WORM anchor.

## 7. Required negative tests

A credible CloudGuard release should retain negative tests for at least:

- unverified evidence,
- missing evidence,
- self-approval,
- same-domain dual approval,
- untrusted CTI without second reviewer,
- security-control weakening without second reviewer,
- no regression evidence,
- duplicate threat version,
- audit-record modification,
- threat absent from database,
- known threat missed by detector,
- policy failure after correct detection,
- ineffective response,
- ineffective recovery,
- false-positive incident.

Future adversarial tests should also cover RAG/CTI poisoning, prompt injection in threat reports, stale IOC replay, detector-evasion mutations, source-identity spoofing, model-induced severity inflation, malicious threat-update proposals, and compromised audit/approval paths.

## 8. Coverage model

Do not collapse security into one headline percentage. Track dimensions independently:

- threat-knowledge coverage,
- ATT&CK behavior/technique coverage,
- telemetry coverage,
- detection coverage,
- policy coverage,
- response/playbook coverage,
- recovery coverage,
- HITL review coverage,
- threat-update regression coverage,
- audit-evidence completeness.

A dimension can be `COVERED`, `PARTIAL`, `GAP`, or `NOT_TESTED`.

## 9. Continuous-improvement lifecycle

```text
new threat / field incident
  -> normalize source + provenance
  -> map behavior / ATT&CK / observables
  -> compare against active coverage
  -> classify gap
  -> propose threat/detector/policy/playbook/telemetry/recovery update
  -> run attack + benign + evasion regression
  -> independent human review
  -> versioned activation
  -> observe outcomes
  -> detect recurrence / false positives
  -> repeat
```

The loop is governed: **feedback proposes; humans and deterministic release gates activate**.

## 10. External standards / source direction

The integration direction is consistent with:

- NIST SP 800-61 Rev. 3 for incorporating incident detection, response, and recovery into cybersecurity risk management;
- MITRE ATT&CK's versioned technique, software, campaign, detection-strategy, analytic, and data-component corpus;
- STIX 2.1 for cyber-threat/observable representation;
- TAXII 2.1 for threat-intelligence exchange;
- CISA KEV as an authoritative input for known exploited vulnerabilities.

The repository does not currently implement live ingestion from those services.

## 11. Empirical evaluation roadmap

A future controlled study should compare:

1. V3 fixed-score baseline,
2. detector-only triage,
3. detector + model analyst,
4. detector + model analyst + deterministic policy gate,
5. full V4 with governed threat-update feedback.

Metrics should include false-positive/false-negative rate, threat-detection latency, response latency, analyst override rate, unsafe-action prevention, escalation rate, regression recurrence, coverage-gap closure, response effectiveness, recovery effectiveness, audit completeness, and human-review time/agreement.

No such production-scale empirical result is claimed by the current repository.
