"""CLI for CloudGuard V4 assurance workflows."""

from __future__ import annotations

from dataclasses import asdict
import argparse
import json
from pathlib import Path
from typing import Mapping

from .cloudguard_v4 import (
    CloudGuardAuditStore,
    CloudGuardFeedbackEngine,
    CloudGuardPolicyEngine,
    DetectionEvidence,
    FieldIssue,
    HumanDisposition,
    HumanReview,
    ResponseImpactTier,
    ResponseOutcome,
    ResponseRequest,
    ThreatChangeType,
    ThreatDetection,
    ThreatKnowledgeRegistry,
    ThreatRecord,
    ThreatSource,
    ThreatSourceTrust,
    ThreatUpdateProposal,
    ThreatUpdateReview,
    RegressionEvidence,
    detection_audit_payload,
    threat_update_audit_payload,
)


def _load(path: str) -> Mapping[str, object]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError("input must be a JSON object")
    return value


def _source(data: Mapping[str, object]) -> ThreatSource:
    return ThreatSource(
        source_id=str(data["source_id"]),
        name=str(data["name"]),
        trust=ThreatSourceTrust(str(data["trust"])),
        reference=str(data["reference"]) if data.get("reference") is not None else None,
        content_digest=str(data["content_digest"]) if data.get("content_digest") is not None else None,
    )


def _threat_record(data: Mapping[str, object]) -> ThreatRecord:
    source = data.get("source")
    if not isinstance(source, Mapping):
        raise ValueError("threat record requires source object")
    confidence = data.get("confidence")
    return ThreatRecord(
        threat_id=str(data["threat_id"]),
        version=str(data["version"]),
        name=str(data["name"]),
        change_type=ThreatChangeType(str(data["change_type"])),
        severity=str(data["severity"]),
        source=_source(source),
        techniques=tuple(str(item) for item in data.get("techniques", [])),
        observables=tuple(str(item) for item in data.get("observables", [])),
        affected_assets=tuple(str(item) for item in data.get("affected_assets", [])),
        first_seen=str(data["first_seen"]) if data.get("first_seen") is not None else None,
        last_seen=str(data["last_seen"]) if data.get("last_seen") is not None else None,
        confidence=int(confidence) if confidence is not None else None,
        notes=str(data.get("notes", "")),
    )


def _regression(data: Mapping[str, object] | None) -> RegressionEvidence | None:
    if data is None:
        return None
    return RegressionEvidence(
        regression_id=str(data["regression_id"]),
        attack_cases_passed=int(data["attack_cases_passed"]),
        benign_cases_passed=int(data["benign_cases_passed"]),
        unexpected_failures=int(data["unexpected_failures"]),
        false_positive_delta=float(data["false_positive_delta"]),
        coverage_added=tuple(str(item) for item in data.get("coverage_added", [])),
    )


def _threat_update_payload(data: Mapping[str, object]) -> dict[str, object]:
    record_data = data.get("record")
    review_data = data.get("review")
    if not isinstance(record_data, Mapping) or not isinstance(review_data, Mapping):
        raise ValueError("threat update requires record and review objects")
    proposal = ThreatUpdateProposal(
        update_id=str(data["update_id"]),
        record=_threat_record(record_data),
        proposed_by=str(data["proposed_by"]),
        rationale=str(data["rationale"]),
        affected_detections=tuple(str(item) for item in data.get("affected_detections", [])),
        affected_playbooks=tuple(str(item) for item in data.get("affected_playbooks", [])),
        weakens_existing_control=bool(data.get("weakens_existing_control", False)),
        source_field_issue=str(data["source_field_issue"]) if data.get("source_field_issue") else None,
    )
    regression_data = review_data.get("regression")
    review = ThreatUpdateReview(
        update_id=proposal.update_id,
        reviewer=str(review_data["reviewer"]),
        disposition=HumanDisposition(str(review_data["disposition"])),
        rationale=str(review_data["rationale"]),
        second_reviewer=str(review_data["second_reviewer"]) if review_data.get("second_reviewer") else None,
        regression=_regression(regression_data if isinstance(regression_data, Mapping) else None),
    )
    registry = ThreatKnowledgeRegistry()
    registry.propose(proposal)
    active = registry.activate(review)
    return {
        "proposal": asdict(proposal),
        "review": asdict(review),
        "active": asdict(active),
        "threat_db_digest": registry.snapshot_digest(),
        "audit_payload": threat_update_audit_payload(proposal, review, active),
    }


def _detection(data: Mapping[str, object]) -> ThreatDetection:
    evidence: list[DetectionEvidence] = []
    for value in data.get("evidence", []):
        if not isinstance(value, Mapping):
            raise ValueError("evidence entries must be objects")
        evidence.append(
            DetectionEvidence(
                evidence_id=str(value["evidence_id"]),
                source=str(value["source"]),
                verified=bool(value["verified"]),
                freshness=str(value["freshness"]),
                content_digest=str(value["content_digest"]),
                attributes=dict(value.get("attributes", {})),  # type: ignore[arg-type]
            )
        )
    return ThreatDetection(
        detection_id=str(data["detection_id"]),
        incident_id=str(data["incident_id"]),
        asset_id=str(data["asset_id"]),
        account_id=str(data["account_id"]) if data.get("account_id") is not None else None,
        threat_id=str(data["threat_id"]),
        threat_version=str(data["threat_version"]),
        detector_id=str(data["detector_id"]),
        detector_version=str(data["detector_version"]),
        detector_digest=str(data["detector_digest"]),
        severity=str(data["severity"]),
        evidence=tuple(evidence),
        techniques=tuple(str(item) for item in data.get("techniques", [])),
        model_hypothesis=str(data["model_hypothesis"]) if data.get("model_hypothesis") is not None else None,
        model_probability=float(data["model_probability"]) if data.get("model_probability") is not None else None,
        evidence_completeness=float(data["evidence_completeness"]) if data.get("evidence_completeness") is not None else None,
        source_agreement=float(data["source_agreement"]) if data.get("source_agreement") is not None else None,
    )


