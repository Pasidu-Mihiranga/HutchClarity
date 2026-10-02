"""Bulk fix, second look, merchant watch, handover, regulator pack."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from clarity.kernel.principal import Permission
from clarity.modules.deskops.public import bulk_fix, get_handover, handover, regulator_pack
from clarity.platform.app.module import AppBuilder, ConfigKey


class BulkFixBody(BaseModel):
    rule_id: str = Field(min_length=1)
    case_ids: list[str] = Field(default_factory=list)
    dry_run: bool = False


class RegulatorPackBody(BaseModel):
    period: str = Field(min_length=1)
    include_receipts: bool = True
    cases: list[dict[str, Any]] = Field(default_factory=list)


class HandoverBody(BaseModel):
    team: str = "desk"
    from_shift: str = "morning"
    to_shift: str = "evening"
    open_cases: list[dict[str, Any]] = Field(default_factory=list)
    promises: list[str] = Field(default_factory=list)
    owners: dict[str, str] = Field(default_factory=dict)


def _build_router() -> APIRouter:
    router = APIRouter(tags=["deskops"])

    @router.post("/v1/bulk-fixes")
    def bulk_fix_route(body: BulkFixBody) -> dict[str, Any]:
        return bulk_fix(rule_id=body.rule_id, case_ids=body.case_ids, dry_run=body.dry_run)

    @router.post("/v1/regulator-packs")
    def regulator_pack_route(body: RegulatorPackBody) -> dict[str, Any]:
        return regulator_pack(
            period=body.period,
            include_receipts=body.include_receipts,
            cases=body.cases,
        )

    @router.get("/v1/desk/handover")
    def handover_get(team: str | None = None) -> dict[str, Any]:
        return get_handover(team=team)

    @router.post("/v1/desk/handover")
    def handover_post(body: HandoverBody) -> dict[str, Any]:
        return handover(
            team=body.team,
            from_shift=body.from_shift,
            to_shift=body.to_shift,
            open_cases=body.open_cases,
            promises=body.promises,
            owners=body.owners,
        )

    return router


class DeskOpsModule:
    name = "deskops"
    schema = "deskops"

    def permissions(self) -> list[Permission]:
        return []

    def config_keys(self) -> list[ConfigKey]:
        return []

    def register(self, app: AppBuilder) -> None:
        app.routes(_build_router(), prefix="")
