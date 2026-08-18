# Role-Separated Multi-Agent Verification Copilot

## A Traceable Workflow for AI-Assisted Pre-Silicon Verification

**Author:** Srinivasa J. Dinakar  
**Date:** August 18, 2026  
**Status:** Working paper and prototype report; not peer reviewed

## Abstract

Pre-silicon verification translates design intent into assertions, scenarios, coverage goals, and executable evidence. Large language models can accelerate drafting, but fluent generation can silently omit qualifiers, blur proposal and approval roles, or produce plausible but invalid properties. This working paper presents a role-separated verification-copilot architecture and V9 prototype combining: (1) a deterministic grammar/review baseline, (2) an optional model-backed generator role, (3) a separate adversarial reviewer role, (4) deterministic assertion validation including a real Verilator adapter, (5) behavioral execution with Icarus Verilog, (6) a three-family labelled RTL mutation corpus, (7) repeated four-condition workflow evaluation, and (8) reproducible experiment bundles with configuration identity, outcome identity, latency, and provider token usage when available. Scripted/offline trials validate the measurement and artifact pipeline; they are not empirical evidence of model superiority. The repository supports repeated live-model trials but does not run them in CI and does not yet establish that model-backed role separation improves verification outcomes.

**Keywords:** pre-silicon verification, multi-agent systems, SystemVerilog Assertions, requirements traceability, mutation testing, independent review, large language models, tool-grounded AI, reproducible experiments

## 1. Motivation

Verification engineers must interpret specifications, resolve ambiguity, design scenarios, write checkers and assertions, define coverage, and investigate failures. An error in requirement interpretation can propagate into every downstream artifact. Generative models can accelerate drafting, but fluency is not evidence of correctness.

The central hypothesis is that role separation plus deterministic verification-tool feedback can make AI-assisted verification more auditable. Proposal, requirement review, model review, tool validation, behavioral execution, human acceptance, and experiment reporting should remain distinguishable stages rather than one opaque model response.

## 2. Research questions

1. Does role separation improve requirement interpretation and defect discovery compared with a single-model workflow?
2. Does adversarial review reduce syntactically invalid, semantically incorrect, or vacuous assertions?
3. Does deterministic tool gating catch failures that model self-review misses?
4. Does behavioral execution against seeded RTL mutations provide a useful ground-truth signal for evaluating generated properties?
5. Which reviewer disagreements or abstentions predict genuine specification or artifact defects?
6. Does orchestration improve total human review efficiency after latency and model/tool usage are considered?
7. Can experiment provenance be captured well enough to support repeatable, auditable comparisons across model and prompt configurations?

## 3. Current architecture

### 3.1 Deterministic baseline

[`verification_copilot.py`](../src/assurance_portfolio/verification_copilot.py) preserves a dependency-free baseline. It performs requirement-quality review, fail-safe complete-match grammar translation, pattern-specific scenario and coverage generation, provenance recording, and independent artifact review.

The baseline remains necessary because a model-backed workflow should be evaluated against a reproducible reference rather than only against another model configuration.

### 3.2 Model generator and reviewer

[`agentic_verification.py`](../src/assurance_portfolio/agentic_verification.py) defines a model-backed generator and separate adversarial reviewer behind a minimal backend contract. The generator returns a strict JSON artifact containing an assertion, scenarios, coverage goal, assumptions, and rationale. The reviewer cannot edit the draft and must return one of:

- `ACCEPT_FOR_TOOL_CHECK`,
- `REVISE`, or
- `ABSTAIN`.

The implementation uses distinct generator and reviewer backend instances. This is workflow separation, not proof of statistical independence when both roles use the same model family.

### 3.3 Deterministic acceptance gate

A reviewer cannot directly mark a candidate accepted. Only `ACCEPT_FOR_TOOL_CHECK` sends the assertion to the configured deterministic validator. `accepted_for_human_review=true` requires both reviewer acceptance-for-tool-check and validator `VALID` status.

That state means the candidate may proceed to expert review. It is not design sign-off.

## 4. Model backend and usage telemetry

The repository includes:

- `ScriptedModelBackend` for deterministic CI and offline tests,
- `OpenAIResponsesBackend` for optional live model calls.

V9 records model request counts for all instrumented backends and input/output/total token counts when the provider returns usage telemetry. Scripted backends deliberately do not invent token counts.

The CLI supports live model execution with either structural or Verilator validation. API credentials are not stored in the repository and CI does not require model access.

Dollar cost is intentionally not inferred from token counts. Prices are external, model-specific, and time-dependent; historical usage should be joined to an explicitly dated pricing table if cost analysis is later required.

## 5. Evidence layers

V9 deliberately separates six evidence claims.

### 5.1 Deterministic reference output

The deterministic grammar provides a reproducible baseline and explicit fallback behavior. A supported translation is still a draft artifact requiring design-context review.

