# V8 Multi-Family RTL Benchmark Corpus

V8 broadens the controlled evaluation from one request/grant mutation pair to three requirement families. Every case contains a known-good RTL implementation and one labelled mutation.

| Case | Requirement family | Requirement | Good RTL | Mutation RTL |
|---|---|---|---|---|
| BR-001 | bounded response | `grant shall assert within 4 cycles after request` | `handshake_good.sv` | `handshake_late_bug.sv` |
| PR-001 | prohibition | `grant shall never assert while reset` | `prohibition_good.sv` | `prohibition_bug.sv` |
| IM-001 | immediate implication | `if request is high, busy shall be high` | `implication_good.sv` | `implication_bug.sv` |

## Evaluation conditions

Each case is evaluated under four workflow conditions:

1. deterministic grammar baseline,
2. single-model generation,
3. generator + reviewer,
4. generator + reviewer + structural tool gate.

The candidate assertion is then evaluated against the case-specific good and mutated RTL when the workflow allows execution.

## Metrics

V8 records per-case outcomes and aggregates them across repeated trials:

- generation-failure rate,
- reviewer escalation rate (`REVISE` / `ABSTAIN`),
- behavioral-execution rate,
- full-correct rate (good RTL passes **and** mutation is detected),
- mutation-detection rate among executed cases,
- false-positive rate on known-good RTL,
- mean elapsed wall-clock time.

A candidate that detects a mutation but fails known-good RTL is not counted as fully correct.

## Scripted/offline repeated trials

```bash
assurance-demo corpus-eval --rtl-root benchmarks/rtl --trials 3
```

The scripted mode is deliberately nontrivial:

- the single-model bounded-response candidate is too strict and creates a false positive on good RTL;
- the generator/reviewer condition escalates that bounded case instead of executing it;
- the tool-gated scripted condition uses the reference candidate.

These results validate the **evaluation and aggregation machinery**. They are not empirical evidence about model quality.

## Live-model repeated trials

```bash
python -m pip install -e ".[agentic]"
export OPENAI_API_KEY="..."
export OPENAI_MODEL="..."
assurance-demo corpus-eval-live --rtl-root benchmarks/rtl --trials 3
```

Live runs use fresh model-backed generator/reviewer calls for every case and trial. The output records `evidence_kind=live_model`, the configured model label, and prompt version `v8.0`.

A small number of trials on this toy corpus is still not sufficient to claim workflow superiority. Stronger evidence requires more requirement families, more independent mutations per family, model/prompt version pinning, usage telemetry, repeated trials, and blinded expert review.

## Trust boundary

V8 proves that the same comparison protocol can execute across several temporal requirement families and aggregate repeated observations. It does **not** establish general natural-language-to-SVA correctness, SoC-scale transfer, production EDA equivalence, or statistically significant gains from role separation.
