"""Hash-chained audit ledger."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from clarity.kernel.common import utc_now
from clarity.kernel.ids import new_id


def _hash_entry(prev: str, payload: dict[str, Any]) -> str:
    blob = prev + json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


@dataclass
class AuditEntry:
    id: str
    actor: str
    action: str
    subject: str
    detail: dict[str, Any]
    at: datetime
    prev_hash: str
    hash: str


@dataclass
class AuditLedger:
    """Append-only, hash-chained audit log. Tamper detection via verify()."""

    entries: list[AuditEntry] = field(default_factory=list)
    _last_hash: str = "0" * 64

    def append(
        self,
        *,
        actor: str,
        action: str,
        subject: str,
        detail: dict[str, Any] | None = None,
    ) -> AuditEntry:
        at = utc_now()
        payload = {
            "actor": actor,
            "action": action,
            "subject": subject,
            "detail": detail or {},
            "at": at.isoformat(),
        }
        digest = _hash_entry(self._last_hash, payload)
        entry = AuditEntry(
            id=new_id("AUD"),
            actor=actor,
            action=action,
            subject=subject,
            detail=detail or {},
            at=at,
            prev_hash=self._last_hash,
            hash=digest,
        )
        self.entries.append(entry)
        self._last_hash = digest
        return entry

    def verify(self) -> bool:
        prev = "0" * 64
        for entry in self.entries:
            payload_stored = {
                "actor": entry.actor,
                "action": entry.action,
                "subject": entry.subject,
                "detail": entry.detail,
                "at": entry.at.isoformat(),
            }
            expected = _hash_entry(entry.prev_hash, payload_stored)
            if entry.prev_hash != prev or entry.hash != expected:
                return False
            prev = entry.hash
        return True

    def tamper(self, index: int, *, action: str) -> None:
        """Test helper: mutate an entry without updating the chain."""
        self.entries[index].action = action
