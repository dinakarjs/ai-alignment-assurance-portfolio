import tempfile
import unittest
from pathlib import Path

from assurance_portfolio.cloudguard_v4 import (
    CloudGuardAuditStore,
    CloudGuardFeedbackEngine,
    CloudGuardPolicyEngine,
    DetectionEvidence,
    FeedbackGap,
    FieldIssue,
    HumanDisposition,
    HumanReview,
    RegressionEvidence,
    ResponseDecision,
    ResponseImpactTier,
    ResponseRequest,
    ThreatChangeType,
    ThreatKnowledgeRegistry,
    ThreatRecord,
    ThreatSource,
    ThreatSourceTrust,
    ThreatUpdateProposal,
    ThreatUpdateReview,
)


class CloudGuardV4Tests(unittest.TestCase):
    def _evidence(self, *, verified: bool = True) -> tuple[DetectionEvidence, ...]:
        return (
            DetectionEvidence(
                evidence_id="EV-1",
                source="cloudtrail",
                verified=verified,
                freshness="CURRENT",
                content_digest="a" * 64,
            ),
        )

    def _review(self, request: ResponseRequest, **overrides: object) -> HumanReview:
        values: dict[str, object] = {
            "review_id": "HR-1",
            "incident_id": request.incident_id,
            "action": request.action,
            "target": request.target,
            "request_digest": request.request_digest,
            "reviewer": "analyst-1",
            "reviewer_trust_domain": "soc",
            "disposition": HumanDisposition.APPROVE,
            "rationale": "Correlated cloud telemetry confirms compromise",
            "evidence_reviewed": ("EV-1",),
            "second_reviewer": None,
            "second_reviewer_trust_domain": None,
        }
        values.update(overrides)
        return HumanReview(**values)  # type: ignore[arg-type]

    def test_read_only_response_allowed_without_human_review(self) -> None:
        request = ResponseRequest(
            "INC-1", "query_cloudtrail", "acct-1", "soc-agent", ResponseImpactTier.OBSERVE,
            evidence_ids=("EV-1",),
        )
        result = CloudGuardPolicyEngine().decide(request, evidence=self._evidence())
        self.assertEqual(result.decision, ResponseDecision.ALLOW)
        self.assertEqual(result.required_reviewers, 0)

    def test_unverified_evidence_cannot_authorize_response(self) -> None:
        request = ResponseRequest(
            "INC-2", "revoke_token", "token-7", "soc-agent",
            ResponseImpactTier.ACCOUNT_OR_PRIVILEGE_CHANGE, evidence_ids=("EV-1",),
        )
        result = CloudGuardPolicyEngine().decide(request, evidence=self._evidence(verified=False))
        self.assertEqual(result.decision, ResponseDecision.ESCALATE)

    def test_account_change_requires_exactly_bound_human_approval(self) -> None:
        request = ResponseRequest(
            "INC-3", "disable_account", "user-7", "soc-agent",
            ResponseImpactTier.ACCOUNT_OR_PRIVILEGE_CHANGE, evidence_ids=("EV-1",),
        )
        self.assertEqual(
            CloudGuardPolicyEngine().decide(request, evidence=self._evidence()).decision,
            ResponseDecision.ESCALATE,
        )
        self.assertEqual(
            CloudGuardPolicyEngine().decide(request, evidence=self._evidence(), review=self._review(request)).decision,
            ResponseDecision.ALLOW,
        )

    def test_target_or_parameter_substitution_invalidates_human_approval(self) -> None:
        request = ResponseRequest(
            "INC-3B", "revoke_token", "token-7", "soc-agent",
            ResponseImpactTier.ACCOUNT_OR_PRIVILEGE_CHANGE,
            parameters={"token": "token-7"}, evidence_ids=("EV-1",),
        )
        review = self._review(request)
        changed_target = ResponseRequest(
            "INC-3B", "revoke_token", "token-8", "soc-agent",
            ResponseImpactTier.ACCOUNT_OR_PRIVILEGE_CHANGE,
            parameters={"token": "token-8"}, evidence_ids=("EV-1",),
        )
        result = CloudGuardPolicyEngine().decide(changed_target, evidence=self._evidence(), review=review)
        self.assertEqual(result.decision, ResponseDecision.BLOCK)

    def test_destructive_action_requires_dual_independent_approval(self) -> None:
        request = ResponseRequest(
            "INC-4", "stop_production_workload", "prod-1", "soc-agent",
            ResponseImpactTier.DESTRUCTIVE_OR_BUSINESS_CRITICAL, evidence_ids=("EV-1",),
        )
        one = self._review(request)
        self.assertEqual(
            CloudGuardPolicyEngine().decide(request, evidence=self._evidence(), review=one).decision,
            ResponseDecision.ESCALATE,
        )
        same_domain = self._review(
            request,
            second_reviewer="analyst-2",
            second_reviewer_trust_domain="soc",
        )
        self.assertEqual(
            CloudGuardPolicyEngine().decide(request, evidence=self._evidence(), review=same_domain).decision,
            ResponseDecision.ESCALATE,
        )
        dual = self._review(
            request,
            second_reviewer="incident-commander",
            second_reviewer_trust_domain="security-leadership",
        )
        self.assertEqual(
            CloudGuardPolicyEngine().decide(request, evidence=self._evidence(), review=dual).decision,
            ResponseDecision.ALLOW,
        )

    def test_emergency_containment_requires_real_time_bound(self) -> None:
        missing = ResponseRequest(
            "INC-E1", "temporary_quarantine", "host-1", "soc-agent",
            ResponseImpactTier.TEMPORARY_CONTAINMENT,
            evidence_ids=("EV-1",), emergency=True,
        )
        self.assertEqual(
            CloudGuardPolicyEngine().decide(missing, evidence=self._evidence()).decision,
            ResponseDecision.BLOCK,
        )
        too_long = ResponseRequest(
            "INC-E2", "temporary_quarantine", "host-1", "soc-agent",
            ResponseImpactTier.TEMPORARY_CONTAINMENT,
            parameters={"expires_after_minutes": 120}, evidence_ids=("EV-1",), emergency=True,
        )
        self.assertEqual(
            CloudGuardPolicyEngine().decide(too_long, evidence=self._evidence()).decision,
            ResponseDecision.BLOCK,
        )
        bounded = ResponseRequest(
            "INC-E3", "temporary_quarantine", "host-1", "soc-agent",
            ResponseImpactTier.TEMPORARY_CONTAINMENT,
            parameters={"expires_after_minutes": 30}, evidence_ids=("EV-1",), emergency=True,
        )
        self.assertEqual(
            CloudGuardPolicyEngine().decide(bounded, evidence=self._evidence()).decision,
            ResponseDecision.ALLOW,
        )

    def _proposal(
        self,
        trust: ThreatSourceTrust = ThreatSourceTrust.AUTHORITATIVE,
        *,
        weakens: bool = False,
        version: str = "1.0.0",
        severity: str = "HIGH",
        confidence: int | None = None,
    ) -> ThreatUpdateProposal:
        source = ThreatSource("SRC-1", "MITRE ATT&CK", trust, reference="T0001", content_digest="b" * 64)
        record = ThreatRecord(
            "THREAT-1", version, "Cloud token replay", ThreatChangeType.NEW_TTP,
            severity, source, techniques=("T0001",), observables=("token-reuse",), confidence=confidence,
        )
        return ThreatUpdateProposal("TDU-1", record, "threat-agent", "New behavior identified", weakens_existing_control=weakens)

    def _regression(self) -> RegressionEvidence:
        return RegressionEvidence("REG-1", 10, 20, 0, 0.001, ("T0001",))

    def test_threat_update_requires_independent_review_and_regression(self) -> None:
        registry = ThreatKnowledgeRegistry()
        registry.propose(self._proposal())
        with self.assertRaises(PermissionError):
            registry.activate(ThreatUpdateReview("TDU-1", "threat-agent", HumanDisposition.APPROVE, "self", regression=self._regression()))
        with self.assertRaises(PermissionError):
            registry.activate(ThreatUpdateReview("TDU-1", "analyst-1", HumanDisposition.APPROVE, "approved"))
        active = registry.activate(ThreatUpdateReview("TDU-1", "analyst-1", HumanDisposition.APPROVE, "validated", regression=self._regression()))
        self.assertEqual(active.version, "1.0.0")

    def test_untrusted_or_weakening_update_requires_second_reviewer(self) -> None:
        for proposal in (self._proposal(ThreatSourceTrust.UNTRUSTED_DISCOVERY), self._proposal(weakens=True)):
            registry = ThreatKnowledgeRegistry()
            registry.propose(proposal)
            with self.assertRaises(PermissionError):
                registry.activate(ThreatUpdateReview("TDU-1", "analyst-1", HumanDisposition.APPROVE, "reviewed", regression=self._regression()))

    def test_threat_record_validation_rejects_bad_version_severity_and_confidence(self) -> None:
        for proposal in (
            self._proposal(version="v1"),
            self._proposal(severity="SEVERE"),
            self._proposal(confidence=101),
        ):
            with self.assertRaises(ValueError):
                ThreatKnowledgeRegistry().propose(proposal)

    def test_threat_version_is_immutable(self) -> None:
        registry = ThreatKnowledgeRegistry()
        proposal = self._proposal()
        registry.propose(proposal)
        with self.assertRaises(ValueError):
            registry.propose(ThreatUpdateProposal(**{**proposal.__dict__, "update_id": "TDU-2"}))

    def test_audit_chain_detects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"
            store = CloudGuardAuditStore(path)
            store.append("THREAT_DETECTION", {"incident_id": "INC-1"})
            store.append("HUMAN_REVIEW", {"reviewer": "analyst-1"})
            self.assertTrue(store.verify()[0])
            path.write_text(path.read_text(encoding="utf-8").replace("analyst-1", "attacker"), encoding="utf-8")
            ok, detail = store.verify()
            self.assertFalse(ok)
            self.assertIn("hash mismatch", detail)

    def test_feedback_loop_classifies_gaps_and_never_auto_activates(self) -> None:
        engine = CloudGuardFeedbackEngine()
        threat_gap = engine.analyze(FieldIssue("FI-1", "INC-1", True, False, False, True, False, False, False, False))
        self.assertEqual(threat_gap.gap, FeedbackGap.THREAT_DB_GAP)
        detector_gap = engine.analyze(FieldIssue("FI-2", "INC-2", True, False, False, True, True, False, False, False))
        self.assertEqual(detector_gap.gap, FeedbackGap.DETECTION_GAP)
        policy_gap = engine.analyze(FieldIssue("FI-3", "INC-3", True, True, True, True, True, False, False, False))
        self.assertEqual(policy_gap.gap, FeedbackGap.POLICY_GAP)
        self.assertTrue(all("activate" not in item.lower() for item in policy_gap.proposed_updates))


if __name__ == "__main__":
    unittest.main()
