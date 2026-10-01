"""PII masking and the token vault (deck S8, plan §20.1).

Nothing reaches a language model in the clear. Text is scanned, personal
values are replaced with tokens, and only the tokens travel. The real values
stay in a vault inside the HUTCH boundary and are restored just before the
reply reaches the customer.

Two categories are treated differently:

- **Maskable** — phone numbers, NICs, names, emails, addresses. Replaced with
  a stable token like ``<PHONE_1>`` so the model can still refer to them
  consistently.
- **Forbidden** — OTPs, card numbers, CVVs, PINs. These are *never* tokenised
  and never stored: "OTPs and cards never sent" (deck S8). Finding one is a
  signal that something upstream is wrong, so the text is refused rather than
  cleaned up quietly.

**Prototype note.** Plan §20.1 uses Microsoft Presidio plus Sri Lankan
recognizers; here the recognizers are explicit regexes with structural
validation. That is narrower but auditable, and it keeps the prototype free of
a large ML dependency. Name detection in Sinhala and Tamil script is the known
weak spot (plan §20.1 limitations).
"""

from __future__ import annotations

import re
import secrets
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum

from clarity.schemas.common import utc_now


class PiiKind(StrEnum):
    PHONE = "PHONE"
    NIC = "NIC"
    EMAIL = "EMAIL"
    PASSPORT = "PASSPORT"
    NAME = "NAME"
    ACCOUNT = "ACCOUNT"


class ForbiddenKind(StrEnum):
    """Values that must never leave the trust boundary, masked or not."""

    OTP = "OTP"
    CARD = "CARD"
    CVV = "CVV"
    PIN = "PIN"


class ForbiddenContent(ValueError):
    """Text contained something that must never be sent to a model."""

    def __init__(self, kinds: set[ForbiddenKind]) -> None:
        listed = ", ".join(sorted(k.value for k in kinds))
        super().__init__(
            f"text contains {listed}, which is never sent to a model or stored by Clarity"
        )
        self.kinds = kinds


@dataclass(frozen=True)
class Match:
    kind: PiiKind
    start: int
    end: int
    value: str


# --------------------------------------------------------------------------- #
# Recognizers
# --------------------------------------------------------------------------- #

#: Sri Lankan mobile and landline numbers, with or without +94, spaces, hyphens.
_PHONE = re.compile(
    r"(?:\+94[\s-]?|0)(?:7\d|1\d|2\d|3\d|4\d|5\d|6\d|8\d|9\d)[\s-]?\d{3}[\s-]?\d{4}\b"
)

#: Old NIC: 9 digits + V or X. New NIC: 12 digits.
_NIC_OLD = re.compile(r"\b(\d{9})[VvXx]\b")
_NIC_NEW = re.compile(r"\b(\d{12})\b")

_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_PASSPORT = re.compile(r"\b[A-Z]\d{7}\b")
_ACCOUNT = re.compile(r"\b\d{10,16}\b")

#: Forbidden. Deliberately broad: a false positive costs a refused message,
#: a false negative leaks a credential.
_OTP = re.compile(r"\b(?:otp|pin|code|කේතය|குறியீடு)\D{0,12}(\d{4,8})\b", re.IGNORECASE)
_CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")
_CVV = re.compile(r"\b(?:cvv|cvc)\D{0,6}(\d{3,4})\b", re.IGNORECASE)


def _luhn(digits: str) -> bool:
    """Card numbers satisfy Luhn; most other long digit strings do not."""
    total, parity = 0, len(digits) % 2
    for index, char in enumerate(digits):
        value = int(char)
        if index % 2 == parity:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def _valid_new_nic(digits: str) -> bool:
    """A new NIC starts with a plausible birth year and day-of-year field."""
    year = int(digits[:4])
    day_field = int(digits[4:7])
    if not 1900 <= year <= utc_now().year:
        return False
    # 500 is added for women, so the day field is 1-366 or 501-866.
    return 1 <= day_field <= 366 or 501 <= day_field <= 866


def find_forbidden(text: str) -> set[ForbiddenKind]:
    """Detect values that must never be sent to a model."""
    found: set[ForbiddenKind] = set()
    if _OTP.search(text):
        found.add(ForbiddenKind.OTP)
    if _CVV.search(text):
        found.add(ForbiddenKind.CVV)
    for candidate in _CARD.finditer(text):
        digits = re.sub(r"\D", "", candidate.group())
        if 13 <= len(digits) <= 19 and _luhn(digits):
            found.add(ForbiddenKind.CARD)
    return found


