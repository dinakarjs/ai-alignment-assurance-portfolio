"""Minimal role-separated verification copilot prototype."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable


@dataclass(frozen=True)
class Requirement:
    requirement_id: str
    text: str


@dataclass(frozen=True)
class VerificationArtifact:
    requirement_id: str
    assertion: str
    scenarios: tuple[str, ...]
    coverage_goal: str
    review_findings: tuple[str, ...]


class VerificationCopilot:
    """Generate traceable draft artifacts and review them independently."""

    def propose(self, requirement: Requirement) -> VerificationArtifact:
        normalized = re.sub(r"\s+", " ", requirement.text.strip())
        lower = normalized.lower()
        findings: list[str] = []

        if not any(word in lower for word in ("must", "shall", "never", "within")):
            findings.append("Requirement lacks a clear normative term")
        if "within" in lower and not re.search(r"within\s+\d+", lower):
            findings.append("Timing bound is not numeric")
        if any(word in lower for word in ("appropriate", "quickly", "secure")):
            findings.append("Requirement contains an ambiguous adjective")

        slug = re.sub(r"[^a-z0-9]+", "_", lower).strip("_")[:48]
        assertion = f"assert property ({slug or 'requirement_holds'});"
        scenarios = (
            "nominal behavior",
            "boundary condition",
            "adversarial or conflicting input",
        )
        coverage = f"cover {requirement.requirement_id}: nominal, boundary, violation"
        return VerificationArtifact(
            requirement_id=requirement.requirement_id,
            assertion=assertion,
            scenarios=scenarios,
            coverage_goal=coverage,
            review_findings=tuple(findings),
        )

    def run(self, requirements: Iterable[Requirement]) -> tuple[VerificationArtifact, ...]:
        return tuple(self.propose(requirement) for requirement in requirements)