### 5.2 Model proposal and review

A generated assertion is a candidate artifact only. Reviewer acceptance indicates that the candidate may proceed to a deterministic check; it does not establish semantic correctness.

### 5.3 Structural validation

`StructuralSVAValidator` catches obvious malformed output such as missing `assert property`, missing semicolon, unbalanced parentheses, or fallback placeholders. It is not a full SVA parser.

### 5.4 Concrete tool acceptance

`VerilatorSVAValidator` constructs a standalone SystemVerilog probe module and invokes an installed Verilator executable. A `VALID` result means that concrete tool/version accepted the assertion. It does not prove design-context correctness, non-vacuity, or requirement adequacy.

### 5.5 Behavioral RTL execution

Icarus Verilog runners compile and execute known-good and mutated RTL against procedural temporal monitors derived from supported assertion families. A compile error or unavailable tool does not count as defect detection.

### 5.6 Reproducible experiment evidence

V9 writes a manifest, structured trials, aggregate summary, row-level CSV, aggregate CSV, and Markdown report. The experiment artifact preserves model/prompt/evidence metadata, code identity where available, behavioral outcomes, reviewer disposition, latency, request counts, and token usage when provided.

## 6. Multi-family seeded RTL corpus

The current corpus contains three temporal requirement families.

### 6.1 Bounded response — BR-001

Requirement:

```text
grant shall assert within 4 cycles after request
```

Fixtures:

- [`handshake_good.sv`](../benchmarks/rtl/handshake_good.sv), intended to satisfy the requirement;
- [`handshake_late_bug.sv`](../benchmarks/rtl/handshake_late_bug.sv), deliberately delays grant beyond the bound.

### 6.2 Prohibition — PR-001

Requirement:

```text
grant shall never assert while reset
```

Fixtures:

- `prohibition_good.sv`, expected to keep grant low while reset is active;
- `prohibition_bug.sv`, contains a labelled violation.

### 6.3 Immediate implication — IM-001

Requirement:

```text
if request is high, busy shall be high
```

Fixtures:

- `implication_good.sv`, expected to satisfy the same-cycle implication;
- `implication_bug.sv`, contains a labelled violation.

[`corpus_benchmark.py`](../src/assurance_portfolio/corpus_benchmark.py) maps supported candidate assertion families to the matching RTL pair and runs both the known-good and mutated design.

## 7. Four-condition repeated evaluation

[`corpus_evaluation.py`](../src/assurance_portfolio/corpus_evaluation.py) applies the same corpus to four workflow conditions:

1. **Deterministic baseline** — deterministic grammar/reference output.
2. **Single-model generation** — one model call proposes the artifact.
3. **Generator + reviewer** — reviewer may accept, revise, or abstain; behavioral scoring is used for evaluation after acceptance.
4. **Generator + reviewer + tool gate** — reviewer acceptance is followed by deterministic structural gating before behavioral evaluation.

Reviewer `REVISE` and `ABSTAIN` outcomes stop execution and are measured as escalation rather than being misclassified as assertion failures.

The evaluator records:

- generation-failure rate,
- reviewer escalation rate,
- behavioral-execution rate,
- full-correct rate: known-good RTL passes and the mutation is detected,
- mutation-detection rate among executed cases,
- false-positive rate on known-good RTL,
- mean elapsed wall-clock time,
- model request counts,
- input/output/total token usage when available.

A candidate that detects the mutation but falsely rejects the known-good design is not counted as fully correct.

## 8. Scripted and live experiment modes

### 8.1 Scripted/offline mode

The scripted corpus deliberately includes a too-strict bounded-response candidate and a reviewer escalation. This ensures the pipeline exercises false positives, reviewer withholding, aggregation, and artifact reporting rather than trivially returning all-green outcomes.

These results validate software behavior and measurement plumbing only. They are not evidence that a model or orchestration strategy is better than another.

### 8.2 Live-model mode

The same evaluator can perform repeated live calls through the optional OpenAI backend. Live runs record `evidence_kind=live_model`, the configured model label, prompt version, request counts, and provider token usage when available.

Live-model trials are not run in repository CI. The existence of a live path does not imply that statistically meaningful live experiments have already been completed.

## 9. Experiment artifact protocol

[`experiment_artifacts.py`](../src/assurance_portfolio/experiment_artifacts.py) writes one experiment bundle containing:

- `manifest.json`,
- `trials.json`,
- `summary.json`,
- `results.csv`,
- `aggregates.csv`,
- `REPORT.md`.

V9 uses two identifiers:

- **experiment ID** — deterministic hash of the recorded configuration and code identity;
- **run ID** — deterministic hash of the experiment ID plus outcome-bearing trial fields.

