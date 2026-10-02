"""Multiple loans overlapping in time."""

from __future__ import annotations

from typing import Any

from clarity.modules.detection.domain.models import Detection
from clarity.modules.detection.domain.rules._util import as_money, events, parse_ts


class LoanStackingDetector:
    rule_id = "LOAN_STACKING"
    version = "1"

    def evaluate(self, timeline: dict[str, Any]) -> Detection | None:
        loans = events(timeline, "loans")
        active = [loan for loan in loans if loan.get("status", "active") in {"active", "open", "outstanding"}]
        if len(active) < 2:
            # Also detect by overlapping windows even if status missing.
            dated = []
            for loan in loans:
                start = parse_ts(loan.get("started_at") or loan.get("at"))
                end = parse_ts(loan.get("ended_at") or loan.get("recovered_at"))
                if start is not None:
                    dated.append((loan, start, end))
            for i, (a, a_start, a_end) in enumerate(dated):
                for b, b_start, b_end in dated[i + 1 :]:
                    a_open = a_end is None or b_start < a_end
                    b_open = b_end is None or a_start < b_end
                    if a_open and b_open:
                        total = (as_money(a.get("amount_lkr") or a.get("amount")) or 0) + (
                            as_money(b.get("amount_lkr") or b.get("amount")) or 0
                        )
                        return Detection(
                            rule_id=self.rule_id,
                            version=self.version,
                            confidence=0.9,
                            evidence=[
                                {"kind": "loan", "ref": a.get("id") or a},
                                {"kind": "loan", "ref": b.get("id") or b},
                            ],
                            amount_lkr=total if total else None,
                        )
            return None

        total = sum(
            (as_money(loan.get("amount_lkr") or loan.get("amount")) or 0) for loan in active
        )
        return Detection(
            rule_id=self.rule_id,
            version=self.version,
            confidence=0.91,
            evidence=[{"kind": "loan", "ref": loan.get("id") or loan} for loan in active[:5]],
            amount_lkr=total if total else None,
        )


detect = LoanStackingDetector()
