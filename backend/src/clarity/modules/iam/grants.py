"""Audit duties held by grant, under separation of duties (audit assurance plan Phase 3).

A role gives a duty to everyone who holds it. Audit work needs something
narrower: *this* person watches the trail this month, *that* one may export it
for one investigation. A grant gives one audit permission to one named staff
user, or to one role, for a bounded time, and every step of its life is in the
trail.

**The five separation-of-duties rules (plan 5.6).**

1. A monitor cannot move money. Enforced in ``permissions_for``: holding any
   audit duty removes money permissions, by role or by grant.
2. Nobody disposes of an alert in which they are the subject:
   ``is_subject`` is what Phase 4's alert lifecycle checks.
3. Granting audit authority needs two people: a grant is *requested* by one
   holder of ``audit:assign`` and *approved* by a different one.
4. Nobody grants themselves anything, by name or through a role they hold.
5. Audit reads are audited: recorded by the ``GET /v1/audit`` route.

**Break-glass** is the one deliberate exception to rules 3 and 4: an admin
takes a short, self-granted duty for an incident. It is recorded as its own
event so it can never pass unnoticed.

Money is never grantable, and neither is ``audit:assign``
(``GRANTABLE_PERMISSIONS``): the authority to grant comes from a role only.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from datetime import datetime, timedelta
from enum import StrEnum

from clarity.kernel.common import ClarityModel, utc_now
from clarity.kernel.ids import new_id
from clarity.modules.iam.authorization import AuthorizationPolicy
from clarity.platform.audit.ledger import ActorKind, AuditEventType, AuditLedger
from clarity.platform.persistence import Repository, UnitOfWorkFactory
from clarity.platform.security.principal import (
    GRANTABLE_PERMISSIONS,
    MONEY_PERMISSIONS,
    STEP_UP_PERMISSIONS,
    Permission,
    Principal,
    Role,
)

#: One collection is one table in B05.
GRANTS = "iam.grants"


class SubjectKind(StrEnum):
    USER = "user"
    ROLE = "role"


class GrantState(StrEnum):
    PENDING = "pending"
    """Requested, waiting for a second holder of audit:assign."""
    ACTIVE = "active"
    REVOKED = "revoked"


class AuditGrant(ClarityModel):
    grant_id: str
    subject_kind: SubjectKind
    subject_ref: str
    permission: Permission
    reason: str
    duration_seconds: int
    requested_by: str
    requested_at: datetime
    state: GrantState = GrantState.PENDING
    approved_by: str | None = None
    approved_at: datetime | None = None
    expires_at: datetime | None = None
    review_by: datetime | None = None
    """An active grant nobody has recertified by this time lapses."""
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    break_glass: bool = False
    revoked_by: str | None = None
    revoked_at: datetime | None = None
    revoke_reason: str | None = None

    def is_active(self, now: datetime) -> bool:
        return (
            self.state is GrantState.ACTIVE
            and self.expires_at is not None
            and now < self.expires_at
            and (self.review_by is None or now < self.review_by)
        )

    def applies_to(self, principal: Principal) -> bool:
        if self.subject_kind is SubjectKind.USER:
            return self.subject_ref == principal.ref
        return any(role.value == self.subject_ref for role in principal.roles)


class GrantRefused(Exception):
    """A grant operation broke a rule. ``code`` is stable for the API."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code


class GrantNotFound(KeyError):
    pass


def is_subject(principal: Principal, *, subject_ref: str) -> bool:
    """Rule 2: is this principal the person an alert or grant is about?"""
    return principal.ref == subject_ref


