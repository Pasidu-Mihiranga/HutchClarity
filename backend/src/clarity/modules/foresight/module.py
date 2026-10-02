"""Scenario APIs, spike radar, backtest."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from clarity.kernel.principal import Permission
from clarity.modules.foresight.public import (
    create_scenario,
    radar_snapshot,
    run_scenario_by_id,
)
from clarity.platform.app.module import AppBuilder, ConfigKey


class ScenarioBody(BaseModel):
    name: str = Field(min_length=1)
    persona: str = "prepaid"
    params: dict[str, Any] = Field(default_factory=dict)
    baseline: dict[str, Any] = Field(default_factory=dict)


class RunBody(BaseModel):
    ticks: int = Field(default=5, ge=1, le=48)


def _build_router() -> APIRouter:
    router = APIRouter(tags=["foresight"])

    @router.post("/v1/simulation/scenarios")
    def create_scenario_route(body: ScenarioBody) -> dict[str, Any]:
        return create_scenario(
            name=body.name,
            persona=body.persona,
            params=body.params,
            baseline=body.baseline,
        )

    @router.post("/v1/simulation/scenarios/{scenario_id}/runs")
    def run_scenario_route(scenario_id: str, body: RunBody | None = None) -> dict[str, Any]:
        body = body or RunBody()
        try:
            return run_scenario_by_id(scenario_id, ticks=body.ticks)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="scenario not found") from error

    @router.get("/v1/foresight/radar")
    def radar_route() -> dict[str, Any]:
        return radar_snapshot()

    return router


class ForesightModule:
    name = "foresight"
    schema = "foresight"

    def permissions(self) -> list[Permission]:
        return []

    def config_keys(self) -> list[ConfigKey]:
        return [
            ConfigKey("foresight.radar.z_threshold", 2.5, "Z-score for spike alerts"),
        ]

    def register(self, app: AppBuilder) -> None:
        app.routes(_build_router(), prefix="")
