"""Local providers: the end of every role's chain (A01, ADR-0009).

Every chain in ``config/ai/models.yaml`` ends in one of these, so "no model is
configured" is a supported state rather than an outage. None of them makes a
network call or spends a token.

Three of them do real work. Two of them answer by saying they cannot, and that
is deliberate: there is no honest local way to judge an output's quality or to
transcribe speech. A fabricated score would be trusted by a release gate, and a
guessed transcript is invented customer input, which the whole system is built
to avoid (I2: text is a hint, never evidence). An admitted gap is an answer the
caller can act on; a made-up one is a lie that propagates.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from clarity.ai.gateway import Prompt, Usage

#: Keyword to intent, for the local `extract` path. Deliberately small and
#: reviewable: this decides nothing, it only narrows which events to look at
#: (I2), and C04 wants the rules tried before the model anyway.
INTENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "unauthorized_vas": ("vas", "subscription", "subscribed", "ringtone", "ගාස්තු", "சந்தா"),
    "reload_missing": ("reload", "recharge", "top up", "topup", "not credited", "රීලෝඩ්"),
    "duplicate_charge": ("twice", "double", "two times", "duplicate", "දෙවරක්"),
    "data_drain": ("data", "gb", "quota", "finished fast", "ඩේටා"),
    "loan_recovery": ("loan", "advance", "deducted", "ණය"),
}

#: Money-like figures, so the extractor can report an amount the customer named
#: without ever using it as the amount to refund (I1).
_AMOUNT = re.compile(r"(?:lkr|rs\.?)\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)", re.IGNORECASE)


@dataclass(frozen=True)
class LocalAnswer:
    """What a local provider returned, and whether it is a real result."""

    text: str
    usage: Usage
    is_refusal: bool = False
    """True when the provider is reporting that it cannot do the job."""


class RuleExtractor:
    """The local ``extract`` provider: keyword rules over the customer's text.

    Reports candidate intents and any figure the customer mentioned. It never
    decides a cause or an amount; those come from system records.
    """

    name = "local-rules"

    def complete(self, prompt: Prompt) -> tuple[str, Usage]:
        text = prompt.user_masked.lower()
        intents = [
            intent
            for intent, words in INTENT_KEYWORDS.items()
            if any(word in text for word in words)
        ]
        amounts = [match.group(1) for match in _AMOUNT.finditer(prompt.user_masked)]
        parts = [f"intents={','.join(intents) if intents else 'none'}"]
        if amounts:
            parts.append(f"amounts_mentioned={','.join(amounts)}")
        return " ".join(parts), Usage()


class UnscoredJudge:
    """The local ``judge`` provider. Returns no score, on purpose.

    Judging an answer's quality needs a model. Returning a number here would
    give the evaluation harness something to average and a release gate
    something to pass, both derived from nothing.
    """

    name = "local-unscored"

    def complete(self, prompt: Prompt) -> tuple[str, Usage]:
        return "unscored: no judge model is configured", Usage()


class UnavailableTranscription:
    """The local ``stt`` provider. Returns no transcript, on purpose.

    A guessed transcript is invented customer input. The conversation flow reads
    this as "no text", which routes the customer to a person rather than acting
    on words nobody said.
    """

    name = "local-unavailable"

    def complete(self, prompt: Prompt) -> tuple[str, Usage]:
        return "transcription unavailable: no speech-to-text model is configured", Usage()


#: Provider name in ``models.yaml`` -> the implementation that answers for it.
#: ``template`` and ``local-bge`` are bound by the composition root, which owns
#: the template registry and the embedding model.
LOCAL_IMPLEMENTATIONS: dict[str, type[RuleExtractor | UnscoredJudge | UnavailableTranscription]] = {
    RuleExtractor.name: RuleExtractor,
    UnscoredJudge.name: UnscoredJudge,
    UnavailableTranscription.name: UnavailableTranscription,
}


__all__ = [
    "INTENT_KEYWORDS",
    "LOCAL_IMPLEMENTATIONS",
    "LocalAnswer",
    "RuleExtractor",
    "UnavailableTranscription",
    "UnscoredJudge",
]
