"""Command-line demos for the assurance portfolio."""

from __future__ import annotations

from dataclasses import asdict
import argparse
import json
import os
from pathlib import Path
from typing import Mapping

from .agentic_verification import (
    AgenticVerificationCopilot,
    OpenAIResponsesBackend,
    ScriptedModelBackend,
)
from .cloudguard import CloudGuardEngine, incident_from_dict
from .controlled_evaluation import run_controlled_evaluation
from .corpus_benchmark import CorpusCase, default_corpus
from .corpus_evaluation import run_corpus_trial, summarize_trials
from .rtl_behavioral import run_handshake_rtl_benchmark
from .sva_validation import StructuralSVAValidator, VerilatorSVAValidator
from .trace_assurance import TraceAssuranceEngine
from .verification_benchmark import run_reference_benchmark
from .verification_copilot import ArtifactGenerator, Requirement, VerificationCopilot


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


def _scripted_model_draft(case: CorpusCase, *, strict_bounded: bool = False) -> str:
    assertion = ArtifactGenerator().generate(Requirement(case.case_id, case.requirement)).assertion
    if strict_bounded and case.case_id == "BR-001":
        assertion = "assert property (@(posedge clk) request |-> ##[1:2] grant);"
    return json.dumps(
        {
            "assertion": assertion,
            "scenarios": ["nominal", "boundary-or-transition", "violation"],
            "coverage_goal": f"exercise {case.case_id} good and mutated RTL",
            "assumptions": ["benchmark fixture signal mapping is authoritative"],
            "rationale": f"scripted candidate for {case.family.value}",
        }
    )


def _scripted_reviewer(case: CorpusCase, *, revise_bounded: bool = False) -> str:
    if revise_bounded and case.case_id == "BR-001":
        return json.dumps(
            {
                "verdict": "REVISE",
                "findings": ["bounded-response candidate requires revision before execution"],
                "recommended_action": "restore the reference four-cycle bound",
            }
        )
    return _SCRIPTED_ACCEPT


def _run_scripted_corpus(trials: int, rtl_root: str) -> tuple[object, object]:
    if trials < 1:
        raise ValueError("trials must be >= 1")
    runs = []
    for trial_id in range(1, trials + 1):
        runs.append(
            run_corpus_trial(
                trial_id,
                single_backend_factory=lambda case: ScriptedModelBackend(
                    [_scripted_model_draft(case, strict_bounded=True)],
                    f"scripted-single-{case.case_id}",
                ),
                reviewed_generator_factory=lambda case: ScriptedModelBackend(
                    [_scripted_model_draft(case, strict_bounded=True)],
                    f"scripted-reviewed-generator-{case.case_id}",
                ),
                reviewer_factory=lambda case: ScriptedModelBackend(
                    [_scripted_reviewer(case, revise_bounded=True)],
                    f"scripted-reviewer-{case.case_id}",
                ),
                tool_generator_factory=lambda case: ScriptedModelBackend(
                    [_scripted_model_draft(case)],
                    f"scripted-tool-generator-{case.case_id}",
                ),
                tool_reviewer_factory=lambda case: ScriptedModelBackend(
                    [_scripted_reviewer(case)],
                    f"scripted-tool-reviewer-{case.case_id}",
                ),
                corpus=default_corpus(),
                rtl_root=rtl_root,
                evidence_kind="scripted_offline",
                model_label="scripted-fixtures",
                prompt_version="v8.0",
            )
        )
    trial_tuple = tuple(runs)
    return trial_tuple, summarize_trials(trial_tuple)


