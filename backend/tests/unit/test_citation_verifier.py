"""The citation verifier (K03 #33, acceptance 1).

A model given retrieved context and asked to cite will sometimes cite a
plausible-looking id it was never given: the right shape, the wrong document.
That is worse than no citation, because it is checkable in principle and so
reads as evidence, and nobody can tell it from a real one without going and
looking.

So the assertions here are about what happens to an answer whose citation does
not hold, and the answer is always the same: the answer does not go out. There
is no "drop the bad citation and send the rest", because a sentence whose
support was removed is a sentence with no support.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from clarity.kernel.common import Language
from clarity.modules.knowledge.answers import AnswerKind
from clarity.modules.knowledge.public import (
    Audience,
    CitationFault,
    KnowledgeRegistry,
    KnowledgeRetriever,
    KnowledgeSource,
    RetrievalConfig,
    SourceKind,
    citations_in,
    compose_answer,
    malformed_citations,
    verify_citations,
)

CONFIG = Path(__file__).parents[3] / "config" / "ai" / "retrieval.yaml"
NOW = datetime(2026, 10, 3, tzinfo=UTC)
LAST_YEAR = datetime(2025, 1, 1, tzinfo=UTC)
NEXT_MONTH = datetime(2026, 11, 1, tzinfo=UTC)

FUP_TEXT = "4.2 Speeds may be reduced once the fair usage threshold is reached."
SOP_TEXT = "A refund above the desk limit is escalated to the duty manager."


def source(**overrides) -> KnowledgeSource:
    fields = {
        "source_id": "SIM-FUP",
        "version": 1,
        "title": "Fair usage",
        "kind": SourceKind.LEGAL_TEXT,
        "owner": "legal-sim",
        "audience": Audience.CUSTOMER,
        "language": Language.EN,
        "clause_prefix": "T&C",
        "body": FUP_TEXT,
        "effective_from": LAST_YEAR,
    }
    return KnowledgeSource(**(fields | overrides))


@pytest.fixture
def retriever() -> KnowledgeRetriever:
    registry = KnowledgeRegistry(clock=lambda: NOW)
    registry.publish(source())
    registry.publish(
        source(
            source_id="SIM-SOP",
            title="Desk procedure",
            kind=SourceKind.STAFF_SOP,
            audience=Audience.STAFF,
            clause_prefix="",
            body=SOP_TEXT,
        )
    )
    built = KnowledgeRetriever(registry, RetrievalConfig.from_file(CONFIG))
    built.index(registry.chunks_as_of(NOW, audience=Audience.STAFF))
    return built


@pytest.fixture
def trace(retriever):
    found = retriever.search("speed reduced fair usage", audience=Audience.CUSTOMER, moment=NOW)
    assert found.returned > 0, "the fixture retrieved nothing, so nothing below is tested"
    return found


def real_citation(trace) -> str:
    return trace.hits[0].citation


# -- acceptance 1: a citation that was not retrieved is blocked ---------- #


def test_an_answer_citing_something_not_retrieved_is_blocked(trace) -> None:
    """Acceptance 1. The hallucination case, and the whole point of the file.

    `SIM-TC-ROAMING@1` has the right shape and does not exist. A verifier that
    only checked the shape, or only that *some* citation was present, would
    pass this.
    """
    report = verify_citations(
        "Charges abroad are set by the visited network [SIM-TC-ROAMING@1].",
        trace=trace,
        audience=Audience.CUSTOMER,
        moment=NOW,
    )

    assert not report.ok
    assert report.faults == (CitationFault.NOT_RETRIEVED.value,)
    assert report.verified == ()


def test_a_model_answer_citing_something_not_retrieved_never_reaches_a_customer(
    trace,
) -> None:
    """Acceptance 1 end to end: the composed answer, not just the report."""

    def hallucinating(context: str, _trace, _language) -> str:
        return "Your speed was reduced under the roaming rules [SIM-TC-ROAMING@1]."

    answer = compose_answer(
        trace,
        audience=Audience.CUSTOMER,
        moment=NOW,
        composer=hallucinating,
    )

    assert "SIM-TC-ROAMING" not in answer.text, "the hallucinated citation was sent"
    assert "roaming rules" not in answer.text, "the unsupported claim was sent"
    # The sources were real, so there is a correct answer available and
    # withholding it would be the wrong failure: the template quotes the clause.
    assert answer.kind is AnswerKind.TEMPLATE
    assert answer.grounded
    assert CitationFault.NOT_RETRIEVED.value in answer.faults, (
        "the model's fault must be recorded even though the turn recovered"
    )


def test_the_right_source_at_the_wrong_version_does_not_verify(trace) -> None:
    """Version is part of the identity, not decoration.

    "The current version says something else" is exactly the error effective
    dating exists to prevent, so citing `@2` of a source retrieved at `@1` is
    a miss rather than a near-match.
    """
    report = verify_citations(
        f"{FUP_TEXT} [SIM-FUP@2]", trace=trace, audience=Audience.CUSTOMER, moment=NOW
    )

    assert not report.ok
    assert report.faults == (CitationFault.NOT_RETRIEVED.value,)


def test_a_staff_source_cited_to_a_customer_does_not_verify(retriever) -> None:
    """A staff SOP reaching a customer is a disclosure, so it is checked twice.

    K02's filter already keeps it out of a customer's result set. This is the
    second check, on the way out, because the verifier is the last thing
    between a model and a customer.
    """
    staff_trace = retriever.search("refund desk limit", audience=Audience.STAFF, moment=NOW)
    assert any(hit.chunk.source_id == "SIM-SOP" for hit in staff_trace.hits)

    report = verify_citations(
        f"{SOP_TEXT} [SIM-SOP@1]",
        trace=staff_trace,
        audience=Audience.CUSTOMER,
        moment=NOW,
    )

    assert not report.ok
    assert report.faults == (CitationFault.NOT_AUDIENCE.value,)


def test_a_superseded_version_cited_after_it_lapsed_does_not_verify(retriever) -> None:
    """Retrieved once, no longer effective at the moment being answered."""
    old = retriever.search("speed reduced", audience=Audience.CUSTOMER, moment=LAST_YEAR)
    assert old.returned > 0

    report = verify_citations(
        f"{FUP_TEXT} [{real_citation(old).split('#')[0]}]",
        trace=old,
        audience=Audience.CUSTOMER,
        # Answered as of a moment the retrieved version does not cover.
        moment=datetime(2024, 1, 1, tzinfo=UTC),
    )

    assert not report.ok
    assert report.faults == (CitationFault.NOT_EFFECTIVE.value,)


# -- the other half: a real citation must verify ------------------------- #


def test_a_citation_that_was_retrieved_verifies(trace) -> None:
    """Without this the verifier could refuse everything and pass the rest."""
    report = verify_citations(
        f"{FUP_TEXT} [{real_citation(trace)}]",
        trace=trace,
        audience=Audience.CUSTOMER,
        moment=NOW,
    )

    assert report.ok, report.faults
    assert report.verified == (real_citation(trace),)


def test_the_template_answer_verifies_against_its_own_retrieval(trace) -> None:
    """The floor: with no model at all, the answer is grounded and cited."""
    answer = compose_answer(trace, audience=Audience.CUSTOMER, moment=NOW)

    assert answer.kind is AnswerKind.TEMPLATE
    assert answer.grounded
    assert answer.citations
    assert "Speeds may be reduced" in answer.text, "the clause was not quoted"


def test_a_model_answer_with_real_citations_is_used(trace) -> None:
    def honest(context: str, _trace, _language) -> str:
        return f"Your speed drops after the fair usage threshold [{real_citation(trace)}]."

    answer = compose_answer(trace, audience=Audience.CUSTOMER, moment=NOW, composer=honest)

    assert answer.kind is AnswerKind.MODEL
    assert answer.grounded
    assert answer.faults == ()


# -- an answer that cites nothing ---------------------------------------- #


def test_an_answer_that_claims_something_and_cites_nothing_is_uncited(trace) -> None:
    """Cite or refuse (plan 22 section 8). An uncited claim is not sendable."""
    report = verify_citations(
        "Your speed was reduced because you used too much data.",
        trace=trace,
        audience=Audience.CUSTOMER,
        moment=NOW,
    )

    assert not report.ok
    assert "UNCITED" in report.faults


def test_a_refusal_is_allowed_to_cite_nothing() -> None:
    """Otherwise the honest answer is the one answer that cannot be sent."""
    from clarity.modules.knowledge.retrieval import RetrievalTrace

    empty = RetrievalTrace(query="q", terms=(), candidates=0, returned=0, semantic=False)

    report = verify_citations(
        "I do not know, let me get a person.",
        trace=empty,
        audience=Audience.CUSTOMER,
        moment=NOW,
        claim_requires_citation=False,
    )

    assert report.ok


def test_a_model_answer_citing_nothing_falls_back_to_the_template(trace) -> None:
    def unciting(context: str, _trace, _language) -> str:
        return "Your speed was reduced because you used too much data."

    answer = compose_answer(trace, audience=Audience.CUSTOMER, moment=NOW, composer=unciting)

    assert answer.kind is AnswerKind.TEMPLATE
    assert "too much data" not in answer.text
    assert "UNCITED" in answer.faults


# -- malformed citation attempts ----------------------------------------- #


@pytest.mark.parametrize("attempt", ["[T&C 4.2]", "[SIM-FUP]", "[clause 4.2]"])
def test_a_citation_attempt_with_no_version_is_malformed(trace, attempt: str) -> None:
    """A reference a customer cannot look up reads as one they can.

    Treating it as prose would ship an answer that appears to cite something.
    """
    assert malformed_citations(f"Speeds may be reduced {attempt}")


def test_a_malformed_attempt_blocks_a_model_answer(trace) -> None:
    def half_citing(context: str, _trace, _language) -> str:
        return f"Speeds may be reduced [T&C 4.2] as set out at [{real_citation(trace)}]."

    answer = compose_answer(trace, audience=Audience.CUSTOMER, moment=NOW, composer=half_citing)

    assert answer.kind is AnswerKind.TEMPLATE
    assert CitationFault.MALFORMED.value in answer.faults


def test_prose_in_brackets_is_not_a_citation_attempt(trace) -> None:
    """The check must not fire on ordinary bracketed text."""
    assert malformed_citations("Speeds may be reduced [see below]") == ("see below",)
    assert malformed_citations("Speeds may be reduced (see below)") == ()


def test_a_citation_pattern_does_not_swallow_surrounding_prose(trace) -> None:
    """A greedy pattern turns a sentence into one enormous citation.

    Which then fails for the wrong reason and makes the audit record useless
    for working out what the model actually did.
    """
    found = citations_in(f"[{real_citation(trace)}] and then more prose [SIM-OTHER@2]")

    assert len(found) == 2
    assert all(len(citation) < 80 for citation in found)


# -- no source at all ----------------------------------------------------- #


def test_with_nothing_retrieved_the_answer_is_a_refusal(retriever) -> None:
    empty = retriever.search("zzzqqq unrelated", audience=Audience.CUSTOMER, moment=NOW)
    assert empty.returned == 0

    answer = compose_answer(empty, audience=Audience.CUSTOMER, moment=NOW)

    assert answer.kind is AnswerKind.REFUSAL
    assert answer.needs_person
    assert not answer.grounded
    assert answer.citations == ()


def test_a_composer_is_not_even_asked_when_there_is_no_source(retriever) -> None:
    """A model given no context will answer from its training, which is a guess."""
    asked: list[str] = []

    def composer(context: str, _trace, _language) -> str:
        asked.append(context)
        return "Speeds are reduced after 25 GB."

    empty = retriever.search("zzzqqq unrelated", audience=Audience.CUSTOMER, moment=NOW)
    answer = compose_answer(empty, audience=Audience.CUSTOMER, moment=NOW, composer=composer)

    assert asked == [], "the composer was asked to answer with no sources"
    assert answer.kind is AnswerKind.REFUSAL


@pytest.mark.parametrize("language", [Language.EN, Language.SI, Language.TA])
def test_the_refusal_is_in_the_language_asked(retriever, language: Language) -> None:
    empty = retriever.search("zzzqqq unrelated", audience=Audience.CUSTOMER, moment=NOW)

    answer = compose_answer(empty, audience=Audience.CUSTOMER, moment=NOW, language=language)

    assert answer.text
    assert answer.needs_person


def test_a_composer_that_raises_falls_back_to_the_template(trace) -> None:
    def broken(context: str, _trace, _language) -> str:
        raise RuntimeError("the provider is down")

    answer = compose_answer(trace, audience=Audience.CUSTOMER, moment=NOW, composer=broken)

    assert answer.kind is AnswerKind.TEMPLATE
    assert answer.grounded


def test_the_context_a_composer_sees_is_delimited_as_untrusted(trace) -> None:
    """Retrieved text is data, never instructions, exactly as in C03."""
    seen: list[str] = []

    def composer(context: str, _trace, _language) -> str:
        seen.append(context)
        return f"{FUP_TEXT} [{real_citation(trace)}]"

    compose_answer(trace, audience=Audience.CUSTOMER, moment=NOW, composer=composer)

    assert "<<<SOURCE" in seen[0]
    assert "<<<END SOURCE>>>" in seen[0]


def test_the_detail_records_what_happened(trace) -> None:
    """The turn audit carries the kind, the citations and the faults."""
    answer = compose_answer(trace, audience=Audience.CUSTOMER, moment=NOW)
    detail = answer.to_detail()

    assert detail["answer_kind"] == "template"
    assert detail["answer_grounded"] is True
    assert detail["citations_ok"] is True
    assert detail["citations_verified"]
