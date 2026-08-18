"""Model-backed generator/reviewer orchestration with deterministic tool grounding.

The deterministic V4 copilot remains the offline baseline. This module adds a
real two-call agentic path: one model invocation proposes an artifact and a
separate model invocation reviews it. A deterministic validator remains the
final source of executable evidence; model agreement never substitutes for a
tool result.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from typing import Mapping, Protocol, Sequence

from .sva_validation import SVAValidationResult, StructuralSVAValidator, ValidationStatus
from .verification_copilot import ArtifactGenerator, Requirement


class ModelBackend(Protocol):
    @property
    def name(self) -> str: ...

    def complete(self, *, role: str, prompt: str) -> str: ...


class ScriptedModelBackend:
    """Deterministic backend for CI and offline orchestration tests."""

    def __init__(self, responses: Sequence[str], name: str = "scripted") -> None:
        self._responses = list(responses)
        self._index = 0
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def complete(self, *, role: str, prompt: str) -> str:
        del role, prompt
        if self._index >= len(self._responses):
            raise RuntimeError("ScriptedModelBackend has no response left")
        response = self._responses[self._index]
        self._index += 1
        return response


class OpenAIResponsesBackend:
    """Optional OpenAI Responses API backend.

    `openai` is imported lazily so the core package remains dependency-light.
    Configure OPENAI_API_KEY normally through the SDK and provide a model via
    `model=` or OPENAI_MODEL.
    """

    def __init__(self, model: str | None = None) -> None:
        self.model = model or os.getenv("OPENAI_MODEL", "")
        if not self.model:
            raise ValueError("An OpenAI model is required via model= or OPENAI_MODEL")

    @property
    def name(self) -> str:
        return f"openai-responses:{self.model}"

    def complete(self, *, role: str, prompt: str) -> str:
        try:
            from openai import OpenAI  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "OpenAI backend requires the optional 'openai' package"
            ) from exc
        client = OpenAI()
        response = client.responses.create(
            model=self.model,
            instructions=role,
            input=prompt,
        )
        text = response.output_text
        if not text:
            raise RuntimeError("OpenAI response did not contain output_text")
        return text


@dataclass(frozen=True)
class ModelDraft:
    requirement_id: str
    assertion: str
    scenarios: tuple[str, ...]
    coverage_goal: str
    assumptions: tuple[str, ...]
    rationale: str


@dataclass(frozen=True)
class ModelReview:
    verdict: str
    findings: tuple[str, ...]
    recommended_action: str


@dataclass(frozen=True)
class AgenticVerificationArtifact:
    requirement_id: str
    deterministic_baseline_assertion: str
    deterministic_baseline_status: str
    model_draft: ModelDraft
    model_review: ModelReview
    validation: SVAValidationResult
    generator_backend: str
    reviewer_backend: str
    accepted_for_human_review: bool


def _extract_json(text: str) -> Mapping[str, object]:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].lstrip()
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError("Model response must be a single JSON object") from exc
    if not isinstance(value, Mapping):
        raise ValueError("Model response must be a JSON object")
    return value


def _string_list(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{field} must be a JSON list of strings")
    return tuple(item.strip() for item in value if item.strip())


class ModelArtifactGenerator:
    ROLE = (
        "You are the generator role in a pre-silicon verification workflow. "
        "Draft reviewable artifacts; never claim sign-off or tool validation. "
        "Return only the requested JSON object."
    )

    def __init__(self, backend: ModelBackend) -> None:
        self.backend = backend

    def generate(self, requirement: Requirement, baseline: Mapping[str, object]) -> ModelDraft:
        prompt = f"""Requirement ID: {requirement.requirement_id}
Requirement: {requirement.text}
Deterministic baseline context: {json.dumps(baseline, sort_keys=True)}

Return exactly this JSON schema:
{{
  "assertion": "one SystemVerilog assert property statement ending with ;",
  "scenarios": ["nominal", "boundary", "violation"],
  "coverage_goal": "concise measurable coverage goal",
  "assumptions": ["explicit assumption"],
  "rationale": "why this draft matches the requirement"
}}

