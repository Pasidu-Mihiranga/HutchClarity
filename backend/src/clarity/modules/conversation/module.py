"""Intake extract, language ID, handoff, composition, suggestions."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field

from clarity.kernel.principal import Permission
from clarity.modules.conversation.public import handle_turn, suggest_for_snapshot
from clarity.platform.app.module import AppBuilder, ConfigKey


class TurnBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    case_id: str | None = None
    facts: dict[str, Any] = Field(default_factory=dict)
    language: str | None = None
    intent: str | None = None
    snapshot: dict[str, Any] = Field(default_factory=dict)


class SuggestionsBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot: dict[str, Any] = Field(default_factory=dict)
    language: str = "en"
    limit: int = Field(default=6, ge=1, le=10)


def _build_router() -> APIRouter:
    router = APIRouter(tags=["conversation"])

    @router.post("/v1/conversation/turn")
    def turn_route(body: TurnBody) -> dict[str, Any]:
        result = handle_turn(
            body.text,
            case_id=body.case_id,
            facts=body.facts,
            language_hint=body.language,
            intent_override=body.intent,
        )
        return {"turn": result.to_dict()}

    @router.post("/v1/conversation/suggestions")
    def suggestions_post(body: SuggestionsBody) -> dict[str, Any]:
        return suggest_for_snapshot(body.snapshot, language=body.language, limit=body.limit)

    @router.get("/v1/conversation/suggestions")
    def suggestions_get(
        language: str = Query(default="en"),
        limit: int = Query(default=6, ge=1, le=10),
        fup_pct: float | None = None,
        unusual_vas: bool = False,
        vas_amount_lkr: str | None = None,
        pack_expires_hours: float | None = None,
        double_charge: bool = False,
        reload_missing: bool = False,
        open_case: bool = False,
    ) -> dict[str, Any]:
        snapshot: dict[str, Any] = {
            "pack": {},
            "subscriptions": [],
            "activity": [],
        }
        if fup_pct is not None:
            snapshot["pack"]["used_pct"] = fup_pct
        if pack_expires_hours is not None:
            snapshot["pack"]["expires_in_hours"] = pack_expires_hours
        if unusual_vas:
            snapshot["subscriptions"] = [{"active": True, "consent": False, "name": "VAS"}]
            if vas_amount_lkr:
                snapshot["activity"] = [
                    {"type": "vas_charge", "amount_lkr": vas_amount_lkr, "detail": "VAS"}
                ]
        if double_charge:
            snapshot["activity"].extend(
                [
                    {"type": "payment_captured", "amount_lkr": "100.00"},
                    {"type": "payment_captured", "amount_lkr": "100.00"},
                ]
            )
        if reload_missing:
            snapshot["activity"].append({"type": "payment_captured", "amount_lkr": "50.00"})
        if open_case:
            snapshot["open_case"] = True
        return suggest_for_snapshot(snapshot, language=language, limit=limit)

    return router


class ConversationModule:
    name = "conversation"
    schema = "conversation"

    def permissions(self) -> list[Permission]:
        return []

    def config_keys(self) -> list[ConfigKey]:
        return [
            ConfigKey("conversation.handoff.confidence_floor", 0.4, "Clarify below this score"),
            ConfigKey("conversation.suggestions.limit", 6, "Max primary suggestion chips"),
        ]

    def register(self, app: AppBuilder) -> None:
        app.routes(_build_router(), prefix="")
