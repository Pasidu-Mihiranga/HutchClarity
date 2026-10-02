"""Detection result model."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass(slots=True)
class Detection:
    rule_id: str
    version: str
    confidence: float
    evidence: list[dict[str, Any]] = field(default_factory=list)
    amount_lkr: Decimal | None = None

    @property
    def ref(self) -> str:
        return f"{self.rule_id}@{self.version}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "version": self.version,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "amount_lkr": f"{self.amount_lkr:.2f}" if self.amount_lkr is not None else None,
            "ref": self.ref,
        }
