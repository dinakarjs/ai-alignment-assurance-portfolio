"""SystemVerilog assertion validation adapters.

The structural validator is dependency-free and intentionally shallow. The
Verilator adapter performs real tool parsing/linting when Verilator is present,
but Verilator has partial SVA support; a VALID result therefore means accepted
by that concrete tool/version, not universal IEEE SystemVerilog correctness.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


class ValidationStatus(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class SVAValidationResult:
    status: ValidationStatus
    validator: str
    detail: str
    tool_version: str | None = None

    @property
    def valid(self) -> bool:
        return self.status is ValidationStatus.VALID


class StructuralSVAValidator:
    """Catch obvious malformed assertion drafts without claiming SVA parsing."""

    name = "structural"

    def validate(self, assertion: str) -> SVAValidationResult:
        text = assertion.strip()
        findings: list[str] = []
        if not text.startswith("assert property"):
            findings.append("missing 'assert property' prefix")
        if not text.endswith(";"):
            findings.append("missing terminating semicolon")
        if text.count("(") != text.count(")"):
            findings.append("unbalanced parentheses")
        if "FALLBACK" in text or "expert review required" in text.lower():
            findings.append("fallback placeholder is not executable evidence")
        if findings:
            return SVAValidationResult(
                ValidationStatus.INVALID,
                self.name,
                "; ".join(findings),
            )
        return SVAValidationResult(
            ValidationStatus.VALID,
            self.name,
            "basic assertion structure accepted",
        )


class VerilatorSVAValidator:
    """Validate a standalone assertion with the installed Verilator executable."""

    name = "verilator"
    _TOKEN = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")
    _RESERVED = {
        "assert",
        "property",
        "posedge",
        "negedge",
        "or",
        "and",
        "not",
        "until",
        "until_with",
        "throughout",
        "first_match",
        "disable",
        "iff",
        "if",
        "else",
        "begin",
        "end",
        "true",
        "false",
        "clk",
        "rose",
        "fell",
        "stable",
        "past",
        "changed",
    }

    def __init__(self, executable: str = "verilator", timeout_seconds: int = 20) -> None:
        self.executable = executable
        self.timeout_seconds = timeout_seconds

    def _version(self, executable: str) -> str | None:
        try:
            result = subprocess.run(
                [executable, "--version"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return (result.stdout or result.stderr).strip() or None

    def _signals(self, assertion: str) -> tuple[str, ...]:
        cleaned = re.sub(r"\$([A-Za-z_][A-Za-z0-9_]*)", r"\1", assertion)
        signals = {
            token
            for token in self._TOKEN.findall(cleaned)
            if token.lower() not in self._RESERVED and not token.isupper()
        }
        return tuple(sorted(signals))

    def _probe_source(self, assertion: str) -> str:
        declarations = "\n".join(
            f"  logic {signal};" for signal in self._signals(assertion)
        )
        return (
            "module assurance_sva_probe;\n"
            "  logic clk;\n"
            f"{declarations}\n"
            f"  {assertion.strip()}\n"
            "endmodule\n"
        )

    def validate(self, assertion: str) -> SVAValidationResult:
        structural = StructuralSVAValidator().validate(assertion)
        if not structural.valid:
            return SVAValidationResult(
                ValidationStatus.INVALID,
                self.name,
                f"structural precheck failed: {structural.detail}",
            )

        executable = shutil.which(self.executable)
        if executable is None:
            return SVAValidationResult(
                ValidationStatus.UNAVAILABLE,
                self.name,
                f"{self.executable!r} was not found on PATH",
            )

        version = self._version(executable)
        with tempfile.TemporaryDirectory(prefix="assurance-sva-") as temp_dir:
            source = Path(temp_dir) / "probe.sv"
            source.write_text(self._probe_source(assertion), encoding="utf-8")
            try:
                result = subprocess.run(
                    [
                        executable,
                        "--lint-only",
                        "--sv",
                        "--timing",
                        "--assert",
                        "-Wno-fatal",
                        str(source),
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                )
            except subprocess.TimeoutExpired:
                return SVAValidationResult(
                    ValidationStatus.INVALID,
                    self.name,
                    "Verilator validation timed out",
                    version,
                )
            except OSError as exc:
                return SVAValidationResult(
                    ValidationStatus.UNAVAILABLE,
                    self.name,
                    f"could not execute Verilator: {exc}",
                    version,
                )

        output = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
        if result.returncode != 0:
            detail = output[-2000:] if output else f"Verilator exited {result.returncode}"
            return SVAValidationResult(
                ValidationStatus.INVALID,
                self.name,
                detail,
                version,
            )
        return SVAValidationResult(
            ValidationStatus.VALID,
            self.name,
            "assertion accepted by Verilator lint",
            version,
        )
