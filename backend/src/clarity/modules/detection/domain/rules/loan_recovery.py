"""Emergency credit recovered from a reload — explain only."""

from __future__ import annotations

from typing import Any

from clarity.modules.detection.domain.models import Detection
from clarity.modules.detection.domain.rules._util import as_money, events, within_seconds


class LoanRecoveryDetector:
    rule_id = "LOAN_RECOVERY"
    version = "1"

    def evaluate(self, timeline: dict[str, Any]) -> Detection | None:
        loans = events(timeline, "loans")
        payments = events(timeline, "payments")

        recoveries = [
            loan
            for loan in loans
            if loan.get("event") == "recovery"
            or loan.get("recovered") is True
            or loan.get("status") == "recovered"
        ]
        for recovery in recoveries:
            recovered_at = recovery.get("recovered_at") or recovery.get("at")
            linked_reload = any(
                within_seconds(
                    payment.get("at") or payment.get("occurred_at"),
                    recovered_at,
                    int(timeline.get("loan_recovery_window_seconds", 3600)),
                )
                for payment in payments
                if str(payment.get("type", "reload")).lower() in {"reload", "topup", "payment"}
            )
            if linked_reload or payments or recovery.get("recovered") is True:
                return Detection(
                    rule_id=self.rule_id,
                    version=self.version,
                    confidence=0.92,
                    evidence=[
                        {"kind": "loan", "ref": recovery.get("id") or recovery},
                        {"kind": "note", "detail": "recovered_from_reload"},
                    ],
                    amount_lkr=as_money(
                        recovery.get("recovered_lkr")
                        or recovery.get("amount_lkr")
                        or recovery.get("amount")
                    ),
                )
        return None


detect = LoanRecoveryDetector()
