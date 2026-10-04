"""What was said, kept as a record rather than as memory (A4, ADR-0040).

**Why this is not the thing plan 22 section 9 rules out.** That section forbids
"long-term memory of conversation content", and `state.py` cites it as the
reason it keeps flow, slots and a turn counter and nothing else. The concern it
is protecting against is an assistant that accumulates what a customer said and
lets it steer later answers: memory that decides. Nothing here is ever read back
into intake, composition, retrieval or a prompt. It is written after the turn is
already decided and read only by the customer whose conversation it is and by
the staff member who picks up the handoff.

That distinction is the whole design, so it is enforced rather than promised:
this module imports nothing from the orchestrator or intake, exposes only
`append` and `for_case`, and the orchestrator writes to it **after** the reply
has been composed and verified. An architecture test asserts no caller reads a
transcript into a turn.

What is written:

- **Masked text only.** The orchestrator masks before anything is stored
  (`MaskedText.text`), so an MSISDN or a NIC in a complaint lands here as a
  token, never in the clear (I13). Forbidden content never reaches this module
  at all, because the turn is refused before composition.
- **Append-only.** A transcript somebody can edit is not a record. The rows go
  in `APPEND_ONLY`, grant-backed in `full`.
- **Bounded.** Entries carry their own expiry and are filtered on read, the
  same shape `ConversationStore` uses, so a sweeper being behind can never
  surface a transcript past its retention.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
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
CONVERSATION_TRANSCRIPTS = "conversation.transcripts"

#: How long a transcript is kept.
#:
#: **ASSUMPTION - REQUIRES HUTCH CONFIRMATION.** Long enough that a customer can
#: look back at a dispute and a supervisor can review a handoff, short enough
#: that it is not a durable record of what somebody said. Ninety days matches
#: the complaint-handling window the plan assumes elsewhere; the container
#: passes a resolved value when one is configured and this is the fallback.
DEFAULT_RETENTION = timedelta(days=90)

#: Who said it. Deliberately two values: there is no third speaker, and a
#: free-text role would end up carrying an agent's name.
CUSTOMER = "customer"
CLARITY = "clarity"


@dataclass(frozen=True)
class TranscriptEntry:
    """One line of a conversation, as it was said.

    Frozen: an entry is a record of a moment. Correcting one means appending,
    never editing, which is the same rule the audit trail keeps.
    """

    case_id: str
    turn_no: int
    role: str
    text: str
    """Masked. The orchestrator never hands this module raw customer text."""
    language: str
    channel: str
    at: datetime
    expires_at: datetime

    @property
    def key(self) -> str:
        """One row per speaker per turn, so a redelivery overwrites itself."""
        return f"{self.case_id}:{self.turn_no:06d}:{self.role}"

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "turn_no": self.turn_no,
            "role": self.role,
            "text": self.text,
            "language": self.language,
            "channel": self.channel,
            "at": self.at.isoformat(),
        }


class TranscriptStore:
    """Appends and reads transcript lines, expiring them on read."""

    def __init__(
        self,
        *,
        open_unit: UnitOfWorkFactory | None = None,
        retention: timedelta = DEFAULT_RETENTION,
    ) -> None:
        if open_unit is None:
            store = MemoryStore()

            def open_memory_unit() -> MemoryUnitOfWork:
                return MemoryUnitOfWork(store)

            open_unit = open_memory_unit
        self._open_unit = open_unit
        self._retention = retention
        self._lock = threading.Lock()

    @property
    def retention(self) -> timedelta:
        return self._retention

    def append(
        self,
        case_id: str,
        *,
        role: str,
        text: str,
        turn_no: int,
        language: str,
        channel: str,
        now: datetime | None = None,
    ) -> TranscriptEntry:
        """Record one line. Empty text is not recorded rather than stored blank."""
        if role not in {CUSTOMER, CLARITY}:
            raise ValueError(f"unknown transcript role: {role!r}")
        moment = now or utc_now()
        entry = TranscriptEntry(
            case_id=case_id,
            turn_no=turn_no,
            role=role,
            text=text,
            language=language,
            channel=channel,
            at=moment,
            expires_at=moment + self._retention,
        )
        with self._lock, self._open_unit() as unit:
            self._entries(unit).put(entry.key, entry)
            unit.commit()
        return entry

    def for_case(self, case_id: str, *, now: datetime | None = None) -> list[TranscriptEntry]:
        """Every line still within retention, oldest first.

        The customer's turn precedes Clarity's within one turn number, which is
        what the key's ordering gives: "clarity" sorts before "customer", so the
        sort is on `(turn_no, role != CUSTOMER)` rather than on the key.
        """
        moment = now or utc_now()
        with self._lock, self._open_unit() as unit:
            found = [
                entry
                for entry in self._entries(unit).values()
                if entry.case_id == case_id and not entry.is_expired(moment)
            ]
        return sorted(found, key=lambda entry: (entry.turn_no, entry.role != CUSTOMER))

    def purge_expired(self, *, now: datetime | None = None) -> int:
        """Housekeeping for the table. Not what enforces retention."""
        moment = now or utc_now()
        with self._lock, self._open_unit() as unit:
            entries = self._entries(unit)
            stale = [entry.key for entry in entries.values() if entry.is_expired(moment)]
            for key in stale:
                entries.delete(key)
            unit.commit()
        return len(stale)

    @staticmethod
    def _entries(unit: Any) -> Repository[str, TranscriptEntry]:
        repository: Repository[str, TranscriptEntry] = unit.repository(CONVERSATION_TRANSCRIPTS)
        return repository


__all__ = [
    "CLARITY",
    "CONVERSATION_TRANSCRIPTS",
    "CUSTOMER",
    "DEFAULT_RETENTION",
    "TranscriptEntry",
    "TranscriptStore",
]
