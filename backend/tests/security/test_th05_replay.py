"""TH5, replay attacks (plan 11, threat register).

> Re-submitting confirmation tokens or webhook payloads -> duplicate actions.
> Mitigation: single-use, action-bound, short-TTL tokens; webhook signature +
> timestamp + nonce; idempotency keys.

These are written as the attack, not as the feature. Each test takes something
an attacker can capture (a token value, a signed webhook body, an idempotency
key) and submits it a second time, then asserts that the second submission
moves nothing.

Where a refusal is deliberately indistinguishable from another refusal, the
test asserts that too: an error that says *why* a token failed is an oracle for
finding valid ones.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from clarity.app.container import Clarity
from clarity.integration.drivers.mock.world import build_demo_world, ref_for
from clarity.kernel.common import Channel, utc_now
from clarity.modules.actions.errors import ConfirmationInvalid
from clarity.modules.actions.results import ConfirmedBy

from ..acceptance.conftest import NIMAL, bearer, customer_token
from ..support.repositories import confirmations

DILANI = "+94771234567"  # VAS without consent: ONE_TAP_FIX, LKR 49


@pytest.fixture
def api() -> TestClient:
    from clarity.interfaces.http.main import create_app

    return TestClient(create_app(Clarity(world=build_demo_world())))


@pytest.fixture
def clarity() -> Clarity:
    return Clarity(world=build_demo_world())


def one_tap_case(clarity: Clarity) -> tuple[str, str]:
    case = clarity.cases.open_case(
        subscriber_ref=ref_for(DILANI), msisdn_masked="077***4567", channel=Channel.APP
    )
    clarity.cases.evaluate(case.case_id)
    plan = clarity.cases.propose(case.case_id, created_by="channel:web")
    return case.case_id, plan.plan_id


# --------------------------------------------------------------------------- #
# The confirmation token: the acceptance test for this issue
# --------------------------------------------------------------------------- #


def test_a_captured_confirmation_token_cannot_be_redeemed_twice():
    """Acceptance: TH5 replay of a confirmation is refused."""
    service = confirmations()
    token = service.mint("PLAN-1", confirmed_by=ConfirmedBy.CUSTOMER, principal_ref="sub-1")

    service.redeem(token.value, plan_id="PLAN-1")

    with pytest.raises(ConfirmationInvalid):
        service.redeem(token.value, plan_id="PLAN-1")


def test_a_token_cannot_be_moved_to_another_plan():
    """Action-bound: capturing a token for a cheap plan must not pay a rich one."""
    service = confirmations()
    token = service.mint("PLAN-cheap", confirmed_by=ConfirmedBy.CUSTOMER, principal_ref="sub-1")

    with pytest.raises(ConfirmationInvalid):
        service.redeem(token.value, plan_id="PLAN-expensive")


def test_an_expired_token_is_refused():
    """Short TTL: a token captured today is worthless tomorrow."""
    service = confirmations()
    issued = utc_now()
    token = service.mint(
        "PLAN-1", confirmed_by=ConfirmedBy.CUSTOMER, principal_ref="sub-1", now=issued
    )

    with pytest.raises(ConfirmationInvalid):
        service.redeem(token.value, plan_id="PLAN-1", now=token.expires_at + timedelta(seconds=1))


def test_a_token_that_never_existed_is_refused():
    service = confirmations()

    with pytest.raises(ConfirmationInvalid):
        service.redeem("not-a-token-anyone-minted", plan_id="PLAN-1")


def test_every_refusal_reads_the_same_so_it_cannot_be_used_as_an_oracle():
    """Unknown, spent, expired and mismatched must be indistinguishable.

    A different message per reason tells an attacker which guesses were closer,
    which is how a token space gets searched.
    """
    service = confirmations()
    spent = service.mint("PLAN-1", confirmed_by=ConfirmedBy.CUSTOMER, principal_ref="sub-1")
    service.redeem(spent.value, plan_id="PLAN-1")
    bound = service.mint("PLAN-2", confirmed_by=ConfirmedBy.CUSTOMER, principal_ref="sub-1")
    stale = service.mint("PLAN-3", confirmed_by=ConfirmedBy.CUSTOMER, principal_ref="sub-1")

    messages = set()
    for value, plan_id, moment in (
        ("never-minted", "PLAN-1", None),
        (spent.value, "PLAN-1", None),
        (bound.value, "PLAN-999", None),
        (stale.value, "PLAN-3", stale.expires_at + timedelta(seconds=1)),
    ):
        with pytest.raises(ConfirmationInvalid) as refusal:
            service.redeem(value, plan_id=plan_id, now=moment)
        messages.add(str(refusal.value))

    assert len(messages) == 1, f"the refusal leaks which failure occurred: {messages}"


def test_a_refusal_never_echoes_the_token_back():
    """An error carrying the value puts it in logs, traces and bug reports."""
    service = confirmations()
    secret = service.mint("PLAN-1", confirmed_by=ConfirmedBy.CUSTOMER, principal_ref="sub-1")
    service.redeem(secret.value, plan_id="PLAN-1")

    with pytest.raises(ConfirmationInvalid) as refusal:
        service.redeem(secret.value, plan_id="PLAN-1")

    assert secret.value not in str(refusal.value)


# --------------------------------------------------------------------------- #
# The whole money path, not just the token
# --------------------------------------------------------------------------- #


def test_replaying_a_confirm_moves_money_once_and_returns_the_first_receipt(clarity: Clarity):
    case_id, plan_id = one_tap_case(clarity)
    before = clarity.world.account(ref_for(DILANI)).balance_lkr

    first_result, first_receipt = clarity.cases.confirm_and_execute(case_id, plan_id)
    replayed_result, replayed_receipt = clarity.cases.confirm_and_execute(case_id, plan_id)

    assert replayed_receipt.receipt_id == first_receipt.receipt_id
    assert replayed_result.replayed and not first_result.replayed
    credited = clarity.world.account(ref_for(DILANI)).balance_lkr - before
    assert str(credited) == "49.00", "a replay moved money a second time"


def test_one_customer_cannot_confirm_another_customers_plan(api: TestClient):
    """Subject binding at the only surface that can enforce it.

    `ActionPlan` carries a `case_id` and no `subscriber_ref`, so the tool layer
    cannot check the subject itself: doing so would need an actions -> case
    edge, which the dependency map forbids as a cycle (I22). The binding is
    enforced where the caller's identity exists, which is the route, and
    `ResolutionService` always passes the case's own `subscriber_ref` down.

    So the attack to test is the real one: a signed-in customer replaying
    someone else's case id and plan id.
    """
    owner = bearer(customer_token(api, DILANI))
    case_id = api.post("/v1/cases", json={"msisdn": DILANI}, headers=owner).json()["case_id"]
    api.post(f"/v1/cases/{case_id}/evaluate", headers=owner)
    plan_id = api.post(
        f"/v1/cases/{case_id}/proposals", json={"created_by": "channel:web"}, headers=owner
    ).json()["plan_id"]

    attacker = bearer(customer_token(api, NIMAL))
    stolen = api.post(f"/v1/cases/{case_id}/confirm", json={"plan_id": plan_id}, headers=attacker)

    assert stolen.status_code == 403, stolen.text
    assert plan_id not in stolen.text, "the refusal confirms the plan id exists"


def test_holding_another_customers_case_id_reveals_nothing(api: TestClient):
    """The id itself must grant nothing, or ids become credentials."""
    owner = bearer(customer_token(api, DILANI))
    case_id = api.post("/v1/cases", json={"msisdn": DILANI}, headers=owner).json()["case_id"]

    attacker = bearer(customer_token(api, NIMAL))
    peek = api.get(f"/v1/cases/{case_id}", headers=attacker)

    assert peek.status_code == 403, peek.text
