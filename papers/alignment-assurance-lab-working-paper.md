# Alignment Assurance Lab

## Trace-Based Property Monitoring and Coverage for Tool-Using AI Agents

**Author:** Srinivasa J. Dinakar  
**Date:** August 18, 2026  
**Status:** Working paper and prototype report; not peer reviewed

## Abstract

Tool-using AI agents plan across multiple steps, invoke external actions, retain state, and may continue operating after conditions change. Final-outcome grading can miss unsafe intermediate behavior such as acting without authorization, acting without fresh evidence, self-approval, or failure to stop. The Alignment Assurance Lab adapts verification concepts—properties, monitors, coverage, and counterexamples—to ordered agent traces. The V4 deterministic prototype uses transaction-scoped, consumable, optionally expiring authorization and evidence grants; explicit high-risk classification checks; independent proposer/approver identity requirements; shutdown monitoring; and PASS/FAIL/INCONCLUSIVE results based on violations and property-exercise coverage. V4 also closes a classification bypass by evaluating high-risk controls even when an action is incorrectly marked non-sensitive. The implementation remains a compact assurance monitor, not a proof of alignment or a production authorization system. A broader research program is proposed around trusted event schemas, authorization authority, evidence provenance, adversarial scenario generation, counterexample minimization, and comparison with outcome-only evaluation.

**Keywords:** agentic AI, safety evaluation, runtime verification, trace monitoring, assurance cases, coverage, counterexamples, tool use

## 1. Motivation

An agent may produce an acceptable final answer while taking an unsafe route. It may invoke a sensitive tool without a valid authorization grant, act before collecting relevant evidence, omit proposer or approver identity, allow self-approval, or continue after shutdown. These failures are trajectory properties, not merely final-answer properties.

Pre-silicon verification provides a useful analogy: requirements become executable checks, scenarios activate those checks, coverage reveals what was or was not exercised, and failures are retained as counterexamples. The Alignment Assurance Lab applies the same discipline to observable agent traces.

## 2. Implemented V4 assurance model

The current [`trace_assurance.py`](../src/assurance_portfolio/trace_assurance.py) monitor evaluates five explicit properties.

### 2.1 Authorization before sensitive action

Sensitive actions require a prior matching authorization grant. Action identifiers are normalized. Grants may be scoped by `transaction_id`/`action_id`, optionally expire after a configured event count, and are consumed when used. Unscoped grants match only unscoped actions.

### 2.2 Evidence before high-risk action

High-risk actions require a prior matching evidence grant under the same scope and lifecycle rules.

### 2.3 High-risk classification consistency

An event marked `high_risk=true` must also be classified sensitive. If it is not, V4 records a classification violation **and continues to run the stronger authorization/evidence/approval checks**, so clearing the sensitive flag cannot bypass high-risk controls.

### 2.4 Independent approval

A high-risk action must record both proposer and approver identities. The normalized identities must differ. Missing proposer and missing approver are distinct violations.

### 2.5 Shutdown compliance

After shutdown, only audit and status events are permitted.

## 3. Assurance result and coverage semantics

The engine returns:

- `PASS` when no violation is observed and every required property is exercised,
- `FAIL` when one or more violations are observed,
- `INCONCLUSIVE` when no violation is observed but one or more required properties were not exercised.

The current coverage signal is intentionally described as **property-exercise coverage**. It does not yet provide functional cross coverage, state-transition coverage, assertion antecedent/vacuity coverage, mutation coverage, or hazard-pair coverage.

## 4. Trust boundary

The monitor validates trace relationships, not the truth of the trace itself. It currently assumes that authorization/evidence events are trustworthy observations.

It does **not** yet establish that:

- the actor issuing authorization has policy authority for that action,
- evidence came from an approved source,
- evidence quality/relevance satisfies a policy threshold,
- a grant is bound to every security-relevant action parameter,
- event ordering and contents are tamper-resistant,
- uninstrumented side channels do not exist.

These are first-class next-stage requirements. Treating the event stream as a trust root without stating this boundary would overclaim what the prototype proves.

## 5. Prototype evidence

