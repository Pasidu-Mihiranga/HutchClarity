"""Complaint embedding and simple bag-of-words clustering."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from clarity.kernel.ids import new_id
from clarity.modules.knowledge.domain.rag import cosine, hash_embed, tokenize


@dataclass(slots=True)
class Cluster:
    id: str
    label: str
    member_ids: list[str] = field(default_factory=list)
    summaries: list[str] = field(default_factory=list)
    centroid: list[float] = field(default_factory=list)
    status: str = "proposed"  # proposed | confirmed | published
    flow_draft: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "member_ids": list(self.member_ids),
            "summaries": list(self.summaries),
            "size": len(self.member_ids),
            "status": self.status,
            "flow_draft": self.flow_draft,
        }


def _label_from_texts(texts: list[str]) -> str:
    counts: dict[str, int] = defaultdict(int)
    stop = {"the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "is", "was", "my", "i"}
    for text in texts:
        for tok in tokenize(text):
            if tok in stop or len(tok) < 3:
                continue
            counts[tok] += 1
    if not counts:
        return "unlabelled"
    top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
    return " ".join(t for t, _ in top)


def agglomerative_cluster(
    items: list[tuple[str, str]],
    *,
    threshold: float = 0.55,
) -> list[Cluster]:
    """Greedy agglomerative grouping by embedding cosine (HDBSCAN-like stand-in)."""
    if not items:
        return []
    vectors = [(iid, text, hash_embed(text)) for iid, text in items]
    assigned = [-1] * len(vectors)
    clusters: list[Cluster] = []

    for i, (iid, text, vec) in enumerate(vectors):
        best_j = -1
        best_sim = threshold
        for j, cluster in enumerate(clusters):
            sim = cosine(vec, cluster.centroid)
            if sim >= best_sim:
                best_sim = sim
                best_j = j
        if best_j < 0:
            cluster = Cluster(
                id=new_id("CLU"),
                label="",
                member_ids=[iid],
                summaries=[text],
                centroid=list(vec),
            )
            clusters.append(cluster)
            assigned[i] = len(clusters) - 1
        else:
            cluster = clusters[best_j]
            n = len(cluster.member_ids)
            # running mean centroid
            cluster.centroid = [
                (c * n + v) / (n + 1) for c, v in zip(cluster.centroid, vec, strict=True)
            ]
            # re-normalise
            norm = math.sqrt(sum(x * x for x in cluster.centroid)) or 1.0
            cluster.centroid = [x / norm for x in cluster.centroid]
            cluster.member_ids.append(iid)
            cluster.summaries.append(text)
            assigned[i] = best_j

    for cluster in clusters:
        cluster.label = _label_from_texts(cluster.summaries)
    return clusters


class ClusterStore:
    def __init__(self) -> None:
        self._clusters: dict[str, Cluster] = {}

    def put_many(self, clusters: list[Cluster]) -> list[Cluster]:
        for cluster in clusters:
            self._clusters[cluster.id] = cluster
        return clusters

    def get(self, cluster_id: str) -> Cluster | None:
        return self._clusters.get(cluster_id)

    def all(self) -> list[Cluster]:
        return list(self._clusters.values())

    def clear(self) -> None:
        self._clusters.clear()
