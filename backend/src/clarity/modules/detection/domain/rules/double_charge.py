"""Two identical charges within a short window."""

from __future__ import annotations

from typing import Any

from clarity.modules.detection.domain.models import Detection
from clarity.modules.detection.domain.rules._util import as_money, events, within_seconds

DEFAULT_WINDOW_SECONDS = 600


class DoubleChargeDetector:
    rule_id = "DOUBLE_CHARGE"
    version = "1"

    def evaluate(self, timeline: dict[str, Any]) -> Detection | None:
        charges = events(timeline, "charges") or events(timeline, "payments")
        window = int(timeline.get("double_charge_window_seconds", DEFAULT_WINDOW_SECONDS))

        for i, a in enumerate(charges):
            for b in charges[i + 1 :]:
                amt_a = as_money(a.get("amount_lkr") or a.get("amount"))
                amt_b = as_money(b.get("amount_lkr") or b.get("amount"))
                if amt_a is None or amt_b is None or amt_a != amt_b:
                    continue
                same_product = (a.get("product") or a.get("sku")) == (b.get("product") or b.get("sku"))
                same_merchant = a.get("merchant_id") == b.get("merchant_id") or (
                    a.get("merchant_id") is None and b.get("merchant_id") is None
                )
                ta = a.get("at") or a.get("occurred_at")
                tb = b.get("at") or b.get("occurred_at")
                if same_product and same_merchant and within_seconds(ta, tb, window):
                    return Detection(
                        rule_id=self.rule_id,
                        version=self.version,
                        confidence=0.96,
                        evidence=[
                            {"kind": "charge", "ref": a.get("id") or a},
                            {"kind": "charge", "ref": b.get("id") or b},
                        ],
                        amount_lkr=amt_a,
                    )
        return None


detect = DoubleChargeDetector()
