"""CLI for the Agent Trace Assurance runtime gateway."""

from __future__ import annotations

from dataclasses import asdict
import argparse
import json
from pathlib import Path
from typing import Mapping

from .runtime_assurance import (
    Capability,
    EvidenceRecord,
    ProposedAction,
    RuntimeAssuranceGateway,
    TrustLabel,
)


def _load(path: str) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a JSON object")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Pre-action Agent Trace Assurance gateway")
    parser.add_argument("input", help="JSON request with proposed_action, capabilities, and evidence")
    args = parser.parse_args()
    data = _mapping(_load(args.input), "runtime request")
    action_data = _mapping(data.get("proposed_action"), "proposed_action")
    proposed = ProposedAction(
        action=str(action_data.get("action", "")),
        principal=str(action_data.get("principal", "")),
        parameters=dict(_mapping(action_data.get("parameters", {}), "parameters")),
        transaction_id=str(action_data["transaction_id"]) if action_data.get("transaction_id") is not None else None,
        sensitive=bool(action_data.get("sensitive", False)),
        high_risk=bool(action_data.get("high_risk", False)),
        proposer=str(action_data["proposer"]) if action_data.get("proposer") is not None else None,
        approver=str(action_data["approver"]) if action_data.get("approver") is not None else None,
        proposer_trust_domain=str(action_data["proposer_trust_domain"]) if action_data.get("proposer_trust_domain") is not None else None,
        approver_trust_domain=str(action_data["approver_trust_domain"]) if action_data.get("approver_trust_domain") is not None else None,
        input_trust=tuple(TrustLabel(str(item)) for item in action_data.get("input_trust", [])),
        delegated_by=str(action_data["delegated_by"]) if action_data.get("delegated_by") is not None else None,
    )
    capabilities = []
    for item in data.get("capabilities", []):
        value = _mapping(item, "capability")
        capabilities.append(
            Capability(
                action=str(value.get("action", "")),
                principal=str(value.get("principal", "")),
                constraints=dict(_mapping(value.get("constraints", {}), "constraints")),
                transaction_id=str(value["transaction_id"]) if value.get("transaction_id") is not None else None,
                delegated_by=str(value["delegated_by"]) if value.get("delegated_by") is not None else None,
                trust_domain=str(value["trust_domain"]) if value.get("trust_domain") is not None else None,
            )
        )
    evidence = []
    for item in data.get("evidence", []):
        value = _mapping(item, "evidence")
        evidence.append(
            EvidenceRecord(
                evidence_id=str(value.get("evidence_id", "")),
                source=str(value.get("source", "")),
                trust_label=TrustLabel(str(value.get("trust_label", TrustLabel.EXTERNAL_CONTENT.value))),
                verified=bool(value.get("verified", False)),
                transaction_id=str(value["transaction_id"]) if value.get("transaction_id") is not None else None,
                action=str(value["action"]) if value.get("action") is not None else None,
                attributes=dict(_mapping(value.get("attributes", {}), "attributes")),
            )
        )
    result = RuntimeAssuranceGateway().decide(
        proposed,
        capabilities=tuple(capabilities),
        evidence=tuple(evidence),
    )
    print(json.dumps(asdict(result), indent=2))


if __name__ == "__main__":
    main()
