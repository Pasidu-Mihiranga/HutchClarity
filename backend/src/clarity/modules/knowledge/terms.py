"""Turning text into the terms an index matches on (K02, #32).

Retrieval is only as good as the agreement between how a document was indexed
and how a query was tokenised, so both go through this one module.

Three jobs, and the third is the one that earns its place.

**Tokenise per script.** Sinhala and Tamil do not put spaces where English does
and have no case, so a single `str.split().casefold()` under-tokenises them.
Splitting on Unicode word boundaries per script keeps each one's words whole.

**Fold English suffixes, and only English ones.** Sinhala and Tamil are
agglutinative and an English stemmer applied to romanised Sinhala mangles it
("gaasthu" to "gaasth"), while a correct stemmer for either language is a
model-sized problem. So `_fold` is guarded to ASCII tokens and applies a short
list of conservative English suffix rules.

The first version of this module folded only plural "s" and said the rest was
an honest limitation. Measuring the golden set showed what that cost: "travel
overseas" missed the clause that says "before travelling", and "how much I
spend" missed the one that says "spending limit". Two of the three misses in
the set were the same missing suffix rule, so the rule is the fix rather than
anything query-specific.

**Expand Singlish to the English the corpus is written in.** This is the part a
generic tokeniser cannot do and the reason acceptance 2 exists. A customer
writing "Mage wegaya adu karala ai?" is asking about speed reduction, and the
clause that answers it says "speed" and "reduced" in English. The content words
in that sentence are romanised Sinhala, not English, so no amount of
case-folding will match them: "wegaya" and "speed" share no characters.

So a query carries a small lexicon of romanised Sinhala domain words, mapped to
their English equivalents, and the expansion is **additive**: the original token
stays, because a Singlish corpus entry should still match on it.

The lexicon is deliberately small and domain-only. It is not a translator and
must not grow into one: a general Singlish lexicon would need a linguist and a
review process, and plan 20 is where that would live. These are the words that
appear in telecom billing complaints, taken from the `si-en` examples already in
`backend/tests/evaluation/datasets/intake.jsonl` (A05).

**ASSUMPTION**: the romanisations below are the common ones. Sinhala has no
standard romanisation, so a customer may write "gasthu", "gaasthu" or "gastu"
for the same word, and each spelling has to be listed to be matched.
**REQUIRES HUTCH CONFIRMATION** against real message traffic.
"""

from __future__ import annotations

import re
import unicodedata

#: Word characters per script. Sinhala and Tamil are matched as their own runs
#: so a mixed sentence tokenises both halves correctly.
_WORD = re.compile(r"[඀-෿]+|[஀-௿]+|[0-9]+|[^\W\d_]+", re.UNICODE)

#: English and Singlish function words. Dropped from a query because they match
#: everything and so rank nothing, and dropped from a document for the same
#: reason. Kept short: an over-long stoplist removes words that carry meaning in
#: a short query, and a knowledge query is usually short.
STOPWORDS = frozenset(
    {
        # English
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "but",
        "by",
        "can",
        "do",
        "does",
        "for",
        "from",
        "has",
        "have",
        "how",
        "i",
        "if",
        "in",
        "is",
        "it",
        "my",
        "me",
        "no",
        "not",
        "of",
        "on",
        "or",
        "that",
        "the",
        "this",
        "to",
        "was",
        "what",
        "when",
        "which",
        "why",
        "will",
        "with",
        "you",
        "your",
        # Singlish function words, from the A05 si-en examples. "mama" (I),
        # "mage" (my), "mata" (to me), "eka"/"eken"/"ekata"/"ekakata" (the,
        # inflected), "oya" (you), "meka" (this), "api" (we), "nam" (if).
        "mama",
        "mage",
        "mata",
        "api",
        "oya",
        "eka",
        "eken",
        "ekata",
        "ekakata",
        "ekak",
        "meka",
        "ara",
        "nam",
        "ba",
        "da",
    }
)

#: Romanised Sinhala domain words, mapped to the English the corpus uses.
#:
#: Additive: the original token is kept as well, so a Singlish document still
#: matches on it. Several spellings map to one English word because Sinhala has
#: no standard romanisation.
SINGLISH_TERMS: dict[str, tuple[str, ...]] = {
    # money and charges
    "gaasthu": ("charge", "fee"),
    "gasthu": ("charge", "fee"),
    "gastu": ("charge", "fee"),
    "rupiyal": ("rupee", "lkr"),
    "salli": ("money", "balance"),
    "mudal": ("money", "amount"),
    "gewila": ("paid", "charged"),
    "gewanna": ("pay",),
    "aragena": ("deducted", "taken"),
    # speed and data
    "wegaya": ("speed",),
    "wega": ("speed",),
    "adu": ("reduced", "low"),
    "aduwela": ("reduced",),
    "hemin": ("slow",),
    "dawasa": ("day",),
    # account actions
    "reload": ("reload", "recharge"),
    "dapu": ("made", "done"),
    "kala": ("did", "made"),
    "karala": ("done", "made"),
    "karanna": ("activate", "do"),
    "enne": ("received", "came"),
    "naththa": ("missing", "not"),
    "naththam": ("missing", "not"),
    "na": ("not",),
    "barida": ("cannot", "unable"),
    "bari": ("cannot", "unable"),
    "nodanne": ("unknown", "unrecognised"),
    "nathuwa": ("without",),
    # support
    "udawa": ("help", "support"),
    "prashnaya": ("problem", "issue"),
    "prashne": ("problem", "issue"),
    "awlak": ("problem", "fault"),
    "kohomada": ("how",),
    "ai": ("why",),
    "mokada": ("what", "why"),
    "kiyada": ("how much",),
    "kawada": ("when",),
}


