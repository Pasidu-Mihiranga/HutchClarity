"""Context-aware suggestion chips from synthetic account signals."""

from __future__ import annotations

from typing import Any

from clarity.core.conversation.intents import TOPIC_CATALOGUE, Intent


def _topic(topic_id: str) -> dict[str, str] | None:
    for item in TOPIC_CATALOGUE:
        if item["id"] == topic_id:
            return dict(item)
    return None


def build_suggestions(
    signals: dict[str, Any] | None = None,
    *,
    language: str = "en",
    limit: int = 6,
) -> dict[str, Any]:
    """Return 4–6 primary chips plus more_topics from the full catalogue.

    ``signals`` may include:
    - fup_pct (float)
    - unusual_vas (bool) / vas_amount_lkr / vas_product
    - pack_expires_hours (float | None)
    - pending_payment (bool)
    - open_case (bool)
    - double_charge (bool)
    - reload_missing (bool)
    """
    _ = language
    signals = signals or {}
    primary: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(topic_id: str, *, label_override: str | None = None, reason: str = "") -> None:
        topic = _topic(topic_id)
        if topic is None or topic_id in seen:
            return
        seen.add(topic_id)
        chip = {
            "id": topic["id"],
            "intent": topic["intent"],
            "i18n_key": topic["i18n_key"],
            "reason": reason,
        }
        if label_override:
            chip["label"] = label_override
        primary.append(chip)

    fup = signals.get("fup_pct")
    if isinstance(fup, (int, float)) and fup >= 80:
        add("slow", reason="fup_high")
        add("fup", reason="fup_high")

    if signals.get("unusual_vas"):
        amount = signals.get("vas_amount_lkr")
        product = signals.get("vas_product") or "a service"
        if amount:
            add(
                "unexpected",
                label_override=f"Why was LKR {amount} deducted?",
                reason="unusual_vas",
            )
        else:
            add("unexpected", reason="unusual_vas")
        add("vas", reason="unusual_vas")
        add("balance", reason="unusual_vas")
        _ = product

    hours = signals.get("pack_expires_hours")
    if isinstance(hours, (int, float)) and 0 <= hours <= 24:
        add("expiry", reason="pack_expiring")
        add("recommend", reason="pack_expiring")

    if signals.get("double_charge"):
        add("twice", reason="double_charge")
        add("balance", reason="double_charge")

    if signals.get("reload_missing") or signals.get("pending_payment"):
        add("reload", reason="reload_missing")

    if signals.get("open_case"):
        add("case", reason="open_case")
        add("refund", reason="open_case")

    # Quiet / fill defaults
    for topic_id in ("balance", "recommend", "esim", "slow", "prevent", "network"):
        if len(primary) >= limit:
            break
        add(topic_id, reason="default")

    primary = primary[:limit]
    more = [dict(t) for t in TOPIC_CATALOGUE if t["id"] not in seen]

    return {
        "suggestions": primary,
        "more_topics": more,
        "signals_used": {k: v for k, v in signals.items() if v not in (None, False, "")},
    }


def signals_from_snapshot(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    """Derive suggestion signals from a me/app-like or timeline-like snapshot."""
    if not snapshot:
        return {}
    signals: dict[str, Any] = {}
    pack = snapshot.get("pack") or {}
    if pack.get("used_pct") is not None:
        signals["fup_pct"] = float(pack["used_pct"])
    subs = snapshot.get("subscriptions") or []
    unusual = [s for s in subs if s.get("active") and not s.get("consent")]
    activity = snapshot.get("activity") or []
    vas_rows = [r for r in activity if r.get("type") == "vas_charge"]
    if unusual or vas_rows:
        signals["unusual_vas"] = True
        row = vas_rows[0] if vas_rows else None
        if row and row.get("amount_lkr"):
            signals["vas_amount_lkr"] = str(row["amount_lkr"])
        if unusual:
            signals["vas_product"] = unusual[0].get("name") or unusual[0].get("product")
        elif row:
            signals["vas_product"] = row.get("detail")
    payments = [r for r in activity if r.get("type") == "payment_captured"]
    credits = [
        r
        for r in activity
        if r.get("type") == "balance_credited" and r.get("detail") != "clarity_refund"
    ]
    counts: dict[str, int] = {}
    for pay in payments:
        key = str(pay.get("amount_lkr") or "")
        counts[key] = counts.get(key, 0) + 1
    if any(c >= 2 for c in counts.values()):
        signals["double_charge"] = True
    if payments and not any(
        str(c.get("amount_lkr")) == str(p.get("amount_lkr")) for p in payments for c in credits
    ):
        # Heuristic: at least one payment without matching credit
        if any(
            not any(str(c.get("amount_lkr")) == str(p.get("amount_lkr")) for c in credits)
            for p in payments
        ):
            signals["reload_missing"] = True
    if snapshot.get("open_cases") or snapshot.get("open_case"):
        signals["open_case"] = True
    expires_in = pack.get("expires_in_hours")
    if expires_in is not None:
        signals["pack_expires_hours"] = float(expires_in)
    return signals


def default_greeting_key() -> str:
    return "chatGreeting"


# Re-export Intent for callers that import suggestions
__all__ = [
    "Intent",
    "build_suggestions",
    "default_greeting_key",
    "signals_from_snapshot",
]
