# V7 Controlled Evaluation

V7 adds a common measurement harness for four verification workflows applied to the same bounded request/grant requirement and the same labelled RTL fixtures.

## Conditions

1. `deterministic` — the complete-match deterministic grammar baseline.
2. `single_model` — one model-backed generator with no independent review.
3. `generator_reviewer` — model generator plus independent reviewer; reviewer `REVISE` or `ABSTAIN` withholds execution.
4. `generator_reviewer_tool` — generator plus reviewer plus deterministic structural gate before behavioural scoring.

The current V7 behavioural evaluator recognizes the bounded assertion form:

```systemverilog
assert property (@(posedge clk) request |-> ##[1:N] grant);
```

and executes the candidate bound `N` against:

- `handshake_good.sv`, which must satisfy the intended four-cycle requirement; and
- `handshake_late_bug.sv`, which contains the labelled late-grant mutation.

## Metrics

Each condition records:

- whether generation succeeded,
- reviewer disposition when applicable,
- assertion structural validity,
- whether behavioural evaluation was executed,
- whether the known-good RTL passed,
- whether the seeded mutation was detected,
- false-positive count on known-good RTL,
- elapsed wall-clock time, and
- token/cost fields only when usage telemetry is available.

Missing usage telemetry remains `null`; the harness does not estimate or invent token cost.

## Offline scripted comparison

```bash
assurance-demo controlled-eval --rtl-root benchmarks/rtl
```

This mode deliberately uses scripted model outputs to validate the **measurement plumbing**, not to claim model quality. The scripted cases demonstrate distinct outcomes, including a too-strict assertion that detects the mutation but also produces a false positive, a reviewer `REVISE` outcome, and an accepted tool-gated candidate.

CI runs this mode with Icarus Verilog after the V6 RTL mutation proof.

## Live-model comparison

Install the optional model dependency, configure the SDK normally, and run:

```bash
python -m pip install -e ".[agentic]"
export OPENAI_API_KEY="..."
export OPENAI_MODEL="..."
assurance-demo controlled-eval-live --rtl-root benchmarks/rtl
```

This uses the same evaluator but replaces scripted generator/reviewer responses with live model calls. A single run is an observation, not evidence of superiority. Meaningful comparison requires repeated trials, fixed datasets, recorded model/version/prompt configuration, and statistical reporting.

## Trust boundary

V7 does **not** claim that the model-backed conditions outperform the deterministic baseline. It establishes a shared comparison protocol and executable measurement harness. The current RTL dataset contains one bounded-response block and one labelled mutation, so external validity remains intentionally limited.

Future controlled studies should expand the mutation set, requirement families, reset/concurrency cases, repeated model trials, usage telemetry, and blinded human-review measurements.
