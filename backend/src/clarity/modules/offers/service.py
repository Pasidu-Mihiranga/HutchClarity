"""Recording an offer, and checking a message against the record (OFFER01).

Two jobs, and they are deliberately different permissions in the interface
layer: staff record what HUTCH sent, a customer checks a message against their
own records. Nothing here lets one do the other's job.

**Every parameter comes from the policy store.** The match thresholds, the
words that read as pressure and the list of HUTCH's own domains are all things
that change without the code changing, and all things somebody should review
before changing (I10). `_catalogue` is the only place that turns the resolver's
answers into typed values, following `foresight/catalogue.py`.

**The clock is injected** (I11): an offer's validity window and therefore a
check's answer depend on "now", and a replay has to get the same answer.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from clarity.kernel.ids import new_id
from clarity.modules.offers.offers import (
    Check,
    MatchThresholds,
    OfferRecord,
    SignalLexicon,
    check_message,
)
from clarity.modules.offers.repository import (
    OFFERS,
    OfferRepository,
    StoredOfferRepository,
)
from clarity.platform.config.resolver import PolicyResolver
from clarity.platform.persistence import (
    MemoryStore,
    MemoryUnitOfWork,
    UnitOfWork,
    UnitOfWorkFactory,
)

CONFIRM_KEY = "offers.match.confirm_containment"
REVIEW_KEY = "offers.match.review_containment"
HUTCH_HOSTS_KEY = "offers.hutch_hosts"
CODE_WORDS_KEY = "offers.signal.code_words"
CALL_WORDS_KEY = "offers.signal.call_words"
PAYMENT_WORDS_KEY = "offers.signal.payment_words"
URGENCY_WORDS_KEY = "offers.signal.urgency_words"


class OfferRefused(ValueError):
    """An offer could not be recorded, or a message could not be checked."""


def _csv(resolver: PolicyResolver, key: str, *, as_of: datetime) -> frozenset[str]:
    """A comma-separated policy value as a set of lowercased entries.

    CSV because the resolver coerces to money, number, bool and string and
    nothing else, so a list has to arrive as one of those;
    `config/policy/proactive.yaml` takes the same escape hatch.
    """
    raw = str(resolver.resolve(key, as_of=as_of) or "")
    return frozenset(part.strip().lower() for part in raw.split(",") if part.strip())


@dataclass(frozen=True)
class OfferPolicy:
    """The resolved parameters for one moment."""

    thresholds: MatchThresholds
    lexicon: SignalLexicon

    @classmethod
    def resolve(cls, resolver: PolicyResolver, *, as_of: datetime) -> OfferPolicy:
        confirm = float(resolver.resolve(CONFIRM_KEY, as_of=as_of))
        review = float(resolver.resolve(REVIEW_KEY, as_of=as_of))
        if not 0.0 < review <= confirm <= 1.0:
            # A review bar above the confirm bar would make `NEEDS_A_PERSON`
            # unreachable and silently turn a partial match into a confirmed
            # one, which is the error that matters here.
            raise OfferRefused(
                f"{REVIEW_KEY} ({review}) must be above 0 and at or below "
                f"{CONFIRM_KEY} ({confirm})"
            )
        return cls(
            thresholds=MatchThresholds(confirm=confirm, review=review),
            lexicon=SignalLexicon(
                hutch_hosts=_csv(resolver, HUTCH_HOSTS_KEY, as_of=as_of),
                code_words=_csv(resolver, CODE_WORDS_KEY, as_of=as_of),
                call_words=_csv(resolver, CALL_WORDS_KEY, as_of=as_of),
                payment_words=_csv(resolver, PAYMENT_WORDS_KEY, as_of=as_of),
                urgency_words=_csv(resolver, URGENCY_WORDS_KEY, as_of=as_of),
            ),
        )


class OfferService:
    """Offers HUTCH sent, and what a pasted message matches."""

    def __init__(
        self,
        resolver: PolicyResolver,
        *,
        open_unit: UnitOfWorkFactory | None = None,
        now: Callable[[], datetime],
    ) -> None:
        if open_unit is None:
            store = MemoryStore()

            def open_memory_unit() -> MemoryUnitOfWork:
                return MemoryUnitOfWork(store)

            open_unit = open_memory_unit
        self._open_unit = open_unit
        self._resolver = resolver
        self._now = now

    @staticmethod
    def _repository(unit: UnitOfWork) -> OfferRepository:
        return StoredOfferRepository(unit.repository(OFFERS))

    # ------------------------------------------------------------ staff side

    def record(
        self,
        *,
        subscriber_ref: str,
        msisdn_masked: str,
        title: str,
        body: str,
        offer_code: str = "",
        valid_from: datetime | None = None,
        valid_to: datetime | None = None,
        recorded_by: str,
        source: str = "hutch-sim",
    ) -> OfferRecord:
        """Record one offer against one number.

        The body is what makes a later check mean anything, so an empty one is
        refused rather than stored: an offer with no text matches nothing and
        would sit in the list looking like coverage.
        """
        if not body.strip():
            raise OfferRefused("an offer needs the message text HUTCH sent")
        if not title.strip():
            raise OfferRefused("an offer needs a title")
        if valid_to is not None and valid_from is not None and valid_to < valid_from:
            raise OfferRefused("valid_to is before valid_from")

        moment = self._now()
        offer = OfferRecord(
            offer_id=new_id("off"),
            subscriber_ref=subscriber_ref,
            msisdn_masked=msisdn_masked,
            title=title.strip(),
            body=body.strip(),
            offer_code=offer_code.strip(),
            valid_from=valid_from or moment,
            valid_to=valid_to,
            recorded_by=recorded_by,
            recorded_at=moment,
            source=source,
        )
        with self._open_unit() as unit:
            self._repository(unit).save(offer)
            # Explicit: leaving a unit without committing rolls it back, which
            # is the right default for a money path and means a write has to
            # say so.
            unit.commit()
        return offer

    def for_subscriber(self, subscriber_ref: str) -> list[OfferRecord]:
        with self._open_unit() as unit:
            return self._repository(unit).for_subscriber(subscriber_ref)

    def all_offers(self) -> list[OfferRecord]:
        with self._open_unit() as unit:
            return self._repository(unit).all_offers()

    # --------------------------------------------------------- customer side

    def check(self, *, subscriber_ref: str, message: str) -> Check:
        """Check a pasted message against this subscriber's own offers.

        Scoped by `subscriber_ref` before the comparison runs, so the domain
        function cannot widen it (I9). An empty message is refused rather than
        compared: it would match nothing and read as "not on record", which is
        a verdict about a message nobody sent.
        """
        if not message.strip():
            raise OfferRefused("paste the message you received")

        moment = self._now()
        policy = OfferPolicy.resolve(self._resolver, as_of=moment)
        with self._open_unit() as unit:
            mine = self._repository(unit).for_subscriber(subscriber_ref)
        return check_message(
            message,
            mine,
            moment=moment,
            thresholds=policy.thresholds,
            lexicon=policy.lexicon,
        )


__all__ = [
    "CALL_WORDS_KEY",
    "CODE_WORDS_KEY",
    "CONFIRM_KEY",
    "HUTCH_HOSTS_KEY",
    "PAYMENT_WORDS_KEY",
    "REVIEW_KEY",
    "URGENCY_WORDS_KEY",
    "OfferPolicy",
    "OfferRefused",
    "OfferService",
]
