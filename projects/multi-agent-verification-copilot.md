# Multi-Agent Verification Copilot

**Status:** Applied research concept  
**Theme:** AI-assisted verification with auditable role separation

## Motivation

Complex verification work requires specification analysis, test planning, assertion design, stimulus generation, coverage review, and failure triage. A single general-purpose assistant can blur these responsibilities and amplify unchecked mistakes. This project explores a multi-agent copilot in which specialized agents propose artifacts while independent agents challenge, verify, and trace them to requirements.

## Proposed architecture

- **Specification analyst:** extracts requirements, interfaces, assumptions, and ambiguities.
- **Test-plan agent:** maps requirements to scenarios, checkers, and coverage goals.
- **Assertion agent:** proposes safety and liveness properties.
- **Adversarial reviewer:** searches for vacuous assertions, missing cases, and conflicting assumptions.
- **Coverage analyst:** identifies untested requirements and weak evidence.
- **Orchestrator:** maintains provenance, disagreement, approval gates, and human escalation.

Every output is linked to its source requirement and carries confidence, assumptions, and review status. No agent is permitted to approve its own work.

## Safety relevance

The same architecture can evaluate agentic AI systems. Separation of proposer and verifier roles reduces correlated error; traceability reveals unsupported claims; and disagreement becomes a signal for human review rather than something to average away.

## First test

Use a compact protocol or control-block specification. Compare:

1. a single-agent workflow,
2. a multi-agent workflow without independence constraints, and
3. the proposed role-separated workflow.

Measure requirement recall, assertion correctness, vacuity, test-plan coverage, defect discovery, false positives, and human review time.

## Key risks

- Multiple agents may share the same model-level blind spots.
- Plausible documentation can create false confidence.
- Orchestration may add cost without improving defect discovery.
- Automated scoring may reward superficial traceability.

The experiment must therefore use seeded defects, independently authored reference properties, and explicit abstention/error analysis.

## Intended outputs

- Role and message schemas
- Traceability graph format
- Evaluation dataset with seeded defects
- Baseline comparison
- Failure taxonomy and research report


## Runnable prototype

A dependency-free reference implementation is available in [`verification_copilot.py`](../src/assurance_portfolio/verification_copilot.py). It converts requirements into traceable draft assertions, scenarios, and coverage goals, then applies a separate ambiguity review. The [example requirements](../examples/requirements.json) include both precise and deliberately weak specifications.
