"""Catalogue mismatch vs charged pack (sold ≠ provisioned)."""

from __future__ import annotations

from typing import Any

from clarity.modules.detection.domain.models import Detection
from clarity.modules.detection.domain.rules._util import as_money, events


class WrongPackDetector:
    rule_id = "WRONG_PACK"
    version = "1"

    def evaluate(self, timeline: dict[str, Any]) -> Detection | None:
        packs = events(timeline, "packs")
        charges = events(timeline, "charges")

        for pack in packs:
            sold = pack.get("sold_sku") or pack.get("catalogue_sku") or pack.get("ordered_sku")
            provisioned = pack.get("provisioned_sku") or pack.get("active_sku") or pack.get("sku")
            if sold and provisioned and sold != provisioned:
                amount = as_money(pack.get("amount_lkr") or pack.get("price_lkr"))
                return Detection(
                    rule_id=self.rule_id,
                    version=self.version,
                    confidence=0.94,
                    evidence=[
                        {"kind": "pack", "ref": pack.get("id") or pack},
                        {"kind": "mismatch", "sold": sold, "provisioned": provisioned},
                    ],
                    amount_lkr=amount,
                )

        for charge in charges:
            expected = charge.get("expected_sku") or charge.get("catalogue_sku")
            actual = charge.get("sku") or charge.get("product")
            if expected and actual and expected != actual:
                return Detection(
                    rule_id=self.rule_id,
                    version=self.version,
                    confidence=0.93,
                    evidence=[
                        {"kind": "charge", "ref": charge.get("id") or charge},
                        {"kind": "mismatch", "expected": expected, "actual": actual},
                    ],
                    amount_lkr=as_money(charge.get("amount_lkr") or charge.get("amount")),
                )
        return None


detect = WrongPackDetector()
