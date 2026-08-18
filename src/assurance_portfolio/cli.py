"""Command-line demos for the assurance portfolio."""

from __future__ import annotations

from dataclasses import asdict
import argparse
import json
from pathlib import Path
from typing import Mapping

from .cloudguard import CloudGuardEngine, incident_from_dict
from .trace_assurance import TraceAssuranceEngine
from .verification_copilot import Requirement, VerificationCopilot


def _load(path: str) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _cloudguard_payload(data: Mapping[str, object]) -> dict[str, object]:
    engine = CloudGuardEngine()
    recommendation = engine.assess(incident_from_dict(data))
    payload: dict[str, object] = {"recommendation": asdict(recommendation)}

    decision_data = data.get("decision")
    if isinstance(decision_data, Mapping):
        record = engine.decide(
            recommendation,
            analyst=str(decision_data.get("analyst", "")),
            decision=str(decision_data.get("decision", "")),
            rationale=str(decision_data.get("rationale", "")),
        )
        payload["audit_record"] = asdict(record)
    else:
        payload["audit_record"] = None
        payload["next_step"] = (
            "Provide a decision object with analyst, decision, and rationale to exercise human oversight."
        )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="AI assurance prototype demos")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("cloudguard", "trace", "copilot"):
        child = subparsers.add_parser(name)
        child.add_argument("input", help="Path to a JSON input file")
    args = parser.parse_args()

    data = _load(args.input)
    if args.command == "cloudguard":
        payload = _cloudguard_payload(data)  # type: ignore[arg-type]
    elif args.command == "trace":
        result = TraceAssuranceEngine().evaluate(data)  # type: ignore[arg-type]
        payload = asdict(result)
    else:
        requirements = tuple(
            Requirement(str(item["id"]), str(item["text"])) for item in data  # type: ignore[union-attr]
        )
        payload = [asdict(item) for item in VerificationCopilot().run(requirements)]
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
