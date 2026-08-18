# Role-Separated Multi-Agent Verification Copilot

## A Traceable Workflow for AI-Assisted Pre-Silicon Verification

**Author:** Srinivasa J. Dinakar  
**Date:** August 18, 2026  
**Status:** Working paper and prototype report; not peer reviewed

## Abstract

Pre-silicon verification translates design intent into assertions, scenarios, coverage goals, and executable evidence. Large language models can accelerate drafting, but fluent generation can silently omit qualifiers, blur proposal and approval roles, or produce plausible but invalid properties. This working paper presents a role-separated verification-copilot architecture and V6 prototype combining: (1) a deterministic grammar/review baseline, (2) an optional model-backed generator role, (3) a separate adversarial reviewer role, (4) deterministic assertion validation including a real Verilator adapter, (5) labelled synthetic trace benchmarks, and (6) behavioral RTL mutation execution with Icarus Verilog. V6 executes a bounded request/grant requirement against an intended implementation and a deliberately late-grant mutation. The benchmark is considered successful only if the intended design passes and the mutation fails. This is the first repository milestone to establish runtime detection of a labelled RTL defect; it does not yet establish that model-backed generation improves verification effectiveness relative to deterministic or single-model baselines.

**Keywords:** pre-silicon verification, multi-agent systems, SystemVerilog Assertions, requirements traceability, mutation testing, independent review, large language models, tool-grounded AI

## 1. Motivation

Verification engineers must interpret specifications, resolve ambiguity, design scenarios, write checkers and assertions, define coverage, and investigate failures. An error in requirement interpretation can propagate into every downstream artifact. Generative models can accelerate drafting, but fluency is not evidence of correctness.

The central hypothesis is that role separation plus deterministic verification-tool feedback can make AI-assisted verification more auditable. Proposal, requirement review, model review, tool validation, behavioral execution, and human acceptance should remain distinguishable stages rather than one opaque model response.

## 2. Research questions

1. Does role separation improve requirement recall and defect discovery compared with a single-model workflow?
2. Does adversarial review reduce syntactically invalid, semantically incorrect, or vacuous assertions?
3. Does deterministic tool gating catch failures that model self-review misses?
4. Does behavioral execution against seeded RTL mutations provide a useful ground-truth signal for evaluating generated properties?
5. Which reviewer disagreements or abstentions predict genuine specification defects?
6. Does orchestration improve total human review efficiency after model and tool cost are included?

## 3. V6 architecture

### 3.1 Deterministic baseline

[`verification_copilot.py`](../src/assurance_portfolio/verification_copilot.py) preserves the dependency-free baseline. It performs requirement-quality review, fail-safe complete-match grammar translation, pattern-specific scenario and coverage generation, provenance recording, and independent artifact review.

The baseline remains necessary because a model-backed workflow should be evaluated against a reproducible reference rather than only against another model configuration.

### 3.2 Model generator and reviewer

[`agentic_verification.py`](../src/assurance_portfolio/agentic_verification.py) defines a model-backed generator and separate adversarial reviewer behind a minimal backend contract. The generator returns a strict JSON artifact containing an assertion, scenarios, coverage goal, assumptions, and rationale. The reviewer cannot edit the draft and must return one of:

- `ACCEPT_FOR_TOOL_CHECK`,
- `REVISE`, or
- `ABSTAIN`.

The implementation requires distinct generator and reviewer backend instances. This is workflow separation, not proof of statistical independence when both roles use the same model family.

### 3.3 Deterministic acceptance gate

A reviewer cannot directly mark a candidate accepted. Only `ACCEPT_FOR_TOOL_CHECK` sends the assertion to the configured deterministic validator. `accepted_for_human_review=true` requires both reviewer acceptance-for-tool-check and validator `VALID` status.

That state means the candidate may proceed to expert review. It is not design sign-off.

## 4. Model backend implementation

The repository includes:

- `ScriptedModelBackend` for deterministic CI and offline tests,
- `OpenAIResponsesBackend` for optional live model calls.

The CLI supports a live path with either structural or Verilator validation. API credentials are not stored in the repository and CI does not require model access.

## 5. Evidence layers

V6 deliberately separates four evidence claims.

### 5.1 Model proposal

A generated assertion is a candidate artifact only. It may be plausible but wrong.

### 5.2 Structural validation

`StructuralSVAValidator` catches obvious malformed output such as missing `assert property`, missing semicolon, unbalanced parentheses, or fallback placeholders. It is not an SVA parser.

### 5.3 Concrete tool acceptance

`VerilatorSVAValidator` constructs a standalone SystemVerilog probe module and invokes an installed Verilator executable. A `VALID` result means that concrete tool/version accepted the assertion. It does not prove design-context correctness, non-vacuity, or requirement adequacy.

### 5.4 Behavioral RTL execution

V6 adds [`rtl_behavioral.py`](../src/assurance_portfolio/rtl_behavioral.py), which uses Icarus Verilog to compile and simulate RTL plus a generated temporal monitor. This layer asks whether the implementation behavior satisfies the bounded requirement at runtime.

## 6. Seeded benchmarks

### 6.1 Synthetic trace benchmark

[`verification_benchmark.py`](../src/assurance_portfolio/verification_benchmark.py) provides labelled traces for bounded response and prohibition requirements and reports accuracy, defect detection, and false positives. These traces remain useful regression baselines but are not RTL simulation evidence.

### 6.2 Behavioral RTL mutation benchmark

The RTL corpus currently contains two request/grant implementations:

