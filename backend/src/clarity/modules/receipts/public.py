"""Public facade for the receipts module."""

from __future__ import annotations

from typing import Any

from clarity.modules.receipts.domain.chain import ReceiptChain, SignedReceipt
from clarity.modules.receipts.domain.render import render_receipt_html

_chain = ReceiptChain()


def get_chain() -> ReceiptChain:
    return _chain


def reset_receipts(chain: ReceiptChain | None = None) -> None:
    global _chain
    if chain is None:
        _chain.clear()
    else:
        _chain = chain


def issue_receipt(
    *,
    subscriber_ref: str,
    summary: str,
    case_id: str | None = None,
    action_type: str | None = None,
    amount_lkr: Any | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not subscriber_ref or not subscriber_ref.strip():
        raise ValueError("subscriber_ref is required")
    payload: dict[str, Any] = {
        "subscriber_ref": subscriber_ref.strip(),
        "summary": summary,
        "case_id": case_id,
        "action_type": action_type,
        "amount_lkr": str(amount_lkr) if amount_lkr is not None else None,
        **(extra or {}),
    }
    html = render_receipt_html(payload)
    receipt = _chain.issue(payload, html=html)
    # Re-render with receipt_id / issued_at filled in.
    receipt.html = render_receipt_html(receipt.payload)
    return receipt.to_dict()


def verify_receipt(receipt_id: str) -> dict[str, Any]:
    return _chain.verify(receipt_id)


def replay_receipt(receipt_id: str) -> dict[str, Any]:
    return _chain.replay(receipt_id)


def get_receipt(receipt_id: str) -> SignedReceipt:
    receipt = _chain.get(receipt_id)
    if receipt is None:
        raise KeyError(receipt_id)
    return receipt


__all__ = [
    "ReceiptChain",
    "SignedReceipt",
    "get_chain",
    "get_receipt",
    "issue_receipt",
    "replay_receipt",
    "reset_receipts",
    "verify_receipt",
]
