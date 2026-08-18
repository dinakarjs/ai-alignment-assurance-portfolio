"""Role-separated verification copilot prototype with traceable draft artifacts."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable


@dataclass(frozen=True)
class Requirement:
    requirement_id: str
    text: str


@dataclass(frozen=True)
class DraftArtifact:
    requirement_id: str
    assertion: str
    scenarios: tuple[str, ...]
    coverage_goal: str


@dataclass(frozen=True)
class VerificationArtifact:
    requirement_id: str
    assertion: str
    scenarios: tuple[str, ...]
    coverage_goal: str
    review_findings: tuple[str, ...]


class ArtifactGenerator:
    """Generation role: translate a requirement into reviewable draft artifacts."""

    _WITHIN_CYCLES = re.compile(r"within\s+(\d+)\s+cycles?", re.IGNORECASE)
    _AFTER = re.compile(
        r"(?P<response>[a-z][a-z0-9_]*)\s+(?:must|shall)\s+(?:assert|occur|complete)\s+"
        r"within\s+(?P<cycles>\d+)\s+cycles?\s+(?:after|of)\s+"
        r"(?P<trigger>[a-z][a-z0-9_]*)",
        re.IGNORECASE,
    )

    @staticmethod
    def _signal(value: str) -> str:
        return re.sub(r"[^a-z0-9_]+", "_", value.lower()).strip("_")

    def _draft_assertion(self, normalized: str) -> str:
        match = self._AFTER.search(normalized)
        if match:
            response = self._signal(match.group("response"))
            trigger = self._signal(match.group("trigger"))
            cycles = int(match.group("cycles"))
            return (
                f"assert property (@(posedge clk) {trigger} |-> ##[1:{cycles}] "
                f"{response});"
            )

        slug = re.sub(r"[^a-z0-9]+", "_", normalized.lower()).strip("_")[:48]
        return f"assert property ({slug or 'requirement_holds'}); // draft: expert review required"

    def generate(self, requirement: Requirement) -> DraftArtifact:
        normalized = re.sub(r"\s+", " ", requirement.text.strip())
        timing = self._WITHIN_CYCLES.search(normalized)
        if timing:
            cycles = timing.group(1)
            boundary = f"response occurs exactly at the {cycles}-cycle boundary"
            violation = f"response occurs later than {cycles} cycles"
        else:
            boundary = "boundary condition at the stated requirement limit"
            violation = "adversarial input that violates the requirement"

        return DraftArtifact(
            requirement_id=requirement.requirement_id,
            assertion=self._draft_assertion(normalized),
            scenarios=(
                "nominal behavior satisfying the requirement",
                boundary,
                violation,
            ),
            coverage_goal=(
                f"cover {requirement.requirement_id}: nominal, boundary, violation"
            ),
        )


class RequirementReviewer:
    """Independent review role: inspect requirement quality without generating artifacts."""

    def review(self, requirement: Requirement) -> tuple[str, ...]:
        normalized = re.sub(r"\s+", " ", requirement.text.strip())
        lower = normalized.lower()
        findings: list[str] = []

        if not any(word in lower for word in ("must", "shall", "never", "within")):
            findings.append("Requirement lacks a clear normative term")
        if "within" in lower and not re.search(r"within\s+\d+", lower):
            findings.append("Timing bound is not numeric")
        if any(word in lower for word in ("appropriate", "quickly", "secure", "soon")):
            findings.append("Requirement contains an ambiguous adjective")
        return tuple(findings)


class VerificationCopilot:
    """Orchestrate generation and independent review while preserving traceability."""

    def __init__(
        self,
        generator: ArtifactGenerator | None = None,
        reviewer: RequirementReviewer | None = None,
    ) -> None:
        self.generator = generator or ArtifactGenerator()
        self.reviewer = reviewer or RequirementReviewer()

    def propose(self, requirement: Requirement) -> VerificationArtifact:
        draft = self.generator.generate(requirement)
        findings = self.reviewer.review(requirement)
        return VerificationArtifact(
            requirement_id=draft.requirement_id,
            assertion=draft.assertion,
            scenarios=draft.scenarios,
            coverage_goal=draft.coverage_goal,
            review_findings=findings,
        )

    def run(self, requirements: Iterable[Requirement]) -> tuple[VerificationArtifact, ...]:
        return tuple(self.propose(requirement) for requirement in requirements)
