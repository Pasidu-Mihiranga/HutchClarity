"""Mock drivers for the eight sources, plus the command port.

These implement the same ports a HUTCH sandbox or production driver would, so
swapping them is a config change, not a code change (plan §9.1 principle 4).
"""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Any

from clarity.contracts.decision import ActionType
from clarity.contracts.timeline import TimelineEvent
from clarity.integration.drivers.mock.world import SyntheticWorld
from clarity.integration.ports import (
    AdapterUnavailable,
    Command,
    CommandPort,
    CommandResult,
    SourceRead,
)
from clarity.kernel.common import Completeness, EventSource, money


class MockReadAdapter:
    """Reads one source out of the synthetic world."""

    def __init__(self, source: EventSource, world: SyntheticWorld) -> None:
        self.source = source
        self._world = world

    def read(self, subscriber_ref: str, window_from: datetime, window_to: datetime) -> SourceRead:
        if self.source in self._world.unavailable:
            # Demonstrates graceful degradation (plan §39): the case is held,
            # never decided on evidence we could not read.
            raise AdapterUnavailable(
                self.source, "UPSTREAM_TIMEOUT", "mock source marked unavailable"
            )

        account = self._world.account(subscriber_ref)
        window_days = max((window_to - window_from).days, 0)
        if account is None:
            return SourceRead(
                source=self.source,
                events=[],
                completeness=Completeness.MISSING,
                note="subscriber not known to this source",
                queried_window_days=window_days,
            )

        events: list[TimelineEvent] = [
            event
            for event in account.records.get(self.source, [])
            if window_from <= event.occurred_at <= window_to
        ]
        events.sort(key=lambda e: e.occurred_at)
        return SourceRead(
            source=self.source,
            events=events,
            completeness=Completeness.COMPLETE,
            queried_window_days=window_days,
        )


class MockCommandAdapter(CommandPort):
    """Applies approved actions to the synthetic world, idempotently.

    Replaying an idempotency key returns the first result instead of acting
    again, which is what keeps "zero duplicate financial executions" true
    (plan §4.2 NFR-COR-01).
    """

    source = EventSource.CHARGING

    _SUPPORTED = frozenset(
        {
            ActionType.REFUND,
            ActionType.DEACTIVATE_VAS,
            ActionType.BLOCK_MERCHANT_UNTIL_OPTIN,
            ActionType.SET_SPEND_CAP,
            ActionType.ENABLE_DATA_STOP,
            ActionType.ENABLE_FUP_ALERTS,
        }
    )

    def __init__(self, world: SyntheticWorld) -> None:
        self._world = world
        self._executed: dict[str, CommandResult] = {}
        self._lock = threading.Lock()

    def supports(self, action_type: ActionType) -> bool:
        return action_type in self._SUPPORTED

    def status_of(self, idempotency_key: str) -> CommandResult | None:
        return self._executed.get(idempotency_key)

    def execute(self, command: Command) -> CommandResult:
        previous = self._executed.get(command.idempotency_key)
        if previous is not None:
            return previous.model_copy(update={"replayed": True})

        if not self.supports(command.action_type):
            return CommandResult(accepted=False, error_code="ACTION_NOT_SUPPORTED_BY_ADAPTER")

        result = self._apply(command)
        self._executed[command.idempotency_key] = result
        return result

    def _apply(self, command: Command) -> CommandResult:
        ref = command.subscriber_ref
        params: dict[str, Any] = command.params

        match command.action_type:
            case ActionType.REFUND:
                amount = money(command.amount_lkr or 0)
                if amount <= 0:
                    return CommandResult(accepted=False, error_code="INVALID_AMOUNT")
                before, after = self._world.credit_balance(
                    ref, amount, reason=params.get("reason", "clarity_refund")
                )
                return CommandResult(
                    accepted=True,
                    adapter_ref=self._world.next_id("adj"),
                    before_state={"balance_lkr": f"{before:.2f}"},
                    after_state={"balance_lkr": f"{after:.2f}"},
                )

            case ActionType.DEACTIVATE_VAS:
                subscription_id = str(params.get("subscription_id", ""))
                changed = self._world.deactivate_subscription(ref, subscription_id)
                if not changed:
                    return CommandResult(
                        accepted=True,
                        adapter_ref=self._world.next_id("vas"),
                        before_state={"subscription_active": False},
                        after_state={"subscription_active": False},
                    )
                return CommandResult(
                    accepted=True,
                    adapter_ref=self._world.next_id("vas"),
                    before_state={"subscription_active": True},
                    after_state={"subscription_active": False},
                )

            case ActionType.BLOCK_MERCHANT_UNTIL_OPTIN:
                merchant_id = str(params.get("merchant_id", ""))
                newly = self._world.block_merchant(ref, merchant_id)
                return CommandResult(
                    accepted=True,
                    adapter_ref=self._world.next_id("blk"),
                    before_state={"merchant_blocked": not newly},
                    after_state={"merchant_blocked": True},
                )

            case (
                ActionType.SET_SPEND_CAP
                | ActionType.ENABLE_DATA_STOP
                | ActionType.ENABLE_FUP_ALERTS
            ):
                kind = command.action_type.value
                previous_safeguards = self._world.set_safeguard(ref, kind, params)
                return CommandResult(
                    accepted=True,
                    adapter_ref=self._world.next_id("sgd"),
                    before_state={"safeguards": dict(previous_safeguards)},
                    after_state={"safeguards": {kind: params}},
                )

        return CommandResult(accepted=False, error_code="ACTION_NOT_SUPPORTED_BY_ADAPTER")
