"""Retired pack auto-migrated — explain + migration card."""

from __future__ import annotations

from typing import Any

from clarity.modules.detection.domain.models import Detection
from clarity.modules.detection.domain.rules._util import events


class PackSunsetDetector:
    rule_id = "PACK_SUNSET"
    version = "1"

    def evaluate(self, timeline: dict[str, Any]) -> Detection | None:
        packs = events(timeline, "packs")
        for pack in packs:
            if (
                pack.get("sunset") is True
                or pack.get("event") == "pack_sunset"
                or pack.get("migrated_from")
                or pack.get("status") == "sunset"
            ):
                return Detection(
                    rule_id=self.rule_id,
                    version=self.version,
                    confidence=0.93,
                    evidence=[
                        {"kind": "pack", "ref": pack.get("id") or pack},
                        {
                            "kind": "migration",
                            "from": pack.get("migrated_from") or pack.get("sku"),
                            "to": pack.get("migrated_to") or pack.get("replacement_sku"),
                        },
                    ],
                )
        return None


detect = PackSunsetDetector()
