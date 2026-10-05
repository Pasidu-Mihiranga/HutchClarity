"""Role permission overrides on the static baseline (ADR-0045).

Platform admin attaches or detaches closed ``Permission`` values on closed
``Role`` values. Effective permissions for a role are
``(baseline ∪ attached) − detached``. Money cannot land on an admin role;
``audit:assign``, ``audit:restore`` and ``iam:role:manage`` stay baseline-only.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from pydantic import Field

from clarity.kernel.common import ClarityModel, utc_now
from clarity.platform.audit.ledger import ActorKind, AuditEventType, AuditLedger
from clarity.platform.persistence.ports import Repository, UnitOfWorkFactory
from clarity.platform.security.principal import (
    MONEY_PERMISSIONS,
    ROLE_PERMISSIONS,
    ROLE_POLICY_LOCKED,
    Permission,
    Role,
    RoleOverrideSnapshot,
)

ROLE_POLICIES = "iam.role_policies"
ROLE_POLICY_IDEMPOTENCY = "iam.role_policy_idempotency"


class RolePolicyRefused(Exception):
    """An attach/detach broke a rule. ``code`` is stable for the API."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code


class RolePolicyOverride(ClarityModel):
    """Persisted attach/detach sets for one role."""

    role: Role
    attached: list[Permission] = Field(default_factory=list)
    detached: list[Permission] = Field(default_factory=list)
    updated_at: datetime | None = None
    updated_by: str | None = None


class RolePolicyIdempotencyRecord(ClarityModel):
    key: str
    operation: str
    role: Role
    permission: Permission
    result: dict[str, Any]


