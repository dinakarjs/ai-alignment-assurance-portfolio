"""Causal/delegation validation for multi-agent trace events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True)
class CausalTraceFinding:
    event_index: int
    code: str
    detail: str


@dataclass(frozen=True)
class CausalTraceValidation:
    valid: bool
    findings: tuple[CausalTraceFinding, ...]


def _constraints_subset(child: Mapping[str, object], parent: Mapping[str, object]) -> bool:
    """Conservative subset check for equality/list and scalar min/max constraints."""

    for key, child_value in child.items():
        if key not in parent:
            return False
        parent_value = parent[key]
        if isinstance(parent_value, Mapping) and isinstance(child_value, Mapping):
            if set(parent_value).issubset({"min", "max"}) and set(child_value).issubset({"min", "max"}):
                parent_min = parent_value.get("min")
                parent_max = parent_value.get("max")
                child_min = child_value.get("min")
                child_max = child_value.get("max")
                if parent_min is not None and (child_min is None or child_min < parent_min):  # type: ignore[operator]
                    return False
                if parent_max is not None and (child_max is None or child_max > parent_max):  # type: ignore[operator]
                    return False
                continue
            if not _constraints_subset(child_value, parent_value):
                return False
            continue
        if isinstance(parent_value, list):
            if isinstance(child_value, list):
                if not set(child_value).issubset(set(parent_value)):
                    return False
            elif child_value not in parent_value:
                return False
            continue
        if child_value != parent_value:
            return False
    return True


def validate_causal_trace(events: Sequence[Mapping[str, object]]) -> CausalTraceValidation:
    findings: list[CausalTraceFinding] = []
    seen_event_ids: set[str] = set()
    capabilities: dict[str, dict[str, object]] = {}

    for index, event in enumerate(events):
        event_id_raw = event.get("event_id")
        event_id = str(event_id_raw).strip() if event_id_raw is not None else ""
        if event_id:
            if event_id in seen_event_ids:
                findings.append(CausalTraceFinding(index, "DUPLICATE_EVENT_ID", f"duplicate event_id {event_id!r}"))
            seen_event_ids.add(event_id)

        parent_raw = event.get("parent_event_id")
        if parent_raw is not None:
            parent = str(parent_raw).strip()
            if parent and parent not in seen_event_ids:
                findings.append(
                    CausalTraceFinding(
                        index,
                        "UNKNOWN_PARENT_EVENT",
                        f"parent_event_id {parent!r} was not observed earlier in the trace",
                    )
                )

        if str(event.get("type", "")).strip().lower() != "delegate":
            continue
        capability_id = str(event.get("capability_id", "")).strip()
        if not capability_id:
            findings.append(CausalTraceFinding(index, "MISSING_CAPABILITY_ID", "delegate event requires capability_id"))
            continue
        if capability_id in capabilities:
            findings.append(CausalTraceFinding(index, "DUPLICATE_CAPABILITY_ID", f"capability_id {capability_id!r} already exists"))
            continue
        constraints = event.get("constraints", {})
        if not isinstance(constraints, Mapping):
            findings.append(CausalTraceFinding(index, "MALFORMED_CONSTRAINTS", "delegation constraints must be an object"))
            continue
        parent_capability_id = event.get("parent_capability_id")
        if parent_capability_id is not None:
            parent_id = str(parent_capability_id).strip()
            parent_capability = capabilities.get(parent_id)
            if parent_capability is None:
                findings.append(
                    CausalTraceFinding(
                        index,
                        "UNKNOWN_PARENT_CAPABILITY",
                        f"parent capability {parent_id!r} was not previously delegated",
                    )
                )
            else:
                if str(event.get("action", "")) != str(parent_capability.get("action", "")):
                    findings.append(
                        CausalTraceFinding(index, "PRIVILEGE_AMPLIFICATION", "delegated action differs from parent capability")
                    )
                parent_constraints = parent_capability.get("constraints", {})
                if isinstance(parent_constraints, Mapping) and not _constraints_subset(constraints, parent_constraints):
                    findings.append(
                        CausalTraceFinding(
                            index,
                            "PRIVILEGE_AMPLIFICATION",
                            "delegated constraints are broader than the parent capability",
                        )
                    )
        capabilities[capability_id] = {
            "action": event.get("action"),
            "constraints": dict(constraints),
            "principal": event.get("principal_id", event.get("agent_id")),
        }

    return CausalTraceValidation(valid=not findings, findings=tuple(findings))
