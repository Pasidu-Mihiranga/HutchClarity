"""Case aggregate, channel thread, handoff, smart queue."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from clarity.kernel.principal import Permission
from clarity.modules.case.public import (
    attach_action,
    create_case,
    get_case,
    handoff,
    list_queue,
)
from clarity.platform.app.module import AppBuilder, ConfigKey


class CreateCaseBody(BaseModel):
    subscriber_ref: str = Field(min_length=1)
    channel: str = "web"
    message: str | None = None
    amount_lkr: str | None = None
    detections: list[dict[str, Any]] = Field(default_factory=list)
    decision: dict[str, Any] | None = None


class HandoffBody(BaseModel):
    reason: str = "customer_requested"
    note: str | None = None


class CaseActionBody(BaseModel):
    action_type: str = Field(min_length=1)
    amount_lkr: str | None = None
    idempotency_key: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


def _build_router() -> APIRouter:
    router = APIRouter(tags=["case"])

    @router.post("/v1/cases")
    def create_case_route(body: CreateCaseBody) -> dict[str, Any]:
        try:
            case = create_case(
                subscriber_ref=body.subscriber_ref,
                channel=body.channel,
                message=body.message,
                amount_lkr=body.amount_lkr,
                detections=body.detections or None,
                decision=body.decision,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return case.to_dict()

    @router.get("/v1/cases/{case_id}")
    def get_case_route(case_id: str) -> dict[str, Any]:
        try:
            return get_case(case_id).to_dict()
        except KeyError as error:
            raise HTTPException(status_code=404, detail="case not found") from error

    @router.get("/v1/desk/queue")
    def desk_queue(limit: int = 50) -> list[dict[str, Any]]:
        return list_queue(limit=limit)

    @router.post("/v1/cases/{case_id}/handoff")
    def handoff_route(case_id: str, body: HandoffBody) -> dict[str, Any]:
        try:
            case = handoff(case_id, reason=body.reason, note=body.note)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="case not found") from error
        return case.to_dict()

    @router.post("/v1/cases/{case_id}/actions")
    def case_actions_route(case_id: str, body: CaseActionBody) -> dict[str, Any]:
        try:
            case = get_case(case_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="case not found") from error

        from clarity.modules.actions.public import propose_action

        try:
            proposal = propose_action(
                case_id=case.id,
                action_type=body.action_type,
                subscriber_ref=case.subscriber_ref,
                amount_lkr=body.amount_lkr,
                idempotency_key=body.idempotency_key,
                params=body.params,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

        attach_action(case_id, proposal)
        return {"case": get_case(case_id).to_dict(), "action": proposal}

    return router


class CaseModule:
    name = "case"
    schema = "case"

    def permissions(self) -> list[Permission]:
        return []

    def config_keys(self) -> list[ConfigKey]:
        return [
            ConfigKey("case.queue.age_weight", 2.0, "Hours weight in smart_score"),
        ]

    def register(self, app: AppBuilder) -> None:
        app.routes(_build_router(), prefix="")
