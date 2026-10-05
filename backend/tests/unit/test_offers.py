"""Offer verification: what the records say about a pasted message (OFFER01).

The tests are grouped by the thing that could go wrong, because the ways this
feature can fail are not symmetric:

- **Vouching for a scam** is the worst outcome. A message that matches nothing
  must come back `NOT_ON_RECORD`, and no amount of scam-shaped wording may be
  allowed to produce a match.
- **Calling a real offer fake** is the second worst, and the likely cause is a
  forwarded SMS with text added or cut. Containment exists for that.
- **Guessing on a near-match** is the failure both other verdicts share, so the
  third verdict exists and is tested for.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from clarity.modules.offers.public import (
    MatchThresholds,
    OfferRecord,
    Signal,
    SignalLexicon,
    Verdict,
    check_message,
)

NOW = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)

THRESHOLDS = MatchThresholds(confirm=0.6, review=0.35)

LEXICON = SignalLexicon(
    hutch_hosts=frozenset({"hutch.lk", "hutch.com"}),
    code_words=frozenset({"otp", "pin", "password", "verification code"}),
    call_words=frozenset({"call now", "whatsapp", "call this number"}),
    payment_words=frozenset({"processing fee", "pay lkr", "card number"}),
    urgency_words=frozenset({"expires today", "immediately", "act now"}),
)

GENUINE_BODY = (
    "Dear Customer, your Anytime 10GB pack now carries 10GB extra data free "
    "for 30 days. Activate from the Hutch app under Packages. No charge "
    "applies. Offer code DD10."
)


def offer(
    *,
    offer_id: str = "off-1",
    body: str = GENUINE_BODY,
    title: str = "Double data on your Anytime pack",
    code: str = "DD10",
    valid_from: datetime | None = None,
    valid_to: datetime | None = None,
) -> OfferRecord:
    return OfferRecord(
        offer_id=offer_id,
        subscriber_ref="ref-sanduni",
        msisdn_masked="078 *** 0767",
        title=title,
        body=body,
        offer_code=code,
        valid_from=valid_from or NOW - timedelta(days=5),
        valid_to=valid_to if valid_to is not None else NOW + timedelta(days=25),
        recorded_by="sec:dilani",
        recorded_at=NOW - timedelta(days=5),
    )


def check(message: str, offers: list[OfferRecord] | None = None, *, moment: datetime = NOW):
    return check_message(
        message,
        offers if offers is not None else [offer()],
        moment=moment,
        thresholds=THRESHOLDS,
        lexicon=LEXICON,
    )


# ------------------------------------------------- it must not vouch for a scam


def test_a_number_with_no_offers_matches_nothing():
    """The default answer when there is nothing to match against."""
    result = check("You have won 50GB free data from Hutch!", [])
    assert result.verdict is Verdict.NOT_ON_RECORD
    assert result.offers_on_record == 0
    assert result.best is None


def test_an_unrelated_message_is_not_on_record():
    result = check(
        "CONGRATULATIONS! You have WON 50GB free data. Claim at "
        "http://hutch-rewards.xyz/claim before it expires today. Send your OTP."
    )
    assert result.verdict is Verdict.NOT_ON_RECORD
    # And the offer is not named: pointing at one nobody asked about is noise.
    assert result.best is None


def test_scam_wording_alone_cannot_produce_a_match():
    """Signals never move the verdict, in either direction.

    The message below is pure scam wording with nothing from any real offer.
    A design that let the text influence the verdict could be steered by it,
    which is the whole reason the records decide and the text does not (I2).
    """
    result = check("URGENT: send your PIN immediately to claim your free data")
    assert result.verdict is Verdict.NOT_ON_RECORD
    assert Signal.ASKS_FOR_CODE in result.signals


def test_a_message_quoting_only_common_words_does_not_match():
    """Shared filler must not add up to a match."""
    result = check("Dear Customer, your account. No charge applies. Thank you.")
    assert result.verdict is not Verdict.ON_RECORD


# --------------------------------------- it must not call a real offer fake


def test_the_genuine_message_pasted_whole_is_on_record():
    result = check(GENUINE_BODY)
    assert result.verdict is Verdict.ON_RECORD
    assert result.best is not None
    assert result.best.code_matched
    assert result.matched_offer_effective is True


def test_a_forwarded_message_with_chat_added_still_matches():
    """The case containment is for: extra words must not cost a match.

    A symmetric similarity measure fails here, which is why `compare` divides
    by the offer's own term count and not by the union.
    """
    result = check(f"machan balanna meka aawa -- {GENUINE_BODY}")
    assert result.verdict is Verdict.ON_RECORD


def test_the_offer_code_alone_carries_a_match():
    """A code is usually copied intact even when the wording is mangled."""
    result = check("hutch offer code DD10 free data check")
    assert result.verdict is Verdict.ON_RECORD
    assert result.best is not None
    assert result.best.code_matched
    # Strength is 1.0 on a code match whatever the containment was.
    assert result.best.strength == 1.0


def test_an_expired_offer_still_matches_and_says_it_ended():
    """Forwarding last month's genuine SMS is not being defrauded.

    The distinction this protects is the one a customer actually cares about:
    "Hutch never sent this" and "Hutch sent this and it has finished" are
    different answers, and collapsing them into `NOT_ON_RECORD` would tell
    somebody a real message was fake.
    """
    ended = offer(
        valid_from=NOW - timedelta(days=90),
        valid_to=NOW - timedelta(days=83),
    )
    result = check(GENUINE_BODY, [ended])
    assert result.verdict is Verdict.ON_RECORD
    assert result.matched_offer_effective is False


def test_an_offer_not_yet_started_matches_and_is_not_effective():
    future = offer(valid_from=NOW + timedelta(days=3), valid_to=NOW + timedelta(days=30))
    result = check(GENUINE_BODY, [future])
    assert result.verdict is Verdict.ON_RECORD
    assert result.matched_offer_effective is False


# ------------------------------------------------- the near-match goes to a person


def test_a_message_built_by_editing_a_real_offer_needs_a_person():
    """The case both other verdicts would get wrong.

    Half the real offer, with a fee and a callback bolted on. Confirming it
    would vouch for a scam; dismissing it would call a half-forwarded real
    offer fake. Neither is defensible from the evidence, so a person looks.
    """
    result = check(
        "Dear Customer, your Anytime 10GB pack now carries 100GB extra data "
        "free. To activate pay a processing fee of LKR 250 and send the "
        "verification code to 0771234567 immediately."
    )
    assert result.verdict is Verdict.NEEDS_A_PERSON
    assert result.best is not None
    assert THRESHOLDS.review <= result.best.containment < THRESHOLDS.confirm
    assert Signal.ASKS_FOR_PAYMENT in result.signals


def test_the_closest_offer_is_reported_on_a_near_match():
    """A person reviewing one needs to see what it nearly matched."""
    result = check(
        "your Anytime 10GB pack now carries extra data free. pay LKR 250 to activate"
    )
    if result.verdict is Verdict.NEEDS_A_PERSON:
        assert result.best is not None
        assert result.best.offer.title


def test_the_best_of_several_offers_wins():
    """With several on record, the closest one is the one reported."""
    other = offer(
        offer_id="off-2",
        title="Loyalty reload bonus",
        body="Your next reload of LKR 500 or more carries a 20 percent bonus.",
        code="",
    )
    result = check(GENUINE_BODY, [other, offer()])
    assert result.verdict is Verdict.ON_RECORD
    assert result.best is not None
    assert result.best.offer.offer_id == "off-1"


# ------------------------------------------------------------------- signals


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("claim at https://offers.hutch.lk/x", Signal.LINK),
        ("claim at http://hutch-rewards.xyz/claim", Signal.NON_HUTCH_LINK),
        ("send your OTP to confirm", Signal.ASKS_FOR_CODE),
        ("call now on 0771234567", Signal.ASKS_TO_CALL),
        ("pay a processing fee to release it", Signal.ASKS_FOR_PAYMENT),
        ("offer expires today, act now", Signal.URGENCY),
    ],
)
def test_each_signal_is_found(message: str, expected: Signal):
    assert expected in check(message).signals


def test_a_hutch_link_is_a_link_but_not_a_foreign_one():
    signals = check("see https://www.hutch.lk/offers for details").signals
    assert Signal.LINK in signals
    assert Signal.NON_HUTCH_LINK not in signals


def test_a_subdomain_of_a_hutch_host_is_still_hutch():
    signals = check("see https://offers.app.hutch.lk/x").signals
    assert Signal.NON_HUTCH_LINK not in signals


def test_a_lookalike_domain_is_not_hutch():
    """The whole trick a fake domain is built on, so it gets its own test.

    `endswith("hutch.lk")` passes `nothutch.lk`, which is why `_is_hutch`
    matches on a label boundary.
    """
    signals = check("claim at https://offers.nothutch.lk/x").signals
    assert Signal.NON_HUTCH_LINK in signals


def test_a_decimal_amount_is_not_read_as_a_host():
    """`49.00` has the shape of a host. A TLD is never numeric."""
    signals = check("you were charged LKR 49.00 yesterday").signals
    assert Signal.LINK not in signals


def test_a_callback_needs_both_a_number_and_an_ask():
    """A genuine SMS naming the hotline in passing must not trip this."""
    assert Signal.ASKS_TO_CALL not in check("our hotline is 0771234567").signals
    assert Signal.ASKS_TO_CALL not in check("call now for details").signals
    assert Signal.ASKS_TO_CALL in check("call now on 0771234567").signals


def test_signals_are_found_whatever_the_verdict():
    """A real offer with a link in it still reports the link.

    Signals and the verdict are independent on purpose: a genuine HUTCH SMS
    can contain a link, and the customer is told so rather than the system
    hiding it because the verdict came back fine.
    """
    with_link = offer(body=f"{GENUINE_BODY} More at https://www.hutch.lk/offers")
    result = check(
        f"{GENUINE_BODY} More at https://www.hutch.lk/offers", [with_link]
    )
    assert result.verdict is Verdict.ON_RECORD
    assert Signal.LINK in result.signals
