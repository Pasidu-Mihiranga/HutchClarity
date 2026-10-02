"""VAS renewal without required prior notice."""

from __future__ import annotations

from typing import Any

from clarity.modules.detection.domain.models import Detection
from clarity.modules.detection.domain.rules._util import as_money, events, within_seconds


class VasRenewalUnnotifiedDetector:
    rule_id = "VAS_RENEWAL_UNNOTIFIED"
    version = "1"

    def evaluate(self, timeline: dict[str, Any]) -> Detection | None:
        vas = events(timeline, "vas")
        notifications = events(timeline, "notifications")

        for charge in vas:
            is_renewal = (
                charge.get("type") in {"renewal", "vas_renewal"}
                or charge.get("event") == "renewal"
                or charge.get("renewed") is True
            )
            if not is_renewal:
                continue
            charged_at = charge.get("at") or charge.get("occurred_at")
            window = int(charge.get("notice_window_seconds", 48 * 3600))
            notified = any(
                n.get("kind") in {"vas_renewal", "renewal_notice", "early_vas_renewal"}
                and within_seconds(n.get("at") or n.get("occurred_at"), charged_at, window)
                and (
                    n.get("subscription_id") == charge.get("subscription_id")
                    or n.get("product") == charge.get("product")
                    or n.get("subscription_id") is None
                )
                for n in notifications
            )
            if not notified:
                return Detection(
                    rule_id=self.rule_id,
                    version=self.version,
                    confidence=0.9,
                    evidence=[
                        {"kind": "vas", "ref": charge.get("id") or charge},
                        {"kind": "absence", "of": "renewal_notice"},
                    ],
                    amount_lkr=as_money(charge.get("amount_lkr") or charge.get("amount")),
                )
        return None


detect = VasRenewalUnnotifiedDetector()