def find_pii(text: str) -> list[Match]:
    """Find maskable personal data, longest matches first, without overlaps."""
    matches: list[Match] = []

    def add(
        kind: PiiKind,
        pattern: re.Pattern[str],
        validate: Callable[[re.Match[str]], bool] | None = None,
    ) -> None:
        for found in pattern.finditer(text):
            if validate is not None and not validate(found):
                continue
            matches.append(Match(kind, found.start(), found.end(), found.group()))

    add(PiiKind.EMAIL, _EMAIL)
    add(PiiKind.PHONE, _PHONE)
    add(PiiKind.NIC, _NIC_OLD)
    add(PiiKind.NIC, _NIC_NEW, lambda m: _valid_new_nic(m.group(1)))
    add(PiiKind.PASSPORT, _PASSPORT)
    add(PiiKind.ACCOUNT, _ACCOUNT)

    # Longest first so a phone number inside a longer account string wins once.
    matches.sort(key=lambda m: (m.start, -(m.end - m.start)))
    chosen: list[Match] = []
    cursor = -1
    for match in matches:
        if match.start >= cursor:
            chosen.append(match)
            cursor = match.end
    return chosen


# --------------------------------------------------------------------------- #
# Token vault
# --------------------------------------------------------------------------- #


@dataclass
class _Entry:
    value: str
    kind: PiiKind
    expires_at: datetime


class TokenVault:
    """Holds the token to real-value mapping, inside the trust boundary.

    Entries expire with the case (plan §20.1: "tokens expire with the case").

    **Prototype note.** Values are held in memory. Production encrypts them
    with a KMS data key in a separate service with its own access audit.
    """

    def __init__(self, *, ttl: timedelta = timedelta(days=1)) -> None:
        self._ttl = ttl
        self._entries: dict[str, _Entry] = {}
        self._restores = 0

    def store(self, token: str, value: str, kind: PiiKind, *, now: datetime | None = None) -> None:
        moment = now or utc_now()
        self._entries[token] = _Entry(value=value, kind=kind, expires_at=moment + self._ttl)

    def resolve(self, token: str, *, now: datetime | None = None) -> str | None:
        entry = self._entries.get(token)
        if entry is None:
            return None
        if (now or utc_now()) >= entry.expires_at:
            del self._entries[token]
            return None
        self._restores += 1
        return entry.value

    def purge(self, *, now: datetime | None = None) -> int:
        moment = now or utc_now()
        expired = [t for t, e in self._entries.items() if moment >= e.expires_at]
        for token in expired:
            del self._entries[token]
        return len(expired)

    @property
    def restore_count(self) -> int:
        """Audited: how many times real values were put back (plan §20.1)."""
        return self._restores

    def __len__(self) -> int:
        return len(self._entries)


# --------------------------------------------------------------------------- #
# Masking
# --------------------------------------------------------------------------- #


@dataclass
class MaskedText:
    """Text safe to send to a model, plus the tokens used."""

    text: str
    tokens: dict[str, str] = field(default_factory=dict)
    """token -> kind, for validating the model's reply. Never the real value."""

    @property
    def token_names(self) -> set[str]:
        return set(self.tokens)


class Masker:
    """Masks text before any model call, and restores afterwards."""

    #: A token looks like <PHONE_1>. The model is told to reuse these verbatim.
    _TOKEN = re.compile(r"<([A-Z]+)_(\d+)>")

    def __init__(self, vault: TokenVault | None = None) -> None:
        self.vault = vault or TokenVault()

    def mask(self, text: str, *, now: datetime | None = None) -> MaskedText:
        """Replace personal data with tokens.

        Raises :class:`ForbiddenContent` if the text contains an OTP, card
        number, CVV or PIN — those are never masked and sent, they are refused.
        """
        forbidden = find_forbidden(text)
        if forbidden:
            raise ForbiddenContent(forbidden)

        matches = find_pii(text)
        if not matches:
            return MaskedText(text=text)

        counters: dict[PiiKind, int] = {}
        seen: dict[str, str] = {}
        tokens: dict[str, str] = {}
        out: list[str] = []
        cursor = 0

        for match in matches:
            out.append(text[cursor : match.start])
            token = seen.get(match.value)
            if token is None:
                counters[match.kind] = counters.get(match.kind, 0) + 1
                token = f"<{match.kind.value}_{counters[match.kind]}>"
                seen[match.value] = token
                self.vault.store(token, match.value, match.kind, now=now)
                tokens[token] = match.kind.value
            out.append(token)
            cursor = match.end

        out.append(text[cursor:])
        return MaskedText(text="".join(out), tokens=tokens)

    def restore(self, text: str, *, now: datetime | None = None) -> str:
        """Put real values back, inside the trust boundary only."""

        def swap(match: re.Match[str]) -> str:
            return self.vault.resolve(match.group(0), now=now) or match.group(0)

        return self._TOKEN.sub(swap, text)

    def unknown_tokens(self, text: str, allowed: set[str]) -> set[str]:
        """Tokens in a model's reply that we never gave it.

        A model inventing ``<PHONE_9>`` is either confused or being steered, so
        the reply is rejected rather than restored (plan §12.6).
        """
        return {m.group(0) for m in self._TOKEN.finditer(text)} - allowed

    def leaks(self, text: str) -> list[Match]:
        """Real personal data appearing in text that should carry only tokens."""
        return find_pii(text)


def iter_tokens(text: str) -> Iterator[str]:
    for match in Masker._TOKEN.finditer(text):
        yield match.group(0)


def new_case_salt() -> str:
    """Per-case salt so tokens cannot be correlated across cases."""
    return secrets.token_hex(8)
