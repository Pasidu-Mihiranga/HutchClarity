"""Intake extract, language ID, handoff, composition."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from clarity.kernel.principal import Permission
from clarity.modules.conversation.public import handle_turn
from clarity.platform.app.module import AppBuilder, ConfigKey


class TurnBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    case_id: str | None = None
    facts: dict[str, Any] = Field(default_factory=dict)
    language: str | None = None


def _build_router() -> APIRouter:
    router = APIRouter(tags=["conversation"])

    @router.post("/v1/conversation/turn")
    def turn_route(body: TurnBody) -> dict[str, Any]:
        result = handle_turn(
            body.text,
            case_id=body.case_id,
            facts=body.facts,
            language_hint=body.language,
        )
        return {"turn": result.to_dict()}

    return router


class ConversationModule:
    name = "conversation"
    schema = "conversation"

    def permissions(self) -> list[Permission]:
        return []

    def config_keys(self) -> list[ConfigKey]:
        return [
            ConfigKey("conversation.handoff.confidence_floor", 0.4, "Clarify below this score"),
        ]

    def register(self, app: AppBuilder) -> None:
        app.routes(_build_router(), prefix="")
