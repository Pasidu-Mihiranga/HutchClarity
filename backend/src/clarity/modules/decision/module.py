"""ZEN decision tables, caps, budgets."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from clarity.kernel.principal import Permission
from clarity.modules.decision.public import decide
from clarity.platform.app.module import AppBuilder, ConfigKey


class DecideBody(BaseModel):
    detections: list[dict[str, Any]] = Field(default_factory=list)
    caps: dict[str, Any] | None = None
    risk: dict[str, Any] | None = None


def _build_router() -> APIRouter:
    router = APIRouter(tags=["decision"])

    @router.post("/v1/decide")
    def decide_route(body: DecideBody) -> dict[str, Any]:
        decision = decide(body.detections, body.caps, risk=body.risk)
        return {"decision": decision.to_dict()}

    return router


class DecisionModule:
    name = "decision"
    schema = "decision"

    def permissions(self) -> list[Permission]:
        return []

    def config_keys(self) -> list[ConfigKey]:
        return [
            ConfigKey("decision.auto_fix.cap_lkr", "1000.00", "Auto-fix money cap"),
            ConfigKey("decision.one_tap.cap_lkr", "5000.00", "One-tap money cap"),
            ConfigKey("decision.four_eyes.threshold_lkr", "25000.00", "Four-eyes threshold"),
            ConfigKey("decision.risk.sim_swap_window_days", 7, "SIM-swap handoff window"),
        ]

    def register(self, app: AppBuilder) -> None:
        app.routes(_build_router(), prefix="")
