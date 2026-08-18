"""Write auditable experiment bundles for corpus evaluation runs."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import csv
import hashlib
import json
from pathlib import Path
import platform
import subprocess
from typing import Iterable

from .corpus_evaluation import CorpusEvaluationSummary, CorpusTrial


ARTIFACT_SCHEMA_VERSION = "v9.0"


def _git_sha() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _canonical_run_id(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _flatten_rows(trials: Iterable[CorpusTrial]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for trial in trials:
        for result in trial.results:
            row = asdict(result)
            row.update(
                {
                    "evidence_kind": trial.evidence_kind,
                    "model_label": trial.model_label,
                    "prompt_version": trial.prompt_version,
                    "notes": " | ".join(result.notes),
                }
            )
            rows.append(row)
    return rows


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _markdown(summary: CorpusEvaluationSummary, manifest: dict[str, object]) -> str:
    lines = [
        "# Verification Corpus Experiment Report",
        "",
        f"**Run ID:** `{manifest['run_id']}`  ",
        f"**Evidence kind:** `{summary.evidence_kind}`  ",
        f"**Model:** `{summary.model_label or 'not applicable'}`  ",
        f"**Prompt version:** `{summary.prompt_version}`  ",
        f"**Trials:** {summary.trials}  ",
        f"**Cases per trial:** {summary.cases_per_trial}",
        "",
        "## Aggregate results",
        "",
        "| Condition | Full-correct | Mutation detection | False-positive | Escalation | Execution | Requests | Input tokens | Output tokens |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in summary.aggregates:
        mutation = "n/a" if item.mutation_detection_rate is None else f"{item.mutation_detection_rate:.3f}"
        false_positive = "n/a" if item.false_positive_rate is None else f"{item.false_positive_rate:.3f}"
        input_tokens = "n/a" if item.input_tokens is None else str(item.input_tokens)
        output_tokens = "n/a" if item.output_tokens is None else str(item.output_tokens)
        lines.append(
            f"| {item.condition} | {item.full_correct_rate:.3f} | {mutation} | {false_positive} | "
            f"{item.escalation_rate:.3f} | {item.behavioral_execution_rate:.3f} | {item.model_requests} | "
            f"{input_tokens} | {output_tokens} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            "This file reports observations from the recorded configuration. Scripted/offline evidence validates evaluation plumbing, not model quality. Live-model results are still limited by corpus size, trial count, model configuration, and benchmark design. No workflow-superiority claim follows from this report alone.",
            "",
            "Dollar cost is intentionally not estimated because pricing is model- and date-dependent; token counts are recorded when the provider returns usage telemetry.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_experiment_bundle(
    trials: tuple[CorpusTrial, ...],
    summary: CorpusEvaluationSummary,
    *,
    output_root: str | Path,
    command: str,
    rtl_root: str,
) -> Path:
    """Write manifest, raw results, summary tables, and a compact report."""

    if not trials:
        raise ValueError("at least one trial is required")
    identity = {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "evidence_kind": summary.evidence_kind,
        "model_label": summary.model_label,
        "prompt_version": summary.prompt_version,
        "trials": summary.trials,
        "cases_per_trial": summary.cases_per_trial,
        "rtl_root": rtl_root,
        "git_sha": _git_sha(),
    }
    run_id = _canonical_run_id(identity)
    output = Path(output_root) / run_id
    output.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, object] = {
        **identity,
        "run_id": run_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "command": command,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "cost_usd": None,
        "cost_note": "Not estimated; provider pricing is model/date dependent.",
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    (output / "trials.json").write_text(
        json.dumps([asdict(item) for item in trials], indent=2), encoding="utf-8"
    )
    (output / "summary.json").write_text(
        json.dumps(asdict(summary), indent=2), encoding="utf-8"
    )

    raw_rows = _flatten_rows(trials)
    _write_csv(output / "results.csv", raw_rows)
    aggregate_rows = [asdict(item) for item in summary.aggregates]
    _write_csv(output / "aggregates.csv", aggregate_rows)
    (output / "REPORT.md").write_text(_markdown(summary, manifest), encoding="utf-8")
    return output
