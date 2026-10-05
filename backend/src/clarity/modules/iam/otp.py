"""One-time passcodes for customer sign-in.

The threat here is not a clever attack, it is a cheap one: trying every
six-digit code. So a challenge is single-use, short-lived, attempt-limited and
rate-limited per number, and a wrong code is indistinguishable from an expired
or unknown one.

The code itself never leaves this module except through the delivery port. In
the demo that port writes to a **clearly labelled simulated inbox** rather than
sending an SMS, which is also how the UI shows it.
"""

from __future__ import annotations

import hmac
import secrets
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal, Protocol, runtime_checkable

from clarity.kernel.common import normalise_msisdn, utc_now
from clarity.platform.persistence import (
    MemoryStore,
    MemoryUnitOfWork,
    Repository,
    UnitOfWorkFactory,
)

OTP_CHALLENGES = "iam.otp_challenges"
OTP_REQUESTS = "iam.otp_requests"

#: Short, because a code that lives long is a code worth stealing.
OTP_TTL = timedelta(minutes=5)

#: Wrong guesses allowed before the challenge is burned.
MAX_ATTEMPTS = 3

#: Challenges one number may request inside the window, to stop SMS pumping.
MAX_REQUESTS_PER_WINDOW = 5
REQUEST_WINDOW = timedelta(minutes=15)

# Break-glass access for the synthetic customer profile only. The composition
# root deliberately does not install it for ``prod``. It still needs a live,
# unexpired challenge, is single-use and proves only this synthetic number.
SYNTHETIC_FALLBACK_MSISDN = "+94781234567"
SYNTHETIC_FALLBACK_CODE = "246810"


class OtpRefused(ValueError):
    """A challenge could not be issued or verified.

    One message for every failure: a specific one would tell an attacker
    whether a number exists, or whether a code was close.
    """

    def __init__(self, code: str = "OTP_INVALID") -> None:
        super().__init__("that code is not valid")
        self.code = code


@runtime_checkable
class OtpDelivery(Protocol):
    """How a code reaches the customer. A port, so HUTCH's SMSC can replace it."""

    def send(self, msisdn: str, code: str) -> None: ...


@dataclass
class SimulatedInbox:
    """Demo delivery: shows the code in the UI, labelled as simulated.

    Deliberately not an SMS gateway. Anything that reads from here is reading
    a mock, and the interface says so.
    """

    messages: list[dict[str, str]] = field(default_factory=list)

    def send(self, msisdn: str, code: str) -> None:
        self.messages.append(
            {
                "to": msisdn,
                "code": code,
                "text": f"Your Hutch Clarity code is {code}. It expires in 5 minutes.",
                "simulated": "yes",
                "at": utc_now().isoformat(),
            }
        )

    def latest_for(self, msisdn: str) -> dict[str, str] | None:
        normalised = normalise_msisdn(msisdn)
        for message in reversed(self.messages):
            if message["to"] == normalised:
                return message
        return None


OtpChannel = Literal["sms", "inbox", "none"]


class RoutedOtpDelivery:
    """Choose, per number, where a code goes.

    - A linked phone (a real phone the operator tied to a synthetic customer)
      gets a real SMS, when an SMS driver is configured.
    - Any other synthetic customer's number gets the labelled inbox, shown on
      the sign-in page: those numbers belong to strangers in the real world,
      so they are never texted.
    - An unknown number gets nothing. The request still issues a challenge, so
      the answer is the same (no enumeration), and nobody can make the server
      text an arbitrary number (no SMS pumping).
    """

    def __init__(
        self,
        *,
        inbox: SimulatedInbox,
        sms: OtpDelivery | None,
        sms_numbers: frozenset[str],
        known: Callable[[str], bool],
    ) -> None:
        self.inbox = inbox
        self._sms = sms
        self._sms_numbers = frozenset(normalise_msisdn(n) for n in sms_numbers)
        self._known = known

    def channel_for(self, msisdn: str) -> OtpChannel:
        normalised = normalise_msisdn(msisdn)
        if self._sms is not None and normalised in self._sms_numbers:
            return "sms"
        if self._known(normalised):
            return "inbox"
        return "none"

    def send(self, msisdn: str, code: str) -> None:
        channel = self.channel_for(msisdn)
        if channel == "sms" and self._sms is not None:
            self._sms.send(normalise_msisdn(msisdn), code)
        elif channel == "inbox":
            self.inbox.send(msisdn, code)


