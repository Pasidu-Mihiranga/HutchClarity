"""Hybrid BM25+pgvector RAG with citations."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from clarity.kernel.principal import Permission
from clarity.modules.knowledge.public import get_article, search
from clarity.platform.app.module import AppBuilder, ConfigKey


class SearchBody(BaseModel):
    query: str = Field(min_length=1)
    lang: str = "en"
    limit: int = Field(default=5, ge=1, le=20)


def _build_router() -> APIRouter:
    router = APIRouter(tags=["knowledge"])

    @router.post("/v1/knowledge/search")
    def search_route(body: SearchBody) -> dict[str, Any]:
        try:
            return search(body.query, lang=body.lang, limit=body.limit)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.get("/v1/knowledge/articles/{article_id}")
    def article_route(article_id: str) -> dict[str, Any]:
        try:
            return get_article(article_id).to_dict()
        except KeyError as error:
            raise HTTPException(status_code=404, detail="article not found") from error

    return router


class KnowledgeModule:
    name = "knowledge"
    schema = "knowledge"

    def permissions(self) -> list[Permission]:
        return []

    def config_keys(self) -> list[ConfigKey]:
        return [
            ConfigKey("knowledge.rag.alpha", 0.55, "Lexical weight in hybrid search"),
        ]

    def register(self, app: AppBuilder) -> None:
        app.routes(_build_router(), prefix="")
