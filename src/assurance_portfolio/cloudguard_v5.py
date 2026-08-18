"""CloudGuard V5 predictive threat intelligence and pre-emptive defense.

V5 is intentionally a forecasting/reference layer above CloudGuard V4.  It
estimates the current attack state, ranks likely next ATT&CK-style techniques,
combines those forecasts with organization-specific exposure, proposes
minimum-impact preventive controls, and governs learning through quarantine and
champion/challenger promotion.

The important trust boundary is unchanged from V4: a forecast score, model
output, CTI item, or learning result never grants response authority.  Proposed
actions still pass through the deterministic V4 policy/HITL gate.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from itertools import combinations
import math
from typing import Iterable, Mapping, Sequence

from .cloudguard_v4 import (
    CloudGuardPolicyEngine,
    DetectionEvidence,
    ResponseDecision,
    ResponseImpactTier,
    ResponsePolicyResult,
    ResponseRequest,
    ThreatSourceTrust,
)


CLOUDGUARD_V5_VERSION = "cloudguard/5.0.0"
FORECAST_MODEL_VERSION = "cloudguard-forecast/1.0.0"
FORECAST_SCHEMA_VERSION = "cloudguard-predictive/1.0.0"
PREDICTIVE_POLICY_VERSION = "cloudguard-predictive-policy/1.0.0"


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _norm(value: str) -> str:
    return " ".join(value.strip().lower().split())


class ForecastHorizon(str, Enum):
    IMMEDIATE = "IMMEDIATE"
    TACTICAL = "TACTICAL"
    STRATEGIC = "STRATEGIC"


class ForecastAssurance(str, Enum):
    HIGH = "HIGH"
    PARTIAL = "PARTIAL"
    LOW = "LOW"
    INSUFFICIENT = "INSUFFICIENT"


class TrainingDisposition(str, Enum):
    QUARANTINED = "QUARANTINED"
    ELIGIBLE = "ELIGIBLE"
    REJECTED = "REJECTED"


class PromotionDecision(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class AttackObservation:
    observation_id: str
    technique_id: str
    sequence: int
    source: str
    verified: bool
    evidence_weight: float = 1.0

    def __post_init__(self) -> None:
        if not self.observation_id.strip() or not self.technique_id.strip():
            raise ValueError("observation requires observation_id and technique_id")
        if self.sequence < 0:
            raise ValueError("observation sequence must be non-negative")
        if not 0.0 <= self.evidence_weight <= 1.0:
            raise ValueError("evidence_weight must be between 0 and 1")


@dataclass(frozen=True)
class Observability:
    expected_sources: tuple[str, ...]
    available_sources: tuple[str, ...]

    @property
    def coverage(self) -> float:
        expected = {_norm(item) for item in self.expected_sources if item.strip()}
        if not expected:
            return 1.0
        available = {_norm(item) for item in self.available_sources if item.strip()}
        return len(expected & available) / len(expected)

    @property
    def missing_sources(self) -> tuple[str, ...]:
        expected = {_norm(item): item for item in self.expected_sources if item.strip()}
        available = {_norm(item) for item in self.available_sources if item.strip()}
        return tuple(expected[key] for key in sorted(expected) if key not in available)


@dataclass(frozen=True)
class TechniqueScore:
    technique_id: str
    score: float


@dataclass(frozen=True)
class ThreatState:
    primary_technique: str | None
    technique_distribution: tuple[TechniqueScore, ...]
    observability_coverage: float
    missing_sources: tuple[str, ...]
    assurance: ForecastAssurance


class ThreatStateEstimator:
    """Deterministic evidence-weighted attack-state estimator.

    The returned values are normalized evidence weights, not calibrated attacker
    intent probabilities.
    """

    def estimate(
        self,
        observations: Sequence[AttackObservation],
        observability: Observability,
    ) -> ThreatState:
        if not observations:
            return ThreatState(
                primary_technique=None,
                technique_distribution=(),
                observability_coverage=observability.coverage,
                missing_sources=observability.missing_sources,
                assurance=ForecastAssurance.INSUFFICIENT,
            )
        maximum_sequence = max(item.sequence for item in observations)
        scores: dict[str, float] = {}
        for item in observations:
            recency = 1.0 / (1.0 + 0.15 * max(0, maximum_sequence - item.sequence))
            verification = 1.0 if item.verified else 0.25
            score = item.evidence_weight * recency * verification
            scores[item.technique_id] = scores.get(item.technique_id, 0.0) + score
        total = sum(scores.values())
        if total <= 0:
            return ThreatState(
                primary_technique=None,
                technique_distribution=(),
                observability_coverage=observability.coverage,
                missing_sources=observability.missing_sources,
                assurance=ForecastAssurance.INSUFFICIENT,
            )
        distribution = tuple(
            TechniqueScore(technique, value / total)
            for technique, value in sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        )
        coverage = observability.coverage
        unverified_fraction = sum(1 for item in observations if not item.verified) / len(observations)
        if coverage >= 0.8 and unverified_fraction == 0:
            assurance = ForecastAssurance.HIGH
        elif coverage >= 0.5 and unverified_fraction <= 0.5:
            assurance = ForecastAssurance.PARTIAL
        else:
            assurance = ForecastAssurance.LOW
        return ThreatState(
            primary_technique=distribution[0].technique_id,
            technique_distribution=distribution,
            observability_coverage=coverage,
            missing_sources=observability.missing_sources,
            assurance=assurance,
        )


@dataclass(frozen=True)
class Transition:
    source_technique: str
    target_technique: str
    empirical_probability: float
    observations: int


class TechniqueTransitionModel:
    """Transparent empirical transition baseline over historical technique sequences."""

    def __init__(self, transitions: Mapping[str, Mapping[str, int]]) -> None:
        normalized: dict[str, dict[str, int]] = {}
        for source, targets in transitions.items():
            if not source.strip():
                raise ValueError("transition source technique must be non-empty")
            clean: dict[str, int] = {}
            for target, count in targets.items():
                if not target.strip() or int(count) < 0:
                    raise ValueError("transition targets must be non-empty with non-negative counts")
                if int(count) > 0:
                    clean[target] = int(count)
            normalized[source] = clean
        self._transitions = normalized

    @classmethod
    def from_sequences(cls, sequences: Sequence[Sequence[str]]) -> "TechniqueTransitionModel":
        counts: dict[str, dict[str, int]] = {}
        for sequence in sequences:
            clean = [item.strip() for item in sequence if item.strip()]
            for source, target in zip(clean, clean[1:]):
                bucket = counts.setdefault(source, {})
                bucket[target] = bucket.get(target, 0) + 1
        return cls(counts)

    def successors(self, technique_id: str) -> tuple[Transition, ...]:
        targets = self._transitions.get(technique_id, {})
        total = sum(targets.values())
        if total <= 0:
            return ()
        return tuple(
            Transition(technique_id, target, count / total, count)
            for target, count in sorted(targets.items(), key=lambda item: (-item[1], item[0]))
        )

    def forecast(self, state: ThreatState, *, top_k: int = 5) -> tuple[TechniqueScore, ...]:
        if top_k < 1:
            raise ValueError("top_k must be >= 1")
        aggregate: dict[str, float] = {}
        for current in state.technique_distribution:
            for transition in self.successors(current.technique_id):
                aggregate[transition.target_technique] = aggregate.get(
                    transition.target_technique, 0.0
                ) + current.score * transition.empirical_probability
        total = sum(aggregate.values())
        if total <= 0:
            return ()
        ranked = sorted(aggregate.items(), key=lambda item: (-item[1], item[0]))[:top_k]
        return tuple(TechniqueScore(technique, score / total) for technique, score in ranked)


@dataclass(frozen=True)
class SecurityNode:
    node_id: str
    kind: str
    criticality: float = 0.5
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.node_id.strip() or not self.kind.strip():
            raise ValueError("security node requires node_id and kind")
        if not 0.0 <= self.criticality <= 1.0:
            raise ValueError("node criticality must be between 0 and 1")


@dataclass(frozen=True)
class ExposureEdge:
    source: str
    target: str
    relation: str
    enabled: bool = True


@dataclass(frozen=True)
class VulnerabilityExposure:
    asset_id: str
    cve: str
    epss: float
    kev: bool
    mitigated: bool = False

    def __post_init__(self) -> None:
        if not 0.0 <= self.epss <= 1.0:
            raise ValueError("EPSS must be between 0 and 1")


@dataclass(frozen=True)
class TechniqueExposure:
    technique_id: str
    target_nodes: tuple[str, ...]
    control_effectiveness: float = 0.0
    requires_vulnerability: bool = False

    def __post_init__(self) -> None:
        if not 0.0 <= self.control_effectiveness <= 1.0:
            raise ValueError("control_effectiveness must be between 0 and 1")


@dataclass(frozen=True)
class ExposureScore:
    technique_id: str
    reachable: bool
    reachable_targets: tuple[str, ...]
    criticality: float
    exploit_likelihood: float
    known_exploited: bool
    control_weakness: float
    local_priority: float


class ExposureGraph:
    """Organization-specific reachability and vulnerability model.

    `local_priority` is a transparent prioritization component, not a calibrated
    breach probability.
    """

    def __init__(
        self,
        *,
        nodes: Sequence[SecurityNode],
        edges: Sequence[ExposureEdge],
        vulnerabilities: Sequence[VulnerabilityExposure],
        technique_exposures: Sequence[TechniqueExposure],
    ) -> None:
        self.nodes = {item.node_id: item for item in nodes}
        if len(self.nodes) != len(nodes):
            raise ValueError("duplicate security node_id")
        for edge in edges:
            if edge.source not in self.nodes or edge.target not in self.nodes:
                raise ValueError("exposure edge references unknown node")
        self.edges = tuple(edges)
        self.vulnerabilities = tuple(vulnerabilities)
        self.technique_exposures = {item.technique_id: item for item in technique_exposures}

    def reachable_from(self, start_nodes: Sequence[str]) -> frozenset[str]:
        unknown = [item for item in start_nodes if item not in self.nodes]
        if unknown:
            raise ValueError(f"unknown start nodes: {unknown}")
        adjacency: dict[str, list[str]] = {}
        for edge in self.edges:
            if edge.enabled:
                adjacency.setdefault(edge.source, []).append(edge.target)
        seen = set(start_nodes)
        queue = list(start_nodes)
        while queue:
            current = queue.pop(0)
            for target in adjacency.get(current, []):
                if target not in seen:
                    seen.add(target)
                    queue.append(target)
        return frozenset(seen)

    def score_technique(self, technique_id: str, *, start_nodes: Sequence[str]) -> ExposureScore:
        exposure = self.technique_exposures.get(technique_id)
        if exposure is None:
            return ExposureScore(technique_id, False, (), 0.0, 0.0, False, 1.0, 0.0)
        reachable = self.reachable_from(start_nodes)
        targets = tuple(sorted(node for node in exposure.target_nodes if node in reachable))
        if not targets:
            return ExposureScore(
                technique_id,
                False,
                (),
                0.0,
                0.0,
                False,
                1.0 - exposure.control_effectiveness,
                0.0,
            )
        criticality = max(self.nodes[node].criticality for node in targets)
        vulns = [
            vuln
            for vuln in self.vulnerabilities
            if vuln.asset_id in targets and not vuln.mitigated
        ]
        known_exploited = any(vuln.kev for vuln in vulns)
        exploit_likelihood = max((vuln.epss for vuln in vulns), default=0.0)
        if known_exploited:
            exploit_likelihood = max(exploit_likelihood, 0.75)
        if exposure.requires_vulnerability and not vulns:
            exploit_likelihood = 0.0
        control_weakness = 1.0 - exposure.control_effectiveness
        reachability_component = 1.0
        local_priority = _clamp01(
            0.30 * reachability_component
            + 0.25 * criticality
            + 0.25 * exploit_likelihood
            + 0.20 * control_weakness
        )
        if exposure.requires_vulnerability and exploit_likelihood == 0.0:
            local_priority *= 0.25
        return ExposureScore(
            technique_id,
            True,
            targets,
            criticality,
            exploit_likelihood,
            known_exploited,
            control_weakness,
            local_priority,
        )


@dataclass(frozen=True)
class ForecastTechnique:
    technique_id: str
    transition_score: float
    exposure_priority: float
    combined_priority: float
    reachable_targets: tuple[str, ...]
    known_exploited: bool


@dataclass(frozen=True)
class AttackPath:
    techniques: tuple[str, ...]
    transition_score: float
    exposure_priority: float
    combined_priority: float
    reachable_targets: tuple[str, ...]


class AttackPathForecaster:
    def __init__(self, transition_model: TechniqueTransitionModel, exposure_graph: ExposureGraph) -> None:
        self.transition_model = transition_model
        self.exposure_graph = exposure_graph

    def next_techniques(
        self,
        state: ThreatState,
        *,
        start_nodes: Sequence[str],
        top_k: int = 5,
    ) -> tuple[ForecastTechnique, ...]:
        forecast = self.transition_model.forecast(state, top_k=max(top_k * 2, top_k))
        items: list[ForecastTechnique] = []
        for item in forecast:
            exposure = self.exposure_graph.score_technique(item.technique_id, start_nodes=start_nodes)
            combined = item.score * (0.35 + 0.65 * exposure.local_priority)
            items.append(
                ForecastTechnique(
                    item.technique_id,
                    item.score,
                    exposure.local_priority,
                    combined,
                    exposure.reachable_targets,
                    exposure.known_exploited,
                )
            )
        return tuple(sorted(items, key=lambda item: (-item.combined_priority, item.technique_id))[:top_k])

    def paths(
        self,
        state: ThreatState,
        *,
        start_nodes: Sequence[str],
        depth: int = 3,
        beam_width: int = 5,
    ) -> tuple[AttackPath, ...]:
        if depth < 1 or beam_width < 1:
            raise ValueError("depth and beam_width must be >= 1")
        seeds = [(item.technique_id, item.score) for item in state.technique_distribution]
        beam: list[tuple[tuple[str, ...], float]] = [((technique,), score) for technique, score in seeds]
        completed: list[AttackPath] = []
        for _ in range(depth):
            expanded: list[tuple[tuple[str, ...], float]] = []
            for path, path_score in beam:
                successors = self.transition_model.successors(path[-1])
                if not successors:
                    continue
                for transition in successors:
                    if transition.target_technique in path:
                        continue
                    new_path = path + (transition.target_technique,)
                    new_score = path_score * transition.empirical_probability
                    expanded.append((new_path, new_score))
            if not expanded:
                break
            scored: list[tuple[AttackPath, tuple[str, ...], float]] = []
            for path, transition_score in expanded:
                exposure_scores = [
                    self.exposure_graph.score_technique(technique, start_nodes=start_nodes)
                    for technique in path[1:]
                ]
                exposure_priority = (
                    sum(item.local_priority for item in exposure_scores) / len(exposure_scores)
                    if exposure_scores
                    else 0.0
                )
                targets = tuple(
                    sorted({target for item in exposure_scores for target in item.reachable_targets})
                )
                combined = transition_score * (0.35 + 0.65 * exposure_priority)
                candidate = AttackPath(path, transition_score, exposure_priority, combined, targets)
                scored.append((candidate, path, transition_score))
            scored.sort(key=lambda item: (-item[0].combined_priority, item[0].techniques))
            completed.extend(item[0] for item in scored[:beam_width])
            beam = [(item[1], item[2]) for item in scored[:beam_width]]
        unique: dict[tuple[str, ...], AttackPath] = {}
        for item in completed:
            previous = unique.get(item.techniques)
            if previous is None or item.combined_priority > previous.combined_priority:
                unique[item.techniques] = item
        return tuple(
            sorted(unique.values(), key=lambda item: (-item.combined_priority, item.techniques))[
                :beam_width
            ]
        )


@dataclass(frozen=True)
class ThreatProfile:
    profile_id: str
    horizon: ForecastHorizon
    state: ThreatState
    next_techniques: tuple[ForecastTechnique, ...]
    attack_paths: tuple[AttackPath, ...]
    forecast_model_version: str
    notes: tuple[str, ...] = ()


class PredictiveThreatEngine:
    def __init__(
        self,
        *,
        state_estimator: ThreatStateEstimator,
        path_forecaster: AttackPathForecaster,
        model_version: str = FORECAST_MODEL_VERSION,
    ) -> None:
        self.state_estimator = state_estimator
        self.path_forecaster = path_forecaster
        self.model_version = model_version

    def build_profile(
        self,
        *,
        profile_id: str,
        observations: Sequence[AttackObservation],
        observability: Observability,
        start_nodes: Sequence[str],
        horizon: ForecastHorizon = ForecastHorizon.IMMEDIATE,
        top_k: int = 5,
        path_depth: int = 3,
    ) -> ThreatProfile:
        state = self.state_estimator.estimate(observations, observability)
        next_techniques = self.path_forecaster.next_techniques(
            state, start_nodes=start_nodes, top_k=top_k
        )
        attack_paths = self.path_forecaster.paths(
            state, start_nodes=start_nodes, depth=path_depth, beam_width=top_k
        )
        notes: list[str] = []
        if state.assurance in {ForecastAssurance.LOW, ForecastAssurance.INSUFFICIENT}:
            notes.append("low observability/evidence quality: do not treat forecast as action authority")
        if not next_techniques:
            notes.append("transition corpus has no supported successor for current state")
        return ThreatProfile(
            profile_id=profile_id,
            horizon=horizon,
            state=state,
            next_techniques=next_techniques,
            attack_paths=attack_paths,
            forecast_model_version=self.model_version,
            notes=tuple(notes),
        )


@dataclass(frozen=True)
class PreventiveControl:
    control_id: str
    action: str
    target: str
    impact_tier: ResponseImpactTier
    operational_cost: float
    blocks_techniques: tuple[str, ...] = ()
    parameters: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= self.operational_cost <= 1.0:
            raise ValueError("operational_cost must be between 0 and 1")


@dataclass(frozen=True)
class PreemptionCandidate:
    control_ids: tuple[str, ...]
    baseline_risk: float
    residual_risk: float
    risk_reduction: float
    operational_cost: float
    utility: float
    blocked_paths: int


class PreemptionOptimizer:
    """Ranks one- or two-control interventions by projected path-risk reduction.

    This is a transparent counterfactual ranking baseline.  It does not claim to
    estimate real-world intervention effectiveness without empirical validation.
    """

    def __init__(self, *, cost_weight: float = 0.35) -> None:
        if not 0.0 <= cost_weight <= 1.0:
            raise ValueError("cost_weight must be between 0 and 1")
        self.cost_weight = cost_weight

    def rank(
        self,
        paths: Sequence[AttackPath],
        controls: Sequence[PreventiveControl],
        *,
        max_controls: int = 2,
    ) -> tuple[PreemptionCandidate, ...]:
        if max_controls < 1:
            raise ValueError("max_controls must be >= 1")
        baseline = sum(item.combined_priority for item in paths)
        if baseline <= 0 or not controls:
            return ()
        candidates: list[PreemptionCandidate] = []
        limit = min(max_controls, len(controls))
        for size in range(1, limit + 1):
            for group in combinations(controls, size):
                blocked = set(technique for control in group for technique in control.blocks_techniques)
                residual = 0.0
                blocked_paths = 0
                for path in paths:
                    if blocked.intersection(path.techniques):
                        blocked_paths += 1
                    else:
                        residual += path.combined_priority
                reduction = _clamp01((baseline - residual) / baseline)
                cost = _clamp01(sum(item.operational_cost for item in group))
                utility = reduction - self.cost_weight * cost
                candidates.append(
                    PreemptionCandidate(
                        tuple(item.control_id for item in group),
                        baseline,
                        residual,
                        reduction,
                        cost,
                        utility,
                        blocked_paths,
                    )
                )
        return tuple(
            sorted(candidates, key=lambda item: (-item.utility, -item.risk_reduction, item.control_ids))
        )


def control_to_response_request(
    control: PreventiveControl,
    *,
    incident_id: str,
    requested_by: str,
    evidence_ids: Sequence[str],
    threat_ids: Sequence[str],
) -> ResponseRequest:
    return ResponseRequest(
        incident_id=incident_id,
        action=control.action,
        target=control.target,
        requested_by=requested_by,
        impact_tier=control.impact_tier,
        parameters=dict(control.parameters),
        evidence_ids=tuple(evidence_ids),
        threat_ids=tuple(threat_ids),
        emergency=False,
    )


def gate_preemption(
    request: ResponseRequest,
    *,
    evidence: Sequence[DetectionEvidence],
) -> ResponsePolicyResult:
    """Run a predictive proposal through the existing V4 authority boundary."""

    return CloudGuardPolicyEngine().decide(request, evidence=evidence, review=None)


@dataclass(frozen=True)
class TrainingExample:
    example_id: str
    incident_id: str
    source_trust: ThreatSourceTrust
    content_digest: str
    labels_confirmed: bool
    corroborated_by: tuple[str, ...] = ()
    analyst_approved: bool = False


@dataclass(frozen=True)
class TrainingEligibility:
    example_id: str
    disposition: TrainingDisposition
    reasons: tuple[str, ...]


class TrainingQuarantine:
    """Determines whether field data may enter a challenger training set."""

    def evaluate(self, example: TrainingExample) -> TrainingEligibility:
        reasons: list[str] = []
        if not example.content_digest.strip():
            return TrainingEligibility(
                example.example_id,
                TrainingDisposition.REJECTED,
                ("missing content digest",),
            )
        if not example.labels_confirmed:
            reasons.append("labels are not confirmed")
        if example.source_trust is ThreatSourceTrust.UNTRUSTED_DISCOVERY:
            if len({item for item in example.corroborated_by if item.strip()}) < 2:
                reasons.append("untrusted source requires at least two independent corroborations")
            if not example.analyst_approved:
                reasons.append("untrusted source requires analyst approval")
        if reasons:
            return TrainingEligibility(
                example.example_id,
                TrainingDisposition.QUARANTINED,
                tuple(reasons),
            )
        return TrainingEligibility(
            example.example_id,
            TrainingDisposition.ELIGIBLE,
            ("provenance and label gates satisfied",),
        )


@dataclass(frozen=True)
class ForecastMetrics:
    next_technique_recall_at_3: float
    brier_score: float
    false_preemption_rate: float
    old_threat_retention: float
    poison_suite_passed: bool
    shadow_cases: int

    def __post_init__(self) -> None:
        for name in (
            "next_technique_recall_at_3",
            "brier_score",
            "false_preemption_rate",
            "old_threat_retention",
        ):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.shadow_cases < 0:
            raise ValueError("shadow_cases must be non-negative")


@dataclass(frozen=True)
class ModelCandidate:
    candidate_id: str
    version: str
    proposed_by: str
    training_examples: tuple[TrainingExample, ...]
    metrics: ForecastMetrics


@dataclass(frozen=True)
class PromotionReview:
    reviewer: str
    approved: bool
    rationale: str


@dataclass(frozen=True)
class PromotionResult:
    decision: PromotionDecision
    candidate_id: str
    version: str
    reasons: tuple[str, ...]


class ModelGovernanceRegistry:
    """Champion/challenger promotion with explicit, independent governance."""

    def __init__(
        self,
        *,
        active_version: str,
        quarantine: TrainingQuarantine | None = None,
        min_recall_at_3: float = 0.60,
        max_brier: float = 0.25,
        max_false_preemption: float = 0.10,
        min_old_threat_retention: float = 0.90,
        min_shadow_cases: int = 20,
    ) -> None:
        self.active_version = active_version
        self.quarantine = quarantine or TrainingQuarantine()
        self.min_recall_at_3 = min_recall_at_3
        self.max_brier = max_brier
        self.max_false_preemption = max_false_preemption
        self.min_old_threat_retention = min_old_threat_retention
        self.min_shadow_cases = min_shadow_cases

    def review(self, candidate: ModelCandidate, review: PromotionReview) -> PromotionResult:
        reasons: list[str] = []
        if _norm(review.reviewer) == _norm(candidate.proposed_by):
            reasons.append("candidate proposer cannot approve own promotion")
        if not review.approved or not review.rationale.strip():
            reasons.append("explicit independent approval with rationale is required")
        eligibility = [self.quarantine.evaluate(item) for item in candidate.training_examples]
        quarantined = [item.example_id for item in eligibility if item.disposition is not TrainingDisposition.ELIGIBLE]
        if quarantined:
            reasons.append(f"training examples remain quarantined/rejected: {quarantined}")
        metrics = candidate.metrics
        if metrics.next_technique_recall_at_3 < self.min_recall_at_3:
            reasons.append("next-technique Recall@3 below promotion threshold")
        if metrics.brier_score > self.max_brier:
            reasons.append("Brier score exceeds calibration threshold")
        if metrics.false_preemption_rate > self.max_false_preemption:
            reasons.append("false pre-emption rate exceeds threshold")
        if metrics.old_threat_retention < self.min_old_threat_retention:
            reasons.append("old-threat retention below threshold")
        if not metrics.poison_suite_passed:
            reasons.append("poisoning/adversarial suite did not pass")
        if metrics.shadow_cases < self.min_shadow_cases:
            reasons.append("insufficient shadow-mode cases")
        if reasons:
            return PromotionResult(
                PromotionDecision.REJECTED,
                candidate.candidate_id,
                candidate.version,
                tuple(reasons),
            )
        return PromotionResult(
            PromotionDecision.APPROVED,
            candidate.candidate_id,
            candidate.version,
            ("challenger satisfies governed promotion gates",),
        )


def recall_at_k(
    ranked_predictions: Sequence[Sequence[str]],
    actual: Sequence[str],
    *,
    k: int,
) -> float:
    if k < 1:
        raise ValueError("k must be >= 1")
    if len(ranked_predictions) != len(actual):
        raise ValueError("predictions and actual lengths differ")
    if not actual:
        return 0.0
    hits = sum(1 for predictions, target in zip(ranked_predictions, actual) if target in list(predictions)[:k])
    return hits / len(actual)


def brier_score(probabilities: Sequence[float], outcomes: Sequence[int]) -> float:
    if len(probabilities) != len(outcomes):
        raise ValueError("probabilities and outcomes lengths differ")
    if not probabilities:
        return 0.0
    total = 0.0
    for probability, outcome in zip(probabilities, outcomes):
        if not 0.0 <= probability <= 1.0 or outcome not in (0, 1):
            raise ValueError("Brier inputs require probabilities in [0,1] and binary outcomes")
        total += (probability - outcome) ** 2
    return total / len(probabilities)


def expected_calibration_error(
    probabilities: Sequence[float],
    outcomes: Sequence[int],
    *,
    bins: int = 10,
) -> float:
    if len(probabilities) != len(outcomes):
        raise ValueError("probabilities and outcomes lengths differ")
    if bins < 1:
        raise ValueError("bins must be >= 1")
    if not probabilities:
        return 0.0
    buckets: list[list[tuple[float, int]]] = [[] for _ in range(bins)]
    for probability, outcome in zip(probabilities, outcomes):
        if not 0.0 <= probability <= 1.0 or outcome not in (0, 1):
            raise ValueError("calibration inputs require probabilities in [0,1] and binary outcomes")
        index = min(bins - 1, int(probability * bins))
        buckets[index].append((probability, outcome))
    total = len(probabilities)
    error = 0.0
    for bucket in buckets:
        if not bucket:
            continue
        confidence = sum(item[0] for item in bucket) / len(bucket)
        accuracy = sum(item[1] for item in bucket) / len(bucket)
        error += (len(bucket) / total) * abs(confidence - accuracy)
    return error


def preemption_lead_time(*, forecast_time: float, actual_time: float) -> float:
    """Return lead time in caller-supplied time units; negative means forecast was late."""

    return float(actual_time) - float(forecast_time)
