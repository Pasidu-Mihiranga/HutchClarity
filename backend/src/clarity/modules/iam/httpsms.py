"""httpSMS delivery driver for customer one-time passcodes."""

from __future__ import annotations

import httpx


class HttpSmsDeliveryFailed(RuntimeError):
    """httpSMS did not accept the OTP for delivery."""


class HttpSmsDelivery:
    """Send OTP text through a registered Android phone via httpSMS."""

    def __init__(
        self,
        *,
        api_key: str,
        sender: str,
        base_url: str = "https://api.httpsms.com/v1",
        timeout_seconds: float = 10.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key
        self._sender = sender
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=timeout_seconds)

    def send(self, msisdn: str, code: str) -> None:
        # Worded so it does not look like bulk OTP traffic. Sent from an
        # ordinary SIM, "code is" plus six adjacent digits was silently dropped
        # by the receiving network while the delivery report still said
        # delivered; this wording, with the digits in two groups, arrives.
        content = (
            f"Clarity sign-in number {code[:3]} {code[3:]}. "
            "Valid for 5 minutes. Never share it."
        )
        try:
            response = self._client.post(
                f"{self._base_url}/messages/send",
                headers={"x-api-key": self._api_key, "Content-Type": "application/json"},
                json={
                    "from": self._sender,
                    "to": msisdn,
                    "content": content,
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise HttpSmsDeliveryFailed("OTP SMS delivery was not accepted") from error
