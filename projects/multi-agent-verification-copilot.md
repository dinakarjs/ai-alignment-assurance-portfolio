# Multi-Agent Verification Copilot

**Status:** Applied research prototype with deterministic baseline, optional model-backed roles, and behavioral RTL mutation proof  
**Theme:** AI-assisted verification with auditable role separation and tool-grounded acceptance

## Motivation

Complex verification work requires specification analysis, assertion design, scenario generation, coverage planning, failure triage, and sign-off evidence. A single assistant can blur these responsibilities and amplify unchecked mistakes. This project separates generation, adversarial review, deterministic verification, behavioral execution, and human acceptance.

## Implemented V6 architecture

### Deterministic baseline

[`verification_copilot.py`](../src/assurance_portfolio/verification_copilot.py) provides:

- requirement-quality review,
- fail-safe complete-match grammar translation,
- draft assertion generation,
- pattern-specific scenarios and coverage goals,
- independent artifact review, and
- matched-pattern/translation provenance.

### Model-backed path

[`agentic_verification.py`](../src/assurance_portfolio/agentic_verification.py) adds:

- model-backed generator role,
- separate adversarial reviewer role,
- strict JSON contracts,
- reviewer outcomes `ACCEPT_FOR_TOOL_CHECK`, `REVISE`, `ABSTAIN`,
- recorded backend identity, and
- deterministic validation as an acceptance gate.

The repository includes an OpenAI Responses API backend for live use and scripted backends for reproducible tests. Distinct calls provide workflow separation but do not guarantee statistical independence when the same model family is used.

## Deterministic validation and behavioral evidence

[`sva_validation.py`](../src/assurance_portfolio/sva_validation.py) distinguishes structural checks from real Verilator assertion/tool acceptance.

V6 adds [`rtl_behavioral.py`](../src/assurance_portfolio/rtl_behavioral.py), which compiles and simulates two request/grant RTL fixtures using Icarus Verilog:

- `handshake_good.sv` must satisfy `grant shall assert within 4 cycles after request`.
- `handshake_late_bug.sv` contains a deliberately seeded late-grant mutation and must violate that requirement.

The benchmark is successful only when the good design passes and the mutation fails. Compile errors or missing tools are not counted as defect detection. CI runs this as a dedicated behavioral-proof job.

## Evidence layers

The project deliberately keeps four claims separate:

1. deterministic grammar/reference output,
2. model proposal/review,
3. standalone tool acceptance of an assertion,
4. behavioral RTL execution against labelled mutations.

A candidate reaching `accepted_for_human_review=true` is not design sign-off. Behavioral success on one labelled fixture is not evidence of general SoC-scale correctness.

## Current benchmark evidence

The repository now includes:

- a synthetic labelled trace benchmark for bounded response and prohibition,
- a real Verilator tool-validation CI job,
- labelled request/grant RTL fixtures,
- a real Icarus Verilog behavioral benchmark for good-versus-mutated RTL.

The next experimental question is no longer whether the plumbing runs. It is whether model-backed role separation improves verification outcomes relative to deterministic and single-model baselines.

## Controlled evaluation plan

Compare:

1. deterministic grammar/reference-property baseline,
2. single model-generated artifact,
3. model generator + independent reviewer,
4. model generator + reviewer + deterministic tool/behavioral feedback.

Measure:

- assertion parse/tool acceptance,
- behavioral mutation detection,
- false positives,
- vacuity where measurable,
- abstention/escalation behavior,
- human review effort,
- latency and model/tool cost.

## Current trust boundary

V6 proves that the role contracts, acceptance gates, external Verilator integration, synthetic benchmarks, and one behavioral RTL mutation test run as software when CI passes. It does **not** establish that model-backed generation is better than the deterministic baseline, that one seeded defect generalizes to proprietary SoCs, or that tool acceptance equals design intent.

## Working paper

[Role-Separated Multi-Agent Verification Copilot: A Traceable Workflow for AI-Assisted Pre-Silicon Verification](../papers/multi-agent-verification-copilot-working-paper.md) documents the architecture, evidence layers, limitations, and controlled-evaluation plan.
