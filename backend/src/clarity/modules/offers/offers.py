"""Offer records, and checking a message against them (OFFER01).

A customer gets an SMS saying HUTCH has given them 10GB free. Is it real? The
only honest way to answer is to look at what HUTCH actually sent that number,
which is what this module holds and what it compares against.

**The verdict is "on record" or "not on record", never "scam".** This is the
most important decision in the module and it is deliberate twice over.

First, I2: the pasted text is a *hint*, never evidence. What decides the answer
is the offer records for that subscriber, and the text only picks which record
to compare against. A verdict derived from how the message is worded would be
a verdict derived from the thing an attacker controls.

Second, honesty about the limit of the evidence. "We have no record of this
offer for your number" is something the system knows. "This is a scam" is an
inference beyond it: the record could be missing, the campaign could have been
sent by a partner, the corpus here is simulated. The customer is told exactly
what was checked and what was found, plus any warning signs in the message
itself, and draws the conclusion with that in front of them. That is the same
rule the rest of Clarity follows - explain with evidence, never assert what was
not checked.

**Warning signs are reported, never decisive.** A genuine HUTCH SMS can contain
a link and a scam can contain none, so the signals below never move the verdict.
They are in the answer because a customer deciding what to do about an
unrecognised message is better served by "this asks for your PIN, and HUTCH
never does" than by a bare no.

**Nothing here is a model.** Matching is weighted term containment and an offer
code, so a customer can be told precisely why a message did or did not match,
and the same input always gives the same answer (I1, I11).

**Why the terms are weighted, found by a test.** Plain containment was tried
first and it vouched for a message it should not have. A short offer is mostly
boilerplate - "3GB of bonus data has been added to your number, no activation
needed" is fourteen terms of which one is distinctive - so an unrelated
campaign written from the same template shared nine of them and cleared a 0.6
bar. The fix is the standard one: weight each term by how rare it is across the
offers on record, so matching "avurudu" counts and matching "data" does not.

The weight is unsmoothed ``log(N / df)``, which takes a term appearing in
*every* offer to exactly zero. That is deliberate and is the point: a term
every offer contains distinguishes none of them, and letting it carry even a
little is what let the false positive through. Where every term is universal
(one offer on record, or several written word for word the same) the weights
are all zero and :func:`compare` falls back to unweighted containment, because
"no term is distinctive" is not a reason to match nothing.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from clarity.ai.language import query_terms
from clarity.kernel.common import ClarityModel


class Verdict(StrEnum):
    """What the records say about a pasted message."""

    ON_RECORD = "ON_RECORD"
    """An offer on record for this number matches the message."""

    NOT_ON_RECORD = "NOT_ON_RECORD"
    """No offer on record for this number matches it.

    Not "scam". See the module docstring: this is what was checked and found,
    and the inference belongs to the person holding the phone.
    """

    NEEDS_A_PERSON = "NEEDS_A_PERSON"
    """Partly matched. Too close to dismiss, not close enough to confirm.

    The case the other two verdicts would both get wrong: a real offer that was
    forwarded with half of it cut off, and a scam built by editing a real one.
    Guessing between those is exactly what a person is for (I2).
    """


class Signal(StrEnum):
    """A warning sign found in the message text. Evidence, never a verdict."""

    LINK = "LINK"
    """Contains a web link. HUTCH offers are in the app, not behind a link."""

    NON_HUTCH_LINK = "NON_HUTCH_LINK"
    """Contains a link to a host that is not one of HUTCH's own."""

    ASKS_FOR_CODE = "ASKS_FOR_CODE"
    """Asks for an OTP, PIN or password. HUTCH never asks for one."""

    ASKS_TO_CALL = "ASKS_TO_CALL"
    """Asks the customer to call or message a number back."""

    ASKS_FOR_PAYMENT = "ASKS_FOR_PAYMENT"
    """Asks for a payment, a reload or card details to release something."""

    URGENCY = "URGENCY"
    """Presses for action inside a deadline, which is how a mark is rushed."""


