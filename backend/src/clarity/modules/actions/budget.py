"""Refund budget ledger (plan §14.4, deck S7 "refund budgets").

A daily ceiling on automated spending is the blast-radius control: if a rule
misfires at 3am, the budget caps how much it can cost before a human notices.

Reservations are taken *before* execution and released if execution fails, so
a failed attempt does not quietly consume the day's allowance.

**Prototype note.** A process-local lock gives real atomicity here because the
prototype is single-process. Production holds these counters in PostgreSQL and
spends them with a conditional ``UPDATE ... WHERE remaining >= :amount``, which
is what makes concurrent decisions unable to overspend across replicas.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from decimal import Decimal

from clarity.contracts.decision import BudgetState
from clarity.kernel.common import money


@dataclass
class _Counter:
    limit: Decimal
    spent: Decimal = Decimal("0.00")
    reserved: Decimal = Decimal("0.00")

    @property
    def remaining(self) -> Decimal:
        return money(self.limit - self.spent - self.reserved)


@dataclass
class Reservation:
    """A hold on budget, released or committed once execution resolves."""

    reservation_id: str
    amount_lkr: Decimal
    rule_id: str | None = None
    settled: bool = field(default=False)


class RefundBudget:
    """Global and per-rule daily refund ceilings."""

    def __init__(
        self,
        *,
        daily_limit_lkr: Decimal | str = "250000.00",
        per_rule_limit_lkr: dict[str, Decimal | str] | None = None,
    ) -> None:
        self._lock = threading.Lock()
        self._global = _Counter(limit=money(daily_limit_lkr))
        self._per_rule: dict[str, _Counter] = {
            rule_id: _Counter(limit=money(limit))
            for rule_id, limit in (per_rule_limit_lkr or {}).items()
        }
        self._reservations: dict[str, Reservation] = {}
        self._next = 0

    # -- reading ----------------------------------------------------------- #

    def state_for(self, rule_id: str | None = None) -> BudgetState:
        """Snapshot for the decision policy's input document."""
        with self._lock:
            rule_counter = self._per_rule.get(rule_id) if rule_id else None
            return BudgetState(
                global_remaining_lkr=self._global.remaining,
                rule_remaining_lkr=rule_counter.remaining if rule_counter else None,
            )

    # -- spending ---------------------------------------------------------- #

    def reserve(self, amount: Decimal, *, rule_id: str | None = None) -> Reservation:
        """Hold budget for a plan about to execute.

        Raises :class:`ValueError` if the amount is not available, which the
        tool layer converts into a refusal.
        """
        wanted = money(amount)
        with self._lock:
            counters = [self._global]
            if rule_id and rule_id in self._per_rule:
                counters.append(self._per_rule[rule_id])
            short = next((c for c in counters if c.remaining < wanted), None)
            if short is not None:
                raise ValueError(
                    f"refund budget cannot cover LKR {wanted} (remaining LKR {short.remaining})"
                )
            for counter in counters:
                counter.reserved = money(counter.reserved + wanted)

            self._next += 1
            reservation = Reservation(
                reservation_id=f"res-{self._next:06d}", amount_lkr=wanted, rule_id=rule_id
            )
            self._reservations[reservation.reservation_id] = reservation
            return reservation

    def commit(self, reservation: Reservation) -> None:
        """Turn a hold into spend, once the actions really applied."""
        with self._lock:
            self._settle(reservation, spend=True)

    def release(self, reservation: Reservation) -> None:
        """Return a hold to the pool after a failed or compensated execution."""
        with self._lock:
            self._settle(reservation, spend=False)

    def _settle(self, reservation: Reservation, *, spend: bool) -> None:
        if reservation.settled:
            return
        counters = [self._global]
        if reservation.rule_id and reservation.rule_id in self._per_rule:
            counters.append(self._per_rule[reservation.rule_id])
        for counter in counters:
            counter.reserved = money(counter.reserved - reservation.amount_lkr)
            if spend:
                counter.spent = money(counter.spent + reservation.amount_lkr)
        reservation.settled = True

    # -- reporting --------------------------------------------------------- #

    @property
    def spent_lkr(self) -> Decimal:
        with self._lock:
            return self._global.spent
