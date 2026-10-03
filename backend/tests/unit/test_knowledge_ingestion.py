"""Ingestion: parse, clean, language tag, structure-aware chunking (K01, #31).

Plan 22 section 7. The acceptance tests cover the two filters that can produce
a wrong or disclosing answer; this covers the step that decides whether a
citation means anything at all.

**Why chunk boundaries are a correctness concern and not a tuning knob.** An
answer must cite ``source_id@version#clause``. A chunk spanning the end of 4.1
and the start of 4.2 can honestly cite neither, so the citation verifier (K03)
would be checking a reference that does not identify the text it came from.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from clarity.kernel.common import Language
from clarity.modules.knowledge.public import (
    WORDS_PER_CHUNK,
    Audience,
    IngestionRefused,
    KnowledgeSource,
    SourceKind,
    clean,
    dominant_script,
    ingest,
)

EFFECTIVE = datetime(2025, 1, 1, tzinfo=UTC)

SINHALA = "ජංගම දුරකථන සේවාව සඳහා අදාළ වන කොන්දේසි මෙසේ වේ. අපගේ සේවාව භාවිත කරන විට මෙම කොන්දේසි අදාළ වේ."
TAMIL = "கைபேசி சேவைக்கு பொருந்தும் நிபந்தனைகள் இவை. எங்கள் சேவையைப் பயன்படுத்தும்போது இந்த நிபந்தனைகள் பொருந்தும்."


def source(**overrides) -> KnowledgeSource:
    fields = {
        "source_id": "TC-GENERAL",
        "version": 1,
        "title": "Terms",
        "kind": SourceKind.LEGAL_TEXT,
        "owner": "legal",
        "audience": Audience.CUSTOMER,
        "language": Language.EN,
        "body": "4.1 First clause.\n\n4.2 Second clause.",
        "effective_from": EFFECTIVE,
    }
    return KnowledgeSource(**(fields | overrides))


# -- structure-aware chunking -------------------------------------------- #


def test_legal_text_is_chunked_one_clause_per_chunk() -> None:
    chunks = ingest(source(clause_prefix="T&C"))

    assert [chunk.clause_ref for chunk in chunks] == ["T&C 4.1", "T&C 4.2"]
    assert [chunk.citation for chunk in chunks] == ["TC-GENERAL@1#T&C 4.1", "TC-GENERAL@1#T&C 4.2"]


def test_no_chunk_spans_two_clauses() -> None:
    """The property the whole chunking strategy exists for."""
    chunks = ingest(
        source(body="4.1 The first rule applies.\n\n4.2 The second rule applies.\n\n4.3 Third.")
    )

    for chunk in chunks:
        others = [ref for ref in ("4.1", "4.2", "4.3") if ref != chunk.clause_ref]
        assert not any(chunk.text.startswith(ref) for ref in others)
    assert len(chunks) == 3


def test_a_cross_reference_inside_a_sentence_does_not_start_a_clause() -> None:
    """``as set out in 4.2`` mid sentence is a reference, not a boundary.

    An unanchored marker pattern splits here and produces a chunk beginning
    "4.2 above, speeds may be reduced", which would then be cited as clause
    4.2 while actually being part of 4.1.
    """
    chunks = ingest(source(body="4.1 Subject to 4.2 below, the pack renews monthly."))

    assert len(chunks) == 1
    assert chunks[0].clause_ref == "4.1"


def test_lettered_subclauses_are_their_own_chunks() -> None:
    chunks = ingest(source(body="(a) First item.\n\n(b) Second item."))

    assert [chunk.clause_ref for chunk in chunks] == ["(a)", "(b)"]


def test_a_preamble_is_kept_but_not_cited_as_a_clause() -> None:
    """Dropping it loses real text; numbering it invents a reference."""
    chunks = ingest(source(body="These terms govern the service.\n\n1. The first clause."))

    assert chunks[0].clause_ref == ""
    assert chunks[0].citation == "TC-GENERAL@1"
    assert chunks[1].clause_ref == "1"


def test_a_catalogue_entry_is_one_chunk_however_long() -> None:
    """An offering is the unit someone asks about.

    Split into three, a question about the price can retrieve the piece that
    does not mention the price.
    """
    long_body = "Unlimited 1299 pack. " + " ".join(f"detail{n}" for n in range(WORDS_PER_CHUNK * 2))

    chunks = ingest(source(kind=SourceKind.CATALOGUE, body=long_body, product_ids=("P-1299",)))

    assert len(chunks) == 1
    assert chunks[0].product_ids == ("P-1299",)


def test_an_over_long_clause_is_split_with_overlap_and_keeps_its_reference() -> None:
    """Length only applies within a clause, and the reference survives it."""
    body = "4.1 " + " ".join(f"word{n}" for n in range(WORDS_PER_CHUNK * 2))

    chunks = ingest(source(body=body))

    assert len(chunks) > 1
    assert {chunk.clause_ref for chunk in chunks} == {"4.1"}
    first_words = chunks[0].text.split()
    second_words = chunks[1].text.split()
    assert set(first_words) & set(second_words), "no overlap, so a sentence on the seam is lost"


def test_chunks_are_ordered_so_a_source_can_be_read_back() -> None:
    chunks = ingest(source(body="1. One.\n\n2. Two.\n\n3. Three."))

    assert [chunk.ordinal for chunk in chunks] == [0, 1, 2]


# -- cleaning ------------------------------------------------------------- #


def test_zero_width_characters_are_stripped() -> None:
    """They survive a copy out of a PDF and silently break a substring match."""
    assert clean("fair​usage") == "fairusage"


def test_combining_marks_are_normalised_to_one_form() -> None:
    """A query normalised one way will not match a corpus normalised the other."""
    decomposed = "සි"
    composed = clean(decomposed)

    assert composed == clean(composed), "cleaning is not idempotent"
    import unicodedata

    assert composed == unicodedata.normalize("NFC", decomposed)


def test_whitespace_runs_collapse_but_paragraphs_survive() -> None:
    """Paragraph breaks are structure; a run of spaces is formatting."""
    assert clean("a    b") == "a b"
    assert clean("one\n\n\n\n\ntwo") == "one\n\ntwo"


# -- language ------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (SINHALA, Language.SI),
        (TAMIL, Language.TA),
        ("The fair usage policy applies to all unlimited packs on this network.", Language.EN),
    ],
)
def test_the_script_identifies_the_language(text: str, expected: Language) -> None:
    assert dominant_script(text) == expected


def test_too_little_text_is_no_evidence_rather_than_english() -> None:
    """Absence of evidence must not read as English.

    That is how a Sinhala document ends up tagged `en`: a short or
    mostly-numeric body detected as English, matching the declared language,
    and the mismatch check passing on nothing.
    """
    assert dominant_script("LKR 49") is None
    assert dominant_script("") is None


def test_a_source_whose_script_contradicts_its_language_is_refused() -> None:
    """Retrieval filters on the declared language, so a mismatch hides the text.

    Refused rather than corrected: guessing the owner meant Sinhala would
    republish legal text under a language nobody reviewed it in.
    """
    with pytest.raises(IngestionRefused, match="written in 'si' script"):
        ingest(source(language=Language.EN, body=SINHALA))


def test_a_correctly_tagged_sinhala_source_ingests() -> None:
    chunks = ingest(source(language=Language.SI, body=SINHALA))

    assert chunks
    assert all(chunk.language is Language.SI for chunk in chunks)


def test_singlish_is_not_refused_as_a_mismatch() -> None:
    """Latin script, Sinhala words. The script check must not reject it.

    C04 (#23) handles Singlish intake. A script check that refused Latin text
    declared as Sinhala would make a Singlish knowledge source unpublishable.
    """
    chunks = ingest(
        source(
            language=Language.SI,
            body="Mata data pack eka activate karanna barida? Mama try kalla but na.",
        )
    )

    assert chunks


# -- metadata ------------------------------------------------------------- #


def test_every_chunk_carries_the_full_filter_metadata() -> None:
    """Plan 22 section 7 lists the metadata retrieval needs on each chunk."""
    chunks = ingest(
        source(
            kind=SourceKind.CATALOGUE,
            body="Unlimited 1299.",
            product_ids=("P-1299",),
            audience=Audience.CUSTOMER,
        )
    )

    chunk = chunks[0]
    assert chunk.source_id == "TC-GENERAL"
    assert chunk.version == 1
    assert chunk.owner == "legal"
    assert chunk.audience is Audience.CUSTOMER
    assert chunk.language is Language.EN
    assert chunk.effective_from == EFFECTIVE
    assert chunk.effective_to is None
    assert chunk.product_ids == ("P-1299",)
    assert chunk.kind is SourceKind.CATALOGUE


def test_ingestion_is_deterministic_except_for_chunk_ids() -> None:
    """Same text in, same chunks out. K02 reindexing depends on it."""
    first = ingest(source())
    second = ingest(source())

    assert [chunk.text for chunk in first] == [chunk.text for chunk in second]
    assert [chunk.clause_ref for chunk in first] == [chunk.clause_ref for chunk in second]
    assert {chunk.chunk_id for chunk in first}.isdisjoint({chunk.chunk_id for chunk in second})
