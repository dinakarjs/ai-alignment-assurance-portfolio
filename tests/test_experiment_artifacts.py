import json
from pathlib import Path
import tempfile
import unittest

from assurance_portfolio.agentic_verification import ModelUsage, ScriptedModelBackend, backend_usage
from assurance_portfolio.corpus_evaluation import (
    ConditionAggregate,
    CorpusEvaluationSummary,
    CorpusTrial,
    CorpusWorkflowResult,
)
from assurance_portfolio.experiment_artifacts import write_experiment_bundle


class ExperimentArtifactTests(unittest.TestCase):
    def test_model_usage_add_and_delta(self):
        first = ModelUsage(True, 2, 100, 40, 140)
        second = ModelUsage(True, 3, 170, 65, 235)
        delta = second.delta(first)
        self.assertEqual(delta.requests, 1)
        self.assertEqual(delta.input_tokens, 70)
        self.assertEqual(delta.output_tokens, 25)
        self.assertEqual(delta.total_tokens, 95)
        combined = first + delta
        self.assertEqual(combined.total_tokens, 235)

    def test_scripted_backend_reports_requests_without_token_claim(self):
        backend = ScriptedModelBackend(["{}"])
        before = backend_usage(backend)
        backend.complete(role="generator", prompt="test")
        delta = backend_usage(backend).delta(before)
        self.assertFalse(delta.available)
        self.assertEqual(delta.requests, 1)
        self.assertEqual(delta.total_tokens, 0)

    def test_experiment_bundle_writes_expected_files_and_stable_id(self):
        row = CorpusWorkflowResult(
            trial_id=1,
            condition="deterministic",
            case_id="BR-001",
            family="bounded_response",
            assertion="assert property (@(posedge clk) request |-> ##[1:4] grant);",
            generation_succeeded=True,
            reviewer_verdict=None,
            structural_valid=True,
            behavioral_executed=True,
            good_rtl_passed=True,
            mutation_detected=True,
            false_positive_count=0,
            fully_correct=True,
            elapsed_seconds=0.1,
            notes=("reference",),
        )
        trial = CorpusTrial(
            trial_id=1,
            evidence_kind="scripted_offline",
            model_label="scripted-fixtures",
            prompt_version="v9.0",
            results=(row,),
        )
        aggregate = ConditionAggregate(
            condition="deterministic",
            cases=1,
            generation_failure_rate=0.0,
            escalation_rate=0.0,
            behavioral_execution_rate=1.0,
            full_correct_rate=1.0,
            mutation_detection_rate=1.0,
            false_positive_rate=0.0,
            mean_elapsed_seconds=0.1,
            usage_available_rate=0.0,
            model_requests=0,
            input_tokens=None,
            output_tokens=None,
            total_tokens=None,
        )
        summary = CorpusEvaluationSummary(
            evidence_kind="scripted_offline",
            trials=1,
            cases_per_trial=1,
            model_label="scripted-fixtures",
            prompt_version="v9.0",
            aggregates=(aggregate,),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            first = write_experiment_bundle(
                (trial,), summary, output_root=temp_dir,
                command="assurance-demo corpus-eval --trials 1",
                rtl_root="benchmarks/rtl",
            )
            second = write_experiment_bundle(
                (trial,), summary, output_root=temp_dir,
                command="assurance-demo corpus-eval --trials 1",
                rtl_root="benchmarks/rtl",
            )
            self.assertEqual(first.name, second.name)
            expected = {
                "manifest.json", "trials.json", "summary.json",
                "results.csv", "aggregates.csv", "REPORT.md",
            }
            self.assertEqual(expected, {path.name for path in first.iterdir()})
            manifest = json.loads((first / "manifest.json").read_text())
            self.assertEqual(manifest["run_id"], first.name)
            self.assertIsNone(manifest["cost_usd"])
            report = (first / "REPORT.md").read_text()
            self.assertIn("Interpretation boundary", report)
            self.assertIn("Dollar cost is intentionally not estimated", report)


if __name__ == "__main__":
    unittest.main()
