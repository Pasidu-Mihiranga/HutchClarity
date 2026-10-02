"""Where case state lives (B02, ADR-0013).

The case service owns no dict of its own: every case record and the case-number
sequence sit behind this protocol, so the ``demo`` profile keeps them in memory
and ``full`` keeps them in PostgreSQL (B05) with no change to the service.
"""

from __future__ import annotations

from typing import Protocol

from clarity.modules.case.records import CaseRecord
from clarity.platform.persistence import Repository

#: Collection names the drivers use. One collection is one table in B05.
CASES = "case.records"
CASE_SEQUENCE = "case.sequence"

#: The single row the case-number sequence lives in.
SEQUENCE_KEY = "case_no"


class CaseRepository(Protocol):
    """Case records and the case-number sequence."""

    def get(self, case_id: str) -> CaseRecord | None:
        """The record, or ``None`` when no case has that id."""
        ...

    def save(self, record: CaseRecord) -> None:
        """Insert or replace the record."""
        ...

    def all_records(self) -> list[CaseRecord]:
        """Every case, in the order the cases were opened."""
        ...

    def next_case_number(self) -> int:
        """The next number in the per-year case sequence, consumed atomically."""
        ...


class StoredCaseRepository:
    """``CaseRepository`` over any persistence driver."""

    def __init__(
        self,
        records: Repository[str, CaseRecord],
        sequence: Repository[str, int],
    ) -> None:
        self._records = records
        self._sequence = sequence

    def get(self, case_id: str) -> CaseRecord | None:
        return self._records.get(case_id)

    def save(self, record: CaseRecord) -> None:
        self._records.put(record.case_id, record)

    def all_records(self) -> list[CaseRecord]:
        return self._records.values()

    def next_case_number(self) -> int:
        current = self._sequence.get(SEQUENCE_KEY) or 0
        nxt = current + 1
        self._sequence.put(SEQUENCE_KEY, nxt)
        return nxt


__all__ = [
    "CASES",
    "CASE_SEQUENCE",
    "SEQUENCE_KEY",
    "CaseRepository",
    "StoredCaseRepository",
]
