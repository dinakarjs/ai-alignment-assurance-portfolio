# Role-Separated Multi-Agent Verification Copilot

## A Traceable Workflow for AI-Assisted Pre-Silicon Verification

**Author:** Srinivasa J. Dinakar  
**Date:** August 18, 2026  
**Status:** Working paper and prototype report; not peer reviewed

## Abstract

Pre-silicon verification translates design intent into test plans, assertions, scenarios, coverage goals, and evidence for sign-off. Large language models can assist this translation, but fluent generation can silently omit qualifiers, blur proposal and approval roles, or produce plausible but invalid assertions. This working paper presents a role-separated verification-copilot architecture and a deterministic reference prototype that preserves requirement identifiers, reviews requirement quality, generates draft SVA-style artifacts for a deliberately small grammar, records generation provenance, and independently reviews generated artifacts. V4 tightens fail-safe behavior by requiring the complete normalized requirement to match a supported grammar; recognizable substrings followed by unsupported clauses fall back instead of being labeled supported. Supported patterns also generate pattern-specific scenarios and coverage goals. The prototype remains a baseline rather than a model-backed agent system or EDA-integrated verifier. A controlled evaluation is proposed using seeded RTL/specification defects, independently authored reference properties, executable assertion checks, and single-agent versus role-separated comparisons.

**Keywords:** pre-silicon verification, multi-agent systems, SystemVerilog Assertions, requirements traceability, verification planning, independent review, large language models

## 1. Motivation

Verification engineers must interpret specifications, resolve ambiguity, design scenarios, write checkers and assertions, define coverage, and investigate failures. An error in requirement interpretation can propagate into every downstream artifact. Generative models can accelerate drafting, but fluency is not evidence of correctness.

The central hypothesis is that role separation plus executable verification-tool feedback can make AI-assisted verification more auditable. Proposal, requirement review, artifact review, tool validation, and human acceptance should be distinguishable stages rather than one opaque model response.

## 2. Research questions

1. Does role separation improve requirement recall and defect discovery compared with a single-agent workflow?
2. Does independent review reduce vacuous, syntactically invalid, or semantically incorrect assertions?
3. Can requirement identifiers and provenance survive the full specification-to-verification workflow?
4. Which disagreements predict genuine specification defects or missing test intent?
5. Does the additional orchestration cost reduce or increase total human review time?
6. How often does conservative abstention outperform partial semantic matching that silently drops qualifiers?

## 3. Proposed architecture

The full research architecture assigns bounded responsibilities.

- **Specification analyst:** extracts requirements, interfaces, assumptions, timing constraints, and ambiguities.
- **Test-plan agent:** maps requirements to nominal, boundary, error, concurrency, reset, and adversarial scenarios.
- **Assertion agent:** drafts safety and liveness properties with explicit assumptions.
- **Adversarial reviewer:** searches for vacuity, missing antecedents, weak timing, conflicting assumptions, and unsupported signals.
- **Coverage analyst:** identifies requirements without measurable evidence and proposes functional or assertion coverage.
- **Orchestrator:** preserves identifiers, artifacts, review findings, approval state, and human escalation.
- **Deterministic verifier:** parses/elaborates assertions and executes simulation/formal checks against reference or generated traces.

No model-backed role should approve its own output. Human experts remain responsible for acceptance and sign-off.

## 4. Runnable V4 reference prototype

The repository prototype implements a deterministic slice of this architecture in [`verification_copilot.py`](../src/assurance_portfolio/verification_copilot.py). It is intentionally not described as a deployed multi-agent LLM system.

For each requirement, it:

1. normalizes whitespace,
2. preserves the requirement identifier,
3. performs independent requirement-quality review,
4. attempts translation using a small explicit grammar,
5. labels generation `SUPPORTED` only when the complete normalized requirement matches,
6. records the matched pattern and extracted translation parameters,
7. generates pattern-specific scenarios and a requirement-linked coverage goal,
8. performs a separate artifact review, and
9. combines findings into a traceable `VerificationArtifact`.

Supported grammar families currently cover bounded response, alternate no-later-than phrasing, conditional bounded response, prohibition, immediate implication, and persistence-until-release.

A requirement such as:

```text
grant shall assert within 4 cycles after request unless reset or abort
```

is deliberately `FALLBACK`, even though its prefix resembles a supported bounded-response requirement. This prevents unsupported trailing semantics from being silently discarded.

## 5. Assertion and scenario semantics

Generated assertions remain drafts. The generator currently assumes `@(posedge clk)` and does not infer clock domains, reset semantics, hierarchy, signal width, unknown-state behavior, or design-specific assumptions. Those limitations are explicit.

