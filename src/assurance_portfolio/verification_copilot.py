"""Role-separated verification copilot with traceable, reviewable draft artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Iterable


class GenerationStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    FALLBACK = "FALLBACK"


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
    generation_status: GenerationStatus
    matched_pattern: str | None


@dataclass(frozen=True)
class VerificationArtifact:
    requirement_id: str
    assertion: str
    scenarios: tuple[str, ...]
    coverage_goal: str
    generation_status: GenerationStatus
    matched_pattern: str | None
    requirement_review_findings: tuple[str, ...]
    artifact_review_findings: tuple[str, ...]
    review_findings: tuple[str, ...]


class ArtifactGenerator:
    """Generation role for a small, explicit grammar of reviewable SVA-style drafts."""

    _WITHIN_CYCLES = re.compile(r"within\s+(\d+)\s+cycles?", re.IGNORECASE)
    _BOUNDED_AFTER = re.compile(
        r"(?P<response>[a-z][a-z0-9_]*)\s+(?:must|shall)\s+"
        r"(?:assert|occur|complete)\s+within\s+(?P<cycles>\d+)\s+cycles?\s+"
        r"(?:after|of)\s+(?P<trigger>[a-z][a-z0-9_]*)",
        re.IGNORECASE,
    )
    _NO_LATER_THAN = re.compile(
        r"(?:the\s+)?(?P<response>[a-z][a-z0-9_]*)\s+(?:signal\s+)?"
        r"(?:must|shall)\s+be\s+(?:asserted|completed)\s+no\s+later\s+than\s+"
        r"(?P<cycles>\d+)\s+cycles?\s+(?:after|following)\s+"
        r"(?:the\s+)?(?P<trigger>[a-z][a-z0-9_]*)",
        re.IGNORECASE,
    )
    _IF_BOUNDED = re.compile(
        r"if\s+(?P<trigger>[a-z][a-z0-9_]*)\s*,?\s*(?P<response>[a-z][a-z0-9_]*)\s+"
        r"(?:must|shall)\s+(?:assert|occur|complete)\s+within\s+"
        r"(?P<cycles>\d+)\s+cycles?",
        re.IGNORECASE,
    )
    _PROHIBITION = re.compile(
        r"(?P<signal>[a-z][a-z0-9_]*)\s+(?:must|shall)\s+never\s+assert\s+"
        r"while\s+(?P<condition>[a-z][a-z0-9_]*)",
        re.IGNORECASE,
    )
    _IMPLICATION = re.compile(
        r"if\s+(?P<trigger>[a-z][a-z0-9_]*)\s+(?:is\s+)?(?:high|asserted)\s*,?\s*"
        r"(?P<response>[a-z][a-z0-9_]*)\s+(?:must|shall)\s+(?:be\s+)?(?:high|asserted)",
        re.IGNORECASE,
    )
    _PERSISTENCE = re.compile(
        r"(?P<signal>[a-z][a-z0-9_]*)\s+(?:must|shall)\s+remain\s+asserted\s+"
        r"until\s+(?P<release>[a-z][a-z0-9_]*)",
        re.IGNORECASE,
    )

    @staticmethod
    def _signal(value: str) -> str:
        return re.sub(r"[^a-z0-9_]+", "_", value.lower()).strip("_")

    def _translate(self, normalized: str) -> tuple[str, GenerationStatus, str | None]:
        match = self._BOUNDED_AFTER.search(normalized)
        if match:
            response = self._signal(match.group("response"))
            trigger = self._signal(match.group("trigger"))
            cycles = int(match.group("cycles"))
            return (
                f"assert property (@(posedge clk) {trigger} |-> ##[1:{cycles}] {response});",
                GenerationStatus.SUPPORTED,
                "bounded_response_after",
            )

        match = self._NO_LATER_THAN.search(normalized)
        if match:
            response = self._signal(match.group("response"))
            trigger = self._signal(match.group("trigger"))
            cycles = int(match.group("cycles"))
            return (
                f"assert property (@(posedge clk) {trigger} |-> ##[1:{cycles}] {response});",
                GenerationStatus.SUPPORTED,
                "no_later_than_following",
            )

        match = self._IF_BOUNDED.search(normalized)
        if match:
            response = self._signal(match.group("response"))
            trigger = self._signal(match.group("trigger"))
            cycles = int(match.group("cycles"))
            return (
                f"assert property (@(posedge clk) {trigger} |-> ##[1:{cycles}] {response});",
                GenerationStatus.SUPPORTED,
                "conditional_bounded_response",
            )

        match = self._PROHIBITION.search(normalized)
        if match:
            signal = self._signal(match.group("signal"))
            condition = self._signal(match.group("condition"))
            return (
                f"assert property (@(posedge clk) {condition} |-> !{signal});",
                GenerationStatus.SUPPORTED,
                "prohibition_while_condition",
            )

        match = self._IMPLICATION.search(normalized)
        if match:
            trigger = self._signal(match.group("trigger"))
            response = self._signal(match.group("response"))
            return (
                f"assert property (@(posedge clk) {trigger} |-> {response});",
                GenerationStatus.SUPPORTED,
                "immediate_implication",
            )

        match = self._PERSISTENCE.search(normalized)
        if match:
            signal = self._signal(match.group("signal"))
            release = self._signal(match.group("release"))
            return (
                f"assert property (@(posedge clk) $rose({signal}) |-> {signal} until_with {release});",
                GenerationStatus.SUPPORTED,
                "persistence_until_release",
            )

        slug = re.sub(r"[^a-z0-9]+", "_", normalized.lower()).strip("_")[:48]
        return (
            f"assert property ({slug or 'requirement_holds'}); // FALLBACK: expert review required",
            GenerationStatus.FALLBACK,
            None,
        )

    def generate(self, requirement: Requirement) -> DraftArtifact:
        normalized = re.sub(r"\s+", " ", requirement.text.strip())
        assertion, status, pattern = self._translate(normalized)
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
            assertion=assertion,
            scenarios=(
                "nominal behavior satisfying the requirement",
                boundary,
                violation,
            ),
            coverage_goal=f"cover {requirement.requirement_id}: nominal, boundary, violation",
            generation_status=status,
            matched_pattern=pattern,
        )


class RequirementReviewer:
    """Independent requirement-quality review, separate from generation."""

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


class ArtifactReviewer:
    """Review the generated draft independently from requirement-quality review."""

    def review(self, draft: DraftArtifact) -> tuple[str, ...]:
        findings: list[str] = []
        if draft.generation_status is GenerationStatus.FALLBACK:
            findings.append("Generator used FALLBACK; no supported temporal pattern matched")
        if "expert review required" in draft.assertion.lower():
            findings.append("Assertion requires expert translation before use")
        if draft.generation_status is GenerationStatus.SUPPORTED and not draft.matched_pattern:
            findings.append("Supported assertion is missing pattern provenance")
        return tuple(findings)


class VerificationCopilot:
    """Orchestrate generation, requirement review, and artifact review."""

    def __init__(
        self,
        generator: ArtifactGenerator | None = None,
        requirement_reviewer: RequirementReviewer | None = None,
        artifact_reviewer: ArtifactReviewer | None = None,
    ) -> None:
        self.generator = generator or ArtifactGenerator()
        self.requirement_reviewer = requirement_reviewer or RequirementReviewer()
        self.artifact_reviewer = artifact_reviewer or ArtifactReviewer()

    def propose(self, requirement: Requirement) -> VerificationArtifact:
        draft = self.generator.generate(requirement)
        requirement_findings = self.requirement_reviewer.review(requirement)
        artifact_findings = self.artifact_reviewer.review(draft)
        return VerificationArtifact(
            requirement_id=draft.requirement_id,
            assertion=draft.assertion,
            scenarios=draft.scenarios,
            coverage_goal=draft.coverage_goal,
            generation_status=draft.generation_status,
            matched_pattern=draft.matched_pattern,
            requirement_review_findings=requirement_findings,
            artifact_review_findings=artifact_findings,
            review_findings=requirement_findings + artifact_findings,
        )

    def run(self, requirements: Iterable[Requirement]) -> tuple[VerificationArtifact, ...]:
        return tuple(self.propose(requirement) for requirement in requirements)
