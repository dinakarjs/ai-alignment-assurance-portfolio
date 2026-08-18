# CloudGuard V5 — Predictive Threat Intelligence & Pre-emptive Defense

**Status:** Runnable predictive reference layer on top of CloudGuard V4  
**Theme:** attack-state estimation, next-technique forecasting, local exposure, attack-path ranking, minimum-impact pre-emption, and governed learning

## Design principle

> **Predict early, but never let prediction become authority.**

CloudGuard V5 estimates likely attack progression and proposes preventive controls. V4 remains the authorization boundary for effectful response and HITL.

## Architecture

```text
ATT&CK / CTI / KEV / EPSS-style signals / internal incidents
                         |
                         v
                Trust & provenance gate
                         |
                         v
                  Threat knowledge
                         |
            +------------+------------+
            |                         |
            v                         v
   Incident provenance          Local exposure graph
   observations / state       IAM / reachability / CVEs
            |                         |
            v                         |
    Threat State Estimator            |
            |                         |
            +------------+------------+
                         v
               Technique Forecast
                         |
                         v
                Attack Path Ranker
                         |
                         v
               Pre-emption Optimizer
             risk reduction vs cost
                         |
                         v
                 Proposed Control
                         |
                         v
                  V4 Policy Gate
               ALLOW/BLOCK/ESCALATE
                         |
                         v
                 HITL where required
                         |
                         v
                    Outcome
                         |
                         v
             Prediction vs actual path
                         |
                         v
                Training Quarantine
                         |
                         v
                Challenger model
                         |
             calibration / retention /
             poison / shadow evidence
                         |
                         v
                Independent promotion
```

## What is implemented

- `ThreatStateEstimator`: evidence-weighted, recency-aware current technique state.
- `Observability`: expected versus available telemetry; missing sources lower assurance.
- `TechniqueTransitionModel`: transparent empirical next-technique baseline from historical sequences.
- `ExposureGraph`: identities/assets/roles/reachability/vulnerabilities and technique-specific exposure.
- `VulnerabilityExposure`: EPSS-style exploit likelihood plus KEV boolean as separate inputs.
- `AttackPathForecaster`: exposure-aware next-technique and multi-step beam-path ranking.
- `PreemptionOptimizer`: ranks low-cost controls by projected path-risk reduction.
- `gate_preemption`: routes proposals into CloudGuard V4 deterministic policy rather than self-authorizing.
- `TrainingQuarantine`: provenance/label/corroboration gate for field data.
- `ModelGovernanceRegistry`: champion/challenger promotion gates.
- Metrics: Recall@K, Brier score, expected calibration error, and pre-emption lead time.

## Safety boundaries

### Forecast score is not authorization

An attack forecast can prioritize investigation and propose a preventive control. It cannot itself disable identities, isolate production, change IAM, or promote a new model.

### ATT&CK/transition scores are not attacker intent

The transition baseline models observed technique succession. It does not infer intent or guarantee the next action.

### Local exposure is not breach probability

Reachability, criticality, KEV, EPSS-style exploit likelihood, and control weakness produce a transparent priority score. Empirical calibration is still required.

### Missing observability reduces assurance

A forecast made without expected endpoint/network/cloud telemetry must explicitly carry lower assurance rather than silently producing a high-confidence result.

### Learning is governed

New incidents enter quarantine. Untrusted discovery data requires confirmed labels, two independent corroborations, and analyst approval before it is eligible for challenger training. The production model is never mutated online by this reference implementation.

### Challenger promotion is independent

Promotion requires a reviewer other than the proposer and passes reference gates for:

- next-technique Recall@3;
- Brier score;
- false pre-emption rate;
- old-threat retention;
- poisoning/adversarial suite;
- minimum shadow-mode evidence.

## Runnable example

```bash
python -m pip install -e .
assurance-cloudguard-predict profile examples/cloudguard_v5_profile.json
```

## Versioned controls

- `checks/cloudguard-predictive-controls/5.0.0.json`
- `policies/cloudguard-predictive/1.0.0.json`
- `benchmarks/CLOUDGUARD_V5.md`
- `papers/cloudguard-v5-predictive-addendum.md`

## Next empirical milestone

The next research step should compare the transparent transition baseline against HMM/sequence/graph forecasting on temporally split historical attack traces, then measure whether local exposure improves ranking and whether proposed controls provide useful lead time at acceptable false-pre-emption cost.

## Claim boundary

This is not a production predictive SOC. It does not yet provide live CTI synchronization, calibrated enterprise forecasts, HMM/Transformer/GNN inference, a complete digital twin, production SOAR integration, or demonstrated security improvement. The architecture and controls are designed so those experiments can be added without weakening the V4 authority boundary.
