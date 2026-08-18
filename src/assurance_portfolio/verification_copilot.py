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
class TranslationResult:
    assertion: str
    generation_status: GenerationStatus
    matched_pattern: str | None
    parameters: tuple[tuple[str, str], ...] = ()

    def parameter(self, name: str) -> str | None:
        return dict(self.parameters).get(name)


@dataclass(frozen=True)
class DraftArtifact:
    requirement_id: str
    assertion: str
    scenarios: tuple[str, ...]
    coverage_goal: str
    generation_status: GenerationStatus
    matched_pattern: str | None
    translation_parameters: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class VerificationArtifact:
    requirement_id: str
    assertion: str
    scenarios: tuple[str, ...]
    coverage_goal: str
    generation_status: GenerationStatus
    matched_pattern: str | None
    translation_parameters: tuple[tuple[str, str], ...]
    requirement_review_findings: tuple[str, ...]
    artifact_review_findings: tuple[str, ...]
    review_findings: tuple[str, ...]


class ArtifactGenerator:
    """Generation role for a small, explicit grammar of reviewable SVA-style drafts.

    A requirement is classified as SUPPORTED only when the complete normalized
    requirement matches one of the explicit grammars. Partial matches are not
    accepted because silently dropping a trailing clause can change semantics.
    """

    _BOUNDED_AFTER = re.compile(
        r"(?P<response>[a-z][a-z0-9_]*)\s+(?:must|shall)\s+"
        r"(?:assert|occur|complete)\s+within\s+(?P<cycles>\d+)\s+cycles?\s+"
        r"(?:after|of)\s+(?P<trigger>[a-z][a-z0-9_]*)\.?",
        re.IGNORECASE,
    )
    _NO_LATER_THAN = re.compile(
        r"(?:the\s+)?(?P<response>[a-z][a-z0-9_]*)\s+(?:signal\s+)?"
        r"(?:must|shall)\s+be\s+(?:asserted|completed)\s+no\s+later\s+than\s+"
        r"(?P<cycles>\d+)\s+cycles?\s+(?:after|following)\s+"
        r"(?:the\s+)?(?P<trigger>[a-z][a-z0-9_]*)\.?",
        re.IGNORECASE,
    )
    _IF_BOUNDED = re.compile(
        r"if\s+(?P<trigger>[a-z][a-z0-9_]*)\s*,?\s*(?P<response>[a-z][a-z0-9_]*)\s+"
        r"(?:must|shall)\s+(?:assert|occur|complete)\s+within\s+"
        r"(?P<cycles>\d+)\s+cycles?\.?",
        re.IGNORECASE,
    )
    _PROHIBITION = re.compile(
        r"(?P<signal>[a-z][a-z0-9_]*)\s+(?:must|shall)\s+never\s+assert\s+"
        r"while\s+(?P<condition>[a-z][a-z0-9_]*)\.?",
        re.IGNORECASE,
    )
    _IMPLICATION = re.compile(
        r"if\s+(?P<trigger>[a-z][a-z0-9_]*)\s+(?:is\s+)?(?:high|asserted)\s*,?\s*"
        r"(?P<response>[a-z][a-z0-9_]*)\s+(?:must|shall)\s+(?:be\s+)?(?:high|asserted)\.?",
        re.IGNORECASE,
    )
    _PERSISTENCE = re.compile(
        r"(?P<signal>[a-z][a-z0-9_]*)\s+(?:must|shall)\s+remain\s+asserted\s+"
        r"until\s+(?P<release>[a-z][a-z0-9_]*)\.?",
        re.IGNORECASE,
    )

    @staticmethod
    def _signal(value: str) -> str:
        return re.sub(r"[^a-z0-9_]+", "_", value.lower()).strip("_")

    @staticmethod
    def _params(**items: object) -> tuple[tuple[str, str], ...]:
        return tuple((name, str(value)) for name, value in items.items())

    def _translate(self, normalized: str) -> TranslationResult:
        match = self._BOUNDED_AFTER.fullmatch(normalized)
        if match:
            response = self._signal(match.group("response"))
            trigger = self._signal(match.group("trigger"))
            cycles = int(match.group("cycles"))
            return TranslationResult(
                assertion=(
                    f"assert property (@(posedge clk) {trigger} |-> ##[1:{cycles}] {response});"
                ),
                generation_status=GenerationStatus.SUPPORTED,
                matched_pattern="bounded_response_after",
                parameters=self._params(trigger=trigger, response=response, cycles=cycles),
            )

        match = self._NO_LATER_THAN.fullmatch(normalized)
        if match:
            response = self._signal(match.group("response"))
            trigger = self._signal(match.group("trigger"))
            cycles = int(match.group("cycles"))
            return TranslationResult(
                assertion=(
                    f"assert property (@(posedge clk) {trigger} |-> ##[1:{cycles}] {response});"
                ),
                generation_status=GenerationStatus.SUPPORTED,
                matched_pattern="no_later_than_following",
                parameters=self._params(trigger=trigger, response=response, cycles=cycles),
            )

        match = self._IF_BOUNDED.fullmatch(normalized)
        if match:
            response = self._signal(match.group("response"))
            trigger = self._signal(match.group("trigger"))
            cycles = int(match.group("cycles"))
            return TranslationResult(
                assertion=(
                    f"assert property (@(posedge clk) {trigger} |-> ##[1:{cycles}] {response});"
                ),
                generation_status=GenerationStatus.SUPPORTED,
                matched_pattern="conditional_bounded_response",
                parameters=self._params(trigger=trigger, response=response, cycles=cycles),
            )

        match = self._PROHIBITION.fullmatch(normalized)
        if match:
            signal = self._signal(match.group("signal"))
            condition = self._signal(match.group("condition"))
            return TranslationResult(
                assertion=f"assert property (@(posedge clk) {condition} |-> !{signal});",
                generation_status=GenerationStatus.SUPPORTED,
                matched_pattern="prohibition_while_condition",
                parameters=self._params(signal=signal, condition=condition),
            )

        match = self._IMPLICATION.fullmatch(normalized)
        if match:
            trigger = self._signal(match.group("trigger"))
            response = self._signal(match.group("response"))
            return TranslationResult(
                assertion=f"assert property (@(posedge clk) {trigger} |-> {response});",
                generation_status=GenerationStatus.SUPPORTED,
                matched_pattern="immediate_implication",
                parameters=self._params(trigger=trigger, response=response),
            )

        match = self._PERSISTENCE.fullmatch(normalized)
        if match:
            signal = self._signal(match.group("signal"))
            release = self._signal(match.group("release"))
            return TranslationResult(
                assertion=(
                    f"assert property (@(posedge clk) ({signal} && !{release}) |=> "
                    f"({signal} || {release}));"
                ),
                generation_status=GenerationStatus.SUPPORTED,
                matched_pattern="persistence_until_release",
                parameters=self._params(signal=signal, release=release),
            )

        slug = re.sub(r"[^a-z0-9]+", "_", normalized.lower()).strip("_")[:48]
        return TranslationResult(
            assertion=(
                f"assert property ({slug or 'requirement_holds'}); "
                "// FALLBACK: expert review required"
            ),
            generation_status=GenerationStatus.FALLBACK,
            matched_pattern=None,
        )

    def _scenarios_and_coverage(
        self, requirement_id: str, translation: TranslationResult
    ) -> tuple[tuple[str, ...], str]:
        pattern = translation.matched_pattern
        params = dict(translation.parameters)

        if pattern in {
            "bounded_response_after",
            "no_later_than_following",
            "conditional_bounded_response",
        }:
            trigger = params["trigger"]
            response = params["response"]
            cycles = params["cycles"]
            return (
                (
                    f"{trigger} occurs and {response} asserts before cycle {cycles}",
                    f"{response} asserts exactly at the {cycles}-cycle boundary",
                    f"{response} remains low beyond {cycles} cycles after {trigger}",
                ),
                (
                    f"cover {requirement_id}: trigger seen; response before bound; "
                    "response at bound; bound violation"
                ),
            )

        if pattern == "prohibition_while_condition":
            signal = params["signal"]
            condition = params["condition"]
            return (
                (
                    f"{condition} is active while {signal} remains low",
                    f"enter {condition} with {signal} low and hold the safe state",
                    f"{signal} asserts while {condition} is active",
                ),
                f"cover {requirement_id}: condition active; safe hold; prohibited assertion",
            )

        if pattern == "immediate_implication":
            trigger = params["trigger"]
            response = params["response"]
            return (
                (
                    f"{trigger} and {response} are high in the same sampled cycle",
                    f"exercise a transition where {trigger} rises and {response} is already high",
                    f"{trigger} is high while {response} is low",
                ),
                f"cover {requirement_id}: antecedent inactive; implication satisfied; implication violated",
            )

        if pattern == "persistence_until_release":
            signal = params["signal"]
            release = params["release"]
            return (
                (
                    f"{signal} stays asserted across multiple cycles until {release}",
                    f"{release} asserts on the earliest cycle where {signal} may stop persisting",
                    f"{signal} deasserts before {release}",
                ),
                f"cover {requirement_id}: persistence active; release observed; early-drop violation",
            )

        return (
            (
                "nominal behavior satisfying the requirement",
                "boundary condition at the stated requirement limit",
                "adversarial input that violates the requirement",
            ),
            f"cover {requirement_id}: nominal, boundary, violation (fallback draft)",
        )

    def generate(self, requirement: Requirement) -> DraftArtifact:
        normalized = re.sub(r"\s+", " ", requirement.text.strip())
        translation = self._translate(normalized)
        scenarios, coverage_goal = self._scenarios_and_coverage(
            requirement.requirement_id, translation
        )
        return DraftArtifact(
            requirement_id=requirement.requirement_id,
            assertion=translation.assertion,
            scenarios=scenarios,
            coverage_goal=coverage_goal,
            generation_status=translation.generation_status,
            matched_pattern=translation.matched_pattern,
            translation_parameters=translation.parameters,
        )


