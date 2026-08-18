# AI Assurance & Agentic Verification Portfolio - Runnable Prototypes

This repository applies semiconductor verification ideas to AI assurance and applies AI/agent workflows back to verification engineering. The implementation deliberately separates deterministic baselines, model-backed proposal/review, tool acceptance, behavioral RTL evidence, and controlled comparative evaluation.

1. **Verification Copilot V8** - deterministic baseline, optional model-backed generator/reviewer roles, deterministic validation, multi-family RTL mutation benchmarks, and repeated-trial workflow comparison.
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
assurance-demo corpus-eval --rtl-root benchmarks/rtl --trials 3
```

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

The workflow performs separate generator and reviewer model calls. The reviewer can return `ACCEPT_FOR_TOOL_CHECK`, `REVISE`, or `ABSTAIN`. A draft reaches `accepted_for_human_review=true` only when the reviewer sends it forward and the configured deterministic validator returns `VALID`. This remains a human-review gate, not design sign-off.

## Verification Copilot V8

### Deterministic baseline

[`verification_copilot.py`](src/assurance_portfolio/verification_copilot.py) preserves requirement IDs, performs requirement-quality review, translates a deliberately narrow complete-match grammar into SVA-style drafts, generates pattern-specific scenarios and coverage goals, and independently reviews generated artifacts.

A requirement is marked **SUPPORTED** only when its complete normalized text matches an explicit grammar. Unsupported trailing semantics force fallback rather than being silently discarded.

### Model-backed roles

[`agentic_verification.py`](src/assurance_portfolio/agentic_verification.py) adds separate generator and adversarial reviewer roles behind a minimal backend interface. `OpenAIResponsesBackend` provides live calls and `ScriptedModelBackend` provides deterministic offline/CI testing. Separate calls do not guarantee statistical independence when both roles use the same model family.

### Deterministic validation

[`sva_validation.py`](src/assurance_portfolio/sva_validation.py) provides a shallow structural validator and a concrete Verilator-backed assertion/lint adapter. Tool acceptance is recorded separately from semantic correctness against RTL.

## Behavioral evidence layers

### V6 request/grant mutation proof

[`rtl_behavioral.py`](src/assurance_portfolio/rtl_behavioral.py) executes the request/grant bounded-response requirement against:

- `handshake_good.sv`, expected to pass, and
- `handshake_late_bug.sv`, expected to fail.

Compile/tool failures do not count as mutation detection.

### V7 four-condition comparison

[`controlled_evaluation.py`](src/assurance_portfolio/controlled_evaluation.py) compares deterministic, single-model, generator+reviewer, and generator+reviewer+tool-gated workflows on the same request/grant mutation pair. It distinguishes mutation detection from false-positive behavior and records reviewer escalation separately from execution.

## V8 multi-family benchmark corpus

V8 broadens the behavioral corpus to three temporal requirement families, each with known-good and mutated RTL:

| Case | Family | Requirement |
|---|---|---|
| BR-001 | bounded response | `grant shall assert within 4 cycles after request` |
| PR-001 | prohibition | `grant shall never assert while reset` |
| IM-001 | immediate implication | `if request is high, busy shall be high` |

The new RTL fixtures are:

- `handshake_good.sv` / `handshake_late_bug.sv`
- `prohibition_good.sv` / `prohibition_bug.sv`
- `implication_good.sv` / `implication_bug.sv`

[`corpus_benchmark.py`](src/assurance_portfolio/corpus_benchmark.py) parses the supported candidate assertion families and executes each candidate against the matching good/mutated RTL pair with Icarus Verilog.

[`corpus_evaluation.py`](src/assurance_portfolio/corpus_evaluation.py) applies the same four workflow conditions across the full corpus and aggregates repeated trials.

Per-condition metrics include:

- generation-failure rate,
- reviewer escalation rate,
- behavioral-execution rate,
- **full-correct rate**: good RTL passes and mutation is detected,
- mutation-detection rate among executed cases,
- false-positive rate on known-good RTL,
- mean elapsed wall-clock time.

A candidate that detects a mutation but falsely rejects known-good RTL is **not** counted as fully correct.

### Scripted/offline repeated trials

```bash
assurance-demo corpus-eval --rtl-root benchmarks/rtl --trials 3
```

This mode validates the multi-family evaluation and aggregation machinery. It deliberately includes a too-strict bounded-response candidate and a reviewer escalation so that false-positive and abstention metrics are exercised. It is **not empirical model-quality evidence**.

### Live-model repeated trials

```bash
python -m pip install -e ".[agentic]"
export OPENAI_API_KEY="..."
export OPENAI_MODEL="..."
assurance-demo corpus-eval-live --rtl-root benchmarks/rtl --trials 3
```

Live runs use fresh model calls for every case and trial and record `evidence_kind=live_model`, the configured model label, and prompt version `v8.0`. A small number of runs on this toy corpus is still not sufficient to claim workflow superiority.

See [`benchmarks/V8_CORPUS.md`](benchmarks/V8_CORPUS.md).

## CI

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

GitHub Actions runs:

- Python 3.10 unit tests and CLI smoke tests,
- Python 3.11 unit tests and CLI smoke tests,
- Python 3.12 unit tests and CLI smoke tests,
- a real Verilator assertion-validation job,
- the V6 Icarus request/grant mutation proof,
- the V7 scripted four-condition comparison, and
- a repeated V8 multi-family corpus evaluation using the real Icarus RTL runner.

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

## What V8 proves - and what it does not

V8 demonstrates in runnable code that the same four-condition evaluation protocol can operate across several temporal requirement families, execute multiple labelled RTL mutations, distinguish false positives from defect detection, preserve reviewer escalation as a separate outcome, and aggregate repeated trials with explicit evidence/model/prompt metadata.

V8 still does **not** prove that model-backed generation is superior to the deterministic baseline, general natural-language-to-SVA correctness, production EDA equivalence, or SoC-scale transfer. The scripted repeated trials are evaluation-plumbing evidence only. Defensible model-performance claims require a larger independently designed corpus, more mutations per family, repeated live-model trials, usage telemetry, fixed model/prompt configuration, and blinded expert review.
