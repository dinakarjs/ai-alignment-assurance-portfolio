import json
import unittest

from assurance_portfolio.agentic_verification import (
    AgenticVerificationCopilot,
    ScriptedModelBackend,
)
from assurance_portfolio.sva_validation import (
    StructuralSVAValidator,
    ValidationStatus,
)
from assurance_portfolio.verification_benchmark import run_reference_benchmark
from assurance_portfolio.verification_copilot import Requirement


class AgenticVerificationTests(unittest.TestCase):
    def _generator_response(self) -> str:
        return json.dumps(
            {
                "assertion": "assert property (@(posedge clk) request |-> ##[1:4] grant);",
                "scenarios": [
                    "grant in two cycles",
                    "grant at four cycles",
                    "grant after four cycles",
                ],
                "coverage_goal": "exercise request and grant timing through cycle four",
                "assumptions": ["request and grant are sampled on clk"],
                "rationale": "the property encodes a bounded response",
            }
        )

    def test_structural_validator_accepts_well_formed_assertion(self) -> None:
        result = StructuralSVAValidator().validate(
            "assert property (@(posedge clk) request |-> grant);"
        )
        self.assertEqual(result.status, ValidationStatus.VALID)

    def test_structural_validator_rejects_fallback_placeholder(self) -> None:
        result = StructuralSVAValidator().validate(
            "assert property (requirement_holds); // FALLBACK: expert review required"
        )
        self.assertEqual(result.status, ValidationStatus.INVALID)

    def test_role_separated_agentic_path_requires_distinct_backends(self) -> None:
        backend = ScriptedModelBackend([])
        with self.assertRaises(ValueError):
            AgenticVerificationCopilot(
                generator_backend=backend,
                reviewer_backend=backend,
            )

    def test_model_draft_reviewer_and_validator_form_acceptance_gate(self) -> None:
        generator = ScriptedModelBackend(
            [self._generator_response()], name="scripted-generator"
        )
        reviewer = ScriptedModelBackend(
            [
                json.dumps(
                    {
                        "verdict": "ACCEPT_FOR_TOOL_CHECK",
                        "findings": ["clock/reset context still requires human confirmation"],
                        "recommended_action": "run deterministic validation",
                    }
                )
            ],
            name="scripted-reviewer",
        )
        artifact = AgenticVerificationCopilot(
            generator_backend=generator,
            reviewer_backend=reviewer,
        ).propose(
            Requirement("REQ-A1", "grant shall assert within 4 cycles after request")
        )
        self.assertEqual(artifact.generator_backend, "scripted-generator")
        self.assertEqual(artifact.reviewer_backend, "scripted-reviewer")
        self.assertEqual(artifact.validation.status, ValidationStatus.VALID)
        self.assertTrue(artifact.accepted_for_human_review)
        self.assertEqual(artifact.deterministic_baseline_status, "SUPPORTED")

    def test_reviewer_revise_blocks_tool_acceptance(self) -> None:
        generator = ScriptedModelBackend([self._generator_response()])
        reviewer = ScriptedModelBackend(
            [
                json.dumps(
                    {
                        "verdict": "REVISE",
                        "findings": ["reset semantics are missing"],
                        "recommended_action": "add reset assumptions and regenerate",
                    }
                )
            ]
        )
        artifact = AgenticVerificationCopilot(
            generator_backend=generator,
            reviewer_backend=reviewer,
        ).propose(
            Requirement("REQ-A2", "grant shall assert within 4 cycles after request")
        )
        self.assertEqual(artifact.validation.status, ValidationStatus.UNAVAILABLE)
        self.assertFalse(artifact.accepted_for_human_review)

    def test_reference_trace_benchmark_detects_seeded_failures(self) -> None:
        results = run_reference_benchmark()
        self.assertTrue(results)
        for result in results:
            self.assertEqual(result.accuracy, 1.0)
            self.assertEqual(result.false_positives, 0)
            self.assertEqual(result.defect_detection_rate, 1.0)


if __name__ == "__main__":
    unittest.main()
