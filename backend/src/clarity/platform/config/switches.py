"""Kill switches: stopping something in seconds, without a deploy.

Our own FR-GOV-04 requires these and we had never built them. They exist for
the case the deck's rollout plan implies but does not spell out: a rule
misfires at 03:00 and someone has to stop it refunding before anyone can ship
code.

A switch is deliberately the *blunt* instrument. Turning one off never breaks
the customer journey - it degrades it. ``auto_fix_global`` off means fixes go
to staff, not that they stop. ``llm_explanations`` off means templates, which
is the path the deck already requires (S7).

Every flip is written to the audit ledger, because "who turned this off and
when" is the first question after an incident.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from clarity.kernel.common import utc_now


class Switch(StrEnum):
    """The switches the plan names (§19 4.2)."""

    AUTO_FIX_GLOBAL = "auto_fix_global"
    """Off: nothing auto-fixes; every fix needs a human."""

    CUSTOMER_ACTIONS = "customer_actions"
    """Off: customers cannot confirm anything; explain and hand off only."""

    LLM_EXPLANATIONS = "llm_explanations"
    """Off: templates only, whatever the gateway is configured with."""

    PROACTIVE_MESSAGES = "proactive_messages"
    """Off: no outbound proactive notifications."""


def auto_fix_switch(rule_id: str) -> str:
    """Per-rule kill switch, e.g. ``auto_fix.DUPLICATE_RELOAD``."""
    return f"auto_fix.{rule_id}"


@dataclass(frozen=True)
class SwitchFlip:
    """An audited change of a switch."""

    name: str
    enabled: bool
    actor_ref: str
    reason: str
    at: datetime


class SwitchBoard:
    """Holds switch state. Everything is on unless someone turned it off."""

    def __init__(
        self,
        *,
        audit_sink: object | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._off: dict[str, SwitchFlip] = {}
        self._history: list[SwitchFlip] = []
        self._lock = threading.Lock()
        self._audit = audit_sink
        #: Time comes from the injected clock (I11). Without it a flip stamped
        #: from the wall clock lands outside a replay's window, and any rule
        #: that joins a flip to what happened between two of them, such as
        #: ``switch_then_pay``, silently sees nothing.
        self._clock = clock or utc_now

    def is_on(self, name: str | Switch) -> bool:
        return str(name) not in self._off

    def is_off(self, name: str | Switch) -> bool:
        return not self.is_on(name)

    def auto_fix_allowed(self, rule_id: str | None) -> bool:
        """Auto-fix needs both the global switch and the rule's own switch."""
        if self.is_off(Switch.AUTO_FIX_GLOBAL):
            return False
        return not (rule_id is not None and self.is_off(auto_fix_switch(rule_id)))

    def turn_off(
        self, name: str | Switch, *, actor_ref: str, reason: str, now: datetime | None = None
    ) -> SwitchFlip:
        return self._flip(str(name), enabled=False, actor_ref=actor_ref, reason=reason, now=now)

    def turn_on(
        self, name: str | Switch, *, actor_ref: str, reason: str, now: datetime | None = None
    ) -> SwitchFlip:
        return self._flip(str(name), enabled=True, actor_ref=actor_ref, reason=reason, now=now)

    def _flip(
        self, name: str, *, enabled: bool, actor_ref: str, reason: str, now: datetime | None
    ) -> SwitchFlip:
        if not reason.strip():
            raise ValueError("a switch flip must record why")

        flip = SwitchFlip(
            name=name,
            enabled=enabled,
            actor_ref=actor_ref,
            reason=reason,
            at=now or self._clock(),
        )
        with self._lock:
            if enabled:
                self._off.pop(name, None)
            else:
                self._off[name] = flip
            self._history.append(flip)

        self._record_audit(flip)
        return flip

    def _record_audit(self, flip: SwitchFlip) -> None:
        if self._audit is None:
            return
        # Imported lazily so the switchboard stays usable without the ledger.
        from clarity.platform.audit.ledger import AuditEventType, AuditLedger

        if isinstance(self._audit, AuditLedger):
            self._audit.append(
                AuditEventType.OVERRIDE_RECORDED,
                actor_ref=flip.actor_ref,
                object_ref=f"switch:{flip.name}",
                payload={"switch": flip.name, "enabled": flip.enabled, "reason": flip.reason},
                detail={"reason": flip.reason, "enabled": flip.enabled},
                now=flip.at,
            )

    @property
    def disabled(self) -> list[str]:
        return sorted(self._off)

    @property
    def history(self) -> list[SwitchFlip]:
        return list(self._history)


@dataclass
class SwitchState:
    """Immutable view handed to a decision, so it cannot change mid-evaluation."""

    auto_fix_global: bool = True
    customer_actions: bool = True
    rule_auto_fix: bool = True
    disabled: list[str] = field(default_factory=list)

    @classmethod
    def of(cls, board: SwitchBoard, *, rule_id: str | None) -> SwitchState:
        return cls(
            auto_fix_global=board.is_on(Switch.AUTO_FIX_GLOBAL),
            customer_actions=board.is_on(Switch.CUSTOMER_ACTIONS),
            rule_auto_fix=(True if rule_id is None else board.is_on(auto_fix_switch(rule_id))),
            disabled=board.disabled,
        )

    @property
    def auto_fix_allowed(self) -> bool:
        return self.auto_fix_global and self.rule_auto_fix
