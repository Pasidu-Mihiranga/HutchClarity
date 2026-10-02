"""Event projections and dashboards."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from clarity.kernel.events import EventType
from clarity.kernel.principal import Permission
from clarity.modules.insights.public import dashboard, ingest_event
from clarity.platform.app.module import AppBuilder, ConfigKey


def _build_router() -> APIRouter:
    router = APIRouter(tags=["insights"])

    @router.get("/v1/insights/dashboard")
    def dashboard_route() -> dict[str, Any]:
        return dashboard()

    return router


_INSIGHT_EVENTS = (
    EventType.CASE_CREATED,
    EventType.CASE_UPDATED,
    EventType.DECISION_GENERATED,
    EventType.ACTION_COMPLETED,
    EventType.CASE_HANDOFF,
    EventType.CAUSE_DETECTED,
)


class InsightsModule:
    name = "insights"
    schema = "insights"

    def permissions(self) -> list[Permission]:
        return []

    def config_keys(self) -> list[ConfigKey]:
        return []

    def register(self, app: AppBuilder) -> None:
        app.routes(_build_router(), prefix="")

        def _handler(payload: dict[str, Any]) -> None:
            ingest_event(payload)

        for et in _INSIGHT_EVENTS:
            app.on_event(et, _handler)
