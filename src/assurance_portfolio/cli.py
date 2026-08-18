"""Command-line demos for the assurance portfolio."""

from __future__ import annotations

from dataclasses import asdict
import argparse
import json
from pathlib import Path

from .cloudguard import CloudGuardEngine, incident_from_dict
from .trace_assurance import TraceAssuranceEngine
from .verification_copilot import Requirement, VerificationCopilot


def _load(path: str) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="AI assurance prototype demos")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("cloudguard", "trace", "copilot"):
        child = subparsers.add_parser(name)
        child.add_argument("input", help="Path to a JSON input file")
    args = parser.parse_args()

    data = _load(args.input)
    if args.command == "cloudguard":
        result = CloudGuardEngine().assess(incident_from_dict(data))  # type: ignore[arg-type]
        payload = asdict(result)
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

