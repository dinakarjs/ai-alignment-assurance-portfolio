import copy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from assurance_portfolio.consumer_profile import PROFILE, numeric_check_version
from assurance_portfolio.result_integrity import generate_ed25519_keypair, verify_result_attestation
from assurance_portfolio.trace_audit import AuditedTraceAssuranceEngine, TraceAuditStore

ROOT = Path(__file__).resolve().parents[1]


class ConsumerProfileTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.private, self.public = self.root / 'TEST-private.pem', self.root / 'TEST-public.pem'
        generate_ed25519_keypair(self.private, self.public)
        self.trace = json.loads((ROOT / 'examples/agent_trace.json').read_bytes())
        self.manifest = self.root / 'manifest.json'
        self.schema = self.root / 'schema.json'
        self.policy = self.root / 'policy.json'
        self.manifest.write_bytes((ROOT / 'checks/agent-trace-checks/6.1.0.json').read_bytes())
        self.schema.write_bytes((ROOT / 'schemas/agent-trace/2.0.0.json').read_bytes())
        self.policy.write_bytes((ROOT / 'policies/agent-trace-policy/2.0.0.json').read_bytes())
        self.store = TraceAuditStore(self.root / 'audit.jsonl')

    def engine(self, **overrides):
        values = dict(consumer_profile=PROFILE, check_version='agent-trace-checks/6.1.0',
                      minimum_check_version='agent-trace-checks/6.1.0', check_manifest_path=self.manifest,
                      schema_path=self.schema, policy_path=self.policy, signing_key_path=self.private,
                      signer_id='test-producer', git_commit_sha='a' * 40)
        values.update(overrides)
        return AuditedTraceAssuranceEngine(self.store, **values)

    def test_run_identity_and_numeric_versions_are_signed(self):
        _, record = self.engine().evaluate(self.trace, run_id='operator-run-1')
        attestation = record['payload']['attestation']
        self.assertEqual(attestation['run_id'], 'operator-run-1')
        self.assertEqual(attestation['check_version'], '6.1.0')
        self.assertEqual(attestation['minimum_check_version'], '6.1.0')
        self.assertEqual(record['payload']['check_version'], 'agent-trace-checks/6.1.0')
        self.assertTrue(verify_result_attestation(attestation, self.public).valid_signature)
        changed = dict(attestation, run_id='substituted-run')
        self.assertFalse(verify_result_attestation(changed, self.public).valid_signature)

    def test_exact_snapshots_match_all_attested_digests(self):
        capture = self.root / 'capture'
        _, record = self.engine(configuration={'test': 'snapshot'}).evaluate(
            self.trace, run_id='operator-run-2', capture_directory=capture)
        attestation = record['payload']['attestation']
        for path in capture.iterdir():
            if path.name.endswith(('_json', '_file')):
                field = path.name.rsplit('_', 1)[0] + '_digest'
                data = path.read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), attestation[field])
        marker = json.loads((capture / 'capture.json').read_bytes())
        self.assertTrue(marker['complete'])
        self.assertFalse(marker['production_approved'])
        self.assertEqual(len(marker['files_sha256']), 8)
        self.assertFalse(any(b'PRIVATE KEY' in path.read_bytes() for path in capture.iterdir()))

    def test_run_id_is_required_and_never_silently_normalized(self):
        for run_id in (None, '', ' leading', 'trailing ', '../path', 'line\nbreak', 12, 'x' * 257):
            with self.subTest(run_id=run_id), self.assertRaises(ValueError):
                self.engine().evaluate(self.trace, run_id=run_id)
        self.assertFalse(self.store.path.exists())

    def test_duplicate_run_in_same_store_rejected(self):
        engine = self.engine()
        engine.evaluate(self.trace, run_id='one-run')
        with self.assertRaisesRegex(ValueError, 'already evaluated'):
            engine.evaluate(self.trace, run_id='one-run')
        self.assertEqual(len(self.store.records()), 1)

    def test_version_profile_rejects_ambiguous_identifiers(self):
        for value in ('checks/6.1.0', 'other/6.1.0', 'v6.1.0', '6.1.0-beta', '06.1.0',
                      '6.1', '6.1.0 ', 'a/agent-trace-checks/6.1.0', 610):
            with self.subTest(value=value), self.assertRaises(ValueError):
                numeric_check_version(value)
        self.assertEqual(numeric_check_version('6.1.0'), '6.1.0')

    def test_version_rollback_rejected_before_signing(self):
        with self.assertRaisesRegex(ValueError, 'minimum'):
            self.engine(minimum_check_version='agent-trace-checks/7.0.0').evaluate(self.trace, run_id='run')
        self.assertFalse(self.store.path.exists())

    def test_missing_artifacts_commit_and_signer_fail_closed(self):
        for values in ({'schema_path': None}, {'policy_path': None}, {'check_manifest_path': None},
                       {'git_commit_sha': 'short'}, {'signing_key_path': None}, {'signer_id': None}):
            with self.subTest(values=list(values)), self.assertRaises(ValueError):
                self.engine(**values).evaluate(self.trace, run_id='run')

    def test_manifest_mismatch_missing_duplicate_and_unknown_checks_rejected(self):
        original = json.loads(self.manifest.read_bytes())
        for changes in ({'check_version': 'agent-trace-checks/6.0.0'}, {'required_checks': []},
                        {'required_checks': ['shutdown_compliance', 'shutdown_compliance']},
                        {'required_checks': ['imaginary_control']}):
            self.manifest.write_text(json.dumps(original | changes))
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.engine().evaluate(self.trace, run_id='run')

    def test_snapshot_survives_source_change_without_rehashing_new_content(self):
        engine = self.engine()
        before = self.schema.read_bytes()
        evaluate = engine.engine.evaluate
        def alter(trace):
            self.schema.write_bytes(b'{"type":"string"}')
            return evaluate(trace)
        with patch.object(engine.engine, 'evaluate', side_effect=alter):
            _, record = engine.evaluate(self.trace, run_id='run', capture_directory=self.root / 'capture')
        self.assertEqual(record['payload']['system_result'], 'PASS')
        self.assertEqual((self.root / 'capture/schema_file').read_bytes(), before)
        self.assertEqual(record['payload']['attestation']['schema_digest'], hashlib.sha256(before).hexdigest())

    def test_capture_refuses_existing_directory(self):
        capture = self.root / 'capture'
        capture.mkdir()
        (capture / 'retained').write_text('keep')
        with self.assertRaises(FileExistsError):
            self.engine().evaluate(self.trace, run_id='run', capture_directory=capture)
        self.assertEqual((capture / 'retained').read_text(), 'keep')
        self.assertFalse(self.store.path.exists())

    def test_capture_failure_does_not_write_completion_marker(self):
        capture = self.root / 'partial'
        with patch('assurance_portfolio.consumer_profile.os.fsync', side_effect=OSError('disk-full')):
            with self.assertRaises(OSError):
                self.engine().evaluate(self.trace, run_id='run', capture_directory=capture)
        self.assertFalse((capture / 'capture.json').exists())

    def test_reserved_configuration_cannot_override_profile(self):
        with self.assertRaises(ValueError):
            self.engine(configuration={'consumer_profile': 'weaker'}).evaluate(self.trace, run_id='run')

    def test_completion_marker_not_published_if_its_flush_fails(self):
        import os
        real_fsync = os.fsync
        calls = 0
        def fail_last(fd):
            nonlocal calls
            calls += 1
            if calls == 10:  # Eight snapshots, attestation, then pending marker.
                raise OSError('marker flush failed')
            real_fsync(fd)
        capture = self.root / 'partial-marker'
        with patch('assurance_portfolio.consumer_profile.os.fsync', side_effect=fail_last):
            with self.assertRaises(OSError):
                self.engine().evaluate(self.trace, run_id='run', capture_directory=capture)
        self.assertFalse((capture / 'capture.json').exists())

    def test_nested_configuration_beyond_consumer_limit_rejected(self):
        nested = {}
        for _ in range(65):
            nested = {'child': nested}
        with self.assertRaisesRegex(ValueError, 'depth'):
            self.engine(configuration=nested).evaluate(self.trace, run_id='run')

    def test_legacy_profile_preserves_version_labels_and_generated_id(self):
        _, record = self.engine(consumer_profile=None).evaluate(self.trace)
        attestation = record['payload']['attestation']
        self.assertTrue(attestation['run_id'].startswith('trace-run-'))
        self.assertEqual(attestation['check_version'], 'agent-trace-checks/6.1.0')

    def test_unknown_profile_and_legacy_capture_rejected(self):
        with self.assertRaises(ValueError):
            self.engine(consumer_profile='unknown')
        with self.assertRaises(ValueError):
            self.engine(consumer_profile=None).evaluate(self.trace, capture_directory=self.root / 'capture')


if __name__ == '__main__':
    unittest.main()
