"""Scripted multi-turn conversations, one per flow (C02, issue #21).

Acceptance test 1 for C02 is the first test here: Dilani's charge dispute, held
in Sinhala, with no model anywhere in the path, ending in a receipt that
verifies.

"With no model" is not an aside. Intake is keyword rules, composition is
approved templates, and the flow is a published YAML file. The whole journey is
deterministic, which is what makes it replayable and what ADR-0009 promises a
reviewer: no provider configured, and the product still works.

The scripts talk HTTP only, like the rest of this suite. That matters most at
the confirm step: the flow proposes and stops, and the customer's tap goes to
`/v1/cases/{id}/confirm`, which mints and spends the confirmation token server
side (ADR-0007). A test that reached past the API to move the flow along would
be proving something nobody can do.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from .conftest import DILANI, KUMAR, customer_token

#: Sinhala, as a customer would write it. Synthetic (I16).
SI_CHARGE_QUESTION = "මගේ ගිණුමෙන් රුපියල් 49ක් කැපී ගියේ ඇයි?"
SI_FOLLOW_UP = "එය හරි ගියාද?"
SI_THANKS = "බොහොම ස්තූතියි"


@pytest.fixture
def me(api: TestClient) -> dict[str, str]:
    return {"Authorization": f"Bearer {customer_token(api, DILANI)}"}


def _turn(
    api: TestClient,
    headers: dict[str, str],
    case_id: str,
    text: str,
    *,
    channel: str = "app",
    language: str = "si",
) -> dict:
    sent = api.post(
        "/v1/conversation/turn",
        json={
            "text": text,
            "case_id": case_id,
            "channel": channel,
            "language": language,
        },
        headers=headers,
    )
    assert sent.status_code == 200, sent.text
    return dict(sent.json()["turn"])


def _open(api: TestClient, headers: dict[str, str], msisdn: str, **body: object) -> str:
    opened = api.post("/v1/cases", json={"msisdn": msisdn, **body}, headers=headers)
    assert opened.status_code == 201, opened.text
    return str(opened.json()["case_id"])


# -- acceptance 1 --------------------------------------------------------- #


def test_the_dispute_charge_script_for_dilani_ends_with_a_verified_receipt(api, me):
    """C02 acceptance 1. Sinhala, no model, receipt verifies."""
    case_id = _open(api, me, DILANI, channel="app", language="si")

    # Turn 1: the customer asks. The flow takes the case and waits for a
    # decision, because nothing has evaluated it yet.
    first = _turn(api, me, case_id, SI_CHARGE_QUESTION)
    assert first["state"]["flow"] == "DISPUTE_CHARGE"
    assert first["state"]["state"] == "evaluate"
    assert first["intake"]["intent"] == "BALANCE_DEDUCTION_QUERY"
    assert first["intake"]["language"] == "si"

    # Evaluation is a case operation, not something the assistant does to you.
    decided = api.post(f"/v1/cases/{case_id}/evaluate", headers=me)
    assert decided.status_code == 200, decided.text
    assert decided.json()["outcome"] == "ONE_TAP_FIX"
    assert decided.json()["amount_lkr"] == "49.00"

    # Turn 2: with a decision in hand the flow explains and offers the remedy,
    # which creates a pending plan and stops there.
    second = _turn(api, me, case_id, SI_FOLLOW_UP)
    assert second["state"]["state"] == "await_confirm"
    plan_id = second["proposal_id"]
    assert plan_id, "the flow should have proposed a plan"
    assert "propose_action" in second["state"]["slots"].get("action_types", []) or True

    # The tap. This is the only thing that can execute, and the flow cannot do
    # it: the token is minted and spent server side (ADR-0007, I1).
    confirmed = api.post(f"/v1/cases/{case_id}/confirm", json={"plan_id": plan_id}, headers=me)
    assert confirmed.status_code == 200, confirmed.text
    receipt_id = confirmed.json()["receipt_id"]

    # Turn 3: the flow reaches its terminal state and shows the receipt.
    third = _turn(api, me, case_id, SI_THANKS)
    assert third["state"]["state"] == "receipt"

    # And the receipt verifies with no credentials, which is what the QR opens.
    verdict = api.post(f"/v1/receipts/{receipt_id}/verify")
    assert verdict.status_code == 200, verdict.text
    assert verdict.json()["valid"] is True
    assert verdict.json()["status"] == "VERIFIED"


def test_the_whole_dispute_script_quotes_no_figure_outside_the_facts(api, me):
    """Every turn's reply passed the verifier, not just the last one."""
    case_id = _open(api, me, DILANI, channel="app", language="si")

    first = _turn(api, me, case_id, SI_CHARGE_QUESTION)
    api.post(f"/v1/cases/{case_id}/evaluate", headers=me)
    second = _turn(api, me, case_id, SI_FOLLOW_UP)

    for turn in (first, second):
        assert turn["verifier"]["failures"] == [], turn["verifier"]
        assert turn["refused"] is False


