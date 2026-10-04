"""SMS delivery for one-time codes (B6).

**What this closes.** `OtpDelivery` had exactly one implementation,
`SimulatedInbox`, which appends the code to a list the demo UI reads. In `prod`
that meant a customer's code was generated into an inbox nobody can reach: the
sign-in path existed and could not complete. A port with one mock driver is a
design, not a capability.

**What this is not.** It is not HUTCH's SMSC. No such interface has been shared,
so this speaks the shape every HTTP SMS gateway shares - a POST with a
destination, a body and a credential - behind settings. The vendor, the field
names and the authentication are **REQUIRES HUTCH CONFIRMATION**, and the
driver is written so that confirming them is a change to configuration and a
small mapping rather than to the sign-in path.

**What it refuses to do.**

- It never logs the code, and never puts it in an exception. A code that
  reaches a log is a code in a place nobody is watching, and support tooling
  reads logs. The number is masked for the same reason (I13).
- It never reports whether the number exists. The gateway may know; this must
  not pass that on, because `POST /v1/auth/otp/request` answers the same way
  for a subscriber and a stranger and a delivery failure that says "unknown
  number" would undo that through the back door.
- It does not retry. A one-time code is valid for five minutes; a retry that
  lands after a customer has already asked for another is a second live code
  for the same number, which is the thing `MAX_REQUESTS_PER_WINDOW` exists to
  bound.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from clarity.kernel.common import mask_msisdn

_log = logging.getLogger("clarity.iam.sms")

#: What the customer reads. Short, because an SMS is 160 characters and a
#: truncated one loses the end, which is where the code is not.
#:
#: Approved wording only (I15). It carries no link: a sign-in message with a
#: link in it teaches customers to tap links in messages about their account,
#: which is the whole mechanism of the attack this system exists to explain.
TEMPLATE = "Your Hutch Clarity code is {code}. It expires in 5 minutes. We will never ask for it."


class SmsUndeliverable(RuntimeError):
    """The gateway would not take the message.

    Carries no detail about the destination, and never the code. The caller
    turns this into the same refusal it gives for every other failure.
    """


@dataclass(frozen=True)
class SmsSettings:
    """Where the gateway is and how it authenticates.

    **REQUIRES HUTCH CONFIRMATION** for every field: the URL, the sender id,
    and whether a bearer token is the credential HUTCH's SMSC expects.
    """

    url: str
    token: str
    sender: str = "HutchClarity"
    timeout_seconds: float = 5.0


class SmsOtpDelivery:
    """Sends the code to a real gateway over HTTP."""

    def __init__(self, settings: SmsSettings, *, client: httpx.Client | None = None) -> None:
        self._settings = settings
        self._client = client or httpx.Client(timeout=settings.timeout_seconds)

    def send(self, msisdn: str, code: str) -> None:
        masked = mask_msisdn(msisdn)
        try:
            response = self._client.post(
                self._settings.url,
                json={
                    "to": msisdn,
                    "from": self._settings.sender,
                    "text": TEMPLATE.format(code=code),
                },
                headers={"Authorization": f"Bearer {self._settings.token}"},
            )
            response.raise_for_status()
        except httpx.HTTPError as error:
            # The exception is logged by type, never by content: a gateway's
            # error body is a place codes and numbers end up.
            _log.warning("sms delivery failed for %s: %s", masked, type(error).__name__)
            raise SmsUndeliverable("the message could not be sent") from error

        _log.info("sms delivered for %s", masked)


__all__ = ["TEMPLATE", "SmsOtpDelivery", "SmsSettings", "SmsUndeliverable"]
