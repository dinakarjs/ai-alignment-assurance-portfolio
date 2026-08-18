"""Evaluation-information-flow integrity for multi-module/agent pipelines.

The evaluator and ground truth are treated as privileged control-plane data.
Predictions are valid only when they are committed before privileged labels or
scoring feedback can influence the system under test.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Sequence


class EvalLabel(str, Enum):
    PUBLIC_INPUT = "PUBLIC_INPUT"
    MODEL_INPUT = "MODEL_INPUT"
    MODEL_DERIVED = "MODEL_DERIVED"
    GROUND_TRUTH = "GROUND_TRUTH"
    ANSWER_KEY = "ANSWER_KEY"
    EVALUATOR_ONLY = "EVALUATOR_ONLY"
    SCORING_SIGNAL = "SCORING_SIGNAL"
    POST_COMMIT_FEEDBACK = "POST_COMMIT_FEEDBACK"
    EVALUATION_CANARY = "EVALUATION_CANARY"


RESTRICTED_PRECOMMIT_LABELS = frozenset(
    {
        EvalLabel.GROUND_TRUTH,
        EvalLabel.ANSWER_KEY,
        EvalLabel.EVALUATOR_ONLY,
        EvalLabel.SCORING_SIGNAL,
        EvalLabel.POST_COMMIT_FEEDBACK,
        EvalLabel.EVALUATION_CANARY,
    }
)


@dataclass(frozen=True)
class EvaluationArtifact:
    artifact_id: str
    producer: str
    labels: tuple[EvalLabel, ...] = ()
    parents: tuple[str, ...] = ()
    digest: str | None = None


@dataclass(frozen=True)
class AccessRecord:
    principal: str
    artifact_id: str
    sequence: int


@dataclass(frozen=True)
class EvaluationRun:
    artifacts: tuple[EvaluationArtifact, ...]
    accesses: tuple[AccessRecord, ...]
    prediction_artifact_id: str
    prediction_commit_sequence: int
    ground_truth_release_sequence: int
    evaluator_principals: tuple[str, ...]
    system_principals: tuple[str, ...]
    scorer_principal: str


@dataclass(frozen=True)
class EvaluationViolation:
    check: str
    detail: str
    artifact_id: str | None = None
    principal: str | None = None


@dataclass(frozen=True)
class EvaluationIntegrityReport:
    valid: bool
    violations: tuple[EvaluationViolation, ...]
    prediction_labels: tuple[str, ...]
    required_checks: tuple[str, ...]
    executed_checks: tuple[str, ...]


REQUIRED_CHECKS = (
    "evaluation_ground_truth_isolation",
    "prediction_before_label_release",
    "prediction_commit_integrity",
    "evaluation_feedback_isolation",
    "transitive_provenance_taint",
    "module_capability_separation",
    "scorer_independence",
    "evaluation_canary_noninterference",
)


def _artifact_map(artifacts: Sequence[EvaluationArtifact]) -> dict[str, EvaluationArtifact]:
    result: dict[str, EvaluationArtifact] = {}
    for artifact in artifacts:
        if not artifact.artifact_id:
            raise ValueError("evaluation artifact_id must be non-empty")
        if artifact.artifact_id in result:
            raise ValueError(f"duplicate evaluation artifact_id {artifact.artifact_id}")
        result[artifact.artifact_id] = artifact
    return result


def _effective_labels(
    artifact_id: str,
    artifacts: Mapping[str, EvaluationArtifact],
    memo: dict[str, frozenset[EvalLabel]],
    stack: set[str],
) -> frozenset[EvalLabel]:
    if artifact_id in memo:
        return memo[artifact_id]
    if artifact_id in stack:
        raise ValueError(f"cycle detected in evaluation provenance at {artifact_id}")
    artifact = artifacts.get(artifact_id)
    if artifact is None:
        raise ValueError(f"unknown evaluation artifact {artifact_id}")
    stack.add(artifact_id)
    labels = set(artifact.labels)
    for parent in artifact.parents:
        labels.update(_effective_labels(parent, artifacts, memo, stack))
    stack.remove(artifact_id)
    memo[artifact_id] = frozenset(labels)
    return memo[artifact_id]


def validate_evaluation_integrity(run: EvaluationRun) -> EvaluationIntegrityReport:
    artifacts = _artifact_map(run.artifacts)
    if run.prediction_artifact_id not in artifacts:
        raise ValueError("prediction artifact is absent from evaluation run")
    violations: list[EvaluationViolation] = []
    memo: dict[str, frozenset[EvalLabel]] = {}
    prediction_labels = _effective_labels(run.prediction_artifact_id, artifacts, memo, set())

    leaked_labels = sorted(label.value for label in prediction_labels & RESTRICTED_PRECOMMIT_LABELS)
    if leaked_labels:
        violations.append(
            EvaluationViolation(
                "transitive_provenance_taint",
                "prediction is transitively influenced by evaluation-only data: " + ", ".join(leaked_labels),
                artifact_id=run.prediction_artifact_id,
            )
        )

    if run.prediction_commit_sequence >= run.ground_truth_release_sequence:
        violations.append(
            EvaluationViolation(
                "prediction_before_label_release",
                "prediction must be irrevocably committed before ground truth is released",
                artifact_id=run.prediction_artifact_id,
            )
        )

    evaluator_set = {item.strip().lower() for item in run.evaluator_principals}
    system_set = {item.strip().lower() for item in run.system_principals}
    if run.scorer_principal.strip().lower() in system_set:
        violations.append(
            EvaluationViolation(
                "scorer_independence",
                "scorer principal is also part of the system under test",
                principal=run.scorer_principal,
            )
        )
    if run.scorer_principal.strip().lower() not in evaluator_set:
        violations.append(
            EvaluationViolation(
                "scorer_independence",
                "scorer principal is not in the evaluator trust boundary",
                principal=run.scorer_principal,
            )
        )

    for access in run.accesses:
        artifact = artifacts.get(access.artifact_id)
        if artifact is None:
            violations.append(
                EvaluationViolation(
                    "module_capability_separation",
                    "access references an unknown artifact",
                    artifact_id=access.artifact_id,
                    principal=access.principal,
                )
            )
            continue
        labels = _effective_labels(access.artifact_id, artifacts, memo, set())
        principal = access.principal.strip().lower()
        if labels & RESTRICTED_PRECOMMIT_LABELS and principal in system_set:
            violations.append(
                EvaluationViolation(
                    "evaluation_ground_truth_isolation",
                    "system-under-test principal accessed evaluation-only data",
                    artifact_id=access.artifact_id,
                    principal=access.principal,
                )
            )
        if (
            EvalLabel.SCORING_SIGNAL in labels or EvalLabel.POST_COMMIT_FEEDBACK in labels
        ) and principal in system_set and access.sequence < run.prediction_commit_sequence:
            violations.append(
                EvaluationViolation(
                    "evaluation_feedback_isolation",
                    "scoring/evaluation feedback reached the system before prediction commit",
                    artifact_id=access.artifact_id,
                    principal=access.principal,
                )
            )
        if EvalLabel.EVALUATION_CANARY in labels and principal in system_set:
            violations.append(
                EvaluationViolation(
                    "evaluation_canary_noninterference",
                    "evaluation-only canary reached the system under test",
                    artifact_id=access.artifact_id,
                    principal=access.principal,
                )
            )

    executed = REQUIRED_CHECKS
    return EvaluationIntegrityReport(
        valid=not violations,
        violations=tuple(violations),
        prediction_labels=tuple(sorted(label.value for label in prediction_labels)),
        required_checks=REQUIRED_CHECKS,
        executed_checks=executed,
    )


@dataclass(frozen=True)
class AttributionComparison:
    baseline_score: float
    full_score: float
    isolated_score: float
    claimed_gain: float
    privileged_channel_dependent_gain: float
    privileged_gain_fraction: float | None


def compare_attribution(*, baseline_score: float, full_score: float, isolated_score: float) -> AttributionComparison:
    """Quantify how much apparent gain disappears when privileged channels are isolated.

    This is descriptive evidence, not an automatic cheating verdict.
    """

    claimed_gain = full_score - baseline_score
    dependent_gain = max(0.0, full_score - isolated_score)
    fraction = dependent_gain / claimed_gain if claimed_gain > 0 else None
    return AttributionComparison(
        baseline_score=baseline_score,
        full_score=full_score,
        isolated_score=isolated_score,
        claimed_gain=claimed_gain,
        privileged_channel_dependent_gain=dependent_gain,
        privileged_gain_fraction=fraction,
    )
