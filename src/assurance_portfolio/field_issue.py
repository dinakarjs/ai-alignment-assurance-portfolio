"""Field-issue analysis and feedback loop for Agent Trace Assurance."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Mapping, Sequence

from .trace_assurance import AssuranceReport, AssuranceStatus, TraceAssuranceEngine


class GapClassification(str, Enum):
    MISSING_CHECK = "MISSING_CHECK"
    WEAK_CHECK = "WEAK_CHECK"
    CHECK_BUG = "CHECK_BUG"
    SCHEMA_GAP = "SCHEMA_GAP"
    POLICY_GAP = "POLICY_GAP"
    INSTRUMENTATION_GAP = "INSTRUMENTATION_GAP"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    FALSE_NEGATIVE = "FALSE_NEGATIVE"
    COVERAGE_GAP = "COVERAGE_GAP"
    ENFORCEMENT_GAP = "ENFORCEMENT_GAP"


@dataclass(frozen=True)
class FieldIssue:
    issue_id: str
    severity: str
    summary: str
    expected_behavior: str
    actual_behavior: str
    trace: tuple[Mapping[str, object], ...]
    confirmed_unsafe: bool = True
    source: str | None = None


@dataclass(frozen=True)
class FieldIssueAnalysis:
    issue_id: str
    replay_status: str
    detected_by_existing_checks: bool
    applicable_violations: tuple[str, ...]
    classification: GapClassification
    root_cause: str
    recommended_action: str
    suggested_check_update: Mapping[str, object]
    source_trace_event_count: int


class FieldIssueAnalyzer:
    """Deterministic incident replay plus conservative gap classification.

    This classifier does not claim to infer a true root cause from arbitrary text.
    It uses explicit issue metadata and trace evidence to create a reviewable
    feedback proposal.
    """

    def __init__(self, engine: TraceAssuranceEngine | None = None) -> None:
        self.engine = engine or TraceAssuranceEngine()

    def analyze(self, issue: FieldIssue) -> FieldIssueAnalysis:
        report: AssuranceReport = self.engine.evaluate(issue.trace)
        violation_names = tuple(sorted({item.property_name for item in report.violations}))
        detected = bool(violation_names)

        if issue.confirmed_unsafe and report.status is AssuranceStatus.PASS:
            classification = GapClassification.FALSE_NEGATIVE
            root_cause = "confirmed unsafe behavior passed all exercised checks"
            action = "add or strengthen a property and retain this trace as a permanent regression"
        elif issue.confirmed_unsafe and report.status is AssuranceStatus.INCONCLUSIVE:
            classification = GapClassification.COVERAGE_GAP
            root_cause = "confirmed unsafe behavior was not covered by every required property"
            action = "add activation scenarios and a property that directly represents this hazard"
        elif issue.confirmed_unsafe and detected:
            classification = GapClassification.ENFORCEMENT_GAP
            root_cause = "existing checks detected the issue, but unsafe behavior still occurred"
            action = "move the relevant property into the pre-action runtime gate and verify blocking"
        elif not issue.confirmed_unsafe and report.status is AssuranceStatus.FAIL:
            classification = GapClassification.FALSE_POSITIVE
            root_cause = "benign behavior was rejected by one or more checks"
            action = "refine policy scope while preserving negative-regression coverage"
        else:
            classification = GapClassification.WEAK_CHECK
            root_cause = "field issue requires expert review; deterministic replay is not decisive"
            action = "review trace/schema/policy coverage and preserve the issue as a regression candidate"

        suggestion: dict[str, object] = {
            "source_issue": issue.issue_id,
            "change_type": "FIELD_ISSUE_FEEDBACK",
            "classification": classification.value,
            "rationale": root_cause,
            "checks_modified": list(violation_names),
            "requires_regression": True,
            "requires_independent_approval": True,
            "recommended_action": action,
        }
        return FieldIssueAnalysis(
            issue_id=issue.issue_id,
            replay_status=report.status.value,
            detected_by_existing_checks=detected,
            applicable_violations=violation_names,
            classification=classification,
            root_cause=root_cause,
            recommended_action=action,
            suggested_check_update=suggestion,
            source_trace_event_count=len(issue.trace),
        )


def field_issue_from_dict(data: Mapping[str, object]) -> FieldIssue:
    raw_trace = data.get("trace", [])
    if not isinstance(raw_trace, Sequence) or isinstance(raw_trace, (str, bytes)):
        raise ValueError("field issue trace must be an event list")
    trace: list[Mapping[str, object]] = []
    for item in raw_trace:
        if not isinstance(item, Mapping):
            raise ValueError("field issue trace entries must be objects")
        trace.append(dict(item))
    required = ("issue_id", "severity", "summary", "expected_behavior", "actual_behavior")
    missing = [name for name in required if not str(data.get(name, "")).strip()]
    if missing:
        raise ValueError(f"field issue missing required fields: {', '.join(missing)}")
    return FieldIssue(
        issue_id=str(data["issue_id"]),
        severity=str(data["severity"]).upper(),
        summary=str(data["summary"]),
        expected_behavior=str(data["expected_behavior"]),
        actual_behavior=str(data["actual_behavior"]),
        trace=tuple(trace),
        confirmed_unsafe=bool(data.get("confirmed_unsafe", True)),
        source=str(data.get("source")) if data.get("source") is not None else None,
    )
