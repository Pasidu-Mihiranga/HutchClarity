"""VAS renewed without a recent consent notification."""

from __future__ import annotations

from typing import Any

from clarity.modules.detection.domain.models import Detection
from clarity.modules.detection.domain.rules._util import as_money, events, within_seconds


class VasSilentRenewalDetector:
    rule_id = "VAS_SILENT_RENEWAL"
    version = "1"

    def evaluate(self, timeline: dict[str, Any]) -> Detection | None:
        vas = events(timeline, "vas")
        notifications = events(timeline, "notifications")
        consents = events(timeline, "consents")

        for charge in vas:
            if charge.get("type") not in {"renewal", "vas_renewal", "silent_renewal", None}:
                # Treat plain vas charges marked renewed=True as renewals too.
                if not charge.get("renewed") and charge.get("event") != "renewal":
                    continue
            amount = as_money(charge.get("amount_lkr") or charge.get("amount"))
            notice_window = int(charge.get("notice_window_seconds", 7 * 86400))
            charged_at = charge.get("at") or charge.get("occurred_at")

            related_consent = any(
                c.get("subscription_id") == charge.get("subscription_id")
                and within_seconds(c.get("at") or c.get("occurred_at"), charged_at, notice_window)
                for c in consents
            )
            related_notice = any(
                n.get("kind") in {"vas_renewal", "consent", "renewal_notice"}
                and (
                    n.get("subscription_id") == charge.get("subscription_id")
                    or n.get("product") == charge.get("product")
                )
                and within_seconds(n.get("at") or n.get("occurred_at"), charged_at, notice_window)
                for n in notifications
            )
            # Also accept a consent notification without matching ids if timeline is sparse.
            if not related_consent and not related_notice:
                # Require at least a renewal-shaped event.
                if charge.get("renewed") or charge.get("type") in {
                    "renewal",
                    "vas_renewal",
                    "silent_renewal",
                } or charge.get("event") == "renewal":
                    return Detection(
                        rule_id=self.rule_id,
                        version=self.version,
                        confidence=0.92,
                        evidence=[
                            {"kind": "vas", "ref": charge.get("id") or charge},
                            {"kind": "absence", "of": "consent_or_renewal_notice"},
                        ],
                        amount_lkr=amount,
                    )
        return None


detect = VasSilentRenewalDetector()
