# Multi-Agent Verification Copilot

**Status:** Applied research prototype with deterministic baseline and optional model-backed roles  
**Theme:** AI-assisted verification with auditable role separation and tool-grounded acceptance

## Motivation

Complex verification work requires specification analysis, assertion design, scenario generation, coverage planning, failure triage, and sign-off evidence. A single general-purpose assistant can blur these responsibilities and amplify unchecked mistakes. This project explores a role-separated copilot in which generation, adversarial review, deterministic verification, and human acceptance remain distinguishable stages.

## Implemented V5 architecture

V5 now contains two deliberately separate paths.

### Deterministic baseline

[`verification_copilot.py`](../src/assurance_portfolio/verification_copilot.py) provides a dependency-free baseline with:

- requirement-quality review,
- fail-safe complete-match grammar translation,
- draft assertion generation,
- pattern-specific scenarios and coverage goals,
- independent artifact review, and
- provenance through matched pattern and translation parameters.

### Model-backed path

[`agentic_verification.py`](../src/assurance_portfolio/agentic_verification.py) adds:

- a model-backed generator role,
- a separate model-backed adversarial reviewer role,
- strict JSON contracts,
- reviewer outcomes `ACCEPT_FOR_TOOL_CHECK`, `REVISE`, and `ABSTAIN`,
- recorded generator/reviewer backend identity, and
- deterministic validation as an acceptance gate.

The repository includes an OpenAI Responses API backend for live use and a scripted backend for reproducible tests. Distinct calls/objects provide workflow separation, but this does not guarantee statistical independence when both roles use the same model family.

## Deterministic verification gate

[`sva_validation.py`](../src/assurance_portfolio/sva_validation.py) separates:

- shallow dependency-free structural validation, and
- an optional Verilator adapter that submits a standalone assertion probe to a concrete installed tool.

A candidate reaches `accepted_for_human_review=true` only if the model reviewer sends it to the tool check and the configured validator returns `VALID`. This state means the candidate may proceed to expert review; it is not design sign-off.

## Benchmark evidence

[`verification_benchmark.py`](../src/assurance_portfolio/verification_benchmark.py) runs a labelled synthetic trace benchmark for bounded-response and prohibition requirements and reports defect detection, accuracy, and false positives.

The [`benchmarks/rtl`](../benchmarks/rtl) fixtures add a small request/grant design plus a labelled late-grant mutation. V5 does not yet claim behavioural detection of that RTL defect; simulator/formal execution remains the next benchmark step.

## Safety and assurance relevance

The workflow makes several failure modes observable instead of implicit:

- unsupported semantics can fall back or trigger reviewer revision,
- model outputs are not treated as executable evidence by default,
- reviewer disagreement/abstention becomes a human-escalation signal,
- tool acceptance is recorded separately from model plausibility, and
- deterministic baseline output remains available for comparison.

The same separation can be applied to agentic AI assurance: proposer, reviewer, policy monitor, execution gate, and human authority need not be collapsed into one model response.

## Controlled evaluation plan

The intended experimental comparison is:

1. deterministic grammar baseline,
2. single model-generated artifact,
3. generator + reviewer model calls without deterministic gating,
4. generator + independent reviewer + deterministic verification-tool gate.

Use compact public RTL blocks with seeded mutations, independently authored reference properties, labelled traces, and deliberately ambiguous/paraphrased requirements.

Measure:

- requirement recall/precision,
- assertion tool acceptance,
- semantic correctness against reference traces,
- vacuity where measurable,
- seeded-defect detection,
- false positives,
- fallback/abstention behaviour,
- human review effort,
- latency and model/tool cost.

## Current trust boundary

V5 proves that the orchestration, role contracts, acceptance gate, Verilator integration, and synthetic benchmark run as software. It does **not** establish that model-backed generation is better than the deterministic baseline, that Verilator acceptance equals semantic correctness, or that the seeded RTL mutation is detected in simulation/formal execution.

## Key risks

- Generator and reviewer may share model-level blind spots.
- Tool acceptance can validate syntax/support without validating design intent.
- Public toy RTL may overstate transfer to SoC-scale verification.
- Seeded defects can differ from organic specification or implementation failures.
- Human review may shift rather than reduce total effort.

## Working paper

[Role-Separated Multi-Agent Verification Copilot: A Traceable Workflow for AI-Assisted Pre-Silicon Verification](../papers/multi-agent-verification-copilot-working-paper.md) documents the V5 architecture, current evidence, limitations, and next controlled experiment.
