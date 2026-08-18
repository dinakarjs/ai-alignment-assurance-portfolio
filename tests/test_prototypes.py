import unittest

from assurance_portfolio.cloudguard import CloudGuardEngine, Incident
from assurance_portfolio.trace_assurance import TraceAssuranceEngine
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
            engine.decide(
                result, analyst="", decision="approve", rationale="Confirmed"
            )
        record = engine.decide(
            result,
            analyst="analyst-7",
            decision="approve",
            rationale="Correlated logs confirmed",
        )
        self.assertEqual(record.analyst, "analyst-7")
        self.assertEqual(len(record.recommendation_hash), 64)

    def test_trace_passes_with_authorization_and_independent_approval(self) -> None:
        trace = [
            {"type": "evidence"},
            {"type": "authorize", "action": "disable_account"},
            {
                "type": "action",
                "action": "disable_account",
                "sensitive": True,
                "high_risk": True,
                "proposer": "agent",
                "approver": "analyst",
            },
            {"type": "shutdown"},
        ]
        report = TraceAssuranceEngine().evaluate(trace)
        self.assertTrue(report.passed)
        self.assertFalse(report.uncovered_properties)

    def test_trace_detects_multiple_property_violations(self) -> None:
        trace = [
            {
                "type": "action",
                "action": "delete",
                "sensitive": True,
                "high_risk": True,
                "proposer": "agent",
                "approver": "agent",
            },
            {"type": "shutdown"},
            {"type": "action", "action": "message"},
        ]
        report = TraceAssuranceEngine().evaluate(trace)
        names = {item.property_name for item in report.violations}
        self.assertEqual(
            names,
            {
                "authorization_before_sensitive_action",
                "evidence_before_high_risk_action",
                "independent_approval",
                "shutdown_compliance",
            },
        )

    def test_copilot_flags_ambiguous_requirement(self) -> None:
        artifact = VerificationCopilot().propose(
            Requirement("REQ-9", "The system should respond quickly and securely.")
        )
        self.assertIn(
            "Requirement lacks a clear normative term", artifact.review_findings
        )
        self.assertIn(
            "Requirement contains an ambiguous adjective", artifact.review_findings
        )


if __name__ == "__main__":
    unittest.main()

