"""The turn verifier: step 9 of the turn lifecycle (C01, plan 22 section 4).

The verifier runs on what is about to be said, after composition and before the
customer sees it. It is the last place a wrong figure can be stopped, and it
exists because the composer is not always a template: `fast-text` writes from
FACTS, and a model that writes from facts can still write a number that is not
in them.

The rule it enforces is I1 from the output side. Rules decide amounts; this
checks that the sentence agrees. A figure in a reply that is not in FACTS came
from somewhere it should not have: the customer's own text, a model's
invention, or a template with a value baked in.

**Failures block, warnings do not.** A reply quoting an amount nobody decided
must not be sent. A reply that fell back to English because no Sinhala template
exists is worse than Sinhala and better than silence, so it is recorded and
sent. Collapsing the two would mean either shipping bad figures or refusing to
answer customers in the languages the templates do not cover yet.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from clarity.ai.pii import find_forbidden

#: Money-shaped figures: a run of digits that is either currency-prefixed, has
#: a decimal part, or is long enough to be an amount or an id in its own right.
#:
#: Deliberately not "every number". A template saying "within 24 hours" or "5
#: minutes" is not quoting an amount, and flagging it would train everyone to
#: ignore the verifier, which is the only failure mode that matters for a check
#: like this.
_FIGURE = re.compile(
    r"(?:(?:LKR|Rs\.?|රු|ரூ)\s*([\d,]+(?:\.\d{1,2})?))"  # currency prefixed
    r"|(\b\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?\b)"  # thousands separated
    r"|(\b\d+\.\d{2}\b)"  # decimal money
    r"|(\b\d{4,}\b)",  # long run: amount or identifier
    re.IGNORECASE,
)

#: Claims that an action already happened. Saying one of these when no action
#: executed is the single most damaging thing a reply can do: the customer stops
#: chasing a refund they never received.
_PROMISES = re.compile(
    r"\b(?:have|has been|already)\s+(?:refunded|credited|reversed|waived|paid)\b"
    r"|\brefund\s+(?:is|has been)\s+(?:complete|completed|done|processed)\b"
    r"|\bmoney\s+(?:is|has been)\s+(?:back|returned)\b"
    r"|\bI\s+(?:have\s+)?(?:refunded|credited|reversed|waived)\b",
    re.IGNORECASE,
)

#: Scripts, for checking the reply is in the language that was asked for.
_SCRIPTS = {
    "si": re.compile(r"[඀-෿]"),
    "ta": re.compile(r"[஀-௿]"),
}

#: Facts keys that mean an action really executed, so a promise is truthful.
_EXECUTED_KEYS = ("executed", "receipt_id", "action_id", "executed_at")


@dataclass(frozen=True)
class VerifierResult:
    """What the verifier concluded, in a form the audit can store.

    `ok` is the only thing the orchestrator branches on. The codes are stable so
    a trail is searchable years later, and the detail is kept out of them so no
    customer value lands in a code.
    """

    ok: bool
    failures: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def codes(self) -> tuple[str, ...]:
        return self.failures + self.warnings

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "failures": list(self.failures),
            "warnings": list(self.warnings),
            "detail": dict(self.detail),
        }


def verify_reply(
    reply: str,
    *,
    facts: Mapping[str, Any] | None = None,
    language: str = "en",
    citations: Sequence[str] = (),
    require_citations: bool = False,
) -> VerifierResult:
    """Check a composed reply against the facts it is supposed to come from.

    Args:
        reply: the text about to be sent.
        facts: the authoritative set. Every figure in the reply must appear here.
        language: the language the customer asked for.
        citations: source ids the reply cites, for knowledge answers.
        require_citations: whether this turn must cite. K03 (#33) sets this for
            knowledge states; a turn answering from case evidence does not.
    """
    known = _figures_in_facts(facts or {})
    failures: list[str] = []
    warnings: list[str] = []
    detail: dict[str, Any] = {}

    # Never, under any composition path. These are refused on the way in too
    # (the masker raises), so reaching here means something constructed one.
    forbidden = find_forbidden(reply)
    if forbidden:
        failures.append("FORBIDDEN_CONTENT")
        detail["forbidden"] = sorted(kind.value for kind in forbidden)

    unsupported = sorted(figure for figure in _figures_in(reply) if figure not in known)
    if unsupported:
        failures.append("NUMBER_NOT_IN_FACTS")
        detail["unsupported_figures"] = unsupported

    if _PROMISES.search(reply) and not _anything_executed(facts or {}):
        failures.append("UNAUTHORISED_PROMISE")

    if require_citations and not citations:
        failures.append("CITATION_MISSING")

    script = _SCRIPTS.get(language)
    if script is not None and not script.search(reply):
        # The template bundle has no entry for this language and fell back to
        # English. Recorded rather than blocked: see the module docstring.
        warnings.append("LANGUAGE_FALLBACK")
        detail["asked_language"] = language

    return VerifierResult(
        ok=not failures,
        failures=tuple(failures),
        warnings=tuple(warnings),
        detail=detail,
    )


def _figures_in(text: str) -> set[str]:
    """Every money-shaped figure in the text, normalised for comparison."""
    found: set[str] = set()
    for match in _FIGURE.finditer(text):
        raw = next((group for group in match.groups() if group), None)
        if raw:
            found.add(_normalise(raw))
    return found


def _figures_in_facts(facts: Mapping[str, Any]) -> set[str]:
    """Figures anywhere in the facts, however nested.

    Walks the whole structure rather than the top level: an amount that lives
    inside a nested evidence record is still a fact the reply may quote, and
    requiring callers to flatten first would make the verifier fail on correct
    replies, which is how a check ends up being switched off.
    """
    known: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, Mapping):
            for nested in value.values():
                walk(nested)
        elif isinstance(value, str | int | float):
            text = str(value)
            known.add(_normalise(text))
            known.update(_figures_in(text))
        elif isinstance(value, Sequence):
            for nested in value:
                walk(nested)

    walk(facts)
    return known


def _normalise(figure: str) -> str:
    """Compare figures by value, not by formatting.

    "1,500.00", "1500.00" and "1500" are the same amount, and a verifier that
    called them different would reject correct replies for having commas in
    them.
    """
    cleaned = figure.replace(",", "").strip()
    try:
        number = float(cleaned)
    except ValueError:
        return cleaned
    return str(int(number)) if number.is_integer() else f"{number:.2f}"


def _anything_executed(facts: Mapping[str, Any]) -> bool:
    return any(facts.get(key) for key in _EXECUTED_KEYS)


__all__ = ["VerifierResult", "verify_reply"]
