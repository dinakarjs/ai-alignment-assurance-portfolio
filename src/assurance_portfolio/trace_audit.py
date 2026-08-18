"""Append-only audit trail for Agent Trace Assurance evaluations and governance changes."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Iterable, Mapping
from uuid import uuid4

from .assurance_selftest import deterministic_replay
from .causal_trace import validate_causal_trace
from .result_integrity import (
    IntegrityStatus,
    build_result_attestation,
    digest_or_identifier,
    merkle_root_hex,
    sha256_file,
    sha256_object,
)
from .schema_registry import InstanceValidation, SchemaRegistry
from .trace_assurance import AssuranceReport, TraceAssuranceEngine

AUDIT_SCHEMA_VERSION = "trace-audit/2.0.0"
DEFAULT_CHECK_VERSION = "agent-trace-checks/6.0.0"
DEFAULT_MINIMUM_CHECK_VERSION = "agent-trace-checks/6.0.0"
DEFAULT_EVENT_SCHEMA_VERSION = "agent-trace/2.0.0"
DEFAULT_POLICY_VERSION = "agent-trace-policy/2.0.0"


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(value: object) -> str:
    return sha256_object(value)


@dataclass(frozen=True)
class AuditVerification:
    valid: bool
    records: int
    first_invalid_index: int | None = None
    detail: str = ""


class TraceAuditStore:
    """JSONL-backed append-only logical audit chain.

    Hash chaining and optional Merkle anchor records make inconsistent mutation or
    reordering detectable. External storage/signature anchoring is still required
    to prevent a privileged actor from replacing the complete local history.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def records(self) -> list[dict[str, object]]:
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
        records = self.records()
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

    def create_anchor(self, *, external_reference: str | None = None) -> dict[str, object]:
        records = self.records()
        hashes = [str(item["record_hash"]) for item in records]
        payload: dict[str, object] = {
            "anchored_record_count": len(records),
            "last_record_hash": hashes[-1] if hashes else None,
            "merkle_root": merkle_root_hex(hashes),
            "external_reference": external_reference,
        }
        return self.append("merkle_anchor", payload)

    def verify(self) -> AuditVerification:
        try:
            records = self.records()
        except (ValueError, json.JSONDecodeError) as exc:
            return AuditVerification(False, 0, 0, f"audit log could not be parsed: {exc}")
        previous_hash: str | None = None
        preceding_hashes: list[str] = []
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
            if record.get("record_type") == "merkle_anchor":
                payload = record.get("payload", {})
                if not isinstance(payload, Mapping):
                    return AuditVerification(False, len(records), index, "anchor payload malformed")
                if payload.get("anchored_record_count") != len(preceding_hashes):
                    return AuditVerification(False, len(records), index, "anchor record count mismatch")
                if payload.get("merkle_root") != merkle_root_hex(preceding_hashes):
                    return AuditVerification(False, len(records), index, "anchor Merkle root mismatch")
            previous_hash = str(supplied)
            preceding_hashes.append(str(supplied))
        return AuditVerification(True, len(records), None, "hash chain and local anchors verified")


