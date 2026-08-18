"""Result-integrity primitives for Agent Trace Assurance.

The module binds an evaluation result to its inputs, checker implementation,
policy/schema artifacts, configuration, runtime environment, and expected check
manifest. Optional Ed25519 signatures turn structurally valid provenance into a
cryptographically verifiable attestation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
import base64
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
from typing import Iterable, Mapping, Sequence

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

ATTESTATION_VERSION = "agent-trace-attestation/1.0.0"


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_object(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: str | Path) -> str:
    file_path = Path(path)
    return sha256_bytes(file_path.read_bytes())


def digest_or_identifier(path: str | Path | None, identifier: str) -> str:
    if path is not None and Path(path).exists():
        return sha256_file(path)
    return sha256_object({"declared_identifier": identifier})


def environment_fingerprint(extra: Mapping[str, object] | None = None) -> str:
    payload: dict[str, object] = {
        "python": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
    }
    if extra:
        payload["extra"] = dict(extra)
    return sha256_object(payload)


def _version_tuple(value: str) -> tuple[int, ...]:
    tail = value.rsplit("/", 1)[-1]
    parts = tail.split(".")
    numbers: list[int] = []
    for part in parts:
        digits = "".join(ch for ch in part if ch.isdigit())
        if not digits:
            break
        numbers.append(int(digits))
    if not numbers:
        raise ValueError(f"version {value!r} does not end in a numeric version")
    return tuple(numbers)


def version_at_least(actual: str, minimum: str) -> bool:
    actual_parts = _version_tuple(actual)
    minimum_parts = _version_tuple(minimum)
    width = max(len(actual_parts), len(minimum_parts))
    actual_parts += (0,) * (width - len(actual_parts))
    minimum_parts += (0,) * (width - len(minimum_parts))
    return actual_parts >= minimum_parts


class IntegrityStatus(str, Enum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    INVALID = "INVALID"


@dataclass(frozen=True)
class AttestationVerification:
    status: IntegrityStatus
    valid_signature: bool
    required_checks_present: bool
    anti_rollback_passed: bool
    payload_digest_matches: bool
    detail: str


@dataclass(frozen=True)
class ResultAttestation:
    attestation_version: str
    run_id: str
    created_at_utc: str
    machine_verdict: str
    trace_digest: str
    raw_result_digest: str
    checker_digest: str
    check_manifest_digest: str
    schema_digest: str
    policy_digest: str
    config_digest: str
    environment_digest: str
    git_commit_sha: str | None
    check_version: str
    minimum_check_version: str
    required_checks: tuple[str, ...]
    executed_checks: tuple[str, ...]
    anti_rollback_passed: bool
    required_checks_present: bool
    signer_id: str | None
    payload_digest: str
    signature_b64: str | None
    integrity_status: IntegrityStatus

    def signing_payload(self) -> dict[str, object]:
        payload = asdict(self)
        payload.pop("signature_b64")
        payload.pop("integrity_status")
        payload.pop("payload_digest")
        return payload


def generate_ed25519_keypair(private_key_path: str | Path, public_key_path: str | Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    private_path = Path(private_key_path)
    public_path = Path(public_key_path)
    private_path.parent.mkdir(parents=True, exist_ok=True)
    public_path.parent.mkdir(parents=True, exist_ok=True)
    private_path.write_bytes(private_bytes)
    public_path.write_bytes(public_bytes)
    try:
        os.chmod(private_path, 0o600)
    except OSError:
        pass


def _load_private_key(path: str | Path) -> Ed25519PrivateKey:
    key = serialization.load_pem_private_key(Path(path).read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise TypeError("private key is not Ed25519")
    return key


def _load_public_key(path: str | Path) -> Ed25519PublicKey:
    key = serialization.load_pem_public_key(Path(path).read_bytes())
    if not isinstance(key, Ed25519PublicKey):
        raise TypeError("public key is not Ed25519")
    return key


def _signature_payload(payload: Mapping[str, object]) -> bytes:
    return canonical_json(dict(payload)).encode("utf-8")


def build_result_attestation(
    *,
    run_id: str,
    machine_verdict: str,
    trace: object,
    raw_result: object,
    checker_digest: str,
    schema_digest: str,
    policy_digest: str,
    config: Mapping[str, object],
    git_commit_sha: str | None,
    check_version: str,
    minimum_check_version: str,
    required_checks: Iterable[str],
    executed_checks: Iterable[str],
    signing_key_path: str | Path | None = None,
    signer_id: str | None = None,
    environment_extra: Mapping[str, object] | None = None,
) -> ResultAttestation:
    required = tuple(sorted(set(required_checks)))
    executed = tuple(sorted(set(executed_checks)))
    required_present = set(required).issubset(executed)
    anti_rollback = version_at_least(check_version, minimum_check_version)
    base: dict[str, object] = {
        "attestation_version": ATTESTATION_VERSION,
        "run_id": run_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "machine_verdict": machine_verdict,
        "trace_digest": sha256_object(trace),
        "raw_result_digest": sha256_object(raw_result),
        "checker_digest": checker_digest,
        "check_manifest_digest": sha256_object({"required": required, "executed": executed}),
        "schema_digest": schema_digest,
        "policy_digest": policy_digest,
        "config_digest": sha256_object(dict(config)),
        "environment_digest": environment_fingerprint(environment_extra),
        "git_commit_sha": git_commit_sha,
        "check_version": check_version,
        "minimum_check_version": minimum_check_version,
        "required_checks": required,
        "executed_checks": executed,
        "anti_rollback_passed": anti_rollback,
        "required_checks_present": required_present,
        "signer_id": signer_id if signing_key_path else None,
    }
    payload_digest = sha256_object(base)
    signature_b64: str | None = None
    if signing_key_path is not None and required_present and anti_rollback:
        signature = _load_private_key(signing_key_path).sign(_signature_payload(base))
        signature_b64 = base64.b64encode(signature).decode("ascii")
        status = IntegrityStatus.VERIFIED
    elif not required_present or not anti_rollback:
        status = IntegrityStatus.INVALID
    else:
        status = IntegrityStatus.UNVERIFIED
    return ResultAttestation(
        **base,  # type: ignore[arg-type]
        payload_digest=payload_digest,
        signature_b64=signature_b64,
        integrity_status=status,
    )


def verify_result_attestation(
    attestation: Mapping[str, object] | ResultAttestation,
    public_key_path: str | Path | None,
) -> AttestationVerification:
    value = asdict(attestation) if isinstance(attestation, ResultAttestation) else dict(attestation)
    signature_b64 = value.pop("signature_b64", None)
    claimed_status = value.pop("integrity_status", None)
    claimed_digest = str(value.pop("payload_digest", ""))
    payload_digest_matches = sha256_object(value) == claimed_digest
    required = set(value.get("required_checks", []))
    executed = set(value.get("executed_checks", []))
    required_present = required.issubset(executed)
    anti_rollback = bool(value.get("anti_rollback_passed")) and version_at_least(
        str(value.get("check_version", "")), str(value.get("minimum_check_version", ""))
    )

    if not required_present or not anti_rollback or not payload_digest_matches:
        return AttestationVerification(
            IntegrityStatus.INVALID,
            False,
            required_present,
            anti_rollback,
            payload_digest_matches,
            "manifest, rollback, or payload-digest validation failed",
        )

    if public_key_path is None or not signature_b64:
        status = IntegrityStatus.UNVERIFIED
        return AttestationVerification(
            status,
            False,
            required_present,
            anti_rollback,
            payload_digest_matches,
            "attestation is structurally valid but has no verifiable signature",
        )

    try:
        signature = base64.b64decode(str(signature_b64), validate=True)
        _load_public_key(public_key_path).verify(signature, _signature_payload(value))
    except (InvalidSignature, ValueError, TypeError):
        return AttestationVerification(
            IntegrityStatus.INVALID,
            False,
            required_present,
            anti_rollback,
            payload_digest_matches,
            "Ed25519 signature verification failed",
        )

    return AttestationVerification(
        IntegrityStatus.VERIFIED,
        True,
        required_present,
        anti_rollback,
        payload_digest_matches,
        f"signature verified (claimed status was {claimed_status})",
    )


def merkle_root_hex(hashes: Sequence[str]) -> str:
    """Return a deterministic binary Merkle root over hexadecimal SHA-256 leaves."""

    if not hashes:
        return sha256_bytes(b"")
    level = [bytes.fromhex(item) for item in hashes]
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [hashlib.sha256(level[index] + level[index + 1]).digest() for index in range(0, len(level), 2)]
    return level[0].hex()
