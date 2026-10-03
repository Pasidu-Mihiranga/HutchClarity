"""Turning a governed source into retrievable chunks (K01, #31).

Plan 22 section 7: parse, clean, language tag, structure-aware chunking,
metadata. "Structure-aware" is the part that matters and the part a generic
splitter gets wrong.

**Why chunk by structure rather than by length.** A legal answer has to cite
``source_id@version#clause``. A fixed-size window cuts across clause
boundaries, so a chunk contains the end of 4.1 and the start of 4.2 and can
honestly cite neither. Chunking per clause means every chunk has exactly one
clause reference, and the citation verifier (K03) has something real to check.
Length only comes into it when a single clause is too long to retrieve well,
and then the pieces keep their clause reference and overlap so a sentence split
across the seam is still findable.

**A catalogue entry is one chunk**, whatever its length. An offering is the unit
someone asks about: splitting "Unlimited 1299" into three pieces means a query
about its price can retrieve the piece that does not mention the price.

**Token counts are word counts.** No tokeniser is a runtime dependency, and a
word count runs about 25 to 35 percent under a subword tokeniser for English
and further under for Sinhala and Tamil. The window is therefore approximate,
and deliberately so: it decides retrieval quality, not an outcome for a
customer, and an approximate window that needs no model is worth more here than
an exact one that does. Named `WORDS_*` rather than `TOKENS_*` so nobody reads
it as exact.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable

from clarity.kernel.common import Language
from clarity.kernel.ids import new_id
from clarity.modules.knowledge.sources import Chunk, KnowledgeSource, SourceKind

#: Target chunk size for legal text, in words. Plan 22 section 7 says 300 to
#: 500 tokens; see the note above on why these are words.
WORDS_PER_CHUNK = 320

#: Overlap between pieces of one over-long clause, in words (10 to 15 percent).
WORDS_OF_OVERLAP = 40

#: A clause marker at the start of a line: ``4``, ``4.2``, ``4.2.1``, ``(a)``.
#: Anchored to the line start because a reference to clause 4.2 *inside* a
#: sentence is a cross-reference, not the beginning of a new clause.
_CLAUSE = re.compile(
    r"^\s*(?P<ref>(?:\d+(?:\.\d+)*)|(?:\([a-z0-9]{1,3}\)))[.)]?\s+(?=\S)",
    re.MULTILINE,
)

#: Unicode blocks that identify a script without ambiguity.
_SINHALA = range(0x0D80, 0x0E00)
_TAMIL = range(0x0B80, 0x0C00)


#: How a kind turns one structural piece into one or more chunks.
_Windowing = Callable[[str], list[str]]


class IngestionRefused(ValueError):
    """The source cannot be ingested as published."""


def clean(text: str) -> str:
    """Normalise without changing meaning.

    NFC first, because Sinhala and Tamil combining marks compare and index
    differently depending on form, and a query normalised one way will not
    match a corpus normalised the other. Then collapse runs of whitespace,
    which is formatting rather than content, and strip zero-width characters
    that survive copy and paste out of a PDF and silently break a substring
    match.
    """
    normalised = unicodedata.normalize("NFC", text)
    without_invisibles = re.sub(r"[​-‏‪-‮﻿]", "", normalised)
    collapsed = re.sub(r"[ \t]+", " ", without_invisibles)
    return re.sub(r"\n{3,}", "\n\n", collapsed).strip()


def dominant_script(text: str) -> Language | None:
    """The language the script says this is, or ``None`` when it cannot tell.

    Script, not language: it separates Sinhala and Tamil from Latin reliably
    and says nothing about Singlish, which is Latin script. ``None`` means "no
    evidence", never "English", because treating absence of evidence as English
    is how a Sinhala document ends up tagged ``en``.
    """
    sinhala = tamil = latin = 0
    for char in text:
        point = ord(char)
        if point in _SINHALA:
            sinhala += 1
        elif point in _TAMIL:
            tamil += 1
        elif char.isalpha() and point < 0x0250:
            latin += 1

    counted = sinhala + tamil + latin
    if counted < 20:
        return None
    if sinhala / counted > 0.2:
        return Language.SI
    if tamil / counted > 0.2:
        return Language.TA
    if latin / counted > 0.8:
        return Language.EN
    return None


def check_language(source: KnowledgeSource) -> None:
    """Refuse a source written in a script its declared language cannot be.

    The declared language is governed metadata an owner sets, and retrieval
    filters on it, so a Sinhala clause tagged ``en`` is invisible to Sinhala
    speakers and quoted to English ones. The script is the one part of that
    claim a machine can check.

    **The check is asymmetric, and has to be.** Sinhala or Tamil script in a
    document declared ``en`` is unambiguously wrong: English is not written in
    those scripts. Latin script in a document declared ``si`` or ``ta`` is
    **not** wrong, because that is Singlish or romanised Tamil, which is how a
    great many customers actually write (C04, #23). A symmetric check would
    make a Singlish knowledge source unpublishable, which is the opposite of
    what the language metadata is for.

    A disagreement is refused rather than corrected. Guessing the owner meant
    the other thing would silently republish legal text under a language nobody
    reviewed it in.
    """
    detected = dominant_script(source.body)
    if detected is None or detected is source.language:
        return
    if detected is Language.EN:
        # Latin script under a Sinhala or Tamil declaration: romanised, not
        # mislabelled. Nothing here can tell those apart, and refusing would
        # be the more damaging guess.
        return
    raise IngestionRefused(
        f"{source.ref}: declared language {source.language.value!r} but the text is written "
        f"in {detected.value!r} script, which that language is not written in; correct the "
        "metadata or the text rather than publishing a mismatch, because retrieval filters "
        "on the declared language"
    )


def ingest(source: KnowledgeSource) -> tuple[Chunk, ...]:
    """Chunk one source version, carrying its metadata onto every chunk."""
    check_language(source)
    body = clean(source.body)

    if source.kind is SourceKind.CATALOGUE:
        # One chunk per offering per version, whatever the length, so it never
        # goes through the window below. An offering is the unit someone asks
        # about: split into three, a question about the price can retrieve the
        # piece that does not mention the price.
        pieces = [("", body)]
        windows: _Windowing = _one_piece
    elif source.kind is SourceKind.LEGAL_TEXT:
        pieces = _by_clause(body, prefix=source.clause_prefix)
        windows = _windows
    else:
        pieces = [("", block) for block in _by_paragraph(body)]
        windows = _windows

    chunks: list[Chunk] = []
    for text, clause_ref in ((text, ref) for ref, text in pieces):
        for window in windows(text):
            chunks.append(
                Chunk(
                    chunk_id=new_id("CHK"),
                    source_id=source.source_id,
                    version=source.version,
                    ordinal=len(chunks),
                    text=window,
                    title=source.title,
                    clause_ref=clause_ref,
                    kind=source.kind,
                    owner=source.owner,
                    audience=source.audience,
                    language=source.language,
                    effective_from=source.effective_from,
                    effective_to=source.effective_to,
                    product_ids=source.product_ids,
                )
            )
    if not chunks:
        raise IngestionRefused(f"{source.ref}: ingestion produced no chunks")
    return tuple(chunks)


# -- chunking ------------------------------------------------------------ #


def _by_clause(body: str, *, prefix: str) -> list[tuple[str, str]]:
    """Split legal text into (clause_ref, text), one entry per clause.

    Text before the first marker keeps an empty reference: a preamble is real
    content and dropping it would lose it, but it is not clause 1 and must not
    be cited as one.
    """
    markers = list(_CLAUSE.finditer(body))
    if not markers:
        return [("", block) for block in _by_paragraph(body)]

    pieces: list[tuple[str, str]] = []
    preamble = body[: markers[0].start()].strip()
    if preamble:
        pieces.append(("", preamble))

    for position, marker in enumerate(markers):
        end = markers[position + 1].start() if position + 1 < len(markers) else len(body)
        text = body[marker.start() : end].strip()
        if not text:
            continue
        ref = marker.group("ref")
        pieces.append((f"{prefix} {ref}".strip() if prefix else ref, text))
    return pieces


def _by_paragraph(body: str) -> list[str]:
    blocks = [block.strip() for block in re.split(r"\n\s*\n", body)]
    return [block for block in blocks if block] or ([body.strip()] if body.strip() else [])


def _one_piece(text: str) -> list[str]:
    """No windowing: the piece is the chunk, whatever its length."""
    return [text] if text.strip() else []


def _windows(text: str) -> list[str]:
    """One piece per chunk, unless the piece is too long to retrieve well.

    The overlap exists so a sentence that lands on a seam is still matchable
    from either side; without it a query quoting across the boundary matches
    nothing.
    """
    words = text.split()
    if len(words) <= WORDS_PER_CHUNK:
        return [text] if words else []

    stride = WORDS_PER_CHUNK - WORDS_OF_OVERLAP
    return [
        " ".join(words[start : start + WORDS_PER_CHUNK])
        for start in range(0, len(words), stride)
        # A tail shorter than the overlap is entirely inside the previous
        # window, so emitting it would be a duplicate chunk.
        if start == 0 or len(words) - start > WORDS_OF_OVERLAP
    ]


__all__ = [
    "WORDS_OF_OVERLAP",
    "WORDS_PER_CHUNK",
    "IngestionRefused",
    "check_language",
    "clean",
    "dominant_script",
    "ingest",
]
