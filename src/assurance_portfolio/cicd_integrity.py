"""CI/CD integrity controls for AI-assisted workflows.

The AI agent is treated as an untrusted planner inside a potentially privileged
runner. Untrusted triggers/data must not silently inherit repository/cloud
permissions or cross the promotion boundary into production.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence


class CICDDecision(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    ESCALATE = "ESCALATE"


class TriggerTrust(str, Enum):
    TRUSTED = "TRUSTED"
    UNTRUSTED = "UNTRUSTED"


@dataclass(frozen=True)
class WorkflowContext:
    workflow_name: str
    trigger: str
    trigger_trust: TriggerTrust
    source_ref: str
    trusted_control_ref: str
    actor: str
    agent_principal: str
    requested_action: str
    requested_permissions: tuple[str, ...] = ()
    runner_permissions: tuple[str, ...] = ()
    secret_names: tuple[str, ...] = ()
    modifies_workflow: bool = False
    modifies_policy: bool = False
    production_effect: bool = False
    artifact_digest: str | None = None
    reviewed_artifact_digest: str | None = None
    approver: str | None = None
    approver_trust_domain: str | None = None
    agent_trust_domain: str | None = None


@dataclass(frozen=True)
class CICDViolation:
    check: str
    detail: str


@dataclass(frozen=True)
class CICDIntegrityReport:
    decision: CICDDecision
    violations: tuple[CICDViolation, ...]
    required_checks: tuple[str, ...]
    executed_checks: tuple[str, ...]


REQUIRED_CHECKS = (
    "untrusted_trigger_cannot_start_privileged_workflow",
    "workflow_definition_must_come_from_trusted_ref",
    "agent_cannot_modify_its_own_policy_or_guardrails",
    "agent_cannot_access_secret_without_explicit_capability",
    "agent_cannot_escalate_repository_permissions",
    "privileged_shell_command_requires_runtime_authorization",
    "deployment_requires_independent_approval",
    "production_credential_cannot_enter_untrusted_agent_context",
    "artifact_must_match_reviewed_commit",
    "security_check_failure_cannot_be_self_waived",
)


def _is_privileged_permission(permission: str) -> bool:
    value = permission.strip().lower()
    return value.endswith(":write") or value in {
        "write",
        "admin",
        "id-token:write",
        "deploy",
        "packages:write",
        "contents:write",
        "pull-requests:write",
        "actions:write",
    }


def validate_cicd_integrity(context: WorkflowContext) -> CICDIntegrityReport:
    violations: list[CICDViolation] = []
    privileged_runner = any(_is_privileged_permission(item) for item in context.runner_permissions)
    privileged_requested = any(_is_privileged_permission(item) for item in context.requested_permissions)

    if context.trigger_trust is TriggerTrust.UNTRUSTED and privileged_runner:
        violations.append(
            CICDViolation(
                "untrusted_trigger_cannot_start_privileged_workflow",
                "untrusted trigger reached a runner with privileged repository/cloud permissions",
            )
        )

    if context.source_ref != context.trusted_control_ref and (
        context.modifies_workflow or context.modifies_policy or context.production_effect
    ):
        violations.append(
            CICDViolation(
                "workflow_definition_must_come_from_trusted_ref",
                "privileged control or production operation is not executing from the trusted control ref",
            )
        )

    if context.modifies_workflow or context.modifies_policy:
        violations.append(
            CICDViolation(
                "agent_cannot_modify_its_own_policy_or_guardrails",
                "AI agent attempted to modify workflow/policy controls governing its own execution",
            )
        )

    if context.secret_names and context.trigger_trust is TriggerTrust.UNTRUSTED:
        violations.append(
            CICDViolation(
                "production_credential_cannot_enter_untrusted_agent_context",
                "secrets are present in an untrusted-trigger agent context",
            )
        )

    if context.secret_names and not any(
        permission.startswith("secret:") for permission in context.requested_permissions
    ):
        violations.append(
            CICDViolation(
                "agent_cannot_access_secret_without_explicit_capability",
                "secret access exists without an explicit secret capability",
            )
        )

    runner_set = set(context.runner_permissions)
    requested_set = set(context.requested_permissions)
    if requested_set - runner_set:
        violations.append(
            CICDViolation(
                "agent_cannot_escalate_repository_permissions",
                "requested permissions exceed runner-granted permissions",
            )
        )

    if privileged_requested and context.trigger_trust is TriggerTrust.UNTRUSTED:
        violations.append(
            CICDViolation(
                "privileged_shell_command_requires_runtime_authorization",
                "untrusted-trigger agent requested privileged execution",
            )
        )

    if context.production_effect:
        if not context.approver:
            violations.append(
                CICDViolation(
                    "deployment_requires_independent_approval",
                    "production effect lacks an independent approver",
                )
            )
        elif context.approver.strip().lower() == context.actor.strip().lower():
            violations.append(
                CICDViolation(
                    "deployment_requires_independent_approval",
                    "actor cannot self-approve production promotion",
                )
            )
        elif (
            context.agent_trust_domain
            and context.approver_trust_domain
            and context.agent_trust_domain.strip().lower()
            == context.approver_trust_domain.strip().lower()
        ):
            violations.append(
                CICDViolation(
                    "deployment_requires_independent_approval",
                    "production promotion approver is not in an independent trust domain",
                )
            )

    if context.production_effect and (
        not context.artifact_digest
        or not context.reviewed_artifact_digest
        or context.artifact_digest != context.reviewed_artifact_digest
    ):
        violations.append(
            CICDViolation(
                "artifact_must_match_reviewed_commit",
                "production artifact digest does not match the independently reviewed artifact",
            )
        )

    if violations:
        hard_block = any(
            item.check
            in {
                "untrusted_trigger_cannot_start_privileged_workflow",
                "agent_cannot_modify_its_own_policy_or_guardrails",
                "production_credential_cannot_enter_untrusted_agent_context",
                "agent_cannot_escalate_repository_permissions",
                "artifact_must_match_reviewed_commit",
            }
            for item in violations
        )
        decision = CICDDecision.BLOCK if hard_block else CICDDecision.ESCALATE
    else:
        decision = CICDDecision.ALLOW

    return CICDIntegrityReport(
        decision=decision,
        violations=tuple(violations),
        required_checks=REQUIRED_CHECKS,
        executed_checks=REQUIRED_CHECKS,
    )