class AuditGrants:
    """Requests, approvals, revocations, recertifications and break-glass."""

    def __init__(
        self,
        open_unit: UnitOfWorkFactory,
        *,
        audit: AuditLedger,
        max_duration: Callable[[], timedelta],
        review_interval: Callable[[], timedelta],
        break_glass_duration: Callable[[], timedelta],
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._open_unit = open_unit
        self._audit = audit
        self._max_duration = max_duration
        self._review_interval = review_interval
        self._break_glass_duration = break_glass_duration
        self._clock = clock or utc_now

    # -- reading -------------------------------------------------------------- #

    def all(self) -> list[AuditGrant]:
        with self._open_unit() as unit:
            store: Repository[str, AuditGrant] = unit.repository(GRANTS)
            return store.values()

    def get(self, grant_id: str) -> AuditGrant:
        with self._open_unit() as unit:
            store: Repository[str, AuditGrant] = unit.repository(GRANTS)
            found = store.get(grant_id)
        if found is None:
            raise GrantNotFound(grant_id)
        return found

    def active_for(self, principal: Principal) -> frozenset[Permission]:
        now = self._clock()
        return frozenset(
            g.permission for g in self.all() if g.is_active(now) and g.applies_to(principal)
        )

    def apply(self, principal: Principal) -> Principal:
        """The principal with its active grants attached, for every check after."""
        if not principal.roles or principal.is_customer:
            return principal
        granted = self.active_for(principal)
        return dataclasses.replace(principal, granted=granted) if granted else principal

    # -- the lifecycle ----------------------------------------------------------- #

    def request(
        self,
        by: Principal,
        *,
        subject_kind: SubjectKind,
        subject_ref: str,
        permission: Permission,
        reason: str,
        duration: timedelta,
    ) -> AuditGrant:
        """Rule 3, first half: one holder of audit:assign asks."""
        self._require_assigner(by)
        if permission not in GRANTABLE_PERMISSIONS:
            raise GrantRefused(
                "NOT_GRANTABLE", f"{permission.value} cannot be granted, only held by role"
            )
        if subject_kind is SubjectKind.ROLE:
            try:
                Role(subject_ref)
            except ValueError as error:
                raise GrantRefused("UNKNOWN_ROLE", f"no role {subject_ref!r}") from error
            if subject_ref == Role.CUSTOMER.value:
                raise GrantRefused("NOT_GRANTABLE", "audit duties are for staff only")
        self._refuse_self(by, subject_kind, subject_ref)
        if not reason.strip():
            raise GrantRefused("REASON_REQUIRED", "a grant needs a reason")
        limit = self._max_duration()
        if duration <= timedelta(0) or duration > limit:
            raise GrantRefused(
                "DURATION_OUT_OF_RANGE", f"a grant lasts more than nothing and at most {limit}"
            )
        grant = AuditGrant(
            grant_id=new_id("GRT"),
            subject_kind=subject_kind,
            subject_ref=subject_ref,
            permission=permission,
            reason=reason.strip(),
            duration_seconds=int(duration.total_seconds()),
            requested_by=by.ref,
            requested_at=self._clock(),
        )
        self._save(grant)
        self._record(AuditEventType.GRANT_REQUESTED, by, grant)
        return grant

    def approve(self, by: Principal, grant_id: str) -> AuditGrant:
        """Rule 3, second half: a *different* holder of audit:assign approves."""
        self._require_assigner(by)
        grant = self.get(grant_id)
        if grant.state is not GrantState.PENDING:
            raise GrantRefused("NOT_PENDING", f"grant is {grant.state.value}")
        if by.ref == grant.requested_by:
            raise GrantRefused("FOUR_EYES", "the person who requested a grant cannot approve it")
        self._refuse_self(by, grant.subject_kind, grant.subject_ref)
        now = self._clock()
        expires_at = now + timedelta(seconds=grant.duration_seconds)
        approved = grant.model_copy(
            update={
                "state": GrantState.ACTIVE,
                "approved_by": by.ref,
                "approved_at": now,
                "expires_at": expires_at,
                "review_by": min(expires_at, now + self._review_interval()),
            }
        )
        self._save(approved)
        self._record(AuditEventType.GRANT_APPROVED, by, approved)
        return approved

    def revoke(self, by: Principal, grant_id: str, *, reason: str) -> AuditGrant:
        self._require_assigner(by)
        grant = self.get(grant_id)
        if grant.state is GrantState.REVOKED:
            raise GrantRefused("NOT_ACTIVE", "grant is already revoked")
        if not reason.strip():
            raise GrantRefused("REASON_REQUIRED", "a revocation needs a reason")
        revoked = grant.model_copy(
            update={
                "state": GrantState.REVOKED,
                "revoked_by": by.ref,
                "revoked_at": self._clock(),
                "revoke_reason": reason.strip(),
            }
        )
        self._save(revoked)
        self._record(AuditEventType.GRANT_REVOKED, by, revoked)
        return revoked

    def recertify(self, by: Principal, grant_id: str) -> AuditGrant:
        """Keep an active grant alive for one more review interval, never past expiry."""
        self._require_assigner(by)
        grant = self.get(grant_id)
        now = self._clock()
        if not grant.is_active(now):
            raise GrantRefused("NOT_ACTIVE", "only an active grant can be recertified")
        self._refuse_self(by, grant.subject_kind, grant.subject_ref)
        expires_at = grant.expires_at or now
        recertified = grant.model_copy(
            update={
                "reviewed_by": by.ref,
                "reviewed_at": now,
                "review_by": min(expires_at, now + self._review_interval()),
            }
        )
        self._save(recertified)
        self._record(AuditEventType.GRANT_RECERTIFIED, by, recertified)
        return recertified

    def break_glass(self, by: Principal, *, permission: Permission, reason: str) -> AuditGrant:
        """Immediate, self-granted and short: the incident exception, always recorded."""
        if not by.has(Permission.ADMIN_MANAGE):
            raise GrantRefused("NOT_PERMITTED", "break-glass is for admins")
        if permission not in GRANTABLE_PERMISSIONS:
            raise GrantRefused("NOT_GRANTABLE", f"{permission.value} cannot be granted")
        if not reason.strip():
            raise GrantRefused("REASON_REQUIRED", "break-glass needs a reason")
        now = self._clock()
        grant = AuditGrant(
            grant_id=new_id("GRT"),
            subject_kind=SubjectKind.USER,
            subject_ref=by.ref,
            permission=permission,
            reason=reason.strip(),
            duration_seconds=int(self._break_glass_duration().total_seconds()),
            requested_by=by.ref,
            requested_at=now,
            state=GrantState.ACTIVE,
            approved_by=by.ref,
            approved_at=now,
            expires_at=now + self._break_glass_duration(),
            break_glass=True,
        )
        self._save(grant)
        self._record(AuditEventType.BREAK_GLASS_USED, by, grant)
        return grant

    # -- helpers ------------------------------------------------------------------ #

    @staticmethod
    def _require_assigner(by: Principal) -> None:
        if not by.has(Permission.AUDIT_ASSIGN):
            raise GrantRefused("NOT_PERMITTED", "this account may not assign audit duties")

    @staticmethod
    def _refuse_self(by: Principal, kind: SubjectKind, subject_ref: str) -> None:
        """Rule 4: not by name, and not through a role you hold."""
        if kind is SubjectKind.USER and subject_ref == by.ref:
            raise GrantRefused("SELF_GRANT", "nobody may grant themselves an audit duty")
        if kind is SubjectKind.ROLE and any(role.value == subject_ref for role in by.roles):
            raise GrantRefused(
                "SELF_GRANT", "nobody may grant a duty to a role they hold themselves"
            )

    def _save(self, grant: AuditGrant) -> None:
        with self._open_unit() as unit:
            store: Repository[str, AuditGrant] = unit.repository(GRANTS)
            store.put(grant.grant_id, grant)
            unit.commit()

    def _record(self, event_type: AuditEventType, by: Principal, grant: AuditGrant) -> None:
        self._audit.append(
            event_type,
            actor_ref=by.ref,
            actor_kind=ActorKind.STAFF,
            object_ref=grant.grant_id,
            payload=grant.model_dump(mode="json"),
            detail={
                "subject": f"{grant.subject_kind.value}:{grant.subject_ref}",
                "permission": grant.permission.value,
                "state": grant.state.value,
                "reason": grant.reason,
                "expires_at": grant.expires_at.isoformat() if grant.expires_at else None,
                "break_glass": grant.break_glass,
            },
        )


class GrantAwareAuthorizationPolicy:
    """Wraps any authorization driver so grants and rule 1 hold under it too.

    The OPA driver sends roles, not grants, so on its own it would refuse a
    granted duty and could allow money to someone who holds a granted one.
    """

    def __init__(self, inner: AuthorizationPolicy) -> None:
        self._inner = inner

    def allows(self, principal: Principal, permission: Permission) -> bool:
        if permission in MONEY_PERMISSIONS and principal.granted:
            return False
        if permission in principal.granted:
            return permission not in STEP_UP_PERMISSIONS or principal.assurance.is_step_up
        return self._inner.allows(principal, permission)


__all__ = [
    "GRANTS",
    "AuditGrant",
    "AuditGrants",
    "GrantAwareAuthorizationPolicy",
    "GrantNotFound",
    "GrantRefused",
    "GrantState",
    "SubjectKind",
    "is_subject",
]
