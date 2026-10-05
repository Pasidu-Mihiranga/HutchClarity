"""The offer-verification routes, black box over `/v1` (OFFER01).

What these cover that the unit tests cannot: the permission split, the subject
binding, and the fact that recording an offer immediately changes what a
customer is told. The verdict logic itself is pinned in
`tests/unit/test_offers.py`.

**The permission split is the point of most of this file.** Recording an offer
decides what the fraud check will vouch for, so `offer:manage` is security
admin's alone and is tested against every other staff role and against a
customer. A customer may check their own messages (`offer:verify`) and nothing
else.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from clarity.app.container import Clarity
from clarity.integration.drivers.mock.world import build_demo_world
from clarity.interfaces.http.main import create_app

from .conftest import bearer, customer_token, staff_token

GENUINE = (
    "Dear Customer, your Anytime 10GB pack now carries 10GB extra data free "
    "for 30 days. Activate from the Hutch app under Packages. No charge "
    "applies. Offer code DD10."
)
SCAM = (
    "CONGRATULATIONS! You have WON 50GB free data from Hutch. Claim now at "
    "http://hutch-rewards.xyz/claim before it expires today. Send your OTP to "
    "confirm."
)

#: The synthetic subscriber the seeded offers belong to (app/offer_seed.py).
SANDUNI = "+94785720767"

#: A subscriber with no offers recorded against them.
DILANI = "+94781234567"


@pytest.fixture
def api() -> TestClient:
    return TestClient(create_app(Clarity(world=build_demo_world())))


@pytest.fixture
def sanduni(api: TestClient) -> dict[str, str]:
    return bearer(customer_token(api, SANDUNI))


@pytest.fixture
def security(api: TestClient) -> dict[str, str]:
    return bearer(staff_token(api, "sec:dilani", ["security_admin"], step_up=True))


# ------------------------------------------------------------- the customer


def test_a_genuine_message_is_on_record(api: TestClient, sanduni: dict[str, str]) -> None:
    response = api.post("/v1/offers/verify", headers=sanduni, json={"message": GENUINE})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["verdict"] == "ON_RECORD"
    assert body["matched"]["code_matched"] is True
    assert body["matched"]["still_valid"] is True
    # I16: the records behind the answer are simulated, and the payload says so
    # wherever the answer is shown.
    assert body["simulated"] is True
    assert body["matched"]["source"] == "hutch-sim"


def test_a_scam_message_is_not_on_record_and_reports_its_signals(
    api: TestClient, sanduni: dict[str, str]
) -> None:
    body = api.post("/v1/offers/verify", headers=sanduni, json={"message": SCAM}).json()
    assert body["verdict"] == "NOT_ON_RECORD"
    codes = {signal["code"] for signal in body["signals"]}
    assert {"NON_HUTCH_LINK", "ASKS_FOR_CODE"} <= codes
    # No offer is named on an outright miss: pointing at one nobody asked
    # about is noise a worried customer does not need.
    assert body["matched"] is None


def test_the_answer_is_never_a_scam_flag(api: TestClient, sanduni: dict[str, str]) -> None:
    """The verdict vocabulary is fixed and does not include one.

    Pinned because it is a product decision somebody would reasonably try to
    "improve" into a boolean. The reason it is not one is in the module
    docstring: a scam verdict is an inference past what was checked, and the
    pasted text is the one thing an attacker controls (I2).
    """
    body = api.post("/v1/offers/verify", headers=sanduni, json={"message": SCAM}).json()
    assert body["verdict"] in {"ON_RECORD", "NOT_ON_RECORD", "NEEDS_A_PERSON"}
    assert "scam" not in str(body).lower()
    assert "fraud" not in str(body).lower()


def test_a_check_is_bound_to_the_callers_own_number(api: TestClient) -> None:
    """Dilani has no offers, so the same genuine message does not match for her.

    The message is identical and the answer differs, because the records are
    per subscriber. A design that searched every subscriber's offers would tell
    Dilani that a message sent to Sanduni was real.
    """
    headers = bearer(customer_token(api, DILANI))
    body = api.post("/v1/offers/verify", headers=headers, json={"message": GENUINE}).json()
    assert body["verdict"] == "NOT_ON_RECORD"
    assert body["offers_on_record"] == 0


def test_an_empty_message_is_refused_rather_than_answered(
    api: TestClient, sanduni: dict[str, str]
) -> None:
    """What must not happen is a verdict about a message nobody sent."""
    response = api.post("/v1/offers/verify", headers=sanduni, json={"message": "   "})
    assert response.status_code == 422


def test_an_anonymous_caller_cannot_check(api: TestClient) -> None:
    assert api.post("/v1/offers/verify", json={"message": GENUINE}).status_code == 401


# ---------------------------------------------------------------- the records


def test_recording_an_offer_changes_what_a_customer_is_told(
    api: TestClient, sanduni: dict[str, str], security: dict[str, str]
) -> None:
    """The loop that makes the feature work: record, then a check matches."""
    message = (
        "Hutch weekend bonus: 2GB of social data has been added to your number "
        "for this weekend only. No activation needed. Code SOC2."
    )

    before = api.post("/v1/offers/verify", headers=sanduni, json={"message": message})
    assert before.json()["verdict"] != "ON_RECORD"

    created = api.post(
        "/v1/admin/offers",
        headers=security,
        json={
            "msisdn": "0785720767",
            "title": "Weekend social bonus",
            "body": message,
            "offer_code": "SOC2",
        },
    )
    assert created.status_code == 201, created.text
    # The raw number never comes back, only the mask.
    assert "785720767" not in created.json()["msisdn_masked"]

    after = api.post("/v1/offers/verify", headers=sanduni, json={"message": message})
    assert after.json()["verdict"] == "ON_RECORD"


def test_the_record_list_never_carries_a_raw_number_or_a_pseudonym(
    api: TestClient, security: dict[str, str]
) -> None:
    response = api.get("/v1/admin/offers", headers=security)
    assert response.status_code == 200
    rows = response.json()
    assert rows, "the synthetic world seeds offers for the journey"
    for row in rows:
        # Neither the MSISDN nor the HMAC pseudonym leaves the module: a staff
        # screen needs a legible label, not a subject identifier.
        assert "subscriber_ref" not in row
        assert "785720767" not in row["msisdn_masked"]


def test_an_unknown_number_is_refused(api: TestClient, security: dict[str, str]) -> None:
    response = api.post(
        "/v1/admin/offers",
        headers=security,
        json={"msisdn": "0770000000", "title": "x", "body": "some offer text"},
    )
    assert response.status_code == 404


def test_an_offer_with_no_text_is_refused(api: TestClient, security: dict[str, str]) -> None:
    """An offer with no body matches nothing and would sit there looking like coverage."""
    response = api.post(
        "/v1/admin/offers",
        headers=security,
        json={"msisdn": "0785720767", "title": "Empty", "body": "   "},
    )
    assert response.status_code == 422


# ------------------------------------------------------------ who may do what


@pytest.mark.parametrize(
    ("user_ref", "roles"),
    [
        ("agent:nadeesha", ["agent"]),
        ("sup:ruwan", ["supervisor"]),
        ("fin:anusha", ["finance"]),
        ("comp:ravi", ["compliance"]),
        ("cxe:tharindu", ["cx_engineer"]),
        ("plat:sam", ["platform_admin"]),
    ],
)
def test_no_other_staff_role_may_record_or_read_offers(
    api: TestClient, user_ref: str, roles: list[str]
) -> None:
    """`offer:manage` is security admin's alone.

    Recording an offer is the authority the fraud check rests on: it makes a
    matching message read as genuine. Spreading it would mean several roles
    could decide what Clarity vouches for, which is the same shape of power as
    a kill switch.
    """
    headers = bearer(staff_token(api, user_ref, roles, step_up=True))
    recorded = api.post(
        "/v1/admin/offers",
        headers=headers,
        json={"msisdn": "0785720767", "title": "x", "body": "some offer text"},
    )
    assert recorded.status_code == 403
    assert api.get("/v1/admin/offers", headers=headers).status_code == 403


def test_a_customer_may_not_record_an_offer(
    api: TestClient, sanduni: dict[str, str]
) -> None:
    response = api.post(
        "/v1/admin/offers",
        headers=sanduni,
        json={"msisdn": "0785720767", "title": "x", "body": "some offer text"},
    )
    assert response.status_code == 403


def test_security_admin_has_no_me_to_check_against(
    api: TestClient, security: dict[str, str]
) -> None:
    """A staff token carries no subscriber, so there is nothing to compare to."""
    response = api.post("/v1/offers/verify", headers=security, json={"message": GENUINE})
    assert response.status_code == 403
