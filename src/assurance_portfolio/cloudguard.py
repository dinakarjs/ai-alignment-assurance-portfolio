"""Explainable cloud-threat triage with mandatory human oversight."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Mapping


DEFAULT_WEIGHTS = {
    "impossible_travel": 42,
    "privilege_escalation": 25,
    "failed_logins": 15,
    "malicious_ip": 12,
    "time_anomaly": 6,
}


@dataclass(frozen=True)
class Incident:
    incident_id: str
    account_id: str
    signals: Mapping[str, float]


@dataclass(frozen=True)
class Recommendation:
    incident_id: str
    risk_score: int
    confidence: float
    top_reasons: tuple[tuple[str, float], ...]
    recommended_action: str
    human_approval_required: bool
    explanation_method: str = "additive SHAP-style attribution"


@dataclass(frozen=True)
class AuditRecord:
    incident_id: str
    recommendation_hash: str
    analyst: str
    decision: str
    rationale: str
    timestamp: str


class CloudGuardEngine:
    """Deterministic reference implementation of the workshop design.

    Signals are normalized to [0, 1]. Each signal contribution is its
    normalized value multiplied by a transparent weight. This is a SHAP-style
    additive explanation, not a fitted SHAP explainer for a production model.
    """

    def __init__(self, weights: Mapping[str, float] | None = None) -> None:
        self.weights = dict(weights or DEFAULT_WEIGHTS)

    def assess(self, incident: Incident) -> Recommendation:
        unknown = set(incident.signals) - set(self.weights)
        if unknown:
            raise ValueError(f"Unknown signals: {sorted(unknown)}")

        contributions: list[tuple[str, float]] = []
        for signal, weight in self.weights.items():
            value = float(incident.signals.get(signal, 0.0))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"Signal {signal!r} must be between 0 and 1")
            contributions.append((signal, round(value * weight, 2)))

        contributions.sort(key=lambda item: item[1], reverse=True)
        score = max(0, min(100, round(sum(value for _, value in contributions))))
        active_weight = sum(
            self.weights[name] for name, value in incident.signals.items() if value > 0
        )
        confidence = round(min(0.99, 0.50 + active_weight / 200), 2)

        if score >= 80:
            action = "disable_account"
        elif score >= 50:
            action = "escalate_investigation"
        else:
            action = "continue_monitoring"

        return Recommendation(
            incident_id=incident.incident_id,
            risk_score=score,
            confidence=confidence,
            top_reasons=tuple(contributions),
            recommended_action=action,
            human_approval_required=action == "disable_account",
        )

    def decide(
        self,
        recommendation: Recommendation,
        *,
        analyst: str,
        decision: str,
        rationale: str,
    ) -> AuditRecord:
        allowed = {"approve", "reject", "investigate"}
        if decision not in allowed:
            raise ValueError(f"Decision must be one of {sorted(allowed)}")
        if recommendation.human_approval_required and not analyst.strip():
            raise PermissionError("A named analyst is required for high-risk action")
        if not rationale.strip():
            raise ValueError("A rationale is required for auditability")

        payload = json.dumps(asdict(recommendation), sort_keys=True)
        return AuditRecord(
            incident_id=recommendation.incident_id,
            recommendation_hash=sha256(payload.encode()).hexdigest(),
            analyst=analyst,
            decision=decision,
            rationale=rationale,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )


def incident_from_dict(data: Mapping[str, object]) -> Incident:
    return Incident(
        incident_id=str(data["incident_id"]),
        account_id=str(data["account_id"]),
        signals=dict(data["signals"]),  # type: ignore[arg-type]
    )

