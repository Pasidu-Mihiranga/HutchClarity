"""Sold pack ≠ provisioned pack (catalogue / BSS mismatch)."""

from __future__ import annotations

from typing import Any

from clarity.modules.detection.domain.models import Detection
from clarity.modules.detection.domain.rules._util import as_money, events


class PackMismatchDetector:
    rule_id = "PACK_MISMATCH"
    version = "1"

    def evaluate(self, timeline: dict[str, Any]) -> Detection | None:
        packs = events(timeline, "packs")
        for pack in packs:
            sold = pack.get("sold_name") or pack.get("ordered_name") or pack.get("sold_sku")
            live = pack.get("provisioned_name") or pack.get("active_name") or pack.get(
                "provisioned_sku"
            )
            if sold and live and sold != live:
                return Detection(
                    rule_id=self.rule_id,
                    version=self.version,
                    confidence=0.94,
                    evidence=[
                        {"kind": "pack", "ref": pack.get("id") or pack},
                        {"kind": "mismatch", "sold": sold, "provisioned": live},
                    ],
                    amount_lkr=as_money(pack.get("amount_lkr") or pack.get("price_lkr")),
                )
            if pack.get("mismatch") is True:
                return Detection(
                    rule_id=self.rule_id,
                    version=self.version,
                    confidence=0.95,
                    evidence=[{"kind": "pack", "ref": pack.get("id") or pack}],
                    amount_lkr=as_money(pack.get("amount_lkr") or pack.get("price_lkr")),
                )
        return None


detect = PackMismatchDetector()
