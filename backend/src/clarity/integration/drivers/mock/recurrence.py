"""Recurrence probe over the synthetic world.

In production each check is a read through the matching adapter (VAS consent,
charging, PCRF). Here it reads the mock world, which really does hold the
merchant block and subscription state the tool layer wrote - so a PASSED
result on the demo means the block is genuinely in place.
"""

from __future__ import annotations

from clarity.integration.drivers.mock.world import SyntheticWorld


class MockRecurrenceProbe:
    """Implements :class:`~clarity.modules.receipts.recurrence.RecurrenceProbe`."""

    def __init__(self, world: SyntheticWorld) -> None:
        self._world = world

    def check(self, name: str, subscriber_ref: str, params: dict[str, object]) -> bool | None:
        account = self._world.account(subscriber_ref)
        if account is None:
            return None

        match name:
            case "merchant_block_active":
                merchant_id = str(params.get("merchant_id", ""))
                if not merchant_id:
                    return None
                return self._world.is_merchant_blocked(subscriber_ref, merchant_id)

            case "subscription_inactive":
                subscription_id = str(params.get("subscription_id", ""))
                subscription = next(
                    (s for s in account.subscriptions if s.subscription_id == subscription_id),
                    None,
                )
                return None if subscription is None else not subscription.active

            case "data_stop_active":
                return "ENABLE_DATA_STOP" in account.safeguards

            case "spend_cap_active":
                return "SET_SPEND_CAP" in account.safeguards

            case "fup_alerts_active":
                return "ENABLE_FUP_ALERTS" in account.safeguards

        return None
