import unittest

from assurance_portfolio.cloudguard_v4 import (
    DetectionEvidence,
    ResponseDecision,
    ResponseImpactTier,
    ThreatSourceTrust,
)
from assurance_portfolio.cloudguard_v5 import (
    AttackObservation,
    AttackPathForecaster,
    ExposureEdge,
    ExposureGraph,
    ForecastAssurance,
    ForecastHorizon,
    ForecastMetrics,
    ModelCandidate,
    ModelGovernanceRegistry,
    Observability,
    PredictiveThreatEngine,
    PreemptionOptimizer,
    PreventiveControl,
    PromotionDecision,
    PromotionReview,
    SecurityNode,
    TechniqueExposure,
    TechniqueTransitionModel,
    ThreatStateEstimator,
    TrainingDisposition,
    TrainingExample,
    TrainingQuarantine,
    VulnerabilityExposure,
    brier_score,
    control_to_response_request,
    expected_calibration_error,
    gate_preemption,
    recall_at_k,
)


class CloudGuardV5Tests(unittest.TestCase):
    def _transition_model(self) -> TechniqueTransitionModel:
        return TechniqueTransitionModel.from_sequences(
            [
                ["T-CRED", "T-DISC", "T-PRIV", "T-SECRET"],
                ["T-CRED", "T-DISC", "T-PRIV", "T-DATA"],
                ["T-CRED", "T-PRIV", "T-SECRET"],
                ["T-DISC", "T-PRIV", "T-DATA"],
            ]
        )

    def _exposure_graph(self) -> ExposureGraph:
        return ExposureGraph(
            nodes=(
                SecurityNode("identity-dev", "identity", 0.4),
                SecurityNode("role-prod", "role", 0.8),
                SecurityNode("secret-prod", "secret", 0.9),
                SecurityNode("data-prod", "storage", 1.0),
            ),
            edges=(
                ExposureEdge("identity-dev", "role-prod", "can_assume"),
                ExposureEdge("role-prod", "secret-prod", "can_read"),
                ExposureEdge("role-prod", "data-prod", "can_read"),
            ),
            vulnerabilities=(
                VulnerabilityExposure("role-prod", "CVE-1", 0.62, True),
            ),
            technique_exposures=(
                TechniqueExposure("T-DISC", ("role-prod",), 0.2),
                TechniqueExposure("T-PRIV", ("role-prod",), 0.1, True),
                TechniqueExposure("T-SECRET", ("secret-prod",), 0.3),
                TechniqueExposure("T-DATA", ("data-prod",), 0.2),
            ),
        )

    def _engine(self) -> PredictiveThreatEngine:
        return PredictiveThreatEngine(
            state_estimator=ThreatStateEstimator(),
            path_forecaster=AttackPathForecaster(self._transition_model(), self._exposure_graph()),
        )

    def test_state_estimator_reduces_assurance_when_observability_is_missing(self) -> None:
        observations = (
            AttackObservation("O1", "T-CRED", 1, "identity", True),
            AttackObservation("O2", "T-DISC", 2, "cloudtrail", True),
        )
        state = ThreatStateEstimator().estimate(
            observations,
            Observability(("identity", "cloudtrail", "endpoint", "network"), ("identity", "cloudtrail")),
        )
        self.assertEqual(state.primary_technique, "T-DISC")
        self.assertEqual(state.assurance, ForecastAssurance.PARTIAL)
        self.assertEqual(set(state.missing_sources), {"endpoint", "network"})

    def test_predictive_profile_ranks_exposure_aware_next_actions(self) -> None:
        profile = self._engine().build_profile(
            profile_id="TP-1",
            observations=(AttackObservation("O1", "T-DISC", 1, "cloudtrail", True),),
            observability=Observability(("cloudtrail",), ("cloudtrail",)),
            start_nodes=("identity-dev",),
            horizon=ForecastHorizon.IMMEDIATE,
            top_k=3,
        )
        self.assertEqual(profile.state.assurance, ForecastAssurance.HIGH)
        self.assertTrue(profile.next_techniques)
        self.assertEqual(profile.next_techniques[0].technique_id, "T-PRIV")
        self.assertTrue(profile.next_techniques[0].known_exploited)
        self.assertTrue(profile.attack_paths)

    def test_unreachable_technique_has_zero_local_priority(self) -> None:
        graph = self._exposure_graph()
        score = graph.score_technique("T-SECRET", start_nodes=("secret-prod",))
        self.assertTrue(score.reachable)
        score = graph.score_technique("T-PRIV", start_nodes=("secret-prod",))
        self.assertFalse(score.reachable)
        self.assertEqual(score.local_priority, 0.0)

    def test_preemption_prefers_path_breaking_low_cost_control(self) -> None:
        profile = self._engine().build_profile(
            profile_id="TP-2",
            observations=(AttackObservation("O1", "T-DISC", 1, "cloudtrail", True),),
            observability=Observability(("cloudtrail",), ("cloudtrail",)),
            start_nodes=("identity-dev",),
            top_k=5,
        )
        controls = (
            PreventiveControl(
                "CTRL-ROLE",
                "restrict_role_assumption",
                "role-prod",
                ResponseImpactTier.TEMPORARY_CONTAINMENT,
                0.15,
                ("T-PRIV",),
                {"expires_after_minutes": 30},
            ),
            PreventiveControl(
                "CTRL-STOP",
                "stop_production_workload",
                "data-prod",
                ResponseImpactTier.DESTRUCTIVE_OR_BUSINESS_CRITICAL,
                0.95,
                ("T-PRIV", "T-SECRET", "T-DATA"),
            ),
        )
        ranked = PreemptionOptimizer().rank(profile.attack_paths, controls)
        self.assertTrue(ranked)
        self.assertEqual(ranked[0].control_ids, ("CTRL-ROLE",))

    def test_predictive_control_still_requires_v4_human_gate(self) -> None:
        control = PreventiveControl(
            "CTRL-ACCOUNT",
            "disable_account",
            "user-1",
            ResponseImpactTier.ACCOUNT_OR_PRIVILEGE_CHANGE,
            0.4,
            ("T-PRIV",),
        )
        request = control_to_response_request(
            control,
            incident_id="INC-1",
            requested_by="cloudguard-v5",
            evidence_ids=("EV-1",),
            threat_ids=("THREAT-1",),
        )
        result = gate_preemption(
            request,
            evidence=(DetectionEvidence("EV-1", "cloudtrail", True, "CURRENT", "a" * 64),),
        )
        self.assertEqual(result.decision, ResponseDecision.ESCALATE)
        self.assertEqual(result.required_reviewers, 1)

    def test_untrusted_training_data_remains_quarantined_without_corroboration(self) -> None:
        example = TrainingExample(
            "EX-1",
            "INC-1",
            ThreatSourceTrust.UNTRUSTED_DISCOVERY,
            "a" * 64,
            True,
            corroborated_by=("source-a",),
            analyst_approved=True,
        )
        result = TrainingQuarantine().evaluate(example)
        self.assertEqual(result.disposition, TrainingDisposition.QUARANTINED)

    def test_untrusted_training_data_can_become_eligible_after_strong_review(self) -> None:
        example = TrainingExample(
            "EX-2",
            "INC-2",
            ThreatSourceTrust.UNTRUSTED_DISCOVERY,
            "b" * 64,
            True,
            corroborated_by=("source-a", "source-b"),
            analyst_approved=True,
        )
        result = TrainingQuarantine().evaluate(example)
        self.assertEqual(result.disposition, TrainingDisposition.ELIGIBLE)

    def test_challenger_promotion_requires_calibration_retention_poison_and_shadow_gates(self) -> None:
        example = TrainingExample(
            "EX-3",
            "INC-3",
            ThreatSourceTrust.INTERNAL_CONFIRMED,
            "c" * 64,
            True,
        )
        good = ModelCandidate(
            "MODEL-2",
            "2.0.0",
            "ml-engineer",
            (example,),
            ForecastMetrics(0.80, 0.12, 0.05, 0.95, True, 100),
        )
        registry = ModelGovernanceRegistry(active_version="1.0.0")
        approved = registry.review(
            good,
            PromotionReview("security-reviewer", True, "shadow and poison suites passed"),
        )
        self.assertEqual(approved.decision, PromotionDecision.APPROVED)

        poor = ModelCandidate(
            "MODEL-3",
            "3.0.0",
            "ml-engineer",
            (example,),
            ForecastMetrics(0.90, 0.10, 0.02, 0.60, False, 100),
        )
        rejected = registry.review(
            poor,
            PromotionReview("security-reviewer", True, "candidate review"),
        )
        self.assertEqual(rejected.decision, PromotionDecision.REJECTED)
        self.assertTrue(any("retention" in reason for reason in rejected.reasons))
        self.assertTrue(any("poison" in reason for reason in rejected.reasons))

    def test_candidate_cannot_self_approve(self) -> None:
        example = TrainingExample(
            "EX-4", "INC-4", ThreatSourceTrust.INTERNAL_CONFIRMED, "d" * 64, True
        )
        candidate = ModelCandidate(
            "MODEL-4",
            "4.0.0",
            "ml-engineer",
            (example,),
            ForecastMetrics(0.80, 0.10, 0.02, 0.96, True, 100),
        )
        result = ModelGovernanceRegistry(active_version="1.0.0").review(
            candidate,
            PromotionReview("ML-ENGINEER", True, "approve"),
        )
        self.assertEqual(result.decision, PromotionDecision.REJECTED)
        self.assertTrue(any("own promotion" in reason for reason in result.reasons))

    def test_forecast_metrics_helpers(self) -> None:
        self.assertEqual(recall_at_k((("A", "B"), ("C", "D")), ("B", "X"), k=2), 0.5)
        self.assertAlmostEqual(brier_score((0.8, 0.2), (1, 0)), 0.04)
        ece = expected_calibration_error((0.9, 0.8, 0.1, 0.2), (1, 1, 0, 0), bins=2)
        self.assertGreaterEqual(ece, 0.0)
        self.assertLessEqual(ece, 1.0)


if __name__ == "__main__":
    unittest.main()