Do not use markdown fences. If the requirement is ambiguous, state that in assumptions rather than inventing missing intent."""
        data = _extract_json(self.backend.complete(role=self.ROLE, prompt=prompt))
        assertion = str(data.get("assertion", "")).strip()
        coverage_goal = str(data.get("coverage_goal", "")).strip()
        rationale = str(data.get("rationale", "")).strip()
        if not assertion:
            raise ValueError("generator response omitted assertion")
        if not coverage_goal or not rationale:
            raise ValueError("generator response omitted coverage_goal or rationale")
        return ModelDraft(
            requirement_id=requirement.requirement_id,
            assertion=assertion,
            scenarios=_string_list(data.get("scenarios"), "scenarios"),
            coverage_goal=coverage_goal,
            assumptions=_string_list(data.get("assumptions", []), "assumptions"),
            rationale=rationale,
        )


class ModelArtifactReviewer:
    ROLE = (
        "You are an independent adversarial verification reviewer. You did not "
        "generate the candidate. Look for semantic mismatch, missing reset/clock "
        "assumptions, vacuity risk, unsupported signals, and weak scenarios. "
        "Never approve based only on plausibility. Return only JSON."
    )

    def __init__(self, backend: ModelBackend) -> None:
        self.backend = backend

    def review(self, requirement: Requirement, draft: ModelDraft) -> ModelReview:
        prompt = f"""Requirement ID: {requirement.requirement_id}
Requirement: {requirement.text}
Candidate draft: {json.dumps(asdict(draft), sort_keys=True)}

Return exactly:
{{
  "verdict": "ACCEPT_FOR_TOOL_CHECK" | "REVISE" | "ABSTAIN",
  "findings": ["specific finding"],
  "recommended_action": "one concise next action"
}}

ACCEPT_FOR_TOOL_CHECK means only that the candidate is coherent enough to send to a deterministic verification tool. It is not sign-off."""
        data = _extract_json(self.backend.complete(role=self.ROLE, prompt=prompt))
        verdict = str(data.get("verdict", "")).strip().upper()
        if verdict not in {"ACCEPT_FOR_TOOL_CHECK", "REVISE", "ABSTAIN"}:
            raise ValueError(
                "reviewer verdict must be ACCEPT_FOR_TOOL_CHECK, REVISE, or ABSTAIN"
            )
        recommended_action = str(data.get("recommended_action", "")).strip()
        if not recommended_action:
            raise ValueError("reviewer response omitted recommended_action")
        return ModelReview(
            verdict=verdict,
            findings=_string_list(data.get("findings", []), "findings"),
            recommended_action=recommended_action,
        )


class AgenticVerificationCopilot:
    """Two-role model workflow with deterministic validation as acceptance gate."""

    def __init__(
        self,
        *,
        generator_backend: ModelBackend,
        reviewer_backend: ModelBackend,
        validator: object | None = None,
    ) -> None:
        if generator_backend is reviewer_backend:
            raise ValueError("generator and reviewer must use distinct backend instances")
        self.generator = ModelArtifactGenerator(generator_backend)
        self.reviewer = ModelArtifactReviewer(reviewer_backend)
        self.validator = validator or StructuralSVAValidator()

    def propose(self, requirement: Requirement) -> AgenticVerificationArtifact:
        deterministic = ArtifactGenerator().generate(requirement)
        baseline: Mapping[str, object] = {
            "assertion": deterministic.assertion,
            "generation_status": deterministic.generation_status.value,
            "matched_pattern": deterministic.matched_pattern,
            "scenarios": deterministic.scenarios,
            "coverage_goal": deterministic.coverage_goal,
        }
        draft = self.generator.generate(requirement, baseline)
        review = self.reviewer.review(requirement, draft)

        if review.verdict == "ACCEPT_FOR_TOOL_CHECK":
            validation = self.validator.validate(draft.assertion)  # type: ignore[attr-defined]
        else:
            validation = SVAValidationResult(
                status=ValidationStatus.UNAVAILABLE,
                validator=getattr(self.validator, "name", type(self.validator).__name__),
                detail=f"tool check skipped because reviewer verdict was {review.verdict}",
            )

        accepted = (
            review.verdict == "ACCEPT_FOR_TOOL_CHECK"
            and validation.status is ValidationStatus.VALID
        )
        return AgenticVerificationArtifact(
            requirement_id=requirement.requirement_id,
            deterministic_baseline_assertion=deterministic.assertion,
            deterministic_baseline_status=deterministic.generation_status.value,
            model_draft=draft,
            model_review=review,
            validation=validation,
            generator_backend=self.generator.backend.name,
            reviewer_backend=self.reviewer.backend.name,
            accepted_for_human_review=accepted,
        )
