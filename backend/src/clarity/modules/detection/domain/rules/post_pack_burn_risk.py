"""Proactive: pack about to end with remaining data — burn risk."""

from __future__ import annotations

from typing import Any

from clarity.modules.detection.domain.models import Detection
from clarity.modules.detection.domain.rules._util import events, parse_ts


class PostPackBurnRiskDetector:
    rule_id = "POST_PACK_BURN_RISK"
    version = "1"

    def evaluate(self, timeline: dict[str, Any]) -> Detection | None:
        packs = events(timeline, "packs")
        usage = events(timeline, "usage")

        for pack in packs:
            remaining_gb = pack.get("remaining_gb")
            if remaining_gb is None:
                remaining_gb = pack.get("data_remaining_gb")
            try:
                remaining = float(remaining_gb) if remaining_gb is not None else None
            except (TypeError, ValueError):
                remaining = None

            hours_left = pack.get("hours_remaining")
            if hours_left is None and pack.get("expires_at"):
                # Caller may supply as_of on the timeline.
                as_of = parse_ts(timeline.get("as_of"))
                expires = parse_ts(pack.get("expires_at"))
                if as_of and expires:
                    hours_left = (expires - as_of).total_seconds() / 3600.0

            risk_flag = pack.get("burn_risk") is True or pack.get("event") == "post_pack_burn_risk"
            ending_soon = hours_left is not None and float(hours_left) <= float(
                timeline.get("burn_risk_hours", 24)
            )
            has_remainder = remaining is not None and remaining >= float(
                timeline.get("burn_risk_min_gb", 0.5)
            )

            # Also: recent PAYG after pack end.
            post_pack_payg = any(
                u.get("after_pack_end") is True or u.get("rated_as") == "payg"
                for u in usage
                if u.get("pack_id") == pack.get("id") or pack.get("status") == "expired"
            )

            if risk_flag or (ending_soon and has_remainder) or (
                pack.get("status") == "expired" and has_remainder and post_pack_payg
            ):
                conf = 0.78
                if remaining is not None and remaining >= 2.0:
                    conf = 0.86
                return Detection(
                    rule_id=self.rule_id,
                    version=self.version,
                    confidence=conf,
                    evidence=[
                        {"kind": "pack", "ref": pack.get("id") or pack},
                        {
                            "kind": "risk",
                            "remaining_gb": remaining,
                            "hours_remaining": hours_left,
                        },
                    ],
                )
        return None


detect = PostPackBurnRiskDetector()
