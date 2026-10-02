"""Idempotent tool layer, approvals, compensation."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from clarity.kernel.principal import Permission
from clarity.modules.actions.domain.layer import ToolLayerError
from clarity.modules.actions.public import (
    approve_action,
    confirm_action,
    execute_action,
    propose_action,
)
from clarity.platform.app.module import AppBuilder, ConfigKey


class ProposeBody(BaseModel):
    action_type: str = Field(min_length=1)
    subscriber_ref: str = Field(min_length=1)
    case_id: str | None = None
    amount_lkr: str | None = None
    idempotency_key: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class ConfirmBody(BaseModel):
    action_id: str = Field(min_length=1)
    subscriber_ref: str = Field(min_length=1)


class ApproveBody(BaseModel):
    action_id: str = Field(min_length=1)
    approver_ref: str = Field(min_length=1)


class ExecuteBody(BaseModel):
    action_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    confirmation_token: str | None = None


def _http_for(error: ToolLayerError) -> HTTPException:
    status = {
        "NOT_FOUND": 404,
        "FORBIDDEN": 403,
        "BUDGET_EXHAUSTED": 429,
        "CONFIRMATION_REQUIRED": 409,
        "CONFIRMATION_INVALID": 401,
        "IDEMPOTENCY_CONFLICT": 409,
        "NOT_PENDING": 409,
    }.get(error.code, 400)
    return HTTPException(status_code=status, detail={"code": error.code, "message": str(error)})


def _build_router() -> APIRouter:
    router = APIRouter(tags=["actions"])

    @router.post("/v1/actions/propose")
    def propose_route(body: ProposeBody) -> dict[str, Any]:
        try:
            return propose_action(
                action_type=body.action_type,
                subscriber_ref=body.subscriber_ref,
                case_id=body.case_id,
                amount_lkr=body.amount_lkr,
                idempotency_key=body.idempotency_key,
                params=body.params,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except ToolLayerError as error:
            raise _http_for(error) from error

    @router.post("/v1/actions/confirm")
    def confirm_route(body: ConfirmBody) -> dict[str, Any]:
        try:
            return confirm_action(body.action_id, subscriber_ref=body.subscriber_ref)
        except ToolLayerError as error:
            raise _http_for(error) from error

    @router.post("/v1/actions/approve")
    def approve_route(body: ApproveBody) -> dict[str, Any]:
        try:
            return approve_action(body.action_id, approver_ref=body.approver_ref)
        except ToolLayerError as error:
            raise _http_for(error) from error

    @router.post("/v1/actions/execute")
    def execute_route(body: ExecuteBody) -> dict[str, Any]:
        try:
            return execute_action(
                body.action_id,
                idempotency_key=body.idempotency_key,
                confirmation_token=body.confirmation_token,
            )
        except ToolLayerError as error:
            raise _http_for(error) from error

    return router


class ActionsModule:
    name = "actions"
    schema = "actions"

    def permissions(self) -> list[Permission]:
        return []

    def config_keys(self) -> list[ConfigKey]:
        return [
            ConfigKey("actions.budget.daily_lkr", "250000.00", "Daily refund budget cap"),
        ]

    def register(self, app: AppBuilder) -> None:
        app.routes(_build_router(), prefix="")
