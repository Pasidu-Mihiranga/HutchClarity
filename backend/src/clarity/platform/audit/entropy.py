"""Refuse low-entropy identifiers before they reach the trail (ADR-0033).

The audit assurance plan originally proposed a **keyed** ``payload_hash``: an
HMAC under a key held beside the checkpoint key, so that a plain SHA-256 of a
phone number could not be reversed by enumerating the ten million numbers a
Sri Lankan mobile prefix allows.

That was the wrong fix, for two reasons.

**It breaks verifiable export.** ``AuditLedger.proves`` exists so an auditor who
holds a document can confirm the ledger recorded *that* document, and plan
section 5.10 promises an export a regulator checks without trusting Clarity. A
keyed hash makes both impossible without the key, which only Clarity holds, so
the trail would be verifiable by Clarity alone, which is the property the whole
design is trying not to have.

**It protects the wrong field.** ``detail`` is stored in the clear, for a human
reading the trail. A phone number in ``detail`` is readable by anyone with
audit access and no hash, keyed or not, changes that.

So the control moved: rather than making the identifier's hash harder to
reverse, the identifier does not reach the ledger. Every append is screened and
a raw MSISDN, NIC, card number or email address is **refused**, in the payload
and in the detail alike. Nothing is quietly cleaned up: masking is never
optional (I13), so a caller that passes one has a defect, and a defect on the
audit path fails loudly rather than persisting personal data forever in an
append-only store that by design cannot be edited.

**Deliberately high precision, not high recall.** A false positive here fails a
real customer operation (ADR-0034: a state change that cannot be audited must
not happen), so each pattern needs a structural signal rather than a shape that
an identifier *might* have: the ``+94``/``07`` prefix for a number, the ``V``
suffix for an old NIC, a Luhn-valid digit run for a card. A bare twelve-digit
run is **not** treated as a new NIC, because a millisecond timestamp is also
twelve digits and refusing those would break honest callers. Recall is the
masker's job on the text path; this is a backstop on the audit path.

Pseudonyms pass, which is the point: ``subscriber_ref`` is already an HMAC of
the number (section 15), and ``mask_msisdn`` leaves four digits, so the forms
the codebase is supposed to use are the forms this allows.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

#: An identifier is a standalone token, never a digit run inside a longer
#: alphanumeric one. Without these boundaries the patterns read a stretch of a
#: SHA-256 hex digest or a base64 signature as a card number, which is not a
#: theoretical risk: a 64-character hex string carries a thirteen-digit run
#: often enough that the test suite hit it, and one in ten of those satisfies
#: Luhn. A boundary of "not a letter or digit" is also exactly right on the
#: merits, because a real number is written on its own, not welded into a hash.
_BEFORE = r"(?<![0-9A-Za-z])"
_AFTER = r"(?![0-9A-Za-z])"

#: A Sri Lankan number in any form that still carries every digit:
#: ``+94771234567``, ``0094771234567``, ``94771234567``, ``0771234567``,
#: with or without spaces and hyphens between the groups.
_MSISDN = re.compile(_BEFORE + r"\+?(?:94|0)[\s-]?[1-9]\d[\s-]?\d{3}[\s-]?\d{4}" + _AFTER)

#: Old-format NIC: nine digits and a V or X. The suffix is the structural
#: signal, so this cannot fire on an ordinary nine-digit number.
_NIC_OLD = re.compile(_BEFORE + r"\d{9}[VvXx]" + r"(?![0-9A-Za-z])")

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[A-Za-z]{2,}")

#: A candidate card number. Confirmed by Luhn before it is refused, because
#: thirteen to nineteen digits on its own is also a reference or a counter.
_CARD = re.compile(_BEFORE + r"(?:\d[\s-]?){12,18}\d" + _AFTER)

#: Keys whose value is never a customer identifier, so screening it is all cost
#: and no benefit. Narrow on purpose: an allowance here is a hole.
#:
#: Two kinds. **Pseudonyms and masked forms** are the shapes the codebase is
#: supposed to use, and they are allowed because they are the answer, not the
#: problem. **Opaque cryptographic material** is machine-generated and cannot
#: carry an identifier at all: a hash, a signature or a key id has no author who
#: could put a phone number in it, and screening one only invites the false
#: positive the boundaries above already mostly closed.
ALLOWED_KEYS: frozenset[str] = frozenset(
    {
        # pseudonyms and masked forms
        "subscriber_ref",
        "session_ref",
        "actor_ref",
        "masked",
        "masked_msisdn",
        "sent_to",
        # opaque cryptographic material
        "chain_hash",
        "chain_head",
        "prev_hash",
        "payload_hash",
        "detail_hash",
        "statement_hash",
        "signature",
        "kid",
        "public_key",
        "digest",
    }
)


class LowEntropyIdentifier(ValueError):
    """An append carried a raw identifier. The caller must pass a pseudonym.

    Raised rather than scrubbed: the value is a defect at its source, and the
    message names the path to it so the fix is in the caller, not here.
    """

    def __init__(self, kind: str, path: str) -> None:
        super().__init__(
            f"a raw {kind} reached the audit trail at {path or '<root>'}; "
            "pass a pseudonym (subscriber_ref) or a masked form instead"
        )
        self.kind = kind
        self.path = path


def _luhn(digits: str) -> bool:
    total, parity = 0, len(digits) % 2
    for index, char in enumerate(digits):
        value = int(char)
        if index % 2 == parity:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def _kind_in(text: str) -> str | None:
    """Which identifier ``text`` carries, if any. First match wins."""
    if _EMAIL.search(text):
        return "email address"
    if _NIC_OLD.search(text):
        return "NIC"
    if _MSISDN.search(text):
        return "phone number"
    for candidate in _CARD.finditer(text):
        digits = re.sub(r"\D", "", candidate.group())
        if 13 <= len(digits) <= 19 and _luhn(digits):
            return "card number"
    return None


def _strings(value: Any, path: str) -> Iterator[tuple[str, str]]:
    """Every string in a nested structure, with the path that reached it."""
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, item in value.items():
            if str(key) in ALLOWED_KEYS:
                continue
            yield from _strings(item, f"{path}.{key}" if path else str(key))
    elif isinstance(value, list | tuple):
        for index, item in enumerate(value):
            yield from _strings(item, f"{path}[{index}]")


def find_identifier(value: Any, *, path: str = "") -> tuple[str, str] | None:
    """The first raw identifier in ``value``, as ``(kind, path)``, or ``None``."""
    for where, text in _strings(value, path):
        kind = _kind_in(text)
        if kind is not None:
            return kind, where
    return None


def refuse_low_entropy(value: Any, *, path: str = "") -> None:
    """Raise :class:`LowEntropyIdentifier` if ``value`` carries a raw identifier."""
    found = find_identifier(value, path=path)
    if found is not None:
        raise LowEntropyIdentifier(*found)


__all__ = [
    "ALLOWED_KEYS",
    "LowEntropyIdentifier",
    "find_identifier",
    "refuse_low_entropy",
]
