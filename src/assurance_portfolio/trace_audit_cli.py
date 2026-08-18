"""CLI for audited Agent Trace Assurance evaluation, attestation, and governance history."""

from __future__ import annotations

from dataclasses import asdict
import argparse
import json
from pathlib import Path

from .assurance_selftest import run_canary_suite
from .field_issue import FieldIssueAnalyzer, field_issue_from_dict
from .result_integrity import generate_ed25519_keypair, verify_result_attestation
from .schema_registry import SchemaRegistry
from .trace_audit import (
    AuditedTraceAssuranceEngine,
    TraceAuditStore,
    record_check_update,
    record_waiver,
)


def _load(path: str) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent Trace Assurance audit and integrity tooling")
    parser.add_argument(
        "--audit-log",
        default="artifacts/trace-audit/audit.jsonl",
        help="Append-only JSONL audit chain",
    )
    parser.add_argument(
        "--schema-root",
        default="schemas",
        help="Root directory for versioned schema registry operations",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    evaluate = subparsers.add_parser("evaluate", help="Evaluate a trace and append an attested result")
    evaluate.add_argument("input", help="JSON file containing an ordered event list")
    evaluate.add_argument("--check-version", default="agent-trace-checks/6.0.0")
    evaluate.add_argument("--minimum-check-version", default="agent-trace-checks/6.0.0")
    evaluate.add_argument("--schema-version", default="agent-trace/2.0.0")
    evaluate.add_argument("--policy-version", default="agent-trace-policy/2.0.0")
    evaluate.add_argument("--checker-source", default=None)
    evaluate.add_argument("--schema-file", default=None)
    evaluate.add_argument("--policy-file", default=None)
    evaluate.add_argument("--signing-key", default=None, help="Ed25519 private key PEM; never commit this file")
    evaluate.add_argument("--signer-id", default=None)
    evaluate.add_argument("--git-commit", default=None)

    update = subparsers.add_parser("check-update", help="Append a check/schema/policy update record")
    update.add_argument("input", help="JSON file describing the update")

    waiver = subparsers.add_parser("waiver", help="Record a human disposition without rewriting a machine result")
    waiver.add_argument("input", help="JSON waiver/disposition record")

    anchor = subparsers.add_parser("anchor", help="Append a Merkle-root checkpoint for prior audit records")
    anchor.add_argument("--external-reference", default=None)

    subparsers.add_parser("verify", help="Verify sequence, hash chain, and local Merkle anchors")
    subparsers.add_parser("self-test", help="Run mutation/canary tests against the assurance monitor")

    field_issue = subparsers.add_parser("field-issue", help="Replay a field issue, append analysis, and propose feedback")
    field_issue.add_argument("input")

    keygen = subparsers.add_parser("keygen", help="Generate a local Ed25519 attestation keypair")
    keygen.add_argument("--private-key", required=True)
    keygen.add_argument("--public-key", required=True)

    verify_attestation = subparsers.add_parser("verify-attestation", help="Verify an attestation JSON object")
    verify_attestation.add_argument("input", help="JSON file containing an attestation object")
    verify_attestation.add_argument("--public-key", default=None)

    schema_propose = subparsers.add_parser("schema-propose", help="Propose an immutable schema version")
    schema_propose.add_argument("input", help="JSON Schema document")
    schema_propose.add_argument("--kind", required=True)
    schema_propose.add_argument("--version", required=True)
    schema_propose.add_argument("--proposer", required=True)
    schema_propose.add_argument("--previous-version", default=None)

    schema_activate = subparsers.add_parser("schema-activate", help="Independently approve and activate a schema version")
    schema_activate.add_argument("--kind", required=True)
    schema_activate.add_argument("--version", required=True)
    schema_activate.add_argument("--approver", required=True)

    args = parser.parse_args()
    store = TraceAuditStore(args.audit_log)

    if args.command == "verify":
        result = store.verify()
        print(json.dumps(asdict(result), indent=2))
        if not result.valid:
            raise SystemExit(1)
        return

    if args.command == "self-test":
        result = run_canary_suite()
        print(json.dumps(asdict(result), indent=2))
        if not result.passed:
            raise SystemExit(1)
        return

    if args.command == "keygen":
        generate_ed25519_keypair(args.private_key, args.public_key)
        print(json.dumps({"private_key": args.private_key, "public_key": args.public_key}, indent=2))
        return

    if args.command == "anchor":
        record = store.create_anchor(external_reference=args.external_reference)
        print(json.dumps(record, indent=2))
        return

    if args.command == "schema-activate":
        descriptor = SchemaRegistry(args.schema_root).approve_and_activate(
            args.kind, args.version, args.approver
        )
        record = store.append(
            "schema_activation",
            {
                "kind": descriptor.kind,
                "version": descriptor.version,
                "digest": descriptor.digest,
                "compatibility": descriptor.compatibility.value if descriptor.compatibility else None,
                "proposer": descriptor.proposer,
                "approver": descriptor.approver,
            },
        )
        print(json.dumps({"schema": asdict(descriptor), "audit_record": record}, indent=2))
        return

    data = _load(args.input)

    if args.command == "schema-propose":
        if not isinstance(data, dict):
            raise ValueError("schema input must be a JSON object")
        descriptor = SchemaRegistry(args.schema_root).propose(
            kind=args.kind,
            version=args.version,
            document=data,
            proposer=args.proposer,
            previous_version=args.previous_version,
        )
        record = store.append(
            "schema_proposal",
            {
                "kind": descriptor.kind,
                "version": descriptor.version,
                "digest": descriptor.digest,
                "compatibility": descriptor.compatibility.value if descriptor.compatibility else None,
                "previous_version": descriptor.previous_version,
                "proposer": descriptor.proposer,
            },
        )
        print(json.dumps({"schema": asdict(descriptor), "audit_record": record}, indent=2))
        return

    if args.command == "verify-attestation":
        if not isinstance(data, dict):
            raise ValueError("attestation input must be a JSON object")
        result = verify_result_attestation(data, args.public_key)
        print(json.dumps(asdict(result), indent=2))
        if result.status.value == "INVALID":
            raise SystemExit(1)
        return

    if args.command == "check-update":
        if not isinstance(data, dict):
            raise ValueError("check-update input must be a JSON object")
        record = record_check_update(store, data)
        print(json.dumps(record, indent=2))
        return

    if args.command == "waiver":
        if not isinstance(data, dict):
            raise ValueError("waiver input must be a JSON object")
        record = record_waiver(store, data)
        print(json.dumps(record, indent=2))
        return

    if args.command == "field-issue":
        if not isinstance(data, dict):
            raise ValueError("field-issue input must be a JSON object")
        analysis = FieldIssueAnalyzer().analyze(field_issue_from_dict(data))
        record = store.append("field_issue_analysis", asdict(analysis))
        print(json.dumps({"analysis": asdict(analysis), "audit_record": record}, indent=2))
        return

    if not isinstance(data, list):
        raise ValueError("evaluation input must be a JSON event list")
    engine = AuditedTraceAssuranceEngine(
        store,
        check_version=args.check_version,
        minimum_check_version=args.minimum_check_version,
        event_schema_version=args.schema_version,
        policy_version=args.policy_version,
        checker_source_path=args.checker_source,
        schema_path=args.schema_file,
        policy_path=args.policy_file,
        signing_key_path=args.signing_key,
        signer_id=args.signer_id,
        git_commit_sha=args.git_commit,
        configuration={
            "cli": "assurance-trace-audit",
            "schema_version": args.schema_version,
            "policy_version": args.policy_version,
        },
    )
    report, record = engine.evaluate(data)
    print(json.dumps({"report": asdict(report), "audit_record": record}, indent=2))


if __name__ == "__main__":
    main()