V4 makes scenario generation pattern-aware rather than reusing a generic nominal/boundary/violation template. For example, a prohibition requirement generates scenarios for the safe hold condition and prohibited assertion; a bounded response generates early, exact-boundary, and late/missing response cases.

This improves traceability, but it still does not establish assertion correctness.

## 6. Prototype evidence

The repository regression suite now checks:

- successful complete matching for supported grammars,
- fail-safe fallback for a partial semantic match with an unsupported trailing clause,
- pattern-specific scenarios and coverage goals,
- generation provenance,
- independent artifact-review findings, and
- deterministic fallback behavior.

These tests validate implementation behavior only. They do not establish semantic SVA correctness, requirement recall, productivity improvement, or superiority of role-separated agents.

## 7. Proposed controlled evaluation

Compare:

1. **Single-agent baseline:** one model produces and reviews artifacts.
2. **Unconstrained multi-agent baseline:** multiple model calls collaborate without independence rules.
3. **Role-separated workflow:** bounded generator/reviewer roles plus deterministic verification-tool feedback and human escalation.
4. **Deterministic baseline:** the current V4 grammar-driven implementation.

### Dataset

Use compact public RTL blocks or protocols with:

- independently authored reference requirements,
- reference assertions and expected traces,
- seeded specification and RTL defects,
- precise and deliberately ambiguous/paraphrased requirement variants,
- reset, timing, concurrency, and error-handling cases.

### Metrics

- requirement recall and precision,
- assertion parse and elaboration success,
- semantic correctness against reference traces,
- vacuity rate,
- seeded-defect detection,
- false-positive rate,
- functional and assertion coverage,
- fallback/abstention calibration,
- provenance completeness,
- human review time,
- inference/tool-execution cost.

## 8. Threats to validity

Multiple agents may share model-level blind spots and create correlated errors. Role labels alone do not guarantee independence. Regex/grammar baselines can reject valid paraphrases or overfit curated examples. Automated judges can reward plausible syntax without semantic validity. Public blocks do not represent full SoC complexity. Seeded defects may differ from organic specification failures.

These risks motivate parser/simulator/formal scoring, mutation testing, independently authored reference artifacts, blinded human review, and explicit error analysis.

## 9. Related work

AssertLLM processes specification documents and generates assertions from natural language and waveform information, demonstrating both the promise and difficulty of document-level assertion generation. VERT and AssertionBench contribute datasets for evaluating LLM-generated assertions. CoverAssert adds a coverage-guided feedback loop and reports that single-pass generation can miss functional intent. The Accellera UVM standard provides the broader reusable verification methodology into which a future copilot must integrate.

The proposed contribution is complementary: explicit proposer-reviewer separation, preserved requirement provenance, conservative fallback on unsupported semantics, deterministic tool verification, and evaluation of the whole requirements-to-evidence workflow.

## 10. Limitations and next milestone

The current prototype contains no model calls, RAG, agent framework, UVM integration, RTL parser, simulator, or formal engine. It is the deterministic baseline against which those additions should be evaluated.

The next milestone is therefore not another regex extension. It is:

1. model-backed generator and reviewer adapters,
2. parser/elaboration validation for generated SVA,
3. a small public RTL target with seeded defects and reference properties,
4. simulation/formal feedback into the workflow,
5. controlled single-agent versus role-separated evaluation.

## 11. Conclusion

A useful verification copilot must do more than generate plausible code. It must preserve design intent, expose unsupported semantics, separate proposal from review, and produce executable evidence that engineers can inspect. V4 strengthens the deterministic baseline by making supported parsing fail-safe and scenario generation pattern-aware; the research value now depends on connecting model-backed roles to actual verification tools and measuring outcomes.

## References

1. Yan, Z. et al. (2024). [AssertLLM: Generating Hardware Verification Assertions from Design Specifications](https://arxiv.org/abs/2411.14436).
2. Menon, A. et al. (2025). [VERT: A SystemVerilog Assertion Dataset to Improve Hardware Verification with LLMs](https://openreview.net/forum?id=rZmQ2z7MPA).
3. Wang, Y. et al. (2026). [CoverAssert: Iterative LLM Assertion Generation Driven by Functional Coverage](https://arxiv.org/abs/2604.06607).
4. Shahidzadeh, M. et al. (2024). [Automatic High-Quality Verilog Assertion Generation through Subtask-Focused Fine-Tuned LLMs and Iterative Prompting](https://arxiv.org/abs/2411.15442).
5. Accellera Systems Initiative. [Universal Verification Methodology](https://www.accellera.org/downloads/standards/uvm).

## Suggested citation

Dinakar, S. J. (2026). *Role-Separated Multi-Agent Verification Copilot: A Traceable Workflow for AI-Assisted Pre-Silicon Verification*. Working paper and prototype report.
