"""Behavioral RTL benchmark using an external SystemVerilog simulator.

V6 uses Icarus Verilog to execute a bounded request/grant requirement against
both an intended implementation and a seeded late-grant mutation. This is
runtime behavioral evidence, distinct from the Verilator syntax/lint check used
for standalone assertion drafts.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import shutil
import subprocess
import tempfile


class RTLRunStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    COMPILE_ERROR = "COMPILE_ERROR"
    TOOL_UNAVAILABLE = "TOOL_UNAVAILABLE"


@dataclass(frozen=True)
class RTLBehavioralResult:
    design: str
    status: RTLRunStatus
    expected_pass: bool
    requirement: str
    simulator: str
    tool_version: str | None
    detail: str
    output: str

    @property
    def expectation_met(self) -> bool:
        if self.expected_pass:
            return self.status is RTLRunStatus.PASS
        return self.status is RTLRunStatus.FAIL


@dataclass(frozen=True)
class RTLBenchmarkReport:
    requirement: str
    results: tuple[RTLBehavioralResult, ...]

    @property
    def mutation_detection_rate(self) -> float:
        mutations = [item for item in self.results if not item.expected_pass]
        if not mutations:
            return 0.0
        detected = sum(item.status is RTLRunStatus.FAIL for item in mutations)
        return detected / len(mutations)

    @property
    def false_positive_count(self) -> int:
        return sum(
            item.status is RTLRunStatus.FAIL
            for item in self.results
            if item.expected_pass
        )

    @property
    def all_expectations_met(self) -> bool:
        return bool(self.results) and all(item.expectation_met for item in self.results)


class IcarusBehavioralRunner:
    """Compile and simulate a simple bounded request/grant temporal monitor."""

    name = "iverilog"

    def __init__(
        self,
        executable: str = "iverilog",
        runtime: str = "vvp",
        timeout_seconds: int = 20,
    ) -> None:
        self.executable = executable
        self.runtime = runtime
        self.timeout_seconds = timeout_seconds

    def _version(self, executable: str) -> str | None:
        try:
            result = subprocess.run(
                [executable, "-V"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        text = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
        return text.splitlines()[0] if text else None

    @staticmethod
    def _testbench(module_name: str, max_cycles: int) -> str:
        return f"""`timescale 1ns/1ps
module assurance_tb;
  logic clk = 1'b0;
  logic rst_n = 1'b0;
  logic request = 1'b0;
  logic grant;
  integer i;
  integer seen;
  integer latency;

  {module_name} dut (
    .clk(clk),
    .rst_n(rst_n),
    .request(request),
    .grant(grant)
  );

  always #5 clk = ~clk;

  initial begin
    seen = 0;
    latency = -1;

    repeat (2) @(posedge clk);
    @(negedge clk);
    rst_n = 1'b1;

    @(negedge clk);
    request = 1'b1;
    @(negedge clk);
    request = 1'b0;

    for (i = 1; i <= {max_cycles}; i = i + 1) begin
      @(posedge clk);
      #1;
      if (grant && !seen) begin
        seen = 1;
        latency = i;
      end
    end

    if (!seen) begin
      $display("ASSURANCE_RTL_FAIL reason=grant_late bound={max_cycles}");
      $fatal(1, "grant did not assert within {max_cycles} cycles after request");
    end

    $display("ASSURANCE_RTL_PASS latency=%0d bound={max_cycles}", latency);
    $finish;
  end
endmodule
"""

    def run(
        self,
        *,
        source: Path,
        module_name: str,
        expected_pass: bool,
        max_cycles: int = 4,
    ) -> RTLBehavioralResult:
        requirement = f"grant shall assert within {max_cycles} cycles after request"
        compiler = shutil.which(self.executable)
        runtime = shutil.which(self.runtime)
        if compiler is None or runtime is None:
            missing = [
                name
                for name, resolved in ((self.executable, compiler), (self.runtime, runtime))
                if resolved is None
            ]
            return RTLBehavioralResult(
                design=module_name,
                status=RTLRunStatus.TOOL_UNAVAILABLE,
                expected_pass=expected_pass,
                requirement=requirement,
                simulator=self.name,
                tool_version=None,
                detail=f"missing tool(s) on PATH: {', '.join(missing)}",
                output="",
            )

        version = self._version(compiler)
        with tempfile.TemporaryDirectory(prefix="assurance-rtl-") as temp_dir:
            temp = Path(temp_dir)
            testbench = temp / "assurance_tb.sv"
            binary = temp / "simulation.out"
            testbench.write_text(
                self._testbench(module_name, max_cycles), encoding="utf-8"
            )

            try:
                compile_result = subprocess.run(
                    [
                        compiler,
                        "-g2012",
                        "-s",
                        "assurance_tb",
                        "-o",
                        str(binary),
                        str(source),
                        str(testbench),
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                )
            except subprocess.TimeoutExpired:
                return RTLBehavioralResult(
                    design=module_name,
                    status=RTLRunStatus.COMPILE_ERROR,
                    expected_pass=expected_pass,
                    requirement=requirement,
                    simulator=self.name,
                    tool_version=version,
                    detail="RTL compilation timed out",
                    output="",
                )

            compile_output = "\n".join(
                part for part in (compile_result.stdout, compile_result.stderr) if part
            ).strip()
            if compile_result.returncode != 0:
                return RTLBehavioralResult(
                    design=module_name,
                    status=RTLRunStatus.COMPILE_ERROR,
                    expected_pass=expected_pass,
                    requirement=requirement,
                    simulator=self.name,
                    tool_version=version,
                    detail=f"iverilog exited {compile_result.returncode}",
                    output=compile_output[-4000:],
                )

            try:
                simulation = subprocess.run(
                    [runtime, str(binary)],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                )
            except subprocess.TimeoutExpired:
                return RTLBehavioralResult(
                    design=module_name,
                    status=RTLRunStatus.FAIL,
                    expected_pass=expected_pass,
                    requirement=requirement,
                    simulator=self.name,
                    tool_version=version,
                    detail="simulation timed out",
                    output=compile_output,
                )

        simulation_output = "\n".join(
            part for part in (simulation.stdout, simulation.stderr) if part
        ).strip()
        combined = "\n".join(part for part in (compile_output, simulation_output) if part)
        passed = simulation.returncode == 0 and "ASSURANCE_RTL_PASS" in simulation_output
        status = RTLRunStatus.PASS if passed else RTLRunStatus.FAIL
        detail = (
            "bounded-response monitor passed"
            if passed
            else "bounded-response monitor detected a behavioral violation"
        )
        return RTLBehavioralResult(
            design=module_name,
            status=status,
            expected_pass=expected_pass,
            requirement=requirement,
            simulator=self.name,
            tool_version=version,
            detail=detail,
            output=combined[-4000:],
        )


def run_handshake_rtl_benchmark(
    rtl_root: str | Path = "benchmarks/rtl",
    *,
    runner: IcarusBehavioralRunner | None = None,
) -> RTLBenchmarkReport:
    root = Path(rtl_root)
    active_runner = runner or IcarusBehavioralRunner()
    cases = (
        ("handshake_good", root / "handshake_good.sv", True),
        ("handshake_late_bug", root / "handshake_late_bug.sv", False),
    )
    results = tuple(
        active_runner.run(
            source=source,
            module_name=module,
            expected_pass=expected,
            max_cycles=4,
        )
        for module, source, expected in cases
    )
    return RTLBenchmarkReport(
        requirement="grant shall assert within 4 cycles after request",
        results=results,
    )
