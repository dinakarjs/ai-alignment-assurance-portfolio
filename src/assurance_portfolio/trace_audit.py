"""Append-only audit trail for Agent Trace Assurance evaluations and check updates."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Iterable, Mapping
from uuid import uuid4

from .trace_assurance import AssuranceReport, TraceAssuranceEngine

AUDIT_SCHEMA_VERSION = "trace-audit/1.0.0"
DEFAULT_CHECK_VERSION = "agent-trace-checks/4.0.0"
DEFAULT_EVENT_SCHEMA_VERSION = "agent-trace/1.0.0"
DEFAULT_POLICY_VERSION = "agent-trace-policy/1.0.0"


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AuditVerification:
    valid: bool
    records: int
    first_invalid_index: int | None = None
    detail: str = ""


class TraceAuditStore:
    """JSONL-backed append-only logical audit chain.

    Hash chaining detects modification/reordering within the stored file. It is not
    a substitute for external immutable/WORM storage or cryptographic signatures.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def _records(self) -> list[dict[str, object]]:
        if not self.path.exists():
            return []
        records: list[dict[str, object]] = []
        for line_no, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"audit line {line_no} is not a JSON object")
            records.append(value)
        return records

    def append(self, record_type: str, payload: Mapping[str, object]) -> dict[str, object]:
        records = self._records()
        previous_hash = str(records[-1]["record_hash"]) if records else None
        body: dict[str, object] = {
            "audit_schema_version": AUDIT_SCHEMA_VERSION,
            "sequence": len(records) + 1,
            "record_type": record_type,
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "previous_hash": previous_hash,
            "payload": dict(payload),
        }
        record = body | {"record_hash": _sha256(body)}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(_canonical(record) + "\n")
        return record

    def verify(self) -> AuditVerification:
        try:
            records = self._records()
        except (ValueError, json.JSONDecodeError) as exc:
            return AuditVerification(False, 0, 0, f"audit log could not be parsed: {exc}")
        previous_hash: str | None = None
        for index, record in enumerate(records):
            expected_sequence = index + 1
            if record.get("sequence") != expected_sequence:
                return AuditVerification(False, len(records), index, "sequence mismatch")
            if record.get("previous_hash") != previous_hash:
                return AuditVerification(False, len(records), index, "previous-hash mismatch")
            supplied = record.get("record_hash")
            body = {key: value for key, value in record.items() if key != "record_hash"}
            computed = _sha256(body)
            if supplied != computed:
                return AuditVerification(False, len(records), index, "record hash mismatch")
            previous_hash = str(supplied)
        return AuditVerification(True, len(records), None, "hash chain verified")


class AuditedTraceAssuranceEngine:
    def __init__(
        self,
        audit_store: TraceAuditStore,
        *,
        check_version: str = DEFAULT_CHECK_VERSION,
        event_schema_version: str = DEFAULT_EVENT_SCHEMA_VERSION,
        policy_version: str = DEFAULT_POLICY_VERSION,
    ) -> None:
        self.audit_store = audit_store
        self.engine = TraceAssuranceEngine()
        self.check_version = check_version
        self.event_schema_version = event_schema_version
        self.policy_version = policy_version

    @property
    def check_set_fingerprint(self) -> str:
        return _sha256(
            {
                "check_version": self.check_version,
                "properties": list(self.engine.PROPERTIES),
                "event_schema_version": self.event_schema_version,
                "policy_version": self.policy_version,
            }
        )

    def evaluate(self, events: Iterable[Mapping[str, object]]) -> tuple[AssuranceReport, dict[str, object]]:
        trace = [dict(item) for item in events]
        report = self.engine.evaluate(trace)
        run_id = f"trace-run-{uuid4()}"
        payload: dict[str, object] = {
            "run_id": run_id,
            "trace_fingerprint": _sha256(trace),
            "event_count": len(trace),
            "check_version": self.check_version,
            "check_set_fingerprint": self.check_set_fingerprint,
            "event_schema_version": self.event_schema_version,
            "policy_version": self.policy_version,
            "result": report.status.value,
            "violations": [asdict(item) for item in report.violations],
            "covered_properties": list(report.covered_properties),
            "uncovered_properties": list(report.uncovered_properties),
        }
        audit_record = self.audit_store.append("evaluation", payload)
        return report, audit_record


def record_check_update(store: TraceAuditStore, update: Mapping[str, object]) -> dict[str, object]:
    required = ("from_version", "to_version", "change_type", "rationale", "proposer")
    missing = [field for field in required if not str(update.get(field, "")).strip()]
    if missing:
        raise ValueError(f"check update missing required fields: {', '.join(missing)}")
    proposer = str(update.get("proposer", "")).strip().lower()
    approver = str(update.get("approver", "")).strip().lower()
    status = str(update.get("status", "PROPOSED")).strip().upper()
    if status == "APPROVED":
        if not approver:
            raise ValueError("approved check update requires approver")
        if proposer == approver:
            raise ValueError("check update proposer and approver must be independent")
    payload: dict[str, object] = {
        "update_id": str(update.get("update_id") or f"check-update-{uuid4()}"),
        "from_version": str(update["from_version"]),
        "to_version": str(update["to_version"]),
        "change_type": str(update["change_type"]).upper(),
        "rationale": str(update["rationale"]),
        "source_issue": update.get("source_issue"),
        "source_evaluation_run": update.get("source_evaluation_run"),
        "checks_added": list(update.get("checks_added", [])),
        "checks_removed": list(update.get("checks_removed", [])),
        "checks_modified": list(update.get("checks_modified", [])),
        "schema_updates": list(update.get("schema_updates", [])),
        "policy_updates": list(update.get("policy_updates", [])),
        "proposer": str(update["proposer"]),
        "approver": str(update.get("approver", "")) or None,
        "status": status,
    }
    return store.append("check_update", payload)