def _folded_lexicon() -> dict[str, tuple[str, ...]]:
    """``SINGLISH_TERMS`` keyed by the form the tokeniser actually produces.

    The lexicon above is written in dictionary form because that is what a
    reviewer can read. Lookup happens *after* folding, so a key that folds
    ("nodanne" to "nodann", "prashne" to "prashn") would never be found and the
    entry would be dead. Two entries that fold together have their expansions
    merged rather than one silently replacing the other.
    """
    merged: dict[str, tuple[str, ...]] = {}
    for singlish, english in SINGLISH_TERMS.items():
        key = _fold(singlish)
        existing = merged.get(key, ())
        merged[key] = existing + tuple(term for term in english if term not in existing)
    return merged


def tokens(text: str) -> list[str]:
    """Index and query terms for one piece of text, stopwords removed.

    NFC first so Sinhala and Tamil combining marks compare the same way they
    were stored (K01 normalises the corpus the same way); a query normalised one
    form and a corpus the other share no terms at all.
    """
    normalised = unicodedata.normalize("NFC", text).casefold()
    found = [match.group(0) for match in _WORD.finditer(normalised)]
    return [_fold(token) for token in found if token not in STOPWORDS]


def query_terms(text: str) -> list[str]:
    """Terms for a query, with Singlish expanded to English.

    Expansion happens on the query and not on the corpus. Expanding the corpus
    would bake one lexicon into stored chunks, so improving the lexicon would
    mean re-indexing everything and old chunks would keep the old expansion.
    On the query it is applied fresh every time.
    """
    expanded: list[str] = []
    for token in tokens(text):
        expanded.append(token)
        # Both sides folded. The lexicon is written in dictionary form
        # ("balance", "charge") while the index holds folded stems ("balanc",
        # "charg"), so an unfolded expansion puts a term in the query that no
        # document can contain, and an unfolded *key* is never looked up at
        # all. Both were real bugs, and both were silent: an expansion that
        # matches nothing looks exactly like a feature that works.
        expanded.extend(_fold(term) for term in _LEXICON.get(token, ()))
    return expanded


#: Conservative English suffix rules, longest first so "ing" wins over "g".
#:
#: Each one keeps a stem of at least four characters, which is what stops
#: "ring" becoming "r" and "used" becoming "us". They are applied once, not
#: repeatedly: a loop turns "billing" into "bil" and then matches "bill",
#: "bills" and nothing useful.
#: The trailing "e" is in the list and matters more than it looks: without it
#: "reduced" folds to "reduc" while "reduce" stays "reduce", so the two forms
#: of the same word never meet. Same for "charges" and "charge". Stripping it
#: makes the stems agree, which is the whole point of folding.
_SUFFIXES: tuple[str, ...] = ("ingly", "edly", "ing", "ed", "ly", "es", "s", "e")

#: Stems that doubled their final consonant before the suffix: "travelling"
#: folds to "travell", which has to lose the double to meet "travel".
_DOUBLED = frozenset("bdglmnprt")


def _fold(token: str) -> str:
    """Fold one token to a stem, for Latin-script tokens only.

    Guarded three ways, because over-stemming creates false matches that are
    harder to notice than missed ones:

    - **ASCII only.** A Sinhala or Tamil word, or a romanised Sinhala one
      ending in a letter that happens to be "s", is not an English inflection.
    - **A stem of at least four characters**, so short words are left alone.
    - **"ss" is never a plural** ("address", "process").
    """
    if not token.isascii() or not token.isalpha() or len(token) < 5:
        return token
    if token.endswith("ss"):
        return token
    for suffix in _SUFFIXES:
        if not token.endswith(suffix):
            continue
        stem = token[: -len(suffix)]
        if len(stem) < 4:
            continue
        if len(stem) > 4 and stem[-1] == stem[-2] and stem[-1] in _DOUBLED:
            stem = stem[:-1]
        return stem
    return token


#: Built once, after ``_fold`` exists. Keyed by the folded form, so a lexicon
#: entry cannot be unreachable; asserted by
#: ``tests/unit/test_knowledge_terms.py``.
_LEXICON: dict[str, tuple[str, ...]] = _folded_lexicon()


__all__ = ["SINGLISH_TERMS", "STOPWORDS", "query_terms", "tokens"]
