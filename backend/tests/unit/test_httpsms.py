"""httpSMS OTP delivery contract without a live SMS call."""

from __future__ import annotations

import httpx
import pytest

from clarity.modules.iam.public import HttpSmsDelivery, HttpSmsDeliveryFailed


def test_httpsms_sends_the_otp_with_the_registered_phone() -> None:
    def accepted(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://sms.example/v1/messages/send"
        assert request.headers["x-api-key"] == "secret-key"
        assert request.read() == (
            b'{"from":"+94780000000","to":"+94781234567",'
            b'"content":"Clarity sign-in number 123456. Valid for 5 minutes. Never share it."}'
        )
        return httpx.Response(200, json={"status": "success"})

    delivery = HttpSmsDelivery(
        api_key="secret-key",
        sender="+94780000000",
        base_url="https://sms.example/v1",
        client=httpx.Client(transport=httpx.MockTransport(accepted)),
    )

    delivery.send("+94781234567", "123456")


def test_httpsms_failure_does_not_expose_the_provider_response() -> None:
    delivery = HttpSmsDelivery(
        api_key="secret-key",
        sender="+94780000000",
        base_url="https://sms.example/v1",
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(401, text="provider-secret-detail")
            )
        ),
    )

    with pytest.raises(HttpSmsDeliveryFailed, match="delivery was not accepted") as refused:
        delivery.send("+94781234567", "123456")

    assert "provider-secret-detail" not in str(refused.value)
