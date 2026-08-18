import unittest

from assurance_portfolio.cloudguard import CloudGuardEngine, Incident
from assurance_portfolio.trace_assurance import AssuranceStatus, TraceAssuranceEngine
from assurance_portfolio.verification_copilot import Requirement, VerificationCopilot


class PrototypeTests(unittest.TestCase):
    def test_cloudguard_recreates_workshop_score(self) -> None:
        incident = Incident(
            "CG-1",
            "user-1",
            {
                "impossible_travel": 1,
                "privilege_escalation": 1,
                "failed_logins": 1,
                "malicious_ip": 0.58,
                "time_anomaly": 1,
            },
        )
        result = CloudGuardEngine().assess(incident)
        self.assertEqual(result.risk_score, 95)
        self.assertEqual(result.recommended_action, "disable_account")
        self.assertTrue(result.human_approval_required)

    def test_cloudguard_rejects_out_of_range_signal(self) -> None:
        with self.assertRaises(ValueError):
            CloudGuardEngine().assess(
                Incident("CG-2", "user-2", {"malicious_ip": 1.2})
            )

    def test_cloudguard_requires_named_analyst_and_rationale(self) -> None:
        engine = CloudGuardEngine()
        result = engine.assess(
            Incident(
                "CG-3",
                "user-3",
                {
                    "impossible_travel": 1,
                    "privilege_escalation": 1,
                    "failed_logins": 1,
                },
            )
        )
        with self.assertRaises(PermissionError):
            engine.decide(result, analyst="", decision="approve", rationale="Confirmed")
        record = engine.decide(
            result,
            analyst="analyst-7",
            decision="approve",
            rationale="Correlated logs confirmed",
        )
        self.assertEqual(record.analyst, "analyst-7")
        self.assertEqual(len(record.recommendation_hash), 64)

    def _complete_trace(self) -> list[dict[str, object]]:
        return [
            {
                "type": "evidence",
                "action": "disable_account",
                "transaction_id": "tx-1",
            },
            {
                "type": "authorize",
                "action": "disable_account",
                "transaction_id": "tx-1",
            },
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

    def test_trace_passes_with_scoped_authorization_evidence_and_approval(self) -> None:
        report = TraceAssuranceEngine().evaluate(self._complete_trace())
        self.assertEqual(report.status, AssuranceStatus.PASS)
        self.assertTrue(report.passed)
        self.assertFalse(report.uncovered_properties)

    def test_trace_is_inconclusive_when_properties_are_uncovered(self) -> None:
        report = TraceAssuranceEngine().evaluate([{"type": "status"}])
        self.assertEqual(report.status, AssuranceStatus.INCONCLUSIVE)
        self.assertFalse(report.passed)
        self.assertTrue(report.uncovered_properties)

    def test_authorization_is_consumed_after_one_use(self) -> None:
        trace = self._complete_trace()[:-1]
        trace.append(
            {
                "type": "action",
                "action": "disable_account",
                "transaction_id": "tx-1",
                "sensitive": True,
                "high_risk": False,
            }
        )
        report = TraceAssuranceEngine().evaluate(trace)
        self.assertIn(
            "authorization_before_sensitive_action",
            {item.property_name for item in report.violations},
        )

    def test_transaction_mismatch_does_not_reuse_authorization_or_evidence(self) -> None:
        trace = self._complete_trace()
        trace[2]["transaction_id"] = "tx-2"
        report = TraceAssuranceEngine().evaluate(trace)
        names = {item.property_name for item in report.violations}
        self.assertIn("authorization_before_sensitive_action", names)
        self.assertIn("evidence_before_high_risk_action", names)

    def test_authorization_can_expire(self) -> None:
        trace = [
            {
                "type": "authorize",
                "action": "delete",
                "transaction_id": "tx-1",
                "expires_after_events": 1,
            },
            {"type": "status"},
            {
                "type": "action",
                "action": "delete",
                "transaction_id": "tx-1",
                "sensitive": True,
            },
        ]
        report = TraceAssuranceEngine().evaluate(trace)
        self.assertIn(
            "authorization_before_sensitive_action",
            {item.property_name for item in report.violations},
        )

    def test_high_risk_action_without_approver_is_violation(self) -> None:
        trace = self._complete_trace()
        del trace[2]["approver"]
        report = TraceAssuranceEngine().evaluate(trace)
        self.assertIn(
            "independent_approval",
            {item.property_name for item in report.violations},
        )

    def test_action_names_are_normalized(self) -> None:
        trace = self._complete_trace()
        trace[0]["action"] = " Disable Account "
        trace[1]["action"] = "DISABLE   ACCOUNT"
        report = TraceAssuranceEngine().evaluate(trace)
        self.assertEqual(report.status, AssuranceStatus.PASS)

    def test_shutdown_allows_audit_and_status_but_blocks_actions(self) -> None:
        trace = self._complete_trace()
        trace.extend(
            [
                {"type": "audit"},
                {"type": "status"},
                {"type": "action", "action": "message"},
            ]
        )
        report = TraceAssuranceEngine().evaluate(trace)
        shutdown_violations = [
            item for item in report.violations if item.property_name == "shutdown_compliance"
        ]
        self.assertEqual(len(shutdown_violations), 1)

    def test_copilot_flags_ambiguous_requirement(self) -> None:
        artifact = VerificationCopilot().propose(
            Requirement("REQ-9", "The system should respond quickly and securely.")
        )
        self.assertIn("Requirement lacks a clear normative term", artifact.review_findings)
        self.assertIn("Requirement contains an ambiguous adjective", artifact.review_findings)

    def test_copilot_generates_temporal_draft_for_bounded_requirement(self) -> None:
        artifact = VerificationCopilot().propose(
            Requirement("REQ-10", "grant shall assert within 4 cycles after request")
        )
        self.assertEqual(
            artifact.assertion,
            "assert property (@(posedge clk) request |-> ##[1:4] grant);",
        )
        self.assertIn("4-cycle boundary", artifact.scenarios[1])
        self.assertFalse(artifact.review_findings)


if __name__ == "__main__":
    unittest.main()
