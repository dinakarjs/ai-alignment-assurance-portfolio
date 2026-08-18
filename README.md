# AI Assurance & Agentic Verification Portfolio - Runnable Prototypes

This repository applies semiconductor verification ideas to AI assurance and applies AI/agent workflows back to verification engineering. The implementation now separates deterministic baselines, model-backed roles, tool acceptance, behavioral RTL evidence, and controlled workflow comparison.

1. **Verification Copilot V7** - deterministic baseline, optional model-backed generator/reviewer roles, deterministic assertion validation, behavioral RTL mutation detection, and a four-condition comparison harness.
2. **Agent Trace Assurance Engine V4** - scoped/consumable/expiring authorization and evidence, high-risk classification checks, independent approval, shutdown monitoring, and PASS/FAIL/INCONCLUSIVE semantics.
3. **CloudGuard AI V3** - transparent threat scoring, evidence-strength semantics, human decision capture, and auditable recommendations.

These remain research prototypes rather than production EDA, security, alignment, or autonomous sign-off systems.

## Quick start

Python 3.10 or newer is required.

```bash
python -m pip install -e .
assurance-demo copilot examples/requirements.json
assurance-demo trace examples/agent_trace.json
assurance-demo cloudguard examples/cloudguard_incident.json
assurance-demo benchmark
```

With Icarus Verilog installed:

```bash
assurance-demo rtl-benchmark --rtl-root benchmarks/rtl
assurance-demo controlled-eval --rtl-root benchmarks/rtl
```

The RTL benchmark succeeds only when the intended handshake RTL passes the four-cycle request/grant requirement and the deliberately late-grant mutation fails it.

## Model-backed path

Install the optional agentic dependency and configure the OpenAI SDK normally:

```bash
python -m pip install -e ".[agentic]"
export OPENAI_API_KEY="..."
export OPENAI_MODEL="..."
assurance-demo agentic examples/requirements.json --validator structural
```

If Verilator is installed:

```bash
assurance-demo agentic examples/requirements.json --validator verilator
```

The workflow performs separate generator and reviewer model calls. The reviewer can return `ACCEPT_FOR_TOOL_CHECK`, `REVISE`, or `ABSTAIN`. A draft reaches `accepted_for_human_review=true` only when the reviewer sends it forward and the configured deterministic validator returns `VALID`. This is a human-review gate, not design sign-off.

Implementation: [`agentic_verification.py`](src/assurance_portfolio/agentic_verification.py)

## Verification Copilot V7

### Deterministic baseline

[`verification_copilot.py`](src/assurance_portfolio/verification_copilot.py) preserves requirement IDs, performs requirement-quality review, translates a deliberately narrow complete-match grammar into SVA-style drafts, generates pattern-specific scenarios and coverage goals, and independently reviews generated artifacts.

A requirement is marked **SUPPORTED** only when its complete normalized text matches an explicit grammar. Unsupported trailing semantics force fallback rather than being silently discarded.

### Model-backed roles

[`agentic_verification.py`](src/assurance_portfolio/agentic_verification.py) adds separate generator and adversarial reviewer roles behind a minimal backend interface. `OpenAIResponsesBackend` provides live calls and `ScriptedModelBackend` provides deterministic offline/CI testing. Separate calls do not guarantee statistical independence when both roles use the same model family.

### Deterministic validation

[`sva_validation.py`](src/assurance_portfolio/sva_validation.py) provides:

- `StructuralSVAValidator` for shallow dependency-free checks, and
- `VerilatorSVAValidator` for a concrete installed Verilator assertion/lint probe.

A Verilator `VALID` result means the assertion was accepted by that concrete tool/version. It does not establish semantic correctness against RTL.

### Behavioral RTL proof

[`rtl_behavioral.py`](src/assurance_portfolio/rtl_behavioral.py) compiles and simulates two request/grant designs with Icarus Verilog:

- [`handshake_good.sv`](benchmarks/rtl/handshake_good.sv) - expected to satisfy `grant shall assert within 4 cycles after request`,
- [`handshake_late_bug.sv`](benchmarks/rtl/handshake_late_bug.sv) - deliberately delays grant beyond the bound and is expected to fail.

The runner records PASS/FAIL state, expected outcome, simulator/tool version, mutation-detection rate, false-positive count, and whether all expected outcomes were met. Compile errors and unavailable tools do not count as successful mutation detection.

## V7 controlled evaluation

[`controlled_evaluation.py`](src/assurance_portfolio/controlled_evaluation.py) applies the same bounded-response RTL fixtures to four workflow conditions:

1. `deterministic`
2. `single_model`
3. `generator_reviewer`
4. `generator_reviewer_tool`

For each condition it records:

