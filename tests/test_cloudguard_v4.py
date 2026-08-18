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

    def test_read_only_response_allowed_without_human_review(self) -> None:
        request = ResponseRequest(
            incident_id="INC-1",
            action="query_cloudtrail",
            target="acct-1",
            requested_by="soc-agent",
            impact_tier=ResponseImpactTier.OBSERVE,
            evidence_ids=("EV-1",),
        )
        result = CloudGuardPolicyEngine().decide(request, evidence=self._evidence())
        self.assertEqual(result.decision, ResponseDecision.ALLOW)
        self.assertEqual(result.required_reviewers, 0)

    def test_unverified_evidence_cannot_authorize_response(self) -> None:
        request = ResponseRequest(
            incident_id="INC-2",
            action="revoke_token",
            target="token-7",
            requested_by="soc-agent",
            impact_tier=ResponseImpactTier.ACCOUNT_OR_PRIVILEGE_CHANGE,
            evidence_ids=("EV-1",),
        )
        result = CloudGuardPolicyEngine().decide(request, evidence=self._evidence(verified=False))
        self.assertEqual(result.decision, ResponseDecision.ESCALATE)

    def test_account_change_requires_human_approval(self) -> None:
        request = ResponseRequest(
            incident_id="INC-3",
            action="disable_account",
            target="user-7",
            requested_by="soc-agent",
            impact_tier=ResponseImpactTier.ACCOUNT_OR_PRIVILEGE_CHANGE,
            evidence_ids=("EV-1",),
        )
        result = CloudGuardPolicyEngine().decide(request, evidence=self._evidence())
        self.assertEqual(result.decision, ResponseDecision.ESCALATE)
        review = HumanReview(
            review_id="HR-1",
            incident_id="INC-3",
            action="disable_account",
            reviewer="analyst-1",
            reviewer_trust_domain="soc",
            disposition=HumanDisposition.APPROVE,
            rationale="Correlated cloud telemetry confirms compromise",
            evidence_reviewed=("EV-1",),
        )
        result = CloudGuardPolicyEngine().decide(request, evidence=self._evidence(), review=review)
        self.assertEqual(result.decision, ResponseDecision.ALLOW)

    def test_destructive_action_requires_dual_independent_approval(self) -> None:
        request = ResponseRequest(
            incident_id="INC-4",
            action="stop_production_workload",
            target="prod-1",
            requested_by="soc-agent",
            impact_tier=ResponseImpactTier.DESTRUCTIVE_OR_BUSINESS_CRITICAL,
            evidence_ids=("EV-1",),
        )
        one_reviewer = HumanReview(
            review_id="HR-2",
            incident_id="INC-4",
            action="stop_production_workload",
            reviewer="analyst-1",
            reviewer_trust_domain="soc",
            disposition=HumanDisposition.APPROVE,
            rationale="Confirmed active destructive compromise",
            evidence_reviewed=("EV-1",),
        )
        result = CloudGuardPolicyEngine().decide(request, evidence=self._evidence(), review=one_reviewer)
        self.assertEqual(result.decision, ResponseDecision.ESCALATE)
        dual = HumanReview(
            **{**one_reviewer.__dict__, "second_reviewer": "incident-commander", "second_reviewer_trust_domain": "security-leadership"}
        )
        result = CloudGuardPolicyEngine().decide(request, evidence=self._evidence(), review=dual)
        self.assertEqual(result.decision, ResponseDecision.ALLOW)

    def _proposal(self, trust: ThreatSourceTrust = ThreatSourceTrust.AUTHORITATIVE, *, weakens: bool = False) -> ThreatUpdateProposal:
        source = ThreatSource("SRC-1", "MITRE ATT&CK", trust, reference="T0001", content_digest="b" * 64)
        record = ThreatRecord(
            threat_id="THREAT-1",
            version="1.0.0",
            name="Cloud token replay",
            change_type=ThreatChangeType.NEW_TTP,
            severity="HIGH",
            source=source,
            techniques=("T0001",),
            observables=("token-reuse",),
        )
        return ThreatUpdateProposal(
            update_id="TDU-1",
            record=record,
            proposed_by="threat-agent",
            rationale="New behavior identified",
            weakens_existing_control=weakens,
        )

    def _regression(self) -> RegressionEvidence:
        return RegressionEvidence("REG-1", 10, 20, 0, 0.001, ("T0001",))

    def test_threat_update_requires_independent_review_and_regression(self) -> None:
        registry = ThreatKnowledgeRegistry()
        proposal = self._proposal()
        registry.propose(proposal)
        with self.assertRaises(PermissionError):
            registry.activate(
                ThreatUpdateReview("TDU-1", "threat-agent", HumanDisposition.APPROVE, "self approve", regression=self._regression())
            )
        with self.assertRaises(PermissionError):
            registry.activate(
                ThreatUpdateReview("TDU-1", "analyst-1", HumanDisposition.APPROVE, "approved")
            )
        active = registry.activate(
            ThreatUpdateReview("TDU-1", "analyst-1", HumanDisposition.APPROVE, "validated", regression=self._regression())
        )
        self.assertEqual(active.version, "1.0.0")
        self.assertEqual(len(active.digest), 64)

    def test_untrusted_threat_update_requires_second_reviewer(self) -> None:
        registry = ThreatKnowledgeRegistry()
        proposal = self._proposal(ThreatSourceTrust.UNTRUSTED_DISCOVERY)
        registry.propose(proposal)
        with self.assertRaises(PermissionError):
            registry.activate(
                ThreatUpdateReview("TDU-1", "analyst-1", HumanDisposition.APPROVE, "looks plausible", regression=self._regression())
            )
        active = registry.activate(
            ThreatUpdateReview(
                "TDU-1",
                "analyst-1",
                HumanDisposition.APPROVE,
                "independently corroborated",
                second_reviewer="security-lead",
                regression=self._regression(),
            )
        )
        self.assertEqual(active.threat_id, "THREAT-1")

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
            ok, _ = store.verify()
            self.assertTrue(ok)
            text = path.read_text(encoding="utf-8").replace("analyst-1", "attacker")
            path.write_text(text, encoding="utf-8")
            ok, detail = store.verify()
            self.assertFalse(ok)
            self.assertIn("hash mismatch", detail)

    def test_feedback_loop_classifies_detection_and_threat_db_gaps(self) -> None:
        engine = CloudGuardFeedbackEngine()
        threat_gap = engine.analyze(
            FieldIssue("FI-1", "INC-1", True, False, False, True, False, False, False, False)
        )
        self.assertEqual(threat_gap.gap, FeedbackGap.THREAT_DB_GAP)
        detector_gap = engine.analyze(
            FieldIssue("FI-2", "INC-2", True, False, False, True, True, False, False, False)
        )
        self.assertEqual(detector_gap.gap, FeedbackGap.DETECTION_GAP)

    def test_feedback_loop_never_auto_activates_change(self) -> None:
        analysis = CloudGuardFeedbackEngine().analyze(
            FieldIssue("FI-3", "INC-3", True, True, True, True, True, False, False, False)
        )
        self.assertEqual(analysis.gap, FeedbackGap.POLICY_GAP)
        self.assertTrue(all("activate" not in item.lower() for item in analysis.proposed_updates))


if __name__ == "__main__":
    unittest.main()