class AuditedTraceAssuranceEngine:
    def __init__(
        self,
        audit_store: TraceAuditStore,
        *,
        check_version: str = DEFAULT_CHECK_VERSION,
        minimum_check_version: str = DEFAULT_MINIMUM_CHECK_VERSION,
        event_schema_version: str = DEFAULT_EVENT_SCHEMA_VERSION,
        policy_version: str = DEFAULT_POLICY_VERSION,
        checker_source_path: str | Path | None = None,
        check_manifest_path: str | Path | None = None,
        schema_path: str | Path | None = None,
        policy_path: str | Path | None = None,
        signing_key_path: str | Path | None = None,
        signer_id: str | None = None,
        git_commit_sha: str | None = None,
        configuration: Mapping[str, object] | None = None,
    ) -> None:
        self.audit_store = audit_store
        self.engine = TraceAssuranceEngine()
        self.check_version = check_version
        self.minimum_check_version = minimum_check_version
        self.event_schema_version = event_schema_version
        self.policy_version = policy_version
        self.checker_source_path = Path(checker_source_path) if checker_source_path else Path(__file__).with_name("trace_assurance.py")
        self.check_manifest_path = Path(check_manifest_path) if check_manifest_path else None
        self.schema_path = Path(schema_path) if schema_path else None
        self.policy_path = Path(policy_path) if policy_path else None
        self.signing_key_path = Path(signing_key_path) if signing_key_path else None
        self.signer_id = signer_id
        self.git_commit_sha = git_commit_sha
        self.configuration = dict(configuration or {})

    @property
    def checker_digest(self) -> str:
        return sha256_file(self.checker_source_path)

    @property
    def check_manifest_digest(self) -> str:
        return digest_or_identifier(self.check_manifest_path, self.check_version)

    @property
    def schema_digest(self) -> str:
        return digest_or_identifier(self.schema_path, self.event_schema_version)

    @property
    def policy_digest(self) -> str:
        return digest_or_identifier(self.policy_path, self.policy_version)

    @property
    def artifact_binding_complete(self) -> bool:
        return (
            self.checker_source_path.exists()
            and self.check_manifest_path is not None
            and self.check_manifest_path.exists()
            and self.schema_path is not None
            and self.schema_path.exists()
            and self.policy_path is not None
            and self.policy_path.exists()
        )

    def _required_checks(self) -> tuple[str, ...]:
        if self.check_manifest_path is None:
            return tuple(self.engine.PROPERTIES)
        value = json.loads(self.check_manifest_path.read_text(encoding="utf-8"))
        if not isinstance(value, Mapping):
            raise ValueError("check manifest must be a JSON object")
        declared_version = str(value.get("check_version", ""))
        if declared_version and declared_version != self.check_version:
            raise ValueError(
                f"check manifest version {declared_version!r} does not match configured {self.check_version!r}"
            )
        checks = value.get("required_checks")
        if not isinstance(checks, list) or not all(isinstance(item, str) and item.strip() for item in checks):
            raise ValueError("check manifest required_checks must be a non-empty string list")
        return tuple(checks)

    @property
    def check_set_fingerprint(self) -> str:
        return _sha256(
            {
                "check_version": self.check_version,
                "properties": list(self.engine.PROPERTIES),
                "checker_digest": self.checker_digest,
                "check_manifest_digest": self.check_manifest_digest,
                "event_schema_version": self.event_schema_version,
                "schema_digest": self.schema_digest,
                "policy_version": self.policy_version,
                "policy_digest": self.policy_digest,
                "configuration": self.configuration,
            }
        )

    def _schema_validation(self, trace: list[dict[str, object]]) -> InstanceValidation:
        if self.schema_path is None:
            return InstanceValidation(
                True,
                ("schema validation not performed because no concrete schema artifact was supplied",),
            )
        document = json.loads(self.schema_path.read_text(encoding="utf-8"))
        if not isinstance(document, Mapping):
            return InstanceValidation(False, ("schema artifact is not a JSON object",))
        return SchemaRegistry.validate_instances(document, trace)

    def evaluate(self, events: Iterable[Mapping[str, object]]) -> tuple[AssuranceReport, dict[str, object]]:
        trace = [dict(item) for item in events]
        report = self.engine.evaluate(trace)
        replay = deterministic_replay(trace)
        causal_validation = validate_causal_trace(trace)
        schema_validation = self._schema_validation(trace)
        system_result = report.status.value if causal_validation.valid and schema_validation.valid else "FAIL"
        run_id = f"trace-run-{uuid4()}"
        raw_result: dict[str, object] = {
            "base_monitor_result": report.status.value,
            "system_result": system_result,
            "violations": [asdict(item) for item in report.violations],
            "covered_properties": list(report.covered_properties),
            "uncovered_properties": list(report.uncovered_properties),
            "replay": asdict(replay),
            "causal_trace_validation": asdict(causal_validation),
            "schema_validation": asdict(schema_validation),
        }
        required_checks = self._required_checks()
        executed_checks = tuple(self.engine.PROPERTIES)
        attestation = build_result_attestation(
            run_id=run_id,
            machine_verdict=system_result,
            trace=trace,
            raw_result=raw_result,
            checker_digest=self.checker_digest,
            check_manifest_digest=self.check_manifest_digest,
            schema_digest=self.schema_digest,
            policy_digest=self.policy_digest,
            config=self.configuration,
            git_commit_sha=self.git_commit_sha,
            check_version=self.check_version,
            minimum_check_version=self.minimum_check_version,
            required_checks=required_checks,
            executed_checks=executed_checks,
            artifact_binding_complete=self.artifact_binding_complete,
            signing_key_path=self.signing_key_path,
            signer_id=self.signer_id,
        )
        if not replay.consistent or not causal_validation.valid or not schema_validation.valid:
            attestation = type(attestation)(
                **{**asdict(attestation), "integrity_status": IntegrityStatus.INVALID}
            )
        payload: dict[str, object] = {
            "run_id": run_id,
            "trace_fingerprint": _sha256(trace),
            "event_count": len(trace),
            "check_version": self.check_version,
            "minimum_check_version": self.minimum_check_version,
            "check_set_fingerprint": self.check_set_fingerprint,
            "checker_digest": self.checker_digest,
            "check_manifest_digest": self.check_manifest_digest,
            "event_schema_version": self.event_schema_version,
            "schema_digest": self.schema_digest,
            "policy_version": self.policy_version,
            "policy_digest": self.policy_digest,
            "configuration_digest": _sha256(self.configuration),
            "git_commit_sha": self.git_commit_sha,
            "base_monitor_result": report.status.value,
            "system_result": system_result,
            "result": system_result,
            "violations": raw_result["violations"],
            "covered_properties": raw_result["covered_properties"],
            "uncovered_properties": raw_result["uncovered_properties"],
            "deterministic_replay": raw_result["replay"],
            "causal_trace_validation": raw_result["causal_trace_validation"],
            "schema_validation": raw_result["schema_validation"],
            "attestation": asdict(attestation),
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
    second_approver = str(update.get("second_approver", "")).strip().lower()
    status = str(update.get("status", "PROPOSED")).strip().upper()
    change_type = str(update["change_type"]).upper()
    checks_removed = list(update.get("checks_removed", []))
    policy_updates = list(update.get("policy_updates", []))
    security_sensitive = bool(checks_removed) or change_type in {
        "CHECK_REMOVAL",
        "POLICY_WEAKENING",
        "SECURITY_SENSITIVE",
    } or any("weaken" in str(item).lower() for item in policy_updates)
    if status == "APPROVED":
        if not approver:
            raise ValueError("approved check update requires approver")
        if proposer == approver:
            raise ValueError("check update proposer and approver must be independent")
        if security_sensitive:
            if not second_approver:
                raise ValueError("security-sensitive approved update requires second_approver")
            if second_approver in {proposer, approver}:
                raise ValueError("security-sensitive update requires three distinct principals")
    payload: dict[str, object] = {
        "update_id": str(update.get("update_id") or f"check-update-{uuid4()}"),
        "from_version": str(update["from_version"]),
        "to_version": str(update["to_version"]),
        "change_type": change_type,
        "rationale": str(update["rationale"]),
        "source_issue": update.get("source_issue"),
        "source_evaluation_run": update.get("source_evaluation_run"),
        "checks_added": list(update.get("checks_added", [])),
        "checks_removed": checks_removed,
        "checks_modified": list(update.get("checks_modified", [])),
        "schema_updates": list(update.get("schema_updates", [])),
        "policy_updates": policy_updates,
        "proposer": str(update["proposer"]),
        "approver": str(update.get("approver", "")) or None,
        "second_approver": str(update.get("second_approver", "")) or None,
        "security_sensitive": security_sensitive,
        "regression_evidence": list(update.get("regression_evidence", [])),
        "status": status,
    }
    return store.append("check_update", payload)


def record_waiver(store: TraceAuditStore, waiver: Mapping[str, object]) -> dict[str, object]:
    """Record a disposition without mutating the original machine verdict."""

    required = ("run_id", "reviewer", "rationale", "disposition", "expires_at")
    missing = [field for field in required if not str(waiver.get(field, "")).strip()]
    if missing:
        raise ValueError(f"waiver missing required fields: {', '.join(missing)}")
    disposition = str(waiver["disposition"]).upper()
    if disposition not in {"WAIVED", "FALSE_POSITIVE", "REQUIRES_INVESTIGATION", "ACCEPTED"}:
        raise ValueError("unsupported waiver disposition")
    payload: dict[str, object] = {
        "waiver_id": str(waiver.get("waiver_id") or f"waiver-{uuid4()}"),
        "run_id": str(waiver["run_id"]),
        "reviewer": str(waiver["reviewer"]),
        "rationale": str(waiver["rationale"]),
        "disposition": disposition,
        "expires_at": str(waiver["expires_at"]),
        "evidence_viewed": list(waiver.get("evidence_viewed", [])),
    }
    return store.append("human_disposition", payload)
