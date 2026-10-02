"""Rule parameters from the policy store, resolved as of the event (D5).

The detection engine asks for a value by key and never learns where it came
from. This is the binding between that port and the policy resolver, built per
evaluation because the moment matters: a case about yesterday's charge is judged
by yesterday's confidence.

Why effective dating is the whole point. Risk raising a rule's confidence this
morning must not change what a decision made last week looks like, because a
receipt already told the customer what was decided and on what basis. Resolving
`as_of` the disputed event is what keeps a replay of that case honest
(ADR-0001, plan 20).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from clarity.platform.config.resolver import ConfigSnapshot, PolicyResolver


class PolicyRuleParameters:
    """``RuleParameters`` over the policy resolver."""

    def __init__(
        self,
        policies: PolicyResolver,
        *,
        as_of: datetime,
        rule_id: str | None = None,
        snapshot: ConfigSnapshot | None = None,
    ) -> None:
        self._policies = policies
        self._as_of = as_of
        # Scoped to the rule, so a value may be overridden for one rule without
        # moving every other rule's confidence at the same time.
        self._context: dict[str, str | None] = {"rule": rule_id} if rule_id else {}
        # Recording each resolution is what puts the values into the decision's
        # config snapshot hash, so a replay can prove which ones were used.
        self._snapshot = snapshot

    def confidence(self, key: str) -> Decimal:
        value = self._policies.resolve(
            key,
            as_of=self._as_of,
            context=self._context,
            snapshot=self._snapshot,
        )
        return Decimal(str(value))

    def duration(self, key: str) -> str:
        value = self._policies.resolve(
            key,
            as_of=self._as_of,
            context=self._context,
            snapshot=self._snapshot,
        )
        if not isinstance(value, str):
            raise TypeError(f"{key}: duration policy values must be ISO-8601 strings")
        return value


__all__ = ["PolicyRuleParameters"]
