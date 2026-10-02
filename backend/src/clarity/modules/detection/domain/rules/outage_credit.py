"""Outage overlapped an active pack — goodwill / credit candidate."""

from __future__ import annotations

from typing import Any

from clarity.modules.detection.domain.models import Detection
from clarity.modules.detection.domain.rules._util import as_money, events, parse_ts


class OutageCreditDetector:
    rule_id = "OUTAGE_CREDIT"
    version = "1"

    def evaluate(self, timeline: dict[str, Any]) -> Detection | None:
        outages = events(timeline, "outages")
        packs = events(timeline, "packs")
        if not outages or not packs:
            return None

        for pack in packs:
            if pack.get("status") not in {None, "active", "expired"}:
                continue
            p_start = parse_ts(pack.get("started_at") or pack.get("activated_at") or pack.get("at"))
            p_end = parse_ts(pack.get("ended_at") or pack.get("expires_at"))
            for outage in outages:
                o_start = parse_ts(outage.get("started_at") or outage.get("at"))
                o_end = parse_ts(outage.get("ended_at"))
                if o_start is None:
                    continue
                # Overlap if outage starts while pack is active.
                pack_active = p_start is None or o_start >= p_start
                if p_end is not None and o_start > p_end:
                    pack_active = False
                if o_end is not None and p_start is not None and o_end < p_start:
                    pack_active = False
                if pack_active:
                    credit = as_money(outage.get("credit_lkr") or pack.get("amount_lkr"))
                    return Detection(
                        rule_id=self.rule_id,
                        version=self.version,
                        confidence=0.85,
                        evidence=[
                            {"kind": "outage", "ref": outage.get("id") or outage},
                            {"kind": "pack", "ref": pack.get("id") or pack},
                        ],
                        amount_lkr=credit,
                    )
        return None


detect = OutageCreditDetector()
