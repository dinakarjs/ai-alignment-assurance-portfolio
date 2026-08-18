import unittest

from assurance_portfolio.rtl_behavioral import (
    RTLBehavioralResult,
    RTLBenchmarkReport,
    RTLRunStatus,
)


class RTLBehavioralTests(unittest.TestCase):
    def _result(self, design: str, status: RTLRunStatus, expected_pass: bool) -> RTLBehavioralResult:
        return RTLBehavioralResult(
            design=design,
            status=status,
            expected_pass=expected_pass,
            requirement="grant shall assert within 4 cycles after request",
            simulator="iverilog",
            tool_version="test",
            detail="test fixture",
            output="",
        )

    def test_report_counts_seeded_mutation_detection_without_false_positive(self) -> None:
        report = RTLBenchmarkReport(
            requirement="grant shall assert within 4 cycles after request",
            results=(
                self._result("handshake_good", RTLRunStatus.PASS, True),
                self._result("handshake_late_bug", RTLRunStatus.FAIL, False),
            ),
        )
        self.assertTrue(report.all_expectations_met)
        self.assertEqual(report.mutation_detection_rate, 1.0)
        self.assertEqual(report.false_positive_count, 0)

    def test_report_rejects_tool_failure_as_successful_mutation_detection(self) -> None:
        report = RTLBenchmarkReport(
            requirement="grant shall assert within 4 cycles after request",
            results=(
                self._result("handshake_good", RTLRunStatus.PASS, True),
                self._result("handshake_late_bug", RTLRunStatus.COMPILE_ERROR, False),
            ),
        )
        self.assertFalse(report.all_expectations_met)
        self.assertEqual(report.mutation_detection_rate, 0.0)


if __name__ == "__main__":
    unittest.main()