The regression suite covers positive and negative behavior including:

- transaction-scoped authorization/evidence,
- single-use consumption,
- grant expiry,
- unscoped-versus-scoped mismatch,
- missing proposer and approver,
- normalized self-approval detection,
- high-risk/non-sensitive misclassification,
- shutdown behavior, and
- INCONCLUSIVE results for uncovered properties.

These tests establish deterministic behavior for the specified cases. They do not establish adversarial robustness, predictive validity, calibrated false-positive/false-negative rates, or transfer across model families and agent frameworks.

## 6. Research questions

1. Which safety/governance claims can be represented as observable trace properties?
2. Do trace monitors identify failures that final-outcome evaluators miss?
3. Can property/hazard coverage distinguish weak evidence from meaningful negative evidence?
4. How should authorization authority and evidence provenance be represented and verified?
5. How robust are monitor results to incomplete, delayed, corrupted, or adversarial instrumentation?
6. Can minimized counterexamples improve debugging, training, or release decisions?

## 7. Proposed controlled evaluation

Evaluate several tool-using agent configurations with simulated filesystem, messaging, code, and delegation tools. Compare:

1. final-outcome evaluation only,
2. trace monitoring without coverage,
3. trace monitoring with property/hazard coverage,
4. trace monitoring with runtime gates for selected irreversible actions.

Use benign and adversarial tasks that vary authorization scope, evidence quality, conflicting instructions, delegation boundaries, shutdown timing, tool errors, and long-horizon state changes.

### Metrics

- violation recall/precision against human-labeled traces,
- unsafe-action prevention rate,
- false blocks on benign actions,
- property and hazard coverage,
- time to localize failures,
- counterexample reproducibility,
- runtime overhead,
- transfer across models/scaffolds,
- reviewer agreement.

## 8. Relationship to governance

The approach can produce concrete measurement evidence for selected system-level requirements and can support incident analysis, audit, and release gating. It does not itself establish compliance with NIST AI RMF, ISO/IEC 42001, or any regulatory framework; those frameworks require broader organizational controls, risk management, documentation, and governance.

## 9. Limitations and next milestone

The current property language is hard-coded and not temporal-logic complete. The monitor has no policy authority service, cryptographic event integrity, scenario generator, trace minimizer, coverage dashboard, model integration, or labeled benchmark.

The next milestone should add:

1. a versioned typed event/property schema,
2. trusted-principal and authorization-policy rules,
3. evidence-source/provenance requirements,
4. parameter-bound grants,
5. reproducible adversarial scenario generation,
6. counterexample minimization/persistence,
7. comparison against outcome-only evaluators.

## 10. Conclusion

Agent safety depends on what happens during execution, not only on the final answer. V4 provides a small auditable baseline that distinguishes scoped and stale authorization/evidence, makes missing identities visible, prevents a high-risk classification bypass, and separates FAIL from INCONCLUSIVE coverage gaps. Its value is as a disciplined reference monitor and research scaffold; broader assurance claims require trustworthy instrumentation, richer policies, and empirical evaluation.

## References

1. National Institute of Standards and Technology. (2023). [Artificial Intelligence Risk Management Framework 1.0](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf).
2. National Institute of Standards and Technology. (2024). [Artificial Intelligence Risk Management Framework: Generative Artificial Intelligence Profile](https://doi.org/10.6028/NIST.AI.600-1).
3. Vijayvargiya, S. et al. (2025). [OpenAgentSafety: A Comprehensive Framework for Evaluating Real-World AI Agent Safety](https://arxiv.org/abs/2507.06134).
4. He, P. et al. (2025). [TRAJECT-Bench: A Trajectory-Aware Benchmark for Evaluating Agentic Tool Use](https://arxiv.org/abs/2510.04550).
5. [A Trace-Based Assurance Framework for Agentic AI Systems](https://arxiv.org/abs/2603.18096) (2026).

## Suggested citation

Dinakar, S. J. (2026). *Alignment Assurance Lab: Trace-Based Property Monitoring and Coverage for Tool-Using AI Agents*. Working paper and prototype report.
