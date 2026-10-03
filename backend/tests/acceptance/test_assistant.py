"""The assistant across channels (C01, issue #19; plan 22 sections 4 and 9).

Acceptance test 1 for C01 is the first test here: a customer starts on WhatsApp,
continues in the app, and because it is the same case it is the same
conversation. Black-box over `/v1`, like the rest of this suite.

The continuity mechanism is deliberately not a session: state is keyed by case
id. Keying it by session or channel would make "carry on where I left off" a
per-channel feature, which is the thing plan 22 section 9 rules out. So the
test asserts on what survives the channel change, and the test after it asserts
that a *different* case does not inherit any of it, because a continuity test
that would pass with one shared bucket of state proves nothing.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from .conftest import DILANI, NIMAL, customer_token


def _open_case(api: TestClient, headers: dict[str, str], msisdn: str) -> str:
    opened = api.post("/v1/cases", json={"msisdn": msisdn}, headers=headers)
    assert opened.status_code == 201, opened.text
    return str(opened.json()["case_id"])


def _turn(
    api: TestClient,
    headers: dict[str, str],
    case_id: str,
    text: str,
    *,
    channel: str,
) -> dict:
    sent = api.post(
        "/v1/conversation/turn",
        json={"text": text, "case_id": case_id, "channel": channel},
        headers=headers,
    )
    assert sent.status_code == 200, sent.text
    return dict(sent.json()["turn"])


@pytest.fixture
def me(api: TestClient) -> dict[str, str]:
    return {"Authorization": f"Bearer {customer_token(api, DILANI)}"}


# -- acceptance 1 --------------------------------------------------------- #


def test_a_conversation_started_on_whatsapp_continues_in_the_app(api, me):
    """C01 acceptance 1: same case id, so the flow resumes where it was."""
    case_id = _open_case(api, me, DILANI)

    first = _turn(
        api,
        me,
        case_id,
        "I was charged LKR 49 twice for a subscription I never agreed to",
        channel="whatsapp",
    )
    second = _turn(api, me, case_id, "has it been sorted?", channel="app")

    # The same conversation, not two first turns.
    assert first["state"]["turn_no"] == 1
    assert second["state"]["turn_no"] == 2
    assert second["state"]["case_id"] == case_id == first["state"]["case_id"]

    # The handover itself is visible, in order, rather than being inferable
    # from two timestamps.
    assert first["state"]["channels"] == ["whatsapp"]
    assert second["state"]["channels"] == ["whatsapp", "app"]

    # Resumed, and the flow state carried rather than restarting.
    assert second["state"]["flow"] == first["state"]["flow"]
    assert second["state"]["state"] == first["state"]["state"]

    # The strongest evidence that it actually resumed: the hint picked up on
    # WhatsApp is still there in the app, where the second message mentions no
    # amount at all.
    assert first["state"]["slots"].get("amount_lkr") == "49"
    assert second["state"]["slots"].get("amount_lkr") == "49"
    assert "49" not in "has it been sorted?"


def test_a_different_case_starts_a_fresh_conversation(api, me):
    """The guard for the test above: state is per case, not one shared bucket."""
    first_case = _open_case(api, me, DILANI)
    _turn(api, me, first_case, "charged LKR 49 twice", channel="whatsapp")

    second_case = _open_case(api, me, DILANI)
    fresh = _turn(api, me, second_case, "what is this charge?", channel="app")

    assert fresh["state"]["turn_no"] == 1
    assert fresh["state"]["channels"] == ["app"]
    assert fresh["state"]["slots"].get("amount_lkr") is None


# -- the case path is subject bound --------------------------------------- #


def test_another_customer_cannot_continue_my_conversation(api, me):
    """Conversation state is case scoped, so the route is too (I9).

    Without this the case id alone would read and extend someone else's
    conversation, which is the hole A04 found on the MCP side: a binding that
    is checked only when convenient is not a binding.
    """
    case_id = _open_case(api, me, DILANI)
    _turn(api, me, case_id, "charged LKR 49 twice", channel="whatsapp")

    stranger = {"Authorization": f"Bearer {customer_token(api, NIMAL)}"}
    refused = api.post(
        "/v1/conversation/turn",
        json={"text": "what is happening with my case?", "case_id": case_id, "channel": "app"},
        headers=stranger,
    )

    assert refused.status_code == 403, refused.text


def test_continuing_a_case_conversation_needs_a_session(api, me):
    case_id = _open_case(api, me, DILANI)

    anonymous = api.post(
        "/v1/conversation/turn",
        json={"text": "what is happening?", "case_id": case_id, "channel": "app"},
    )

    assert anonymous.status_code == 401, anonymous.text


def test_a_turn_with_no_case_still_answers_without_credentials(api):
    """The stateless path is unchanged: nothing to attach, nothing to leak.

    This is what keeps the contract change additive. The chat page asks
    questions before a case exists, and that still works with no session.
    """
    answered = api.post("/v1/conversation/turn", json={"text": "why is my data slow?"})

    assert answered.status_code == 200, answered.text
    turn = answered.json()["turn"]
    assert turn["reply"]
    # No conversation state without a case, and the field is simply absent
    # rather than present and empty.
    assert "state" not in turn


# -- the response stayed a superset --------------------------------------- #


def test_the_stateful_turn_keeps_every_field_the_stateless_one_had(api, me):
    """The route is additive, so no existing consumer loses a field.

    Checked against the stateless shape rather than a hand-written list, so
    this keeps holding if the stateless shape gains a field.
    """
    stateless = api.post("/v1/conversation/turn", json={"text": "charged LKR 49 twice"})
    assert stateless.status_code == 200, stateless.text

    case_id = _open_case(api, me, DILANI)
    stateful = _turn(api, me, case_id, "charged LKR 49 twice", channel="app")

    missing = sorted(set(stateless.json()["turn"]) - set(stateful))
    assert missing == [], f"the stateful turn dropped {missing}"
    for added in ("state", "verifier", "refused"):
        assert added in stateful


# -- K03 acceptance 2: no source means a person --------------------------- #


def test_a_question_with_no_source_says_so_and_offers_a_person(api, me):
    """K03 (#33) acceptance 2, black box over `/v1`.

    Plan 22 section 7: no source means "I do not know" plus a person. The
    failure this guards against is not a crash, it is the assistant answering
    anyway, which is the whole thing the knowledge module exists to prevent
    (I2: missing evidence goes to a person, never a guess).

    Two assertions, and both are needed. The reply has to *say* it does not
    know, and the turn has to actually route to a person: a reply that says
    "let me get someone" while the handoff flag is false has told the customer
    something untrue and left them waiting.
    """
    case_id = _open_case(api, me, DILANI)

    turn = _turn(api, me, case_id, "What is the capital of France?", channel="app")

    assert turn["citations"] == [], "an ungrounded answer cited something"
    assert turn["handoff"]["handoff"] is True, "no source, so a person is owed"
    assert turn["handoff"]["reason"] == "no_published_source"
    assert "do not have a published source" in turn["reply"]


def test_a_question_the_corpus_answers_is_answered_with_a_citation(api, me):
    """The other half, without which the test above passes by refusing always.

    A module that offered a person for everything would satisfy acceptance 2
    and be useless.
    """
    case_id = _open_case(api, me, DILANI)

    turn = _turn(api, me, case_id, "What is the fair use policy?", channel="app")

    assert turn["citations"], "the corpus holds a fair-use article and it was not cited"
    assert all("@" in citation for citation in turn["citations"])
    assert turn["handoff"]["handoff"] is False
    assert "do not have a published source" not in turn["reply"]


def test_an_ungrounded_answer_is_never_sent_with_a_citation_attached(api, me):
    """The property that matters across both halves.

    Either the reply is grounded and cites a version a reader can look up, or
    it is a refusal and cites nothing. There is no third state, and a reply
    carrying a citation it did not earn is the one outcome that would make the
    whole trust story false.
    """
    case_id = _open_case(api, me, DILANI)

    for question in (
        "What is the capital of France?",
        "What is the fair use policy?",
        "How do I convert my SIM to an eSIM?",
    ):
        turn = _turn(api, me, case_id, question, channel="app")
        refused = "do not have a published source" in turn["reply"]
        assert refused != bool(turn["citations"]), (
            f"{question!r}: refused={refused} citations={turn['citations']}"
        )
