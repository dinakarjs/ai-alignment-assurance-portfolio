"""CLI for CloudGuard V5 predictive threat intelligence reference workflows."""

from __future__ import annotations

from dataclasses import asdict
import argparse
import json
from pathlib import Path
from typing import Mapping

from .cloudguard_v4 import ResponseImpactTier, ThreatSourceTrust
from .cloudguard_v5 import (
    AttackObservation,
    AttackPathForecaster,
    ExposureEdge,
    ExposureGraph,
    ForecastHorizon,
    ForecastMetrics,
    ModelCandidate,
    ModelGovernanceRegistry,
    Observability,
    PredictiveThreatEngine,
    PreemptionOptimizer,
    PreventiveControl,
    PromotionReview,
    SecurityNode,
    TechniqueExposure,
    TechniqueTransitionModel,
    ThreatStateEstimator,
    TrainingExample,
    TrainingQuarantine,
    VulnerabilityExposure,
)


def _load(path: str) -> Mapping[str, object]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError("input must be a JSON object")
    return value


def _build_engine(data: Mapping[str, object]) -> PredictiveThreatEngine:
    graph_data = data.get("exposure_graph")
    transitions_data = data.get("transition_sequences")
    if not isinstance(graph_data, Mapping) or not isinstance(transitions_data, list):
        raise ValueError("profile input requires exposure_graph and transition_sequences")

    nodes = tuple(
        SecurityNode(
            str(item["node_id"]),
            str(item["kind"]),
            float(item.get("criticality", 0.5)),
            tuple(str(tag) for tag in item.get("tags", [])),
        )
        for item in graph_data.get("nodes", [])
        if isinstance(item, Mapping)
    )
    edges = tuple(
        ExposureEdge(
            str(item["source"]),
            str(item["target"]),
            str(item["relation"]),
            bool(item.get("enabled", True)),
        )
        for item in graph_data.get("edges", [])
        if isinstance(item, Mapping)
    )
    vulnerabilities = tuple(
        VulnerabilityExposure(
            str(item["asset_id"]),
            str(item["cve"]),
            float(item["epss"]),
            bool(item["kev"]),
            bool(item.get("mitigated", False)),
        )
        for item in graph_data.get("vulnerabilities", [])
        if isinstance(item, Mapping)
    )
    technique_exposures = tuple(
        TechniqueExposure(
            str(item["technique_id"]),
            tuple(str(value) for value in item.get("target_nodes", [])),
            float(item.get("control_effectiveness", 0.0)),
            bool(item.get("requires_vulnerability", False)),
        )
        for item in graph_data.get("technique_exposures", [])
        if isinstance(item, Mapping)
    )
    graph = ExposureGraph(
        nodes=nodes,
        edges=edges,
        vulnerabilities=vulnerabilities,
        technique_exposures=technique_exposures,
    )
    sequences = tuple(
        tuple(str(value) for value in sequence)
        for sequence in transitions_data
        if isinstance(sequence, list)
    )
    model = TechniqueTransitionModel.from_sequences(sequences)
    return PredictiveThreatEngine(
        state_estimator=ThreatStateEstimator(),
        path_forecaster=AttackPathForecaster(model, graph),
    )


def _profile_payload(data: Mapping[str, object]) -> dict[str, object]:
    observations = tuple(
        AttackObservation(
            str(item["observation_id"]),
            str(item["technique_id"]),
            int(item["sequence"]),
            str(item["source"]),
            bool(item["verified"]),
            float(item.get("evidence_weight", 1.0)),
        )
        for item in data.get("observations", [])
        if isinstance(item, Mapping)
    )
    observability_data = data.get("observability")
    if not isinstance(observability_data, Mapping):
        raise ValueError("profile input requires observability")
    observability = Observability(
        tuple(str(item) for item in observability_data.get("expected_sources", [])),
        tuple(str(item) for item in observability_data.get("available_sources", [])),
    )
    profile = _build_engine(data).build_profile(
        profile_id=str(data["profile_id"]),
        observations=observations,
        observability=observability,
        start_nodes=tuple(str(item) for item in data.get("start_nodes", [])),
        horizon=ForecastHorizon(str(data.get("horizon", "IMMEDIATE"))),
        top_k=int(data.get("top_k", 5)),
        path_depth=int(data.get("path_depth", 3)),
    )
    return asdict(profile)


