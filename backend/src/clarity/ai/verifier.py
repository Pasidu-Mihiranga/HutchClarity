"""Deterministic output verifier (deck S7 "verifier checks numbers", plan §12.6).

Every sentence shown to a customer passes through here. The verifier does not
judge whether the text reads well - it checks that the text cannot mislead:

1. **Numbers.** Every amount, date and identifier in the text must appear in
   the FACTS the decision produced. A model that writes "LKR 499" when the
   decision says 49.00 is blocked, not corrected.
2. **Tokens.** No token we did not issue, and no raw personal data.
3. **Promises.** No commitment to refund, cancel or block unless the decision
   actually authorised it.
4. **Language.** The reply is in the language that was asked for.

A failed check never reaches the customer: the caller falls back to an
approved template (deck S7: "Works without the LLM").
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from clarity.ai.pii import Masker
from clarity.kernel.common import Language

#: Money and bare numbers. Thousands separators are allowed.
_NUMBER = re.compile(r"\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\b|\b\d+(?:\.\d+)?\b")

#: Identifiers a reply might quote: rule names, receipt and case numbers.
_IDENTIFIER = re.compile(r"\b(?:TR-\d{4}-\d{6}|CASE-\d{4}-\d{6}|[A-Z][A-Z0-9_]{4,})\b")

#: Promise language, per language. Matching one of these requires the decision
#: to permit the matching action.
_PROMISES: dict[str, tuple[str, ...]] = {
    "REFUND": ("refund", "refunded", "return your money", "money back", "ආපසු", "திரும்ப"),
    "DEACTIVATE_VAS": ("cancel", "cancelled", "switch off", "switched off", "unsubscrib"),
    "BLOCK_MERCHANT_UNTIL_OPTIN": ("block", "blocked", "blacklist"),
}

#: Script ranges used to check the reply is in the language that was asked for.
_SINHALA = re.compile(r"[඀-෿]")
_TAMIL = re.compile(r"[஀-௿]")


@dataclass
class Facts:
    """The deterministic values a reply is allowed to state.

    Built from the decision, never from a model. Anything numeric in the reply
    must be traceable to this.
    """

    amounts: set[Decimal] = field(default_factory=set)
    identifiers: set[str] = field(default_factory=set)
    allowed_actions: set[str] = field(default_factory=set)
    language: Language = Language.EN
    #: Numbers that may appear without being amounts, e.g. a rule version.
    plain_numbers: set[Decimal] = field(default_factory=set)

    def knows(self, value: Decimal) -> bool:
        return value in self.amounts or value in self.plain_numbers


@dataclass
class VerificationIssue:
    code: str
    detail: str


@dataclass
class VerificationResult:
    ok: bool
    issues: list[VerificationIssue] = field(default_factory=list)

    @property
    def summary(self) -> str:
        return "; ".join(f"{i.code}: {i.detail}" for i in self.issues) or "ok"


def _parse(text: str) -> Decimal | None:
    try:
        return Decimal(text.replace(",", ""))
    except (InvalidOperation, ValueError):
        return None


class OutputVerifier:
    """Checks model output against the facts. Deterministic and side-effect free."""

    def __init__(self, masker: Masker | None = None) -> None:
        self._masker = masker or Masker()

    def verify(
        self, text: str, facts: Facts, *, issued_tokens: set[str] | None = None
    ) -> VerificationResult:
        issues: list[VerificationIssue] = []
        issues += self._check_numbers(text, facts)
        issues += self._check_tokens(text, issued_tokens or set())
        issues += self._check_promises(text, facts)
        issues += self._check_language(text, facts.language)
        return VerificationResult(ok=not issues, issues=issues)

    # -- 1. numbers ------------------------------------------------------- #

    def _check_numbers(self, text: str, facts: Facts) -> list[VerificationIssue]:
        issues = []
        for found in _NUMBER.finditer(text):
            value = _parse(found.group())
            if value is None:
                continue
            if facts.knows(value):
                continue
            # A decimal amount that is not in the facts is always a problem.
            # A bare small integer may be a count or a date part, so it is only
            # rejected when it looks like money.
            looks_like_money = "." in found.group() or "," in found.group() or value >= 100
            if looks_like_money:
                issues.append(
                    VerificationIssue(
                        "UNVERIFIED_NUMBER",
                        f"{found.group()} does not appear in the case facts",
                    )
                )
        for found in _IDENTIFIER.finditer(text):
            token = found.group()
            if token not in facts.identifiers:
                issues.append(
                    VerificationIssue("UNVERIFIED_IDENTIFIER", f"{token} is not part of this case")
                )
        return issues

    # -- 2. tokens and leaked PII ---------------------------------------- #

    def _check_tokens(self, text: str, issued: set[str]) -> list[VerificationIssue]:
        issues = []
        invented = self._masker.unknown_tokens(text, issued)
        if invented:
            issues.append(
                VerificationIssue(
                    "INVENTED_TOKEN", f"reply refers to {', '.join(sorted(invented))}"
                )
            )
        leaks = self._masker.leaks(text)
        if leaks:
            kinds = ", ".join(sorted({leak.kind.value for leak in leaks}))
            issues.append(VerificationIssue("PII_IN_OUTPUT", f"reply contains {kinds}"))
        return issues

    # -- 3. promises ------------------------------------------------------ #

    @staticmethod
    def _check_promises(text: str, facts: Facts) -> list[VerificationIssue]:
        lowered = text.lower()
        issues = []
        for action, phrases in _PROMISES.items():
            if action in facts.allowed_actions:
                continue
            hit = next((p for p in phrases if p in lowered), None)
            if hit is not None:
                issues.append(
                    VerificationIssue(
                        "UNAUTHORISED_PROMISE",
                        f"reply says {hit!r} but the decision does not permit {action}",
                    )
                )
        return issues

    # -- 4. language ------------------------------------------------------ #

    @staticmethod
    def _check_language(text: str, language: Language) -> list[VerificationIssue]:
        has_sinhala = bool(_SINHALA.search(text))
        has_tamil = bool(_TAMIL.search(text))
        match language:
            case Language.SI if not has_sinhala:
                return [VerificationIssue("WRONG_LANGUAGE", "Sinhala was asked for")]
            case Language.TA if not has_tamil:
                return [VerificationIssue("WRONG_LANGUAGE", "Tamil was asked for")]
            case Language.EN if has_sinhala or has_tamil:
                return [VerificationIssue("WRONG_LANGUAGE", "English was asked for")]
        return []
