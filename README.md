# AI Assurance & Agentic Verification Portfolio - Runnable Prototypes

This repository applies semiconductor verification ideas to AI assurance and applies AI/agent workflows back to verification engineering. It now separates a deterministic reference baseline from an optional model-backed verification path:

1. **Verification Copilot V5** - V4 deterministic grammar/review baseline plus optional model-backed generator and independent reviewer roles, deterministic assertion validation, and seeded benchmark fixtures.
2. **Agent Trace Assurance Engine V4** - a deterministic policy monitor for ordered agent-event traces with scoped/consumable/expiring grants, high-risk classification checks, independent approval checks, shutdown monitoring, and PASS/FAIL/INCONCLUSIVE semantics.
3. **CloudGuard AI V3** - transparent cloud-threat scoring, evidence-strength semantics, human decision capture, and auditable recommendations.

These are research prototypes, not production EDA, security, alignment, or autonomous sign-off systems.

## Quick start - deterministic/offline

Python 3.10 or newer is required.

```bash
python -m pip install -e .
assurance-demo copilot examples/requirements.json
assurance-demo trace examples/agent_trace.json
assurance-demo cloudguard examples/cloudguard_incident.json
assurance-demo benchmark
```

## Model-backed V5 path

Install the optional agentic dependency and configure the OpenAI SDK normally:

```bash
python -m pip install -e ".[agentic]"
export OPENAI_API_KEY="..."
export OPENAI_MODEL="..."
assurance-demo agentic examples/requirements.json --validator structural
```

If Verilator is installed, the same workflow can require that concrete tool to accept the proposed assertion:

```bash
assurance-demo agentic examples/requirements.json --validator verilator
```

The model-backed workflow performs **separate generator and reviewer model calls**. The reviewer can return `ACCEPT_FOR_TOOL_CHECK`, `REVISE`, or `ABSTAIN`. A draft is marked `accepted_for_human_review=true` only when the reviewer sends it forward **and** the configured deterministic validator returns `VALID`. This remains a human-review gate, not design sign-off.

Implementation: [`agentic_verification.py`](src/assurance_portfolio/agentic_verification.py)

## Test and CI

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

GitHub Actions runs the unit suite and CLI smoke tests on Python 3.10, 3.11, and 3.12. A separate CI job installs Verilator and requires a representative immediate-implication assertion to be accepted by the real tool adapter. CI does not use API credentials; model orchestration is tested with deterministic scripted backends.

## Verification Copilot V5

### Deterministic V4 baseline

The dependency-free baseline in [`verification_copilot.py`](src/assurance_portfolio/verification_copilot.py) preserves requirement IDs, reviews requirement quality, translates a deliberately narrow complete-match grammar into SVA-style drafts, generates pattern-specific scenarios/coverage goals, and independently reviews generated artifacts.

A requirement is marked **SUPPORTED** only when its complete normalized text matches an explicit grammar. For example:

```text
grant shall assert within 4 cycles after request unless reset or abort
```

falls back rather than silently dropping `unless reset or abort`.

Supported deterministic grammar families currently include bounded response, alternate no-later-than phrasing, conditional bounded response, prohibition, immediate implication, and persistence-until-release.

### Model-backed roles

[`agentic_verification.py`](src/assurance_portfolio/agentic_verification.py) adds bounded model interfaces without replacing the deterministic baseline:

```text
Requirement
    |
    +--> Deterministic V4 baseline context
    |
    +--> Model Generator --------> candidate assertion/scenarios/assumptions
                                      |
                                      v
                              Independent Model Reviewer
                         REVISE / ABSTAIN / ACCEPT_FOR_TOOL_CHECK
                                      |
                                      v
                              Deterministic Validator
                                      |
                                      v
                           Human-review candidate only
```

The generator and reviewer use distinct backend instances. The included `OpenAIResponsesBackend` performs live model calls; `ScriptedModelBackend` provides reproducible CI/offline testing. Role separation does not guarantee model-level independence if both calls use the same model family, so the output records both backend identities and still requires deterministic validation.

### Assertion validation

[`sva_validation.py`](src/assurance_portfolio/sva_validation.py) provides two explicit validation levels:

- **StructuralSVAValidator** - dependency-free checks for obvious malformed/fallback drafts. It is not an SVA parser.
- **VerilatorSVAValidator** - builds a standalone probe module and invokes installed Verilator in SystemVerilog assertion/lint mode. A `VALID` result means that assertion was accepted by that concrete tool/version; it does not establish universal IEEE-SVA semantics or correctness against a target RTL design.

V5 therefore distinguishes three different claims that should not be conflated:

1. **model proposal** - a candidate artifact,
2. **tool acceptance** - syntax/tool support from a concrete validator,
3. **semantic design correctness** - still requires execution against reference traces/RTL and expert review.

## Seeded verification benchmark

`assurance-demo benchmark` runs a small dependency-free labelled trace benchmark for:

- `grant shall assert within 4 cycles after request`, and
- `grant shall never assert while reset`.

It reports accuracy, seeded-defect detection rate, and false positives for the reference monitors. This is a reproducible baseline, **not** an RTL simulation result.

The [`benchmarks/rtl`](benchmarks/rtl) directory also contains:

- `handshake_good.sv` - intended bounded-response behavior,
- `handshake_late_bug.sv` - a deliberately seeded late-grant defect.

Those RTL files are fixtures for the next simulator/formal benchmark step. V5 does not yet claim behavioural detection of the RTL mutation. See [`benchmarks/README.md`](benchmarks/README.md).

## Agent Trace Assurance V4

Agent Trace Assurance treats each execution as an ordered event trace and evaluates explicit safety properties at relevant steps.

V4 includes:

- normalized action identifiers,
- transaction/action IDs for authorization and evidence,
- single-use authorization and evidence consumption,
- optional event-count expiry,
- strict scope matching,
- rejection of `high_risk=true` actions that are not also classified sensitive,
- continued evaluation of stronger high-risk controls even after that classification error,
- required proposer and approver identity for independence evaluation,
- shutdown compliance with audit/status exceptions, and
- PASS/FAIL/INCONCLUSIVE results.

Current coverage is **property-exercise coverage**, not full functional/assertion/vacuity coverage. Authorization/evidence events are still assumed trustworthy observations; actor authority, evidence provenance/quality, and trace integrity are future work.

Implementation: [`trace_assurance.py`](src/assurance_portfolio/trace_assurance.py)

## CloudGuard AI V3

CloudGuard remains a small Responsible-AI demonstration built around transparent weighted threat signals, heuristic evidence strength, top contributing reasons, named human decision/rationale capture, and a recommendation hash.

Its decision API is an audit/demo mechanism rather than a production execution gate. The explanation is intentionally described as **SHAP-style additive attribution**, not fitted SHAP on a trained production model.

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

## What V5 proves - and what it does not

V5 now demonstrates, in runnable code:

- a deterministic verification baseline,
- separate model-backed generator/reviewer roles,
- strict JSON contracts and reviewer abstention/revision states,
- deterministic acceptance gating,
- a real Verilator tool adapter exercised in CI,
- a reproducible seeded trace benchmark, and
- labelled RTL mutation fixtures.

V5 **does not yet prove** that the model-backed workflow improves assertion correctness, defect detection, vacuity, coverage, or engineering productivity. The next research milestone is behavioural execution against the RTL fixtures and a controlled comparison of deterministic, single-model, and role-separated workflows using measured outcomes, latency/cost, and human review effort.
