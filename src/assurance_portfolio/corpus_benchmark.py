"""Multi-family RTL benchmark corpus for V8 controlled evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


class AssertionFamily(str, Enum):
    BOUNDED_RESPONSE = "bounded_response"
    PROHIBITION = "prohibition"
    IMMEDIATE_IMPLICATION = "immediate_implication"


class CorpusRunStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    INVALID_ASSERTION = "INVALID_ASSERTION"
    TOOL_ERROR = "TOOL_ERROR"
    TOOL_UNAVAILABLE = "TOOL_UNAVAILABLE"


@dataclass(frozen=True)
class ParsedAssertion:
    family: AssertionFamily
    trigger: str
    response: str
    cycles: int | None = None


@dataclass(frozen=True)
class CorpusCase:
    case_id: str
    family: AssertionFamily
    requirement: str
    good_module: str
    good_file: str
    mutation_module: str
    mutation_file: str
    expected_signals: tuple[str, str]


@dataclass(frozen=True)
class CorpusAssertionResult:
    case_id: str
    family: AssertionFamily
    assertion: str
    status: CorpusRunStatus
    good_rtl_passed: bool | None
    mutation_detected: bool | None
    false_positive_count: int | None
    tool_version: str | None
    detail: str

    @property
    def fully_correct(self) -> bool:
        return self.good_rtl_passed is True and self.mutation_detected is True


_BOUNDED = re.compile(
    r"^assert\s+property\s*\(\s*@\(posedge\s+clk\)\s+"
    r"(?P<trigger>[A-Za-z_][A-Za-z0-9_]*)\s*\|->\s*##\[1:(?P<cycles>\d+)\]\s*"
    r"(?P<response>[A-Za-z_][A-Za-z0-9_]*)\s*\)\s*;\s*$"
)
_PROHIBITION = re.compile(
    r"^assert\s+property\s*\(\s*@\(posedge\s+clk\)\s+"
    r"(?P<trigger>[A-Za-z_][A-Za-z0-9_]*)\s*\|->\s*!\s*(?P<response>[A-Za-z_][A-Za-z0-9_]*)\s*\)\s*;\s*$"
)
_IMPLICATION = re.compile(
    r"^assert\s+property\s*\(\s*@\(posedge\s+clk\)\s+"
    r"(?P<trigger>[A-Za-z_][A-Za-z0-9_]*)\s*\|->\s*(?P<response>[A-Za-z_][A-Za-z0-9_]*)\s*\)\s*;\s*$"
)


def parse_assertion(assertion: str) -> ParsedAssertion | None:
    text = assertion.strip()
    match = _BOUNDED.fullmatch(text)
    if match:
        return ParsedAssertion(
            AssertionFamily.BOUNDED_RESPONSE,
            match.group("trigger"),
            match.group("response"),
            int(match.group("cycles")),
        )
    match = _PROHIBITION.fullmatch(text)
    if match:
        return ParsedAssertion(
            AssertionFamily.PROHIBITION,
            match.group("trigger"),
            match.group("response"),
        )
    match = _IMPLICATION.fullmatch(text)
    if match:
        return ParsedAssertion(
            AssertionFamily.IMMEDIATE_IMPLICATION,
            match.group("trigger"),
            match.group("response"),
        )
    return None


def default_corpus() -> tuple[CorpusCase, ...]:
    return (
        CorpusCase(
            case_id="BR-001",
            family=AssertionFamily.BOUNDED_RESPONSE,
            requirement="grant shall assert within 4 cycles after request",
            good_module="handshake_good",
            good_file="handshake_good.sv",
            mutation_module="handshake_late_bug",
            mutation_file="handshake_late_bug.sv",
            expected_signals=("request", "grant"),
        ),
        CorpusCase(
            case_id="PR-001",
            family=AssertionFamily.PROHIBITION,
            requirement="grant shall never assert while reset",
            good_module="prohibition_good",
            good_file="prohibition_good.sv",
            mutation_module="prohibition_bug",
            mutation_file="prohibition_bug.sv",
            expected_signals=("reset", "grant"),
        ),
        CorpusCase(
            case_id="IM-001",
            family=AssertionFamily.IMMEDIATE_IMPLICATION,
            requirement="if request is high, busy shall be high",
            good_module="implication_good",
            good_file="implication_good.sv",
            mutation_module="implication_bug",
            mutation_file="implication_bug.sv",
            expected_signals=("request", "busy"),
        ),
    )


class IcarusCorpusRunner:
    name = "iverilog"

    def __init__(self, executable: str = "iverilog", runtime: str = "vvp", timeout_seconds: int = 20) -> None:
        self.executable = executable
        self.runtime = runtime
        self.timeout_seconds = timeout_seconds

    def _tool_paths(self) -> tuple[str | None, str | None]:
        return shutil.which(self.executable), shutil.which(self.runtime)

    def _version(self, compiler: str) -> str | None:
        try:
            result = subprocess.run([compiler, "-V"], check=False, capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.SubprocessError):
            return None
        output = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
        return output.splitlines()[0] if output else None

    @staticmethod
    def _bounded_tb(module_name: str, cycles: int) -> str:
        return f"""`timescale 1ns/1ps
module assurance_tb;
  logic clk=0, rst_n=0, request=0;
  logic grant;
  integer i; integer seen;
  {module_name} dut(.clk(clk), .rst_n(rst_n), .request(request), .grant(grant));
  always #5 clk=~clk;
  initial begin
    seen=0;
    repeat(2) @(posedge clk);
    @(negedge clk); rst_n=1;
    @(negedge clk); request=1;
    @(negedge clk); request=0;
    for(i=1;i<={cycles};i=i+1) begin @(posedge clk); #1; if(grant) seen=1; end
    if(!seen) begin $display("ASSURANCE_FAIL"); $fatal(1, "late grant"); end
    $display("ASSURANCE_PASS"); $finish;
  end
endmodule
"""

    @staticmethod
    def _prohibition_tb(module_name: str) -> str:
        return f"""`timescale 1ns/1ps
