"""T+1 matching of completed Clarity actions to adapter confirmations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from clarity.contracts.events import ActionCompletedV1, ReconciliationMismatchV1
from clarity.integration.ports import CommandPort
from clarity.kernel.common import Money, utc_now
from clarity.platform.messaging.envelope import Event
from clarity.platform.messaging.outbox import outbox_in
from clarity.platform.persistence import Repository, UnitOfWorkFactory

EXPECTED_ACTIONS = "reconciliation.expected_actions"
MISMATCHES = "reconciliation.mismatches"


@dataclass(frozen=True)
class ExpectedAction:
    action_id: str
    plan_id: str
    subscriber_ref: str
    idempotency_key: str
    adapter_ref: str | None
    expected_lkr: Money
    completed_at: datetime


@dataclass(frozen=True)
class ReconciliationMismatch:
    mismatch_id: str
    action_id: str
    plan_id: str
    subscriber_ref: str
    expected_lkr: Money
    confirmed_lkr: Money | None
    reason: str
    detected_at: datetime


class ReconciliationService:
    """Consume completions, match them on T+1, and expose finance findings."""

    def __init__(
        self,
        *,
        open_unit: UnitOfWorkFactory,
        confirmations: CommandPort,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._open_unit = open_unit
        self._confirmations = confirmations
        self._clock = clock

    def on_action_completed(self, event: Event) -> None:
        payload = event.payload()
        if not isinstance(payload, ActionCompletedV1):  # pragma: no cover - type guard
            return
        with self._open_unit() as unit:
            expected: Repository[str, ExpectedAction] = unit.repository(EXPECTED_ACTIONS)
            for step in payload.steps:
                expected.put(
                    step.action_id,
                    ExpectedAction(
                        action_id=step.action_id,
                        plan_id=payload.plan_id,
                        subscriber_ref=event.subject,
                        idempotency_key=step.idempotency_key,
                        adapter_ref=step.adapter_ref,
                        expected_lkr=step.amount_lkr or Money("0.00"),
                        completed_at=event.time,
                    ),
                )
            unit.commit()

    def run_daily(self, *, day: date | None = None) -> list[ReconciliationMismatch]:
        """Match actions completed before ``day`` and publish new mismatches."""
        run_day = day or self._clock().date()
        cutoff = run_day - timedelta(days=1)
        with self._open_unit() as unit:
            expected: Repository[str, ExpectedAction] = unit.repository(EXPECTED_ACTIONS)
            mismatches: Repository[str, ReconciliationMismatch] = unit.repository(MISMATCHES)
            created: list[ReconciliationMismatch] = []
            for action in expected.values():
                mismatch_id = f"{run_day.isoformat()}:{action.action_id}"
                if action.completed_at.date() > cutoff or mismatches.get(mismatch_id) is not None:
                    continue
                confirmation = self._confirmations.status_of(action.idempotency_key)
                reason: str | None = None
                if confirmation is None:
                    reason = "no adapter confirmation"
                elif not confirmation.accepted:
                    reason = "adapter confirmation was not accepted"
                elif not confirmation.adapter_ref:
                    reason = "adapter confirmation has no reference"
                elif action.adapter_ref and confirmation.adapter_ref != action.adapter_ref:
                    reason = "adapter confirmation reference differs"
                if reason is None:
                    continue
                mismatch = ReconciliationMismatch(
                    mismatch_id=mismatch_id,
                    action_id=action.action_id,
                    plan_id=action.plan_id,
                    subscriber_ref=action.subscriber_ref,
                    expected_lkr=action.expected_lkr,
                    confirmed_lkr=None,
                    reason=reason,
                    detected_at=self._clock(),
                )
                mismatches.put(mismatch_id, mismatch)
                outbox_in(unit).append(
                    Event.of(
                        ReconciliationMismatchV1(
                            plan_id=mismatch.plan_id,
                            action_id=mismatch.action_id,
                            expected_lkr=mismatch.expected_lkr,
                            confirmed_lkr=mismatch.confirmed_lkr,
                            reason=mismatch.reason,
                        ),
                        subject=mismatch.subscriber_ref,
                    )
                )
                created.append(mismatch)
            unit.commit()
        return created

    def queue(self) -> list[ReconciliationMismatch]:
        with self._open_unit() as unit:
            records: Repository[str, ReconciliationMismatch] = unit.repository(MISMATCHES)
            return records.values()


__all__ = [
    "EXPECTED_ACTIONS",
    "MISMATCHES",
    "ExpectedAction",
    "ReconciliationMismatch",
    "ReconciliationService",
]