class RequirementReviewer:
    """Independent requirement-quality review, separate from generation."""

    _NORMATIVE = re.compile(r"\b(must|shall|never|within)\b", re.IGNORECASE)

    def review(self, requirement: Requirement) -> tuple[str, ...]:
        normalized = re.sub(r"\s+", " ", requirement.text.strip())
        lower = normalized.lower()
        findings: list[str] = []

        if not self._NORMATIVE.search(normalized):
            findings.append("Requirement lacks a clear normative term")
        if "within" in lower and not re.search(r"\bwithin\s+\d+\b", lower):
            findings.append("Timing bound is not numeric")
        if any(
            re.search(rf"\b{word}\b", lower)
            for word in ("appropriate", "quickly", "secure", "soon")
        ):
            findings.append("Requirement contains an ambiguous adjective")
        return tuple(findings)


class ArtifactReviewer:
    """Review the generated draft independently from requirement-quality review."""

    def review(self, draft: DraftArtifact) -> tuple[str, ...]:
        findings: list[str] = []
        if draft.generation_status is GenerationStatus.FALLBACK:
            findings.append(
                "Generator used FALLBACK; complete requirement did not match a supported grammar"
            )
        if "expert review required" in draft.assertion.lower():
            findings.append("Assertion requires expert translation before use")
        if draft.generation_status is GenerationStatus.SUPPORTED and not draft.matched_pattern:
            findings.append("Supported assertion is missing pattern provenance")
        if draft.generation_status is GenerationStatus.SUPPORTED:
            if not draft.assertion.startswith("assert property (@(posedge clk)"):
                findings.append("Supported assertion failed structural assertion-prefix review")
            if not draft.assertion.endswith(");"):
                findings.append("Supported assertion failed structural termination review")
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
            translation_parameters=draft.translation_parameters,
            requirement_review_findings=requirement_findings,
            artifact_review_findings=artifact_findings,
            review_findings=requirement_findings + artifact_findings,
        )

    def run(self, requirements: Iterable[Requirement]) -> tuple[VerificationArtifact, ...]:
        return tuple(self.propose(requirement) for requirement in requirements)
