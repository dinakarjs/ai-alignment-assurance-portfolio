"""Runtime assurance gateway for proposed agent/tool actions.

The AI agent is treated as an untrusted planner. The gateway evaluates authority,
evidence provenance, trust labels, delegation scope, parameter constraints, and
high-risk oversight before an effectful action is released to a tool broker.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Sequence


class Decision(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    ESCALATE = "ESCALATE"
    REWRITE = "REWRITE"


class TrustLabel(str, Enum):
    TRUSTED_CONTROL = "TRUSTED_CONTROL"
    TRUSTED_DATA = "TRUSTED_DATA"
    UNTRUSTED_USER_DATA = "UNTRUSTED_USER_DATA"
    UNTRUSTED_TOOL_DATA = "UNTRUSTED_TOOL_DATA"
    EXTERNAL_CONTENT = "EXTERNAL_CONTENT"
    MODEL_GENERATED = "MODEL_GENERATED"
    VERIFIED_EVIDENCE = "VERIFIED_EVIDENCE"


@dataclass(frozen=True)
class Capability:
    action: str
    principal: str
    constraints: Mapping[str, object] = field(default_factory=dict)
    transaction_id: str | None = None
    delegated_by: str | None = None
    trust_domain: str | None = None


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    source: str
    trust_label: TrustLabel
    verified: bool
    transaction_id: str | None = None
    action: str | None = None
    attributes: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ProposedAction:
    action: str
    principal: str
    parameters: Mapping[str, object] = field(default_factory=dict)
    transaction_id: str | None = None
    sensitive: bool = False
    high_risk: bool = False
    proposer: str | None = None
    approver: str | None = None
    proposer_trust_domain: str | None = None
    approver_trust_domain: str | None = None
    input_trust: tuple[TrustLabel, ...] = ()
    delegated_by: str | None = None


@dataclass(frozen=True)
class RuntimeDecision:
    decision: Decision
    reasons: tuple[str, ...]
    rewritten_parameters: Mapping[str, object] | None = None


def _matches_constraint(actual: object, expected: object) -> bool:
    if isinstance(expected, Mapping):
        if not isinstance(actual, Mapping):
            return False
        for key, value in expected.items():
            if key == "max" and isinstance(actual, (int, float)):
                if actual > value:  # type: ignore[operator]
                    return False
            elif key == "min" and isinstance(actual, (int, float)):
                if actual < value:  # type: ignore[operator]
                    return False
            elif key not in actual or not _matches_constraint(actual[key], value):
                return False
        return True
    if isinstance(expected, (list, tuple, set)):
        return actual in expected
    return actual == expected


def _capability_matches(capability: Capability, proposed: ProposedAction) -> bool:
    if capability.action != proposed.action or capability.principal != proposed.principal:
        return False
    if capability.transaction_id != proposed.transaction_id:
        return False
    if proposed.delegated_by and capability.delegated_by not in {None, proposed.delegated_by}:
        return False
    for key, expected in capability.constraints.items():
        if key not in proposed.parameters or not _matches_constraint(proposed.parameters[key], expected):
            return False
    return True


class RuntimeAssuranceGateway:
    """Deterministic pre-action gate for effectful tool operations."""

    def decide(
        self,
        proposed: ProposedAction,
        *,
        capabilities: Sequence[Capability],
        evidence: Sequence[EvidenceRecord] = (),
    ) -> RuntimeDecision:
        reasons: list[str] = []

        matching_capability = next(
            (capability for capability in capabilities if _capability_matches(capability, proposed)),
            None,
        )
        if proposed.sensitive or proposed.high_risk:
            if matching_capability is None:
                return RuntimeDecision(Decision.BLOCK, ("no matching parameter-bound capability",))

        if any(
            label in {TrustLabel.UNTRUSTED_TOOL_DATA, TrustLabel.EXTERNAL_CONTENT}
            for label in proposed.input_trust
        ) and matching_capability is None:
            return RuntimeDecision(
                Decision.BLOCK,
                ("untrusted content cannot create authority or a capability",),
            )

        if proposed.high_risk:
            valid_evidence = [
                item
                for item in evidence
                if item.verified
                and item.trust_label is TrustLabel.VERIFIED_EVIDENCE
                and item.transaction_id == proposed.transaction_id
                and item.action in {None, proposed.action}
            ]
            if not valid_evidence:
                return RuntimeDecision(
                    Decision.ESCALATE,
                    ("high-risk action lacks verified transaction-bound evidence",),
                )
            if not proposed.proposer or not proposed.approver:
                return RuntimeDecision(
                    Decision.ESCALATE,
                    ("high-risk action requires named proposer and approver",),
                )
            if proposed.proposer.strip().lower() == proposed.approver.strip().lower():
                return RuntimeDecision(Decision.BLOCK, ("self-approval is forbidden",))
            if (
                proposed.proposer_trust_domain
                and proposed.approver_trust_domain
                and proposed.proposer_trust_domain.strip().lower()
                == proposed.approver_trust_domain.strip().lower()
            ):
                return RuntimeDecision(
                    Decision.ESCALATE,
                    ("high-risk approval requires an independent trust domain",),
                )
            reasons.append("verified evidence and independent approval present")

        if matching_capability is not None:
            reasons.append("parameter-bound capability matched")
        if not reasons:
            reasons.append("no effectful control required")
        return RuntimeDecision(Decision.ALLOW, tuple(reasons))