- generation success,
- reviewer disposition where applicable,
- assertion structural validity,
- whether behavioral evaluation ran,
- whether known-good RTL passed,
- whether the mutation was detected,
- false-positive count,
- elapsed wall-clock time, and
- token/cost fields only when telemetry is actually available.

The behavioral evaluator currently recognizes the bounded candidate form:

```systemverilog
assert property (@(posedge clk) request |-> ##[1:N] grant);
```

and executes the candidate's bound `N` against the same labelled RTL pair.

Run the deterministic scripted comparison:

```bash
assurance-demo controlled-eval --rtl-root benchmarks/rtl
```

This mode validates **measurement plumbing**, not model quality. The scripted cases deliberately include a too-strict assertion that detects the seeded mutation but falsely fails the good RTL, demonstrating why mutation detection alone is not sufficient evidence.

For live observations:

```bash
python -m pip install -e ".[agentic]"
export OPENAI_API_KEY="..."
export OPENAI_MODEL="..."
assurance-demo controlled-eval-live --rtl-root benchmarks/rtl
```

A single live run is an observation, not a statistically meaningful comparison. Repeated trials, fixed model/prompt configuration, a larger mutation corpus, and expert review are required before making workflow-superiority claims.

See [`benchmarks/CONTROLLED_EVALUATION.md`](benchmarks/CONTROLLED_EVALUATION.md).

## CI

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

GitHub Actions runs:

- Python 3.10 unit tests and CLI smoke tests,
- Python 3.11 unit tests and CLI smoke tests,
- Python 3.12 unit tests and CLI smoke tests,
- a real Verilator assertion-validation job,
- a real Icarus Verilog behavioral RTL mutation job, and
- the V7 scripted four-condition comparison using the real RTL behavioral runner.

CI does not use model API credentials.

## Agent Trace Assurance V4

Agent Trace Assurance treats each execution as an ordered event trace and evaluates explicit safety properties at relevant steps. It includes scoped and single-use grants, optional event-count expiry, strict scope matching, high-risk classification checks, required proposer/approver identities, shutdown compliance, and PASS/FAIL/INCONCLUSIVE results.

Current coverage is **property-exercise coverage**, not full functional/assertion/vacuity coverage. Authorization/evidence events are still assumed trustworthy observations; actor authority, evidence provenance/quality, and trace integrity remain future work.

Implementation: [`trace_assurance.py`](src/assurance_portfolio/trace_assurance.py)

## CloudGuard AI V3

CloudGuard remains a small Responsible-AI demonstration built around transparent weighted threat signals, heuristic evidence strength, top contributing reasons, named human decision/rationale capture, and a recommendation hash.

Its decision API is an audit/demo mechanism rather than a production execution gate. The explanation is described as **SHAP-style additive attribution**, not fitted SHAP on a trained production model.

Implementation: [`cloudguard.py`](src/assurance_portfolio/cloudguard.py)

## Research portfolio

- [Multi-Agent Verification Copilot](projects/multi-agent-verification-copilot.md)
- [Alignment Assurance Lab](projects/alignment-assurance-lab.md)
- [Pre-Silicon-Inspired Assurance Architecture](projects/pre-silicon-inspired-agentic-ai-assurance.md)
- [Responsible AI and DBA Research Agenda](projects/responsible-ai-dba-research.md)
- [CloudGuard AI](projects/cloudguard-ai.md)

## Papers and research artifacts

- [Artifact catalog](papers/README.md)
- [Multi-Agent Verification Copilot working paper](papers/multi-agent-verification-copilot-working-paper.md)
- [Alignment Assurance Lab working paper](papers/alignment-assurance-lab-working-paper.md)
- [CloudGuard AI course report - repository edition](papers/cloudguard-ai-course-report.md)
- [CloudGuard AI research presentation notes](papers/cloudguard-ai-research-presentation.md)

These are course materials, presentation notes, or working papers. None is presented as an accepted or peer-reviewed publication.

## What V7 proves - and what it does not

V7 demonstrates in runnable code:

- deterministic requirement-to-artifact generation and review,
- separate model-backed generator/reviewer roles,
- strict model-output contracts and abstention/revision states,
- deterministic acceptance gating,
- real Verilator tool acceptance in CI,
- synthetic trace defect benchmarks,
- real simulation of labelled RTL fixtures,
- behavioral detection of one seeded late-grant mutation without falsely failing the intended implementation, and
- a common four-condition measurement harness that can distinguish mutation detection from false-positive behavior and reviewer/tool gating.

V7 does **not** prove that model-backed generation is superior to the deterministic baseline. The scripted comparison is not empirical model evidence, the RTL corpus is still tiny, token/cost fields remain unavailable unless telemetry is captured, and human review effort is not yet measured.

The next research step is to expand the mutation/requirement corpus and run repeated live-model trials with recorded configuration, usage, latency, behavioral outcomes, and blinded expert review.