class OfferRecord(ClarityModel):
    """One offer HUTCH sent to one subscriber.

    ``subscriber_ref`` is the HMAC pseudonym, never the MSISDN: this table is
    a list of who was sent what, and holding raw numbers in it would make it a
    marketing list with a breach radius. ``msisdn_masked`` is for a staff
    screen to be legible and cannot be reversed.
    """

    offer_id: str
    subscriber_ref: str
    msisdn_masked: str
    title: str
    body: str
    """The offer text as HUTCH sent it. What a pasted message is compared to."""

    offer_code: str = ""
    """A short code the real SMS carries, when it carries one.

    Worth its own field rather than being left inside the body: a code is the
    one part of an offer that is both distinctive and usually copied intact, so
    matching on it is both cheap and strong.
    """

    valid_from: datetime
    valid_to: datetime | None = None
    recorded_by: str = ""
    """The staff member who entered it, for the trail."""

    recorded_at: datetime
    source: str = "hutch-sim"
    """Where the record came from. ``hutch-sim`` is simulated (I16)."""

    def is_effective(self, moment: datetime) -> bool:
        """Whether this offer was live at ``moment``.

        An expired offer still matches a message - somebody forwarding last
        month's genuine SMS is not being defrauded - so this is reported beside
        the match rather than used to filter the record out.
        """
        if moment < self.valid_from:
            return False
        return self.valid_to is None or moment <= self.valid_to


@dataclass(frozen=True)
class MatchThresholds:
    """How much of an offer has to appear in a message to count as a match.

    From the policy store (I10). Containment rather than similarity on purpose:
    the question is "how much of the real offer is in this message", and a
    forwarded SMS with a line of chat added before it should still match. A
    symmetric measure would punish the extra words.
    """

    confirm: float
    """At or above this, the message matches the offer."""

    review: float
    """At or above this but below ``confirm``, a person looks at it."""


#: A URL, loosely. Deliberately generous: a shortener with no scheme
#: ("bit.ly/x") is the common shape in a smishing SMS, and missing it would be
#: missing the signal that matters most.
_LINK = re.compile(
    r"\b(?:https?://|www\.)?(?P<host>[a-z0-9][a-z0-9.-]*\.[a-z]{2,})(?:/\S*)?",
    re.IGNORECASE,
)

#: A phone number a message asks the reader to call back. Sri Lankan mobile
#: shapes and a generic long run of digits.
_CALLBACK = re.compile(r"(?:\+94|0)\d{9}\b|\b\d{10,}\b")


def _hosts(text: str) -> list[str]:
    """Every host-looking token in the text, lowercased."""
    out: list[str] = []
    for found in _LINK.finditer(text):
        host = found.group("host").lower().rstrip(".")
        # A decimal amount ("49.00") matches the host shape. Reject anything
        # whose last label is not alphabetic, which a TLD always is.
        if host.rsplit(".", 1)[-1].isalpha():
            out.append(host)
    return out


@dataclass(frozen=True)
class SignalLexicon:
    """The words each textual signal looks for, and HUTCH's own domains.

    All of it is policy (I10): which words read as pressure, and which hosts
    are HUTCH's, are both things that change without the code changing, and
    both are things somebody should have to review before changing.
    """

    hutch_hosts: frozenset[str]
    code_words: frozenset[str]
    call_words: frozenset[str]
    payment_words: frozenset[str]
    urgency_words: frozenset[str]

    def signals(self, text: str) -> tuple[Signal, ...]:
        """Which warning signs this text carries. Order is stable."""
        lowered = text.lower()
        found: list[Signal] = []

        hosts = _hosts(text)
        if hosts:
            found.append(Signal.LINK)
            if any(not self._is_hutch(host) for host in hosts):
                found.append(Signal.NON_HUTCH_LINK)

        if any(word in lowered for word in self.code_words):
            found.append(Signal.ASKS_FOR_CODE)
        if _CALLBACK.search(text) and any(word in lowered for word in self.call_words):
            found.append(Signal.ASKS_TO_CALL)
        if any(word in lowered for word in self.payment_words):
            found.append(Signal.ASKS_FOR_PAYMENT)
        if any(word in lowered for word in self.urgency_words):
            found.append(Signal.URGENCY)
        return tuple(found)

    def _is_hutch(self, host: str) -> bool:
        """True for a HUTCH host or a subdomain of one.

        Suffix matching on a label boundary, not ``endswith``: without the dot
        `nothutch.lk` would pass as `hutch.lk`, which is the whole trick a
        lookalike domain is built on.
        """
        return any(host == owned or host.endswith(f".{owned}") for owned in self.hutch_hosts)


def term_weights(offers: Sequence[OfferRecord]) -> dict[str, float]:
    """How distinctive each term is across the offers on record.

    ``log(N / df)``, unsmoothed, so a term in every offer weighs exactly zero.
    See the module docstring for why that matters: with a smoothed weight the
    boilerplate every campaign shares still added up to a match.
    """
    if not offers:
        return {}
    documents = [set(query_terms(f"{o.title} {o.body}")) for o in offers]
    frequency: Counter[str] = Counter()
    for terms in documents:
        frequency.update(terms)
    total = len(documents)
    return {term: math.log(total / df) for term, df in frequency.items()}


