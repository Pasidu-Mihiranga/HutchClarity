"""Python rule detectors (16 + POST_PACK_BURN_RISK)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from clarity.kernel.principal import Permission
from clarity.modules.detection.public import detect, detections_to_dicts
from clarity.platform.app.module import AppBuilder, ConfigKey


class DetectBody(BaseModel):
    timeline: dict[str, Any] = Field(default_factory=dict)


def _build_router() -> APIRouter:
    router = APIRouter(tags=["detection"])

    @router.post("/v1/detect")
    def detect_route(body: DetectBody) -> dict[str, Any]:
        detections = detect(body.timeline)
        return {
            "detections": detections_to_dicts(detections),
            "count": len(detections),
        }

    return router


class DetectionModule:
    name = "detection"
    schema = "detection"

    def permissions(self) -> list[Permission]:
        return []

    def config_keys(self) -> list[ConfigKey]:
        return [
            ConfigKey("detection.double_charge.window_seconds", 600, "Duplicate charge window"),
            ConfigKey("detection.burn_risk.hours", 24, "Hours before pack end for burn risk"),
        ]

    def register(self, app: AppBuilder) -> None:
        app.routes(_build_router(), prefix="")
