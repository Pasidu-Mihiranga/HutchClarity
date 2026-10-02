"""The recurrence test: "PASSED only if really blocked" (deck S6).

A receipt that claims a safeguard is in place without checking would be worse
than no receipt, so this re-reads live state *after* the action and reports
what it finds. If the state cannot be read, the result is ``UNAVAILABLE``,
never an optimistic pass.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from clarity.contracts.decision import ActionType
from clarity.contracts.receipt import RecurrenceResult

#: Safeguard action -> the named check that proves it took effect.
#: Rule packs refer to these names in their ``recurrence_check`` field.
CHECK_FOR_ACTION: dict[ActionType, str] = {
    ActionType.BLOCK_MERCHANT_UNTIL_OPTIN: "merchant_block_active",
    ActionType.DEACTIVATE_VAS: "subscription_inactive",
    ActionType.ENABLE_DATA_STOP: "data_stop_active",
    ActionType.SET_SPEND_CAP: "spend_cap_active",
    ActionType.ENABLE_FUP_ALERTS: "fup_alerts_active",
}


@runtime_checkable
class RecurrenceProbe(Protocol):
    """Re-reads state to confirm a safeguard is really in force."""

    def check(self, name: str, subscriber_ref: str, params: dict[str, object]) -> bool | None:
        """``True`` in force, ``False`` not in force, ``None`` cannot tell."""


def run_check(
    probe: RecurrenceProbe | None,
    name: str | None,
    subscriber_ref: str,
    params: dict[str, object],
) -> RecurrenceResult:
    """Translate a probe answer into a receipt-safe result."""
    if name is None:
        return RecurrenceResult.NOT_APPLICABLE
    if probe is None:
        return RecurrenceResult.UNAVAILABLE

    try:
        answer = probe.check(name, subscriber_ref, params)
    except Exception:
        return RecurrenceResult.UNAVAILABLE

    if answer is None:
        return RecurrenceResult.UNAVAILABLE
    return RecurrenceResult.PASSED if answer else RecurrenceResult.FAILED
