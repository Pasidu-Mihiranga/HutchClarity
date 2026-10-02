"""In-memory knowledge corpus with versioned pack labels."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Article:
    id: str
    title: str
    body: str
    labels: list[str] = field(default_factory=list)
    pack_version: str = "1.0"
    language: str = "en"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "body": self.body,
            "labels": list(self.labels),
            "pack_version": self.pack_version,
            "language": self.language,
        }


SEED_ARTICLES: list[Article] = [
    Article(
        id="KB-VAS",
        title="Manage subscriptions (VAS)",
        body=(
            "Paid daily or monthly services (games, news, tones) appear under "
            "Subscriptions. You can cancel any active one there. Hutch must hold OTP "
            "or second-confirmation evidence for a VAS charge. If you see a charge "
            "you never confirmed, ask Clarity to check this number."
        ),
        labels=["vas", "subscription", "otp", "cancel"],
        pack_version="2026.10",
    ),
    Article(
        id="KB-FUP",
        title="What fair-use (FUP) means",
        body=(
            "Unlimited and large data packs include a fair-use cap shown at purchase. "
            "After you use that volume, speed drops to the stated rate — data is not "
            "cut off. The cap and after-cap speed are on the pack screen before you buy. "
            "Alerts at 80% and 95% help you plan before throttling starts."
        ),
        labels=["fup", "fair-use", "cap", "throttle", "unlimited"],
        pack_version="2026.10",
    ),
    Article(
        id="KB-PACKS",
        title="Activate and understand data packs",
        body=(
            "Open Packages in the Hutch app, choose Anytime, Unlimited, Social, Work "
            "or Combo, and confirm the price will debit your main balance. Wait for "
            "the confirmation SMS. Packs show under Usage. If activation fails, your "
            "balance is not kept for that attempt. Social packs only cover listed apps."
        ),
        labels=["pack", "activate", "anytime", "social", "data"],
        pack_version="2026.10",
    ),
    Article(
        id="KB-LOANS",
        title="Airtime and data loans",
        body=(
            "Emergency loans appear as a temporary credit that recovers from the next "
            "reload. Only one active loan is allowed at a time unless a stacking "
            "exception is approved. Recovery fees are shown before you accept. Ask "
            "Clarity if two loans appeared on the same day."
        ),
        labels=["loan", "recovery", "reload", "airtime", "stacking"],
        pack_version="2026.10",
    ),
    Article(
        id="KB-OUTAGE-CREDIT",
        title="Outage credit during an active pack",
        body=(
            "When a confirmed network outage overlaps an active data pack, Clarity can "
            "propose a credit based on outage duration and pack remaining value. Keep "
            "the outage ticket or SMS for evidence. Credits are not automatic for "
            "planned maintenance windows disclosed in advance."
        ),
        labels=["outage", "credit", "network", "pack", "compensation"],
        pack_version="2026.10",
    ),
]


class Corpus:
    """Simple article store keyed by id."""

    def __init__(self, articles: list[Article] | None = None) -> None:
        self._articles: dict[str, Article] = {}
        for article in articles or list(SEED_ARTICLES):
            self.put(article)

    def put(self, article: Article) -> Article:
        self._articles[article.id] = article
        return article

    def get(self, article_id: str) -> Article | None:
        return self._articles.get(article_id)

    def all(self, *, lang: str | None = None) -> list[Article]:
        items = list(self._articles.values())
        if lang:
            items = [a for a in items if a.language == lang]
        return items

    def clear(self) -> None:
        self._articles.clear()

    def reset_seed(self) -> None:
        self.clear()
        for article in SEED_ARTICLES:
            self.put(article)
