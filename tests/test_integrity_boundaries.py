import unittest

from assurance_portfolio.cicd_integrity import (
    CICDDecision,
    TriggerTrust,
    WorkflowContext,
    validate_cicd_integrity,
)
from assurance_portfolio.evaluation_integrity import (
    AccessRecord,
    EvalLabel,
    EvaluationArtifact,
    EvaluationRun,
    compare_attribution,
    validate_evaluation_integrity,
)


class EvaluationIntegrityTests(unittest.TestCase):
    def test_clean_prediction_committed_before_label_release_is_valid(self):
        run = EvaluationRun(
            artifacts=(
                EvaluationArtifact("input", "dataset", (EvalLabel.MODEL_INPUT,)),
                EvaluationArtifact("intermediate", "module-a", (EvalLabel.MODEL_DERIVED,), ("input",)),
                EvaluationArtifact("prediction", "module-b", (EvalLabel.MODEL_DERIVED,), ("intermediate",)),
                EvaluationArtifact("gold", "evaluator", (EvalLabel.GROUND_TRUTH, EvalLabel.EVALUATOR_ONLY)),
            ),
            accesses=(
                AccessRecord("module-a", "input", 1),
                AccessRecord("module-b", "intermediate", 2),
                AccessRecord("evaluator", "gold", 5),
            ),
            prediction_artifact_id="prediction",
            prediction_commit_sequence=4,
            ground_truth_release_sequence=5,
            evaluator_principals=("evaluator",),
            system_principals=("module-a", "module-b"),
            scorer_principal="evaluator",
        )
        report = validate_evaluation_integrity(run)
        self.assertTrue(report.valid)
        self.assertEqual(report.violations, ())

    def test_transitive_answer_leak_invalidates_prediction(self):
        run = EvaluationRun(
            artifacts=(
                EvaluationArtifact("input", "dataset", (EvalLabel.MODEL_INPUT,)),
                EvaluationArtifact("gold", "evaluator", (EvalLabel.ANSWER_KEY, EvalLabel.EVALUATOR_ONLY)),
                EvaluationArtifact("hint", "module-a", (EvalLabel.MODEL_DERIVED,), ("gold",)),
                EvaluationArtifact("prediction", "module-b", (EvalLabel.MODEL_DERIVED,), ("input", "hint")),
            ),
            accesses=(AccessRecord("module-a", "gold", 2),),
            prediction_artifact_id="prediction",
            prediction_commit_sequence=4,
            ground_truth_release_sequence=5,
            evaluator_principals=("evaluator",),
            system_principals=("module-a", "module-b"),
            scorer_principal="evaluator",
        )
        report = validate_evaluation_integrity(run)
        self.assertFalse(report.valid)
        checks = {item.check for item in report.violations}
        self.assertIn("transitive_provenance_taint", checks)
        self.assertIn("evaluation_ground_truth_isolation", checks)

    def test_scoring_feedback_before_commit_is_rejected(self):
        run = EvaluationRun(
            artifacts=(
                EvaluationArtifact("input", "dataset", (EvalLabel.MODEL_INPUT,)),
                EvaluationArtifact("score", "evaluator", (EvalLabel.SCORING_SIGNAL,)),
                EvaluationArtifact("prediction", "module", (EvalLabel.MODEL_DERIVED,), ("input",)),
            ),
            accesses=(AccessRecord("module", "score", 2),),
            prediction_artifact_id="prediction",
            prediction_commit_sequence=4,
            ground_truth_release_sequence=5,
            evaluator_principals=("evaluator",),
            system_principals=("module",),
            scorer_principal="evaluator",
        )
        report = validate_evaluation_integrity(run)
        self.assertFalse(report.valid)
        self.assertIn("evaluation_feedback_isolation", {item.check for item in report.violations})

    def test_canary_access_is_detected(self):
        run = EvaluationRun(
            artifacts=(
                EvaluationArtifact("input", "dataset", (EvalLabel.MODEL_INPUT,)),
                EvaluationArtifact("canary", "evaluator", (EvalLabel.EVALUATION_CANARY, EvalLabel.EVALUATOR_ONLY)),
                EvaluationArtifact("prediction", "module", (EvalLabel.MODEL_DERIVED,), ("input",)),
            ),
            accesses=(AccessRecord("module", "canary", 2),),
            prediction_artifact_id="prediction",
            prediction_commit_sequence=3,
            ground_truth_release_sequence=4,
            evaluator_principals=("evaluator",),
            system_principals=("module",),
            scorer_principal="evaluator",
        )
        report = validate_evaluation_integrity(run)
        self.assertFalse(report.valid)
        self.assertIn("evaluation_canary_noninterference", {item.check for item in report.violations})

    def test_attribution_reports_privileged_channel_dependent_gain(self):
        result = compare_attribution(baseline_score=0.50, full_score=0.85, isolated_score=0.55)
        self.assertAlmostEqual(result.claimed_gain, 0.35)
        self.assertAlmostEqual(result.privileged_channel_dependent_gain, 0.30)
        self.assertGreater(result.privileged_gain_fraction, 0.8)


