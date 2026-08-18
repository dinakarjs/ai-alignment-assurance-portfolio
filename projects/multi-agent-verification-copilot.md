# Multi-Agent Verification Copilot

**Status:** Applied research prototype with deterministic baseline, optional model-backed roles, behavioral RTL mutation proof, and repeated multi-family evaluation  
**Theme:** AI-assisted verification with auditable role separation, tool-grounded acceptance, and measured behavioral outcomes

## Motivation

Complex verification work requires specification analysis, assertion design, scenario generation, coverage planning, failure triage, and sign-off evidence. A single assistant can blur these responsibilities and amplify unchecked mistakes. This project separates generation, adversarial review, deterministic verification, behavioral execution, and human acceptance.

## Implemented architecture

### Deterministic baseline

[`verification_copilot.py`](../src/assurance_portfolio/verification_copilot.py) provides fail-safe complete-match grammar translation, draft assertion generation, pattern-specific scenarios/coverage goals, independent artifact review, and matched-pattern provenance.

### Model-backed path

[`agentic_verification.py`](../src/assurance_portfolio/agentic_verification.py) adds a model-backed generator, separate adversarial reviewer, strict JSON contracts, reviewer outcomes `ACCEPT_FOR_TOOL_CHECK` / `REVISE` / `ABSTAIN`, recorded backend identity, and deterministic validation as an acceptance gate.

The repository includes an OpenAI Responses API backend for live use and scripted backends for reproducible tests. Distinct calls provide workflow separation but do not guarantee statistical independence when the same model family is used.

## Deterministic validation and behavioral evidence

[`sva_validation.py`](../src/assurance_portfolio/sva_validation.py) distinguishes structural checks from real Verilator assertion/tool acceptance.

[`rtl_behavioral.py`](../src/assurance_portfolio/rtl_behavioral.py) provides the original request/grant behavioral proof with Icarus Verilog.

V8 broadens behavioral evaluation through [`corpus_benchmark.py`](../src/assurance_portfolio/corpus_benchmark.py) to three requirement families:

- bounded response: request → grant within four cycles,
- prohibition: grant must remain low during reset,
- immediate implication: request high implies busy high.

Each family has a known-good RTL implementation and one labelled mutation. A compile/tool failure never counts as successful mutation detection.

## Four workflow conditions

[`corpus_evaluation.py`](../src/assurance_portfolio/corpus_evaluation.py) evaluates the same RTL corpus under:

1. deterministic grammar baseline,
2. single-model generation,
3. generator + reviewer,
4. generator + reviewer + structural tool gate.

Reviewer `REVISE` / `ABSTAIN` outcomes stop execution and are measured as escalation rather than assertion failure.

## Repeated-trial metrics

V8 aggregates repeated trials using:

- generation-failure rate,
- reviewer escalation rate,
- behavioral-execution rate,
- full-correct rate: good RTL passes and mutation is detected,
- mutation-detection rate among executed cases,
- false-positive rate on known-good RTL,
- mean elapsed wall-clock time.

The scripted/offline corpus deliberately includes a too-strict bounded-response candidate and a reviewer escalation so the measurement system exercises both false-positive and abstention behavior. These scripted results validate evaluation plumbing, not model quality.

Live trials use the same evaluator and record evidence kind, model label, and prompt version. Repeated live observations still do not justify a superiority claim without a larger independent corpus and expert review.

## Evidence layers

The project deliberately keeps these claims separate:

1. deterministic reference output,
2. model proposal/review,
3. standalone assertion tool acceptance,
4. behavioral RTL execution,
5. repeated comparative evaluation.

A candidate reaching `accepted_for_human_review=true` is not design sign-off. Behavioral success on this small corpus is not evidence of general SoC-scale correctness.

## Current trust boundary

V8 demonstrates that the role contracts, acceptance gates, Verilator integration, multiple behavioral mutation pairs, and repeated four-condition evaluation run as software. It does **not** establish general natural-language-to-SVA correctness, model superiority, production EDA equivalence, or SoC-scale transfer.

The next defensible research step is a larger independently authored mutation corpus, repeated live-model trials with fixed configuration and usage telemetry, and blinded expert review of semantic correctness and engineering effort.

## Benchmark documentation

- [V7 controlled evaluation](../benchmarks/CONTROLLED_EVALUATION.md)
- [V8 multi-family corpus](../benchmarks/V8_CORPUS.md)

## Working paper

[Role-Separated Multi-Agent Verification Copilot: A Traceable Workflow for AI-Assisted Pre-Silicon Verification](../papers/multi-agent-verification-copilot-working-paper.md) documents the architecture and research framing. The V8 benchmark documentation is the authoritative description of the current expanded corpus and repeated-trial protocol.
