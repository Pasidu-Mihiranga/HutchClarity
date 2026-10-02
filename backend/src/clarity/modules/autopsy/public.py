"""Public facade for the autopsy module."""

from __future__ import annotations

from typing import Any

from clarity.modules.autopsy.domain.cluster import Cluster, ClusterStore, agglomerative_cluster

_store = ClusterStore()


def reset_autopsy() -> None:
    _store.clear()


def cluster_cases(
    summaries: list[dict[str, Any]] | list[str],
    *,
    threshold: float = 0.55,
) -> list[dict[str, Any]]:
    """Embed case summaries and group by similar bag-of-words vectors."""
    items: list[tuple[str, str]] = []
    for idx, item in enumerate(summaries):
        if isinstance(item, str):
            items.append((f"case-{idx}", item))
        elif isinstance(item, dict):
            cid = str(item.get("id") or item.get("case_id") or f"case-{idx}")
            text = str(item.get("summary") or item.get("text") or "")
            if text:
                items.append((cid, text))
    clusters = agglomerative_cluster(items, threshold=threshold)
    _store.put_many(clusters)
    return [c.to_dict() for c in clusters]


def list_clusters() -> list[dict[str, Any]]:
    return [c.to_dict() for c in _store.all()]


def confirm_cluster(cluster_id: str) -> dict[str, Any]:
    cluster = _store.get(cluster_id)
    if cluster is None:
        raise KeyError(cluster_id)
    cluster.status = "confirmed"
    return cluster.to_dict()


def publish_flow(cluster_id: str, *, flow: dict[str, Any] | None = None) -> dict[str, Any]:
    cluster = _store.get(cluster_id)
    if cluster is None:
        raise KeyError(cluster_id)
    if cluster.status not in {"confirmed", "published"}:
        raise ValueError("cluster must be confirmed before publish")
    cluster.flow_draft = flow or {
        "name": f"flow_{cluster.label.replace(' ', '_')}",
        "entry": "complaint_intake",
        "steps": ["detect", "decide", "notify"],
        "cluster_id": cluster.id,
    }
    cluster.status = "published"
    return cluster.to_dict()


__all__ = [
    "Cluster",
    "cluster_cases",
    "confirm_cluster",
    "list_clusters",
    "publish_flow",
    "reset_autopsy",
]
