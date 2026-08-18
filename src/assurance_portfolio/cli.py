"""Command-line demos for the assurance portfolio."""

from __future__ import annotations

from dataclasses import asdict
import argparse
import json
from pathlib import Path
from typing import Mapping

from .agentic_verification import (
    AgenticVerificationCopilot,
    OpenAIResponsesBackend,
    ScriptedModelBackend,
)
from .cloudguard import CloudGuardEngine, incident_from_dict
from .controlled_evaluation import run_controlled_evaluation
from .rtl_behavioral import run_handshake_rtl_benchmark
from .sva_validation import StructuralSVAValidator, VerilatorSVAValidator
from .trace_assurance import TraceAssuranceEngine
from .verification_benchmark import run_reference_benchmark
from .verification_copilot import Requirement, VerificationCopilot


_SCRIPTED_GOOD_DRAFT = json.dumps(
    {
        "assertion": "assert property (@(posedge clk) request |-> ##[1:4] grant);",
        "scenarios": ["nominal", "boundary", "violation"],
        "coverage_goal": "cover request-to-grant timing",
        "assumptions": ["posedge clk"],
        "rationale": "bounded response",
    }
)
_SCRIPTED_STRICT_DRAFT = json.dumps(
    {
        "assertion": "assert property (@(posedge clk) request |-> ##[1:2] grant);",
        "scenarios": ["nominal", "boundary", "violation"],
        "coverage_goal": "cover request-to-grant timing",
        "assumptions": ["posedge clk"],
        "rationale": "intentionally too-strict scripted candidate",
    }
)
_SCRIPTED_ACCEPT = json.dumps(
    {
        "verdict": "ACCEPT_FOR_TOOL_CHECK",
        "findings": [],
        "recommended_action": "run deterministic tool check",
    }
)
_SCRIPTED_REVISE = json.dumps(
    {
        "verdict": "REVISE",
        "findings": ["timing bound is too strict"],
        "recommended_action": "restore the four-cycle bound",
    }
)


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


def _evaluation_payload(report: object) -> dict[str, object]:
    return asdict(report)  # type: ignore[arg-type]


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
    agentic.add_argument("--model", default=None, help="OpenAI model name; defaults to OPENAI_MODEL")
    agentic.add_argument(
        "--validator",
        choices=("structural", "verilator"),
        default="structural",
        help="Deterministic acceptance validator",
    )

    subparsers.add_parser("benchmark", help="Run the dependency-free seeded trace benchmark")

    rtl_benchmark = subparsers.add_parser(
        "rtl-benchmark",
        help="Compile and simulate the seeded request/grant RTL mutation benchmark",
    )
    rtl_benchmark.add_argument(
        "--rtl-root",
        default="benchmarks/rtl",
        help="Directory containing handshake_good.sv and handshake_late_bug.sv",
    )

    controlled = subparsers.add_parser(
        "controlled-eval",
        help="Run the labelled scripted/offline V7 four-condition comparison",
    )
    controlled.add_argument("--rtl-root", default="benchmarks/rtl")

    live = subparsers.add_parser(
        "controlled-eval-live",
        help="Run the same four-condition comparison with live OpenAI model calls",
    )
    live.add_argument("--rtl-root", default="benchmarks/rtl")
    live.add_argument("--model", default=None, help="OpenAI model name; defaults to OPENAI_MODEL")

    args = parser.parse_args()

    if args.command == "benchmark":
        payload = [
            asdict(item)
            | {
                "accuracy": item.accuracy,
                "defect_detection_rate": item.defect_detection_rate,
            }
            for item in run_reference_benchmark()
        ]
        print(json.dumps(payload, indent=2))
        return

    if args.command == "rtl-benchmark":
        report = run_handshake_rtl_benchmark(args.rtl_root)
        payload = asdict(report) | {
            "mutation_detection_rate": report.mutation_detection_rate,
            "false_positive_count": report.false_positive_count,
            "all_expectations_met": report.all_expectations_met,
        }
        print(json.dumps(payload, indent=2))
        if not report.all_expectations_met:
            raise SystemExit(1)
        return

    if args.command in {"controlled-eval", "controlled-eval-live"}:
        requirement = Requirement(
            "REQ-EVAL-1", "grant shall assert within 4 cycles after request"
        )
        if args.command == "controlled-eval":
            report = run_controlled_evaluation(
                requirement,
                single_generator_backend=ScriptedModelBackend(
                    [_SCRIPTED_STRICT_DRAFT], "scripted-single"
                ),
                reviewed_generator_backend=ScriptedModelBackend(
                    [_SCRIPTED_STRICT_DRAFT], "scripted-reviewed-generator"
                ),
                reviewer_backend=ScriptedModelBackend(
                    [_SCRIPTED_REVISE], "scripted-reviewer"
                ),
                tool_generator_backend=ScriptedModelBackend(
                    [_SCRIPTED_GOOD_DRAFT], "scripted-tool-generator"
                ),
                tool_reviewer_backend=ScriptedModelBackend(
                    [_SCRIPTED_ACCEPT], "scripted-tool-reviewer"
                ),
                rtl_root=args.rtl_root,
                evidence_kind="scripted_offline",
            )
        else:
            report = run_controlled_evaluation(
                requirement,
                single_generator_backend=OpenAIResponsesBackend(model=args.model),
                reviewed_generator_backend=OpenAIResponsesBackend(model=args.model),
                reviewer_backend=OpenAIResponsesBackend(model=args.model),
                tool_generator_backend=OpenAIResponsesBackend(model=args.model),
                tool_reviewer_backend=OpenAIResponsesBackend(model=args.model),
                rtl_root=args.rtl_root,
                evidence_kind="live_model",
            )
        print(json.dumps(_evaluation_payload(report), indent=2))
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
