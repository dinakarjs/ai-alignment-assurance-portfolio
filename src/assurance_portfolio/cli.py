"""Command-line demos for the assurance portfolio."""

from __future__ import annotations

from dataclasses import asdict
import argparse
import json
from pathlib import Path
from typing import Mapping

from .agentic_verification import AgenticVerificationCopilot, OpenAIResponsesBackend
from .cloudguard import CloudGuardEngine, incident_from_dict
from .sva_validation import StructuralSVAValidator, VerilatorSVAValidator
from .trace_assurance import TraceAssuranceEngine
from .verification_benchmark import run_reference_benchmark
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


def _requirements(data: object) -> tuple[Requirement, ...]:
    if not isinstance(data, list):
        raise ValueError("requirements input must be a JSON list")
    return tuple(
        Requirement(str(item["id"]), str(item["text"]))
        for item in data
        if isinstance(item, Mapping)
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="AI assurance prototype demos")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("cloudguard", "trace", "copilot"):
        child = subparsers.add_parser(name)
        child.add_argument("input", help="Path to a JSON input file")

    agentic = subparsers.add_parser(
        "agentic", help="Run model-backed generator/reviewer roles using the OpenAI Responses API"
    )
    agentic.add_argument("input", help="Path to a JSON requirements list")
    agentic.add_argument(
        "--model",
        default=None,
        help="OpenAI model name; defaults to OPENAI_MODEL",
    )
    agentic.add_argument(
        "--validator",
        choices=("structural", "verilator"),
        default="structural",
        help="Deterministic acceptance validator",
    )

    subparsers.add_parser(
        "benchmark",
        help="Run the dependency-free seeded trace benchmark",
    )

    args = parser.parse_args()

    if args.command == "benchmark":
        payload = [asdict(item) | {"accuracy": item.accuracy, "defect_detection_rate": item.defect_detection_rate} for item in run_reference_benchmark()]
        print(json.dumps(payload, indent=2))
        return

    data = _load(args.input)
    if args.command == "cloudguard":
        payload = _cloudguard_payload(data)  # type: ignore[arg-type]
    elif args.command == "trace":
        result = TraceAssuranceEngine().evaluate(data)  # type: ignore[arg-type]
        payload = asdict(result)
    elif args.command == "copilot":
        payload = [asdict(item) for item in VerificationCopilot().run(_requirements(data))]
    else:
        generator_backend = OpenAIResponsesBackend(model=args.model)
        reviewer_backend = OpenAIResponsesBackend(model=args.model)
        validator = (
            VerilatorSVAValidator()
            if args.validator == "verilator"
            else StructuralSVAValidator()
        )
        copilot = AgenticVerificationCopilot(
            generator_backend=generator_backend,
            reviewer_backend=reviewer_backend,
            validator=validator,
        )
        payload = [asdict(copilot.propose(requirement)) for requirement in _requirements(data)]

    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
