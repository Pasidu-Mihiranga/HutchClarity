"""In-memory case store (lite)."""

from __future__ import annotations

import threading
from typing import Any

from clarity.modules.case.domain.aggregate import Case, CaseStatus


class CaseStore:
    """Process-local case ledger keyed by case id."""

    def __init__(self) -> None:
        self._cases: dict[str, Case] = {}
        self._lock = threading.Lock()
        self._sequence = 0

    def next_sequence(self) -> int:
        with self._lock:
            self._sequence += 1
            return self._sequence

    def put(self, case: Case) -> Case:
        with self._lock:
            self._cases[case.id] = case
            return case

    def get(self, case_id: str) -> Case | None:
        with self._lock:
            return self._cases.get(case_id)

    def all(self) -> list[Case]:
        with self._lock:
            return list(self._cases.values())

    def update(self, case_id: str, **fields: Any) -> Case | None:
        with self._lock:
            case = self._cases.get(case_id)
            if case is None:
                return None
            for key, value in fields.items():
                if key == "status" and isinstance(value, str):
                    value = CaseStatus(value)
                if hasattr(case, key):
                    setattr(case, key, value)
            return case

    def clear(self) -> None:
        with self._lock:
            self._cases.clear()
            self._sequence = 0
