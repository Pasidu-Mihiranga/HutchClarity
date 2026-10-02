"""Confirmation tokens: the thing the model never gets to hold (plan §10.5).

A token is minted **outside** the AI path - by the channel when a customer taps
Confirm, or by the Desk when a staff member approves with MFA step-up. The tool
layer will not execute without one. That is the mechanism behind "the LLM may
propose, never execute": a model can call ``propose``, but it has no way to
produce the token that turns a proposal into money moving.

Tokens are single-use, bound to one plan, and short-lived.

**Where they are kept** (M-ACT). A token used to live in a dict in one process,
which meant a customer whose Confirm tap reached a different replica from the
one that minted the token was refused. They now live in a repository, so single
use is enforced by the store rather than by a lock that only one process holds.

Redemption looks a token up by a hash of its value, never by scanning. A scan
over every issued token is both slow and a timing side channel, and the lookup
has to be exact for the repository to make it atomic.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from clarity.kernel.common import utc_now
from clarity.modules.actions.errors import ConfirmationInvalid
from clarity.modules.actions.results import ConfirmationToken, ConfirmedBy
from clarity.platform.persistence import (
    ConcurrentUpdate,
    Repository,
    UnitOfWork,
    UnitOfWorkFactory,
)

#: How long a customer has to tap Confirm before the offer goes stale.
#: ASSUMPTION - short enough to bound replay, long enough for a real person.
DEFAULT_TTL = timedelta(minutes=15)


#: Collection the token records live in. One collection is one table in B05.
CONFIRMATIONS = "actions.confirmations"


@dataclass
class ConfirmationRecord:
    """One minted token and whether it has been spent.

    The token's value is **not** stored. A record holds a hash of it, so a dump
    of this table does not let anyone execute a plan.
    """

    token_hash: str
    plan_id: str
    confirmed_by: ConfirmedBy
    principal_ref: str
    issued_at: datetime
    expires_at: datetime
    redeemed_at: datetime | None = None

    @property
    def is_spent(self) -> bool:
        return self.redeemed_at is not None

    def token(self, value: str) -> ConfirmationToken:
        """Rebuild the caller's token from the record, for the executor."""
        return ConfirmationToken(
            value=value,
            plan_id=self.plan_id,
            confirmed_by=self.confirmed_by,
            principal_ref=self.principal_ref,
            issued_at=self.issued_at,
            expires_at=self.expires_at,
        )


def _hash(value: str) -> str:
    """A token's lookup key. SHA-256 of the value, never the value itself."""
    return hashlib.sha256(value.encode()).hexdigest()


class ConfirmationService:
    """Mints and redeems tokens. Redemption is one-shot."""

    def __init__(
        self,
        open_unit: UnitOfWorkFactory,
        *,
        ttl: timedelta = DEFAULT_TTL,
    ) -> None:
        self._ttl = ttl
        self._open_unit = open_unit

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
        with self._open_unit() as unit:
            self._records(unit).put(
                _hash(token.value),
                ConfirmationRecord(
                    token_hash=_hash(token.value),
                    plan_id=plan_id,
                    confirmed_by=confirmed_by,
                    principal_ref=principal_ref,
                    issued_at=issued_at,
                    expires_at=token.expires_at,
                ),
            )
            unit.commit()
        return token

    def redeem(self, value: str, *, plan_id: str, now: datetime | None = None) -> ConfirmationToken:
        """Consume a token for ``plan_id``.

        Raises :class:`ConfirmationInvalid` for unknown, expired, reused, or
        mismatched tokens. Each failure is deliberately indistinguishable to
        the caller, so the error cannot be used to probe which tokens exist.
        """
        moment = now or utc_now()
        key = _hash(value)

        # The read, the checks and the write are one transaction, so two
        # replicas redeeming the same token cannot both pass: one commits and
        # the other is refused by the row's version (B02, B05). That is what
        # makes single use a property of the store rather than of a lock.
        with self._open_unit() as unit:
            records = self._records(unit)
            record = records.get(key)

            if (
                record is None
                or record.is_spent
                or not hmac.compare_digest(record.plan_id, plan_id)
                or moment >= record.expires_at
            ):
                # Deliberately one message for every reason, so the error cannot
                # be used to probe which tokens exist.
                raise ConfirmationInvalid("confirmation token is not valid")

            record.redeemed_at = moment
            records.put(key, record)
            try:
                unit.commit()
            except ConcurrentUpdate as clash:
                # Another replica spent it between the read and the commit.
                raise ConfirmationInvalid("confirmation token is not valid") from clash
            return record.token(value)

    @staticmethod
    def _records(unit: UnitOfWork) -> Repository[str, ConfirmationRecord]:
        return unit.repository(CONFIRMATIONS)


__all__ = [
    "CONFIRMATIONS",
    "DEFAULT_TTL",
    "ConfirmationRecord",
    "ConfirmationService",
]
