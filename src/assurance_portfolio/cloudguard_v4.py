"""CloudGuard V4 assurance-governed cloud incident response.

V4 preserves the small transparent CloudGuard V3 scorer as a compatibility/demo
baseline and adds the controls needed around a realistic agentic SOC workflow:
trusted threat intake, versioned threat knowledge, policy-gated response,
human-in-the-loop review, tamper-evident audit history, response outcomes, and
field-issue feedback.

The AI/model is deliberately *not* the authority. It may propose a hypothesis or
response, while deterministic policy and human governance decide whether a
security-sensitive action may execute.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from pathlib import Path
import re
from typing import Mapping, Sequence


CLOUDGUARD_V4_VERSION = "cloudguard/4.0.0"
THREAT_SCHEMA_VERSION = "cloudguard-threat/1.0.0"
DETECTION_MANIFEST_VERSION = "cloudguard-detections/4.0.0"
RESPONSE_POLICY_VERSION = "cloudguard-response/1.0.0"

_MAX_EMERGENCY_CONTAINMENT_MINUTES = 60
_SEVERITIES = frozenset({"INFORMATIONAL", "LOW", "MEDIUM", "HIGH", "CRITICAL"})
_SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_object(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _norm(value: str) -> str:
    return " ".join(value.strip().lower().split())


class ThreatSourceTrust(str, Enum):
    AUTHORITATIVE = "AUTHORITATIVE"
    VERIFIED_CTI = "VERIFIED_CTI"
    INTERNAL_CONFIRMED = "INTERNAL_CONFIRMED"
    UNTRUSTED_DISCOVERY = "UNTRUSTED_DISCOVERY"


class ThreatChangeType(str, Enum):
    NEW_IOC = "NEW_IOC"
    NEW_MALWARE = "NEW_MALWARE"
    NEW_TTP = "NEW_TTP"
    MODIFIED_TTP = "MODIFIED_TTP"
    NEW_CVE = "NEW_CVE"
    ACTIVE_EXPLOIT = "ACTIVE_EXPLOIT"
    NEW_CAMPAIGN = "NEW_CAMPAIGN"
    DETECTION_EVASION = "DETECTION_EVASION"
    FALSE_POSITIVE_PATTERN = "FALSE_POSITIVE_PATTERN"
    FALSE_NEGATIVE = "FALSE_NEGATIVE"
    TELEMETRY_GAP = "TELEMETRY_GAP"
    RESPONSE_GAP = "RESPONSE_GAP"
    RECOVERY_GAP = "RECOVERY_GAP"


class ThreatUpdateStatus(str, Enum):
    PROPOSED = "PROPOSED"
    AUTOMATED_VALIDATION = "AUTOMATED_VALIDATION"
    HIL_REVIEW_PENDING = "HIL_REVIEW_PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REGRESSION_VALIDATED = "REGRESSION_VALIDATED"
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    ROLLED_BACK = "ROLLED_BACK"


class ResponseDecision(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    ESCALATE = "ESCALATE"


class HumanDisposition(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    REQUEST_CHANGES = "REQUEST_CHANGES"
    ESCALATE = "ESCALATE"
    EXCEPTION_APPROVED = "EXCEPTION_APPROVED"


class ResponseImpactTier(int, Enum):
    OBSERVE = 0
    ENRICH = 1
    TEMPORARY_CONTAINMENT = 2
    ACCOUNT_OR_PRIVILEGE_CHANGE = 3
    DESTRUCTIVE_OR_BUSINESS_CRITICAL = 4


class FeedbackGap(str, Enum):
    DETECTION_GAP = "DETECTION_GAP"
    TELEMETRY_GAP = "TELEMETRY_GAP"
    THREAT_DB_GAP = "THREAT_DB_GAP"
    CORRELATION_GAP = "CORRELATION_GAP"
    POLICY_GAP = "POLICY_GAP"
    PLAYBOOK_GAP = "PLAYBOOK_GAP"
    MODEL_GAP = "MODEL_GAP"
    RESPONSE_GAP = "RESPONSE_GAP"
    RECOVERY_GAP = "RECOVERY_GAP"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


@dataclass(frozen=True)
class ThreatSource:
    source_id: str
    name: str
    trust: ThreatSourceTrust
    reference: str | None = None
    content_digest: str | None = None


@dataclass(frozen=True)
class ThreatRecord:
    threat_id: str
    version: str
    name: str
    change_type: ThreatChangeType
    severity: str
    source: ThreatSource
    techniques: tuple[str, ...] = ()
    observables: tuple[str, ...] = ()
    affected_assets: tuple[str, ...] = ()
    first_seen: str | None = None
    last_seen: str | None = None
    confidence: int | None = None
    notes: str = ""

    @property
    def digest(self) -> str:
        return _sha256_object(asdict(self))


@dataclass(frozen=True)
class RegressionEvidence:
    regression_id: str
    attack_cases_passed: int
    benign_cases_passed: int
    unexpected_failures: int
    false_positive_delta: float
    coverage_added: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return self.unexpected_failures == 0 and self.attack_cases_passed >= 1


@dataclass(frozen=True)
class ThreatUpdateProposal:
    update_id: str
    record: ThreatRecord
    proposed_by: str
    rationale: str
    affected_detections: tuple[str, ...] = ()
    affected_playbooks: tuple[str, ...] = ()
    weakens_existing_control: bool = False
    source_field_issue: str | None = None


@dataclass(frozen=True)
class ThreatUpdateReview:
    update_id: str
    reviewer: str
    disposition: HumanDisposition
    rationale: str
    second_reviewer: str | None = None
    regression: RegressionEvidence | None = None


@dataclass(frozen=True)
class ActiveThreatVersion:
    threat_id: str
    version: str
    digest: str
    activated_at_utc: str
    update_id: str


@dataclass(frozen=True)
class DetectionEvidence:
    evidence_id: str
    source: str
    verified: bool
    freshness: str
    content_digest: str
    attributes: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ThreatDetection:
    detection_id: str
    incident_id: str
    asset_id: str
    account_id: str | None
    threat_id: str
    threat_version: str
    detector_id: str
    detector_version: str
    detector_digest: str
    severity: str
    evidence: tuple[DetectionEvidence, ...]
    techniques: tuple[str, ...] = ()
    model_hypothesis: str | None = None
    model_probability: float | None = None
    evidence_completeness: float | None = None
    source_agreement: float | None = None


@dataclass(frozen=True)
class ResponseRequest:
    incident_id: str
    action: str
    target: str
    requested_by: str
    impact_tier: ResponseImpactTier
    parameters: Mapping[str, object] = field(default_factory=dict)
    evidence_ids: tuple[str, ...] = ()
    threat_ids: tuple[str, ...] = ()
    emergency: bool = False

    @property
    def request_digest(self) -> str:
        return _sha256_object(
            {
                "incident_id": self.incident_id,
                "action": self.action,
                "target": self.target,
                "requested_by": self.requested_by,
                "impact_tier": self.impact_tier.value,
                "parameters": dict(self.parameters),
                "evidence_ids": tuple(self.evidence_ids),
                "threat_ids": tuple(self.threat_ids),
                "emergency": self.emergency,
            }
        )


@dataclass(frozen=True)
class HumanReview:
    review_id: str
    incident_id: str
    action: str
    target: str
    request_digest: str
    reviewer: str
    reviewer_trust_domain: str
    disposition: HumanDisposition
    rationale: str
    evidence_reviewed: tuple[str, ...] = ()
    second_reviewer: str | None = None
    second_reviewer_trust_domain: str | None = None


@dataclass(frozen=True)
class ResponsePolicyResult:
    decision: ResponseDecision
    reasons: tuple[str, ...]
    required_reviewers: int


@dataclass(frozen=True)
class ResponseOutcome:
    incident_id: str
    action: str
    outcome: str
    threat_contained: bool
    recovery_required: bool
    false_positive: bool
    followup_required: bool
    notes: str = ""


@dataclass(frozen=True)
class FieldIssue:
    field_issue_id: str
    incident_id: str
    confirmed_unsafe: bool
    detected_before_effect: bool
    detector_fired: bool
    telemetry_complete: bool
    threat_known: bool
    policy_blocked: bool
    response_effective: bool
    recovery_effective: bool
    false_positive: bool = False


@dataclass(frozen=True)
class FeedbackAnalysis:
    field_issue_id: str
    gap: FeedbackGap
    detail: str
    proposed_updates: tuple[str, ...]


def _validate_threat_record(record: ThreatRecord) -> None:
    if not record.threat_id.strip() or not record.name.strip():
        raise ValueError("threat record requires non-empty threat_id and name")
    if not _SEMVER.fullmatch(record.version):
        raise ValueError("threat version must be numeric semantic version x.y.z")
    severity = record.severity.strip().upper()
    if severity not in _SEVERITIES:
        raise ValueError(f"invalid threat severity {record.severity!r}")
    if not record.source.source_id.strip() or not record.source.name.strip():
        raise ValueError("threat source requires source_id and name")
    if record.confidence is not None and not 0 <= record.confidence <= 100:
        raise ValueError("source confidence must be between 0 and 100")


class CloudGuardPolicyEngine:
    """Deterministic response policy independent of model confidence."""

    def decide(
        self,
        request: ResponseRequest,
        *,
        evidence: Sequence[DetectionEvidence],
        review: HumanReview | None = None,
    ) -> ResponsePolicyResult:
        evidence_by_id = {item.evidence_id: item for item in evidence}
        required = set(request.evidence_ids)
        missing = required - set(evidence_by_id)
        if missing:
            return ResponsePolicyResult(
                ResponseDecision.BLOCK,
                (f"missing required evidence: {sorted(missing)}",),
                0,
            )
        unverified = [
            item.evidence_id
            for item in evidence
            if item.evidence_id in required and not item.verified
        ]
        if unverified:
            return ResponsePolicyResult(
                ResponseDecision.ESCALATE,
                (f"unverified evidence cannot authorize response: {sorted(unverified)}",),
                1,
            )

        if request.impact_tier <= ResponseImpactTier.ENRICH:
            return ResponsePolicyResult(ResponseDecision.ALLOW, ("read/enrich operation",), 0)

        if request.impact_tier is ResponseImpactTier.TEMPORARY_CONTAINMENT:
            if request.emergency:
                expiry = request.parameters.get("expires_after_minutes")
                if not isinstance(expiry, (int, float)) or isinstance(expiry, bool):
                    return ResponsePolicyResult(
                        ResponseDecision.BLOCK,
                        ("emergency containment requires numeric expires_after_minutes",),
                        0,
                    )
                if not 1 <= float(expiry) <= _MAX_EMERGENCY_CONTAINMENT_MINUTES:
                    return ResponsePolicyResult(
                        ResponseDecision.BLOCK,
                        (
                            "emergency containment expiry must be between 1 and "
                            f"{_MAX_EMERGENCY_CONTAINMENT_MINUTES} minutes"
                        ,),
                        0,
                    )
                return ResponsePolicyResult(
                    ResponseDecision.ALLOW,
                    ("bounded emergency containment under pre-authorized playbook",),
                    0,
                )
            if review is None:
                return ResponsePolicyResult(
                    ResponseDecision.ESCALATE,
                    ("containment requires policy/HIL review",),
                    1,
                )

        required_reviewers = 1
        if request.impact_tier >= ResponseImpactTier.DESTRUCTIVE_OR_BUSINESS_CRITICAL:
            required_reviewers = 2
        if request.impact_tier >= ResponseImpactTier.ACCOUNT_OR_PRIVILEGE_CHANGE and review is None:
            return ResponsePolicyResult(
                ResponseDecision.ESCALATE,
                ("high-impact response requires human approval",),
                required_reviewers,
            )

        if review is not None:
            if (
                review.incident_id != request.incident_id
                or _norm(review.action) != _norm(request.action)
                or review.target != request.target
                or review.request_digest != request.request_digest
            ):
                return ResponsePolicyResult(
                    ResponseDecision.BLOCK,
                    ("human review is not bound to exact requested action/target/parameters",),
                    required_reviewers,
                )
            if review.disposition not in {
                HumanDisposition.APPROVE,
                HumanDisposition.EXCEPTION_APPROVED,
            }:
                return ResponsePolicyResult(
                    ResponseDecision.BLOCK,
                    (f"human disposition is {review.disposition.value}",),
                    required_reviewers,
                )
            if not review.rationale.strip():
                return ResponsePolicyResult(
                    ResponseDecision.BLOCK,
                    ("human review requires rationale",),
                    required_reviewers,
                )
            if required_reviewers == 2:
                if not review.second_reviewer or not review.second_reviewer_trust_domain:
                    return ResponsePolicyResult(
                        ResponseDecision.ESCALATE,
                        ("dual independent approval required",),
                        2,
                    )
                if _norm(review.reviewer) == _norm(review.second_reviewer):
                    return ResponsePolicyResult(
                        ResponseDecision.BLOCK,
                        ("self/duplicate dual approval forbidden",),
                        2,
                    )
                if _norm(review.reviewer_trust_domain) == _norm(review.second_reviewer_trust_domain):
                    return ResponsePolicyResult(
                        ResponseDecision.ESCALATE,
                        ("dual approval requires independent trust domains",),
                        2,
                    )

        return ResponsePolicyResult(
            ResponseDecision.ALLOW,
            ("response satisfies deterministic policy and oversight",),
            required_reviewers,
        )


class ThreatKnowledgeRegistry:
    """Immutable-version threat registry with governed activation and rollback."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str], ThreatRecord] = {}
        self._active: dict[str, ActiveThreatVersion] = {}
        self._proposals: dict[str, ThreatUpdateProposal] = {}

    def propose(self, proposal: ThreatUpdateProposal) -> None:
        if not proposal.proposed_by.strip() or not proposal.rationale.strip():
            raise ValueError("threat update requires proposer and rationale")
        _validate_threat_record(proposal.record)
        key = (proposal.record.threat_id, proposal.record.version)
        if key in self._records:
            raise ValueError("threat version is immutable and already exists")
        if proposal.update_id in self._proposals:
            raise ValueError("duplicate threat update_id")
        self._records[key] = proposal.record
        self._proposals[proposal.update_id] = proposal

    def activate(self, review: ThreatUpdateReview) -> ActiveThreatVersion:
        proposal = self._proposals.get(review.update_id)
        if proposal is None:
            raise ValueError("unknown threat update")
        if review.disposition is not HumanDisposition.APPROVE:
            raise PermissionError("only APPROVE review can activate threat update")
        if _norm(review.reviewer) == _norm(proposal.proposed_by):
            raise PermissionError("proposer cannot approve own threat update")
        if (
            proposal.record.source.trust is ThreatSourceTrust.UNTRUSTED_DISCOVERY
            and review.second_reviewer is None
        ):
            raise PermissionError("untrusted threat source requires second independent reviewer")
        if proposal.weakens_existing_control and review.second_reviewer is None:
            raise PermissionError("control weakening requires second independent reviewer")
        if review.second_reviewer and _norm(review.second_reviewer) in {
            _norm(proposal.proposed_by),
            _norm(review.reviewer),
        }:
            raise PermissionError("threat update reviewers must be independent principals")
        if review.regression is None or not review.regression.passed:
            raise PermissionError("activation requires passing regression evidence")
        record = proposal.record
        active = ActiveThreatVersion(
            threat_id=record.threat_id,
            version=record.version,
            digest=record.digest,
            activated_at_utc=datetime.now(timezone.utc).isoformat(),
            update_id=proposal.update_id,
        )
        self._active[record.threat_id] = active
        return active

    def active(self, threat_id: str) -> ActiveThreatVersion | None:
        return self._active.get(threat_id)

    def get(self, threat_id: str, version: str) -> ThreatRecord:
        try:
            return self._records[(threat_id, version)]
        except KeyError as exc:
            raise KeyError(f"unknown threat {threat_id}/{version}") from exc

    def rollback(
        self,
        *,
        threat_id: str,
        version: str,
        authorized_by: str,
        rationale: str,
    ) -> ActiveThreatVersion:
        if not authorized_by.strip() or not rationale.strip():
            raise ValueError("rollback requires authorized_by and rationale")
        record = self.get(threat_id, version)
        active = ActiveThreatVersion(
            threat_id=record.threat_id,
            version=record.version,
            digest=record.digest,
            activated_at_utc=datetime.now(timezone.utc).isoformat(),
            update_id=f"ROLLBACK:{authorized_by}:{_sha256_object(rationale)[:12]}",
        )
        self._active[threat_id] = active
        return active

    def snapshot_digest(self) -> str:
        payload = {key: asdict(value) for key, value in sorted(self._active.items())}
        return _sha256_object(payload)


