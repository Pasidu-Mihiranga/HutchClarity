"""Grounded answers: compose from what was retrieved, or refuse (K03, #33).

Plan 22 section 7 ("Answer") and section 8 ("Hallucinated policy: cite-or-refuse").

Three paths, and which one runs is decided by what is available rather than by
configuration:

| Retrieved | Model | Answer |
|---|---|---|
| nothing | either | **refusal**: does not know, offers a person |
| something | none | **template**: the source's own words, cited |
| something | `fast-text` | model wording, verified, template on failure |

**The template path quotes the source verbatim.** It does not paraphrase. I15
allows no free text to customers from an LLM and I1 keeps the LLM out of
deciding anything, and a paraphrase of a policy clause is a new claim about
policy made by whoever wrote the paraphraser. Quoting the clause and citing it
is the strongest grounded answer available without a model, and it is the
fallback the model path lands on, so the floor is never worse than "here is
what the rule says, here is where to check it".

**The refusal is a real answer, not an error.** "No source" is the honest
outcome for a question the published corpus does not cover, and plan 22 makes
it a template plus a person. A system that guesses instead is the failure mode
this whole module exists to prevent (I2: missing evidence goes to a person,
never a guess).

**A model answer that fails verification is discarded whole**, not repaired.
See `citations.py` for why there is no "drop the bad citation and send the
rest".
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from clarity.kernel.common import Language
from clarity.modules.knowledge.citations import (
    CitationReport,
    all_faults,
    verify_citations,
)
from clarity.modules.knowledge.retrieval import RetrievalTrace
from clarity.modules.knowledge.sources import Audience

#: How many retrieved chunks the template answer quotes.
#:
#: Two, not `top_k`. A template answer is read by a customer in a chat bubble,
#: and five quoted clauses is a wall of text nobody reads, which is its own
#: failure to communicate. The rest of the result set stays in the trace for
#: the audit and for a model path that wants more context.
QUOTED_IN_TEMPLATE = 2

#: The longest a quoted chunk runs before it is trimmed at a sentence end.
QUOTE_CHARS = 420


class AnswerKind(StrEnum):
    """How this answer was produced. Recorded, because it is not cosmetic."""

    TEMPLATE = "template"
    """The source's own words, cited. No model involved."""

    MODEL = "model"
    """Model wording over the retrieved context, citations verified."""

    REFUSAL = "refusal"
    """No source, or a model answer that failed verification."""


#: Refusal and framing wording, per language.
#:
#: **ASSUMPTION** on the Sinhala and Tamil strings: written for the prototype
#: and not reviewed by a native speaker. Plan 22 section 10's language review
#: gate (`language_review.mean_rating`) is the thing that would clear them, and
#: it reports UNEVALUABLE until native-speaker ratings exist (FE01, #28).
#: **REQUIRES HUTCH CONFIRMATION** before any of this reaches a customer.
NO_SOURCE: dict[Language, str] = {
    Language.EN: (
        "I do not have a published source that answers that, so I would rather "
        "not guess. Let me get a person who can check it for you."
    ),
    Language.SI: (
        "එයට පිළිතුරු දෙන ප්රකාශිත මූලාශ්රයක් මා සතුව නැත, එබැවින් අනුමාන කිරීමට "
        "මා අකමැතියි. එය පරීක්ෂා කළ හැකි නිලධාරියෙකු සම්බන්ධ කර දෙන්නම්."
    ),
    Language.TA: (
        "அதற்கு விடை அளிக்கும் வெளியிடப்பட்ட ஆவணம் என்னிடம் இல்லை, எனவே ஊகிக்க "
        "விரும்பவில்லை. அதைச் சரிபார்க்கக்கூடிய ஒருவரைத் தொடர்பு கொள்கிறேன்."
    ),
}

#: The line that introduces a quoted clause.
ACCORDING_TO: dict[Language, str] = {
    # Neutral on purpose: the corpus holds help articles as well as terms, and
    # "the published terms say" is untrue of an article about installing an
    # eSIM. A framing line that misdescribes its own source is a small lie in
    # the one place the module exists to be trustworthy.
    Language.EN: "Here is what the published guidance says:",
    Language.SI: "ප්රකාශිත මාර්ගෝපදේශයේ මෙසේ සඳහන් වේ:",
    Language.TA: "வெளியிடப்பட்ட வழிகாட்டலில் உள்ளது:",
}


@dataclass(frozen=True)
class GroundedAnswer:
    """What to say, where it came from, and whether it may be sent."""

    text: str
    kind: AnswerKind
    citations: tuple[str, ...] = ()
    report: CitationReport = field(default_factory=CitationReport)
    faults: tuple[str, ...] = ()
    """Why a model answer was rejected, when one was. Empty otherwise."""

    needs_person: bool = False
    """Whether the customer should be offered a person."""

    @property
    def grounded(self) -> bool:
        """Whether every claim in this answer is backed by a *verified* source.

        The citation list is not enough on its own. An empty `CitationReport`
        means "nothing was checked", and `all([])` is true, so an answer
        carrying citations with a default report would read as verified without
        anything having verified it. That is a trust hole rather than a cosmetic
        one: `grounded` is what the HTTP route and the turn audit report, and a
        cache refuses an answer that is not grounded.

        So every citation this answer claims has to appear in the report's
        verified set. An answer that claims none is grounded only if it is not
        a refusal and the report came back clean.
        """
        if self.kind is AnswerKind.REFUSAL or not self.report.ok:
            return False
        return set(self.citations) <= set(self.report.verified)

    def to_detail(self) -> dict[str, object]:
        return {
            "answer_kind": self.kind.value,
            "answer_grounded": self.grounded,
            "answer_needs_person": self.needs_person,
            **self.report.to_detail(),
            "answer_faults": list(self.faults),
        }


