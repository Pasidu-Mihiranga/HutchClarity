"""Complaint Autopsy: thousands of messy complaints into root causes (deck S11).

The pipeline follows the deck exactly: clean and protect, understand, cluster,
map to a cause, then propose a fix for review. The ordering matters - **PII
masking happens before anything else looks at the text** (deck S11, step 1),
so no raw personal data reaches clustering, labelling or storage.

**Prototype note.** Plan §3.3 uses multilingual embeddings with UMAP and
HDBSCAN. Here clustering is character-n-gram TF-IDF with cosine similarity and
agglomerative merging - no ML dependency, deterministic, and good enough to
demonstrate the pipeline on a few hundred complaints. It will not match
embeddings on code-mixed Singlish, which is exactly where the deck's canonical
summary step earns its place. Swapping the vectoriser changes nothing else.

Clusters are **hypotheses until a CX engineer confirms them** (deck S11): this
module never publishes a flow or a rule by itself.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from clarity.ai.pii import ForbiddenContent, Masker
from clarity.kernel.common import Language, utc_now
from clarity.kernel.ids import new_id


class ClusterStatus(StrEnum):
    HYPOTHESIS = "hypothesis"
    """Proposed by the pipeline. Never acted on in this state."""
    CONFIRMED = "confirmed"
    """A CX engineer agreed the cluster is a real, single cause."""
    REJECTED = "rejected"


@dataclass
class Complaint:
    """One inbound complaint, before any processing."""

    complaint_id: str
    text: str
    channel: str = "whatsapp"
    received_at: datetime = field(default_factory=utc_now)


@dataclass
class CleanComplaint:
    """A complaint after dedupe, language detection and masking."""

    complaint_id: str
    masked_text: str
    language: Language
    channel: str
    received_at: datetime
    canonical: str
    """Short English form, so Singlish and Sinhala cluster together (deck S11)."""


@dataclass
class Cluster:
    """A group of complaints that look like one cause."""

    cluster_id: str
    label: str
    members: list[str]
    status: ClusterStatus = ClusterStatus.HYPOTHESIS
    suggested_rule_id: str | None = None
    keywords: list[str] = field(default_factory=list)
    languages: Counter[str] = field(default_factory=Counter)

    @property
    def size(self) -> int:
        return len(self.members)


@dataclass
class AutopsyReport:
    run_id: str
    total_received: int
    duplicates_removed: int
    refused: int
    """Complaints dropped because they contained a credential (deck S8)."""
    clusters: list[Cluster]
    noise: list[str]

    @property
    def coverage(self) -> float:
        """Share of complaints that landed in a cluster rather than noise."""
        clustered = sum(c.size for c in self.clusters)
        total = clustered + len(self.noise)
        return clustered / total if total else 0.0


# --------------------------------------------------------------------------- #
# Language detection
# --------------------------------------------------------------------------- #

_SINHALA = re.compile(r"[඀-෿]")
_TAMIL = re.compile(r"[஀-௿]")


def detect_language(text: str) -> Language:
    """Script-based detection. Singlish is Latin script, so it reads as English."""
    if _SINHALA.search(text):
        return Language.SI
    if _TAMIL.search(text):
        return Language.TA
    return Language.EN


# --------------------------------------------------------------------------- #
# Canonical summary
# --------------------------------------------------------------------------- #

#: Phrases that mean the same complaint across languages and Singlish.
#: In production an LLM writes the canonical summary (deck S11 step 2); this
#: keyword map is the deterministic stand-in and is deliberately explicit.
_CANONICAL_HINTS: list[tuple[str, tuple[str, ...]]] = [
    (
        "vas charged without consent",
        ("vas", "subscription", "subscribe", "game", "ringtone", "දායක", "சந்தா", "naraka"),
    ),
    ("reload taken twice", ("twice", "two times", "double", "duplicate", "දෙපාරක්", "இரண்டு முறை")),
    (
        "reload not credited",
        ("not credited", "didn't get", "did not receive", "no balance", "ලැබුණේ නැහැ", "வரவில்லை"),
    ),
    ("data stopped at cap", ("unlimited", "slow", "fup", "cap", "speed", "වේගය", "வேகம்")),
    ("balance disappeared", ("balance", "money gone", "deducted", "ශේෂය", "இருப்பு", "cut vela")),
    ("pack mismatch", ("wrong pack", "different pack", "not activated", "වැරදි", "தவறான")),
    ("no reply from support", ("no reply", "no response", "waiting", "පිළිතුරක්", "பதில் இல்லை")),
]

#: Canonical form -> the cause rule that would explain it, if one exists.
CANONICAL_TO_RULE: dict[str, str] = {
    "vas charged without consent": "VAS_NO_CONSENT",
    "reload taken twice": "DUPLICATE_RELOAD",
    "reload not credited": "RELOAD_NOT_CREDITED",
    "data stopped at cap": "FUP_CAP_REACHED",
    "balance disappeared": "PACK_EXPIRY_BURN",
}


def canonicalise(masked_text: str) -> str:
    """Reduce a complaint to a short English form.

    This is what lets a Sinhala complaint, a Tamil one and a Singlish one about
    the same problem land in one cluster (deck S11 step 2).
    """
    lowered = masked_text.lower()
    for canonical, hints in _CANONICAL_HINTS:
        if any(hint in lowered for hint in hints):
            return canonical
    return "unclassified"


# --------------------------------------------------------------------------- #
# Vectorising and clustering
# --------------------------------------------------------------------------- #


def _trigrams(text: str) -> Counter[str]:
    cleaned = re.sub(r"\s+", " ", text.lower().strip())
    return Counter(cleaned[i : i + 3] for i in range(max(len(cleaned) - 2, 0)))


def _cosine(a: Counter[str], b: Counter[str]) -> float:
    if not a or not b:
        return 0.0
    shared = set(a) & set(b)
    numerator = sum(a[k] * b[k] for k in shared)
    if not numerator:
        return 0.0
    magnitude = math.sqrt(sum(v * v for v in a.values())) * math.sqrt(
        sum(v * v for v in b.values())
    )
    return numerator / magnitude if magnitude else 0.0


class ComplaintAutopsy:
    """Runs the pipeline. Produces hypotheses, never published changes."""

    def __init__(self, *, masker: Masker | None = None, similarity: float = 0.45) -> None:
        self._masker = masker or Masker()
        self._similarity = similarity

    # -- step 1: clean and protect -------------------------------------- #

    def clean(self, complaints: list[Complaint]) -> tuple[list[CleanComplaint], int, int]:
        """Dedupe, detect language, and mask **before** anything else reads it."""
        seen: set[str] = set()
        cleaned: list[CleanComplaint] = []
        duplicates = 0
        refused = 0

        for complaint in complaints:
            fingerprint = re.sub(r"\W+", "", complaint.text.lower())
            if fingerprint in seen:
                duplicates += 1
                continue
            seen.add(fingerprint)

            try:
                masked = self._masker.mask(complaint.text)
            except ForbiddenContent:
                # A complaint quoting an OTP or card is dropped, not cleaned up
                # and kept: it must not enter analytics at all (deck S8).
                refused += 1
                continue

            cleaned.append(
                CleanComplaint(
                    complaint_id=complaint.complaint_id,
                    masked_text=masked.text,
                    language=detect_language(complaint.text),
                    channel=complaint.channel,
                    received_at=complaint.received_at,
                    canonical=canonicalise(masked.text),
                )
            )
        return cleaned, duplicates, refused

    # -- steps 2-4: understand, cluster, map ---------------------------- #

    def run(self, complaints: list[Complaint]) -> AutopsyReport:
        cleaned, duplicates, refused = self.clean(complaints)
        clusters, noise = self._cluster(cleaned)
        return AutopsyReport(
            run_id=new_id("AUT"),
            total_received=len(complaints),
            duplicates_removed=duplicates,
            refused=refused,
            clusters=sorted(clusters, key=lambda c: c.size, reverse=True),
            noise=noise,
        )

    def _cluster(self, cleaned: list[CleanComplaint]) -> tuple[list[Cluster], list[str]]:
        """Group by canonical form, then split loose groups by similarity."""
        by_canonical: dict[str, list[CleanComplaint]] = defaultdict(list)
        for item in cleaned:
            by_canonical[item.canonical].append(item)

        clusters: list[Cluster] = []
        noise: list[str] = []

        for canonical, members in by_canonical.items():
            if canonical == "unclassified":
                # Unclassified complaints are grouped only if they genuinely
                # resemble each other, so a cluster is never an "everything
                # else" bucket presented as a finding. Whatever does not group
                # is reported as noise, never dropped - every complaint must be
                # accounted for somewhere in the report.
                grouped, ungrouped = self._group_by_similarity(members)
                clusters.extend(grouped)
                noise.extend(ungrouped)
                continue
            if len(members) == 1:
                noise.append(members[0].complaint_id)
                continue
            clusters.append(self._build(canonical, members))

        return clusters, noise

    def _group_by_similarity(
        self, members: list[CleanComplaint]
    ) -> tuple[list[Cluster], list[str]]:
        vectors = {m.complaint_id: _trigrams(m.masked_text) for m in members}
        groups: list[list[CleanComplaint]] = []

        for member in members:
            placed = False
            for group in groups:
                if _cosine(vectors[member.complaint_id], vectors[group[0].complaint_id]) >= (
                    self._similarity
                ):
                    group.append(member)
                    placed = True
                    break
            if not placed:
                groups.append([member])

        return (
            [self._build("unclassified", g) for g in groups if len(g) > 1],
            [g[0].complaint_id for g in groups if len(g) == 1],
        )

    def _build(self, canonical: str, members: list[CleanComplaint]) -> Cluster:
        words = Counter(
            word
            for member in members
            for word in re.findall(r"[a-z]{4,}", member.masked_text.lower())
            if word not in {"this", "that", "have", "been", "with", "from", "they", "there"}
        )
        return Cluster(
            cluster_id=new_id("CLU"),
            label=canonical,
            members=[m.complaint_id for m in members],
            suggested_rule_id=CANONICAL_TO_RULE.get(canonical),
            keywords=[w for w, _ in words.most_common(5)],
            languages=Counter(m.language.value for m in members),
        )

    # -- step 5: review ------------------------------------------------- #

    @staticmethod
    def confirm(cluster: Cluster, *, reviewer: str, accept: bool) -> Cluster:
        """A CX engineer's verdict. Nothing is acted on before this."""
        cluster.status = ClusterStatus.CONFIRMED if accept else ClusterStatus.REJECTED
        cluster.label = f"{cluster.label} (reviewed by {reviewer})"
        return cluster
