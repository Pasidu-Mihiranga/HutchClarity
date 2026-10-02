"""8-source timeline snapshots."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from clarity.kernel.principal import Permission
from clarity.modules.timeline.public import build_timeline
from clarity.platform.app.module import AppBuilder, ConfigKey


class BuildTimelineBody(BaseModel):
    subscriber_ref: str = Field(min_length=1)
    world: dict[str, Any] = Field(default_factory=dict)
    ports: dict[str, Any] | None = None


def _build_router() -> APIRouter:
    router = APIRouter(tags=["timeline"])

    @router.post("/v1/timeline/build")
    def timeline_build(body: BuildTimelineBody) -> dict[str, Any]:
        try:
            return build_timeline(
                body.subscriber_ref,
                ports=body.ports,
                world=body.world,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    return router


class TimelineModule:
    name = "timeline"
    schema = "timeline"

    def permissions(self) -> list[Permission]:
        return []

    def config_keys(self) -> list[ConfigKey]:
        return [
            ConfigKey("timeline.window_days", 90, "Default lookback window"),
        ]

    def register(self, app: AppBuilder) -> None:
        app.routes(_build_router(), prefix="")
