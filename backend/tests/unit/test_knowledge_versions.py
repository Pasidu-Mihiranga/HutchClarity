"""Effective dating: what applied then, not what applies now (K01 #31, acceptance 1).

A dispute is about a charge that happened on a date, and the policy that
governs it is the policy that was in force on that date. Plan 22 section 7 puts
the effective-date filter in retrieval for exactly this reason, and plan 20
keeps old versions retrievable rather than replacing them.

Getting this wrong is not a degraded answer, it is a confidently wrong one: a
customer told about the terms published next month has been told something
untrue about their own charge, with a citation attached.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from clarity.kernel.common import Language
from clarity.modules.knowledge.public import (
    Audience,
    KnowledgeRegistry,
    KnowledgeSource,
    PublicationRefused,
    SourceKind,
)
from clarity.platform.persistence import MemoryStore, MemoryUnitOfWork

TODAY = datetime(2026, 10, 3, tzinfo=UTC)
LAST_YEAR = datetime(2025, 1, 1, tzinfo=UTC)
NEXT_MONTH = datetime(2026, 11, 1, tzinfo=UTC)


def clause(version: int, *, text: str, effective_from: datetime, effective_to=None):
    return KnowledgeSource(
        source_id="TC-FUP",
        version=version,
        title="Fair usage policy",
        kind=SourceKind.LEGAL_TEXT,
        owner="legal",
        audience=Audience.CUSTOMER,
        language=Language.EN,
        clause_prefix="T&C",
        body=text,
        effective_from=effective_from,
        effective_to=effective_to,
    )


@pytest.fixture
def registry() -> KnowledgeRegistry:
    store = MemoryStore()

    def open_unit() -> MemoryUnitOfWork:
        return MemoryUnitOfWork(store)

    return KnowledgeRegistry(open_unit=open_unit, clock=lambda: TODAY)


VERSION_1 = "4.2 Speeds may be reduced after 25 GB in a billing cycle."
VERSION_2 = "4.2 Speeds may be reduced after 40 GB in a billing cycle."


def test_a_version_effective_next_month_is_not_returned_today(registry) -> None:
    """Acceptance 1. Version 2 starts next month, so today still gets version 1."""
    registry.publish(clause(1, text=VERSION_1, effective_from=LAST_YEAR, effective_to=NEXT_MONTH))
    registry.publish(clause(2, text=VERSION_2, effective_from=NEXT_MONTH))

    today = registry.chunks_as_of(TODAY, audience=Audience.CUSTOMER)

    assert [chunk.version for chunk in today] == [1]
    assert "25 GB" in today[0].text
    assert "40 GB" not in today[0].text
    assert today[0].citation == "TC-FUP@1#T&C 4.2"


def test_the_future_version_is_returned_once_it_is_in_force(registry) -> None:
    """The other half: the filter is a window, not a "hide the newest" rule."""
    registry.publish(clause(1, text=VERSION_1, effective_from=LAST_YEAR, effective_to=NEXT_MONTH))
    registry.publish(clause(2, text=VERSION_2, effective_from=NEXT_MONTH))

    later = registry.chunks_as_of(NEXT_MONTH + timedelta(days=1), audience=Audience.CUSTOMER)

    assert [chunk.version for chunk in later] == [2]
    assert "40 GB" in later[0].text


def test_the_old_version_is_still_retrievable_for_the_period_it_covered(registry) -> None:
    """Plan 20: old versions stay retrievable for "what applied then".

    This is the dispute case. The charge happened in March, the terms changed
    in November, and the answer has to be March's terms however long ago that
    was.
    """
    registry.publish(clause(1, text=VERSION_1, effective_from=LAST_YEAR, effective_to=NEXT_MONTH))
    registry.publish(clause(2, text=VERSION_2, effective_from=NEXT_MONTH))

    march = registry.chunks_as_of(datetime(2026, 3, 15, tzinfo=UTC), audience=Audience.CUSTOMER)

    assert [chunk.version for chunk in march] == [1]
    assert registry.versions("TC-FUP") == sorted(
        registry.versions("TC-FUP"), key=lambda source: source.version
    )
    assert len(registry.versions("TC-FUP")) == 2, "the superseded version was not kept"


def test_nothing_is_returned_before_the_first_version_took_effect(registry) -> None:
    """A question about a date before the policy existed has no answer here.

    Returning the earliest version anyway would be the tempting fallback and
    the wrong one: it would answer a question about an uncovered period with
    text that did not apply (I2, missing evidence is a person, never a guess).
    """
    registry.publish(clause(1, text=VERSION_1, effective_from=LAST_YEAR))

    before = registry.chunks_as_of(datetime(2024, 6, 1, tzinfo=UTC), audience=Audience.CUSTOMER)

    assert before == []


def test_two_versions_may_not_be_in_force_at_once(registry) -> None:
    """The refusal that makes "what applied then" have one answer.

    Without it, an overlap is resolved by whatever tie-break retrieval happens
    to use, so the answer to a question about March could change when an
    unrelated record is rewritten.
    """
    registry.publish(clause(1, text=VERSION_1, effective_from=LAST_YEAR))

    with pytest.raises(PublicationRefused) as refused:
        registry.publish(clause(2, text=VERSION_2, effective_from=TODAY))

    assert "same time" in str(refused.value)


def test_supersede_closes_the_previous_version_at_the_successor_start(registry) -> None:
    """The governed path, so the common case needs no manual bookkeeping.

    No gap and no overlap: the window is half-open, so the instant the
    successor starts is the instant the predecessor stops.
    """
    registry.publish(clause(1, text=VERSION_1, effective_from=LAST_YEAR))

    registry.supersede(clause(2, text=VERSION_2, effective_from=NEXT_MONTH))

    today = registry.chunks_as_of(TODAY, audience=Audience.CUSTOMER)
    once_live = registry.chunks_as_of(NEXT_MONTH, audience=Audience.CUSTOMER)

    assert [chunk.version for chunk in today] == [1]
    assert [chunk.version for chunk in once_live] == [2]
    closed = registry.versions("TC-FUP")[0]
    assert closed.effective_to == NEXT_MONTH


def test_republishing_the_same_version_is_refused(registry) -> None:
    """A correction is a new version, because the old one may already be cited."""
    registry.publish(clause(1, text=VERSION_1, effective_from=LAST_YEAR, effective_to=NEXT_MONTH))

    with pytest.raises(PublicationRefused) as refused:
        registry.publish(
            clause(1, text=VERSION_2, effective_from=LAST_YEAR, effective_to=NEXT_MONTH)
        )

    assert "already published" in str(refused.value)


def test_a_version_that_was_never_in_force_is_refused() -> None:
    """An empty window is a deletion dressed as a publication."""
    with pytest.raises(ValueError, match="never in force"):
        clause(1, text=VERSION_1, effective_from=NEXT_MONTH, effective_to=LAST_YEAR)
