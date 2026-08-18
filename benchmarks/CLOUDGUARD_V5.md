# CloudGuard V5 Predictive Threat Intelligence Protocol

## Purpose

CloudGuard V5 extends the V4 assurance-governed SOC architecture with a measurable predictive layer for attack-state estimation, next-technique forecasting, organization-specific exposure ranking, attack-path simulation, pre-emption proposals, and governed champion/challenger learning.

V5 does **not** treat a forecast as authorization. Every effectful pre-emption proposal remains subject to the CloudGuard V4 deterministic response policy and HITL requirements.

## Research questions

1. Can provenance-aware attack-state estimation improve next-technique forecasting over a transition-only baseline?
2. Does organization-specific reachability, criticality, KEV, EPSS-style exploit likelihood, and control effectiveness improve attack-path prioritization?
3. Can minimum-impact preventive controls reduce simulated path risk with less operational cost than broad reactive containment?
4. Can quarantine and champion/challenger governance prevent low-quality or poisoned field feedback from silently degrading the active predictor?

## Implemented reference components

### Threat-state estimator

`ThreatStateEstimator` combines verified/unverified observations, evidence weights, recency, and source observability. Missing telemetry reduces the returned assurance level. The technique distribution is an evidence-weighted state estimate, not a calibrated attacker-intent probability.

### Transition baseline

`TechniqueTransitionModel` learns transparent empirical transition frequencies from historical technique sequences. This is intentionally dependency-light and provides a reproducible baseline for later HMM, sequence-model, or graph-model comparisons.

### Exposure graph

`ExposureGraph` represents identities, roles, workloads, secrets, storage, reachability edges, vulnerabilities, and technique-specific exposure. Local priority combines reachability, target criticality, exploit-likelihood input, KEV status, and control weakness. It is a prioritization score, not a breach probability.

### Attack-path forecasting

`AttackPathForecaster` combines transition evidence with local exposure to rank likely next techniques and beam-search attack paths. Unreachable techniques receive zero local exposure priority.

### Pre-emption optimizer

`PreemptionOptimizer` ranks one- or two-control combinations by projected path-risk reduction minus operational cost. The output is a proposal ranking only. `control_to_response_request` and `gate_preemption` deliberately route effectful proposals back through the V4 policy boundary.

### Learning quarantine

`TrainingQuarantine` prevents field data from automatically entering production training. Untrusted discovery data requires confirmed labels, at least two independent corroborations, and analyst approval before becoming training-eligible.

### Champion/challenger governance

`ModelGovernanceRegistry` requires independent promotion review plus reference thresholds for Recall@3, Brier score, false-pre-emption rate, old-threat retention, poisoning/adversarial suite success, and shadow-mode evidence. These thresholds are prototype defaults and require empirical justification before production deployment.

## Evaluation metrics

The implementation provides reference helpers for:

- next-technique Recall@K,
- Brier score,
- expected calibration error,
- pre-emption lead time.

Future empirical studies should additionally measure attack-path recall, false pre-emption, operational cost, old-threat retention, poisoning resistance, and analyst override/acceptance rates.

## Threat and safety invariants

- model/forecast scores cannot grant response authority;
- missing observability must reduce forecast assurance;
- KEV and EPSS-style signals are inputs, not complete risk scores;
- untrusted CTI cannot directly update the active model;
- field incidents enter training quarantine first;
- production models are not mutated online;
- challenger promotion requires independent review and regression evidence;
- high-impact pre-emption remains subject to V4 HITL/dual approval.

## Runnable fixture

```bash
python -m pip install -e .
assurance-cloudguard-predict profile examples/cloudguard_v5_profile.json
```

## Claim boundary

This implementation does not yet demonstrate calibrated next-technique probabilities, live ATT&CK/STIX/TAXII/KEV/EPSS ingestion, trained HMM/Transformer/GNN models, real enterprise attack-path accuracy, production SOAR pre-emption, or empirical security improvement. It is a transparent baseline and governance substrate for controlled research.