This lets stochastic reruns share a configuration identity without overwriting different observed outcomes. Wall-clock latency and free-form notes are retained in the artifact but excluded from the run fingerprint.

The report explicitly states the interpretation boundary and leaves dollar cost unset unless a separate dated pricing policy is supplied.

## 10. Current implementation evidence

When the current CI matrix passes, the repository establishes the following implementation facts:

- deterministic requirement-to-artifact generation and fallback behavior remain regression-tested;
- generator and reviewer roles are separate workflow stages;
- model JSON outputs are schema-checked;
- reviewer revision/abstention prevents execution;
- a real Verilator adapter is exercised in CI;
- the request/grant mutation benchmark executes in Icarus Verilog;
- the four-condition V7 comparison executes against RTL;
- the three-family V8 corpus executes repeatedly against known-good and mutated RTL;
- V9 writes and validates the expected experiment bundle files;
- scripted runs record model request counts without fabricating token counts.

These are implementation and benchmark facts. They do not establish superiority of the model-backed workflow.

## 11. Threats to validity

Separate model calls may retain correlated blind spots. Structural or syntax acceptance can admit semantically wrong assertions. The current corpus has only three simple requirement families and one mutation per family. Seeded defects may be easier than organic design failures. Procedural monitors and open-source simulator semantics may differ from commercial sign-off flows. Repeated trials on a small corpus can give misleadingly stable aggregate rates. Human-review effort is not yet measured. The corpus and reference behavior were developed alongside the prototype, which creates benchmark-design bias.

These limitations motivate independently authored requirements and reference properties, multiple mutations per family, larger public RTL blocks, preregistered analysis, frozen model/prompt configurations, repeated live trials, additional simulator/formal checks, and blinded expert review.

## 12. Next controlled study

The next research milestone should be empirical rather than architectural.

A stronger study should:

1. freeze the model, prompt version, corpus revision, and analysis code before running the primary experiment;
2. use an independently authored or externally reviewed corpus with more mutations and requirement variants;
3. run enough repeated live trials to characterize variance rather than rely on one observation;
4. preserve raw model/tool outputs and V9 experiment manifests;
5. have expert reviewers score semantic correctness and review effort without seeing workflow condition where practical;
6. report confidence intervals or other uncertainty measures appropriate to the sample size;
7. keep exploratory results clearly separate from preregistered primary analyses.

The central empirical question is whether the added reviewer and tool-gating stages improve full-correct outcomes enough to justify their latency, token usage, and human-review cost.

## 13. What V9 contributes

The contribution is now an executable and auditable research skeleton:

**requirement → deterministic baseline → optional model generator → independent reviewer → deterministic validation → behavioral RTL evaluation → repeated comparison → reproducible experiment bundle → human review**

V9 does not resolve the research question. It makes the next experiment measurable and traceable enough that a positive or negative result can be inspected rather than inferred from a demo.

## 14. Limitations

V9 still does not:

- establish general natural-language-to-SVA correctness;
- run formal proof or counterexample minimization;
- measure vacuity systematically;
- use RAG over production specifications;
- integrate UVM regressions or commercial EDA tools;
- provide an independently designed large benchmark;
- report blinded expert-review data;
- report statistically meaningful live-model performance gains;
- estimate historical dollar cost without an explicitly dated pricing policy.

## 15. Conclusion

A useful verification copilot must do more than generate plausible code. It must preserve design intent, expose uncertainty, separate proposal from review, ground acceptance in executable tools, distinguish defect detection from false positives, and preserve enough experiment provenance to support scrutiny. V9 implements that research skeleton across three temporal requirement families and repeated workflow comparisons. The remaining question is empirical: whether role-separated model assistance materially improves verification outcomes on a larger, independently evaluated corpus after latency, token usage, and human review effort are accounted for.

## References

1. Yan, Z. et al. (2024). [AssertLLM: Generating Hardware Verification Assertions from Design Specifications](https://arxiv.org/abs/2411.14436).
2. Menon, A. et al. (2025). [VERT: A SystemVerilog Assertion Dataset to Improve Hardware Verification with LLMs](https://openreview.net/forum?id=rZmQ2z7MPA).
3. Wang, Y. et al. (2026). [CoverAssert: Iterative LLM Assertion Generation Driven by Functional Coverage](https://arxiv.org/abs/2604.06607).
4. Shahidzadeh, M. et al. (2024). [Automatic High-Quality Verilog Assertion Generation through Subtask-Focused Fine-Tuned LLMs and Iterative Prompting](https://arxiv.org/abs/2411.15442).
5. Accellera Systems Initiative. [Universal Verification Methodology](https://www.accellera.org/downloads/standards/uvm).

## Suggested citation

Dinakar, S. J. (2026). *Role-Separated Multi-Agent Verification Copilot: A Traceable Workflow for AI-Assisted Pre-Silicon Verification*. Working paper and prototype report.
