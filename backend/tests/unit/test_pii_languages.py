"""Masking covers all four languages, not just English (issue #4, A03; I13).

The golden set is the point of this file. Masking was tested on English
examples, and a Sinhala or Tamil name went to the model untouched: nothing in
the suite would have noticed, because nothing asked.

Two directions matter equally. A raw identifier surviving is a privacy failure.
Masking an ordinary word is a usefulness failure, and a reply built from text
with the nouns removed is not an explanation anyone can read. So every case
below is checked both ways.
"""

from __future__ import annotations

import pytest

from clarity.ai.pii import Masker, PiiKind, find_pii

#: (language, text, the raw substrings that must not survive).
#: Written as the deck promises them: Sinhala, Tamil, English and the Singlish
#: people actually type.
PII_SETS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "en",
        "My name is Dilani Perera, number 0781234567, NIC 912345678V",
        ("Dilani", "Perera", "0781234567", "912345678V"),
    ),
    (
        "en",
        "Please help Mr Nimal Fernando, email nimal@example.lk",
        ("Nimal", "Fernando", "nimal@example.lk"),
    ),
    (
        "si",
        "මගේ නම දිලානි පෙරේරා, දුරකථන 0781234567, හැඳුනුම්පත 912345678V",
        ("දිලානි", "පෙරේරා", "0781234567", "912345678V"),
    ),
    (
        "si",
        "මාගේ නම නිමල් බණ්ඩාර, අංකය +94 78 123 4567",
        ("නිමල්", "බණ්ඩාර", "+94 78 123 4567"),
    ),
    (
        "ta",
        "என் பெயர் திலானி பெரேரா, எண் 0781234567, அடையாள அட்டை 912345678V",
        ("திலானி", "பெரேரா", "0781234567", "912345678V"),
    ),
    (
        "ta",
        "எனது பெயர் ராஜன் குமார், எண் 0712345678",
        ("ராஜன்", "குமார்", "0712345678"),
    ),
    (
        "singlish",
        "mage nama Dilani Perera, number eka 078-123-4567 nic 199012345678",
        ("Dilani", "Perera", "078-123-4567", "199012345678"),
    ),
    (
        "singlish",
        "mama Silva, mata call karanna 0781234567 ekata",
        ("Silva", "0781234567"),
    ),
)

#: Ordinary complaints. None of these contains an identifier, so masking any of
#: it would be destroying the only text the model has to work from.
ORDINARY: tuple[tuple[str, str], ...] = (
    ("en", "I was charged LKR 49.00 twice for a VAS subscription yesterday"),
    ("en", "My data pack finished in two days, I am not happy"),
    ("en", "I am still waiting for a reply about my reload"),
    ("en", "Why was I charged for Anytime 10GB when I bought Anytime 5GB"),
    ("si", "මගේ ඩේටා පැකේජය දෙදිනකින් අවසන් විය"),
    ("si", "රීලෝඩ් එක බැංකුවෙන් කැපුණා නමුත් බැලන්ස් එකට ආවේ නැහැ"),
    ("ta", "எனது தரவு தொகுப்பு இரண்டு நாட்களில் முடிந்தது"),
    ("singlish", "mata VAS charge ekak awa, mama eka ganna nathi"),
)


# -- acceptance 1: no raw identifier survives, in any language ------------- #


@pytest.mark.parametrize(("language", "text", "raw"), PII_SETS, ids=lambda v: str(v)[:28])
def test_no_raw_identifier_survives_masking(language: str, text: str, raw: tuple[str, ...]) -> None:
    masked = Masker().mask(text).text

    survived = [value for value in raw if value in masked]
    assert survived == [], (
        f"[{language}] these identifiers reached the model unmasked: {survived}\n"
        f"  original: {text}\n  masked:   {masked}"
    )


@pytest.mark.parametrize(("language", "text", "raw"), PII_SETS, ids=lambda v: str(v)[:28])
def test_masking_replaces_with_a_token_rather_than_deleting(
    language: str, text: str, raw: tuple[str, ...]
) -> None:
    """The model still needs to know something was there, and what kind."""
    masked = Masker().mask(text)

    assert "<" in masked.text, f"[{language}] nothing was tokenised"
    assert masked.tokens, "the vault must record what each token stands for"
    assert all(kind in {k.value for k in PiiKind} for kind in masked.tokens.values())


def test_a_name_is_found_in_every_language() -> None:
    """Pinned separately, because this is the gap A03 found.

    `PiiKind.NAME` existed with no detector behind it, so numbers and NICs were
    masked while the customer's name was not, in all four languages.
    """
    for language, text, _ in PII_SETS:
        kinds = {match.kind for match in find_pii(text)}
        assert PiiKind.NAME in kinds, f"[{language}] no name detected in: {text}"


# -- the other direction: ordinary text is left alone --------------------- #


@pytest.mark.parametrize(("language", "text"), ORDINARY, ids=lambda v: str(v)[:28])
def test_an_ordinary_complaint_is_not_masked(language: str, text: str) -> None:
    masked = Masker().mask(text).text

    assert masked == text, (
        f"[{language}] masking changed a complaint that contains no identifier.\n"
        f"  original: {text}\n  masked:   {masked}\n"
        "Over-masking leaves the model nothing to explain from."
    )


# -- the restore path ------------------------------------------------------ #


@pytest.mark.parametrize(("language", "text", "raw"), PII_SETS, ids=lambda v: str(v)[:28])
def test_a_reply_can_be_restored_in_every_language(
    language: str, text: str, raw: tuple[str, ...]
) -> None:
    """A token is only useful if the reply can be turned back into readable text."""
    masker = Masker()
    masked = masker.mask(text)

    # A reply that reuses the tokens verbatim, as the model is instructed to.
    reply = " ".join(f"<{token}>" for token in masked.token_names)
    restored = masker.restore(reply)

    for token in masked.token_names:
        assert f"<{token}>" not in restored, f"[{language}] {token} was not restored"
