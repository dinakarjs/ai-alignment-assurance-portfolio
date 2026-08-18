import json
import tempfile
import unittest
from pathlib import Path

from assurance_portfolio.trace_assurance import AssuranceStatus
from assurance_portfolio.trace_audit import (
    AuditedTraceAssuranceEngine,
    TraceAuditStore,
    record_check_update,
)


class TraceAuditTests(unittest.TestCase):
    def _trace(self):
        return [
            {"type": "evidence", "action": "disable_account", "transaction_id": "tx-1"},
            {"type": "authorize", "action": "disable_account", "transaction_id": "tx-1"},
            {
                "type": "action",
                "action": "disable_account",
                "transaction_id": "tx-1",
                "sensitive": True,
                "high_risk": True,
                "proposer": "agent",
                "approver": "analyst",
            },
            {"type": "shutdown"},
        ]

    def test_evaluation_is_appended_with_versions_and_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = TraceAuditStore(Path(tmp) / "audit.jsonl")
            engine = AuditedTraceAssuranceEngine(
                store,
                check_version="checks/5.0.0",
                event_schema_version="schema/2.0.0",
                policy_version="policy/3.0.0",
            )
            report, record = engine.evaluate(self._trace())
            self.assertEqual(report.status, AssuranceStatus.PASS)
            payload = record["payload"]
            self.assertEqual(payload["result"], "PASS")
            self.assertEqual(payload["check_version"], "checks/5.0.0")
            self.assertEqual(payload["event_schema_version"], "schema/2.0.0")
            self.assertEqual(payload["policy_version"], "policy/3.0.0")
            self.assertEqual(len(payload["trace_fingerprint"]), 64)
            self.assertTrue(store.verify().valid)

    def test_check_update_and_evaluation_share_one_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = TraceAuditStore(Path(tmp) / "audit.jsonl")
            update = record_check_update(
                store,
                {
                    "from_version": "checks/4.0.0",
                    "to_version": "checks/5.0.0",
                    "change_type": "POLICY_STRENGTHENING",
                    "rationale": "Bind authorization to action parameters",
                    "source_issue": "FI-2026-014",
                    "checks_modified": ["authorization_before_sensitive_action"],
                    "proposer": "engineer-a",
                    "approver": "reviewer-b",
                    "status": "APPROVED",
                },
            )
            _, evaluation = AuditedTraceAssuranceEngine(store).evaluate(self._trace())
            self.assertEqual(update["sequence"], 1)
            self.assertEqual(evaluation["sequence"], 2)
            self.assertEqual(evaluation["previous_hash"], update["record_hash"])
            self.assertTrue(store.verify().valid)

    def test_approved_update_requires_independent_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = TraceAuditStore(Path(tmp) / "audit.jsonl")
            with self.assertRaises(ValueError):
                record_check_update(
                    store,
                    {
                        "from_version": "checks/4.0.0",
                        "to_version": "checks/5.0.0",
                        "change_type": "CHECK_CHANGE",
                        "rationale": "test",
                        "proposer": "same-user",
                        "approver": "SAME-USER",
                        "status": "APPROVED",
                    },
                )

    def test_tampering_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            store = TraceAuditStore(path)
            AuditedTraceAssuranceEngine(store).evaluate(self._trace())
            record = json.loads(path.read_text(encoding="utf-8"))
            record["payload"]["result"] = "FAIL"
            path.write_text(json.dumps(record) + "\n", encoding="utf-8")
            verification = store.verify()
            self.assertFalse(verification.valid)
            self.assertEqual(verification.first_invalid_index, 0)
            self.assertEqual(verification.detail, "record hash mismatch")


if __name__ == "__main__":
    unittest.main()
