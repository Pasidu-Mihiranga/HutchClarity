"""Event-fed proactive risk detectors."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Literal

from clarity.contracts.events import (
    PackExpiringV1,
    PaymentRecordedV1,
    RiskDetectedV1,
    UsageThresholdReachedV1,
)
from clarity.platform.config.resolver import PolicyResolver
from clarity.platform.messaging.envelope import Event, EventType
from clarity.platform.messaging.outbox import outbox_in
from clarity.platform.persistence import Repository, UnitOfWorkFactory

SIGNALS = "proactive.signals"
RISKS = "proactive.risks"

_DURATION = re.compile(r"^PT(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?$")
RiskBand = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class SignalRecord:
    event_id: str
    subject: str
    kind: str
    reference: str
    amount_lkr: Decimal | None
    group_key: str
    occurred_at: datetime


@dataclass(frozen=True)
class RiskRecord:
    risk_key: str
    source_event_id: str
    subject: str
    risk_type: str


def _duration(value: str) -> timedelta:
    match = _DURATION.fullmatch(value)
    if match is None or not any(match.groupdict().values()):
        raise ValueError(f"unsupported proactive duration {value!r}")
    return timedelta(
        hours=int(match.group("hours") or 0),
        minutes=int(match.group("minutes") or 0),
    )


class ProactiveService:
    """Recognize stream risks and publish each fact exactly once."""

    def __init__(self, *, open_unit: UnitOfWorkFactory, policies: PolicyResolver) -> None:
        self._open_unit = open_unit
        self._policies = policies

    def consume_event(self, event: Event) -> None:
        payload = event.payload()
        risk: tuple[str, str, list[str], RiskBand] | None = None

        with self._open_unit() as unit:
            signals: Repository[str, SignalRecord] = unit.repository(SIGNALS)
            risks: Repository[str, RiskRecord] = unit.repository(RISKS)
            if signals.get(event.id) is not None:
                return

            if isinstance(payload, PaymentRecordedV1):
                signal = SignalRecord(
                    event_id=event.id,
                    subject=event.subject,
                    kind="payment",
                    reference=payload.payment_ref,
                    amount_lkr=payload.amount_lkr,
                    group_key=payload.bank_ref_hash,
                    occurred_at=payload.captured_at,
                )
                window = _duration(
                    str(
                        self._policies.resolve(
                            "detection.duplicate_reload.window",
                            as_of=payload.captured_at,
                            context={"rule": "DUPLICATE_RELOAD"},
                        )
                    )
                )
                prior = [
                    item
                    for item in signals.values()
                    if item.subject == event.subject
                    and item.kind == "payment"
                    and item.group_key == payload.bank_ref_hash
                    and item.amount_lkr == payload.amount_lkr
                    and abs(payload.captured_at - item.occurred_at) <= window
                ]
                if prior:
                    risk = (
                        f"duplicate:{event.subject}:{payload.bank_ref_hash}",
                        "duplicate_reload",
                        [prior[-1].reference, payload.payment_ref],
                        "high",
                    )
            elif isinstance(payload, UsageThresholdReachedV1):
                signal = SignalRecord(
                    event_id=event.id,
                    subject=event.subject,
                    kind="usage",
                    reference=payload.offering_id,
                    amount_lkr=None,
                    group_key=str(payload.threshold_percent),
                    occurred_at=payload.reached_at,
                )
                configured = str(
                    self._policies.resolve(
                        "proactive.fup.warning_thresholds",
                        as_of=payload.reached_at,
                    )
                )
                thresholds = sorted(int(item.strip()) for item in configured.split(","))
                if payload.threshold_percent in thresholds:
                    band: RiskBand = (
                        "high" if payload.threshold_percent == thresholds[-1] else "medium"
                    )
                    risk = (
                        f"fup:{event.subject}:{payload.offering_id}:{payload.threshold_percent}",
                        f"fup_{payload.threshold_percent}",
                        [payload.offering_id],
                        band,
                    )
            elif isinstance(payload, PackExpiringV1):
                signal = SignalRecord(
                    event_id=event.id,
                    subject=event.subject,
                    kind="pack",
                    reference=payload.offering_id,
                    amount_lkr=None,
                    group_key=payload.expires_at.isoformat(),
                    occurred_at=payload.expires_at,
                )
                risk = (
                    f"pack:{event.subject}:{payload.offering_id}:{payload.expires_at.isoformat()}",
                    "pack_expiring",
                    [payload.offering_id],
                    "medium",
                )
            else:
                return

            signals.put(event.id, signal)
            if risk is not None and risks.get(risk[0]) is None:
                risks.put(
                    risk[0],
                    RiskRecord(
                        risk_key=risk[0],
                        source_event_id=event.id,
                        subject=event.subject,
                        risk_type=risk[1],
                    ),
                )
                derived = event.caused(
                    RiskDetectedV1(
                        risk_type=risk[1],
                        band=risk[3],
                        evidence_refs=risk[2],
                    )
                ).model_copy(update={"time": event.time})
                outbox_in(unit).append(derived)
            unit.commit()


CONSUMED_EVENTS = (
    EventType.PAYMENT_RECORDED,
    EventType.USAGE_THRESHOLD_REACHED,
    EventType.PACK_EXPIRING,
)


__all__ = [
    "CONSUMED_EVENTS",
    "RISKS",
    "SIGNALS",
    "ProactiveService",
    "RiskRecord",
    "SignalRecord",
]
