"""Network outage consumed pack validity window."""

from __future__ import annotations

from typing import Any

from clarity.modules.detection.domain.models import Detection
from clarity.modules.detection.domain.rules._util import as_money, events, parse_ts


class OutageDuringPackDetector:
    rule_id = "OUTAGE_DURING_PACK"
    version = "1"

    def evaluate(self, timeline: dict[str, Any]) -> Detection | None:
        outages = events(timeline, "outages")
        packs = events(timeline, "packs")
        if not outages or not packs:
            return None

        for pack in packs:
            p_start = parse_ts(pack.get("started_at") or pack.get("activated_at") or pack.get("at"))
            p_end = parse_ts(pack.get("ended_at") or pack.get("expires_at"))
            for outage in outages:
                o_start = parse_ts(outage.get("started_at") or outage.get("at"))
                o_end = parse_ts(outage.get("ended_at"))
                if o_start is None:
                    continue
                starts_in = p_start is None or o_start >= p_start
                ends_ok = p_end is None or o_start <= p_end
                if starts_in and ends_ok:
                    # Prefer outages that flag pack impact.
                    if outage.get("impacted_pack") or outage.get("affects_pack") or True:
                        hours = outage.get("duration_hours")
                        return Detection(
                            rule_id=self.rule_id,
                            version=self.version,
                            confidence=0.84,
                            evidence=[
                                {"kind": "outage", "ref": outage.get("id") or outage},
                                {"kind": "pack", "ref": pack.get("id") or pack},
                                {"kind": "duration_hours", "value": hours},
                                {
                                    "kind": "window",
                                    "outage_end": o_end.isoformat() if o_end else None,
                                },
                            ],
                            amount_lkr=as_money(
                                outage.get("goodwill_lkr") or pack.get("amount_lkr")
                            ),
                        )
        return None


detect = OutageDuringPackDetector()
