# AI Assurance & Agentic Verification Portfolio - Runnable Prototypes

This repository applies semiconductor verification ideas to AI assurance and applies AI/agent workflows back to verification engineering. It deliberately separates deterministic baselines, model-backed proposal/review, tool acceptance, behavioral RTL evidence, comparative evaluation, and experiment reporting.

1. **Verification Copilot V9** - deterministic baseline, optional model-backed generator/reviewer roles, deterministic validation, multi-family RTL mutation benchmarks, repeated-trial comparison, model usage telemetry, and reproducible experiment bundles.
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

## Verification Copilot V9

### Deterministic baseline

[`verification_copilot.py`](src/assurance_portfolio/verification_copilot.py) preserves requirement IDs, performs requirement-quality review, translates a deliberately narrow complete-match grammar into SVA-style drafts, generates pattern-specific scenarios and coverage goals, and independently reviews generated artifacts. Unsupported trailing semantics force fallback rather than being silently discarded.

### Model-backed roles and usage telemetry

[`agentic_verification.py`](src/assurance_portfolio/agentic_verification.py) adds separate generator and adversarial reviewer roles behind a minimal backend interface. `OpenAIResponsesBackend` performs live calls; `ScriptedModelBackend` provides deterministic offline/CI testing.

V9 additionally records cumulative request and token usage when a backend provides it. The OpenAI Responses backend captures input, output, and total token counts from the API response. Scripted backends record request counts but explicitly leave token telemetry unavailable.

Separate model calls do not guarantee statistical independence when both roles use the same model family.

### Deterministic validation

[`sva_validation.py`](src/assurance_portfolio/sva_validation.py) provides a shallow structural validator and a concrete Verilator-backed assertion/lint adapter. Tool acceptance is recorded separately from semantic correctness against RTL.

## Behavioral evidence layers

### V6 request/grant mutation proof

[`rtl_behavioral.py`](src/assurance_portfolio/rtl_behavioral.py) executes the request/grant bounded-response requirement against a known-good implementation and a deliberately late-grant mutation. Compile/tool failures do not count as mutation detection.

### V7 four-condition comparison

[`controlled_evaluation.py`](src/assurance_portfolio/controlled_evaluation.py) compares:

1. deterministic,
2. single model,
3. generator + reviewer,
4. generator + reviewer + tool gate.

The evaluator distinguishes mutation detection from false-positive behavior and records reviewer escalation separately from execution.

### V8 multi-family benchmark corpus

V8 broadened the behavioral corpus to three temporal requirement families, each with known-good and mutated RTL:

| Case | Family | Requirement |
|---|---|---|
| BR-001 | bounded response | `grant shall assert within 4 cycles after request` |
| PR-001 | prohibition | `grant shall never assert while reset` |
| IM-001 | immediate implication | `if request is high, busy shall be high` |

[`corpus_benchmark.py`](src/assurance_portfolio/corpus_benchmark.py) parses supported candidate assertion families and executes each candidate against the matching good/mutated RTL pair with Icarus Verilog.

[`corpus_evaluation.py`](src/assurance_portfolio/corpus_evaluation.py) applies the four workflow conditions across the corpus and aggregates repeated trials. Metrics include generation failure, reviewer escalation, behavioral execution, full-correct rate, mutation detection, false positives, elapsed time, model requests, and token usage when available.

A candidate that detects a mutation but falsely rejects known-good RTL is **not** counted as fully correct.

## V9 reproducible experiment artifacts

V9 converts repeated corpus runs into reusable evidence bundles rather than console-only output.

A scripted/offline run can opt in:

```bash
assurance-demo corpus-eval \
  --rtl-root benchmarks/rtl \
  --trials 3 \
  --output-root artifacts/experiments
```

A live-model run writes an experiment bundle by default:

```bash
python -m pip install -e ".[agentic]"
export OPENAI_API_KEY="..."
export OPENAI_MODEL="..."
assurance-demo corpus-eval-live \
  --rtl-root benchmarks/rtl \
  --trials 3 \
  --output-root artifacts/experiments
```

Each deterministic run directory contains:

- `manifest.json` - run ID, evidence/model/prompt configuration, git SHA where available, invocation and environment;
- `trials.json` - complete structured trial output;
- `summary.json` - aggregate metrics;
- `results.csv` - row-level case/workflow observations;
- `aggregates.csv` - per-condition summary metrics;
- `REPORT.md` - a compact human-readable report with an explicit interpretation boundary.

The run ID is a hash of experiment identity fields rather than a timestamp. Dollar cost is deliberately left unset because pricing is model- and date-dependent; historical token counts should be joined to an explicitly dated pricing table rather than silently repriced.

See [`benchmarks/V8_CORPUS.md`](benchmarks/V8_CORPUS.md) and [`benchmarks/V9_EXPERIMENT_ARTIFACTS.md`](benchmarks/V9_EXPERIMENT_ARTIFACTS.md).

## CI

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

GitHub Actions runs:

- Python 3.10, 3.11, and 3.12 unit tests and CLI smoke tests;
- real Verilator assertion validation;
- the V6 Icarus request/grant mutation proof;
- the V7 four-condition comparison;
- repeated V8 multi-family corpus evaluation with the real Icarus runner; and
- V9 experiment-bundle creation and artifact-shape checks.

CI does not use model API credentials.

## Agent Trace Assurance V4

Agent Trace Assurance treats each execution as an ordered event trace and evaluates explicit safety properties at relevant steps. It includes scoped and single-use grants, optional event-count expiry, strict scope matching, high-risk classification checks, required proposer/approver identities, shutdown compliance, and PASS/FAIL/INCONCLUSIVE results.

Current coverage is **property-exercise coverage**, not full functional/assertion/vacuity coverage. Authorization/evidence events are still assumed trustworthy observations; actor authority, evidence provenance/quality, and trace integrity remain future work.

Implementation: [`trace_assurance.py`](src/assurance_portfolio/trace_assurance.py)

## CloudGuard AI V3

CloudGuard remains a small Responsible-AI demonstration built around transparent weighted threat signals, heuristic evidence strength, top contributing reasons, named human decision/rationale capture, and a recommendation hash. Its decision API is an audit/demo mechanism rather than a production execution gate.

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

## What V9 proves - and what it does not

V9 demonstrates that repeated model/verification trials can be captured with model/prompt/evidence metadata, behavioral outcomes, false positives, escalation, latency, request counts, provider token usage when available, and reproducible machine-readable/human-readable experiment artifacts.

V9 does **not** prove that model-backed generation is superior to the deterministic baseline, general natural-language-to-SVA correctness, production EDA equivalence, or SoC-scale transfer. Scripted runs remain plumbing evidence. Live runs are observations, not statistical conclusions. Defensible comparative claims still require a larger independently designed corpus, more mutations per family, a preregistered/frozen analysis plan, repeated live trials, and blinded expert review.
