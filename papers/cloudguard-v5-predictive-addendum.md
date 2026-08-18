# CloudGuard V5 Addendum: Predictive Threat Intelligence and Pre-emptive Defense

**Status:** Working research addendum; not peer reviewed.

## Motivation

CloudGuard V4 established governed threat knowledge, deterministic response policy, HITL, auditability, and a field-feedback loop. V5 asks a different question: can the system forecast likely attack progression early enough to propose a smaller, lower-impact preventive action before the attack reaches a higher-value target?

The design deliberately avoids the claim that an AI model can infer attacker intent. It estimates current attack state, ranks likely next techniques and paths, conditions those rankings on local exposure, and proposes controls whose authority is still decided by V4.

## Literature-grounded design direction

The V5 architecture is motivated by recent work on provenance-based attack-stage estimation, HMM/sequence/graph attack-path forecasting, ATT&CK-aligned cyber knowledge graphs, vulnerability exploit likelihood, continual learning under concept drift, and poisoning-resistant cyber-agent knowledge. The repository literature review concluded that the strongest defensible architecture is not an LLM-only predictor. It is a fusion of temporal state estimation, graph/exposure context, structured CTI, calibrated evaluation, and deterministic response governance.

ATT&CK remains the behavioral ontology rather than being treated as a probabilistic transition model. Historical incident sequences provide transition evidence. Local IAM/reachability and vulnerability context then determine whether a globally plausible technique is relevant to the organization.

## Implemented V5 baseline

The runnable reference implementation adds:

- evidence-weighted threat-state estimation;
- explicit observability coverage and missing-source reporting;
- empirical next-technique transition baseline;
- organization-specific exposure graph;
- KEV and EPSS-style exploit-likelihood inputs;
- beam-ranked attack paths;
- minimum-impact pre-emption ranking;
- V4 policy/HITL routing for effectful proposals;
- training-data quarantine;
- champion/challenger model governance;
- Recall@K, Brier, calibration-error, and lead-time metrics.

## Safety design

Forecasts never create authority. A high-ranked technique or attack path may increase investigation or preparedness priority, but cannot independently revoke credentials, isolate production, change cloud policy, or modify the production predictor.

Field incidents do not update the active model directly. Training candidates are quarantined until provenance and labels are acceptable. Untrusted discovery data requires stronger corroboration and analyst approval. Challenger promotion is independent of the proposer and requires calibration, false-pre-emption, historical-retention, poisoning-suite, and shadow-mode gates.

## Evaluation plan

The first empirical study should compare:

1. transition-frequency baseline;
2. provenance/state-aware forecast;
3. provenance + local exposure forecast;
4. later HMM/sequence/graph models under the same evaluation protocol.

Primary outcomes should include next-technique Recall@1/3, path recall, Brier score, expected calibration error, forecast lead time, false pre-emption rate, projected intervention cost, old-threat retention, and poisoning-suite robustness.

Temporal splits should be preferred over random train/test leakage when studying attack progression. Prediction records should be committed before future labels/outcomes are revealed, reusing the repository's evaluation-integrity principles.

## Novelty boundary

Predictive cyber defense, ATT&CK mapping, attack graphs, and continual IDS learning are established research areas. V5 does not claim novelty for any of those ideas alone.

The proposed research contribution is the combination of predictive threat-state/path modeling with verification-style assurance: organization-specific exposure, explicit uncertainty, minimum-impact counterfactual defense proposals, deterministic authorization, HITL, governed learning, poisoning resistance, reproducible evaluation, and closed-loop prediction-versus-outcome evidence.

## Limitations

The current implementation is a transparent reference baseline. It has no live CTI connector, no trained HMM/Transformer/GNN, no calibrated enterprise forecast probabilities, no production cloud digital twin, no real SOAR actuator, and no evidence yet that predictive pre-emption improves security outcomes. Those claims require controlled experiments and deployment studies.
