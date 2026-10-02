"""T+1 action vs adapter confirmation match."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from clarity.kernel.principal import Permission
from clarity.modules.reconciliation.public import run_reconciliation
from clarity.platform.app.module import AppBuilder, ConfigKey
from clarity.platform.messaging.jobs import JobQueue


class RunReconBody(BaseModel):
    day: str | None = Field(default=None, description="ISO date YYYY-MM-DD; default today")


def _build_router() -> APIRouter:
    router = APIRouter(tags=["reconciliation"])

    @router.post("/v1/reconciliation/run")
    def run_route(body: RunReconBody | None = None) -> dict[str, Any]:
        day = body.day if body else None
        mismatches = run_reconciliation(day)
        return {
            "day": day,
            "mismatch_count": len(mismatches),
            "mismatches": mismatches,
        }

    return router


class ReconciliationModule:
    name = "reconciliation"
    schema = "reconciliation"

    def permissions(self) -> list[Permission]:
        return []

    def config_keys(self) -> list[ConfigKey]:
        return [
            ConfigKey("reconciliation.cron", "0 2 * * *", "Daily T+1 match schedule"),
        ]

    def register(self, app: AppBuilder) -> None:
        app.routes(_build_router(), prefix="")

        def _daily() -> list[dict[str, Any]]:
            return run_reconciliation()

        app.job("reconciliation.daily", cron="0 2 * * *", fn=_daily)
        try:
            queue: JobQueue = app.resolve(JobQueue)
            queue.register("reconciliation.daily", cron="0 2 * * *", fn=_daily)
        except KeyError:
            pass
