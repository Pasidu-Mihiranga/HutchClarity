"""App traffic outside social-pack scope — explain only."""

from __future__ import annotations

from typing import Any

from clarity.modules.detection.domain.models import Detection
from clarity.modules.detection.domain.rules._util import as_money, events


class SocialPackScopeDetector:
    rule_id = "SOCIAL_PACK_SCOPE"
    version = "1"

    def evaluate(self, timeline: dict[str, Any]) -> Detection | None:
        usage = events(timeline, "usage")
        packs = events(timeline, "packs")

        social_packs = [
            p
            for p in packs
            if p.get("kind") == "social"
            or p.get("pack_type") == "social"
            or "social" in str(p.get("sku", "")).lower()
            or "social" in str(p.get("name", "")).lower()
        ]
        if not social_packs:
            return None

        allowed = set()
        for pack in social_packs:
            for app in pack.get("allowed_apps") or pack.get("scope") or []:
                allowed.add(str(app).lower())

        for row in usage:
            app = str(row.get("app") or row.get("destination") or "").lower()
            if not app:
                continue
            if row.get("charged_to") == "main_balance" or row.get("outside_scope") is True:
                if allowed and app not in allowed:
                    return Detection(
                        rule_id=self.rule_id,
                        version=self.version,
                        confidence=0.9,
                        evidence=[
                            {"kind": "usage", "ref": row.get("id") or row},
                            {"kind": "pack", "ref": social_packs[0].get("id") or social_packs[0]},
                        ],
                        amount_lkr=as_money(row.get("amount_lkr") or row.get("amount")),
                    )
            if row.get("outside_scope") is True:
                return Detection(
                    rule_id=self.rule_id,
                    version=self.version,
                    confidence=0.91,
                    evidence=[{"kind": "usage", "ref": row.get("id") or row}],
                    amount_lkr=as_money(row.get("amount_lkr") or row.get("amount")),
                )
        return None


detect = SocialPackScopeDetector()