@dataclass
class OtpChallenge:
    code: str
    msisdn: str
    expires_at: datetime
    attempts: int = 0


class OtpService:
    """Issues and verifies one-time codes."""

    def __init__(
        self,
        delivery: OtpDelivery | None = None,
        *,
        open_unit: UnitOfWorkFactory | None = None,
        fallback: tuple[str, str] | None = None,
    ) -> None:
        self._delivery = delivery or SimulatedInbox()
        self._fallback = (
            (normalise_msisdn(fallback[0]), fallback[1]) if fallback is not None else None
        )
        if open_unit is None:
            store = MemoryStore()

            def open_memory_unit() -> MemoryUnitOfWork:
                return MemoryUnitOfWork(store)

            open_unit = open_memory_unit
        self._open_unit = open_unit
        self._lock = threading.Lock()

    @property
    def delivery(self) -> OtpDelivery:
        return self._delivery

    def request(self, msisdn: str, *, now: datetime | None = None) -> str:
        """Issue a challenge and deliver the code. Returns the challenge id.

        The code is never returned to the caller: it travels only through the
        delivery port, so possession of the phone is what proves identity.
        """
        normalised = normalise_msisdn(msisdn)
        moment = now or utc_now()

        with self._lock, self._open_unit() as unit:
            requests: Repository[str, list[datetime]] = unit.repository(OTP_REQUESTS)
            challenges: Repository[str, OtpChallenge] = unit.repository(OTP_CHALLENGES)
            recent = [at for at in (requests.get(normalised) or []) if moment - at < REQUEST_WINDOW]
            if len(recent) >= MAX_REQUESTS_PER_WINDOW:
                raise OtpRefused("OTP_RATE_LIMITED")
            recent.append(moment)
            requests.put(normalised, recent)

            challenge_id = secrets.token_urlsafe(16)
            code = f"{secrets.randbelow(1_000_000):06d}"
            challenges.put(
                challenge_id,
                OtpChallenge(
                    code=code,
                    msisdn=normalised,
                    expires_at=moment + OTP_TTL,
                ),
            )
            unit.commit()

        self._delivery.send(normalised, code)
        return challenge_id

    def verify(self, challenge_id: str, code: str, *, now: datetime | None = None) -> str:
        """Check a code and return the number it proves. Single use."""
        moment = now or utc_now()

        with self._lock, self._open_unit() as unit:
            challenges: Repository[str, OtpChallenge] = unit.repository(OTP_CHALLENGES)
            challenge = challenges.get(challenge_id)
            if challenge is None:
                raise OtpRefused
            if moment >= challenge.expires_at:
                challenges.delete(challenge_id)
                unit.commit()
                raise OtpRefused

            challenge.attempts += 1
            if challenge.attempts > MAX_ATTEMPTS:
                challenges.delete(challenge_id)
                unit.commit()
                raise OtpRefused("OTP_TOO_MANY_ATTEMPTS")

            # Constant-time, so response timing does not leak how much of
            # the code was right.
            supplied = code.strip()
            regular_match = hmac.compare_digest(challenge.code, supplied)
            fallback_match = False
            if self._fallback is not None:
                fallback_msisdn, fallback_code = self._fallback
                fallback_match = hmac.compare_digest(
                    challenge.msisdn, fallback_msisdn
                ) and hmac.compare_digest(fallback_code, supplied)
            if not (regular_match or fallback_match):
                challenges.put(challenge_id, challenge)
                unit.commit()
                raise OtpRefused

            challenges.delete(challenge_id)  # single use
            unit.commit()
            return challenge.msisdn

    @property
    def outstanding(self) -> int:
        with self._open_unit() as unit:
            challenges: Repository[str, OtpChallenge] = unit.repository(OTP_CHALLENGES)
            return len(challenges.keys())
