"""Public facade for the case module."""

from __future__ import annotations

from typing import Any

from clarity.kernel.common import Channel, money
from clarity.modules.case.domain.aggregate import Case, CaseMessage, CaseStatus
from clarity.modules.case.domain.queue import smart_score
from clarity.modules.case.domain.store import CaseStore

_store = CaseStore()


def get_store() -> CaseStore:
    return _store


def reset_cases(store: CaseStore | None = None) -> None:
    global _store
    if store is None:
        _store.clear()
    else:
        _store = store


def create_case(
    *,
    subscriber_ref: str,
    channel: str = Channel.WEB.value,
    message: str | None = None,
    amount_lkr: Any | None = None,
    detections: list[dict[str, Any]] | None = None,
    decision: dict[str, Any] | None = None,
) -> Case:
    if not subscriber_ref or not subscriber_ref.strip():
        raise ValueError("subscriber_ref is required")
    amount = money(amount_lkr) if amount_lkr is not None else None
    seq = _store.next_sequence()
    case = Case.create(
        subscriber_ref=subscriber_ref.strip(),
        channel=channel,
        message=message,
        amount_lkr=amount,
        sequence=seq,
    )
    if detections:
        case.detections = list(detections)
    if decision:
        case.decision = dict(decision)
        if case.amount_lkr is None and decision.get("amount_lkr") is not None:
            case.amount_lkr = money(decision["amount_lkr"])
        outcome = str(decision.get("outcome", "")).upper()
        if outcome in {"HANDOFF", "STAFF_APPROVAL", "FOUR_EYES"}:
            case.status = CaseStatus.AWAITING_APPROVAL
        elif outcome in {"ONE_TAP_FIX", "AUTO_FIX"}:
            case.status = CaseStatus.AWAITING_CONFIRMATION
        else:
            case.status = CaseStatus.EVALUATED
    return _store.put(case)


def get_case(case_id: str) -> Case:
    case = _store.get(case_id)
    if case is None:
        raise KeyError(case_id)
    return case


def list_queue(*, limit: int = 50) -> list[dict[str, Any]]:
    """Cases needing a person, highest smart_score first."""
    waiting_outcomes = frozenset({"HANDOFF", "STAFF_APPROVAL", "FOUR_EYES"})
    waiting = [
        c
        for c in _store.all()
        if c.status in {CaseStatus.AWAITING_APPROVAL, CaseStatus.HANDED_OFF, CaseStatus.OPEN}
        or (
            c.decision is not None
            and str(c.decision.get("outcome", "")).upper() in waiting_outcomes
        )
    ]
    scored = sorted(waiting, key=lambda c: smart_score(c), reverse=True)
    return [
        {
            **c.to_dict(),
            "smart_score": round(smart_score(c), 2),
        }
        for c in scored[:limit]
    ]


def handoff(case_id: str, *, reason: str = "customer_requested", note: str | None = None) -> Case:
    case = get_case(case_id)
    case.status = CaseStatus.HANDED_OFF
    case.handoff_reason = reason
    if note:
        case.messages.append(
            CaseMessage(role="system", text=note, channel=Channel.SYSTEM.value)
        )
    return _store.put(case)


def attach_action(case_id: str, action: dict[str, Any]) -> Case:
    case = get_case(case_id)
    case.actions.append(action)
    status = str(action.get("status", "")).lower()
    if status in {"completed", "executed"}:
        case.status = CaseStatus.ACTIONED
    elif status in {"proposed", "pending"} and case.status is CaseStatus.OPEN:
        case.status = CaseStatus.AWAITING_CONFIRMATION
    return _store.put(case)


__all__ = [
    "Case",
    "CaseStatus",
    "attach_action",
    "create_case",
    "get_case",
    "get_store",
    "handoff",
    "list_queue",
    "reset_cases",
    "smart_score",
]
