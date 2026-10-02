"""Public facade for the customer module."""

from __future__ import annotations

import threading
from typing import Any

from clarity.modules.customer.domain.safeguards import Safeguards

_lock = threading.Lock()
_store: dict[str, Safeguards] = {}


def get_safeguards(subscriber_ref: str) -> Safeguards:
    """Return safeguards for a subscriber, creating defaults if absent."""
    ref = subscriber_ref.strip()
    if not ref:
        raise ValueError("subscriber_ref is required")
    with _lock:
        existing = _store.get(ref)
        if existing is None:
            existing = Safeguards.defaults(ref)
            _store[ref] = existing
        return existing


def put_safeguards(
    subscriber_ref: str,
    *,
    spend_cap_lkr: Any | None = None,
    quiet_hours: dict[str, Any] | None = None,
    language: str | None = None,
    allow_auto_refund: bool | None = None,
) -> Safeguards:
    """Replace or patch safeguards for a subscriber."""
    current = get_safeguards(subscriber_ref)
    payload = current.to_dict()
    if spend_cap_lkr is not None:
        payload["spend_cap_lkr"] = spend_cap_lkr
    if quiet_hours is not None:
        payload["quiet_hours"] = quiet_hours
    if language is not None:
        payload["language"] = language
    if allow_auto_refund is not None:
        payload["allow_auto_refund"] = allow_auto_refund
    updated = Safeguards.from_dict(subscriber_ref.strip(), payload)
    with _lock:
        _store[updated.subscriber_ref] = updated
    return updated


def reset_safeguards() -> None:
    """Clear in-memory store (tests)."""
    with _lock:
        _store.clear()


__all__ = [
    "Safeguards",
    "get_safeguards",
    "put_safeguards",
    "reset_safeguards",
]
