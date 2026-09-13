"""Actual producer CLI -> pinned consumer gate, using disposable test identities.

Host-only operator test, not deployed agent capture or production approval.
"""
import base64
from dataclasses import asdict, fields, replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from assurance_portfolio.result_integrity import generate_ed25519_keypair

CONSUMER_PIN = 'ddfa7893b6b2edca97807ba00f24ebef3ddf644a'
PRODUCER = Path(__file__).resolve().parents[2]
CONSUMER = Path(os.environ['VI_CONSUMER_ROOT']).resolve(strict=True)
if subprocess.check_output(['git', '-C', str(CONSUMER), 'rev-parse', 'HEAD'], text=True).strip() != CONSUMER_PIN:
    raise RuntimeError('Consumer pin mismatch')
sys.path.insert(0, str(CONSUMER / 'src'))
from verification_intelligence.models import ContractError, ToolRequest
from verification_intelligence.task_safety import TaskScopeGate, plan_signing_bytes, request_digest
from verification_intelligence.trace_artifacts import TraceArtifactBytes, measure_trace_artifacts
from verification_intelligence.trace_consumption import consumption_signing_bytes


class ConsumerRoundTripTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'operator-workspace'
        self.state = Path(self.temp.name) / 'protected-state'
        self.root.mkdir()
        self.state.mkdir()
        self.private, public = self.state / 'TEST-producer.pem', self.state / 'TEST-producer-public.pem'
        generate_ed25519_keypair(self.private, public)
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
        producer_public = load_pem_public_key(public.read_bytes()).public_bytes(Encoding.Raw, PublicFormat.Raw)
        self.reviewer = Ed25519PrivateKey.generate()
        self.commit = subprocess.check_output(['git', '-C', str(PRODUCER), 'rev-parse', 'HEAD'], text=True).strip()
        inputs = {'trace.json': 'examples/agent_trace.json', 'manifest.json': 'checks/agent-trace-checks/6.1.0.json',
                  'schema.json': 'schemas/agent-trace/2.0.0.json', 'policy.json': 'policies/agent-trace-policy/2.0.0.json'}
        for name, source in inputs.items():
            (self.root / name).write_bytes((PRODUCER / source).read_bytes())
        self.command = (sys.executable, '-m', 'assurance_portfolio.trace_audit_cli',
            '--audit-log', str(self.root / 'producer-audit.jsonl'), 'evaluate', str(self.root / 'trace.json'),
            '--check-version', 'agent-trace-checks/6.1.0', '--minimum-check-version', 'agent-trace-checks/6.1.0',
            '--check-manifest-file', str(self.root / 'manifest.json'), '--schema-file', str(self.root / 'schema.json'),
            '--policy-file', str(self.root / 'policy.json'), '--signing-key', str(self.private),
            '--signer-id', 'TEST-producer', '--git-commit', self.commit, '--consumer-profile', 'verification-intelligence/1',
            '--run-id', 'operator-approved-run', '--capture-directory', str(self.root / 'capture'))
        request = ToolRequest('evaluate-trace', 'portfolio-fixture', ('BASE-CHECKS',), {})
        now = datetime.now(timezone.utc)
        plan = {'schema_version': 1, 'project_id': request.project_id, 'run_id': 'operator-approved-run',
            'workspace': str(self.root), 'expires_at': (now + timedelta(minutes=10)).isoformat(),
            'tasks': [{'task_id': 'producer', 'request_digest': request_digest(request), 'command': self.command,
                'executable_sha256': hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
                'cwd': '.', 'environment': {'PYTHONPATH': str(PRODUCER / 'src'), 'PYTHONDONTWRITEBYTECODE': '1'},
                'inputs': [{'path': name, 'sha256': hashlib.sha256((self.root / name).read_bytes()).hexdigest()} for name in inputs],
                'needs': [], 'max_attempts': 1, 'timeout_seconds': 30}]}
        self.gate = TaskScopeGate(plan, key_id='TEST-reviewer',
            signature=base64.b64encode(self.reviewer.sign(plan_signing_bytes(plan))).decode(),
            trusted_reviewers={'TEST-reviewer': self.reviewer.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)},
            workspace=self.root, run_id='operator-approved-run', state_directory=self.state,
            trusted_evidence_signers={'TEST-producer': producer_public})
        self.addCleanup(self.gate.close)
        result = self.gate.execute(request, self.root, self.command, task_id='producer')
        self.assertEqual(result.status, 'completed', result.summary)
        capture = self.root / 'capture'
        self.artifacts = TraceArtifactBytes(**{field.name: (capture / field.name).read_bytes() for field in fields(TraceArtifactBytes)})
        # Verify exported input snapshots against the operator's retained inputs,
        # not against untrusted digest claims in the attestation.
        for artifact, name in (('check_manifest_file', 'manifest.json'), ('schema_file', 'schema.json'), ('policy_file', 'policy.json')):
            self.assertEqual(getattr(self.artifacts, artifact), (self.root / name).read_bytes())
        self.assertEqual(json.loads(self.artifacts.trace_json), json.loads((self.root / 'trace.json').read_bytes()))
        self.assertEqual(self.artifacts.checker_file, (PRODUCER / 'src/assurance_portfolio/trace_assurance.py').read_bytes())
        self.document = (capture / 'attestation.json').read_bytes()
        expected = {'run_id': 'operator-approved-run', 'signer_id': 'TEST-producer', 'machine_verdict': 'PASS',
            'git_commit_sha': self.commit, 'artifacts': measure_trace_artifacts(self.artifacts).model_dump(),
            'minimum_check_version': '6.1.0', 'required_checks': json.loads((self.root / 'manifest.json').read_bytes())['required_checks'],
            'not_before': now.isoformat(), 'not_after': (now + timedelta(minutes=5)).isoformat()}
        self.approval = {'schema_version': 1, 'plan_digest': self.gate._digest, 'task_id': 'producer', 'expected': expected}

    def consume(self, **overrides):
        args = dict(task_id='producer', document=self.document, artifacts=self.artifacts, approval=self.approval,
                    reviewer_id='TEST-reviewer', signature=base64.b64encode(self.reviewer.sign(consumption_signing_bytes(self.approval))).decode())
        args.update(overrides)
        return self.gate.consume_trace_evidence(**args)

    def codes(self):
        return [json.loads(line)['code'] for file in (self.state / 'incidents').glob('*.jsonl') for line in file.read_text().splitlines()]

    def test_actual_cli_consumption_and_replay_alarm(self):
        receipt = self.consume()
        self.assertEqual(receipt.run_id, 'operator-approved-run')
        self.assertEqual(receipt.plan_digest, self.gate._digest)
        with self.assertRaises(ContractError):
            self.consume()
        self.assertIn('evidence_replay', self.codes())
        if os.environ.get('VI_CONTRACT_EVIDENCE'):
            destination = Path(os.environ['VI_CONTRACT_EVIDENCE']) / 'TEST-ONLY-round-trip'
            destination.mkdir(parents=True, exist_ok=False)
            for path in (self.root / 'capture').iterdir():
                (destination / path.name).write_bytes(path.read_bytes())
            (destination / 'receipt.json').write_text(json.dumps(asdict(receipt), indent=2))
            (destination / 'approval.json').write_text(json.dumps(self.approval, indent=2))
            (destination / 'context.json').write_text(json.dumps({
                'producer_commit': self.commit, 'consumer_commit': CONSUMER_PIN,
                'scope': 'operator-host-only public example with disposable test identities',
                'production_approved': False, 'human_approval_exercised': False,
                'observed_incidents': self.codes()}, indent=2))
            (destination / 'TEST-producer-public.pem').write_bytes((self.state / 'TEST-producer-public.pem').read_bytes())

    def test_captured_artifact_substitution_rejected(self):
        with self.assertRaises(ContractError):
            self.consume(artifacts=replace(self.artifacts, checker_file=b'substitution'))
        self.assertIn('evidence_rejected', self.codes())

    def test_unsigned_reviewer_approval_rejected(self):
        with self.assertRaises(ContractError):
            self.consume(signature='')
        self.assertIn('evidence_rejected', self.codes())

    def test_revoked_producer_rejected(self):
        self.gate.revoke_evidence_signer('TEST-producer')
        with self.assertRaises(ContractError):
            self.consume()
        self.assertIn('evidence_rejected', self.codes())

    def test_expired_approval_rejected(self):
        now = datetime.now(timezone.utc)
        self.approval['expected']['not_before'] = (now - timedelta(hours=2)).isoformat()
        self.approval['expected']['not_after'] = (now - timedelta(hours=1)).isoformat()
        with self.assertRaises(ContractError):
            self.consume()

    def test_cross_run_attestation_tamper_rejected(self):
        document = json.loads(self.document)
        document['run_id'] = 'other-run'
        with self.assertRaises(ContractError):
            self.consume(document=json.dumps(document).encode())


if __name__ == '__main__':
    unittest.main()
