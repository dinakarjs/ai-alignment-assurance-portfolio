# V9 Experiment Evidence Bundles

V9 turns repeated corpus runs into auditable experiment artifacts rather than console-only output.

## What is recorded

Each corpus workflow result records the existing behavioral metrics plus model-use telemetry when the backend exposes it:

- model request count,
- input tokens,
- output tokens,
- total tokens,
- whether usage telemetry was available,
- elapsed wall-clock time,
- model label,
- prompt version,
- evidence kind,
- trial ID, condition, case, and requirement family.

The OpenAI Responses backend reads token usage from the API response. Scripted backends record request counts but deliberately do not invent token counts.

## Experiment bundle

`corpus-eval-live` writes to `artifacts/experiments` by default. Scripted runs can opt in with `--output-root`.

Each run directory contains:

- `manifest.json` — run ID, evidence kind, model/prompt configuration, git SHA where available, command, environment, and explicit cost policy;
- `trials.json` — complete structured trial outputs;
- `summary.json` — aggregate condition metrics;
- `results.csv` — row-level workflow/case observations;
- `aggregates.csv` — compact per-condition metrics;
- `REPORT.md` — human-readable results table and interpretation boundary.

The run ID is a deterministic hash of the experiment identity fields rather than a timestamp. Re-running the same recorded configuration on the same commit resolves to the same experiment directory; the manifest still records execution time.

## Commands

Scripted/offline bundle:

```bash
assurance-demo corpus-eval \
  --rtl-root benchmarks/rtl \
  --trials 3 \
  --output-root artifacts/experiments
```

Live-model bundle:

```bash
python -m pip install -e ".[agentic]"
export OPENAI_API_KEY="..."
export OPENAI_MODEL="..."
assurance-demo corpus-eval-live \
  --rtl-root benchmarks/rtl \
  --trials 3 \
  --output-root artifacts/experiments
```

## Cost policy

V9 does **not** convert tokens to dollars. Model prices are external, model-specific, and time-dependent. `manifest.json` therefore records `cost_usd: null` and explains the policy. A future pricing analysis should join recorded token usage to an explicitly dated pricing table rather than silently applying current prices to historical runs.

## Evidence boundary

A reproducible artifact does not make a small experiment statistically meaningful. Scripted/offline bundles remain plumbing evidence. Live-model bundles are observations. Defensible comparative claims still require a larger independently designed corpus, repeated trials, frozen model/prompt configuration, expert review, and an analysis plan defined before inspecting results.
