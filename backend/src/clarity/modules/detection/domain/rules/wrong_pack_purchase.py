"""Customer bought the wrong pack (even if used) — one-tap within policy window."""

from __future__ import annotations

from typing import Any

from clarity.modules.detection.domain.models import Detection
from clarity.modules.detection.domain.rules._util import as_money, events


class WrongPackPurchaseDetector:
    rule_id = "WRONG_PACK_PURCHASE"
    version = "1"

    def evaluate(self, timeline: dict[str, Any]) -> Detection | None:
        packs = events(timeline, "packs")
        for pack in packs:
            if (
                pack.get("wrong_purchase") is True
                or pack.get("customer_intent_sku")
                and pack.get("customer_intent_sku") != (pack.get("sku") or pack.get("sold_sku"))
                or pack.get("event") == "wrong_pack_purchase"
            ):
                intent = pack.get("customer_intent_sku")
                actual = pack.get("sku") or pack.get("sold_sku")
                return Detection(
                    rule_id=self.rule_id,
                    version=self.version,
                    confidence=0.88,
                    evidence=[
                        {"kind": "pack", "ref": pack.get("id") or pack},
                        {"kind": "intent", "wanted": intent, "bought": actual},
                    ],
                    amount_lkr=as_money(pack.get("amount_lkr") or pack.get("price_lkr")),
                )
        return None


detect = WrongPackPurchaseDetector()
