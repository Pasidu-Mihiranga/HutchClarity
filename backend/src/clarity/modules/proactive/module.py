"""Zero-contact stream detectors."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from clarity.kernel.events import EventType
from clarity.kernel.principal import Permission
from clarity.modules.proactive.public import evaluate_event
from clarity.platform.app.module import AppBuilder, ConfigKey
from clarity.platform.messaging.outbox import InMemoryBus


class EvaluateBody(BaseModel):
    type: str = Field(min_length=1)
    subject: str | None = None
    subscriber_ref: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


def _build_router() -> APIRouter:
    router = APIRouter(tags=["proactive"])

    @router.post("/v1/proactive/evaluate")
    def evaluate_route(body: EvaluateBody) -> dict[str, Any]:
        event = {
            "type": body.type,
            "subject": body.subject or body.subscriber_ref or "",
            "subscriber_ref": body.subscriber_ref,
            "data": body.data,
        }
        try:
            actions = evaluate_event(event)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {"actions": actions, "count": len(actions)}

    return router


_BUS_TYPES = (
    EventType.PAYMENT_RECORDED,
    EventType.USAGE_THRESHOLD_REACHED,
    EventType.PACK_EXPIRING,
    EventType.VAS_RENEWED,
    EventType.CHARGE_APPLIED,
    EventType.RISK_DETECTED,
)


class ProactiveModule:
    name = "proactive"
    schema = "proactive"

    def permissions(self) -> list[Permission]:
        return []

    def config_keys(self) -> list[ConfigKey]:
        return [
            ConfigKey("proactive.fup.band_low", 80, "FUP notice low band percent"),
            ConfigKey("proactive.fup.band_high", 95, "FUP notice high band percent"),
        ]

    def register(self, app: AppBuilder) -> None:
        app.routes(_build_router(), prefix="")

        def _on_payload(payload: dict[str, Any]) -> None:
            evaluate_event(payload)

        for et in _BUS_TYPES:
            app.on_event(et, _on_payload)

        # Also wire InMemoryBus when provided (lite profile).
        try:
            bus: InMemoryBus = app.resolve(InMemoryBus)
        except KeyError:
            return

        def _bus_handler(event: Any) -> None:
            payload = {
                "type": event.type.value if hasattr(event.type, "value") else str(event.type),
                "subject": getattr(event, "subject", ""),
                "subscriber_ref": (getattr(event, "data", None) or {}).get("subscriber_ref"),
                "data": getattr(event, "data", {}) or {},
            }
            evaluate_event(payload)

        for et in _BUS_TYPES:
            bus.subscribe(et, _bus_handler)
