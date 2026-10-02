"""Smart desk queue scoring."""

from __future__ import annotations

from contextlib import suppress
from datetime import datetime
from decimal import Decimal

from clarity.kernel.common import utc_now
from clarity.modules.case.domain.aggregate import Case

# Channel urgency boost (deck S9 - desk/shop first).
_CHANNEL_BOOST: dict[str, float] = {
    "desk": 40.0,
    "shop": 35.0,
    "whatsapp": 20.0,
    "app": 15.0,
    "sms": 12.0,
    "ussd": 10.0,
    "web": 8.0,
    "system": 5.0,
}


def smart_score(case: Case, *, now: datetime | None = None) -> float:
    """Rank a case for the desk queue.

    Higher is more urgent. Combines money at stake, origin channel, and age.
    """
    moment = now or utc_now()
    amount = float(case.amount_lkr or Decimal("0.00"))
    if case.decision and case.decision.get("amount_lkr") is not None:
        with suppress(TypeError, ValueError):
            amount = max(amount, float(case.decision["amount_lkr"]))

    channel = (case.channel or "web").lower()
    channel_boost = _CHANNEL_BOOST.get(channel, 5.0)

    age_hours = max(0.0, (moment - case.created_at).total_seconds() / 3600.0)
    # Amount weight: LKR 1000 ~ 10 points; age: 2 points/hour.
    return amount * 0.01 + channel_boost + age_hours * 2.0