class CloudGuardAuditStore:
    """Canonical hash-linked audit store for threat, detection, HIL, action and outcome records."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def _records(self) -> list[dict[str, object]]:
        if not self.path.exists():
            return []
        result: list[dict[str, object]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                result.append(json.loads(line))
        return result

    def append(self, record_type: str, payload: Mapping[str, object]) -> dict[str, object]:
        records = self._records()
        sequence = len(records) + 1
        previous_hash = str(records[-1]["record_hash"]) if records else None
        base = {
            "audit_schema_version": "cloudguard-audit/1.0.0",
            "sequence": sequence,
            "record_type": record_type,
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "previous_hash": previous_hash,
            "payload": dict(payload),
        }
        record_hash = _sha256_object(base)
        record = base | {"record_hash": record_hash}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(_canonical_json(record) + "\n")
        return record

    def verify(self) -> tuple[bool, str]:
        records = self._records()
        previous_hash: str | None = None
        for index, record in enumerate(records, start=1):
            if record.get("sequence") != index:
                return False, f"sequence mismatch at record {index}"
            if record.get("previous_hash") != previous_hash:
                return False, f"previous-hash mismatch at record {index}"
            claimed_hash = str(record.get("record_hash", ""))
            base = dict(record)
            base.pop("record_hash", None)
            expected_hash = _sha256_object(base)
            if claimed_hash != expected_hash:
                return False, f"record hash mismatch at record {index}"
            previous_hash = claimed_hash
        return True, f"verified {len(records)} records"


class CloudGuardFeedbackEngine:
    """Conservative field-issue classifier; proposes changes but never activates them."""

    def analyze(self, issue: FieldIssue) -> FeedbackAnalysis:
        if issue.false_positive:
            return FeedbackAnalysis(
                issue.field_issue_id,
                FeedbackGap.FALSE_POSITIVE,
                "benign activity was treated as malicious",
                ("review detector threshold/context", "add benign regression"),
            )
        if not issue.telemetry_complete:
            return FeedbackAnalysis(
                issue.field_issue_id,
                FeedbackGap.TELEMETRY_GAP,
                "required telemetry was missing or incomplete",
                ("propose telemetry update", "add missing-telemetry regression"),
            )
        if not issue.threat_known:
            return FeedbackAnalysis(
                issue.field_issue_id,
                FeedbackGap.THREAT_DB_GAP,
                "field threat was absent from active threat knowledge",
                ("propose threat-db update", "map TTPs and observables"),
            )
        if not issue.detector_fired:
            return FeedbackAnalysis(
                issue.field_issue_id,
                FeedbackGap.DETECTION_GAP,
                "known threat escaped active detection",
                ("propose detector update", "add attack/evasion regressions"),
            )
        if issue.confirmed_unsafe and issue.detected_before_effect and not issue.policy_blocked:
            return FeedbackAnalysis(
                issue.field_issue_id,
                FeedbackGap.POLICY_GAP,
                "unsafe behavior was detected but policy did not prevent effect",
                ("propose response-policy update", "add policy regression"),
            )
        if issue.confirmed_unsafe and not issue.response_effective:
            return FeedbackAnalysis(
                issue.field_issue_id,
                FeedbackGap.RESPONSE_GAP,
                "response did not contain the confirmed threat",
                ("propose playbook update", "add response-outcome regression"),
            )
        if not issue.recovery_effective and issue.response_effective:
            return FeedbackAnalysis(
                issue.field_issue_id,
                FeedbackGap.RECOVERY_GAP,
                "containment succeeded but recovery was ineffective",
                ("propose recovery-playbook update", "add recovery regression"),
            )
        return FeedbackAnalysis(
            issue.field_issue_id,
            FeedbackGap.REVIEW_REQUIRED,
            "deterministic evidence is insufficient for a narrower root cause",
            ("expert review",),
        )


def detection_audit_payload(
    detection: ThreatDetection,
    *,
    threat_db_digest: str,
    response_policy_version: str = RESPONSE_POLICY_VERSION,
) -> dict[str, object]:
    return {
        "detection": asdict(detection),
        "threat_db_digest": threat_db_digest,
        "detection_manifest_version": DETECTION_MANIFEST_VERSION,
        "response_policy_version": response_policy_version,
        "detection_digest": _sha256_object(asdict(detection)),
    }


def threat_update_audit_payload(
    proposal: ThreatUpdateProposal,
    review: ThreatUpdateReview,
    active: ActiveThreatVersion,
) -> dict[str, object]:
    return {
        "update": asdict(proposal),
        "review": asdict(review),
        "active": asdict(active),
        "threat_record_digest": proposal.record.digest,
    }
