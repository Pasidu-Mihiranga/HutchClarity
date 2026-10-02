"""Customer profile and safeguards."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from clarity.kernel.common import Language
from clarity.kernel.principal import Permission
from clarity.modules.customer.public import get_safeguards, put_safeguards
from clarity.platform.app.module import AppBuilder, ConfigKey


class SafeguardsBody(BaseModel):
    spend_cap_lkr: str | None = None
    quiet_hours: dict[str, Any] | None = None
    language: str | None = Field(default=None)
    allow_auto_refund: bool | None = None


def _subscriber_from_header(x_subscriber_ref: str | None) -> str:
    """Lite principal: subscriber ref arrives on X-Subscriber-Ref."""
    if not x_subscriber_ref or not x_subscriber_ref.strip():
        raise HTTPException(status_code=401, detail="X-Subscriber-Ref required")
    return x_subscriber_ref.strip()


def _build_router() -> APIRouter:
    router = APIRouter(tags=["customer"])

    @router.get("/v1/customers/me/safeguards")
    def get_me_safeguards(
        x_subscriber_ref: str | None = Header(default=None, alias="X-Subscriber-Ref"),
    ) -> dict[str, Any]:
        ref = _subscriber_from_header(x_subscriber_ref)
        return get_safeguards(ref).to_dict()

    @router.put("/v1/customers/me/safeguards")
    def put_me_safeguards(
        body: SafeguardsBody,
        x_subscriber_ref: str | None = Header(default=None, alias="X-Subscriber-Ref"),
    ) -> dict[str, Any]:
        ref = _subscriber_from_header(x_subscriber_ref)
        if body.language is not None:
            try:
                Language(body.language)
            except ValueError as error:
                raise HTTPException(status_code=400, detail=f"unknown language: {error}") from error
        try:
            updated = put_safeguards(
                ref,
                spend_cap_lkr=body.spend_cap_lkr,
                quiet_hours=body.quiet_hours,
                language=body.language,
                allow_auto_refund=body.allow_auto_refund,
            )
        except (ValueError, TypeError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return updated.to_dict()

    return router


class CustomerModule:
    name = "customer"
    schema = "customer"

    def permissions(self) -> list[Permission]:
        return []

    def config_keys(self) -> list[ConfigKey]:
        return [
            ConfigKey("customer.safeguards.default_spend_cap_lkr", "0.00", "Default spend cap"),
        ]

    def register(self, app: AppBuilder) -> None:
        app.routes(_build_router(), prefix="")