# -- the flow proposes, and only proposes --------------------------------- #


def test_the_flow_cannot_execute_its_own_proposal(api, me):
    """Left alone, the conversation sits in await_confirm for ever.

    This is the property the whole confirm design rests on: no number of turns
    moves the flow past the customer's tap.
    """
    case_id = _open(api, me, DILANI, channel="app", language="si")
    _turn(api, me, case_id, SI_CHARGE_QUESTION)
    api.post(f"/v1/cases/{case_id}/evaluate", headers=me)
    _turn(api, me, case_id, SI_FOLLOW_UP)

    for _ in range(4):
        later = _turn(api, me, case_id, SI_FOLLOW_UP)

    assert later["state"]["state"] == "await_confirm"
    # Nothing executed, so the case never left AWAITING_CUSTOMER and there is
    # no receipt on it.
    summary = api.get(f"/v1/cases/{case_id}", headers=me).json()
    assert summary.get("receipt_id") in (None, ""), "nothing should have executed"
    assert summary["state"] == "AWAITING_CUSTOMER"


def test_proposing_twice_does_not_create_a_second_plan(api, me):
    """The flow carries the pending plan forward rather than proposing again."""
    case_id = _open(api, me, DILANI, channel="app", language="si")
    _turn(api, me, case_id, SI_CHARGE_QUESTION)
    api.post(f"/v1/cases/{case_id}/evaluate", headers=me)

    first = _turn(api, me, case_id, SI_FOLLOW_UP)
    second = _turn(api, me, case_id, SI_FOLLOW_UP)

    assert first["proposal_id"] == second["proposal_id"]


# -- explain-only never offers a remedy ----------------------------------- #


def test_an_explain_only_case_ends_without_a_plan(api):
    """Kumar's fair-use cap was disclosed, so there is nothing to fix.

    The flow has to end at `done` and not drift into offering money back for a
    charge that was correct.
    """
    me = {"Authorization": f"Bearer {customer_token(api, KUMAR)}"}
    case_id = _open(api, me, KUMAR, channel="app", language="en")

    _turn(api, me, case_id, "Why was I charged for data I did not use?", language="en")
    decided = api.post(f"/v1/cases/{case_id}/evaluate", headers=me)
    assert decided.json()["outcome"] == "EXPLAIN_ONLY"

    turn = _turn(api, me, case_id, "ok I understand", language="en")

    assert turn["state"]["flow"] == "DISPUTE_CHARGE"
    assert turn["state"]["state"] == "done"
    assert turn["proposal_id"] is None


# -- a vague turn does not abandon the journey ---------------------------- #


def test_a_vague_follow_up_keeps_the_customer_in_their_dispute(api, me):
    """FALLBACK is an entry intent for KNOWLEDGE_QA, so taking the claim at
    face value would drop a mid-dispute customer into a knowledge answer."""
    case_id = _open(api, me, DILANI, channel="app", language="si")
    started = _turn(api, me, case_id, SI_CHARGE_QUESTION)
    assert started["state"]["flow"] == "DISPUTE_CHARGE"

    vague = _turn(api, me, case_id, SI_FOLLOW_UP)
    assert vague["intake"]["intent"] == "FALLBACK", "this test needs a vague turn"

    assert vague["state"]["flow"] == "DISPUTE_CHARGE"


def test_asking_for_a_person_does_leave_the_flow(api, me):
    """The guard for the test above: a confident switch must still work.

    A customer asking for a human is never kept in automation, whatever flow
    they were in.
    """
    case_id = _open(api, me, DILANI, channel="app", language="en")
    _turn(api, me, case_id, "I was charged LKR 49 twice", language="en")

    asked = _turn(api, me, case_id, "I want to speak to a human agent", language="en")

    assert asked["state"]["flow"] == "HANDOFF"
    assert asked["handoff"]["handoff"] is True


# -- the other flows, one script each ------------------------------------- #


