"""Confirmation tokens: the thing the model never gets to hold (plan §10.5).

A token is minted **outside** the AI path — by the channel when a customer taps
Confirm, or by the Desk when a staff member approves with MFA step-up. The tool
layer will not execute without one. That is the mechanism behind "the LLM may
propose, never execute": a model can call ``propose``, but it has no way to
produce the token that turns a proposal into money moving.

Tokens are single-use, bound to one plan, and short-lived.
"""

from __future__ import annotations

import hmac
import secrets
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from clarity.core.tools.errors import ConfirmationInvalid
from clarity.schemas.common import utc_now

#: How long a customer has to tap Confirm before the offer goes stale.
#: ASSUMPTION — short enough to bound replay, long enough for a real person.
DEFAULT_TTL = timedelta(minutes=15)


class ConfirmedBy(StrEnum):
    """Who authorised execution. Recorded on the receipt as the actor."""

    CUSTOMER = "customer_confirmed"
    STAFF = "staff_approved"
    SYSTEM = "system_auto_fix"
    """Only ever minted for an AUTO_FIX decision (deck S5 zero-contact)."""


@dataclass(frozen=True)
class ConfirmationToken:
    """Opaque, single-use authority to execute exactly one plan."""

    value: str
    plan_id: str
    confirmed_by: ConfirmedBy
    principal_ref: str
    issued_at: datetime
    expires_at: datetime


class ConfirmationService:
    """Mints and redeems tokens. Redemption is one-shot."""

    def __init__(self, *, ttl: timedelta = DEFAULT_TTL) -> None:
        self._ttl = ttl
        self._issued: dict[str, ConfirmationToken] = {}
        self._redeemed: set[str] = set()
        # Single use must hold because of this lock, not because CPython
        # happens to serialise the check and the add.
        self._lock = threading.Lock()

    def mint(
        self,
        plan_id: str,
        *,
        confirmed_by: ConfirmedBy,
        principal_ref: str,
        now: datetime | None = None,
    ) -> ConfirmationToken:
        issued_at = now or utc_now()
        token = ConfirmationToken(
            value=secrets.token_urlsafe(32),
            plan_id=plan_id,
            confirmed_by=confirmed_by,
            principal_ref=principal_ref,
            issued_at=issued_at,
            expires_at=issued_at + self._ttl,
        )
        self._issued[token.value] = token
        return token

    def redeem(self, value: str, *, plan_id: str, now: datetime | None = None) -> ConfirmationToken:
        """Consume a token for ``plan_id``.

        Raises :class:`ConfirmationInvalid` for unknown, expired, reused, or
        mismatched tokens. Each failure is deliberately indistinguishable to
        the caller, so the error cannot be used to probe which tokens exist.
        """
        moment = now or utc_now()

        with self._lock:
            return self._redeem_locked(value, plan_id, moment)

    def _redeem_locked(self, value: str, plan_id: str, moment: datetime) -> ConfirmationToken:
        token = next(
            (t for t in self._issued.values() if hmac.compare_digest(t.value, value)),
            None,
        )
        if token is None:
            raise ConfirmationInvalid("confirmation token is not valid")
        if token.value in self._redeemed:
            raise ConfirmationInvalid("confirmation token is not valid")
        if token.plan_id != plan_id:
            raise ConfirmationInvalid("confirmation token is not valid")
        if moment >= token.expires_at:
            raise ConfirmationInvalid("confirmation token is not valid")

        self._redeemed.add(token.value)
        return token
