"""Desk operations: bulk fix, second look, merchant watch, handover, regulator pack."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from clarity.kernel.common import utc_now
from clarity.kernel.ids import new_id


@dataclass(slots=True)
class BulkFixJob:
    id: str
    rule_id: str
    case_ids: list[str]
    status: str = "queued"
    applied: int = 0
    skipped: int = 0
    created_at: str = field(default_factory=lambda: utc_now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "rule_id": self.rule_id,
            "case_ids": list(self.case_ids),
            "status": self.status,
            "applied": self.applied,
            "skipped": self.skipped,
            "created_at": self.created_at,
        }


class DeskOps:
    def __init__(self) -> None:
        self.bulk_jobs: dict[str, BulkFixJob] = {}
        self.second_looks: list[dict[str, Any]] = []
        self.merchant_flags: dict[str, dict[str, Any]] = {}
        self.handovers: list[dict[str, Any]] = []
        self.regulator_packs: dict[str, dict[str, Any]] = {}

    def bulk_fix_all(
        self,
        *,
        rule_id: str,
        case_ids: list[str],
        dry_run: bool = False,
    ) -> BulkFixJob:
        job = BulkFixJob(
            id=new_id("BLK"),
            rule_id=rule_id,
            case_ids=list(case_ids),
        )
        if dry_run:
            job.status = "dry_run"
            job.applied = 0
            job.skipped = len(case_ids)
        else:
            job.status = "completed"
            job.applied = len(case_ids)
            job.skipped = 0
        self.bulk_jobs[job.id] = job
        return job

    def second_look(self, *, case_id: str, reviewer: str, note: str = "") -> dict[str, Any]:
        record = {
            "id": new_id("SLK"),
            "case_id": case_id,
            "reviewer": reviewer,
            "note": note,
            "created_at": utc_now().isoformat(),
        }
        self.second_looks.append(record)
        return record

    def merchant_watch(
        self,
        *,
        merchant_id: str,
        reason: str,
        active: bool = True,
    ) -> dict[str, Any]:
        record = {
            "merchant_id": merchant_id,
            "reason": reason,
            "active": active,
            "updated_at": utc_now().isoformat(),
        }
        self.merchant_flags[merchant_id] = record
        return record

    def shift_handover(
        self,
        *,
        team: str = "desk",
        from_shift: str = "morning",
        to_shift: str = "evening",
        open_cases: list[dict[str, Any]] | None = None,
        promises: list[str] | None = None,
        owners: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        record = {
            "id": new_id("HDO"),
            "team": team,
            "from_shift": from_shift,
            "to_shift": to_shift,
            "open_cases": list(open_cases or []),
            "promises": list(promises or []),
            "owners": dict(owners or {}),
            "created_at": utc_now().isoformat(),
        }
        self.handovers.append(record)
        return record

    def latest_handover(self, *, team: str | None = None) -> dict[str, Any] | None:
        items = self.handovers
        if team:
            items = [h for h in items if h.get("team") == team]
        return items[-1] if items else None

    def regulator_pack(
        self,
        *,
        period: str,
        include_receipts: bool = True,
        cases: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        pack = {
            "id": new_id("RGP"),
            "period": period,
            "include_receipts": include_receipts,
            "case_count": len(cases or []),
            "cases": list(cases or []),
            "generated_at": utc_now().isoformat(),
            "status": "ready",
        }
        self.regulator_packs[pack["id"]] = pack
        return pack

    def clear(self) -> None:
        self.bulk_jobs.clear()
        self.second_looks.clear()
        self.merchant_flags.clear()
        self.handovers.clear()
        self.regulator_packs.clear()