def _preemption_payload(data: Mapping[str, object]) -> dict[str, object]:
    profile_data = data.get("profile")
    controls_data = data.get("controls")
    if not isinstance(profile_data, Mapping) or not isinstance(controls_data, list):
        raise ValueError("preemption input requires profile and controls")
    profile_payload = _profile_payload(profile_data)
    # Rebuild profile from source input to retain dataclass types for optimizer.
    observations = tuple(
        AttackObservation(
            str(item["observation_id"]), str(item["technique_id"]), int(item["sequence"]),
            str(item["source"]), bool(item["verified"]), float(item.get("evidence_weight", 1.0))
        )
        for item in profile_data.get("observations", []) if isinstance(item, Mapping)
    )
    obs_data = profile_data.get("observability")
    assert isinstance(obs_data, Mapping)
    profile = _build_engine(profile_data).build_profile(
        profile_id=str(profile_data["profile_id"]),
        observations=observations,
        observability=Observability(
            tuple(str(item) for item in obs_data.get("expected_sources", [])),
            tuple(str(item) for item in obs_data.get("available_sources", [])),
        ),
        start_nodes=tuple(str(item) for item in profile_data.get("start_nodes", [])),
        horizon=ForecastHorizon(str(profile_data.get("horizon", "IMMEDIATE"))),
        top_k=int(profile_data.get("top_k", 5)),
        path_depth=int(profile_data.get("path_depth", 3)),
    )
    controls = tuple(
        PreventiveControl(
            str(item["control_id"]),
            str(item["action"]),
            str(item["target"]),
            ResponseImpactTier(int(item["impact_tier"])),
            float(item["operational_cost"]),
            tuple(str(value) for value in item.get("blocks_techniques", [])),
            dict(item.get("parameters", {})),
        )
        for item in controls_data if isinstance(item, Mapping)
    )
    ranked = PreemptionOptimizer(cost_weight=float(data.get("cost_weight", 0.35))).rank(
        profile.attack_paths, controls, max_controls=int(data.get("max_controls", 2))
    )
    return {"profile": profile_payload, "ranked_preemption": [asdict(item) for item in ranked]}


def _training_payload(data: Mapping[str, object]) -> dict[str, object]:
    example = TrainingExample(
        str(data["example_id"]),
        str(data["incident_id"]),
        ThreatSourceTrust(str(data["source_trust"])),
        str(data["content_digest"]),
        bool(data["labels_confirmed"]),
        tuple(str(item) for item in data.get("corroborated_by", [])),
        bool(data.get("analyst_approved", False)),
    )
    return asdict(TrainingQuarantine().evaluate(example))


def _promotion_payload(data: Mapping[str, object]) -> dict[str, object]:
    examples = tuple(
        TrainingExample(
            str(item["example_id"]), str(item["incident_id"]),
            ThreatSourceTrust(str(item["source_trust"])), str(item["content_digest"]),
            bool(item["labels_confirmed"]),
            tuple(str(value) for value in item.get("corroborated_by", [])),
            bool(item.get("analyst_approved", False)),
        )
        for item in data.get("training_examples", []) if isinstance(item, Mapping)
    )
    metrics_data = data.get("metrics")
    review_data = data.get("review")
    if not isinstance(metrics_data, Mapping) or not isinstance(review_data, Mapping):
        raise ValueError("promotion input requires metrics and review")
    candidate = ModelCandidate(
        str(data["candidate_id"]),
        str(data["version"]),
        str(data["proposed_by"]),
        examples,
        ForecastMetrics(
            float(metrics_data["next_technique_recall_at_3"]),
            float(metrics_data["brier_score"]),
            float(metrics_data["false_preemption_rate"]),
            float(metrics_data["old_threat_retention"]),
            bool(metrics_data["poison_suite_passed"]),
            int(metrics_data["shadow_cases"]),
        ),
    )
    review = PromotionReview(
        str(review_data["reviewer"]), bool(review_data["approved"]), str(review_data["rationale"])
    )
    registry = ModelGovernanceRegistry(active_version=str(data.get("active_version", "1.0.0")))
    return asdict(registry.review(candidate, review))


def main() -> None:
    parser = argparse.ArgumentParser(description="CloudGuard V5 predictive threat intelligence")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("profile", "preemption", "training-check", "promotion-check"):
        child = sub.add_parser(name)
        child.add_argument("input")
    args = parser.parse_args()
    data = _load(args.input)
    if args.command == "profile":
        payload = _profile_payload(data)
    elif args.command == "preemption":
        payload = _preemption_payload(data)
    elif args.command == "training-check":
        payload = _training_payload(data)
    else:
        payload = _promotion_payload(data)
    print(json.dumps(payload, indent=2, default=str))


if __name__ == "__main__":
    main()
