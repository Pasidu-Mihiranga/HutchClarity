"""Desk operations as one surface (D01, #26; plan 02 section 3.5).

Holds the batches so an approval survives the request that gave it, and reads
case facts through a protocol the composition root fills, so `deskops` adds no
module edge (I22).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from typing import Any, Protocol

from clarity.kernel.common import utc_now
from clarity.kernel.ids import new_id
from clarity.modules.deskops.bulk import (
    BulkFix,
    BulkFixes,
    BulkFixRefused,
    CaseFixer,
)
from clarity.modules.deskops.watch import (
    DEFAULT_WINDOW,
    DeskCase,
    Handover,
    MerchantScore,
    RegulatorPack,
    handover,
    merchant_watch,
    regulator_pack,
)
from clarity.platform.persistence import (
    MemoryStore,
    MemoryUnitOfWork,
    Repository,
    UnitOfWork,
    UnitOfWorkFactory,
)

#: One collection is one table in B05.
BATCHES = "deskops.batches"


class DeskCases(Protocol):
    """The case facts the desk views read."""

    def recent(self, since: datetime) -> Sequence[DeskCase]: ...


class DeskOps:
    """Bulk fixes, merchant watch, regulator packs and shift handovers."""

    def __init__(
        self,
        *,
        fixer: CaseFixer,
        cases: DeskCases,
        open_unit: UnitOfWorkFactory | None = None,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        if open_unit is None:
            store = MemoryStore()

            def open_memory_unit() -> MemoryUnitOfWork:
                return MemoryUnitOfWork(store)

            open_unit = open_memory_unit
        self._open_unit = open_unit
        self._cases = cases
        self._clock = clock
        self._batches = BulkFixes(fixer, clock=clock)

    @staticmethod
    def _store(unit: UnitOfWork) -> Repository[str, BulkFix]:
        return unit.repository(BATCHES)

    # -- bulk fix --------------------------------------------------------- #

    def draft_bulk_fix(self, case_ids: Sequence[str], *, reason: str, created_by: str) -> BulkFix:
        """Draft and dry run. Nothing can execute from this state."""
        batch = self._batches.draft(case_ids, reason=reason, created_by=created_by)
        self._save(batch)
        return batch

    def approve_bulk_fix(
        self, batch_id: str, *, approver_ref: str, role: str, fingerprint: str
    ) -> BulkFix:
        """Record a checker's approval of the dry run they were shown."""
        batch = self._require(batch_id)
        approved = self._batches.approve(
            batch, approver_ref=approver_ref, role=role, fingerprint=fingerprint
        )
        self._save(approved)
        return approved

    def execute_bulk_fix(self, batch_id: str) -> BulkFix:
        """Execute an approved batch, producing one receipt per case."""
        batch = self._require(batch_id)
        executed = self._batches.execute(batch)
        self._save(executed)
        return executed

    def batch(self, batch_id: str) -> BulkFix | None:
        with self._open_unit() as unit:
            return self._store(unit).get(batch_id)

    def batches(self) -> list[BulkFix]:
        with self._open_unit() as unit:
            return self._store(unit).values()

    def _require(self, batch_id: str) -> BulkFix:
        found = self.batch(batch_id)
        if found is None:
            raise BulkFixRefused(f"no batch {batch_id}")
        return found

    def _save(self, batch: BulkFix) -> None:
        with self._open_unit() as unit:
            self._store(unit).put(batch.batch_id, batch)
            unit.commit()

    # -- the read-only views --------------------------------------------- #

    def merchant_watch(self, *, span: timedelta = DEFAULT_WINDOW) -> list[MerchantScore]:
        return merchant_watch(self._window(span))

    def regulator_pack(
        self, *, generated_by: str, span: timedelta = DEFAULT_WINDOW
    ) -> RegulatorPack:
        now = self._clock()
        return regulator_pack(
            self._window(span),
            window_from=now - span,
            window_to=now,
            generated_by=generated_by,
            now=now,
            pack_id=new_id("PACK"),
        )

    def handover(self, *, prepared_by: str, span: timedelta = timedelta(hours=8)) -> Handover:
        now = self._clock()
        return handover(
            self._window(span),
            shift_from=now - span,
            shift_to=now,
            prepared_by=prepared_by,
        )

    def _window(self, span: timedelta) -> Sequence[DeskCase]:
        return self._cases.recent(self._clock() - span)

    def to_dict(self) -> dict[str, Any]:
        """A desk summary, for a console or a smoke check."""
        return {
            "batches": [b.to_dict() for b in self.batches()],
            "merchant_watch": [m.to_dict() for m in self.merchant_watch()],
        }


__all__ = ["BATCHES", "DeskCases", "DeskOps"]
