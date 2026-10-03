"""Conversation state per case, with a TTL (C01, plan 22 section 9).

State is keyed by **case id**, not by channel or session, and that is the whole
mechanism behind cross-channel continuity: a customer who starts on WhatsApp and
opens the app is the same conversation because it is the same case. Keying by
session would make "continue where I left off" a per-channel feature, which is
the thing plan 22 section 9 rules out.

What is kept is deliberately small: flow, state, slots, language, the last
proposal id, and a turn counter. Three things are deliberately **not** kept:

- **No message history.** Plan 22 section 9 allows no long-term memory of
  conversation content. Durable preferences belong in the customer profile.
- **No personal data.** Slots hold hints like an amount or a product, never a
  number or a name. The orchestrator masks before anything is stored.
- **No authority.** `last_proposal_id` is a pointer, not a permission. Executing
  a proposal still needs a confirmation token minted outside this path
  (ADR-0007), so a stale or stolen state object buys nothing.

Storage goes through the unit of work (B02), so `lite` gets the in-memory
repository and `full` gets PostgreSQL with no change here.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from clarity.kernel.common import utc_now
from clarity.platform.persistence import (
    MemoryStore,
    MemoryUnitOfWork,
    Repository,
    UnitOfWorkFactory,
)

#: The repository collection. Owned by the conversation module (I6).
CONVERSATION_STATES = "conversation.states"

#: How long a conversation can be resumed for.
#:
#: **ASSUMPTION - REQUIRES HUTCH CONFIRMATION.** Plan 22 section 9 proposes 24
#: hours. It is a constant rather than a policy artefact because it decides how
#: long a chat resumes, not an amount, an eligibility or a cap: nothing about a
#: decision changes when it moves. `OTP_TTL` in the iam module sits here for the
#: same reason. If HUTCH wants it under the policy lifecycle it becomes a
#: resolved value and this constant becomes the fallback.
DEFAULT_TTL = timedelta(hours=24)

#: The state a conversation starts in before any flow has claimed it. C02 (#21)
#: brings the flow registry; until then every turn stays here, which is a
#: truthful "no flow is driving this" rather than a guess at one.
NO_FLOW = "none"
INITIAL_STATE = "start"


@dataclass
class ConversationState:
    """Short-term state for one case's conversation.

    `channels` records every channel this conversation has been held on, in
    order. It exists so the audit trail can show a handover actually happened
    rather than leaving it to be inferred from two timestamps.
    """

    case_id: str
    flow: str = NO_FLOW
    state: str = INITIAL_STATE
    language: str = "en"
    slots: dict[str, Any] = field(default_factory=dict)
    last_proposal_id: str | None = None
    turn_no: int = 0
    channels: list[str] = field(default_factory=list)
    updated_at: datetime = field(default_factory=utc_now)
    expires_at: datetime = field(default_factory=lambda: utc_now() + DEFAULT_TTL)

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at

    def to_dict(self) -> dict[str, Any]:
        """A view for the audit detail and the API. Carries no personal data."""
        return {
            "case_id": self.case_id,
            "flow": self.flow,
            "state": self.state,
            "language": self.language,
            "slots": dict(self.slots),
            "last_proposal_id": self.last_proposal_id,
            "turn_no": self.turn_no,
            "channels": list(self.channels),
        }


class ConversationStore:
    """Reads and writes conversation state, expiring it on read.

    Expiry is applied when the state is read, not by a sweeper. A sweeper that
    has not run yet would hand back state past its TTL, and "the cleanup job is
    behind" is not a reason a conversation should resume a day later. The sweep
    in `purge_expired` is housekeeping for the table, not the thing that
    enforces the TTL.
    """

    def __init__(
        self,
        *,
        open_unit: UnitOfWorkFactory | None = None,
        ttl: timedelta = DEFAULT_TTL,
    ) -> None:
        if open_unit is None:
            store = MemoryStore()

            def open_memory_unit() -> MemoryUnitOfWork:
                return MemoryUnitOfWork(store)

            open_unit = open_memory_unit
        self._open_unit = open_unit
        self._ttl = ttl
        self._lock = threading.Lock()

    @property
    def ttl(self) -> timedelta:
        return self._ttl

    def get(self, case_id: str, *, now: datetime | None = None) -> ConversationState | None:
        """The live state for a case, or None when there is none or it expired."""
        moment = now or utc_now()
        with self._lock, self._open_unit() as unit:
            states = self._states(unit)
            found = states.get(case_id)
            if found is None:
                return None
            if found.is_expired(moment):
                # Dropped on read, so an expired conversation cannot come back
                # if a later caller happens to pass an earlier timestamp.
                states.delete(case_id)
                unit.commit()
                return None
            return found

    def resume_or_start(
        self,
        case_id: str,
        *,
        channel: str,
        language: str | None = None,
        now: datetime | None = None,
    ) -> tuple[ConversationState, bool]:
        """The state for this case, creating it if there is none.

        Returns the state and whether it was resumed. The caller needs to know
        which, because resuming across a channel is an auditable fact.
        """
        moment = now or utc_now()
        existing = self.get(case_id, now=moment)
        if existing is not None:
            if channel and (not existing.channels or existing.channels[-1] != channel):
                existing.channels.append(channel)
            if language:
                existing.language = language
            self.save(existing, now=moment)
            return existing, True

        fresh = ConversationState(
            case_id=case_id,
            language=language or "en",
            channels=[channel] if channel else [],
            updated_at=moment,
            expires_at=moment + self._ttl,
        )
        self.save(fresh, now=moment)
        return fresh, False

    def save(self, state: ConversationState, *, now: datetime | None = None) -> ConversationState:
        """Persist the state and push its expiry out by the full TTL.

        Each turn extends the window: a conversation someone is still having
        should not expire mid-sentence because it started 24 hours ago.
        """
        moment = now or utc_now()
        state.updated_at = moment
        state.expires_at = moment + self._ttl
        with self._lock, self._open_unit() as unit:
            self._states(unit).put(state.case_id, state)
            unit.commit()
        return state

    def drop(self, case_id: str) -> None:
        with self._lock, self._open_unit() as unit:
            self._states(unit).delete(case_id)
            unit.commit()

    def purge_expired(self, *, now: datetime | None = None) -> int:
        """Housekeeping: remove expired rows. Returns how many went.

        The TTL is already enforced on read, so this only keeps the table from
        growing. It is safe to never call it and safe to call it often.
        """
        moment = now or utc_now()
        with self._lock, self._open_unit() as unit:
            states = self._states(unit)
            # `keys()` is the Repository port's method, not a mapping's.
            stored: list[str] = states.keys()
            stale = [key for key in stored if _expired(states.get(key), moment)]
            for key in stale:
                states.delete(key)
            unit.commit()
            return len(stale)

    @staticmethod
    def _states(unit: Any) -> Repository[str, ConversationState]:
        repository: Repository[str, ConversationState] = unit.repository(CONVERSATION_STATES)
        return repository


def _expired(state: ConversationState | None, now: datetime) -> bool:
    return state is not None and state.is_expired(now)


__all__ = [
    "CONVERSATION_STATES",
    "DEFAULT_TTL",
    "INITIAL_STATE",
    "NO_FLOW",
    "ConversationState",
    "ConversationStore",
]
