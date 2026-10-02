"""Teach once, golden runs, four-eyes publish."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from clarity.kernel.principal import Permission
from clarity.modules.governance.public import publish, replay, teach
from clarity.platform.app.module import AppBuilder, ConfigKey


class ReplayBody(BaseModel):
    timeline: dict[str, Any] = Field(default_factory=dict)
    proposal: dict[str, Any] | None = None


class TeachBody(BaseModel):
    case_summary: str = Field(min_length=1)
    expected_cause: str = Field(min_length=1)
    expected_outcome: str = Field(min_length=1)
    notes: str = ""


class PublishBody(BaseModel):
    proposal: dict[str, Any] = Field(default_factory=dict)
    change_class: str = "C1"
    approver_a: str = Field(min_length=1)
    approver_b: str | None = None


def _build_router() -> APIRouter:
    router = APIRouter(tags=["governance"])

    @router.post("/v1/policy/replays")
    def replay_route(body: ReplayBody) -> dict[str, Any]:
        return replay(timeline=body.timeline, proposal=body.proposal)

    @router.post("/v1/policy/teach")
    def teach_route(body: TeachBody) -> dict[str, Any]:
        return teach(
            case_summary=body.case_summary,
            expected_cause=body.expected_cause,
            expected_outcome=body.expected_outcome,
            notes=body.notes,
        )

    @router.post("/v1/policy/publish")
    def publish_route(body: PublishBody) -> dict[str, Any]:
        try:
            return publish(
                proposal=body.proposal,
                change_class=body.change_class,
                approver_a=body.approver_a,
                approver_b=body.approver_b,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    return router


class GovernanceModule:
    name = "governance"
    schema = "governance"

    def permissions(self) -> list[Permission]:
        return []

    def config_keys(self) -> list[ConfigKey]:
        return []

    def register(self, app: AppBuilder) -> None:
        app.routes(_build_router(), prefix="")
