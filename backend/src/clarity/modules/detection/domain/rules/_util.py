"""Shared helpers for timeline-dict detectors."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any


def events(timeline: dict[str, Any], key: str) -> list[dict[str, Any]]:
    raw = timeline.get(key) or []
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def as_money(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except Exception:  # noqa: BLE001
        return None


def parse_ts(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def within_seconds(a: Any, b: Any, window: int) -> bool:
    ta, tb = parse_ts(a), parse_ts(b)
    if ta is None or tb is None:
        return False
    return abs((ta - tb).total_seconds()) <= window


def has_field(items: list[dict[str, Any]], **matches: Any) -> bool:
    for item in items:
        if all(item.get(k) == v for k, v in matches.items()):
            return True
    return False


def any_matching(items: list[dict[str, Any]], predicate) -> list[dict[str, Any]]:
    return [item for item in items if predicate(item)]
