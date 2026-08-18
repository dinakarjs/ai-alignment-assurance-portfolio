import unittest

from assurance_portfolio.agentic_verification import ScriptedModelBackend
from assurance_portfolio.controlled_evaluation import (
    WorkflowCondition,
    parse_bounded_assertion,
    run_controlled_evaluation,
)
from assurance_portfolio.rtl_behavioral import RTLBehavioralResult, RTLRunStatus
from assurance_portfolio.verification_copilot import Requirement


GOOD_DRAFT = """{
  "assertion": "assert property (@(posedge clk) request |-> ##[1:4] grant);",
  "scenarios": ["nominal", "boundary", "violation"],
  "coverage_goal": "cover request-to-grant timing",
  "assumptions": ["posedge clk"],
  "rationale": "bounded response"
}"""

TOO_STRICT_DRAFT = """{
  "assertion": "assert property (@(posedge clk) request |-> ##[1:2] grant);",
  "scenarios": ["nominal", "boundary", "violation"],
  "coverage_goal": "cover request-to-grant timing",
  "assumptions": ["posedge clk"],
  "rationale": "intentionally too strict scripted candidate"
}"""

ACCEPT_REVIEW = """{
  "verdict": "ACCEPT_FOR_TOOL_CHECK",
  "findings": [],
  "recommended_action": "run deterministic tool check"
}"""

REVISE_REVIEW = """{
  "verdict": "REVISE",
  "findings": ["timing bound is too strict"],
  "recommended_action": "restore the four-cycle bound"
}"""


class FakeBehavioralRunner:
    """Reproduce the labelled fixture behavior without requiring a simulator."""

    def run(self, *, source, module_name, expected_pass, max_cycles=4):
        del source
        if module_name == "handshake_good":
            # Good RTL grants on cycle 3.
            passed = max_cycles >= 3
        else:
            # Mutated RTL grants after cycle 4, so a <=4 bound detects it.
            passed = max_cycles >= 7
        return RTLBehavioralResult(
            design=module_name,
            status=RTLRunStatus.PASS if passed else RTLRunStatus.FAIL,
            expected_pass=expected_pass,
            requirement=f"grant shall assert within {max_cycles} cycles after request",
            simulator="fake",
            tool_version="fake-1",
            detail="scripted behavioral result",
            output="",
        )


class ControlledEvaluationTests(unittest.TestCase):
    def test_parse_bounded_assertion(self):
        parsed = parse_bounded_assertion(
            "assert property (@(posedge clk) request |-> ##[1:4] grant);"
        )
        self.assertEqual(parsed, ("request", "grant", 4))

    def test_scripted_comparison_records_distinct_workflow_outcomes(self):
        report = run_controlled_evaluation(
            Requirement("REQ-EVAL-1", "grant shall assert within 4 cycles after request"),
            single_generator_backend=ScriptedModelBackend([TOO_STRICT_DRAFT], "single"),
            reviewed_generator_backend=ScriptedModelBackend([TOO_STRICT_DRAFT], "reviewed-gen"),
            reviewer_backend=ScriptedModelBackend([REVISE_REVIEW], "reviewer"),
            tool_generator_backend=ScriptedModelBackend([GOOD_DRAFT], "tool-gen"),
            tool_reviewer_backend=ScriptedModelBackend([ACCEPT_REVIEW], "tool-reviewer"),
            runner_factory=FakeBehavioralRunner,
        )
        self.assertEqual(
            report.conditions,
            (
                "deterministic",
                "single_model",
                "generator_reviewer",
                "generator_reviewer_tool",
            ),
        )

        by_condition = {item.condition: item for item in report.evaluations}
        deterministic = by_condition[WorkflowCondition.DETERMINISTIC]
        single = by_condition[WorkflowCondition.SINGLE_MODEL]
        reviewed = by_condition[WorkflowCondition.GENERATOR_REVIEWER]
        gated = by_condition[WorkflowCondition.GENERATOR_REVIEWER_TOOL]

        self.assertTrue(deterministic.good_rtl_passed)
        self.assertTrue(deterministic.mutation_detected)
        self.assertEqual(deterministic.false_positive_count, 0)

        self.assertFalse(single.good_rtl_passed)
        self.assertTrue(single.mutation_detected)
        self.assertEqual(single.false_positive_count, 1)

        self.assertEqual(reviewed.reviewer_verdict, "REVISE")
        self.assertFalse(reviewed.behavioral_executed)

        self.assertEqual(gated.reviewer_verdict, "ACCEPT_FOR_TOOL_CHECK")
        self.assertTrue(gated.assertion_valid)
        self.assertTrue(gated.good_rtl_passed)
        self.assertTrue(gated.mutation_detected)
        self.assertFalse(gated.usage_available)


if __name__ == "__main__":
    unittest.main()
