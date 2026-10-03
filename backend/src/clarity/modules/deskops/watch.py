"""Merchant watch, the regulator pack and the shift handover (D01, #26).

Plan 02 section 3.5. Three read-only views over cases the desk already has.
Nothing here decides anything or moves anything: a watch score is a reason to
look, a pack is an export of what happened, and a handover is a summary of what
is outstanding.

**Every number here is counted, never modelled.** A merchant watch score that
blended a count with a trend estimate would be a prediction wearing a count's
clothes, and the desk would act on it. So the score is a weighted count of
facts from case records, the weights are stated, and the output carries what it
was counted from so a reader can disagree with the weighting rather than with
the number.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Protocol

#: How far back a watch score and a handover look.
DEFAULT_WINDOW = timedelta(days=7)

#: What each signal contributes to a merchant's score.
#:
#: Stated as a table rather than buried in a sum, because the weighting is a
#: judgement and a reader has to be able to argue with it. These are
#: **PROPOSED TARGET - REQUIRES HUTCH VALIDATION**: they are not derived from
#: HUTCH data and nothing has tuned them.
WEIGHTS: dict[str, int] = {
    # A case naming this merchant at all.
    "case": 1,
    # A cause of unconsented charging. The signal that matters most, which is
    # why it outweighs four ordinary cases.
    "no_consent": 5,
    # Clarity moved money back because of this merchant.
    "refunded": 3,
    # The same subscriber complaining about this merchant more than once. A
    # repeat is worth more than two unrelated cases: it is the shape of a
    # merchant doing something systematic rather than making one mistake.
    "repeat_subscriber": 4,
}


class CaseFacts(Protocol):
    """The case fields these views read, supplied by the composition root.

    A protocol rather than an import of the case module, so `deskops` adds no
    module edge for a read. The composition root already holds the case service
    and can answer this.
    """

    def recent(self, since: datetime) -> Sequence[DeskCase]: ...


@dataclass(frozen=True)
class DeskCase:
    """The flattened case facts the desk views need.

    Deliberately small and already pseudonymous: `subscriber_ref` is the HMAC
    pseudonym and never an MSISDN, and there is no customer text here at all.
    A desk view is read by staff and exported to a regulator, so it carries the
    least that answers the question.
    """

    case_id: str
    subscriber_ref: str
    opened_at: datetime
    outcome: str | None = None
    cause_ref: str | None = None
    merchant_ids: tuple[str, ...] = ()
    refunded_lkr: str | None = None
    receipt_id: str | None = None
    handed_off: bool = False


@dataclass(frozen=True)
class MerchantScore:
    """One merchant, and what the count was made of."""

    merchant_id: str
    score: int
    cases: int
    no_consent: int
    refunded: int
    repeat_subscribers: int
    case_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "merchant_id": self.merchant_id,
            "score": self.score,
            # The working, so a reader can disagree with the weighting rather
            # than with the number.
            "counted_from": {
                "cases": self.cases,
                "no_consent": self.no_consent,
                "refunded": self.refunded,
                "repeat_subscribers": self.repeat_subscribers,
            },
            "case_ids": list(self.case_ids),
            "weights": {k: v for k, v in WEIGHTS.items()},
            "measured": True,
            "note": (
                "A counted score over case records, not a prediction. It is a reason "
                "to look at a merchant, not a finding about one."
            ),
        }


def merchant_watch(cases: Sequence[DeskCase]) -> list[MerchantScore]:
    """Score merchants by what the cases say, highest first.

    Ties break on merchant id so the list is stable: a desk reading the same
    window twice should see the same order, or the top of the list stops
    meaning anything.
    """
    per_merchant: dict[str, list[DeskCase]] = {}
    for case in cases:
        for merchant_id in case.merchant_ids:
            per_merchant.setdefault(merchant_id, []).append(case)

    scores: list[MerchantScore] = []
    for merchant_id, touching in per_merchant.items():
        no_consent = sum(1 for c in touching if c.cause_ref and "CONSENT" in c.cause_ref.upper())
        refunded = sum(1 for c in touching if c.refunded_lkr)
        subscribers = Counter(c.subscriber_ref for c in touching)
        repeat = sum(1 for count in subscribers.values() if count > 1)
        scores.append(
            MerchantScore(
                merchant_id=merchant_id,
                score=(
                    len(touching) * WEIGHTS["case"]
                    + no_consent * WEIGHTS["no_consent"]
                    + refunded * WEIGHTS["refunded"]
                    + repeat * WEIGHTS["repeat_subscriber"]
                ),
                cases=len(touching),
                no_consent=no_consent,
                refunded=refunded,
                repeat_subscribers=repeat,
                case_ids=tuple(sorted(c.case_id for c in touching)),
            )
        )
    return sorted(scores, key=lambda s: (-s.score, s.merchant_id))


@dataclass(frozen=True)
class RegulatorPack:
    """An export of what happened, for a regulator or an auditor.

    **Pseudonymous by construction.** Every row is keyed by `subscriber_ref`,
    the HMAC pseudonym, and the pack carries no MSISDN, no name and no customer
    text. A regulator asking "what did you do about unconsented charging"
    needs counts, causes and receipt ids, not identities, and a pack that
    carried them would be a personal data export with a different name.
    """

    pack_id: str
    window_from: datetime
    window_to: datetime
    generated_at: datetime
    generated_by: str
    cases: int
    by_outcome: dict[str, int]
    by_cause: dict[str, int]
    receipts: tuple[str, ...]
    merchants: tuple[MerchantScore, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "pack_id": self.pack_id,
            "window": {
                "from": self.window_from.isoformat(),
                "to": self.window_to.isoformat(),
            },
            "generated_at": self.generated_at.isoformat(),
            "generated_by": self.generated_by,
            "cases": self.cases,
            "by_outcome": dict(self.by_outcome),
            "by_cause": dict(self.by_cause),
            "receipts": list(self.receipts),
            "merchants": [m.to_dict() for m in self.merchants],
            "contains_personal_data": False,
            "note": (
                "Pseudonymous: every subscriber is an HMAC reference and the pack "
                "carries no MSISDN, name or customer text. Figures are counted from "
                "case records in the window. HUTCH systems are simulated in this "
                "profile and the data is synthetic."
            ),
        }


def regulator_pack(
    cases: Sequence[DeskCase],
    *,
    window_from: datetime,
    window_to: datetime,
    generated_by: str,
    now: datetime,
    pack_id: str,
) -> RegulatorPack:
    """Build the pack from cases in the window."""
    return RegulatorPack(
        pack_id=pack_id,
        window_from=window_from,
        window_to=window_to,
        generated_at=now,
        generated_by=generated_by,
        cases=len(cases),
        by_outcome=dict(Counter(c.outcome or "undecided" for c in cases)),
        by_cause=dict(Counter(c.cause_ref or "none" for c in cases)),
        receipts=tuple(sorted(c.receipt_id for c in cases if c.receipt_id)),
        merchants=tuple(merchant_watch(cases)),
    )


@dataclass(frozen=True)
class Handover:
    """What the next shift needs to know.

    Ordered by what somebody has to do something about, not by recency: a
    handover read top to bottom should let the next shift start on the oldest
    thing still waiting rather than the newest thing that happened.
    """

    shift_from: datetime
    shift_to: datetime
    prepared_by: str
    open_cases: int
    awaiting_person: tuple[str, ...]
    """Cases handed to a person and not yet resolved. The first thing to pick up."""

    executed: int
    receipts: int
    by_outcome: dict[str, int] = field(default_factory=dict)
    top_merchants: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "shift": {"from": self.shift_from.isoformat(), "to": self.shift_to.isoformat()},
            "prepared_by": self.prepared_by,
            "open_cases": self.open_cases,
            "awaiting_person": list(self.awaiting_person),
            "executed": self.executed,
            "receipts": self.receipts,
            "by_outcome": dict(self.by_outcome),
            "top_merchants": list(self.top_merchants),
        }


def handover(
    cases: Sequence[DeskCase],
    *,
    shift_from: datetime,
    shift_to: datetime,
    prepared_by: str,
    top: int = 3,
) -> Handover:
    """Summarise a shift for the next one."""
    waiting = tuple(
        sorted(
            (c.case_id for c in cases if c.handed_off and not c.receipt_id),
            key=lambda case_id: next(c.opened_at for c in cases if c.case_id == case_id),
        )
    )
    return Handover(
        shift_from=shift_from,
        shift_to=shift_to,
        prepared_by=prepared_by,
        open_cases=sum(1 for c in cases if not c.receipt_id),
        awaiting_person=waiting,
        executed=sum(1 for c in cases if c.receipt_id),
        receipts=sum(1 for c in cases if c.receipt_id),
        by_outcome=dict(Counter(c.outcome or "undecided" for c in cases)),
        top_merchants=tuple(m.merchant_id for m in merchant_watch(cases)[:top]),
    )


def window(
    now: Callable[[], datetime] | datetime, span: timedelta = DEFAULT_WINDOW
) -> tuple[datetime, datetime]:
    """The (from, to) a desk view covers. Time is injected (I11)."""
    moment = now() if callable(now) else now
    return moment - span, moment


__all__ = [
    "DEFAULT_WINDOW",
    "WEIGHTS",
    "CaseFacts",
    "DeskCase",
    "Handover",
    "MerchantScore",
    "RegulatorPack",
    "handover",
    "merchant_watch",
    "regulator_pack",
    "window",
]
