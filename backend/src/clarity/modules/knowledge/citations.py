"""The citation verifier: a cited source must be one that was really there.

K03 (#33), plan 22 section 7 ("Verify") and section 8 ("Hallucinated policy:
cite-or-refuse; citation verifier; effective-date filters").

**What this exists to stop.** A model given retrieved context and asked to cite
its sources will sometimes cite a plausible-looking id it was never given: the
right shape, the wrong document, or a version that never existed. A citation
like that is worse than no citation, because it is *checkable in principle* and
so reads as evidence. The customer, and anyone auditing the case later, has no
way to tell it apart from a real one without going and looking.

So every citation in a composed answer is checked against the retrieval that
produced the answer, and three independent things have to hold:

1. **Retrieved.** The cited chunk was in this answer's own result set. Not "the
   source exists", not "it could have been retrieved": this query returned it.
   A source that exists and is effective and is audience-allowed, but was not
   retrieved for *this* question, is a model reaching for something it liked
   the look of.
2. **Effective.** The cited version was in force at the moment being asked
   about. K02's filter already guarantees this for anything retrieved, so a
   failure here means the trace and the citation disagree, which is a bug
   rather than a hallucination. Checked anyway: the verifier is the last thing
   between a model and a customer, and a check that is cheap and redundant is
   worth keeping when the alternative is a wrong answer about the law.
3. **Audience-allowed.** The reader may see it. Same argument.

**A failed verification never degrades the answer; it replaces it.** There is no
"drop the bad citation and send the rest": a sentence whose support was removed
is a sentence with no support, and the model's other sentences were written in
the context of the claim it could no longer make. The answer is discarded whole
and the caller gets the template or the refusal.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from clarity.modules.knowledge.retrieval import RetrievalTrace
from clarity.modules.knowledge.sources import Audience

#: A citation as the composer writes it and as the verifier reads it:
#: ``SOURCE@version`` with an optional ``#clause``.
#:
#: The source id is matched narrowly rather than as ``.+``: a greedy pattern
#: swallows surrounding prose and turns a sentence into one enormous "citation"
#: that then fails for the wrong reason, which makes the audit record useless
#: for finding out what the model actually did.
CITATION = re.compile(r"\[([A-Za-z0-9][A-Za-z0-9._\-]*@\d+(?:#[^\]]{1,64})?)\]")


class CitationFault(StrEnum):
    """Why one citation did not verify. Stable: the audit records it."""

    NOT_RETRIEVED = "NOT_RETRIEVED"
    """Cited something this query did not return. The hallucination case."""

    NOT_EFFECTIVE = "NOT_EFFECTIVE"
    """Cited a version not in force at the moment asked about."""

    NOT_AUDIENCE = "NOT_AUDIENCE"
    """Cited a source this reader may not see."""

    MALFORMED = "MALFORMED"
    """Not a citation at all: no version, or an unparseable shape."""


@dataclass(frozen=True)
class CitationCheck:
    """One citation and what became of it."""

    citation: str
    ok: bool
    fault: CitationFault | None = None

    @property
    def source_id(self) -> str:
        return self.citation.split("@", 1)[0]


@dataclass(frozen=True)
class CitationReport:
    """Every citation in one answer, checked.

    ``uncited`` is separate from a fault because it is a different problem: a
    faulty citation is a claim with the wrong support, and an uncited answer is
    a claim with none. Plan 22 section 7 refuses both, by different routes.
    """

    checks: tuple[CitationCheck, ...] = ()
    uncited: bool = False
    """The answer made a claim and cited nothing at all."""

    @property
    def ok(self) -> bool:
        return not self.uncited and all(check.ok for check in self.checks)

    @property
    def faults(self) -> tuple[str, ...]:
        """Fault codes, for the audit. Deduplicated, in first-seen order."""
        codes = [check.fault.value for check in self.checks if check.fault is not None]
        if self.uncited:
            codes.insert(0, "UNCITED")
        return tuple(dict.fromkeys(codes))

    @property
    def verified(self) -> tuple[str, ...]:
        return tuple(check.citation for check in self.checks if check.ok)

    def to_detail(self) -> dict[str, object]:
        return {
            "citations_ok": self.ok,
            "citations_verified": list(self.verified),
            "citation_faults": list(self.faults),
        }


def citations_in(text: str) -> tuple[str, ...]:
    """Every citation the answer carries, in order, deduplicated."""
    return tuple(dict.fromkeys(match.group(1) for match in CITATION.finditer(text)))


def verify_citations(
    text: str,
    *,
    trace: RetrievalTrace,
    audience: Audience,
    moment: datetime,
    claim_requires_citation: bool = True,
) -> CitationReport:
    """Check every citation in ``text`` against the retrieval behind it.

    ``claim_requires_citation`` is true for a knowledge answer and false for
    wording that makes no policy claim, such as a refusal or a handoff line:
    those have nothing to support and demanding a citation would make the
    honest answer unsendable.
    """
    found = citations_in(text)
    if not found:
        # An answer with no citation is uncited only if it claimed something.
        # The distinction matters: "I do not know, let me get a person" is a
        # correct, sendable answer that cites nothing.
        return CitationReport(uncited=bool(claim_requires_citation and text.strip()))

    # Keyed by the full `source@version`, so citing the right source at the
    # wrong version does not verify. A version is the unit a reader can look
    # up, and "the current version says something else" is exactly the error
    # effective dating exists to prevent.
    retrieved = {f"{hit.chunk.source_id}@{hit.chunk.version}": hit.chunk for hit in trace.hits}

    checks: list[CitationCheck] = []
    for citation in found:
        root = citation.split("#", 1)[0]
        chunk = retrieved.get(root)
        if chunk is None:
            checks.append(
                CitationCheck(citation=citation, ok=False, fault=CitationFault.NOT_RETRIEVED)
            )
            continue
        if not chunk.effective_at(moment):
            checks.append(
                CitationCheck(citation=citation, ok=False, fault=CitationFault.NOT_EFFECTIVE)
            )
            continue
        if not chunk.readable_by(audience):
            checks.append(
                CitationCheck(citation=citation, ok=False, fault=CitationFault.NOT_AUDIENCE)
            )
            continue
        checks.append(CitationCheck(citation=citation, ok=True))

    return CitationReport(checks=tuple(checks))


def malformed_citations(text: str) -> tuple[str, ...]:
    """Bracketed things that look like a citation attempt but are not one.

    Reported rather than ignored. A model writing ``[T&C 4.2]`` or
    ``[KB-FUP]`` without a version is trying to cite and failing, and silently
    treating that as prose means the answer ships with what reads to a customer
    as a reference to something they cannot look up.
    """
    attempts = re.findall(r"\[([^\]]{1,80})\]", text)
    return tuple(
        attempt
        for attempt in dict.fromkeys(attempts)
        if not CITATION.fullmatch(f"[{attempt}]")
        and any(character.isalnum() for character in attempt)
    )


def all_faults(text: str, report: CitationReport) -> tuple[str, ...]:
    """Every reason this answer may not be sent, including malformed attempts."""
    codes = list(report.faults)
    if malformed_citations(text):
        codes.append(CitationFault.MALFORMED.value)
    return tuple(dict.fromkeys(codes))


def sources_of(trace: RetrievalTrace) -> Sequence[str]:
    """The citations an answer grounded in ``trace`` is allowed to use."""
    return tuple(dict.fromkeys(hit.citation for hit in trace.hits))


__all__ = [
    "CITATION",
    "CitationCheck",
    "CitationFault",
    "CitationReport",
    "all_faults",
    "citations_in",
    "malformed_citations",
    "sources_of",
    "verify_citations",
]
