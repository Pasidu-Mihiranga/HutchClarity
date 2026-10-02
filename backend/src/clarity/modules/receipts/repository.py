"""Where the receipt chain lives (B02, ADR-0013).

Receipts are append-only and hash-chained, so order is part of the data: the
repository preserves issue order, which is what ``chain_is_intact`` walks.
"""

from __future__ import annotations

from typing import Protocol

from clarity.contracts.receipt import TrustReceipt
from clarity.platform.persistence import Repository

#: Collection names the drivers use. One collection is one table in B05.
RECEIPTS = "receipts.chain"
SUPERSEDED = "receipts.superseded"
SUBSCRIBERS = "receipts.subscriber"
RECEIPT_SEQUENCE = "receipts.sequence"
BY_PLAN = "receipts.by_plan"

#: The single row the receipt-number sequence lives in.
SEQUENCE_KEY = "receipt_no"


class ReceiptRepository(Protocol):
    """The receipt chain, in issue order, and what each receipt is about."""

    def get(self, receipt_id: str) -> TrustReceipt | None: ...

    def append(self, receipt: TrustReceipt, *, subscriber_ref: str) -> None:
        """Add a receipt to the end of the chain."""
        ...

    def in_order(self) -> list[TrustReceipt]:
        """Every receipt, oldest first."""
        ...

    def ids_in_order(self) -> list[str]: ...

    def subscriber_ref_for(self, receipt_id: str) -> str | None: ...

    def mark_superseded(self, superseded_id: str, *, by_receipt_id: str) -> None: ...

    def superseded_by(self, receipt_id: str) -> str | None: ...

    def next_receipt_number(self) -> int: ...

    def bump_sequence_to(self, value: int) -> None:
        """Keep the sequence ahead of a receipt number restored from storage."""
        ...

    def receipt_id_for_plan(self, plan_id: str) -> str | None:
        """The one receipt issued for this plan, if one has been."""
        ...

    def link_plan(self, plan_id: str, *, receipt_id: str) -> None:
        """Record that this plan's receipt is this receipt. One plan, one receipt."""
        ...


class StoredReceiptRepository:
    """``ReceiptRepository`` over any persistence driver."""

    def __init__(
        self,
        receipts: Repository[str, TrustReceipt],
        superseded: Repository[str, str],
        subscribers: Repository[str, str],
        sequence: Repository[str, int],
        by_plan: Repository[str, str],
    ) -> None:
        self._receipts = receipts
        self._superseded = superseded
        self._subscribers = subscribers
        self._sequence = sequence
        self._by_plan = by_plan

    def get(self, receipt_id: str) -> TrustReceipt | None:
        return self._receipts.get(receipt_id)

    def append(self, receipt: TrustReceipt, *, subscriber_ref: str) -> None:
        self._receipts.put(receipt.receipt_id, receipt)
        self._subscribers.put(receipt.receipt_id, subscriber_ref)

    def in_order(self) -> list[TrustReceipt]:
        return self._receipts.values()

    def ids_in_order(self) -> list[str]:
        return self._receipts.keys()

    def subscriber_ref_for(self, receipt_id: str) -> str | None:
        return self._subscribers.get(receipt_id)

    def mark_superseded(self, superseded_id: str, *, by_receipt_id: str) -> None:
        self._superseded.put(superseded_id, by_receipt_id)

    def superseded_by(self, receipt_id: str) -> str | None:
        return self._superseded.get(receipt_id)

    def next_receipt_number(self) -> int:
        current = self._sequence.get(SEQUENCE_KEY) or 0
        nxt = current + 1
        self._sequence.put(SEQUENCE_KEY, nxt)
        return nxt

    def bump_sequence_to(self, value: int) -> None:
        if value > (self._sequence.get(SEQUENCE_KEY) or 0):
            self._sequence.put(SEQUENCE_KEY, value)

    def receipt_id_for_plan(self, plan_id: str) -> str | None:
        return self._by_plan.get(plan_id)

    def link_plan(self, plan_id: str, *, receipt_id: str) -> None:
        self._by_plan.put(plan_id, receipt_id)


__all__ = [
    "BY_PLAN",
    "RECEIPTS",
    "RECEIPT_SEQUENCE",
    "SEQUENCE_KEY",
    "SUBSCRIBERS",
    "SUPERSEDED",
    "ReceiptRepository",
    "StoredReceiptRepository",
]
