"""Versioned templates and config admin."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from clarity.kernel.principal import Permission
from clarity.modules.content.public import get_flags, get_template, put_template
from clarity.platform.app.module import AppBuilder, ConfigKey


class TemplateBody(BaseModel):
    body: str = Field(min_length=1)
    name: str | None = None
    language: str = "en"
    channel: str = "app"
    created_by: str = "admin"


def _build_router() -> APIRouter:
    router = APIRouter(tags=["content"])

    @router.get("/v1/admin/templates/{template_id}")
    def get_template_route(template_id: str) -> dict[str, Any]:
        try:
            return get_template(template_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="template not found") from error

    @router.put("/v1/admin/templates/{template_id}")
    def put_template_route(template_id: str, body: TemplateBody) -> dict[str, Any]:
        return put_template(
            template_id,
            body=body.body,
            name=body.name,
            language=body.language,
            channel=body.channel,
            created_by=body.created_by,
        )

    @router.get("/v1/admin/flags")
    def flags_route() -> dict[str, Any]:
        return {"flags": get_flags()}

    return router


class ContentModule:
    name = "content"
    schema = "content"

    def permissions(self) -> list[Permission]:
        return []

    def config_keys(self) -> list[ConfigKey]:
        return []

    def register(self, app: AppBuilder) -> None:
        app.routes(_build_router(), prefix="")
