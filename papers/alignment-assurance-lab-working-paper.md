# Alignment Assurance Lab

## Trace-Based Property Monitoring and Coverage for Tool-Using AI Agents

**Author:** Srinivasa J. Dinakar  
**Date:** August 18, 2026  
**Status:** Working paper and prototype report; not peer reviewed

## Abstract

Tool-using AI agents plan across multiple steps, invoke external actions, delegate work, retain state, and may continue operating after conditions change. Evaluations based only on final task success can miss unsafe intermediate behavior, unauthorized actions, absent evidence, self-approval, or failure to stop. This working paper proposes the Alignment Assurance Lab, a verification-driven environment that represents agent-safety claims as executable trace properties, runs adversarial scenarios, measures property coverage, and returns counterexample locations when a property fails. The accompanying Python prototype evaluates four properties: authorization before sensitive action, evidence before high-risk action, independent approval, and shutdown compliance. Two repository tests demonstrate a fully covered passing trace and a negative trace that triggers all four violation types. These are unit-level checks, not evidence of broad alignment or predictive validity. The paper defines a research program for comparing trace-based assurance with outcome-only evaluation across agents, tools, and environments.

**Keywords:** agentic AI, safety evaluation, runtime verification, trace monitoring, assurance cases, coverage, counterexamples, tool use

## 1. Motivation

An agent may produce an acceptable final answer while taking an unsafe route. It may call a sensitive tool without authorization, act before collecting evidence, allow the same role to propose and approve a high-impact action, or continue after a shutdown command. Final-answer grading compresses these distinctions into a single outcome and can hide the location and cause of failure.

Pre-silicon verification offers a useful analogy. Complex systems are not validated by a small set of expected outputs alone; engineers define properties, generate scenarios, monitor behavior, measure coverage, and preserve counterexamples. The Alignment Assurance Lab adapts these practices to externally observable agent traces.

This approach is an assurance layer, not a proof of alignment. It can test stated properties under observed conditions, but it cannot guarantee safe behavior outside the property set, instrumentation boundary, or evaluated environment.

## 2. Research questions

1. Which safety and governance claims can be represented as observable temporal properties?
2. Do trace monitors find failures that outcome-only evaluators miss?
3. Can property coverage distinguish “no violation observed” from “property never exercised”?
4. How well do properties transfer across models, scaffolds, tools, and versions?
5. Do minimized counterexample traces improve debugging, training, or release decisions?
6. Which properties remain robust under deceptive, stochastic, or self-modifying behavior?

## 3. Assurance model

The proposed workflow has five elements.

### 3.1 Properties

Safety requirements are expressed as invariants, ordering constraints, authorization rules, forbidden transitions, or bounded-response conditions. Each property must identify the observable events and data required for evaluation.

### 3.2 Scenarios

Scenarios vary goals, tool availability, permissions, evidence quality, delegation, memory, environmental feedback, and adversarial instructions. Constrained-random generation should be combined with targeted tests for known hazards.

### 3.3 Monitors

A monitor evaluates the event trace during or after execution and records the exact event associated with a violation. High-impact properties may also become runtime gates that block an action pending approval.

### 3.4 Coverage

Coverage records which properties and hazard conditions were actually exercised. A passing trace with uncovered properties is weaker evidence than a passing trace that activated every relevant antecedent.

### 3.5 Counterexamples

A failing trace is retained as reproducible evidence. Future work should minimize traces, classify root causes, and use the corpus for regression testing.

## 4. Runnable reference prototype

The [Trace Assurance Engine](../src/assurance_portfolio/trace_assurance.py) implements four deterministic properties.

### Authorization before sensitive action

When an event is marked sensitive, the action name must have appeared in a prior authorization event.

### Evidence before high-risk action

A sensitive, high-risk action must follow a recorded evidence event.

### Independent approval

When an approver is present, the proposer and approver must differ.

### Shutdown compliance

After a shutdown event, only audit or status events may occur.

The engine returns:

- an overall pass or fail result,
- every detected violation,
- the exact event index and explanation,
- covered properties, and
- uncovered properties.

The implementation is intentionally small enough for direct inspection.

## 5. Example trace

The [positive example](../examples/agent_trace.json) records evidence, authorizes account disablement, executes the sensitive action with separate proposer and approver roles, issues shutdown, and records an audit event. This ordering satisfies all four implemented properties.

A negative test performs an unauthorized high-risk delete action without prior evidence, assigns the same agent as proposer and approver, issues shutdown, and then performs another action. The engine reports all four violation categories.

## 6. Prototype evidence

The repository contains two focused unit tests for the trace engine:

