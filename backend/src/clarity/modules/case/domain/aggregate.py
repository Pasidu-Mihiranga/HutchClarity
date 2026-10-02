"""Case aggregate: dispute thread shared across channels."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from clarity.kernel.common import Channel, utc_now
from clarity.kernel.ids import case_no, new_id


class CaseStatus(StrEnum):
    OPEN = "open"
    EVALUATED = "evaluated"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    ACTIONED = "actioned"
    HANDED_OFF = "handed_off"
    CLOSED = "closed"


@dataclass(slots=True)
class CaseMessage:
    role: str
    text: str
    at: datetime = field(default_factory=utc_now)
    channel: str = Channel.SYSTEM.value

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "text": self.text,
            "at": self.at.isoformat(),
            "channel": self.channel,
        }


@dataclass(slots=True)
class Case:
    """A dispute or question with one shared trail across channels."""

    id: str
    case_no: str
    subscriber_ref: str
    channel: str
    status: CaseStatus = CaseStatus.OPEN
    messages: list[CaseMessage] = field(default_factory=list)
    detections: list[dict[str, Any]] = field(default_factory=list)
    decision: dict[str, Any] | None = None
    created_at: datetime = field(default_factory=utc_now)
    amount_lkr: Decimal | None = None
    handoff_reason: str | None = None
    actions: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        *,
        subscriber_ref: str,
        channel: str = Channel.WEB.value,
        message: str | None = None,
        amount_lkr: Decimal | None = None,
        sequence: int = 1,
        year: int | None = None,
    ) -> Case:
        now = utc_now()
        y = year or now.year
        case = cls(
            id=new_id("CAS"),
            case_no=case_no(sequence, year=y),
            subscriber_ref=subscriber_ref,
            channel=channel,
            amount_lkr=amount_lkr,
            created_at=now,
        )
        if message:
            case.messages.append(
                CaseMessage(role="customer", text=message, channel=channel, at=now)
            )
        return case

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "case_id": self.id,
            "case_no": self.case_no,
            "subscriber_ref": self.subscriber_ref,
            "channel": self.channel,
            "status": self.status.value,
            "messages": [m.to_dict() for m in self.messages],
            "detections": list(self.detections),
            "decision": self.decision,
            "created_at": self.created_at.isoformat(),
            "amount_lkr": f"{self.amount_lkr:.2f}" if self.amount_lkr is not None else None,
            "handoff_reason": self.handoff_reason,
            "actions": list(self.actions),
        }