#: A model asked to word an answer from retrieved context. Optional (ADR-0009).
#:
#: It is handed the context already assembled and cited, and must return prose
#: that carries the citations through. Whatever it returns is verified before
#: anyone sees it, so a composer cannot be trusted and does not need to be.
Composer = Callable[[str, RetrievalTrace, Language], str]


def compose_answer(
    trace: RetrievalTrace,
    *,
    audience: Audience,
    moment: datetime,
    language: Language = Language.EN,
    composer: Composer | None = None,
) -> GroundedAnswer:
    """Turn a retrieval into something sendable, or into a refusal."""
    if trace.returned == 0:
        return refuse(language)

    template = _template_answer(trace, language=language)
    if composer is None:
        return _verified(template, AnswerKind.TEMPLATE, trace, audience, moment, language)

    try:
        worded = composer(_context(trace), trace, language)
    except Exception:
        # A composer is a provider call. Its failure costs the wording, never
        # the answer: the template already says the true thing.
        return _verified(template, AnswerKind.TEMPLATE, trace, audience, moment, language)

    if not worded or not worded.strip():
        return _verified(template, AnswerKind.TEMPLATE, trace, audience, moment, language)

    candidate = _verified(worded, AnswerKind.MODEL, trace, audience, moment, language)
    if candidate.kind is AnswerKind.MODEL:
        return candidate

    # The model answer did not verify. Fall back to the template rather than
    # refusing: the sources are real and the template quotes them, so there is
    # a correct answer available and refusing would withhold it. The faults
    # travel with the answer so the audit records what the model did.
    fallback = _verified(template, AnswerKind.TEMPLATE, trace, audience, moment, language)
    return GroundedAnswer(
        text=fallback.text,
        kind=fallback.kind,
        citations=fallback.citations,
        report=fallback.report,
        faults=candidate.faults,
        needs_person=fallback.needs_person,
    )


def refuse(language: Language = Language.EN) -> GroundedAnswer:
    """The honest answer to a question the corpus does not cover."""
    return GroundedAnswer(
        text=NO_SOURCE.get(language, NO_SOURCE[Language.EN]),
        kind=AnswerKind.REFUSAL,
        needs_person=True,
    )


def _verified(
    text: str,
    kind: AnswerKind,
    trace: RetrievalTrace,
    audience: Audience,
    moment: datetime,
    language: Language,
) -> GroundedAnswer:
    """Check an answer's citations, and refuse it if they do not hold."""
    report = verify_citations(text, trace=trace, audience=audience, moment=moment)
    faults = all_faults(text, report)
    if faults:
        if kind is AnswerKind.TEMPLATE:
            # The template is built from the trace, so its citations are the
            # trace's own. Failing here is a bug in this module rather than a
            # model misbehaving, and the safe outcome is still a refusal.
            return GroundedAnswer(
                text=NO_SOURCE.get(language, NO_SOURCE[Language.EN]),
                kind=AnswerKind.REFUSAL,
                report=report,
                faults=faults,
                needs_person=True,
            )
        return GroundedAnswer(
            text="", kind=AnswerKind.REFUSAL, report=report, faults=faults, needs_person=True
        )

    return GroundedAnswer(
        text=text,
        kind=kind,
        citations=report.verified,
        report=report,
    )


def _template_answer(trace: RetrievalTrace, *, language: Language) -> str:
    """Quote the best sources verbatim, each with its citation.

    Verbatim, because a paraphrase of a policy clause is a new claim about
    policy (I15). Trimmed at a sentence boundary rather than mid-word, so a
    quote never ends in the middle of a condition and changes its meaning.
    """
    lines = [ACCORDING_TO.get(language, ACCORDING_TO[Language.EN])]
    for hit in trace.hits[:QUOTED_IN_TEMPLATE]:
        lines.append(f"{_trim(hit.chunk.text)} [{hit.citation}]")
    return "\n\n".join(lines)


def _context(trace: RetrievalTrace) -> str:
    """The CONTEXT block a composer is given: cited, delimited, untrusted.

    Retrieved text is untrusted data, exactly as a tool result is in C03: a
    document that says "ignore your instructions" is a document that says
    that. The composer's own prompt lives in the AI layer; what this supplies
    is the content, already fenced.
    """
    blocks = [
        f"<<<SOURCE [{hit.citation}]>>>\n{hit.chunk.text}\n<<<END SOURCE>>>" for hit in trace.hits
    ]
    return "\n\n".join(blocks)


def _trim(text: str) -> str:
    """Cut a quote to length at a sentence end where there is one."""
    collapsed = " ".join(text.split())
    if len(collapsed) <= QUOTE_CHARS:
        return collapsed
    window = collapsed[:QUOTE_CHARS]
    stop = max(window.rfind(". "), window.rfind("ග "), window.rfind("? "))
    if stop > QUOTE_CHARS // 2:
        return window[: stop + 1]
    return window.rsplit(" ", 1)[0] + " ..."


__all__ = [
    "ACCORDING_TO",
    "NO_SOURCE",
    "QUOTED_IN_TEMPLATE",
    "AnswerKind",
    "Composer",
    "GroundedAnswer",
    "compose_answer",
    "refuse",
]
