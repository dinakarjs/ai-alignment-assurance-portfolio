# Role-Separated Multi-Agent Verification Copilot

## A Traceable Workflow for AI-Assisted Pre-Silicon Verification

**Author:** Srinivasa J. Dinakar  
**Date:** August 18, 2026  
**Status:** Working paper and prototype report; not peer reviewed

## Abstract

Pre-silicon verification translates design intent into test plans, assertions, scenarios, coverage goals, and evidence for sign-off. Large language models can assist this translation, but a single assistant may generate plausible artifacts without detecting ambiguity, preserving traceability, or separating proposal from approval. This working paper presents a role-separated verification-copilot architecture in which specialized agents propose artifacts and an independent review role challenges their assumptions before human acceptance. The accompanying dependency-free Python prototype converts natural-language requirements into requirement-linked draft assertions, nominal, boundary, and adversarial scenarios, coverage goals, and ambiguity findings. The current implementation is intentionally narrow: it demonstrates provenance and review separation rather than correct SystemVerilog Assertion generation or production EDA integration. A controlled evaluation is proposed to compare a single-agent baseline, an unconstrained multi-agent workflow, and a role-separated workflow using seeded defects, independently authored reference properties, and explicit abstention analysis.

**Keywords:** pre-silicon verification, multi-agent systems, SystemVerilog Assertions, requirements traceability, verification planning, independent review, large language models

## 1. Motivation

Verification engineers must interpret specifications, resolve ambiguity, design scenarios, write checkers and assertions, define coverage, and investigate failures. These activities are coupled: an error in requirement interpretation can propagate into every downstream artifact. Generative models can accelerate drafting, but fluency is not evidence of correctness.

The central hypothesis is that role separation can make AI-assisted verification more auditable. Instead of allowing one model invocation to interpret a requirement, generate an artifact, and implicitly approve it, the workflow records distinct proposal and review stages. Disagreement, missing evidence, and ambiguous language become escalation signals rather than hidden assumptions.

## 2. Research questions

1. Does role separation improve requirement recall and defect discovery compared with a single-agent workflow?
2. Does independent review reduce vacuous, syntactically invalid, or semantically incorrect assertions?
3. Can requirement identifiers and provenance survive the full specification-to-verification workflow?
4. Which disagreements predict genuine specification defects or missing test intent?
5. Does the additional orchestration cost reduce or increase total human review time?

## 3. Proposed architecture

The full research architecture assigns bounded responsibilities.

- **Specification analyst:** extracts requirements, interfaces, assumptions, timing constraints, and ambiguities.
- **Test-plan agent:** maps requirements to nominal, boundary, error, concurrency, reset, and adversarial scenarios.
- **Assertion agent:** drafts safety and liveness properties with explicit assumptions.
- **Adversarial reviewer:** searches for vacuity, missing antecedents, weak timing, conflicting assumptions, and unsupported signals.
- **Coverage analyst:** identifies requirements without measurable evidence and proposes functional or assertion coverage.
- **Orchestrator:** preserves identifiers, artifacts, review findings, confidence, approval state, and human escalation.

No role approves its own output. Human experts remain responsible for acceptance, simulation or formal execution, and sign-off.

## 4. Runnable reference prototype

The repository prototype implements a compact slice of this architecture in [verification_copilot.py](../src/assurance_portfolio/verification_copilot.py).

For each requirement, it:

1. normalizes whitespace,
2. preserves the requirement identifier,
3. produces a draft assertion placeholder,
4. generates nominal, boundary, and adversarial scenario labels,
5. creates a requirement-linked coverage goal, and
6. performs a separate ambiguity review.

The review currently flags:

- absence of normative terms such as “must,” “shall,” “never,” or “within,”
- a non-numeric timing bound following “within,” and
- ambiguous adjectives including “appropriate,” “quickly,” and “secure.”

The generated assertion is explicitly a draft string, not a claim of syntactic or semantic correctness. The prototype does not parse RTL, invoke a simulator or formal engine, test vacuity, or measure design coverage.

## 5. Traceability model

Every output carries the original requirement identifier. This creates a minimal chain:

**Requirement -> Draft assertion -> Scenarios -> Coverage goal -> Review findings**

A production system should extend this into a typed provenance graph containing source-document locations, model and prompt versions, retrieved evidence, tool results, reviewer identity, unresolved disagreement, and approval state. Traceability should be evaluated for correctness, not merely for the presence of identifiers.

