"""Explicit, pre-signing verification-intelligence/1 producer contract."""
import hashlib
import json
import os
from pathlib import Path
import re

PROFILE = 'verification-intelligence/1'
VERSION = r'(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})'


def numeric_check_version(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r'(?:agent-trace-checks/)?' + VERSION, value):
        raise ValueError('Unsupported checker version for consumer profile')
    return value.removeprefix('agent-trace-checks/')


def validate_run_id(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,255}', value):
        raise ValueError('An explicit portable operator run ID is required')
    return value


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode('utf-8')


def _pairs(items):
    value = {}
    for key, item in items:
        if key in value:
            raise ValueError('Duplicate JSON key in captured artifact')
        value[key] = item
    return value


def strict_json(document: bytes):
    value = json.loads(document.decode('utf-8'), object_pairs_hook=_pairs)
    canonical_bytes(value)  # Reject nonfinite values, including exponent overflow.
    return value


def file_snapshot(path: Path | None) -> bytes:
    if path is None or not path.is_file():
        raise ValueError('Concrete regular-file artifacts are required')
    with path.open('rb') as stream:
        data = stream.read(8 * 1024 * 1024 + 1)
    if not data or len(data) > 8 * 1024 * 1024:
        raise ValueError('Artifact exceeds consumer size bounds')
    return data


def validate_snapshots(snapshots: dict[str, bytes]) -> None:
    if any(not value or len(value) > 8 * 1024 * 1024 for value in snapshots.values()):
        raise ValueError('Artifact exceeds consumer size bounds')
    if sum(map(len, snapshots.values())) > 32 * 1024 * 1024:
        raise ValueError('Capture exceeds consumer bundle size bound')
    for name, data in snapshots.items():
        if name.endswith('_json'):
            value = strict_json(data)
            stack = [(iter((value,)), 1)]
            while stack:
                nodes, depth = stack[-1]
                try:
                    item = next(nodes)
                except StopIteration:
                    stack.pop()
                    continue
                if depth > 64:
                    raise ValueError('Consumer JSON depth limit exceeded')
                if isinstance(item, (dict, list)):
                    stack.append((iter(item.values() if isinstance(item, dict) else item), depth + 1))


def export_capture(directory: Path, snapshots: dict[str, bytes], attestation: dict) -> None:
    """Exclusive files in a newly reserved operator directory; completion last.

    Failure leaves diagnostic partial output, never a completed capture marker.
    No signing key or private credential is included.
    """
    def write(name, data):
        with (directory / name).open('xb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    for name, data in snapshots.items():
        write(name, data)
    write('attestation.json', canonical_bytes(attestation))
    write('.capture.pending.json', canonical_bytes({
        'schema_version': 'agent-trace-capture/1', 'consumer_profile': PROFILE,
        'run_id': attestation['run_id'], 'payload_digest': attestation['payload_digest'],
        'files_sha256': {name: hashlib.sha256(data).hexdigest() for name, data in snapshots.items()},
        'complete': True, 'production_approved': False,
    }))
    (directory / '.capture.pending.json').rename(directory / 'capture.json')
