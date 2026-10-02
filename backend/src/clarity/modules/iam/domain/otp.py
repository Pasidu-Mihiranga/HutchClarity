"""OTP challenge store: 6-digit codes, 5-minute TTL, in-memory."""

from __future__ import annotations

import hmac
import secrets
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta

from clarity.kernel.common import normalise_msisdn, utc_now

OTP_TTL = timedelta(minutes=5)
MAX_ATTEMPTS = 3
MAX_REQUESTS_PER_WINDOW = 5
REQUEST_WINDOW = timedelta(minutes=15)


class OtpRefused(ValueError):
    """Challenge could not be issued or verified (intentionally opaque)."""

    def __init__(self, code: str = "OTP_INVALID") -> None:
        super().__init__("that code is not valid")
        self.code = code


@dataclass
class _Challenge:
    code: str
    msisdn: str
    expires_at: datetime
    attempts: int = 0


class OtpStore:
    """Issues and verifies one-time codes keyed by normalised MSISDN."""

    def __init__(self) -> None:
        self._challenges: dict[str, _Challenge] = {}
        self._requests: dict[str, list[datetime]] = {}
        self._lock = threading.Lock()

    def request(self, msisdn: str, *, now: datetime | None = None) -> str:
        """Issue a challenge. Returns the 6-digit code (caller delivers it)."""
        normalised = normalise_msisdn(msisdn)
        moment = now or utc_now()

        with self._lock:
            recent = [
                at for at in self._requests.get(normalised, []) if moment - at < REQUEST_WINDOW
            ]
            if len(recent) >= MAX_REQUESTS_PER_WINDOW:
                raise OtpRefused("OTP_RATE_LIMITED")
            recent.append(moment)
            self._requests[normalised] = recent

            code = f"{secrets.randbelow(1_000_000):06d}"
            self._challenges[normalised] = _Challenge(
                code=code, msisdn=normalised, expires_at=moment + OTP_TTL
            )
            return code

    def verify(self, msisdn: str, code: str, *, now: datetime | None = None) -> str:
        """Check a code; returns the normalised MSISDN. Single use."""
        normalised = normalise_msisdn(msisdn)
        moment = now or utc_now()

        with self._lock:
            challenge = self._challenges.get(normalised)
            if challenge is None:
                raise OtpRefused
            if moment >= challenge.expires_at:
                del self._challenges[normalised]
                raise OtpRefused

            challenge.attempts += 1
            if challenge.attempts > MAX_ATTEMPTS:
                del self._challenges[normalised]
                raise OtpRefused("OTP_TOO_MANY_ATTEMPTS")

            if not hmac.compare_digest(challenge.code, code.strip()):
                raise OtpRefused

            del self._challenges[normalised]
            return challenge.msisdn

    def peek_code(self, msisdn: str) -> str | None:
        """Demo helper: read outstanding code without consuming it."""
        normalised = normalise_msisdn(msisdn)
        with self._lock:
            challenge = self._challenges.get(normalised)
            return challenge.code if challenge else None
