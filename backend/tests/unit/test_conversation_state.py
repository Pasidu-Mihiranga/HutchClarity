"""Conversation state, its TTL, and the reply verifier (C01, issue #19).

Two units that the acceptance tests exercise but do not pin down: the TTL, which
needs a controlled clock, and the verifier, which is the thing standing between
a model-written sentence and a customer reading a figure nobody decided.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from clarity.modules.conversation.state import (
    DEFAULT_TTL,
    ConversationState,
    ConversationStore,
)
from clarity.modules.conversation.verify import verify_reply

CASE = "CASE-01J0000000000000000000001"
AT = datetime(2026, 10, 3, 9, 0, tzinfo=UTC)


# -- the TTL -------------------------------------------------------------- #


def test_state_resumes_within_the_ttl():
    store = ConversationStore()
    store.resume_or_start(CASE, channel="whatsapp", now=AT)

    found = store.get(CASE, now=AT + DEFAULT_TTL - timedelta(minutes=1))

    assert found is not None
    assert found.case_id == CASE


def test_state_is_gone_once_the_ttl_has_passed():
    store = ConversationStore()
    store.resume_or_start(CASE, channel="whatsapp", now=AT)

    assert store.get(CASE, now=AT + DEFAULT_TTL) is None


def test_an_expired_conversation_starts_fresh_rather_than_resuming():
    store = ConversationStore()
    first, _ = store.resume_or_start(CASE, channel="whatsapp", now=AT)
    first.slots["amount_lkr"] = "49"
    store.save(first, now=AT)

    later, resumed = store.resume_or_start(
        CASE, channel="app", now=AT + DEFAULT_TTL + timedelta(seconds=1)
    )

    assert resumed is False
    assert later.turn_no == 0
    assert later.slots == {}
    assert later.channels == ["app"]


def test_each_turn_extends_the_window():
    """A conversation someone is still having must not expire mid-sentence."""
    store = ConversationStore()
    state, _ = store.resume_or_start(CASE, channel="app", now=AT)

    # Active 20 hours in, with a 24 hour TTL.
    active = AT + timedelta(hours=20)
    store.save(state, now=active)

    # Would have expired on the original clock, but the turn pushed it out.
    assert store.get(CASE, now=AT + DEFAULT_TTL + timedelta(hours=1)) is not None
    assert store.get(CASE, now=active + DEFAULT_TTL) is None


def test_expiry_is_applied_on_read_not_by_a_sweeper():
    """A sweeper that has not run yet would hand back state past its TTL."""
    store = ConversationStore()
    store.resume_or_start(CASE, channel="app", now=AT)

    past = AT + DEFAULT_TTL + timedelta(hours=5)
    assert store.get(CASE, now=past) is None
    # And it is actually gone, so a later call with an earlier clock cannot
    # bring it back.
    assert store.get(CASE, now=AT) is None


def test_purge_removes_expired_rows_and_leaves_live_ones():
    store = ConversationStore()
    store.resume_or_start("CASE-old", channel="app", now=AT)
    store.resume_or_start("CASE-new", channel="app", now=AT + timedelta(hours=23))

    removed = store.purge_expired(now=AT + DEFAULT_TTL + timedelta(minutes=1))

    assert removed == 1
    assert store.get("CASE-new", now=AT + timedelta(hours=23)) is not None


def test_a_shorter_ttl_can_be_configured():
    store = ConversationStore(ttl=timedelta(minutes=30))
    store.resume_or_start(CASE, channel="app", now=AT)

    assert store.get(CASE, now=AT + timedelta(minutes=29)) is not None
    assert store.get(CASE, now=AT + timedelta(minutes=31)) is None


def test_the_channel_trail_does_not_repeat_the_same_channel():
    store = ConversationStore()
    store.resume_or_start(CASE, channel="app", now=AT)
    store.resume_or_start(CASE, channel="app", now=AT + timedelta(minutes=1))
    state, _ = store.resume_or_start(CASE, channel="whatsapp", now=AT + timedelta(minutes=2))

    assert state.channels == ["app", "whatsapp"]


def test_state_carries_no_message_text_by_shape():
    """There is nowhere to put a transcript, which is the point."""
    fields = set(ConversationState.__dataclass_fields__)

    assert "text" not in fields
    assert "history" not in fields
    assert "messages" not in fields
    assert "transcript" not in fields


# -- the verifier --------------------------------------------------------- #


def test_a_figure_in_the_facts_passes():
    result = verify_reply(
        "We found a charge of LKR 49.00 and reversed nothing yet.",
        facts={"amount_lkr": "49.00"},
    )

    assert result.ok, result.failures


def test_a_figure_not_in_the_facts_is_refused():
    """I1 from the output side: a figure nobody decided must not be sent."""
    result = verify_reply("We will refund LKR 50000 today.", facts={"amount_lkr": "49.00"})

    assert not result.ok
    assert "NUMBER_NOT_IN_FACTS" in result.failures
    assert "50000" in result.detail["unsupported_figures"]


def test_formatting_does_not_make_a_correct_figure_fail():
    """1,500.00 and 1500 are the same amount."""
    result = verify_reply("That is LKR 1,500.00 in total.", facts={"total": "1500"})

    assert result.ok, result.failures


def test_a_figure_nested_in_the_facts_is_accepted():
    """Requiring callers to flatten first is how a check gets switched off."""
    result = verify_reply(
        "The charge was LKR 49.00.",
        facts={"evidence": [{"event": {"amount_lkr": "49.00"}}]},
    )

    assert result.ok, result.failures


def test_a_duration_in_a_template_is_not_treated_as_a_figure():
    """Flagging "within 24 hours" trains everyone to ignore the verifier."""
    result = verify_reply("A person will look at this within 24 hours.", facts={})

    assert result.ok, result.failures


def test_claiming_a_refund_happened_when_nothing_executed_is_refused():
    """The most damaging sentence available: the customer stops chasing it."""
    result = verify_reply("I have refunded the charge.", facts={"amount_lkr": "49.00"})

    assert not result.ok
    assert "UNAUTHORISED_PROMISE" in result.failures


def test_the_same_claim_is_allowed_once_something_really_executed():
    """The guard for the test above, so the check is not just a word filter."""
    result = verify_reply(
        "I have refunded the charge.",
        facts={"amount_lkr": "49.00", "receipt_id": "RCPT-1"},
    )

    assert result.ok, result.failures


def test_a_card_number_in_a_reply_is_refused():
    result = verify_reply("Your card 4111111111111111 was charged.", facts={})

    assert not result.ok
    assert "FORBIDDEN_CONTENT" in result.failures


def test_missing_citations_fail_only_when_they_are_required():
    without = verify_reply("The fair use cap applies.", facts={}, require_citations=True)
    not_required = verify_reply("The fair use cap applies.", facts={})

    assert "CITATION_MISSING" in without.failures
    assert not_required.ok


def test_falling_back_to_english_warns_rather_than_blocking():
    """Worse than Sinhala, better than silence. Recorded and sent."""
    result = verify_reply("A person will help you shortly.", facts={}, language="si")

    assert result.ok
    assert "LANGUAGE_FALLBACK" in result.warnings
    assert result.failures == ()


def test_a_sinhala_reply_does_not_warn():
    result = verify_reply("ඔබගේ ගැටලුව බලමු.", facts={}, language="si")

    assert result.ok
    assert result.warnings == ()


@pytest.mark.parametrize("language", ["si", "ta"])
def test_the_language_check_covers_both_scripts(language):
    result = verify_reply("A person will help you shortly.", facts={}, language=language)

    assert "LANGUAGE_FALLBACK" in result.warnings
