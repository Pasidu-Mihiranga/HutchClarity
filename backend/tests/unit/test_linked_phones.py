"""Linked phones: who gets a real SMS, and as whom a real phone signs in.

The synthetic customers' numbers (078...) belong to real strangers. With
httpSMS configured, the OTP route used to text whatever number was typed, so a
sign-in as a synthetic customer texted a stranger, anyone could make the server
send SMS to any number, and a tester's own phone (not a synthetic customer)
received a code that could never verify. Now only linked phones get SMS.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from clarity.app.container import Clarity
from clarity.app.settings import Settings, SettingsInvalid
from clarity.interfaces.http.main import create_app
from clarity.modules.iam.public import HttpSmsDelivery, RoutedOtpDelivery, SimulatedInbox

TESTER = "+94771112233"  # a real phone in the test, linked to Dilani
DILANI = "+94781234567"
NIMAL = "+94782223333"  # synthetic, not linked
STRANGER = "+94779998877"  # nobody


class RecordingSms:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def send(self, msisdn: str, code: str) -> None:
        self.sent.append((msisdn, code))


def _router(sms: RecordingSms | None) -> RoutedOtpDelivery:
    return RoutedOtpDelivery(
        inbox=SimulatedInbox(),
        sms=sms,
        sms_numbers=frozenset({TESTER}),
        known=lambda msisdn: msisdn in {TESTER, DILANI, NIMAL},
    )


def test_only_a_linked_phone_is_texted() -> None:
    sms = RecordingSms()
    router = _router(sms)

    router.send(TESTER, "111111")
    router.send(NIMAL, "222222")
    router.send(STRANGER, "333333")

    assert sms.sent == [(TESTER, "111111")]
    assert router.inbox.latest_for(NIMAL)["code"] == "222222"
    assert router.inbox.latest_for(STRANGER) is None
    assert router.channel_for(STRANGER) == "none"


def test_without_an_sms_driver_a_linked_phone_uses_the_inbox() -> None:
    router = _router(None)
    router.send(TESTER, "444444")
    assert router.channel_for(TESTER) == "inbox"
    assert router.inbox.latest_for(TESTER)["code"] == "444444"


@pytest.fixture()
def texted(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(
        HttpSmsDelivery, "send", lambda self, msisdn, code: sent.append((msisdn, code))
    )
    return sent


def _client() -> TestClient:
    settings = Settings(
        HTTPSMS_API_KEY="uk_test",
        HTTPSMS_SENDER="+94700000000",
        CLARITY_LINKED_PHONES=f"{TESTER}={DILANI}",
        _env_file=None,
    )
    return TestClient(create_app(Clarity(settings=settings)))


def test_a_linked_phone_gets_a_real_sms_and_signs_in_as_its_customer(texted) -> None:
    client = _client()

    started = client.post("/v1/auth/otp/request", json={"msisdn": "0771112233"})
    assert started.status_code == 200
    assert started.json()["detail"] == "A sign-in code was sent by SMS."
    assert [to for to, _ in texted] == [TESTER]

    code = texted[0][1]
    session = client.post(
        "/v1/auth/otp/verify",
        json={"challenge_id": started.json()["challenge_id"], "code": code},
    )
    assert session.status_code == 200
    me = client.get("/v1/me/app", headers={"Authorization": f"Bearer {session.json()['token']}"})
    assert me.json()["name"] == "Dilani Perera"


def test_a_synthetic_number_is_never_texted(texted) -> None:
    client = _client()
    started = client.post("/v1/auth/otp/request", json={"msisdn": NIMAL})

    assert started.status_code == 200
    assert texted == []
    assert client.get("/v1/demo/inbox", params={"msisdn": NIMAL}).status_code == 200


def test_an_unknown_number_is_not_texted_and_looks_like_any_other(texted) -> None:
    client = _client()
    unknown = client.post("/v1/auth/otp/request", json={"msisdn": STRANGER}).json()
    synthetic = client.post("/v1/auth/otp/request", json={"msisdn": NIMAL}).json()

    assert texted == []
    assert unknown["detail"] == synthetic["detail"]
    assert unknown["simulated"] == synthetic["simulated"]


def test_a_link_to_a_number_that_is_no_customer_stops_startup() -> None:
    settings = Settings(CLARITY_LINKED_PHONES=f"{TESTER}={STRANGER}", _env_file=None)
    with pytest.raises(ValueError, match="no synthetic customer"):
        Clarity(settings=settings)


def test_a_malformed_link_is_a_settings_error() -> None:
    with pytest.raises(SettingsInvalid, match="CLARITY_LINKED_PHONES"):
        Settings(CLARITY_LINKED_PHONES="0771112233", _env_file=None)