def _run_live_corpus(trials: int, rtl_root: str, model: str | None) -> tuple[object, object]:
    if trials < 1:
        raise ValueError("trials must be >= 1")
    model_label = model or os.getenv("OPENAI_MODEL")
    if not model_label:
        raise ValueError("live corpus evaluation requires --model or OPENAI_MODEL")
    runs = []
    for trial_id in range(1, trials + 1):
        factory = lambda case: OpenAIResponsesBackend(model=model_label)
        runs.append(
            run_corpus_trial(
                trial_id,
                single_backend_factory=factory,
                reviewed_generator_factory=factory,
                reviewer_factory=factory,
                tool_generator_factory=factory,
                tool_reviewer_factory=factory,
                corpus=default_corpus(),
                rtl_root=rtl_root,
                evidence_kind="live_model",
                model_label=model_label,
                prompt_version="v8.0",
            )
        )
    trial_tuple = tuple(runs)
    return trial_tuple, summarize_trials(trial_tuple)


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
    rtl_benchmark.add_argument("--rtl-root", default="benchmarks/rtl")

    controlled = subparsers.add_parser(
        "controlled-eval",
        help="Run the labelled scripted/offline V7 four-condition comparison",
    )
    controlled.add_argument("--rtl-root", default="benchmarks/rtl")

    live = subparsers.add_parser(
        "controlled-eval-live",
        help="Run the V7 four-condition comparison with live OpenAI model calls",
    )
    live.add_argument("--rtl-root", default="benchmarks/rtl")
    live.add_argument("--model", default=None, help="OpenAI model name; defaults to OPENAI_MODEL")

    corpus_eval = subparsers.add_parser(
        "corpus-eval",
        help="Run repeated scripted/offline V8 evaluation across three RTL requirement families",
    )
    corpus_eval.add_argument("--rtl-root", default="benchmarks/rtl")
    corpus_eval.add_argument("--trials", type=int, default=3)

    corpus_live = subparsers.add_parser(
        "corpus-eval-live",
        help="Run repeated live-model V8 evaluation across the RTL corpus",
    )
    corpus_live.add_argument("--rtl-root", default="benchmarks/rtl")
    corpus_live.add_argument("--trials", type=int, default=1)
    corpus_live.add_argument("--model", default=None, help="OpenAI model name; defaults to OPENAI_MODEL")

    args = parser.parse_args()

    if args.command == "benchmark":
        payload = [
            asdict(item)
            | {"accuracy": item.accuracy, "defect_detection_rate": item.defect_detection_rate}
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

    if args.command in {"corpus-eval", "corpus-eval-live"}:
        if args.command == "corpus-eval":
            trials, summary = _run_scripted_corpus(args.trials, args.rtl_root)
        else:
            trials, summary = _run_live_corpus(args.trials, args.rtl_root, args.model)
        print(json.dumps({"summary": asdict(summary), "trials": [asdict(item) for item in trials]}, indent=2))
        return

    if args.command in {"controlled-eval", "controlled-eval-live"}:
        requirement = Requirement("REQ-EVAL-1", "grant shall assert within 4 cycles after request")
        if args.command == "controlled-eval":
            report = run_controlled_evaluation(
                requirement,
                single_generator_backend=ScriptedModelBackend([_SCRIPTED_STRICT_DRAFT], "scripted-single"),
                reviewed_generator_backend=ScriptedModelBackend([_SCRIPTED_STRICT_DRAFT], "scripted-reviewed-generator"),
                reviewer_backend=ScriptedModelBackend([_SCRIPTED_REVISE], "scripted-reviewer"),
                tool_generator_backend=ScriptedModelBackend([_SCRIPTED_GOOD_DRAFT], "scripted-tool-generator"),
                tool_reviewer_backend=ScriptedModelBackend([_SCRIPTED_ACCEPT], "scripted-tool-reviewer"),
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
        validator = VerilatorSVAValidator() if args.validator == "verilator" else StructuralSVAValidator()
        copilot = AgenticVerificationCopilot(
            generator_backend=generator_backend,
            reviewer_backend=reviewer_backend,
            validator=validator,
        )
        payload = [asdict(copilot.propose(requirement)) for requirement in _requirements(data)]

    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