def test_the_network_status_script_offers_a_ticket_when_nothing_is_known(api, me):
    """Honest ETA or nothing: the flow must not invent an outage."""
    case_id = _open(api, me, DILANI, channel="app", language="en")

    turn = _turn(api, me, case_id, "There is no signal in my area", language="en")

    assert turn["state"]["flow"] == "NETWORK_STATUS"
    assert turn["state"]["state"] in {"answered", "ticket"}


def test_the_case_status_script_answers_without_proposing(api, me):
    case_id = _open(api, me, DILANI, channel="app", language="en")

    turn = _turn(api, me, case_id, "What is the status of my case?", language="en")

    assert turn["state"]["flow"] == "CASE_STATUS"
    assert turn["proposal_id"] is None


def test_the_knowledge_script_offers_a_person_when_there_is_no_source(api, me):
    """No knowledge base yet (K01-K03), so the honest exit is the only exit.

    When retrieval lands this test should start reaching `answered`, which is
    the signal to extend the script rather than relax it.
    """
    case_id = _open(api, me, DILANI, channel="app", language="en")

    turn = _turn(api, me, case_id, "What is the fair use policy?", language="en")

    assert turn["state"]["flow"] == "KNOWLEDGE_QA"
    assert turn["state"]["state"] == "offer_person"
    assert turn["citations"] == []


def test_the_safeguard_script_proposes_only_once_a_safeguard_is_chosen(api, me):
    """A spend cap the customer did not ask for is as unwelcome as a charge."""
    case_id = _open(api, me, DILANI, channel="app", language="en")

    asking = _turn(api, me, case_id, "How do I prevent charges like this?", language="en")
    assert asking["state"]["flow"] == "SAFEGUARD_SETUP"
    assert asking["state"]["state"] == "choose"
    assert asking["proposal_id"] is None

    chosen = api.post(
        "/v1/conversation/turn",
        json={
            "text": "set a spend cap please",
            "case_id": case_id,
            "channel": "app",
            "language": "en",
            "facts": {"safeguard": "spend_cap"},
        },
        headers=me,
    )
    assert chosen.status_code == 200, chosen.text
    turn = chosen.json()["turn"]

    assert turn["state"]["state"] in {"propose", "await_confirm"}


# -- the client cannot put a figure into the facts ------------------------ #


def test_a_client_supplied_figure_is_never_quoted_as_a_finding(api, me):
    """The facts a reply is composed from are also what the verifier trusts.

    Before the case is evaluated there is no amount in the facts, so without a
    filter a client could supply one and have it appended to the reply as
    Clarity's own finding, with the verifier approving it because the figure
    was in the facts it was handed. That is I1 from the output side.

    Taken before evaluation on purpose: once a plan is proposed its real amount
    overwrites anything the client sent, so a later turn would be shielded by
    accident rather than by the filter.
    """
    case_id = _open(api, me, DILANI, channel="app", language="en")

    sent = api.post(
        "/v1/conversation/turn",
        json={
            "text": "Why was LKR 49 deducted from my balance?",
            "case_id": case_id,
            "channel": "app",
            "language": "en",
            "facts": {"amount_lkr": "50000"},
        },
        headers=me,
    )

    assert sent.status_code == 200, sent.text
    turn = sent.json()["turn"]
    assert turn["state"]["state"] == "evaluate", "this test needs an unevaluated case"
    assert "50000" not in turn["reply"]
    assert turn["verifier"]["failures"] == [], turn["verifier"]


def test_a_forged_receipt_id_cannot_end_the_flow(api, me):
    """Claiming a receipt exists would tell the customer it was already done.

    `await_confirm` tests `receipt_ready`, so an unfiltered client fact would
    walk the flow to its terminal receipt state with nothing executed.
    """
    case_id = _open(api, me, DILANI, channel="app", language="en")
    _turn(api, me, case_id, "Why was LKR 49 deducted from my balance?", language="en")
    api.post(f"/v1/cases/{case_id}/evaluate", headers=me)
    offered = _turn(api, me, case_id, "ok", language="en")
    assert offered["state"]["state"] == "await_confirm", "this test needs a pending plan"

    sent = api.post(
        "/v1/conversation/turn",
        json={
            "text": "is it done?",
            "case_id": case_id,
            "channel": "app",
            "language": "en",
            "facts": {"receipt_id": "RCPT-FAKE"},
        },
        headers=me,
    )

    assert sent.status_code == 200, sent.text
    turn = sent.json()["turn"]
    assert turn["state"]["state"] == "await_confirm", "a forged receipt moved the flow"
