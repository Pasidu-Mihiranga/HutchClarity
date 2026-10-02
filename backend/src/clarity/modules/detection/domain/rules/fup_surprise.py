"""FUP throttle without a prior disclosure event."""

from __future__ import annotations

from typing import Any

from clarity.modules.detection.domain.models import Detection
from clarity.modules.detection.domain.rules._util import events, parse_ts


class FupSurpriseDetector:
    rule_id = "FUP_SURPRISE"
    version = "1"

    def evaluate(self, timeline: dict[str, Any]) -> Detection | None:
        usage = events(timeline, "usage")
        notifications = events(timeline, "notifications")
        packs = events(timeline, "packs")

        throttles = [
            u
            for u in usage
            if u.get("event") in {"fup_throttle", "throttle"} or u.get("throttled") is True
        ]
        if not throttles:
            return None

        disclosures = [
            n
            for n in notifications
            if n.get("kind") in {"fup_disclosure", "fup_notice", "pack_terms"}
        ] + [p for p in packs if p.get("fup_disclosed") is True]

        for throttle in throttles:
            t_at = parse_ts(throttle.get("at") or throttle.get("occurred_at"))
            prior = False
            for d in disclosures:
                d_at = parse_ts(d.get("at") or d.get("occurred_at") or d.get("purchased_at"))
                if d_at is None or t_at is None or d_at <= t_at:
                    if d.get("fup_disclosed") or d.get("kind"):
                        # If no timestamps, treat pack-level disclosure as prior.
                        if d_at is None or (t_at is not None and d_at <= t_at):
                            prior = True
                            break
            if not prior and not disclosures:
                return Detection(
                    rule_id=self.rule_id,
                    version=self.version,
                    confidence=0.88,
                    evidence=[
                        {"kind": "usage", "ref": throttle.get("id") or throttle},
                        {"kind": "absence", "of": "fup_disclosure"},
                    ],
                )
            if not prior:
                return Detection(
                    rule_id=self.rule_id,
                    version=self.version,
                    confidence=0.88,
                    evidence=[
                        {"kind": "usage", "ref": throttle.get("id") or throttle},
                        {"kind": "absence", "of": "prior_fup_disclosure"},
                    ],
                )
        return None


detect = FupSurpriseDetector()
