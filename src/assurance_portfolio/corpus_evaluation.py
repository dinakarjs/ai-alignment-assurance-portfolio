"""Repeated multi-family workflow evaluation for the V8 benchmark corpus."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from time import perf_counter
from typing import Callable

from .agentic_verification import ModelArtifactGenerator, ModelArtifactReviewer, ModelBackend
from .corpus_benchmark import CorpusCase, IcarusCorpusRunner, default_corpus
from .sva_validation import StructuralSVAValidator, ValidationStatus
from .verification_copilot import ArtifactGenerator, Requirement


CONDITIONS = (
    "deterministic",
    "single_model",
    "generator_reviewer",
    "generator_reviewer_tool",
)


@dataclass(frozen=True)
class CorpusWorkflowResult:
    trial_id: int
    condition: str
    case_id: str
    family: str
    assertion: str | None
    generation_succeeded: bool
    reviewer_verdict: str | None
    structural_valid: bool | None
    behavioral_executed: bool
    good_rtl_passed: bool | None
    mutation_detected: bool | None
    false_positive_count: int | None
    fully_correct: bool | None
    elapsed_seconds: float
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class CorpusTrial:
    trial_id: int
    evidence_kind: str
    model_label: str | None
    prompt_version: str
    results: tuple[CorpusWorkflowResult, ...]


@dataclass(frozen=True)
class ConditionAggregate:
    condition: str
    cases: int
    generation_failure_rate: float
    escalation_rate: float
    behavioral_execution_rate: float
    full_correct_rate: float
    mutation_detection_rate: float | None
    false_positive_rate: float | None
    mean_elapsed_seconds: float


@dataclass(frozen=True)
class CorpusEvaluationSummary:
    evidence_kind: str
    trials: int
    cases_per_trial: int
    model_label: str | None
    prompt_version: str
    aggregates: tuple[ConditionAggregate, ...]


def _requirement(case: CorpusCase) -> Requirement:
    return Requirement(case.case_id, case.requirement)


def _baseline_context(requirement: Requirement) -> dict[str, object]:
    draft = ArtifactGenerator().generate(requirement)
    return {
        "assertion": draft.assertion,
        "generation_status": draft.generation_status.value,
        "matched_pattern": draft.matched_pattern,
        "scenarios": draft.scenarios,
        "coverage_goal": draft.coverage_goal,
    }


def _stopped(
    *,
    trial_id: int,
    condition: str,
    case: CorpusCase,
    assertion: str | None,
    generation_succeeded: bool,
    reviewer_verdict: str | None,
    structural_valid: bool | None,
    started: float,
    notes: tuple[str, ...],
) -> CorpusWorkflowResult:
    return CorpusWorkflowResult(
        trial_id=trial_id,
        condition=condition,
        case_id=case.case_id,
        family=case.family.value,
        assertion=assertion,
        generation_succeeded=generation_succeeded,
        reviewer_verdict=reviewer_verdict,
        structural_valid=structural_valid,
        behavioral_executed=False,
        good_rtl_passed=None,
        mutation_detected=None,
        false_positive_count=None,
        fully_correct=None,
        elapsed_seconds=perf_counter() - started,
        notes=notes,
    )


def _execute(
    *,
    trial_id: int,
    condition: str,
    case: CorpusCase,
    assertion: str,
    reviewer_verdict: str | None,
    started: float,
    rtl_root: str | Path,
    runner: IcarusCorpusRunner,
    notes: tuple[str, ...] = (),
) -> CorpusWorkflowResult:
    structural = StructuralSVAValidator().validate(assertion)
    if structural.status is not ValidationStatus.VALID:
        return _stopped(
            trial_id=trial_id,
            condition=condition,
            case=case,
            assertion=assertion,
            generation_succeeded=True,
            reviewer_verdict=reviewer_verdict,
            structural_valid=False,
            started=started,
            notes=notes + (f"structural validation failed: {structural.detail}",),
        )
    result = runner.evaluate(case, assertion, rtl_root)
    behavioral = result.good_rtl_passed is not None and result.mutation_detected is not None
    return CorpusWorkflowResult(
        trial_id=trial_id,
        condition=condition,
        case_id=case.case_id,
        family=case.family.value,
        assertion=assertion,
        generation_succeeded=True,
        reviewer_verdict=reviewer_verdict,
        structural_valid=True,
        behavioral_executed=behavioral,
        good_rtl_passed=result.good_rtl_passed,
        mutation_detected=result.mutation_detected,
        false_positive_count=result.false_positive_count,
        fully_correct=result.fully_correct if behavioral else None,
        elapsed_seconds=perf_counter() - started,
        notes=notes + (result.detail,),
    )


def _deterministic(
    trial_id: int, case: CorpusCase, *, rtl_root: str | Path, runner: IcarusCorpusRunner
) -> CorpusWorkflowResult:
    started = perf_counter()
    draft = ArtifactGenerator().generate(_requirement(case))
    return _execute(
        trial_id=trial_id,
        condition="deterministic",
        case=case,
        assertion=draft.assertion,
        reviewer_verdict=None,
        started=started,
        rtl_root=rtl_root,
        runner=runner,
        notes=(f"deterministic status={draft.generation_status.value}",),
    )


def _single_model(
    trial_id: int,
    case: CorpusCase,
    *,
    backend: ModelBackend,
    rtl_root: str | Path,
    runner: IcarusCorpusRunner,
) -> CorpusWorkflowResult:
    started = perf_counter()
    requirement = _requirement(case)
    try:
        draft = ModelArtifactGenerator(backend).generate(requirement, _baseline_context(requirement))
    except (ValueError, RuntimeError) as exc:
        return _stopped(
            trial_id=trial_id,
            condition="single_model",
            case=case,
            assertion=None,
            generation_succeeded=False,
            reviewer_verdict=None,
            structural_valid=None,
            started=started,
            notes=(f"generation failed: {exc}",),
        )
    return _execute(
        trial_id=trial_id,
        condition="single_model",
        case=case,
        assertion=draft.assertion,
        reviewer_verdict=None,
        started=started,
        rtl_root=rtl_root,
        runner=runner,
    )


def _reviewed(
    trial_id: int,
    condition: str,
    case: CorpusCase,
    *,
    generator_backend: ModelBackend,
    reviewer_backend: ModelBackend,
    rtl_root: str | Path,
    runner: IcarusCorpusRunner,
    tool_gate: bool,
) -> CorpusWorkflowResult:
    started = perf_counter()
    requirement = _requirement(case)
    try:
        draft = ModelArtifactGenerator(generator_backend).generate(requirement, _baseline_context(requirement))
        review = ModelArtifactReviewer(reviewer_backend).review(requirement, draft)
    except (ValueError, RuntimeError) as exc:
        return _stopped(
            trial_id=trial_id,
            condition=condition,
            case=case,
            assertion=None,
            generation_succeeded=False,
            reviewer_verdict=None,
            structural_valid=None,
            started=started,
            notes=(f"workflow failed: {exc}",),
        )
    if review.verdict != "ACCEPT_FOR_TOOL_CHECK":
        return _stopped(
            trial_id=trial_id,
            condition=condition,
            case=case,
            assertion=draft.assertion,
            generation_succeeded=True,
            reviewer_verdict=review.verdict,
            structural_valid=None,
            started=started,
            notes=("execution withheld by reviewer",) + review.findings,
        )
    if tool_gate:
        structural = StructuralSVAValidator().validate(draft.assertion)
        if structural.status is not ValidationStatus.VALID:
            return _stopped(
                trial_id=trial_id,
                condition=condition,
                case=case,
                assertion=draft.assertion,
                generation_succeeded=True,
                reviewer_verdict=review.verdict,
                structural_valid=False,
                started=started,
                notes=(f"tool gate rejected assertion: {structural.detail}",),
            )
        notes = ("reviewer and structural tool gate accepted candidate",)
    else:
        notes = ("reviewer accepted; RTL scoring is evaluation-only",)
    return _execute(
        trial_id=trial_id,
        condition=condition,
        case=case,
        assertion=draft.assertion,
        reviewer_verdict=review.verdict,
        started=started,
        rtl_root=rtl_root,
        runner=runner,
        notes=notes,
    )


def run_corpus_trial(
    trial_id: int,
    *,
    single_backend_factory: Callable[[CorpusCase], ModelBackend],
    reviewed_generator_factory: Callable[[CorpusCase], ModelBackend],
    reviewer_factory: Callable[[CorpusCase], ModelBackend],
    tool_generator_factory: Callable[[CorpusCase], ModelBackend],
    tool_reviewer_factory: Callable[[CorpusCase], ModelBackend],
    corpus: tuple[CorpusCase, ...] | None = None,
    rtl_root: str | Path = "benchmarks/rtl",
    runner_factory: Callable[[], IcarusCorpusRunner] = IcarusCorpusRunner,
    evidence_kind: str = "scripted_offline",
    model_label: str | None = None,
    prompt_version: str = "v8.0",
) -> CorpusTrial:
    active_corpus = corpus or default_corpus()
    results: list[CorpusWorkflowResult] = []
    for case in active_corpus:
        results.append(_deterministic(trial_id, case, rtl_root=rtl_root, runner=runner_factory()))
        results.append(
            _single_model(
                trial_id, case,
                backend=single_backend_factory(case),
                rtl_root=rtl_root,
                runner=runner_factory(),
            )
        )
        results.append(
            _reviewed(
                trial_id, "generator_reviewer", case,
                generator_backend=reviewed_generator_factory(case),
                reviewer_backend=reviewer_factory(case),
                rtl_root=rtl_root,
                runner=runner_factory(),
                tool_gate=False,
            )
        )
        results.append(
            _reviewed(
                trial_id, "generator_reviewer_tool", case,
                generator_backend=tool_generator_factory(case),
                reviewer_backend=tool_reviewer_factory(case),
                rtl_root=rtl_root,
                runner=runner_factory(),
                tool_gate=True,
            )
        )
    return CorpusTrial(
        trial_id=trial_id,
        evidence_kind=evidence_kind,
        model_label=model_label,
        prompt_version=prompt_version,
        results=tuple(results),
    )


def summarize_trials(trials: tuple[CorpusTrial, ...]) -> CorpusEvaluationSummary:
    if not trials:
        raise ValueError("at least one trial is required")
    first = trials[0]
    if any(t.evidence_kind != first.evidence_kind for t in trials):
        raise ValueError("cannot aggregate mixed evidence kinds")
    if any(t.prompt_version != first.prompt_version for t in trials):
        raise ValueError("cannot aggregate mixed prompt versions")
    if any(t.model_label != first.model_label for t in trials):
        raise ValueError("cannot aggregate mixed model labels")

    aggregates: list[ConditionAggregate] = []
    for condition in CONDITIONS:
        rows = [row for trial in trials for row in trial.results if row.condition == condition]
        generated_failures = sum(not row.generation_succeeded for row in rows)
        escalations = sum(row.reviewer_verdict in {"REVISE", "ABSTAIN"} for row in rows)
        executed = [row for row in rows if row.behavioral_executed]
        fully_correct = sum(row.fully_correct is True for row in rows)
        mutations = [row for row in executed if row.mutation_detected is not None]
        mutation_rate = (
            sum(row.mutation_detected is True for row in mutations) / len(mutations)
            if mutations else None
        )
        false_positive_rate = (
            sum((row.false_positive_count or 0) > 0 for row in executed) / len(executed)
            if executed else None
        )
        aggregates.append(
            ConditionAggregate(
                condition=condition,
                cases=len(rows),
                generation_failure_rate=generated_failures / len(rows),
                escalation_rate=escalations / len(rows),
                behavioral_execution_rate=len(executed) / len(rows),
                full_correct_rate=fully_correct / len(rows),
                mutation_detection_rate=mutation_rate,
                false_positive_rate=false_positive_rate,
                mean_elapsed_seconds=mean(row.elapsed_seconds for row in rows),
            )
        )

    conditions_per_trial = len(first.results) // len(CONDITIONS)
    return CorpusEvaluationSummary(
        evidence_kind=first.evidence_kind,
        trials=len(trials),
        cases_per_trial=conditions_per_trial,
        model_label=first.model_label,
        prompt_version=first.prompt_version,
        aggregates=tuple(aggregates),
    )
