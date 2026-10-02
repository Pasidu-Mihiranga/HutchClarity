"""Pay-as-you-go usage draining main balance with no active pack."""

from __future__ import annotations

from typing import Any

from clarity.modules.detection.domain.models import Detection
from clarity.modules.detection.domain.rules._util import as_money, events


class BalanceBurnPaygDetector:
    rule_id = "BALANCE_BURN_PAYG"
    version = "1"

    def evaluate(self, timeline: dict[str, Any]) -> Detection | None:
        usage = events(timeline, "usage")
        packs = events(timeline, "packs")

        active_packs = [
            p for p in packs if p.get("status", "active") in {"active", "live"} and not p.get("expired")
        ]
        payg = [
            u
            for u in usage
            if u.get("rated_as") in {"payg", "main_balance", "pay_as_you_go"}
            or u.get("payg") is True
            or u.get("charged_to") == "main_balance"
        ]
        if payg and not active_packs:
            total = sum((as_money(u.get("amount_lkr") or u.get("amount")) or 0) for u in payg)
            return Detection(
                rule_id=self.rule_id,
                version=self.version,
                confidence=0.89,
                evidence=[
                    {"kind": "usage", "ref": payg[0].get("id") or payg[0]},
                    {"kind": "absence", "of": "active_pack"},
                ],
                amount_lkr=total if total else None,
            )
        return None


detect = BalanceBurnPaygDetector()
