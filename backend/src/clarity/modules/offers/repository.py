"""Where offer records live (OFFER01, B02).

One collection, keyed by offer id, with a secondary read by subscriber. The
secondary read is a scan rather than an index because this is the prototype and
the synthetic world holds tens of offers; the shape of the call
(``for_subscriber``) is what a driver with an index would implement, so moving
to one is a driver change and not a service change.

**Append-only.** An offer record is a claim about what HUTCH sent to a number,
and a customer's fraud check is decided against it. If it can be edited after
the check, the check proves nothing: somebody could add the offer the customer
was asking about and the answer would change retrospectively. So a correction
is a new record and the collection is in ``APPEND_ONLY``, which the migration
backs with grants so the database refuses an UPDATE rather than the code
remembering not to issue one.
"""

from __future__ import annotations

from typing import Protocol

from clarity.modules.offers.offers import OfferRecord
from clarity.platform.persistence import Repository

#: One collection is one table in B05.
OFFERS = "offers.records"


class OfferRepository(Protocol):
    """Offers HUTCH sent, by id and by subscriber."""

    def save(self, offer: OfferRecord) -> None: ...

    def get(self, offer_id: str) -> OfferRecord | None: ...

    def for_subscriber(self, subscriber_ref: str) -> list[OfferRecord]: ...

    def all_offers(self) -> list[OfferRecord]: ...


class StoredOfferRepository:
    """``OfferRepository`` over any persistence driver."""

    def __init__(self, offers: Repository[str, OfferRecord]) -> None:
        self._offers = offers

    def save(self, offer: OfferRecord) -> None:
        self._offers.put(offer.offer_id, offer)

    def get(self, offer_id: str) -> OfferRecord | None:
        return self._offers.get(offer_id)

    def for_subscriber(self, subscriber_ref: str) -> list[OfferRecord]:
        return [
            offer
            for offer in self._offers.values()
            if offer.subscriber_ref == subscriber_ref
        ]

    def all_offers(self) -> list[OfferRecord]:
        return self._offers.values()


__all__ = ["OFFERS", "OfferRepository", "StoredOfferRepository"]