module assurance_tb;
  logic clk=0, rst_n=1, enable=0;
  logic grant;
  {module_name} dut(.clk(clk), .rst_n(rst_n), .enable(enable), .grant(grant));
  always #5 clk=~clk;
  initial begin
    @(negedge clk); rst_n=0;
    @(posedge clk); #1;
    if(grant) begin $display("ASSURANCE_FAIL"); $fatal(1, "grant asserted during reset"); end
    $display("ASSURANCE_PASS"); $finish;
  end
endmodule
"""

    @staticmethod
    def _implication_tb(module_name: str) -> str:
        return f"""`timescale 1ns/1ps
module assurance_tb;
  logic clk=0, request=0;
  logic busy;
  {module_name} dut(.request(request), .busy(busy));
  always #5 clk=~clk;
  initial begin
    @(negedge clk); request=1;
    @(posedge clk); #1;
    if(!busy) begin $display("ASSURANCE_FAIL"); $fatal(1, "request did not imply busy"); end
    $display("ASSURANCE_PASS"); $finish;
  end
endmodule
"""

    def _tb(self, parsed: ParsedAssertion, module_name: str) -> str:
        if parsed.family is AssertionFamily.BOUNDED_RESPONSE:
            return self._bounded_tb(module_name, parsed.cycles or 0)
        if parsed.family is AssertionFamily.PROHIBITION:
            return self._prohibition_tb(module_name)
        return self._implication_tb(module_name)

    def _simulate(self, source: Path, module_name: str, parsed: ParsedAssertion) -> tuple[CorpusRunStatus, str, str | None]:
        compiler, runtime = self._tool_paths()
        if compiler is None or runtime is None:
            return CorpusRunStatus.TOOL_UNAVAILABLE, "Icarus Verilog not available", None
        version = self._version(compiler)
        with tempfile.TemporaryDirectory(prefix="assurance-corpus-") as temp_dir:
            temp = Path(temp_dir)
            tb = temp / "assurance_tb.sv"
            binary = temp / "sim.out"
            tb.write_text(self._tb(parsed, module_name), encoding="utf-8")
            try:
                comp = subprocess.run(
                    [compiler, "-g2012", "-s", "assurance_tb", "-o", str(binary), str(source), str(tb)],
                    check=False, capture_output=True, text=True, timeout=self.timeout_seconds,
                )
            except subprocess.TimeoutExpired:
                return CorpusRunStatus.TOOL_ERROR, "compile timeout", version
            if comp.returncode != 0:
                output = "\n".join(part for part in (comp.stdout, comp.stderr) if part).strip()
                return CorpusRunStatus.TOOL_ERROR, output[-2000:] or "compile failed", version
            try:
                sim = subprocess.run([runtime, str(binary)], check=False, capture_output=True, text=True, timeout=self.timeout_seconds)
            except subprocess.TimeoutExpired:
                return CorpusRunStatus.TOOL_ERROR, "simulation timeout", version
        output = "\n".join(part for part in (sim.stdout, sim.stderr) if part).strip()
        if sim.returncode == 0 and "ASSURANCE_PASS" in output:
            return CorpusRunStatus.PASS, output[-2000:], version
        return CorpusRunStatus.FAIL, output[-2000:] or "behavioral monitor failed", version

    def evaluate(self, case: CorpusCase, assertion: str, rtl_root: str | Path = "benchmarks/rtl") -> CorpusAssertionResult:
        parsed = parse_assertion(assertion)
        if parsed is None:
            return CorpusAssertionResult(
                case.case_id, case.family, assertion, CorpusRunStatus.INVALID_ASSERTION,
                None, None, None, None, "candidate is outside the supported corpus assertion grammar",
            )
        if parsed.family is not case.family:
            return CorpusAssertionResult(
                case.case_id, case.family, assertion, CorpusRunStatus.INVALID_ASSERTION,
                None, None, None, None, f"candidate family {parsed.family.value} does not match case {case.family.value}",
            )
        if (parsed.trigger, parsed.response) != case.expected_signals:
            return CorpusAssertionResult(
                case.case_id, case.family, assertion, CorpusRunStatus.INVALID_ASSERTION,
                None, None, None, None, "candidate signal mapping does not match the benchmark fixture",
            )

        root = Path(rtl_root)
        good_status, good_detail, version = self._simulate(root / case.good_file, case.good_module, parsed)
        mutation_status, mutation_detail, mutation_version = self._simulate(
            root / case.mutation_file, case.mutation_module, parsed
        )
        version = version or mutation_version
        if good_status in {CorpusRunStatus.TOOL_ERROR, CorpusRunStatus.TOOL_UNAVAILABLE}:
            return CorpusAssertionResult(
                case.case_id, case.family, assertion, good_status,
                None, None, None, version, f"good RTL execution failed: {good_detail}",
            )
        if mutation_status in {CorpusRunStatus.TOOL_ERROR, CorpusRunStatus.TOOL_UNAVAILABLE}:
            return CorpusAssertionResult(
                case.case_id, case.family, assertion, mutation_status,
                good_status is CorpusRunStatus.PASS, None, None, version,
                f"mutation RTL execution failed: {mutation_detail}",
            )

        good_passed = good_status is CorpusRunStatus.PASS
        mutation_detected = mutation_status is CorpusRunStatus.FAIL
        return CorpusAssertionResult(
            case.case_id,
            case.family,
            assertion,
            CorpusRunStatus.PASS if good_passed and mutation_detected else CorpusRunStatus.FAIL,
            good_passed,
            mutation_detected,
            0 if good_passed else 1,
            version,
            f"good={good_status.value}; mutation={mutation_status.value}",
        )