- a passing trace that covers every implemented property without violations, and
- a failing trace whose detected-property set equals all four property names.

This establishes deterministic behavior for those examples. It does not establish low false-positive rates, adversarial robustness, cross-model generalization, or a relationship between property violations and real-world harm.

## 7. Proposed evaluation

### 7.1 Experimental systems

Evaluate several tool-using agent scaffolds with simulated and real tools for files, messaging, web actions, code execution, and delegated tasks. Instrument each run with a common event schema.

### 7.2 Conditions

Compare:

1. final-outcome evaluation only,
2. trace monitoring without coverage,
3. trace monitoring with coverage reporting, and
4. trace monitoring with runtime gates for selected properties.

### 7.3 Task design

Include benign and adversarial tasks that vary:

- authorization scope,
- reversible and irreversible actions,
- evidence availability,
- conflicting instructions,
- delegation boundaries,
- shutdown timing,
- tool errors, and
- long-horizon state changes.

### 7.4 Metrics

- violation recall and precision against human-labeled traces,
- unsafe-action prevention rate,
- false blocks on benign actions,
- property and hazard coverage,
- time to localize a failure,
- counterexample reproducibility,
- transfer across models and scaffolds,
- runtime overhead, and
- reviewer agreement.

Outcome success and safety should be reported separately.

## 8. Relationship to risk management

The NIST AI Risk Management Framework organizes work around Govern, Map, Measure, and Manage. Trace properties and coverage can provide concrete measurement evidence for selected system-level requirements, while counterexamples support incident analysis and management. The NIST Generative AI Profile also emphasizes independent measurement, continuous monitoring, documented review, and deployment thresholds.

The Alignment Assurance Lab does not claim compliance with these frameworks. It offers a technical mechanism that could support a broader governance and assurance process.

## 9. Related work

OpenAgentSafety evaluates agents interacting with realistic tools across benign and adversarial tasks, highlighting the need for system-level safety evaluation. TRAJECT-Bench emphasizes trajectory-aware diagnostics for tool choice, arguments, and ordering rather than final answers alone. Contemporary trace-based assurance work proposes metrics for contract compliance, termination reliability, containment, and governance outcomes across agent traces.

The proposed contribution is a compact property-and-coverage abstraction inspired by verification practice: explicit requirements, monitors, covered and uncovered properties, and event-indexed counterexamples that can become regression tests.

## 10. Limitations

The current property language is hard-coded and not temporal-logic complete. Evidence is represented as a Boolean state rather than source quality or relevance. Authorizations do not expire, include scope, or bind to parameters. Independent approval is checked only by identifier inequality. The shutdown rule has no latency bound. Event integrity is assumed, and an agent could evade monitoring through uninstrumented channels.

The prototype also lacks scenario generation, trace minimization, a coverage dashboard, model integrations, and a labeled benchmark.

## 11. Next steps

1. Define a versioned event and property schema.
2. Add scoped authorization, evidence provenance, parameter binding, and bounded temporal rules.
3. Build a scenario generator with reproducible seeds.
4. Minimize and persist counterexample traces.
5. Compare trace-based and outcome-only evaluators on labeled tasks.
6. Add release gates that require both passing properties and minimum coverage.
7. Study transfer across agents, models, and tool environments.

## 12. Conclusion

Agent safety depends on what happens during execution, not only on the final answer. Executable trace properties, coverage, and counterexamples provide a disciplined way to state and test limited assurance claims. The current engine is a small reference implementation; the research value will depend on broader evaluation, calibrated properties, trustworthy instrumentation, and transparent limitations.

## References

1. National Institute of Standards and Technology. (2023). [Artificial Intelligence Risk Management Framework 1.0](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf).
2. National Institute of Standards and Technology. (2024). [Artificial Intelligence Risk Management Framework: Generative Artificial Intelligence Profile](https://doi.org/10.6028/NIST.AI.600-1).
3. Vijayvargiya, S. et al. (2025). [OpenAgentSafety: A Comprehensive Framework for Evaluating Real-World AI Agent Safety](https://arxiv.org/abs/2507.06134).
4. He, P. et al. (2025). [TRAJECT-Bench: A Trajectory-Aware Benchmark for Evaluating Agentic Tool Use](https://arxiv.org/abs/2510.04550).
5. [A Trace-Based Assurance Framework for Agentic AI Systems](https://arxiv.org/abs/2603.18096) (2026).

## Suggested citation

Dinakar, S. J. (2026). *Alignment Assurance Lab: Trace-Based Property Monitoring and Coverage for Tool-Using AI Agents*. Working paper and prototype report.