- [`handshake_good.sv`](../benchmarks/rtl/handshake_good.sv), intended to satisfy `grant shall assert within 4 cycles after request`.
- [`handshake_late_bug.sv`](../benchmarks/rtl/handshake_late_bug.sv), a deliberately seeded mutation that delays grant beyond the bound.

`IcarusBehavioralRunner` generates a SystemVerilog testbench, resets the DUT, pulses `request`, observes `grant`, and requires grant within four sampled cycles. The benchmark succeeds only if:

1. the intended RTL passes,
2. the late-grant mutation fails,
3. mutation-detection rate is 1.0, and
4. false-positive count is zero.

Compilation failure or simulator unavailability is reported separately and does not count as mutation detection.

The CLI entry point is:

```text
assurance-demo rtl-benchmark --rtl-root benchmarks/rtl
```

GitHub Actions installs Icarus Verilog and runs the benchmark in a dedicated `rtl-behavioral-proof` job.

## 7. Prototype evidence

When the V6 CI matrix passes, the repository establishes the following implementation facts:

- generator and reviewer roles require separate backend instances,
- model outputs are schema-checked,
- reviewer revision/abstention prevents tool acceptance,
- deterministic validator acceptance is required for a human-review candidate,
- fallback placeholders fail structural validation,
- a real Verilator adapter is exercised in CI,
- deterministic synthetic monitors detect the labelled trace defects,
- the intended handshake RTL satisfies the four-cycle behavioral monitor, and
- the seeded late-grant RTL mutation violates that same monitor.

These are software and benchmark facts for the included fixtures. They do not prove superiority of the model-backed workflow.

## 8. Controlled evaluation design

The next experiment should compare four conditions on the same mutation corpus:

1. **Deterministic baseline** - complete-match grammar/reference-property workflow.
2. **Single-model generation** - one model call produces the artifact without independent review.
3. **Role-separated model workflow** - generator plus reviewer without deterministic behavioral gating.
4. **Role-separated + tool-gated workflow** - generator plus reviewer plus syntax/behavioral verification feedback.

### Dataset

Expand the current corpus with compact public RTL blocks containing independently authored requirements, reference assertions, expected traces, seeded mutations, ambiguous/paraphrased requirement variants, reset cases, timing cases, concurrency, and error-handling behavior.

### Metrics

- requirement recall and precision,
- assertion parse/elaboration success,
- behavioral mutation detection,
- false-positive rate,
- vacuity rate where measurable,
- reviewer escalation/abstention rate,
- human review time,
- model latency/token cost,
- verification-tool execution cost.

Repeated trials should vary model, prompt, seed, and orchestration configuration. Human reviewers should be blinded to workflow condition where practical.

## 9. Threats to validity

Separate model calls may retain correlated blind spots. Syntax acceptance can admit semantically wrong assertions. One toy handshake mutation is not representative of SoC-scale verification. Seeded defects may be easier than organic design failures. Procedural behavioral monitors and specific simulator semantics may differ from commercial sign-off flows. Human-review effort can shift rather than decrease.

These limitations motivate a larger mutation corpus, independently authored reference properties, multiple simulators/formal engines, vacuity analysis, repeated trials, and blinded expert review.

## 10. What V6 contributes

The contribution is now a narrow but executable end-to-end assurance chain:

**requirement → deterministic baseline → optional model generator → independent reviewer → deterministic assertion validation → behavioral RTL benchmark → human-review evidence**

V6 closes the specific gap left by V5: the repository no longer stops at standalone assertion acceptance. It now executes a temporal requirement against actual RTL and demonstrates detection of a labelled mutation when CI passes.

## 11. Limitations and next milestone

V6 still does not:

- execute arbitrary model-generated properties automatically against arbitrary RTL,
- run formal proof or counterexample minimization,
- measure vacuity on real designs,
- use RAG over specifications,
- integrate UVM regressions or commercial EDA tools,
- compare live model conditions experimentally,
- establish statistically meaningful productivity or defect-detection gains.

The next milestone is therefore a **controlled comparative experiment over a larger mutation corpus**, not another orchestration layer.

## 12. Conclusion

A useful verification copilot must do more than generate plausible code. It must preserve design intent, expose uncertainty, separate proposal from review, ground acceptance in executable tools, and retain human authority. V6 adds behavioral mutation proof to that chain. The remaining question is empirical: whether role-separated model assistance improves real verification outcomes enough to justify its complexity and cost.

## References

1. Yan, Z. et al. (2024). [AssertLLM: Generating Hardware Verification Assertions from Design Specifications](https://arxiv.org/abs/2411.14436).
2. Menon, A. et al. (2025). [VERT: A SystemVerilog Assertion Dataset to Improve Hardware Verification with LLMs](https://openreview.net/forum?id=rZmQ2z7MPA).
3. Wang, Y. et al. (2026). [CoverAssert: Iterative LLM Assertion Generation Driven by Functional Coverage](https://arxiv.org/abs/2604.06607).
4. Shahidzadeh, M. et al. (2024). [Automatic High-Quality Verilog Assertion Generation through Subtask-Focused Fine-Tuned LLMs and Iterative Prompting](https://arxiv.org/abs/2411.15442).
5. Accellera Systems Initiative. [Universal Verification Methodology](https://www.accellera.org/downloads/standards/uvm).

## Suggested citation

Dinakar, S. J. (2026). *Role-Separated Multi-Agent Verification Copilot: A Traceable Workflow for AI-Assisted Pre-Silicon Verification*. Working paper and prototype report.
