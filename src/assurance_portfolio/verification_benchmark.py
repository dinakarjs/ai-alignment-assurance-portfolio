"""Small deterministic benchmark for verification-artifact defect detection.

This benchmark is intentionally synthetic. It measures whether a candidate
assertion agrees with labelled reference traces for a few compact requirement
families. It does not claim simulator/formal equivalence or production RTL
coverage; it provides a repeatable defect-oriented baseline for comparing
artifact sources before richer EDA-backed evaluation is added.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Sequence


@dataclass(frozen=True)
class TraceCase:
    case_id: str
    signals: tuple[Mapping[str, bool], ...]
    should_pass: bool
    defect: str | None = None


@dataclass(frozen=True)
class BenchmarkCase:
    requirement_id: str
    requirement: str
    reference_assertion: str
    traces: tuple[TraceCase, ...]


@dataclass(frozen=True)
class BenchmarkResult:
    requirement_id: str
    evaluated_cases: int
    correct_cases: int
    defect_detection_total: int
    defects_detected: int
    false_positives: int

    @property
    def accuracy(self) -> float:
        return self.correct_cases / self.evaluated_cases if self.evaluated_cases else 0.0

    @property
    def defect_detection_rate(self) -> float:
        if not self.defect_detection_total:
            return 0.0
        return self.defects_detected / self.defect_detection_total


BENCHMARK_CASES = (
    BenchmarkCase(
        requirement_id="BENCH-BOUND-4",
        requirement="grant shall assert within 4 cycles after request",
        reference_assertion="assert property (@(posedge clk) request |-> ##[1:4] grant);",
        traces=(
            TraceCase(
                "nominal-2",
                (
                    {"request": True, "grant": False},
                    {"request": False, "grant": False},
                    {"request": False, "grant": True},
                ),
                True,
            ),
            TraceCase(
                "boundary-4",
                (
                    {"request": True, "grant": False},
                    {"request": False, "grant": False},
                    {"request": False, "grant": False},
                    {"request": False, "grant": False},
                    {"request": False, "grant": True},
                ),
                True,
            ),
            TraceCase(
                "late-5",
                (
                    {"request": True, "grant": False},
                    {"request": False, "grant": False},
                    {"request": False, "grant": False},
                    {"request": False, "grant": False},
                    {"request": False, "grant": False},
                    {"request": False, "grant": True},
                ),
                False,
                "response-late",
            ),
            TraceCase(
                "missing-response",
                (
                    {"request": True, "grant": False},
                    {"request": False, "grant": False},
                    {"request": False, "grant": False},
                    {"request": False, "grant": False},
                    {"request": False, "grant": False},
                ),
                False,
                "response-missing",
            ),
        ),
    ),
    BenchmarkCase(
        requirement_id="BENCH-PROHIBIT",
        requirement="grant shall never assert while reset",
        reference_assertion="assert property (@(posedge clk) reset |-> !grant);",
        traces=(
            TraceCase(
                "safe-reset",
                ({"reset": True, "grant": False}, {"reset": True, "grant": False}),
                True,
            ),
            TraceCase(
                "inactive-reset",
                ({"reset": False, "grant": True},),
                True,
            ),
            TraceCase(
                "grant-during-reset",
                ({"reset": True, "grant": True},),
                False,
                "prohibited-assertion",
            ),
        ),
    ),
)


def bounded_response_monitor(
    trace: Sequence[Mapping[str, bool]], *, trigger: str, response: str, cycles: int
) -> bool:
    for index, sample in enumerate(trace):
        if not sample.get(trigger, False):
            continue
        end = min(len(trace) - 1, index + cycles)
        if not any(trace[position].get(response, False) for position in range(index + 1, end + 1)):
            return False
    return True


def prohibition_monitor(
    trace: Sequence[Mapping[str, bool]], *, signal: str, condition: str
) -> bool:
    return all(
        not (sample.get(condition, False) and sample.get(signal, False))
        for sample in trace
    )


def evaluate_case(
    case: BenchmarkCase,
    evaluator: Callable[[Sequence[Mapping[str, bool]]], bool],
) -> BenchmarkResult:
    correct = 0
    defect_total = 0
    defects_detected = 0
    false_positives = 0
    for trace_case in case.traces:
        observed = bool(evaluator(trace_case.signals))
        if observed == trace_case.should_pass:
            correct += 1
        if trace_case.defect is not None:
            defect_total += 1
            if not observed:
                defects_detected += 1
        elif not observed:
            false_positives += 1
    return BenchmarkResult(
        requirement_id=case.requirement_id,
        evaluated_cases=len(case.traces),
        correct_cases=correct,
        defect_detection_total=defect_total,
        defects_detected=defects_detected,
        false_positives=false_positives,
    )


def run_reference_benchmark() -> tuple[BenchmarkResult, ...]:
    bounded = BENCHMARK_CASES[0]
    prohibited = BENCHMARK_CASES[1]
    return (
        evaluate_case(
            bounded,
            lambda trace: bounded_response_monitor(
                trace, trigger="request", response="grant", cycles=4
            ),
        ),
        evaluate_case(
            prohibited,
            lambda trace: prohibition_monitor(trace, signal="grant", condition="reset"),
        ),
    )
