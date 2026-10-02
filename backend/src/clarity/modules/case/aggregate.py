"""The case aggregate: the record and its state machine (M-CASE).

What this module owns is one case's identity, its evidence, its decision and
the states it may move between. What it deliberately does **not** own is the
sequence of calls that fills those in: that is orchestration, and it lives in
``clarity.modules.resolution`` (plan 21 section 2.2).

The split matters for a reason beyond tidiness. The orchestrator calls six
modules; the aggregate calls none. Separating them makes ``case`` a leaf in the
dependency map, so the module that holds the customer's case can be reasoned
about, tested and eventually deployed without dragging the rest of the system
behind it.
"""

from __future__ import annotations

import threading
from datetime import datetime

from clarity.contracts.case import Case, CaseState, CaseTrigger, CustomerReference
from clarity.contracts.decision import ActionType, Decision, Outcome
from clarity.kernel.common import Channel, Language, utc_now
from clarity.kernel.ids import case_no as make_case_no
from clarity.kernel.ids import new_id
from clarity.modules.case.records import CaseNotFound, CaseNotReady, CaseRecord
from clarity.modules.case.repository import CaseRepository
from clarity.platform.persistence import ConcurrentUpdate

#: Channels that cannot capture a reliable confirmation for a service change
#: (plan section 9.7). The decision policy uses this to route them to staff.
NO_CONFIRMATION_CHANNELS = frozenset({Channel.SMS, Channel.USSD})


class CaseAggregate:
    """One case's state, and the only code that moves it between states."""

    def __init__(
        self,
        cases: CaseRepository,
        *,
        clock: datetime | None = None,
    ) -> None:
        # All case state lives in the repository (B02): the aggregate keeps none.
        self._cases = cases
        self._clock = clock
        self._lock = threading.Lock()

    def open_case(
        self,
        *,
        subscriber_ref: str,
        msisdn_masked: str,
        channel: Channel,
        trigger: CaseTrigger = CaseTrigger.CUSTOMER,
        language: Language = Language.EN,
        charge_ref: str | None = None,
    ) -> Case:
        with self._lock:
            sequence = self._cases.next_case_number()
            case = Case(
                case_id=new_id("CASE"),
                case_no=make_case_no(sequence, year=self._now().year),
                customer=CustomerReference(
                    subscriber_ref=subscriber_ref,
                    msisdn_masked=msisdn_masked,
                    preferred_language=language,
                ),
                trigger=trigger,
                origin_channel=channel,
                language=language,
                charge_ref=charge_ref,
                opened_at=self._now(),
            )
            self._cases.save(CaseRecord(case=case, subscriber_ref=subscriber_ref))
            return case

    def get(self, case_id: str) -> CaseRecord:
        record = self._cases.get(case_id)
        if record is None:
            raise CaseNotFound(case_id)
        return record

    def save(self, record: CaseRecord) -> None:
        """Persist a record the caller mutated.

        The service mutates a record in place and then writes it back, so a
        driver that stores a copy (B05) sees every change. Strict: a conflict
        here means two callers changed one case differently, and silently
        dropping one of those changes is how a case loses its decision.
        """
        self._cases.save(record)

    def _cache_outcome(self, record: CaseRecord) -> None:
        """Write back the outcome facts that other modules own.

        ``execution`` and ``receipts_by_plan`` are this module's read cache of
        state the actions and receipts modules are authoritative for. Two
        confirmations of one plan necessarily produce the same values: the tool
        layer's idempotency key gives one execution result, and the receipt's
        plan index gives one receipt. So a conflict means another thread already
        wrote the identical cache, and standing down loses nothing.

        Unlike :meth:`save`, which stays strict, because a conflict there is a
        genuine lost update.
        """
        try:
            self._cases.save(record)
        except ConcurrentUpdate:
            return

    def all_cases(self) -> list[CaseRecord]:
        return self._cases.all_records()

    # ------------------------------------------------------------------ #
    # Evidence and decision
    # ------------------------------------------------------------------ #

    def _advance(self, record: CaseRecord, target: CaseState) -> None:
        """Move the case on, tolerating a no-op when it is already there.

        Does not persist: a public method advances the case through several
        states in one go, and the enclosing method writes the record back once
        it is finished.
        """
        if record.case.state is target:
            return
        record.case = record.case.with_state(target)

    @staticmethod
    def _state_for(outcome: Outcome) -> CaseState:
        match outcome:
            case Outcome.AUTO_FIX:
                return CaseState.EXECUTING
            case Outcome.ONE_TAP_FIX:
                return CaseState.AWAITING_CUSTOMER
            case Outcome.STAFF_APPROVAL:
                return CaseState.AWAITING_APPROVAL
            case Outcome.EXPLAIN_ONLY:
                return CaseState.EXPLAINED
            case _:
                return CaseState.HANDED_OFF

    # ------------------------------------------------------------------ #
    # Act
    # ------------------------------------------------------------------ #

    @staticmethod
    def _require_decision(record: CaseRecord) -> Decision:
        if record.decision is None:
            raise CaseNotReady(f"case {record.case_id} has not been evaluated yet")
        return record.decision

    def _safeguard_params(self, record: CaseRecord) -> dict[ActionType, dict[str, object]]:
        """Fill action parameters from evidence, not from the caller.

        The subscription and merchant a remedy applies to come from the events
        the rule matched, so a caller cannot redirect a block onto a different
        merchant.
        """
        flat = self._flat_safeguard_params(record)
        return {
            ActionType.DEACTIVATE_VAS: {k: v for k, v in flat.items() if k == "subscription_id"},
            ActionType.BLOCK_MERCHANT_UNTIL_OPTIN: {
                k: v for k, v in flat.items() if k == "merchant_id"
            },
        }

    @staticmethod
    def _flat_safeguard_params(record: CaseRecord) -> dict[str, object]:
        evaluation, snapshot = record.evaluation, record.snapshot
        if evaluation is None or evaluation.top is None or snapshot is None:
            return {}

        params: dict[str, object] = {}
        for event in evaluation.top.bindings.values():
            for key in ("subscription_id", "merchant_id", "bucket", "offering_id"):
                value = event.attr(key)
                if value is not None and key not in params:
                    params[key] = value
        return params

    def _now(self) -> datetime:
        """Fixed clock in the demo, wall clock otherwise."""
        return self._clock or utc_now()

    # ------------------------------------------------------------------ #
    # Open
    # ------------------------------------------------------------------ #


__all__ = [
    "NO_CONFIRMATION_CHANNELS",
    "CaseAggregate",
    "CaseNotFound",
    "CaseNotReady",
    "CaseRecord",
]
