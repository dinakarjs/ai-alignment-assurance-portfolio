"""Controlled comparison harness for deterministic and model-backed verification flows.

V7 measures workflow outputs against the same bounded-response RTL fixtures. It
separates reproducible scripted/offline evidence from optional live-model runs.
No condition is declared superior merely because the harness executes.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from pathlib import Path
from time import perf_counter
from typing import Callable

from .agentic_verification import (
    ModelArtifactGenerator,
    ModelArtifactReviewer,
    ModelBackend,
    ModelDraft,
)
from .rtl_behavioral import IcarusBehavioralRunner, RTLRunStatus
from .sva_validation import StructuralSVAValidator, ValidationStatus
from .verification_copilot import ArtifactGenerator, Requirement


class WorkflowCondition(str, Enum):
    DETERMINISTIC = "deterministic"
    SINGLE_MODEL = "single_model"
    GENERATOR_REVIEWER = "generator_reviewer"
    GENERATOR_REVIEWER_TOOL = "generator_reviewer_tool"


@dataclass(frozen=True)
class WorkflowEvaluation:
    condition: WorkflowCondition
    requirement_id: str
    assertion: str | None
    generation_succeeded: bool
    reviewer_verdict: str | None
    assertion_valid: bool | None
    behavioral_executed: bool
    good_rtl_passed: bool | None
    mutation_detected: bool | None
    false_positive_count: int | None
    elapsed_seconds: float
    usage_available: bool
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost_usd: float | None = None
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ControlledEvaluationReport:
    requirement: Requirement
    evaluations: tuple[WorkflowEvaluation, ...]
    evidence_kind: str

    @property
    def conditions(self) -> tuple[str, ...]:
        return tuple(item.condition.value for item in self.evaluations)


_BOUNDED_ASSERTION = re.compile(
    r"^assert\s+property\s*\(\s*@\(posedge\s+clk\)\s+"
    r"(?P<trigger>[A-Za-z_][A-Za-z0-9_]*)\s*\|->\s*##\[1:(?P<cycles>\d+)\]\s*"
    r"(?P<response>[A-Za-z_][A-Za-z0-9_]*)\s*\)\s*;\s*$"
)


def parse_bounded_assertion(assertion: str) -> tuple[str, str, int] | None:
    match = _BOUNDED_ASSERTION.fullmatch(assertion.strip())
    if not match:
        return None
    return (
        match.group("trigger"),
        match.group("response"),
        int(match.group("cycles")),
    )


def _baseline_context(requirement: Requirement) -> dict[str, object]:
    draft = ArtifactGenerator().generate(requirement)
    return {
        "assertion": draft.assertion,
        "generation_status": draft.generation_status.value,
        "matched_pattern": draft.matched_pattern,
        "scenarios": draft.scenarios,
        "coverage_goal": draft.coverage_goal,
    }


def _behavioral_score(
    assertion: str,
    *,
    rtl_root: str | Path,
    runner: IcarusBehavioralRunner,
) -> tuple[bool, bool | None, bool | None, int | None, tuple[str, ...]]:
    structural = StructuralSVAValidator().validate(assertion)
    valid = structural.status is ValidationStatus.VALID
    if not valid:
        return False, None, None, None, (f"structural validation failed: {structural.detail}",)

    parsed = parse_bounded_assertion(assertion)
    if parsed is None:
        return True, None, None, None, (
            "behavioral execution skipped: candidate is outside the V7 bounded-response evaluator grammar",
        )

    trigger, response, cycles = parsed
    if (trigger, response) != ("request", "grant"):
        return True, None, None, None, (
            "behavioral execution skipped: RTL fixture exposes request/grant only",
        )

    root = Path(rtl_root)
    good = runner.run(
        source=root / "handshake_good.sv",
        module_name="handshake_good",
        expected_pass=True,
        max_cycles=cycles,
    )
    mutation = runner.run(
        source=root / "handshake_late_bug.sv",
        module_name="handshake_late_bug",
        expected_pass=False,
        max_cycles=cycles,
    )

    if good.status in {RTLRunStatus.COMPILE_ERROR, RTLRunStatus.TOOL_UNAVAILABLE}:
        return True, None, None, None, (f"good RTL tool execution failed: {good.detail}",)
    if mutation.status in {RTLRunStatus.COMPILE_ERROR, RTLRunStatus.TOOL_UNAVAILABLE}:
        return True, None, None, None, (f"mutation RTL tool execution failed: {mutation.detail}",)

    good_passed = good.status is RTLRunStatus.PASS
    mutation_detected = mutation.status is RTLRunStatus.FAIL
    false_positives = 0 if good_passed else 1
    return True, good_passed, mutation_detected, false_positives, ()


def _evaluate_assertion(
    *,
    condition: WorkflowCondition,
    requirement: Requirement,
    assertion: str | None,
    generation_succeeded: bool,
    reviewer_verdict: str | None,
    started: float,
    rtl_root: str | Path,
    runner: IcarusBehavioralRunner,
    notes: tuple[str, ...] = (),
) -> WorkflowEvaluation:
    if not assertion:
        return WorkflowEvaluation(
            condition=condition,
            requirement_id=requirement.requirement_id,
            assertion=None,
            generation_succeeded=generation_succeeded,
            reviewer_verdict=reviewer_verdict,
            assertion_valid=None,
            behavioral_executed=False,
            good_rtl_passed=None,
            mutation_detected=None,
            false_positive_count=None,
            elapsed_seconds=perf_counter() - started,
            usage_available=False,
            notes=notes,
        )

    valid, good, mutation, false_positives, behavioral_notes = _behavioral_score(
        assertion, rtl_root=rtl_root, runner=runner
    )
    return WorkflowEvaluation(
        condition=condition,
        requirement_id=requirement.requirement_id,
        assertion=assertion,
        generation_succeeded=generation_succeeded,
        reviewer_verdict=reviewer_verdict,
        assertion_valid=valid,
        behavioral_executed=good is not None and mutation is not None,
        good_rtl_passed=good,
        mutation_detected=mutation,
        false_positive_count=false_positives,
        elapsed_seconds=perf_counter() - started,
        usage_available=False,
        notes=notes + behavioral_notes,
    )


def evaluate_deterministic(
    requirement: Requirement,
    *,
    rtl_root: str | Path,
    runner: IcarusBehavioralRunner,
) -> WorkflowEvaluation:
    started = perf_counter()
    draft = ArtifactGenerator().generate(requirement)
    return _evaluate_assertion(
        condition=WorkflowCondition.DETERMINISTIC,
        requirement=requirement,
        assertion=draft.assertion,
        generation_succeeded=True,
        reviewer_verdict=None,
        started=started,
        rtl_root=rtl_root,
        runner=runner,
        notes=(f"deterministic status={draft.generation_status.value}",),
    )


def evaluate_single_model(
    requirement: Requirement,
    *,
    generator_backend: ModelBackend,
    rtl_root: str | Path,
    runner: IcarusBehavioralRunner,
) -> WorkflowEvaluation:
    started = perf_counter()
    try:
        draft = ModelArtifactGenerator(generator_backend).generate(
            requirement, _baseline_context(requirement)
        )
    except (ValueError, RuntimeError) as exc:
        return _evaluate_assertion(
            condition=WorkflowCondition.SINGLE_MODEL,
            requirement=requirement,
            assertion=None,
            generation_succeeded=False,
            reviewer_verdict=None,
            started=started,
            rtl_root=rtl_root,
            runner=runner,
            notes=(f"generation failed: {exc}",),
        )
    return _evaluate_assertion(
        condition=WorkflowCondition.SINGLE_MODEL,
        requirement=requirement,
        assertion=draft.assertion,
        generation_succeeded=True,
        reviewer_verdict=None,
        started=started,
        rtl_root=rtl_root,
        runner=runner,
    )


def _reviewed_condition(
    condition: WorkflowCondition,
    requirement: Requirement,
    *,
    generator_backend: ModelBackend,
    reviewer_backend: ModelBackend,
    rtl_root: str | Path,
    runner: IcarusBehavioralRunner,
    require_tool_gate: bool,
) -> WorkflowEvaluation:
    started = perf_counter()
    try:
        draft: ModelDraft = ModelArtifactGenerator(generator_backend).generate(
            requirement, _baseline_context(requirement)
        )
        review = ModelArtifactReviewer(reviewer_backend).review(requirement, draft)
    except (ValueError, RuntimeError) as exc:
        return _evaluate_assertion(
            condition=condition,
            requirement=requirement,
            assertion=None,
            generation_succeeded=False,
            reviewer_verdict=None,
            started=started,
            rtl_root=rtl_root,
            runner=runner,
            notes=(f"workflow failed: {exc}",),
        )

    if review.verdict != "ACCEPT_FOR_TOOL_CHECK":
        return _evaluate_assertion(
            condition=condition,
            requirement=requirement,
            assertion=draft.assertion,
            generation_succeeded=True,
            reviewer_verdict=review.verdict,
            started=started,
            rtl_root=rtl_root,
            runner=runner,
            notes=("behavioral execution withheld by reviewer",),
        ) if not require_tool_gate else WorkflowEvaluation(
            condition=condition,
            requirement_id=requirement.requirement_id,
            assertion=draft.assertion,
            generation_succeeded=True,
            reviewer_verdict=review.verdict,
            assertion_valid=None,
            behavioral_executed=False,
            good_rtl_passed=None,
            mutation_detected=None,
            false_positive_count=None,
            elapsed_seconds=perf_counter() - started,
            usage_available=False,
            notes=("tool-gated condition stopped because reviewer did not accept for tool check",),
        )

    if not require_tool_gate:
        return _evaluate_assertion(
            condition=condition,
            requirement=requirement,
            assertion=draft.assertion,
            generation_succeeded=True,
            reviewer_verdict=review.verdict,
            started=started,
            rtl_root=rtl_root,
            runner=runner,
            notes=("reviewer accepted; behavioral scoring used only for evaluation, not as a workflow gate",),
        )

    structural = StructuralSVAValidator().validate(draft.assertion)
    if structural.status is not ValidationStatus.VALID:
        return WorkflowEvaluation(
            condition=condition,
            requirement_id=requirement.requirement_id,
            assertion=draft.assertion,
            generation_succeeded=True,
            reviewer_verdict=review.verdict,
            assertion_valid=False,
            behavioral_executed=False,
            good_rtl_passed=None,
            mutation_detected=None,
            false_positive_count=None,
            elapsed_seconds=perf_counter() - started,
            usage_available=False,
            notes=(f"tool gate rejected assertion: {structural.detail}",),
        )

    return _evaluate_assertion(
        condition=condition,
        requirement=requirement,
        assertion=draft.assertion,
        generation_succeeded=True,
        reviewer_verdict=review.verdict,
        started=started,
        rtl_root=rtl_root,
        runner=runner,
        notes=("reviewer and structural tool gate accepted candidate",),
    )


def run_controlled_evaluation(
    requirement: Requirement,
    *,
    single_generator_backend: ModelBackend,
    reviewed_generator_backend: ModelBackend,
    reviewer_backend: ModelBackend,
    tool_generator_backend: ModelBackend,
    tool_reviewer_backend: ModelBackend,
    rtl_root: str | Path = "benchmarks/rtl",
    runner_factory: Callable[[], IcarusBehavioralRunner] = IcarusBehavioralRunner,
    evidence_kind: str = "scripted_offline",
) -> ControlledEvaluationReport:
    evaluations = (
        evaluate_deterministic(
            requirement, rtl_root=rtl_root, runner=runner_factory()
        ),
        evaluate_single_model(
            requirement,
            generator_backend=single_generator_backend,
            rtl_root=rtl_root,
            runner=runner_factory(),
        ),
        _reviewed_condition(
            WorkflowCondition.GENERATOR_REVIEWER,
            requirement,
            generator_backend=reviewed_generator_backend,
            reviewer_backend=reviewer_backend,
            rtl_root=rtl_root,
            runner=runner_factory(),
            require_tool_gate=False,
        ),
        _reviewed_condition(
            WorkflowCondition.GENERATOR_REVIEWER_TOOL,
            requirement,
            generator_backend=tool_generator_backend,
            reviewer_backend=tool_reviewer_backend,
            rtl_root=rtl_root,
            runner=runner_factory(),
            require_tool_gate=True,
        ),
    )
    return ControlledEvaluationReport(
        requirement=requirement,
        evaluations=evaluations,
        evidence_kind=evidence_kind,
    )
