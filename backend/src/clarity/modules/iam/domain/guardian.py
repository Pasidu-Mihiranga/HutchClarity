"""Guardian delegation: a parent subject may act for a child subscriber_ref after OTP."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

from clarity.kernel.principal import Assurance, Principal, Role


class GuardianError(ValueError):
    """Delegation could not be established or applied."""


@dataclass
class GuardianRegistry:
    """In-memory guardian links: parent_subscriber_ref -> child refs."""

    _links: dict[str, set[str]] = field(default_factory=dict)
    _pending: dict[str, str] = field(default_factory=dict)  # child_msisdn_key -> parent_ref
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def request_link(self, parent_ref: str, child_subscriber_ref: str) -> None:
        """Record intent to link; completed after child OTP verification."""
        if not parent_ref or not child_subscriber_ref:
            raise GuardianError("parent and child refs are required")
        if parent_ref == child_subscriber_ref:
            raise GuardianError("cannot delegate to self")
        with self._lock:
            self._pending[child_subscriber_ref] = parent_ref

    def confirm_after_otp(self, child_subscriber_ref: str) -> str:
        """After OTP on the child number, activate the pending link. Returns parent_ref."""
        with self._lock:
            parent_ref = self._pending.pop(child_subscriber_ref, None)
            if parent_ref is None:
                raise GuardianError("no pending guardian link for this subject")
            self._links.setdefault(parent_ref, set()).add(child_subscriber_ref)
            return parent_ref

    def link_direct(self, parent_ref: str, child_subscriber_ref: str) -> None:
        """Activate a link immediately (demo / already-OTP'd path)."""
        with self._lock:
            self._links.setdefault(parent_ref, set()).add(child_subscriber_ref)

    def children_of(self, parent_ref: str) -> set[str]:
        with self._lock:
            return set(self._links.get(parent_ref, set()))

    def apply(
        self,
        principal: Principal,
        *,
        acting_for: str | None = None,
    ) -> Principal:
        """Return a principal that may act for delegated children.

        If ``acting_for`` is set, it must be in the parent's delegations
        (or freshly linked). The returned principal keeps the parent subject
        and adds the child to ``delegations``.
        """
        if principal.assurance is Assurance.ANONYMOUS:
            raise GuardianError("guardian action requires authenticated principal")

        parent_ref = principal.subscriber_ref or principal.subject
        linked = self.children_of(parent_ref)
        delegations = set(principal.delegations) | linked

        if acting_for is not None:
            if acting_for not in delegations and acting_for != parent_ref:
                raise GuardianError("no guardian link for that subscriber")
            delegations.add(acting_for)

        return Principal.from_roles(
            subject=principal.subject,
            roles=set(principal.roles) or {Role.CUSTOMER},
            subscriber_ref=principal.subscriber_ref or parent_ref,
            assurance=principal.assurance,
            actor_ref=principal.actor_ref or principal.subject,
            delegations=delegations,
        )
