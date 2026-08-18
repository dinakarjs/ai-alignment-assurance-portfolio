"""CLI for audited Agent Trace Assurance evaluation and check-update history."""

from __future__ import annotations

from dataclasses import asdict
import argparse
import json
from pathlib import Path

from .trace_audit import AuditedTraceAssuranceEngine, TraceAuditStore, record_check_update


def _load(path: str) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent Trace Assurance audit tooling")
    parser.add_argument(
        "--audit-log",
        default="artifacts/trace-audit/audit.jsonl",
        help="Append-only JSONL audit chain",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    evaluate = subparsers.add_parser("evaluate", help="Evaluate a trace and append its result")
    evaluate.add_argument("input", help="JSON file containing an ordered event list")
    evaluate.add_argument("--check-version", default="agent-trace-checks/4.0.0")
    evaluate.add_argument("--schema-version", default="agent-trace/1.0.0")
    evaluate.add_argument("--policy-version", default="agent-trace-policy/1.0.0")

    update = subparsers.add_parser("check-update", help="Append a check/schema/policy update record")
    update.add_argument("input", help="JSON file describing the update")

    subparsers.add_parser("verify", help="Verify sequence and hash-chain integrity")

    args = parser.parse_args()
    store = TraceAuditStore(args.audit_log)

    if args.command == "verify":
        result = store.verify()
        print(json.dumps(asdict(result), indent=2))
        if not result.valid:
            raise SystemExit(1)
        return

    data = _load(args.input)
    if args.command == "check-update":
        if not isinstance(data, dict):
            raise ValueError("check-update input must be a JSON object")
        record = record_check_update(store, data)
        print(json.dumps(record, indent=2))
        return

    if not isinstance(data, list):
        raise ValueError("evaluation input must be a JSON event list")
    engine = AuditedTraceAssuranceEngine(
        store,
        check_version=args.check_version,
        event_schema_version=args.schema_version,
        policy_version=args.policy_version,
    )
    report, record = engine.evaluate(data)
    print(json.dumps({"report": asdict(report), "audit_record": record}, indent=2))


if __name__ == "__main__":
    main()
