"""Publishing the simulated help articles into the knowledge registry (K03).

The composition root's job, not the module's. `clarity.modules.knowledge` has
no opinion about what is in the corpus and must not: a module that ships its own
content is a module whose content nobody reviews.

**Why these articles and nothing invented.** The five entries in
`clarity.integration.drivers.mock.store.knowledge` already exist in the
repository and are already served to customers by `/v1/knowledge/search`. K03
moves that route onto this module (issue #33), so the same content has to be
reachable through the registry or the route would regress to answering nothing.
Publishing what is already there invents no HUTCH policy, which writing a T&C
corpus would (I16).

They are labelled on the way in. The owner is `hutch-sim`, which is the
repository's word for a simulated HUTCH system, so every chunk and every
citation produced from them carries that provenance.

**REQUIRES HUTCH CONFIRMATION** for the real corpus: catalogue, T&C, Gazette
2316/14 and CX-approved answers, each with its own owner and effective date,
published through the governance lifecycle (plan 20, kind K2).
"""

from __future__ import annotations

from datetime import UTC, datetime

from clarity.kernel.common import Language
from clarity.modules.knowledge.public import (
    Audience,
    KnowledgeRegistry,
    KnowledgeSource,
    SourceKind,
)

#: The owner recorded against every seeded source. Not a real team: it is the
#: repository's label for a simulated HUTCH system, so a citation produced from
#: this content says so.
SEED_OWNER = "hutch-sim"

#: When the seeded articles take effect. Deliberately far back, so they are in
#: force for any moment a demo or a test asks about, including a dispute about
#: a charge from last year.
SEED_EFFECTIVE_FROM = datetime(2024, 1, 1, tzinfo=UTC)


def seed_help_articles(registry: KnowledgeRegistry) -> int:
    """Publish the simulated help articles. Returns how many were published.

    Idempotent by refusal: the registry rejects a `(source_id, version)` it
    already holds, so calling this twice on a shared store is not an error and
    does not duplicate anything.
    """
    from clarity.integration.drivers.mock.store.knowledge import KNOWLEDGE_ARTICLES

    published = 0
    for article in KNOWLEDGE_ARTICLES:
        source = KnowledgeSource(
            source_id=str(article["article_id"]),
            version=1,
            title=str(article["title"]),
            kind=SourceKind.HELP_ARTICLE,
            owner=SEED_OWNER,
            audience=Audience.CUSTOMER,
            language=Language(str(article.get("language") or "en")),
            body=str(article["body"]),
            effective_from=SEED_EFFECTIVE_FROM,
        )
        try:
            registry.publish(source)
        except ValueError:
            # Already published, or refused by a validator. Either way this is
            # not the place to decide what to do about it: the registry's
            # refusal is the authority and a seed must not override one.
            continue
        published += 1
    return published


__all__ = ["SEED_EFFECTIVE_FROM", "SEED_OWNER", "seed_help_articles"]