## 6. Prototype evidence

The [example requirements](../examples/requirements.json) include:

- a human-approval requirement,
- a numeric shutdown-timing requirement, and
- a deliberately weak statement that the system should respond “quickly and securely.”

The repository test suite includes a unit test confirming that the weak requirement produces both a missing-normative-term finding and an ambiguous-adjective finding. This is implementation validation only. It is not an empirical comparison of agent architectures and does not establish assertion correctness, requirement recall, or productivity improvement.

## 7. Proposed evaluation

A controlled study should compare:

1. **Single-agent baseline:** one model produces and reviews all artifacts.
2. **Unconstrained multi-agent baseline:** multiple agents collaborate without independence rules.
3. **Role-separated workflow:** proposal and review roles are distinct, with human escalation.

### Dataset

Use compact public RTL blocks or protocols with:

- independently authored reference requirements,
- reference assertions and expected traces,
- seeded specification and RTL defects,
- precise and deliberately ambiguous requirement variants, and
- reset, timing, concurrency, and error-handling cases.

### Metrics

- requirement recall and precision,
- assertion parse and elaboration success,
- semantic correctness against reference traces,
- vacuity rate,
- seeded-defect detection,
- false-positive rate,
- functional and assertion coverage,
- provenance completeness,
- calibrated abstention,
- human review time, and
- inference and tool-execution cost.

Repeated trials should vary model, prompt, seed, and orchestration configuration. Reviewers should be blinded to workflow condition where practical.

## 8. Threats to validity

Multiple agents may share model-level blind spots and create correlated errors. Role labels alone do not guarantee independence. Automated judges may reward plausible wording rather than executable correctness. A small public benchmark may not represent proprietary SoC complexity. Seeded defects may be easier to detect than organic specification failures. Human-review time can also shift rather than decrease.

These risks motivate tool-grounded scoring with parsers, simulators, formal engines, mutation testing, and independently authored reference artifacts.

## 9. Related work

AssertLLM processes specification documents and generates assertions from natural language and waveform information, demonstrating the promise and difficulty of document-level assertion generation. VERT and AssertionBench contribute datasets for evaluating LLM-generated assertions. CoverAssert adds a coverage-guided feedback loop and reports that single-pass assertion generation can miss functional intent. The Accellera UVM standard provides the broader reusable verification methodology into which a future copilot must integrate.

The contribution proposed here is complementary: explicit proposer-reviewer separation, preserved requirement provenance, disagreement as an escalation signal, and evaluation of the whole requirements-to-evidence workflow.

## 10. Limitations and next steps

The current prototype is dependency-free demonstration code. It does not contain multiple model-backed agents, generate correct SVA, connect to UVM, or execute EDA tools. The next implementation milestone should add a typed requirement schema, parser-backed SVA checks, a small open RTL target, seeded defects, provenance records, and a baseline comparison.

## 11. Conclusion

A useful verification copilot must do more than generate plausible code. It must preserve design intent, expose uncertainty, separate proposal from approval, and produce evidence that engineers can inspect. The current prototype demonstrates the smallest auditable version of that idea and defines a path toward controlled evaluation.

## References

1. Yan, Z. et al. (2024). [AssertLLM: Generating Hardware Verification Assertions from Design Specifications](https://arxiv.org/abs/2411.14436).
2. Menon, A. et al. (2025). [VERT: A SystemVerilog Assertion Dataset to Improve Hardware Verification with LLMs](https://openreview.net/forum?id=rZmQ2z7MPA).
3. Wang, Y. et al. (2026). [CoverAssert: Iterative LLM Assertion Generation Driven by Functional Coverage](https://arxiv.org/abs/2604.06607).
4. Shahidzadeh, M. et al. (2024). [Automatic High-Quality Verilog Assertion Generation through Subtask-Focused Fine-Tuned LLMs and Iterative Prompting](https://arxiv.org/abs/2411.15442).
5. Accellera Systems Initiative. [Universal Verification Methodology](https://www.accellera.org/downloads/standards/uvm).

## Suggested citation

Dinakar, S. J. (2026). *Role-Separated Multi-Agent Verification Copilot: A Traceable Workflow for AI-Assisted Pre-Silicon Verification*. Working paper and prototype report.
