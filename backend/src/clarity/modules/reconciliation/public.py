"""Public facade for the reconciliation module."""

from __future__ import annotations

from datetime import date
from typing import Any

from clarity.kernel.common import utc_now
from clarity.modules.actions.public import get_tool_layer
from clarity.modules.reconciliation.domain.matcher import (
    Mismatch,
    ReconciliationStore,
    match_actions,
)

_store = ReconciliationStore()


def get_recon_store() -> ReconciliationStore:
    return _store


def reset_reconciliation() -> None:
    _store.clear()


def add_adapter_confirmation(confirmation: dict[str, Any]) -> None:
    _store.add_confirmation(confirmation)


def run_reconciliation(day: str | date | None = None) -> list[dict[str, Any]]:
    """Match day's executed actions to adapter confirmations; return mismatches."""
    if day is None:
        day_str = utc_now().date().isoformat()
    elif isinstance(day, date):
        day_str = day.isoformat()
    else:
        day_str = str(day)

    actions = get_tool_layer().list_executed(day=day_str)
    # Confirmations may carry a day field; otherwise include all.
    confirmations = [
        c
        for c in _store.confirmations
        if not c.get("day") or str(c.get("day")) == day_str
    ]
    mismatches = match_actions(actions, confirmations)
    return [m.to_dict() for m in mismatches]


__all__ = [
    "Mismatch",
    "add_adapter_confirmation",
    "get_recon_store",
    "match_actions",
    "reset_reconciliation",
    "run_reconciliation",
]
