"""Audience: a staff SOP is never shown to a customer (K01 #31, acceptance 2).

Plan 22 section 7 makes staff SOPs staff-audience only. This is the one
knowledge filter whose failure is a disclosure rather than a wrong answer: an
internal procedure quoted back to a customer may name thresholds, fraud
heuristics or escalation paths that exist precisely because customers do not
see them.

So the filter is deny by default (I9), in three independent places, and each
one has a test below:

1. ``Audience.may_read`` is asymmetric: customer readers cannot read staff
   content, and there is no "unknown" audience that could slip through.
2. ``chunks_as_of`` requires the audience argument, so no call forgets it.
3. ``SourceKind.STAFF_SOP`` cannot be published as customer audience at all,
   so a mistyped audience on an SOP is refused at publication.
"""

from __future__ import annotations

import inspect
from datetime import UTC, datetime

import pytest

from clarity.kernel.common import Language
from clarity.modules.knowledge.public import (
    Audience,
    KnowledgeRegistry,
    KnowledgeSource,
    SourceKind,
)
from clarity.platform.persistence import MemoryStore, MemoryUnitOfWork

TODAY = datetime(2026, 10, 3, tzinfo=UTC)
LAST_YEAR = datetime(2025, 1, 1, tzinfo=UTC)

SOP_TEXT = (
    "When a refund exceeds LKR 10000, escalate to the duty manager before approving. "
    "Do not disclose the threshold to the customer."
)
ARTICLE_TEXT = "Refunds are credited to your account within three working days."


@pytest.fixture
def registry() -> KnowledgeRegistry:
    store = MemoryStore()

    def open_unit() -> MemoryUnitOfWork:
        return MemoryUnitOfWork(store)

    registry = KnowledgeRegistry(open_unit=open_unit, clock=lambda: TODAY)
    registry.publish(
        KnowledgeSource(
            source_id="SOP-REFUND-ESCALATION",
            version=1,
            title="Refund escalation procedure",
            kind=SourceKind.STAFF_SOP,
            owner="cx-operations",
            audience=Audience.STAFF,
            language=Language.EN,
            body=SOP_TEXT,
            effective_from=LAST_YEAR,
        )
    )
    registry.publish(
        KnowledgeSource(
            source_id="HELP-REFUND-TIMING",
            version=1,
            title="When will I get my refund",
            kind=SourceKind.HELP_ARTICLE,
            owner="cx-knowledge",
            audience=Audience.CUSTOMER,
            language=Language.EN,
            body=ARTICLE_TEXT,
            effective_from=LAST_YEAR,
        )
    )
    return registry


def test_a_staff_sop_is_never_retrieved_for_a_customer(registry) -> None:
    """Acceptance 2. The assertion is on the corpus, not on a ranking.

    Everything in force is returned by `chunks_as_of`, so if the SOP were
    readable it would be in this list whatever a later score did to it. That is
    the point of filtering before ranking: a disclosure must not depend on a
    relevance threshold.
    """
    visible = registry.chunks_as_of(TODAY, audience=Audience.CUSTOMER)

    assert [chunk.source_id for chunk in visible] == ["HELP-REFUND-TIMING"]
    assert all(chunk.audience is Audience.CUSTOMER for chunk in visible)
    assert not any("duty manager" in chunk.text for chunk in visible)
    assert not any("10000" in chunk.text for chunk in visible)


def test_a_staff_reader_sees_both(registry) -> None:
    """The other half: an agent needs the SOP and the article.

    Without this the filter could be "return nothing", which would pass the
    test above and make the module useless.
    """
    visible = registry.chunks_as_of(TODAY, audience=Audience.STAFF)

    assert sorted(chunk.source_id for chunk in visible) == [
        "HELP-REFUND-TIMING",
        "SOP-REFUND-ESCALATION",
    ]


def test_the_audience_rule_is_asymmetric() -> None:
    """Customer content is for everyone; staff content is not."""
    assert Audience.STAFF.may_read(Audience.CUSTOMER)
    assert Audience.STAFF.may_read(Audience.STAFF)
    assert Audience.CUSTOMER.may_read(Audience.CUSTOMER)
    assert not Audience.CUSTOMER.may_read(Audience.STAFF)


def test_retrieval_cannot_be_called_without_naming_an_audience() -> None:
    """Deny by default, enforced by the signature rather than by a default.

    An `audience: Audience = Audience.CUSTOMER` default would be the safe
    direction and still wrong: the caller that should have passed STAFF gets
    silently wrong results, and the caller that forgot entirely is never found.
    Keyword-only with no default makes both a loud error.
    """
    parameter = inspect.signature(KnowledgeRegistry.chunks_as_of).parameters["audience"]

    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default is inspect.Parameter.empty


def test_an_sop_cannot_be_published_as_customer_facing() -> None:
    """A mistyped audience on an SOP is refused at publication.

    Plan 22 section 7 makes SOPs staff-only, which is a property of the kind
    and not a per-source choice. Catching it here means the corpus cannot
    contain a customer-audience SOP for a filter to get right later.
    """
    with pytest.raises(ValueError, match="staff audience"):
        KnowledgeSource(
            source_id="SOP-LEAK",
            version=1,
            title="Procedure",
            kind=SourceKind.STAFF_SOP,
            owner="cx-operations",
            audience=Audience.CUSTOMER,
            language=Language.EN,
            body=SOP_TEXT,
            effective_from=LAST_YEAR,
        )


def test_every_chunk_carries_its_own_audience(registry) -> None:
    """The filter reads the chunk, never a join back to the source.

    A filter that has to look up another record to decide is a filter that gets
    skipped when the lookup is inconvenient, and it also stops being truthful
    about the version it came from once a successor is published.
    """
    for chunk in registry.chunks_as_of(TODAY, audience=Audience.STAFF):
        assert chunk.audience in set(Audience)
        assert chunk.owner
        assert chunk.effective_from == LAST_YEAR


def test_an_expired_staff_sop_is_not_readable_by_anyone(registry) -> None:
    """Audience and effective date are independent filters, both applied."""
    registry.supersede(
        KnowledgeSource(
            source_id="SOP-REFUND-ESCALATION",
            version=2,
            title="Refund escalation procedure",
            kind=SourceKind.STAFF_SOP,
            owner="cx-operations",
            audience=Audience.STAFF,
            language=Language.EN,
            body="Escalate every refund to the duty manager.",
            effective_from=TODAY,
        )
    )

    before = registry.chunks_as_of(LAST_YEAR, audience=Audience.STAFF)
    now = registry.chunks_as_of(TODAY, audience=Audience.STAFF)

    assert [chunk.version for chunk in before if chunk.source_id == "SOP-REFUND-ESCALATION"] == [1]
    assert [chunk.version for chunk in now if chunk.source_id == "SOP-REFUND-ESCALATION"] == [2]
