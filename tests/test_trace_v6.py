import json
import tempfile
import unittest
from pathlib import Path

from assurance_portfolio.assurance_selftest import deterministic_replay, run_canary_suite
from assurance_portfolio.field_issue import FieldIssueAnalyzer, GapClassification, field_issue_from_dict
from assurance_portfolio.result_integrity import (
    IntegrityStatus,
    build_result_attestation,
    generate_ed25519_keypair,
    verify_result_attestation,
)
from assurance_portfolio.runtime_assurance import (
    Capability,
    Decision,
    EvidenceRecord,
    ProposedAction,
    RuntimeAssuranceGateway,
    TrustLabel,
)
from assurance_portfolio.schema_registry import Compatibility, SchemaRegistry
from assurance_portfolio.trace_audit import (
    AuditedTraceAssuranceEngine,
    TraceAuditStore,
    record_check_update,
    record_waiver,
)


class TraceV6Tests(unittest.TestCase):
    def _proposed(self, **changes):
        values = {
            "action": "transfer",
            "principal": "finance-agent",
            "parameters": {"recipient": "vendor-1", "amount": 8000},
            "transaction_id": "tx-1",
            "sensitive": True,
            "high_risk": True,
            "proposer": "finance-agent",
            "approver": "human-reviewer",
            "proposer_trust_domain": "automation",
            "approver_trust_domain": "finance-ops",
            "input_trust": (TrustLabel.UNTRUSTED_TOOL_DATA,),
        }
        values.update(changes)
        return ProposedAction(**values)

    def _capability(self):
        return Capability(
            action="transfer",
            principal="finance-agent",
            transaction_id="tx-1",
            constraints={"recipient": ["vendor-1"], "amount": {"max": 10000}},
        )

    def _evidence(self):
        return EvidenceRecord(
            evidence_id="ev-1",
            source="invoice-service",
            trust_label=TrustLabel.VERIFIED_EVIDENCE,
            verified=True,
            transaction_id="tx-1",
            action="transfer",
        )

    def test_runtime_gateway_allows_parameter_bound_high_risk_action(self):
        result = RuntimeAssuranceGateway().decide(
            self._proposed(), capabilities=[self._capability()], evidence=[self._evidence()]
        )
        self.assertEqual(result.decision, Decision.ALLOW)

    def test_runtime_gateway_blocks_parameter_substitution(self):
        proposed = self._proposed(parameters={"recipient": "vendor-1", "amount": 10001})
        result = RuntimeAssuranceGateway().decide(
            proposed, capabilities=[self._capability()], evidence=[self._evidence()]
        )
        self.assertEqual(result.decision, Decision.BLOCK)
        self.assertIn("parameter-bound", result.reasons[0])

    def test_runtime_gateway_escalates_unverified_high_risk_evidence(self):
        evidence = EvidenceRecord(
            evidence_id="ev-2",
            source="email",
            trust_label=TrustLabel.EXTERNAL_CONTENT,
            verified=False,
            transaction_id="tx-1",
            action="transfer",
        )
        result = RuntimeAssuranceGateway().decide(
            self._proposed(), capabilities=[self._capability()], evidence=[evidence]
        )
        self.assertEqual(result.decision, Decision.ESCALATE)

    def test_runtime_gateway_escalates_same_trust_domain_approval(self):
        proposed = self._proposed(approver_trust_domain="automation")
        result = RuntimeAssuranceGateway().decide(
            proposed, capabilities=[self._capability()], evidence=[self._evidence()]
        )
        self.assertEqual(result.decision, Decision.ESCALATE)

    def test_signed_attestation_detects_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            private_key = Path(tmp) / "private.pem"
            public_key = Path(tmp) / "public.pem"
            generate_ed25519_keypair(private_key, public_key)
            attestation = build_result_attestation(
                run_id="run-1",
                machine_verdict="PASS",
                trace=[{"type": "status"}],
                raw_result={"result": "PASS"},
                checker_digest="a" * 64,
                schema_digest="b" * 64,
                policy_digest="c" * 64,
                config={"mode": "test"},
                git_commit_sha="deadbeef",
                check_version="checks/6.0.0",
                minimum_check_version="checks/6.0.0",
                required_checks=["a", "b"],
                executed_checks=["a", "b"],
                signing_key_path=private_key,
                signer_id="runner-1",
            )
            verification = verify_result_attestation(attestation, public_key)
            self.assertEqual(verification.status, IntegrityStatus.VERIFIED)
            tampered = dict(attestation.__dict__)
            tampered["machine_verdict"] = "FAIL"
            verification = verify_result_attestation(tampered, public_key)
            self.assertEqual(verification.status, IntegrityStatus.INVALID)

    def test_attestation_rejects_missing_check_and_rollback(self):
        attestation = build_result_attestation(
            run_id="run-2",
            machine_verdict="PASS",
            trace=[],
            raw_result={"result": "PASS"},
            checker_digest="a" * 64,
            schema_digest="b" * 64,
            policy_digest="c" * 64,
            config={},
            git_commit_sha=None,
            check_version="checks/5.0.0",
            minimum_check_version="checks/6.0.0",
            required_checks=["a", "b"],
            executed_checks=["a"],
        )
        self.assertEqual(attestation.integrity_status, IntegrityStatus.INVALID)
        self.assertFalse(attestation.required_checks_present)
        self.assertFalse(attestation.anti_rollback_passed)

    def test_audited_evaluation_is_signed_and_bound_to_artifacts(self):
        trace = [
            {"type": "evidence", "action": "disable", "transaction_id": "tx"},
            {"type": "authorize", "action": "disable", "transaction_id": "tx"},
            {
                "type": "action",
                "action": "disable",
                "transaction_id": "tx",
                "sensitive": True,
                "high_risk": True,
                "proposer": "agent",
                "approver": "human",
            },
            {"type": "shutdown"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            private_key, public_key = root / "private.pem", root / "public.pem"
            generate_ed25519_keypair(private_key, public_key)
            schema = root / "schema.json"
            policy = root / "policy.json"
            schema.write_text('{"schema":"v2"}', encoding="utf-8")
            policy.write_text('{"policy":"v2"}', encoding="utf-8")
            store = TraceAuditStore(root / "audit.jsonl")
            _, record = AuditedTraceAssuranceEngine(
                store,
                check_version="checks/6.0.0",
                minimum_check_version="checks/6.0.0",
                event_schema_version="schema/2.0.0",
                policy_version="policy/2.0.0",
                schema_path=schema,
                policy_path=policy,
                signing_key_path=private_key,
                signer_id="trusted-runner",
                git_commit_sha="abc123",
            ).evaluate(trace)
            attestation = record["payload"]["attestation"]
            self.assertEqual(attestation["integrity_status"], "VERIFIED")
            self.assertEqual(
                verify_result_attestation(attestation, public_key).status,
                IntegrityStatus.VERIFIED,
            )

    def test_waiver_does_not_mutate_machine_result_and_anchor_verifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = TraceAuditStore(Path(tmp) / "audit.jsonl")
            evaluation = store.append("evaluation", {"run_id": "r1", "result": "FAIL"})
            waiver = record_waiver(
                store,
                {
                    "run_id": "r1",
                    "reviewer": "reviewer",
                    "rationale": "known issue",
                    "disposition": "WAIVED",
                    "expires_at": "2026-08-25T00:00:00Z",
                },
            )
            anchor = store.create_anchor(external_reference="external-checkpoint-1")
            records = store.records()
            self.assertEqual(records[0]["payload"]["result"], "FAIL")
            self.assertEqual(waiver["record_type"], "human_disposition")
            self.assertEqual(anchor["record_type"], "merkle_anchor")
            self.assertTrue(store.verify().valid)
            self.assertEqual(evaluation["sequence"], 1)

    def test_security_sensitive_update_requires_second_approver(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = TraceAuditStore(Path(tmp) / "audit.jsonl")
            update = {
                "from_version": "checks/6.0.0",
                "to_version": "checks/6.1.0",
                "change_type": "CHECK_REMOVAL",
                "rationale": "test only",
                "checks_removed": ["shutdown_compliance"],
                "proposer": "a",
                "approver": "b",
                "status": "APPROVED",
            }
            with self.assertRaises(ValueError):
                record_check_update(store, update)
            update["second_approver"] = "c"
            record = record_check_update(store, update)
            self.assertTrue(record["payload"]["security_sensitive"])

    def test_schema_registry_classifies_breaking_and_compatible_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = SchemaRegistry(tmp)
            base = {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$id": "schema/1",
                "type": "object",
                "properties": {"type": {"type": "string"}},
                "required": ["type"],
            }
            registry.propose(kind="trace", version="1.0.0", document=base, proposer="a")
            registry.approve_and_activate("trace", "1.0.0", "b")
            additive = dict(base)
            additive["$id"] = "schema/1.1"
            additive["properties"] = {**base["properties"], "event_id": {"type": "string"}}
            descriptor = registry.propose(
                kind="trace",
                version="1.1.0",
                document=additive,
                proposer="a",
                previous_version="1.0.0",
            )
            self.assertEqual(descriptor.compatibility, Compatibility.BACKWARD_COMPATIBLE)
            breaking = dict(additive)
            breaking["$id"] = "schema/2"
            breaking["properties"] = {"event_id": {"type": "string"}}
            descriptor = registry.propose(
                kind="trace",
                version="2.0.0",
                document=breaking,
                proposer="a",
                previous_version="1.1.0",
            )
            self.assertEqual(descriptor.compatibility, Compatibility.SECURITY_SENSITIVE)

    def test_field_issue_becomes_enforcement_gap_when_check_detected_it(self):
        issue = field_issue_from_dict(
            {
                "issue_id": "FI-1",
                "severity": "HIGH",
                "summary": "unauthorized delete executed",
                "expected_behavior": "block",
                "actual_behavior": "executed",
                "confirmed_unsafe": True,
                "trace": [
                    {
                        "type": "action",
                        "action": "delete",
                        "transaction_id": "x",
                        "sensitive": True,
                    }
                ],
            }
        )
        analysis = FieldIssueAnalyzer().analyze(issue)
        self.assertEqual(analysis.classification, GapClassification.ENFORCEMENT_GAP)
        self.assertTrue(analysis.detected_by_existing_checks)

    def test_canary_suite_and_replay_pass(self):
        self.assertTrue(run_canary_suite().passed)
        replay = deterministic_replay([{"type": "status"}])
        self.assertTrue(replay.consistent)
        self.assertEqual(replay.first_digest, replay.second_digest)


if __name__ == "__main__":
    unittest.main()
