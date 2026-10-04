"""Every OTP delivery driver keeps the same promises (B6, I20).

`OtpDelivery` had one implementation for the whole life of the project, so
nothing had ever said what a second one must do. These are the properties the
sign-in path relies on, asserted against both drivers:

1. The code reaches the customer, whole.
2. The code is never logged, raised, or returned.
3. A failure says nothing about whether the number exists.

The third is the one that is easy to lose. `POST /v1/auth/otp/request` answers
identically for a subscriber and a stranger, which is the fix that stopped the
route being a subscriber directory. A delivery driver that reported "unknown
destination" would reinstate the oracle one layer down, where nobody would
think to look for it.
"""

from __future__ import annotations

import logging

import httpx
import pytest

from clarity.integration.drivers.sms import SmsOtpDelivery, SmsSettings, SmsUndeliverable
from clarity.modules.iam.public import OtpDelivery, SimulatedInbox

CODE = "483920"
NUMBER = "+94781234567"


def _sms(handler) -> SmsOtpDelivery:
    return SmsOtpDelivery(
        SmsSettings(url="http://sms.invalid/send", token="development-only"),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def _accepting() -> SmsOtpDelivery:
    return _sms(lambda request: httpx.Response(200, json={"status": "queued"}))


@pytest.fixture(params=["simulated-inbox", "sms-gateway"])
def delivery(request: pytest.FixtureRequest) -> OtpDelivery:
    if request.param == "sms-gateway":
        return _accepting()
    return SimulatedInbox()


def test_every_driver_satisfies_the_port(delivery: OtpDelivery) -> None:
    assert isinstance(delivery, OtpDelivery)


def test_sending_a_code_returns_nothing(delivery: OtpDelivery) -> None:
    """The code travels through the port and comes back by no other route.

    A driver that returned the message, or a receipt containing it, would give
    `OtpService` something to leak; `request` is careful never to return the
    code and this is the other half of that.
    """
    assert delivery.send(NUMBER, CODE) is None


def test_the_code_never_reaches_the_log(
    delivery: OtpDelivery, caplog: pytest.LogCaptureFixture
) -> None:
    """Support tooling reads logs. A code in one is a code in the open."""
    with caplog.at_level(logging.DEBUG):
        delivery.send(NUMBER, CODE)

    assert CODE not in caplog.text


def test_the_number_is_not_written_in_the_clear(
    delivery: OtpDelivery, caplog: pytest.LogCaptureFixture
) -> None:
    """I13: an MSISDN is masked wherever it is recorded."""
    with caplog.at_level(logging.DEBUG):
        delivery.send(NUMBER, CODE)

    assert NUMBER not in caplog.text


# --------------------------------------------------------------------------- #
# Failures, which only the real driver can have
# --------------------------------------------------------------------------- #


def test_a_refused_message_raises_without_naming_the_destination() -> None:
    failing = _sms(lambda request: httpx.Response(400, json={"error": "unknown destination"}))

    with pytest.raises(SmsUndeliverable) as refused:
        failing.send(NUMBER, CODE)

    assert NUMBER not in str(refused.value)
    assert CODE not in str(refused.value)
    assert "unknown" not in str(refused.value).lower()


def test_a_failure_says_nothing_about_whether_the_number_exists() -> None:
    """Otherwise the enumeration oracle comes back one layer down."""
    unknown = _sms(lambda request: httpx.Response(404, json={"error": "no such subscriber"}))
    broken = _sms(lambda request: httpx.Response(503, json={"error": "gateway down"}))

    with pytest.raises(SmsUndeliverable) as first:
        unknown.send(NUMBER, CODE)
    with pytest.raises(SmsUndeliverable) as second:
        broken.send(NUMBER, CODE)

    assert str(first.value) == str(second.value)


def test_a_failed_send_does_not_log_the_code(caplog: pytest.LogCaptureFixture) -> None:
    """The failure path is the one that tends to log the request body."""
    failing = _sms(lambda request: httpx.Response(500))

    with caplog.at_level(logging.DEBUG), pytest.raises(SmsUndeliverable):
        failing.send(NUMBER, CODE)

    assert CODE not in caplog.text
    assert NUMBER not in caplog.text


def test_the_message_carries_the_code_and_no_link() -> None:
    """A sign-in message with a link teaches customers to tap links in messages
    about their account, which is the mechanism of the attack this product
    exists to explain."""
    sent: dict[str, object] = {}

    def capture(request: httpx.Request) -> httpx.Response:
        import json

        sent.update(json.loads(request.content))
        return httpx.Response(200)

    _sms(capture).send(NUMBER, CODE)

    assert CODE in str(sent["text"])
    assert "http" not in str(sent["text"]).lower()


def test_the_simulated_driver_is_labelled() -> None:
    """I16: anything reading the inbox is reading a mock and must be told."""
    inbox = SimulatedInbox()
    inbox.send(NUMBER, CODE)

    assert inbox.latest_for(NUMBER)["simulated"] == "yes"
