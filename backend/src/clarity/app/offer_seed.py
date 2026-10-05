"""The offers HUTCH is simulated to have sent (OFFER01).

The composition root's job, not the module's. `clarity.modules.offers` has no
opinion about which campaigns exist and must not: a module that ships its own
records is a module whose records nobody reviews.

**What these are.** Four offers against the synthetic subscriber
``+94785720767``, written in the shape a real HUTCH promotional SMS takes, plus
one that has already expired. They are the records a pasted message is compared
against, so the demo has something true to be measured by.

**They are simulated and labelled** (I16). ``source`` is ``hutch-sim``, which
is this repository's word for a simulated HUTCH system, so an answer composed
from one says where it came from. No real HUTCH campaign is reproduced here and
no real offer terms are asserted.

**REQUIRES HUTCH CONFIRMATION** for the real thing: campaign records come from
the CVM or campaign management system per subscriber, with their own effective
window, and are loaded through an integration port rather than seeded.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from clarity.integration.drivers.mock.world import ref_for
from clarity.modules.offers.public import OfferRefused, OfferService

#: The synthetic subscriber the offer journey runs on.
SEED_MSISDN = "+94785720767"

#: How the staff screen shows that number. Masked the same way the rest of the
#: system masks one, so a reviewer sees what a reviewer would see.
SEED_MASKED = "078 *** 0767"

#: Who the seeded records are attributed to. Not a real person: it is the
#: repository's label for a simulated operator action.
SEED_RECORDED_BY = "hutch-sim:campaign-load"


@dataclass(frozen=True)
class SeedOffer:
    """One simulated campaign. Typed rather than a dict so `**` keeps its types."""

    title: str
    body: str
    offer_code: str
    valid_from: datetime
    valid_to: datetime


def seed_offers(service: OfferService, *, now: Callable[[], datetime]) -> int:
    """Record the simulated offers. Returns how many were recorded.

    Idempotent by refusal is not available here - an offer id is minted per
    call - so the caller is expected to seed once, at startup, exactly as
    `seed_help_articles` is. Seeding twice would double the records, which
    would not change any verdict (containment is per offer) but would make the
    staff list misleading.
    """
    moment = now()
    recorded = 0
    offers: list[SeedOffer] = [
        # The ordinary case: a genuine offer, currently live. A customer
        # pasting this gets ON_RECORD.
        SeedOffer(
            title= "Double data on your Anytime pack",
            body=(
                "Dear Customer, your Anytime 10GB pack now carries 10GB extra "
                "data free for 30 days. Activate from the Hutch app under "
                "Packages. No charge applies. Offer code DD10."
            ),
            offer_code="DD10",
            valid_from=moment - timedelta(days=5),
            valid_to=moment + timedelta(days=25),
        ),
        # A second live offer, worded without a code, so the match has to come
        # from containment alone.
        SeedOffer(
            title= "Loyalty reload bonus",
            body=(
                "Thank you for 3 years with Hutch. Your next reload of LKR 500 "
                "or more will carry a 20 percent bonus to your main balance. "
                "Reload from the Hutch app or any Hutch dealer."
            ),
            offer_code="",
            valid_from=moment - timedelta(days=2),
            valid_to=moment + timedelta(days=12),
        ),
        # Night-time data, a common real campaign shape.
        SeedOffer(
            title= "Night data for your number",
            body=(
                "You have been given 5GB of night data, usable between 12am "
                "and 6am, valid for 14 days. It is already on your account and "
                "needs no activation. Offer code NIGHT5."
            ),
            offer_code="NIGHT5",
            valid_from=moment - timedelta(days=1),
            valid_to=moment + timedelta(days=13),
        ),
        # Expired on purpose. A customer forwarding last month's genuine SMS is
        # not being defrauded, so this has to match and be reported as expired
        # rather than read as "not on record".
        SeedOffer(
            title= "Avurudu data bonus",
            body=(
                "Happy Avurudu from Hutch. 3GB of bonus data has been added to "
                "your number, valid for 7 days. No activation needed."
            ),
            offer_code="",
            valid_from=moment - timedelta(days=90),
            valid_to=moment - timedelta(days=83),
        ),
    ]

    for offer in offers:
        try:
            service.record(
                subscriber_ref=ref_for(SEED_MSISDN),
                msisdn_masked=SEED_MASKED,
                recorded_by=SEED_RECORDED_BY,
                source="hutch-sim",
                title=offer.title,
                body=offer.body,
                offer_code=offer.offer_code,
                valid_from=offer.valid_from,
                valid_to=offer.valid_to,
            )
        except OfferRefused:
            # The service's refusal is the authority; a seed must not override
            # one. Skipping keeps a bad row out rather than forcing it in.
            continue
        recorded += 1
    return recorded


__all__ = ["SEED_MASKED", "SEED_MSISDN", "SEED_RECORDED_BY", "SeedOffer", "seed_offers"]