def _response_payload(data: Mapping[str, object]) -> dict[str, object]:
    detection_data = data.get("detection")
    request_data = data.get("request")
    if not isinstance(detection_data, Mapping) or not isinstance(request_data, Mapping):
        raise ValueError("response input requires detection and request")
    detection = _detection(detection_data)
    request = ResponseRequest(
        incident_id=str(request_data["incident_id"]),
        action=str(request_data["action"]),
        target=str(request_data["target"]),
        requested_by=str(request_data["requested_by"]),
        impact_tier=ResponseImpactTier(int(request_data["impact_tier"])),
        parameters=dict(request_data.get("parameters", {})),  # type: ignore[arg-type]
        evidence_ids=tuple(str(item) for item in request_data.get("evidence_ids", [])),
        threat_ids=tuple(str(item) for item in request_data.get("threat_ids", [])),
        emergency=bool(request_data.get("emergency", False)),
    )
    review_data = data.get("review")
    review = None
    if isinstance(review_data, Mapping):
        review = HumanReview(
            review_id=str(review_data["review_id"]),
            incident_id=str(review_data["incident_id"]),
            action=str(review_data["action"]),
            reviewer=str(review_data["reviewer"]),
            reviewer_trust_domain=str(review_data["reviewer_trust_domain"]),
            disposition=HumanDisposition(str(review_data["disposition"])),
            rationale=str(review_data["rationale"]),
            evidence_reviewed=tuple(str(item) for item in review_data.get("evidence_reviewed", [])),
            second_reviewer=str(review_data["second_reviewer"]) if review_data.get("second_reviewer") else None,
            second_reviewer_trust_domain=str(review_data["second_reviewer_trust_domain"]) if review_data.get("second_reviewer_trust_domain") else None,
        )
    result = CloudGuardPolicyEngine().decide(request, evidence=detection.evidence, review=review)
    return {"detection": asdict(detection), "request": asdict(request), "review": asdict(review) if review else None, "policy_result": asdict(result)}


def _feedback_payload(data: Mapping[str, object]) -> dict[str, object]:
    issue = FieldIssue(
        field_issue_id=str(data["field_issue_id"]),
        incident_id=str(data["incident_id"]),
        confirmed_unsafe=bool(data["confirmed_unsafe"]),
        detected_before_effect=bool(data["detected_before_effect"]),
        detector_fired=bool(data["detector_fired"]),
        telemetry_complete=bool(data["telemetry_complete"]),
        threat_known=bool(data["threat_known"]),
        policy_blocked=bool(data["policy_blocked"]),
        response_effective=bool(data["response_effective"]),
        recovery_effective=bool(data["recovery_effective"]),
        false_positive=bool(data.get("false_positive", False)),
    )
    return asdict(CloudGuardFeedbackEngine().analyze(issue))


def main() -> None:
    parser = argparse.ArgumentParser(description="CloudGuard V4 assurance-governed SOC reference workflows")
    parser.add_argument("--audit-log", default=None, help="Optional JSONL audit file")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("threat-update", "response", "feedback"):
        child = sub.add_parser(name)
        child.add_argument("input")
    detect = sub.add_parser("record-detection")
    detect.add_argument("input")
    detect.add_argument("--threat-db-digest", required=True)
    outcome = sub.add_parser("record-outcome")
    outcome.add_argument("input")
    sub.add_parser("verify-audit")

    args = parser.parse_args()
    store = CloudGuardAuditStore(args.audit_log) if args.audit_log else None

    if args.command == "verify-audit":
        if store is None:
            raise ValueError("verify-audit requires --audit-log")
        ok, detail = store.verify()
        print(json.dumps({"valid": ok, "detail": detail}, indent=2))
        if not ok:
            raise SystemExit(1)
        return

    data = _load(args.input)
    if args.command == "threat-update":
        payload = _threat_update_payload(data)
        if store is not None:
            store.append("THREAT_DB_UPDATE", payload["audit_payload"])  # type: ignore[arg-type]
    elif args.command == "response":
        payload = _response_payload(data)
        if store is not None:
            store.append("RESPONSE_POLICY_DECISION", payload)
    elif args.command == "feedback":
        payload = _feedback_payload(data)
        if store is not None:
            store.append("FIELD_FEEDBACK", payload)
    elif args.command == "record-detection":
        detection = _detection(data)
        payload = detection_audit_payload(detection, threat_db_digest=args.threat_db_digest)
        if store is not None:
            store.append("THREAT_DETECTION", payload)
    else:
        payload = {
            "incident_id": str(data["incident_id"]),
            "action": str(data["action"]),
            "outcome": str(data["outcome"]),
            "threat_contained": bool(data["threat_contained"]),
            "recovery_required": bool(data["recovery_required"]),
            "false_positive": bool(data["false_positive"]),
            "followup_required": bool(data["followup_required"]),
            "notes": str(data.get("notes", "")),
        }
        # Constructing the dataclass catches missing fields and documents shape.
        response_outcome = ResponseOutcome(**payload)
        payload = asdict(response_outcome)
        if store is not None:
            store.append("RESPONSE_OUTCOME", payload)

    print(json.dumps(payload, indent=2, default=str))


if __name__ == "__main__":
    main()
