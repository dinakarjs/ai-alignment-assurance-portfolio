"""Versioned schema/policy registry with controlled activation and compatibility checks."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
from typing import Mapping

from .result_integrity import sha256_object


class Compatibility(str, Enum):
    BACKWARD_COMPATIBLE = "BACKWARD_COMPATIBLE"
    MIGRATION_REQUIRED = "MIGRATION_REQUIRED"
    BREAKING = "BREAKING"
    SECURITY_SENSITIVE = "SECURITY_SENSITIVE"


@dataclass(frozen=True)
class SchemaDescriptor:
    kind: str
    version: str
    digest: str
    status: str
    path: str
    previous_version: str | None = None
    compatibility: Compatibility | None = None
    proposer: str | None = None
    approver: str | None = None


class SchemaRegistry:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.registry_path = self.root / "registry.json"

    def _load_registry(self) -> dict[str, object]:
        if not self.registry_path.exists():
            return {"active": {}, "entries": []}
        value = json.loads(self.registry_path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("schema registry must be a JSON object")
        return value

    def _save_registry(self, value: Mapping[str, object]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.registry_path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    @staticmethod
    def validate_document(document: Mapping[str, object]) -> None:
        required = {"$schema", "$id", "type"}
        missing = required - set(document)
        if missing:
            raise ValueError(f"schema missing required fields: {', '.join(sorted(missing))}")
        if document.get("type") != "object":
            raise ValueError("top-level schema type must be object")
        properties = document.get("properties")
        if properties is not None and not isinstance(properties, Mapping):
            raise ValueError("schema properties must be an object")

    @staticmethod
    def classify_change(old: Mapping[str, object], new: Mapping[str, object]) -> Compatibility:
        old_required = set(old.get("required", []))
        new_required = set(new.get("required", []))
        old_props = old.get("properties", {})
        new_props = new.get("properties", {})
        if not isinstance(old_props, Mapping) or not isinstance(new_props, Mapping):
            return Compatibility.BREAKING
        removed = set(old_props) - set(new_props)
        if removed:
            return Compatibility.SECURITY_SENSITIVE
        if new_required - old_required:
            return Compatibility.MIGRATION_REQUIRED
        for key in set(old_props) & set(new_props):
            old_type = old_props[key].get("type") if isinstance(old_props[key], Mapping) else None
            new_type = new_props[key].get("type") if isinstance(new_props[key], Mapping) else None
            if old_type != new_type:
                return Compatibility.BREAKING
        return Compatibility.BACKWARD_COMPATIBLE

    def propose(
        self,
        *,
        kind: str,
        version: str,
        document: Mapping[str, object],
        proposer: str,
        previous_version: str | None = None,
    ) -> SchemaDescriptor:
        self.validate_document(document)
        registry = self._load_registry()
        entries = list(registry.get("entries", []))
        if any(isinstance(item, Mapping) and item.get("kind") == kind and item.get("version") == version for item in entries):
            raise ValueError(f"schema {kind}/{version} already exists")
        relative = Path(kind) / f"{version}.json"
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        compatibility = None
        if previous_version:
            previous_path = self.root / kind / f"{previous_version}.json"
            if not previous_path.exists():
                raise ValueError("previous schema version does not exist")
            old = json.loads(previous_path.read_text(encoding="utf-8"))
            compatibility = self.classify_change(old, document)
        descriptor = SchemaDescriptor(
            kind=kind,
            version=version,
            digest=sha256_object(document),
            status="PROPOSED",
            path=str(relative),
            previous_version=previous_version,
            compatibility=compatibility,
            proposer=proposer,
        )
        entries.append({**descriptor.__dict__, "compatibility": compatibility.value if compatibility else None})
        registry["entries"] = entries
        self._save_registry(registry)
        return descriptor

    def approve_and_activate(self, kind: str, version: str, approver: str) -> SchemaDescriptor:
        registry = self._load_registry()
        entries = list(registry.get("entries", []))
        target_index = None
        target = None
        for index, item in enumerate(entries):
            if isinstance(item, dict) and item.get("kind") == kind and item.get("version") == version:
                target_index, target = index, item
                break
        if target is None or target_index is None:
            raise ValueError("schema version not found")
        proposer = str(target.get("proposer", "")).strip().lower()
        if proposer and proposer == approver.strip().lower():
            raise ValueError("schema proposer and approver must be independent")
        target = dict(target)
        target["status"] = "ACTIVE"
        target["approver"] = approver
        entries[target_index] = target
        active = dict(registry.get("active", {}))
        active[kind] = version
        registry["entries"] = entries
        registry["active"] = active
        self._save_registry(registry)
        compatibility = target.get("compatibility")
        return SchemaDescriptor(
            kind=kind,
            version=version,
            digest=str(target["digest"]),
            status="ACTIVE",
            path=str(target["path"]),
            previous_version=target.get("previous_version"),
            compatibility=Compatibility(str(compatibility)) if compatibility else None,
            proposer=target.get("proposer"),
            approver=approver,
        )
