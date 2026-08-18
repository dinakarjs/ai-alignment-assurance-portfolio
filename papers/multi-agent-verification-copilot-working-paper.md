# Role-Separated Multi-Agent Verification Copilot

## A Traceable Workflow for AI-Assisted Pre-Silicon Verification

**Author:** Srinivasa J. Dinakar  
**Date:** August 18, 2026  
**Status:** Working paper and prototype report; not peer reviewed

## Abstract

Pre-silicon verification translates design intent into assertions, scenarios, coverage goals, and executable evidence. Large language models can accelerate drafting, but fluent generation can silently omit qualifiers, blur proposal and approval roles, or produce plausible but invalid properties. This working paper presents a role-separated verification-copilot architecture and V5 prototype that combines: (1) a deterministic grammar/review baseline, (2) an optional model-backed generator role, (3) a separate model-backed adversarial reviewer role, (4) deterministic assertion validation including a Verilator adapter, and (5) a small labelled defect benchmark. The implementation explicitly separates model proposal, reviewer disposition, tool acceptance, and human review. CI tests the orchestration with scripted backends and exercises a real Verilator validation job without API credentials. V5 does not yet establish that model-backed role separation improves semantic assertion correctness or RTL defect detection; the next controlled experiment must execute candidate properties against seeded RTL mutations and compare deterministic, single-model, and role-separated workflows.

**Keywords:** pre-silicon verification, multi-agent systems, SystemVerilog Assertions, requirements traceability, verification planning, independent review, large language models, tool-grounded AI

## 1. Motivation

Verification engineers must interpret specifications, resolve ambiguity, design scenarios, write checkers and assertions, define coverage, and investigate failures. An error in requirement interpretation can propagate into every downstream artifact. Generative models can accelerate drafting, but fluency is not evidence of correctness.

The central hypothesis is that role separation plus deterministic verification-tool feedback can make AI-assisted verification more auditable. Proposal, requirement review, model review, tool validation, and human acceptance should remain distinguishable stages rather than one opaque model response.

## 2. Research questions

1. Does role separation improve requirement recall and defect discovery compared with a single-model workflow?
2. Does an adversarial reviewer reduce syntactically invalid, semantically incorrect, or vacuous assertions?
3. Does deterministic tool gating catch failures that model self-review misses?
4. Can provenance survive requirement-to-artifact-to-tool workflows?
5. Which reviewer disagreements or abstentions predict genuine specification defects?
6. Does the additional orchestration cost reduce or increase total human review effort?

## 3. V5 architecture

V5 implements four bounded stages.

### 3.1 Deterministic baseline

[`verification_copilot.py`](../src/assurance_portfolio/verification_copilot.py) preserves a dependency-free V4 baseline. It performs requirement-quality review, fail-safe complete-match grammar translation, pattern-specific scenario/coverage generation, provenance recording, and independent artifact review.

The deterministic baseline remains important because a model-backed workflow should be compared against something reproducible rather than only against another model configuration.

### 3.2 Model generator

[`agentic_verification.py`](../src/assurance_portfolio/agentic_verification.py) defines a `ModelArtifactGenerator` behind a minimal backend interface. The generator receives the natural-language requirement and deterministic-baseline context and must return a strict JSON object containing:

- one candidate `assert property` statement,
- scenarios,
- a measurable coverage goal,
- explicit assumptions, and
- rationale.

The generator is instructed not to claim sign-off or tool validation.

### 3.3 Independent model reviewer

A separate `ModelArtifactReviewer` sees the requirement and generated draft but cannot edit the candidate. Its output is constrained to:

- `ACCEPT_FOR_TOOL_CHECK`,
- `REVISE`, or
- `ABSTAIN`,

plus explicit findings and a recommended next action.

The implementation requires distinct generator and reviewer backend instances. This is workflow separation, not a guarantee of statistical independence: two calls to the same model family may retain correlated blind spots.

### 3.4 Deterministic validator and human-review gate

The reviewer cannot directly mark a draft accepted. Only `ACCEPT_FOR_TOOL_CHECK` sends the assertion to a configured deterministic validator. The final `accepted_for_human_review` flag is true only when both conditions hold:

1. reviewer verdict is `ACCEPT_FOR_TOOL_CHECK`, and
2. the validator returns `VALID`.

This flag means the candidate can proceed to expert review. It does not mean the property is semantically correct or approved for sign-off.

## 4. Model backend implementation

V5 includes two backends.

- `ScriptedModelBackend` supplies deterministic canned responses for CI and offline testing.
- `OpenAIResponsesBackend` provides the optional live model path while keeping the core package dependency-free by importing the SDK lazily.

The CLI supports:

```text
assurance-demo agentic examples/requirements.json --validator structural
```

or, when Verilator is installed:

```text
assurance-demo agentic examples/requirements.json --validator verilator
```

The repository does not store API credentials, and CI does not require model access.

## 5. Tool-grounded assertion validation

[`sva_validation.py`](../src/assurance_portfolio/sva_validation.py) deliberately separates two validation claims.

### Structural validator

`StructuralSVAValidator` catches obvious malformed output such as missing `assert property`, missing semicolon, unbalanced parentheses, or fallback placeholders. It is not an SVA parser.

### Verilator validator

`VerilatorSVAValidator` constructs a standalone SystemVerilog probe module, declares inferred signal identifiers, and invokes the installed Verilator executable in assertion/lint mode. The result records validator identity and tool version where available.

A `VALID` result means the candidate was accepted by that concrete Verilator invocation. It does **not** prove universal IEEE-SVA semantics, design-context correctness, non-vacuity, or property adequacy.

The GitHub Actions workflow installs Verilator in a dedicated job and requires a representative assertion to pass the real adapter. This converts the validator from a paper interface into an exercised integration point.