class CICDIntegrityTests(unittest.TestCase):
    def test_untrusted_trigger_on_read_only_sandbox_can_pass(self):
        context = WorkflowContext(
            workflow_name="agent-review",
            trigger="pull_request",
            trigger_trust=TriggerTrust.UNTRUSTED,
            source_ref="refs/pull/7/head",
            trusted_control_ref="refs/heads/main",
            actor="external-user",
            agent_principal="coding-agent",
            requested_action="analyze",
            requested_permissions=("contents:read",),
            runner_permissions=("contents:read",),
        )
        self.assertEqual(validate_cicd_integrity(context).decision, CICDDecision.ALLOW)

    def test_untrusted_trigger_cannot_use_write_runner(self):
        context = WorkflowContext(
            workflow_name="agent-fix",
            trigger="issue_comment",
            trigger_trust=TriggerTrust.UNTRUSTED,
            source_ref="refs/pull/7/head",
            trusted_control_ref="refs/heads/main",
            actor="external-user",
            agent_principal="coding-agent",
            requested_action="patch",
            requested_permissions=("contents:write",),
            runner_permissions=("contents:write",),
        )
        report = validate_cicd_integrity(context)
        self.assertEqual(report.decision, CICDDecision.BLOCK)
        self.assertIn(
            "untrusted_trigger_cannot_start_privileged_workflow",
            {item.check for item in report.violations},
        )

    def test_agent_cannot_modify_its_own_workflow(self):
        context = WorkflowContext(
            workflow_name="agent-fix",
            trigger="workflow_dispatch",
            trigger_trust=TriggerTrust.TRUSTED,
            source_ref="refs/heads/main",
            trusted_control_ref="refs/heads/main",
            actor="maintainer",
            agent_principal="coding-agent",
            requested_action="edit-workflow",
            requested_permissions=("contents:write",),
            runner_permissions=("contents:write",),
            modifies_workflow=True,
        )
        report = validate_cicd_integrity(context)
        self.assertEqual(report.decision, CICDDecision.BLOCK)
        self.assertIn(
            "agent_cannot_modify_its_own_policy_or_guardrails",
            {item.check for item in report.violations},
        )

    def test_production_promotion_requires_reviewed_artifact_and_independent_approval(self):
        context = WorkflowContext(
            workflow_name="promote",
            trigger="workflow_dispatch",
            trigger_trust=TriggerTrust.TRUSTED,
            source_ref="refs/heads/main",
            trusted_control_ref="refs/heads/main",
            actor="release-agent",
            agent_principal="release-agent",
            requested_action="deploy",
            requested_permissions=("deploy",),
            runner_permissions=("deploy",),
            production_effect=True,
            artifact_digest="sha256:good",
            reviewed_artifact_digest="sha256:good",
            approver="security-reviewer",
            approver_trust_domain="security",
            agent_trust_domain="automation",
        )
        self.assertEqual(validate_cicd_integrity(context).decision, CICDDecision.ALLOW)

    def test_mismatched_production_artifact_is_blocked(self):
        context = WorkflowContext(
            workflow_name="promote",
            trigger="workflow_dispatch",
            trigger_trust=TriggerTrust.TRUSTED,
            source_ref="refs/heads/main",
            trusted_control_ref="refs/heads/main",
            actor="release-agent",
            agent_principal="release-agent",
            requested_action="deploy",
            requested_permissions=("deploy",),
            runner_permissions=("deploy",),
            production_effect=True,
            artifact_digest="sha256:changed",
            reviewed_artifact_digest="sha256:reviewed",
            approver="security-reviewer",
            approver_trust_domain="security",
            agent_trust_domain="automation",
        )
        report = validate_cicd_integrity(context)
        self.assertEqual(report.decision, CICDDecision.BLOCK)
        self.assertIn("artifact_must_match_reviewed_commit", {item.check for item in report.violations})


if __name__ == "__main__":
    unittest.main()
