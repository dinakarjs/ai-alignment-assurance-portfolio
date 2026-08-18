"""CLI for evaluation-information-flow and CI/CD privilege integrity checks."""

from __future__ import annotations

from dataclasses import asdict
import argparse
import json
from pathlib import Path

from .cicd_integrity import TriggerTrust, WorkflowContext, validate_cicd_integrity
from .evaluation_integrity import (
    AccessRecord,
    EvalLabel,
    EvaluationArtifact,
    EvaluationRun,
    compare_attribution,
    validate_evaluation_integrity,
)


def _load(path: str) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _evaluation_from_dict(data: dict[str, object]) -> EvaluationRun:
    artifacts = tuple(
        EvaluationArtifact(
            artifact_id=str(item["artifact_id"]),
            producer=str(item["producer"]),
            labels=tuple(EvalLabel(str(label)) for label in item.get("labels", [])),
            parents=tuple(str(parent) for parent in item.get("parents", [])),
            digest=str(item["digest"]) if item.get("digest") is not None else None,
        )
        for item in data.get("artifacts", [])
    )
    accesses = tuple(
        AccessRecord(
            principal=str(item["principal"]),
            artifact_id=str(item["artifact_id"]),
            sequence=int(item["sequence"]),
        )
        for item in data.get("accesses", [])
    )
    return EvaluationRun(
        artifacts=artifacts,
        accesses=accesses,
        prediction_artifact_id=str(data["prediction_artifact_id"]),
        prediction_commit_sequence=int(data["prediction_commit_sequence"]),
        ground_truth_release_sequence=int(data["ground_truth_release_sequence"]),
        evaluator_principals=tuple(str(item) for item in data.get("evaluator_principals", [])),
        system_principals=tuple(str(item) for item in data.get("system_principals", [])),
        scorer_principal=str(data["scorer_principal"]),
    )


def _cicd_from_dict(data: dict[str, object]) -> WorkflowContext:
    return WorkflowContext(
        workflow_name=str(data["workflow_name"]),
        trigger=str(data["trigger"]),
        trigger_trust=TriggerTrust(str(data["trigger_trust"])),
        source_ref=str(data["source_ref"]),
        trusted_control_ref=str(data["trusted_control_ref"]),
        actor=str(data["actor"]),
        agent_principal=str(data["agent_principal"]),
        requested_action=str(data["requested_action"]),
        requested_permissions=tuple(str(item) for item in data.get("requested_permissions", [])),
        runner_permissions=tuple(str(item) for item in data.get("runner_permissions", [])),
        secret_names=tuple(str(item) for item in data.get("secret_names", [])),
        modifies_workflow=bool(data.get("modifies_workflow", False)),
        modifies_policy=bool(data.get("modifies_policy", False)),
        production_effect=bool(data.get("production_effect", False)),
        artifact_digest=str(data["artifact_digest"]) if data.get("artifact_digest") is not None else None,
        reviewed_artifact_digest=(
            str(data["reviewed_artifact_digest"])
            if data.get("reviewed_artifact_digest") is not None
            else None
        ),
        approver=str(data["approver"]) if data.get("approver") is not None else None,
        approver_trust_domain=(
            str(data["approver_trust_domain"])
            if data.get("approver_trust_domain") is not None
            else None
        ),
        agent_trust_domain=(
            str(data["agent_trust_domain"])
            if data.get("agent_trust_domain") is not None
            else None
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent Trace Assurance integrity-boundary checks")
    subparsers = parser.add_subparsers(dest="command", required=True)

    evaluation = subparsers.add_parser("evaluation", help="Validate evaluation leakage/collusion boundaries")
    evaluation.add_argument("input")

    cicd = subparsers.add_parser("cicd", help="Validate AI-assisted CI/CD privilege boundaries")
    cicd.add_argument("input")

    attribution = subparsers.add_parser("attribution", help="Compare apparent gain with privileged-channel isolation")
    attribution.add_argument("--baseline", type=float, required=True)
    attribution.add_argument("--full", type=float, required=True)
    attribution.add_argument("--isolated", type=float, required=True)

    args = parser.parse_args()
    if args.command == "attribution":
        print(
            json.dumps(
                asdict(
                    compare_attribution(
                        baseline_score=args.baseline,
                        full_score=args.full,
                        isolated_score=args.isolated,
                    )
                ),
                indent=2,
            )
        )
        return

    data = _load(args.input)
    if not isinstance(data, dict):
        raise ValueError("integrity input must be a JSON object")

    if args.command == "evaluation":
        report = validate_evaluation_integrity(_evaluation_from_dict(data))
        print(json.dumps(asdict(report), indent=2))
        if not report.valid:
            raise SystemExit(1)
        return

    report = validate_cicd_integrity(_cicd_from_dict(data))
    print(json.dumps(asdict(report), indent=2))
    if report.decision.value != "ALLOW":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
