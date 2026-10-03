"""Knowledge sources and the chunks ingestion makes of them (K01, #31).

Plan 22 section 7, and plan 20 kind K2. A knowledge source is **governed
content**, not data: it has an owner, a version and an effective window, it is
reviewed before it is published, and old versions stay retrievable so a
question about what applied in March can be answered in June.

Three fields carry the weight, and all three are required rather than
defaulted:

- ``owner``: a source with no owner is a source nobody is accountable for, and
  what gets quoted to a customer needs an accountable author (plan 20 section
  188 names the owning roles per kind).
- ``effective_from``: a source with no effective date cannot answer "what
  applied then", which is the whole reason old versions are kept.
- ``audience``: a staff SOP read out to a customer is a disclosure. There is no
  default audience, so nobody gets one by forgetting.

``effective_to`` is optional, and ``None`` means open-ended rather than
unknown: the current version of a policy has no end date until a successor
gives it one.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, model_validator

from clarity.kernel.common import ClarityModel, Language


class Audience(StrEnum):
    """Who a source may be shown to."""

    CUSTOMER = "customer"
    """Published, customer-facing text. Staff may read it too."""

    STAFF = "staff"
    """Internal only: SOPs, desk procedures, anything not for a customer."""

    def may_read(self, other: Audience) -> bool:
        """Whether a reader of *self* may be shown content marked *other*.

        Customer-facing text is readable by everyone; staff content only by
        staff. Asymmetric on purpose: the risk is a staff SOP reaching a
        customer, not a customer article reaching an agent.
        """
        return other is Audience.CUSTOMER or self is Audience.STAFF


class SourceKind(StrEnum):
    """What a source is, which decides how it is chunked (plan 22 section 7)."""

    CATALOGUE = "catalogue"
    """A product or pack offering. One chunk per offering per version."""

    LEGAL_TEXT = "legal_text"
    """T&C clauses, a Gazette direction. Chunked per clause."""

    VAS_RULE = "vas_rule"
    HELP_ARTICLE = "help_article"
    CX_ANSWER = "cx_answer"
    """Wording CX has already approved for customers."""

    STAFF_SOP = "staff_sop"
    """Always staff audience, enforced on the source."""


class KnowledgeSource(ClarityModel):
    """One version of one governed source.

    Identity is ``(source_id, version)``. Two versions of the same
    ``source_id`` are two records, because the old one has to stay readable.
    """

    source_id: str
    version: int = Field(ge=1)
    title: str
    kind: SourceKind
    owner: str
    """The accountable role or team, for example ``legal`` or ``cx-knowledge``."""

    audience: Audience
    language: Language
    body: str
    effective_from: datetime
    effective_to: datetime | None = None
    product_ids: tuple[str, ...] = ()
    """Which offerings this is about, for the retrieval filter (K02)."""

    clause_prefix: str = ""
    """Prefix for clause references, for example ``T&C`` in ``T&C 4.2``."""

    @model_validator(mode="after")
    def _window_is_ordered(self) -> KnowledgeSource:
        if self.effective_to is not None and self.effective_to <= self.effective_from:
            raise ValueError(
                f"{self.ref}: effective_to {self.effective_to.isoformat()} is not after "
                f"effective_from {self.effective_from.isoformat()}; an empty window means "
                "this version was never in force, which is a deletion, not a publication"
            )
        if self.kind is SourceKind.STAFF_SOP and self.audience is not Audience.STAFF:
            raise ValueError(
                f"{self.ref}: a staff SOP must be staff audience; "
                "plan 22 section 7 makes SOPs staff-only and this is not a per-source choice"
            )
        if not self.body.strip():
            raise ValueError(f"{self.ref}: a source with no text has nothing to cite")
        return self

    @property
    def ref(self) -> str:
        """The citation root: ``source_id@version`` (plan 22 section 7)."""
        return f"{self.source_id}@{self.version}"

    def effective_at(self, moment: datetime) -> bool:
        """Whether this version was in force at *moment*.

        Half-open: ``effective_from`` inclusive, ``effective_to`` exclusive, so
        a successor starting the instant the old one ends leaves no gap and no
        overlap.
        """
        if moment < self.effective_from:
            return False
        return self.effective_to is None or moment < self.effective_to

    def overlaps(self, other: KnowledgeSource) -> bool:
        """Whether two versions of one source claim the same instant."""
        if self.source_id != other.source_id:
            return False
        later_start = max(self.effective_from, other.effective_from)
        ends = [end for end in (self.effective_to, other.effective_to) if end is not None]
        return not ends or later_start < min(ends)


class Chunk(ClarityModel):
    """A retrievable piece of a source, carrying the metadata to filter it.

    The metadata is copied from the source rather than looked up through it.
    Retrieval filters on effective date, audience and language (plan 22 section
    7), and a filter that has to join to another record to decide is a filter
    that gets skipped under load. Copying also means a chunk stays truthful
    about the version it came from after a successor is published.
    """

    chunk_id: str
    source_id: str
    version: int
    ordinal: int
    """Position within the source version, so chunks can be read back in order."""

    text: str
    clause_ref: str = ""
    """The clause this came from, for example ``4.2``. Empty when unstructured."""

    kind: SourceKind
    owner: str
    audience: Audience
    language: Language
    effective_from: datetime
    effective_to: datetime | None = None
    product_ids: tuple[str, ...] = ()

    @property
    def citation(self) -> str:
        """What an answer must cite: ``source_id@version#clause``.

        The ``#clause`` part is dropped when there is no clause, rather than
        left empty, so a citation is always something a reader can look up.
        """
        root = f"{self.source_id}@{self.version}"
        return f"{root}#{self.clause_ref}" if self.clause_ref else root

    def effective_at(self, moment: datetime) -> bool:
        if moment < self.effective_from:
            return False
        return self.effective_to is None or moment < self.effective_to

    def readable_by(self, audience: Audience) -> bool:
        return audience.may_read(self.audience)


__all__ = ["Audience", "Chunk", "KnowledgeSource", "SourceKind"]
