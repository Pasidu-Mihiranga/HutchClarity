"""Durable idempotency for execution (M-ACT, ADR-0005, I8).

One record per ``Idempotency-Key``, in the repository rather than in a dict, so
the guarantee survives a restart and holds across replicas. Two things it has
to get right, and the prototype got only the first:

**Never twice.** A duplicate request finds the record and takes the original
outcome instead of acting again. The claim is an insert that only one caller
can win, which is what the key's uniqueness buys.

**Never stuck.** The prototype stored the first failure and replayed it forever,
so a plan refused because the day's refund budget was spent could never execute,
even after the budget reset. A failure is now recorded with whether it was
final, and a transient one leaves the key claimable again under the next attempt
number. A final refusal still replays, because a caller must not get a different
answer for the same request by asking twice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from clarity.kernel.common import utc_now
from clarity.modules.actions.results import ExecutionResult
from clarity.platform.persistence import (
    ConcurrentUpdate,
    Repository,
    UnitOfWork,
    UnitOfWorkFactory,
)

#: Collection the attempt records live in. One collection is one table in B05.
ATTEMPTS = "actions.attempts"


class AttemptState(StrEnum):
    RUNNING = "running"
    """Claimed and still executing. A duplicate waits for the outcome."""

    SUCCEEDED = "succeeded"
    """Executed. A duplicate returns this result, marked as a replay."""

    REFUSED = "refused"
    """Refused for good. A duplicate gets the same refusal."""

    FAILED_TRANSIENTLY = "failed_transiently"
    """Nothing was applied and the cause may pass. The key is claimable again."""


@dataclass
class AttemptRecord:
    """What happened to one idempotency key."""

    idempotency_key: str
    plan_id: str
    attempt: int = 1
    state: AttemptState = AttemptState.RUNNING
    error_code: str | None = None
    error_message: str | None = None
    result: ExecutionResult | None = None
    started_at: datetime = field(default_factory=utc_now)
    settled_at: datetime | None = None

    @property
    def is_open(self) -> bool:
        """Whether a caller may claim this key for a new attempt."""
        return self.state is AttemptState.FAILED_TRANSIENTLY

    @property
    def is_settled(self) -> bool:
        return self.state in {
            AttemptState.SUCCEEDED,
            AttemptState.REFUSED,
            AttemptState.FAILED_TRANSIENTLY,
        }


class AttemptLost(RuntimeError):
    """Another caller holds this idempotency key.

    Not an error for the caller to show anyone: it means "that request is
    already being handled", and the caller waits for the original outcome.
    """


class AttemptLog:
    """The attempt records, claimed and settled one transaction at a time."""

    def __init__(self, open_unit: UnitOfWorkFactory) -> None:
        self._open_unit = open_unit

    def get(self, idempotency_key: str) -> AttemptRecord | None:
        with self._open_unit() as unit:
            return self._records(unit).get(idempotency_key)

    def claim(self, idempotency_key: str, *, plan_id: str) -> AttemptRecord:
        """Take this key for a new attempt, or raise ``AttemptLost``.

        The whole exactly-once guarantee rests here. The read and the write are
        one transaction, so two replicas claiming the same key at the same moment
        cannot both succeed: one commits and the other is refused by the row's
        version (B02, B05).
        """
        with self._open_unit() as unit:
            records: Repository[str, AttemptRecord] = unit.repository(ATTEMPTS)
            existing = records.get(idempotency_key)

            if existing is not None and not existing.is_open:
                raise AttemptLost(idempotency_key)

            attempt = AttemptRecord(
                idempotency_key=idempotency_key,
                plan_id=plan_id,
                # A transient failure leaves the key claimable, and the next
                # claim is a new attempt rather than a repeat of the old one.
                attempt=1 if existing is None else existing.attempt + 1,
            )
            records.put(idempotency_key, attempt)
            try:
                unit.commit()
            except ConcurrentUpdate as clash:
                raise AttemptLost(idempotency_key) from clash
            return attempt

    def succeeded(self, idempotency_key: str, result: ExecutionResult) -> None:
        self._settle(idempotency_key, AttemptState.SUCCEEDED, result=result)

    def refused(self, idempotency_key: str, *, code: str, message: str) -> None:
        """Record a final refusal: a duplicate must get this same answer."""
        self._settle(idempotency_key, AttemptState.REFUSED, code=code, message=message)

    def failed_transiently(self, idempotency_key: str, *, code: str, message: str) -> None:
        """Record a failure that changed nothing, leaving the key claimable."""
        self._settle(idempotency_key, AttemptState.FAILED_TRANSIENTLY, code=code, message=message)

    def _settle(
        self,
        idempotency_key: str,
        state: AttemptState,
        *,
        result: ExecutionResult | None = None,
        code: str | None = None,
        message: str | None = None,
    ) -> None:
        with self._open_unit() as unit:
            records: Repository[str, AttemptRecord] = unit.repository(ATTEMPTS)
            record = records.get(idempotency_key)
            if record is None:  # pragma: no cover - the claim created it
                return
            record.state = state
            record.result = result
            record.error_code = code
            record.error_message = message
            record.settled_at = utc_now()
            records.put(idempotency_key, record)
            try:
                unit.commit()
            except ConcurrentUpdate:
                # Another replica settled the same attempt. Both wrote the same
                # outcome, because only the claim holder reaches this.
                return

    @staticmethod
    def _records(unit: UnitOfWork) -> Repository[str, AttemptRecord]:
        return unit.repository(ATTEMPTS)


__all__ = [
    "ATTEMPTS",
    "AttemptLog",
    "AttemptLost",
    "AttemptRecord",
    "AttemptState",
]
