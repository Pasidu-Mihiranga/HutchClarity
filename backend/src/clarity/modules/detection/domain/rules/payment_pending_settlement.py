"""Bank payment still pending settlement — explain only, not a failure."""

from __future__ import annotations

from typing import Any

from clarity.modules.detection.domain.models import Detection
from clarity.modules.detection.domain.rules._util import as_money, events


class PaymentPendingSettlementDetector:
    rule_id = "PAYMENT_PENDING_SETTLEMENT"
    version = "1"

    def evaluate(self, timeline: dict[str, Any]) -> Detection | None:
        payments = events(timeline, "payments")
        for payment in payments:
            status = str(payment.get("status", "")).lower()
            if status in {"pending", "pending_settlement", "processing", "authorised"}:
                if payment.get("failed") or status == "failed":
                    continue
                return Detection(
                    rule_id=self.rule_id,
                    version=self.version,
                    confidence=0.97,
                    evidence=[{"kind": "payment", "ref": payment.get("id") or payment}],
                    amount_lkr=as_money(payment.get("amount_lkr") or payment.get("amount")),
                )
        return None


detect = PaymentPendingSettlementDetector()
