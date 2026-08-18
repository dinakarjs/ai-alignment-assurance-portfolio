# Multi-Agent Verification Copilot

**Status:** Applied research concept with deterministic reference prototype  
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

No role is intended to approve its own work. In the full research architecture, model-backed roles will remain subject to deterministic tool checks and human acceptance.

## Runnable V4 baseline

The dependency-free reference implementation in [`verification_copilot.py`](../src/assurance_portfolio/verification_copilot.py) is deliberately **not** presented as a deployed multi-agent LLM system. It provides a deterministic baseline with separate components for:

- requirement-quality review,
- explicit-grammar artifact generation,
- independent artifact review, and
- orchestration into a traceable `VerificationArtifact`.

A requirement is marked **SUPPORTED** only if the entire normalized text matches one of the supported grammars. Partial semantic matches fall back rather than discarding unsupported clauses. Supported patterns generate pattern-specific scenarios and coverage goals, and the output records pattern provenance plus extracted translation parameters.

The current generator still produces draft SVA-style strings. It does not parse RTL, infer clock/reset context, invoke simulation/formal tools, or establish semantic correctness.

## Safety relevance

The same architecture can evaluate agentic AI systems. Separation of proposer and verifier roles can reduce some correlated workflow errors; traceability reveals unsupported claims; and disagreement can become a signal for human review rather than something to average away. Role labels alone do not guarantee statistical or model-level independence.

## First controlled evaluation

Use a compact public protocol or control block and compare:

1. a single-agent workflow,
2. a multi-agent workflow without independence constraints, and
3. a role-separated workflow with deterministic verification-tool feedback.

Measure requirement recall, assertion parse/elaboration success, semantic correctness, vacuity, seeded-defect detection, false positives, coverage, human review time, and cost.

## Key risks

- Multiple agents may share the same model-level blind spots.
- Plausible documentation can create false confidence.
- Natural-language parsers may silently omit qualifiers unless fail-safe matching is enforced.
- Orchestration may add cost without improving defect discovery.
- Automated scoring may reward superficial traceability.

The experiment must therefore use seeded defects, independently authored reference properties, executable tool checks, and explicit abstention/error analysis.

## Intended outputs

- Role and message schemas
- Traceability graph format
- Model-backed generator/reviewer adapters
- Parser/simulator/formal assertion checks
- Evaluation dataset with seeded defects
- Baseline comparison and failure taxonomy

## Working paper

[Role-Separated Multi-Agent Verification Copilot: A Traceable Workflow for AI-Assisted Pre-Silicon Verification](../papers/multi-agent-verification-copilot-working-paper.md) is a working paper and prototype report. It separates implemented deterministic behavior from the proposed model-backed comparative study.
