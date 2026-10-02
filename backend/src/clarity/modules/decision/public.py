"""Public facade for the decision module."""

from __future__ import annotations

from typing import Any

from clarity.modules.detection.domain.models import Detection
from clarity.modules.decision.domain.engine import Decision, evaluate
from clarity.modules.decision.domain.zen_tables import DEFAULT_CAPS, all_tables


def decide(
    detections: list[Detection] | list[dict[str, Any]],
    caps: dict[str, Any] | None = None,
    *,
    risk: dict[str, Any] | None = None,
) -> Decision:
    """Evaluate detections through ZEN tables + hard gates."""
    normalised: list[Detection] = []
    for item in detections:
        if isinstance(item, Detection):
            normalised.append(item)
        else:
            amount = item.get("amount_lkr")
            from decimal import Decimal

            normalised.append(
                Detection(
                    rule_id=str(item["rule_id"]),
                    version=str(item.get("version", "1")),
                    confidence=float(item.get("confidence", 0.0)),
                    evidence=list(item.get("evidence") or []),
                    amount_lkr=Decimal(str(amount)) if amount is not None else None,
                )
            )
    return evaluate(normalised, caps or DEFAULT_CAPS, risk=risk)


__all__ = ["DEFAULT_CAPS", "Decision", "all_tables", "decide", "evaluate"]