@dataclass(frozen=True)
class Comparison:
    """What comparing the message against one offer produced."""

    offer: OfferRecord
    containment: float
    """Weighted share of the offer's own terms found in the message, 0-1.

    Weighted by how distinctive each term is (see :func:`term_weights`), so
    this is "how much of what makes this offer *this* offer is present", not
    "how many words overlap".
    """

    code_matched: bool
    shared_terms: tuple[str, ...] = field(default_factory=tuple)
    distinctive_terms: tuple[str, ...] = field(default_factory=tuple)
    """The shared terms that carried weight, for explaining the match."""

    @property
    def strength(self) -> float:
        """A matched code is a full match whatever the wording looks like."""
        return 1.0 if self.code_matched else self.containment


@dataclass(frozen=True)
class Check:
    """The answer: what was compared, what matched, and what the text carries."""

    verdict: Verdict
    signals: tuple[Signal, ...]
    offers_on_record: int
    """How many offers this number has. Zero is itself worth telling somebody."""

    best: Comparison | None = None
    """The closest offer, when anything came close. Kept even when it did not
    reach the verdict, because "we found something similar" is the evidence a
    person reviewing a `NEEDS_A_PERSON` needs."""

    matched_offer_effective: bool = False
    """Whether the matched offer was live at the moment asked about."""


def compare(
    offer: OfferRecord,
    message_terms: set[str],
    message: str,
    weights: dict[str, float] | None = None,
) -> Comparison:
    """How much of what makes ``offer`` distinctive appears in the message.

    ``weights`` comes from :func:`term_weights` over the whole set on record.
    Passing none, or a set in which nothing is distinctive, falls back to
    unweighted containment.
    """
    offer_terms = set(query_terms(f"{offer.title} {offer.body}"))
    code_matched = bool(offer.offer_code) and offer.offer_code.lower() in message.lower()
    if not offer_terms:
        # An offer with no indexable terms cannot be matched by containment.
        # Its code is the only handle, and saying so beats dividing by zero.
        return Comparison(offer=offer, containment=0.0, code_matched=code_matched)

    shared = offer_terms & message_terms
    weights = weights or {}
    total_weight = sum(weights.get(term, 0.0) for term in offer_terms)

    if total_weight > 0:
        found_weight = sum(weights.get(term, 0.0) for term in shared)
        containment = found_weight / total_weight
        distinctive = tuple(sorted(term for term in shared if weights.get(term, 0.0) > 0))
    else:
        # Nothing here distinguishes one offer from another: a single offer on
        # record, or several written word for word the same. Unweighted
        # containment is the honest fallback - "no term is distinctive" is not
        # a reason to match nothing.
        containment = len(shared) / len(offer_terms)
        distinctive = ()

    return Comparison(
        offer=offer,
        containment=containment,
        code_matched=code_matched,
        shared_terms=tuple(sorted(shared)),
        distinctive_terms=distinctive,
    )


def check_message(
    message: str,
    offers: list[OfferRecord],
    *,
    moment: datetime,
    thresholds: MatchThresholds,
    lexicon: SignalLexicon,
) -> Check:
    """Compare a pasted message against the offers on record for one number.

    ``offers`` are already scoped to the subscriber by the caller: this function
    never sees a number and cannot widen the scope, which is what keeps subject
    binding in one place (I9).
    """
    signals = lexicon.signals(message)
    message_terms = set(query_terms(message))

    if not offers:
        return Check(
            verdict=Verdict.NOT_ON_RECORD,
            signals=signals,
            offers_on_record=0,
        )

    weights = term_weights(offers)
    comparisons = [compare(offer, message_terms, message, weights) for offer in offers]
    best = max(comparisons, key=lambda c: (c.strength, c.offer.offer_id))

    if best.strength >= thresholds.confirm:
        verdict = Verdict.ON_RECORD
    elif best.strength >= thresholds.review:
        verdict = Verdict.NEEDS_A_PERSON
    else:
        verdict = Verdict.NOT_ON_RECORD

    return Check(
        verdict=verdict,
        signals=signals,
        offers_on_record=len(offers),
        # The closest offer is reported for every verdict except an outright
        # miss, where naming an offer nobody is asking about would be noise.
        best=best if verdict is not Verdict.NOT_ON_RECORD else None,
        matched_offer_effective=best.offer.is_effective(moment),
    )


__all__ = [
    "Check",
    "Comparison",
    "MatchThresholds",
    "OfferRecord",
    "Signal",
    "SignalLexicon",
    "Verdict",
    "check_message",
    "compare",
    "term_weights",
]