## 6. Seeded defect benchmark

[`verification_benchmark.py`](../src/assurance_portfolio/verification_benchmark.py) provides a deterministic labelled trace benchmark for two compact requirement families:

- bounded response: `grant shall assert within 4 cycles after request`, and
- prohibition: `grant shall never assert while reset`.

The benchmark reports:

- evaluated cases,
- correct classifications,
- seeded defects detected,
- false positives,
- accuracy, and
- defect-detection rate.

These are synthetic trace results. They are useful for regression and orchestration baselines but are not RTL simulation evidence.

V5 also adds two RTL fixtures:

- [`handshake_good.sv`](../benchmarks/rtl/handshake_good.sv), and
- [`handshake_late_bug.sv`](../benchmarks/rtl/handshake_late_bug.sv).

The second fixture contains a labelled late-grant mutation beyond the intended bounded-response requirement. V5 does not yet claim behavioural detection of this mutation; it is the target for the next simulator/formal experiment.

## 7. Prototype evidence

The automated test suite now establishes the following implementation facts:

- generator and reviewer roles must use distinct backend instances,
- model JSON outputs are schema-checked,
- reviewer `REVISE` prevents tool acceptance,
- reviewer `ACCEPT_FOR_TOOL_CHECK` plus validator `VALID` produces a human-review candidate,
- fallback placeholders fail structural validation,
- deterministic reference monitors detect all labelled synthetic benchmark defects without false positives in the included cases,
- the existing V4 fail-safe grammar and trace-policy regression suite remains active, and
- a CI job exercises a real installed Verilator adapter.

These tests establish software behavior only. They do not prove that live model generation improves verification quality.

## 8. Proposed controlled evaluation

The next experiment should compare four conditions on the same dataset:

1. **Deterministic baseline** - V4 complete-match grammar workflow.
2. **Single-model generation** - one model call produces the artifact without independent review.
3. **Role-separated model workflow** - generator + reviewer without deterministic tool gating.
4. **Role-separated + tool-gated workflow** - generator + reviewer + simulator/formal/tool feedback.

### Dataset

Use compact public RTL blocks or protocols with:

- independently authored reference requirements,
- reference assertions,
- expected pass/fail traces,
- seeded RTL mutations,
- ambiguous and paraphrased requirement variants,
- reset/timing/concurrency/error cases.

### Metrics

- requirement recall and precision,
- assertion parse/elaboration success,
- semantic correctness against labelled traces,
- vacuity rate where measurable,
- seeded-defect detection,
- false-positive rate,
- reviewer escalation/abstention rate,
- human review time,
- latency,
- model token cost, and
- verification-tool execution cost.

Repeated trials should vary model, prompt, seed, and orchestration configuration. Human reviewers should be blinded to workflow condition where practical.

## 9. Threats to validity

Multiple agents may share model-level blind spots. Separate calls do not guarantee independent reasoning. A syntax/tool acceptance gate may still admit a semantically wrong assertion. Small synthetic benchmarks can overstate performance. Seeded defects may be easier than organic design failures. Public RTL blocks do not represent proprietary SoC complexity. Human review effort can shift rather than decrease.

These risks motivate executable reference properties, mutation testing, simulation/formal scoring, repeated trials, error taxonomy, and blinded expert review.

## 10. What V5 contributes

The contribution is no longer only an architectural proposal. V5 implements a narrow but real end-to-end skeleton:

**requirement → deterministic baseline → model generator → independent model reviewer → deterministic validator → human-review candidate**

It also provides offline scripted testing, a live model adapter, a concrete Verilator integration, a seeded trace benchmark, and labelled RTL fixtures.

The remaining research question is empirical: whether this architecture actually improves verification outcomes enough to justify its complexity and cost.

## 11. Limitations and next milestone

V5 does not yet:

- execute generated assertions against the target RTL fixtures,
- run formal proof or counterexample generation,
- measure vacuity on real designs,
- use RAG over specification documents,
- integrate UVM regressions or commercial EDA tools,
- compare live model conditions experimentally, or
- report statistically meaningful productivity or defect-detection gains.

The next milestone is therefore **behavioural execution and controlled measurement**, not another orchestration abstraction.

## 12. Conclusion

A useful verification copilot must do more than generate plausible code. It must preserve design intent, expose uncertainty, separate proposal from review, ground acceptance in executable tools, and retain human authority. V5 implements that skeleton while maintaining a deterministic baseline and explicit trust boundaries. Its value now depends on executing candidate properties against seeded RTL defects and measuring whether role separation plus tool grounding improves real verification outcomes.

## References

1. Yan, Z. et al. (2024). [AssertLLM: Generating Hardware Verification Assertions from Design Specifications](https://arxiv.org/abs/2411.14436).
2. Menon, A. et al. (2025). [VERT: A SystemVerilog Assertion Dataset to Improve Hardware Verification with LLMs](https://openreview.net/forum?id=rZmQ2z7MPA).
3. Wang, Y. et al. (2026). [CoverAssert: Iterative LLM Assertion Generation Driven by Functional Coverage](https://arxiv.org/abs/2604.06607).
4. Shahidzadeh, M. et al. (2024). [Automatic High-Quality Verilog Assertion Generation through Subtask-Focused Fine-Tuned LLMs and Iterative Prompting](https://arxiv.org/abs/2411.15442).
5. Accellera Systems Initiative. [Universal Verification Methodology](https://www.accellera.org/downloads/standards/uvm).

## Suggested citation

Dinakar, S. J. (2026). *Role-Separated Multi-Agent Verification Copilot: A Traceable Workflow for AI-Assisted Pre-Silicon Verification*. Working paper and prototype report.
