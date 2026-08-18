# AI Assurance & Agentic Verification Portfolio - Runnable Prototypes

This repository applies semiconductor verification ideas to AI assurance and applies AI/agent workflows back to verification engineering. The implementation now has four deliberately separated evidence layers:

1. **Verification Copilot V6** - deterministic baseline, optional model-backed generator/reviewer roles, deterministic assertion validation, synthetic trace benchmarks, and executable RTL mutation detection.
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

For the V6 RTL behavioral benchmark, install Icarus Verilog and run:

```bash
assurance-demo rtl-benchmark --rtl-root benchmarks/rtl
```

The benchmark succeeds only when the intended handshake RTL passes the four-cycle request/grant requirement and the deliberately late-grant mutation fails it.

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

The workflow performs separate generator and reviewer model calls. The reviewer can return `ACCEPT_FOR_TOOL_CHECK`, `REVISE`, or `ABSTAIN`. A draft reaches `accepted_for_human_review=true` only when the reviewer sends it forward and the configured deterministic validator returns `VALID`. This is still a human-review gate, not design sign-off.

Implementation: [`agentic_verification.py`](src/assurance_portfolio/agentic_verification.py)

## Verification Copilot V6

### Deterministic baseline

[`verification_copilot.py`](src/assurance_portfolio/verification_copilot.py) preserves requirement IDs, performs requirement-quality review, translates a deliberately narrow complete-match grammar into SVA-style drafts, generates pattern-specific scenarios and coverage goals, and independently reviews generated artifacts.

A requirement is marked **SUPPORTED** only when its complete normalized text matches an explicit grammar. For example:

```text
grant shall assert within 4 cycles after request unless reset or abort
```

falls back rather than silently discarding the unsupported qualifier.

### Model-backed roles

[`agentic_verification.py`](src/assurance_portfolio/agentic_verification.py) adds:

```text
Requirement
    |
    +--> Deterministic baseline context
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

The generator and reviewer must use distinct backend instances. The included `OpenAIResponsesBackend` performs live calls; `ScriptedModelBackend` provides reproducible offline/CI testing. Separate calls do not guarantee statistical independence when both roles use the same model family.

## Three verification evidence levels

V6 explicitly distinguishes three claims.

### 1. Synthetic trace behavior

`assurance-demo benchmark` runs labelled bounded-response and prohibition traces and reports accuracy, defect detection, and false positives. These are deterministic synthetic traces, not RTL simulation.

### 2. Standalone assertion tool acceptance

[`sva_validation.py`](src/assurance_portfolio/sva_validation.py) provides:

- `StructuralSVAValidator` for shallow dependency-free checks,
- `VerilatorSVAValidator` for a real installed Verilator lint/assertion probe.

A Verilator `VALID` result means the assertion was accepted by that concrete tool/version. It does not prove semantic correctness against RTL.

### 3. V6 behavioral RTL mutation proof

[`rtl_behavioral.py`](src/assurance_portfolio/rtl_behavioral.py) compiles and simulates two SystemVerilog designs with Icarus Verilog:

- [`handshake_good.sv`](benchmarks/rtl/handshake_good.sv) - expected to satisfy `grant shall assert within 4 cycles after request`,
- [`handshake_late_bug.sv`](benchmarks/rtl/handshake_late_bug.sv) - deliberately delays grant beyond the bound and is expected to fail.

The generated SystemVerilog testbench pulses `request`, samples `grant`, and enforces the four-cycle temporal requirement at runtime. A compile error or unavailable simulator does **not** count as successful mutation detection.

The benchmark reports:

- per-design PASS/FAIL state,
- expected outcome,
- simulator/tool version,
- mutation-detection rate,
- false-positive count,
- whether all expected outcomes were met.

GitHub Actions contains a dedicated `rtl-behavioral-proof` job that installs Icarus Verilog and runs this benchmark.

See [`benchmarks/README.md`](benchmarks/README.md).

## CI

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

GitHub Actions now runs:

- Python 3.10 unit tests and CLI smoke tests,
- Python 3.11 unit tests and CLI smoke tests,
- Python 3.12 unit tests and CLI smoke tests,
- a real Verilator assertion-validation job,
- a real Icarus Verilog behavioral RTL mutation job.

CI does not use model API credentials; model orchestration is exercised with deterministic scripted backends.

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

## What V6 proves - and what it does not

V6 demonstrates in runnable code:

- deterministic requirement-to-artifact generation and review,
- separate model-backed generator/reviewer roles,
- strict model-output contracts and abstention/revision states,
- deterministic acceptance gating,
- real Verilator tool acceptance in CI,
- reproducible synthetic trace defect benchmarks,
- real simulation of labelled RTL fixtures, and
- behavioral detection of one seeded late-grant mutation without falsely failing the intended implementation, when the dedicated RTL CI job passes.

V6 still does **not** prove that model-backed generation is superior to the deterministic baseline, that one mutation generalizes to SoC-scale verification, that generated assertions are non-vacuous across arbitrary designs, or that the workflow improves engineering productivity.

The next controlled milestone should compare deterministic, single-model, and role-separated model workflows on the same RTL mutation corpus using measured behavioral defect detection, false positives, abstention, latency/cost, and expert review effort.
