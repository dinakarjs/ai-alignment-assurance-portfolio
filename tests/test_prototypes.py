import unittest

from assurance_portfolio.cli import _cloudguard_payload
from assurance_portfolio.cloudguard import CloudGuardEngine, Incident
from assurance_portfolio.trace_assurance import AssuranceStatus, TraceAssuranceEngine
from assurance_portfolio.verification_copilot import (
    GenerationStatus,
    Requirement,
    VerificationCopilot,
)


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
        self.assertEqual(result.confidence, result.evidence_strength)
        self.assertLessEqual(len(result.top_reasons), 3)
        self.assertTrue(all(value > 0 for _, value in result.top_reasons))

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
            analyst=" analyst-7 ",
            decision="approve",
            rationale=" Correlated logs confirmed ",
        )
        self.assertEqual(record.analyst, "analyst-7")
        self.assertEqual(record.rationale, "Correlated logs confirmed")
        self.assertEqual(len(record.recommendation_hash), 64)

    def test_cloudguard_cli_payload_includes_human_decision_audit(self) -> None:
        payload = _cloudguard_payload(
            {
                "incident_id": "CG-4",
                "account_id": "user-4",
                "signals": {
                    "impossible_travel": 1,
                    "privilege_escalation": 1,
                    "failed_logins": 1,
                },
                "decision": {
                    "analyst": "analyst-4",
                    "decision": "approve",
                    "rationale": "Evidence confirmed",
                },
            }
        )
        self.assertIn("recommendation", payload)
        self.assertIn("audit_record", payload)
        self.assertEqual(payload["audit_record"]["analyst"], "analyst-4")  # type: ignore[index]

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

    def test_unscoped_grants_do_not_approve_scoped_transaction(self) -> None:
        trace = self._complete_trace()
        del trace[0]["transaction_id"]
        del trace[1]["transaction_id"]
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

    def test_principal_names_are_normalized_before_independence_check(self) -> None:
        trace = self._complete_trace()
        trace[2]["proposer"] = " Agent "
        trace[2]["approver"] = "AGENT"
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

    def test_empty_action_in_grant_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            TraceAssuranceEngine().evaluate([{"type": "authorize", "action": "  "}])

    def test_negative_expiry_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            TraceAssuranceEngine().evaluate(
                [{"type": "authorize", "action": "delete", "expires_after_events": -1}]
            )

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
            item
            for item in report.violations
            if item.property_name == "shutdown_compliance"
        ]
        self.assertEqual(len(shutdown_violations), 1)

    def test_copilot_flags_ambiguous_requirement(self) -> None:
        artifact = VerificationCopilot().propose(
            Requirement("REQ-9", "The system should respond quickly and securely.")
        )
        self.assertIn("Requirement lacks a clear normative term", artifact.review_findings)
        self.assertIn("Requirement contains an ambiguous adjective", artifact.review_findings)
        self.assertEqual(artifact.generation_status, GenerationStatus.FALLBACK)
        self.assertTrue(artifact.artifact_review_findings)

    def test_copilot_generates_bounded_response(self) -> None:
        artifact = VerificationCopilot().propose(
            Requirement("REQ-10", "grant shall assert within 4 cycles after request")
        )
        self.assertEqual(
            artifact.assertion,
            "assert property (@(posedge clk) request |-> ##[1:4] grant);",
        )
        self.assertEqual(artifact.generation_status, GenerationStatus.SUPPORTED)
        self.assertEqual(artifact.matched_pattern, "bounded_response_after")
        self.assertFalse(artifact.review_findings)

    def test_copilot_supports_no_later_than_following(self) -> None:
        artifact = VerificationCopilot().propose(
            Requirement(
                "REQ-12",
                "the grant signal shall be asserted no later than 4 cycles following the request",
            )
        )
        self.assertIn("##[1:4] grant", artifact.assertion)
        self.assertEqual(artifact.matched_pattern, "no_later_than_following")

    def test_copilot_supports_conditional_bounded_response(self) -> None:
        artifact = VerificationCopilot().propose(
            Requirement("REQ-13", "if request, grant shall assert within 3 cycles")
        )
        self.assertIn("request |-> ##[1:3] grant", artifact.assertion)
        self.assertEqual(artifact.matched_pattern, "conditional_bounded_response")

    def test_copilot_supports_prohibition(self) -> None:
        artifact = VerificationCopilot().propose(
            Requirement("REQ-14", "grant shall never assert while reset")
        )
        self.assertIn("reset |-> !grant", artifact.assertion)
        self.assertEqual(artifact.matched_pattern, "prohibition_while_condition")

    def test_copilot_supports_immediate_implication(self) -> None:
        artifact = VerificationCopilot().propose(
            Requirement("REQ-15", "if request is high, busy shall be high")
        )
        self.assertIn("request |-> busy", artifact.assertion)
        self.assertEqual(artifact.matched_pattern, "immediate_implication")

    def test_copilot_supports_persistence(self) -> None:
        artifact = VerificationCopilot().propose(
            Requirement("REQ-16", "busy shall remain asserted until done")
        )
        self.assertIn("busy until_with done", artifact.assertion)
        self.assertEqual(artifact.matched_pattern, "persistence_until_release")

    def test_copilot_fallback_is_explicitly_reviewed(self) -> None:
        artifact = VerificationCopilot().propose(
            Requirement("REQ-11", "The service shall preserve authorization state.")
        )
        self.assertEqual(artifact.generation_status, GenerationStatus.FALLBACK)
        self.assertIn("FALLBACK", artifact.assertion)
        self.assertIn(
            "Generator used FALLBACK; no supported temporal pattern matched",
            artifact.artifact_review_findings,
        )


if __name__ == "__main__":
    unittest.main()
