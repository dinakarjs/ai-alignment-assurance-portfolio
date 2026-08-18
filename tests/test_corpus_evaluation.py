import json
import unittest

from assurance_portfolio.agentic_verification import ScriptedModelBackend
from assurance_portfolio.corpus_benchmark import (
    AssertionFamily,
    CorpusAssertionResult,
    CorpusRunStatus,
    default_corpus,
    parse_assertion,
)
from assurance_portfolio.corpus_evaluation import run_corpus_trial, summarize_trials
from assurance_portfolio.verification_copilot import ArtifactGenerator, Requirement


class FakeCorpusRunner:
    def evaluate(self, case, assertion, rtl_root="benchmarks/rtl"):
        del rtl_root
        parsed = parse_assertion(assertion)
        if parsed is None or parsed.family is not case.family:
            return CorpusAssertionResult(
                case.case_id,
                case.family,
                assertion,
                CorpusRunStatus.INVALID_ASSERTION,
                None,
                None,
                None,
                None,
                "invalid assertion",
            )
        if case.case_id == "BR-001" and parsed.cycles == 2:
            return CorpusAssertionResult(
                case.case_id,
                case.family,
                assertion,
                CorpusRunStatus.FAIL,
                False,
                True,
                1,
                "fake",
                "too strict: false positive on good RTL",
            )
        return CorpusAssertionResult(
            case.case_id,
            case.family,
            assertion,
            CorpusRunStatus.PASS,
            True,
            True,
            0,
            "fake",
            "good passes; mutation detected",
        )


def draft_json(case, strict=False):
    assertion = ArtifactGenerator().generate(Requirement(case.case_id, case.requirement)).assertion
    if strict and case.case_id == "BR-001":
        assertion = "assert property (@(posedge clk) request |-> ##[1:2] grant);"
    return json.dumps(
        {
            "assertion": assertion,
            "scenarios": ["nominal", "boundary", "violation"],
            "coverage_goal": "exercise good and mutated RTL",
            "assumptions": ["benchmark fixture"],
            "rationale": "scripted test candidate",
        }
    )


def review_json(case, revise=False):
    if revise and case.case_id == "BR-001":
        return json.dumps(
            {
                "verdict": "REVISE",
                "findings": ["timing too strict"],
                "recommended_action": "revise bound",
            }
        )
    return json.dumps(
        {
            "verdict": "ACCEPT_FOR_TOOL_CHECK",
            "findings": [],
            "recommended_action": "run tool",
        }
    )


class CorpusBenchmarkTests(unittest.TestCase):
    def test_parser_covers_three_families(self):
        bounded = parse_assertion(
            "assert property (@(posedge clk) request |-> ##[1:4] grant);"
        )
        prohibition = parse_assertion(
            "assert property (@(posedge clk) reset |-> !grant);"
        )
        implication = parse_assertion(
            "assert property (@(posedge clk) request |-> busy);"
        )
        self.assertEqual(bounded.family, AssertionFamily.BOUNDED_RESPONSE)
        self.assertEqual(bounded.cycles, 4)
        self.assertEqual(prohibition.family, AssertionFamily.PROHIBITION)
        self.assertEqual(implication.family, AssertionFamily.IMMEDIATE_IMPLICATION)

    def test_default_corpus_has_three_requirement_families(self):
        corpus = default_corpus()
        self.assertEqual(len(corpus), 3)
        self.assertEqual({case.family for case in corpus}, set(AssertionFamily))

    def test_repeated_summary_tracks_false_positive_and_escalation(self):
        trials = []
        for trial_id in (1, 2):
            trials.append(
                run_corpus_trial(
                    trial_id,
                    single_backend_factory=lambda case: ScriptedModelBackend(
                        [draft_json(case, strict=True)], "single"
                    ),
                    reviewed_generator_factory=lambda case: ScriptedModelBackend(
                        [draft_json(case, strict=True)], "reviewed-generator"
                    ),
                    reviewer_factory=lambda case: ScriptedModelBackend(
                        [review_json(case, revise=True)], "reviewer"
                    ),
                    tool_generator_factory=lambda case: ScriptedModelBackend(
                        [draft_json(case)], "tool-generator"
                    ),
                    tool_reviewer_factory=lambda case: ScriptedModelBackend(
                        [review_json(case)], "tool-reviewer"
                    ),
                    corpus=default_corpus(),
                    runner_factory=FakeCorpusRunner,
                    evidence_kind="scripted_offline",
                    model_label="scripted-fixtures",
                    prompt_version="v8.0",
                )
            )

        summary = summarize_trials(tuple(trials))
        by_condition = {item.condition: item for item in summary.aggregates}

        self.assertEqual(summary.trials, 2)
        self.assertEqual(summary.cases_per_trial, 3)
        self.assertEqual(by_condition["deterministic"].full_correct_rate, 1.0)
        self.assertAlmostEqual(by_condition["single_model"].full_correct_rate, 2 / 3)
        self.assertAlmostEqual(by_condition["single_model"].false_positive_rate, 1 / 3)
        self.assertAlmostEqual(by_condition["generator_reviewer"].escalation_rate, 1 / 3)
        self.assertAlmostEqual(
            by_condition["generator_reviewer"].behavioral_execution_rate, 2 / 3
        )
        self.assertEqual(by_condition["generator_reviewer_tool"].full_correct_rate, 1.0)

    def test_mixed_evidence_kinds_are_not_aggregated(self):
        base_kwargs = dict(
            single_backend_factory=lambda case: ScriptedModelBackend([draft_json(case)], "s"),
            reviewed_generator_factory=lambda case: ScriptedModelBackend([draft_json(case)], "rg"),
            reviewer_factory=lambda case: ScriptedModelBackend([review_json(case)], "r"),
            tool_generator_factory=lambda case: ScriptedModelBackend([draft_json(case)], "tg"),
            tool_reviewer_factory=lambda case: ScriptedModelBackend([review_json(case)], "tr"),
            corpus=default_corpus(),
            runner_factory=FakeCorpusRunner,
            model_label="same",
            prompt_version="v8.0",
        )
        one = run_corpus_trial(1, evidence_kind="scripted_offline", **base_kwargs)
        two = run_corpus_trial(2, evidence_kind="live_model", **base_kwargs)
        with self.assertRaises(ValueError):
            summarize_trials((one, two))


if __name__ == "__main__":
    unittest.main()
