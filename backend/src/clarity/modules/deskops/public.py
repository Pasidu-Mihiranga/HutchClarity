"""Public facade for the deskops module."""

from __future__ import annotations

from typing import Any

from clarity.modules.deskops.domain.ops import DeskOps

_ops = DeskOps()


def reset_deskops() -> None:
    _ops.clear()


def bulk_fix(
    *,
    rule_id: str,
    case_ids: list[str],
    dry_run: bool = False,
) -> dict[str, Any]:
    return _ops.bulk_fix_all(rule_id=rule_id, case_ids=case_ids, dry_run=dry_run).to_dict()


def second_look(*, case_id: str, reviewer: str, note: str = "") -> dict[str, Any]:
    return _ops.second_look(case_id=case_id, reviewer=reviewer, note=note)


def merchant_watch(*, merchant_id: str, reason: str, active: bool = True) -> dict[str, Any]:
    return _ops.merchant_watch(merchant_id=merchant_id, reason=reason, active=active)


def handover(
    *,
    team: str = "desk",
    from_shift: str = "morning",
    to_shift: str = "evening",
    open_cases: list[dict[str, Any]] | None = None,
    promises: list[str] | None = None,
    owners: dict[str, str] | None = None,
) -> dict[str, Any]:
    return _ops.shift_handover(
        team=team,
        from_shift=from_shift,
        to_shift=to_shift,
        open_cases=open_cases,
        promises=promises,
        owners=owners,
    )


def get_handover(*, team: str | None = None) -> dict[str, Any]:
    record = _ops.latest_handover(team=team)
    if record is None:
        # Empty structured handover when none recorded yet.
        return {
            "team": team or "desk",
            "open_cases": [],
            "promises": [],
            "owners": {},
            "status": "empty",
        }
    return record


def regulator_pack(
    *,
    period: str,
    include_receipts: bool = True,
    cases: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return _ops.regulator_pack(
        period=period,
        include_receipts=include_receipts,
        cases=cases,
    )


__all__ = [
    "bulk_fix",
    "get_handover",
    "handover",
    "merchant_watch",
    "regulator_pack",
    "reset_deskops",
    "second_look",
]