class RolePolicies:
    """Read and mutate the override layer; expose snapshots for authz."""

    def __init__(
        self,
        open_unit: UnitOfWorkFactory,
        *,
        audit: AuditLedger,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._open_unit = open_unit
        self._audit = audit
        self._clock = clock or utc_now

    def snapshot(self) -> RoleOverrideSnapshot:
        out: RoleOverrideSnapshot = {}
        with self._open_unit() as unit:
            store: Repository[str, RolePolicyOverride] = unit.repository(ROLE_POLICIES)
            for row in store.values():
                out[row.role] = (
                    frozenset(row.attached),
                    frozenset(row.detached),
                )
        return out

    def catalogue(self) -> dict[str, Any]:
        """Roles, permissions, and the effective matrix for the console."""
        snap = self.snapshot()
        roles = []
        for role in Role:
            attached, detached = snap.get(role, (frozenset(), frozenset()))
            baseline = ROLE_PERMISSIONS.get(role, frozenset())
            effective = (baseline | attached) - detached
            roles.append(
                {
                    "role": role.value,
                    "is_admin": role.is_admin,
                    "baseline": sorted(p.value for p in baseline),
                    "attached": sorted(p.value for p in attached),
                    "detached": sorted(p.value for p in detached),
                    "effective": sorted(p.value for p in effective),
                }
            )
        return {
            "roles": roles,
            "permissions": sorted(p.value for p in Permission),
            "locked_permissions": sorted(p.value for p in ROLE_POLICY_LOCKED),
            "money_permissions": sorted(p.value for p in MONEY_PERMISSIONS),
        }

    def attach(
        self,
        *,
        role: Role,
        permission: Permission,
        actor_ref: str,
        reason: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return self._mutate(
            operation="attach",
            role=role,
            permission=permission,
            actor_ref=actor_ref,
            reason=reason,
            idempotency_key=idempotency_key,
        )

    def detach(
        self,
        *,
        role: Role,
        permission: Permission,
        actor_ref: str,
        reason: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return self._mutate(
            operation="detach",
            role=role,
            permission=permission,
            actor_ref=actor_ref,
            reason=reason,
            idempotency_key=idempotency_key,
        )

    def _mutate(
        self,
        *,
        operation: str,
        role: Role,
        permission: Permission,
        actor_ref: str,
        reason: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        if not reason.strip():
            raise RolePolicyRefused("REASON_REQUIRED", "a reason is required")
        prior = self._idempotent_hit(idempotency_key, operation, role, permission)
        if prior is not None:
            return prior

        self._refuse_illegal(operation, role, permission)

        now = self._clock()
        with self._open_unit() as unit:
            store: Repository[str, RolePolicyOverride] = unit.repository(ROLE_POLICIES)
            row = store.get(role.value) or RolePolicyOverride(role=role)
            attached = set(row.attached)
            detached = set(row.detached)
            if operation == "attach":
                detached.discard(permission)
                attached.add(permission)
            else:
                attached.discard(permission)
                # Detach means "not effective", including baseline members.
                detached.add(permission)
            row = RolePolicyOverride(
                role=role,
                attached=sorted(attached, key=lambda p: p.value),
                detached=sorted(detached, key=lambda p: p.value),
                updated_at=now,
                updated_by=actor_ref,
            )
            store.put(role.value, row)
            unit.commit()

        baseline = ROLE_PERMISSIONS.get(role, frozenset())
        attached_set = frozenset(row.attached)
        detached_set = frozenset(row.detached)
        result = {
            "role": role.value,
            "permission": permission.value,
            "operation": operation,
            "reason": reason.strip(),
            "baseline": sorted(p.value for p in baseline),
            "attached": [p.value for p in row.attached],
            "detached": [p.value for p in row.detached],
            "effective": sorted(p.value for p in (baseline | attached_set) - detached_set),
            "replayed": False,
        }
        self._record_idempotency(idempotency_key, operation, role, permission, result)
        self._audit.append(
            AuditEventType.ROLE_POLICY_ATTACHED
            if operation == "attach"
            else AuditEventType.ROLE_POLICY_DETACHED,
            actor_ref=actor_ref,
            actor_kind=ActorKind.STAFF,
            object_ref=f"{role.value}:{permission.value}",
            payload={
                "role": role.value,
                "permission": permission.value,
                "operation": operation,
                "reason": reason.strip(),
            },
            detail={"idempotency_key": idempotency_key},
            now=now,
        )
        return result

    def _refuse_illegal(self, operation: str, role: Role, permission: Permission) -> None:
        if permission in ROLE_POLICY_LOCKED:
            raise RolePolicyRefused(
                "PERMISSION_LOCKED",
                f"{permission.value} stays on the checked-in baseline only",
            )
        if operation == "attach" and permission in MONEY_PERMISSIONS and role.is_admin:
            raise RolePolicyRefused(
                "ADMIN_MONEY_DENIED",
                "money permissions cannot be attached to an admin role",
            )

    def _idempotent_hit(
        self,
        key: str,
        operation: str,
        role: Role,
        permission: Permission,
    ) -> dict[str, Any] | None:
        with self._open_unit() as unit:
            store: Repository[str, RolePolicyIdempotencyRecord] = unit.repository(
                ROLE_POLICY_IDEMPOTENCY
            )
            found = store.get(key)
        if found is None:
            return None
        if (
            found.operation != operation
            or found.role != role
            or found.permission != permission
        ):
            raise RolePolicyRefused(
                "IDEMPOTENCY_CONFLICT",
                "this Idempotency-Key was used for a different IAM change",
            )
        replayed = dict(found.result)
        replayed["replayed"] = True
        return replayed

    def _record_idempotency(
        self,
        key: str,
        operation: str,
        role: Role,
        permission: Permission,
        result: dict[str, Any],
    ) -> None:
        with self._open_unit() as unit:
            store: Repository[str, RolePolicyIdempotencyRecord] = unit.repository(
                ROLE_POLICY_IDEMPOTENCY
            )
            store.put(
                key,
                RolePolicyIdempotencyRecord(
                    key=key,
                    operation=operation,
                    role=role,
                    permission=permission,
                    result={k: v for k, v in result.items() if k != "replayed"},
                ),
            )
            unit.commit()


__all__ = [
    "ROLE_POLICIES",
    "ROLE_POLICY_IDEMPOTENCY",
    "RolePolicies",
    "RolePolicyIdempotencyRecord",
    "RolePolicyOverride",
    "RolePolicyRefused",
]
