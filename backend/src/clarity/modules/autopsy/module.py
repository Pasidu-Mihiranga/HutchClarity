"""Embeddings, HDBSCAN clusters, flow publish."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from clarity.kernel.principal import Permission
from clarity.modules.autopsy.public import (
    cluster_cases,
    confirm_cluster,
    list_clusters,
    publish_flow,
)
from clarity.platform.app.module import AppBuilder, ConfigKey


class ClusterBody(BaseModel):
    summaries: list[Any] = Field(default_factory=list)
    threshold: float = Field(default=0.55, ge=0.0, le=1.0)


class ConfirmBody(BaseModel):
    publish: bool = False
    flow: dict[str, Any] | None = None


def _build_router() -> APIRouter:
    router = APIRouter(tags=["autopsy"])

    @router.get("/v1/autopsy/clusters")
    def clusters_list() -> dict[str, Any]:
        items = list_clusters()
        return {"clusters": items, "count": len(items)}

    @router.post("/v1/autopsy/cluster")
    def cluster_route(body: ClusterBody) -> dict[str, Any]:
        clusters = cluster_cases(body.summaries, threshold=body.threshold)
        return {"clusters": clusters, "count": len(clusters)}

    @router.post("/v1/autopsy/clusters/{cluster_id}/confirm")
    def confirm_route(cluster_id: str, body: ConfirmBody | None = None) -> dict[str, Any]:
        body = body or ConfirmBody()
        try:
            confirmed = confirm_cluster(cluster_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="cluster not found") from error
        if body.publish:
            try:
                confirmed = publish_flow(cluster_id, flow=body.flow)
            except ValueError as error:
                raise HTTPException(status_code=400, detail=str(error)) from error
        return confirmed

    return router


class AutopsyModule:
    name = "autopsy"
    schema = "autopsy"

    def permissions(self) -> list[Permission]:
        return []

    def config_keys(self) -> list[ConfigKey]:
        return [
            ConfigKey("autopsy.cluster.threshold", 0.55, "Cosine threshold for agglomeration"),
        ]

    def register(self, app: AppBuilder) -> None:
        app.routes(_build_router(), prefix="")
