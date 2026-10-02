"""AI gateway: the single point every model call goes through (plan §7.2 T6, §12.2).

It owns the four-tier routing from deck S14 - templates, then cache, then a
small model, then a reasoning model - and, more importantly, it owns the
guarantees that must hold no matter which tier answers:

- masking happens before the call, never inside a provider;
- the verifier runs on whatever comes back;
- a failure falls back to a template rather than to nothing;
- tokens and cost are counted per call.

**No model is configured by default.** The prototype ships
:class:`TemplateProvider`, which answers from approved templates with zero
tokens. That is not a stub standing in for missing work: deck S7 states Clarity
"works without the LLM", and this is that path, running for real. Plugging in a
hosted or self-hosted model means implementing :class:`ModelProvider` - the
guardrails around it do not change.
"""

from __future__ import annotations

import hashlib
from collections import OrderedDict
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Protocol, runtime_checkable

from clarity.ai.pii import ForbiddenContent, Masker
from clarity.ai.verifier import Facts, OutputVerifier, VerificationResult
from clarity.contracts.decision import Decision, Outcome
from clarity.kernel.common import Language
from clarity.platform.content.templates import explanation as template_explanation


class Tier(StrEnum):
    """Where an answer came from (deck S14)."""

    TEMPLATE = "template"
    CACHE = "cache"
    SMALL_MODEL = "small_model"
    REASONING_MODEL = "reasoning_model"


@dataclass
class Usage:
    """Token accounting, for the AI disclosure (Guidelines §6.1)."""

    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class Answer:
    """What the gateway returns. Always safe to show a customer."""

    text: str
    tier: Tier
    usage: Usage = field(default_factory=Usage)
    verified: bool = True
    fell_back: bool = False
    verification: VerificationResult | None = None
    model: str | None = None


@dataclass
class Prompt:
    """A request for language, already masked.

    ``facts`` is the deterministic record the reply must agree with; the
    provider sees it as read-only context and can never add to it.
    """

    system: str
    facts: dict[str, object]
    user_masked: str
    language: Language


@runtime_checkable
class ModelProvider(Protocol):
    """What a real model implementation has to offer."""

    name: str

    def complete(self, prompt: Prompt) -> tuple[str, Usage]: ...


class TemplateProvider:
    """Answers from approved templates. Zero tokens, cannot hallucinate."""

    name = "templates"

    def complete(self, prompt: Prompt) -> tuple[str, Usage]:
        rule_id = prompt.facts.get("rule_id")
        amount = prompt.facts.get("amount_lkr")
        outcome = prompt.facts.get("outcome")
        return (
            template_explanation(
                rule_id=str(rule_id) if rule_id else None,
                outcome=Outcome(str(outcome)) if outcome else Outcome.HANDOFF,
                amount=Decimal(str(amount)) if amount is not None else None,
                language=prompt.language,
            ),
            Usage(),
        )


class _AnswerCache:
    """Tier 2: generic answers only (deck S14, "HOW THE CACHE STAYS SAFE").

    Keyed by language plus the facts that make an answer generic. A reply that
    mentions a specific amount is never cached, because serving it to another
    customer would state someone else's number as fact.
    """

    def __init__(self, max_entries: int = 512) -> None:
        self._entries: OrderedDict[str, str] = OrderedDict()
        self._max = max_entries
        self.hits = 0
        self.misses = 0

    @staticmethod
    def _key(prompt: Prompt) -> str:
        material = f"{prompt.language}|{prompt.facts.get('rule_id')}|{prompt.facts.get('outcome')}"
        return hashlib.sha256(material.encode()).hexdigest()

    @staticmethod
    def _is_generic(prompt: Prompt) -> bool:
        amount = prompt.facts.get("amount_lkr")
        return amount in (None, "0.00", Decimal("0.00"))

    def get(self, prompt: Prompt) -> str | None:
        if not self._is_generic(prompt):
            return None
        found = self._entries.get(self._key(prompt))
        if found is None:
            self.misses += 1
            return None
        self.hits += 1
        self._entries.move_to_end(self._key(prompt))
        return found

    def put(self, prompt: Prompt, text: str) -> None:
        if not self._is_generic(prompt):
            return
        self._entries[self._key(prompt)] = text
        self._entries.move_to_end(self._key(prompt))
        while len(self._entries) > self._max:
            self._entries.popitem(last=False)


_SYSTEM_PROMPT = """You are Hutch Clarity. Explain a telecom charge to a customer.

Rules you must follow:
- State only what appears in FACTS. Never introduce an amount, date or
  identifier that is not there.
- Do not promise any action that is not listed in FACTS.allowed_actions.
- Keep placeholders like <PHONE_1> exactly as written.
- Reply only in the requested language. Be brief, plain and calm.
"""


class AIGateway:
    """Routes a request through the tiers and enforces the guardrails."""

    def __init__(
        self,
        *,
        provider: ModelProvider | None = None,
        masker: Masker | None = None,
        verifier: OutputVerifier | None = None,
        prefer_templates: bool = True,
    ) -> None:
        self.masker = masker or Masker()
        self.verifier = verifier or OutputVerifier(self.masker)
        self.provider = provider or TemplateProvider()
        self.cache = _AnswerCache()
        self._prefer_templates = prefer_templates
        self.calls: list[Answer] = []

    # ------------------------------------------------------------------ #

    def explain(
        self,
        decision: Decision,
        *,
        rule_id: str | None,
        language: Language = Language.EN,
        customer_text: str | None = None,
    ) -> Answer:
        """Produce a customer-facing explanation of a decision.

        The decision is the source of truth. Customer text, if any, is masked
        and passed only as context - it is a hint, never evidence (deck S7).
        """
        facts = self._facts(decision, rule_id)
        issued_tokens: set[str] = set()
        masked_user = ""

        if customer_text:
            try:
                masked = self.masker.mask(customer_text)
                masked_user, issued_tokens = masked.text, masked.token_names
            except ForbiddenContent:
                # An OTP or card in the message means we drop the text entirely
                # and answer from the record alone.
                masked_user, issued_tokens = "", set()

        prompt = Prompt(
            system=_SYSTEM_PROMPT, facts=facts, user_masked=masked_user, language=language
        )

        # Tier 1 - templates. Deterministic, free, and always correct.
        if self._prefer_templates or isinstance(self.provider, TemplateProvider):
            return self._record(
                Answer(text=self._template(decision, rule_id, language), tier=Tier.TEMPLATE)
            )

        # Tier 2 - cache of generic answers.
        cached = self.cache.get(prompt)
        if cached is not None:
            return self._record(Answer(text=cached, tier=Tier.CACHE))

        # Tier 3/4 - a model, then verify what it wrote.
        try:
            text, usage = self.provider.complete(prompt)
        except Exception:
            return self._record(
                Answer(
                    text=self._template(decision, rule_id, language),
                    tier=Tier.TEMPLATE,
                    fell_back=True,
                )
            )

        checked = self.verifier.verify(
            text, self._verifier_facts(decision, rule_id, language), issued_tokens=issued_tokens
        )
        if not checked.ok:
            return self._record(
                Answer(
                    text=self._template(decision, rule_id, language),
                    tier=Tier.TEMPLATE,
                    usage=usage,
                    verified=False,
                    fell_back=True,
                    verification=checked,
                    model=self.provider.name,
                )
            )

        restored = self.masker.restore(text)
        self.cache.put(prompt, restored)
        return self._record(
            Answer(
                text=restored,
                tier=Tier.SMALL_MODEL,
                usage=usage,
                verification=checked,
                model=self.provider.name,
            )
        )

    # ------------------------------------------------------------------ #

    @staticmethod
    def _template(decision: Decision, rule_id: str | None, language: Language) -> str:
        return template_explanation(
            rule_id=rule_id,
            outcome=decision.outcome,
            amount=decision.amount_lkr,
            language=language,
        )

    @staticmethod
    def _facts(decision: Decision, rule_id: str | None) -> dict[str, object]:
        return {
            "rule_id": rule_id,
            "outcome": decision.outcome.value,
            "amount_lkr": None if decision.amount_lkr is None else f"{decision.amount_lkr:.2f}",
            "allowed_actions": [a.value for a in decision.allowed_actions],
            "policy_version": decision.policy_version,
            "ruled_out": [c.rule_id for c in decision.ruled_out],
        }

    @staticmethod
    def _verifier_facts(decision: Decision, rule_id: str | None, language: Language) -> Facts:
        amounts = {decision.amount_lkr} if decision.amount_lkr is not None else set()
        identifiers = {c.rule_id for c in decision.ruled_out}
        if rule_id:
            identifiers.add(rule_id)
        return Facts(
            amounts=amounts,
            identifiers=identifiers,
            allowed_actions={a.value for a in decision.allowed_actions},
            language=language,
        )

    def _record(self, answer: Answer) -> Answer:
        self.calls.append(answer)
        return answer

    # ------------------------------------------------------------------ #

    @property
    def usage_summary(self) -> dict[str, object]:
        """Measured token usage, for the AI disclosure (Guidelines §6.2)."""
        total_in = sum(a.usage.input_tokens for a in self.calls)
        total_out = sum(a.usage.output_tokens for a in self.calls)
        by_tier: dict[str, int] = {}
        for answer in self.calls:
            by_tier[answer.tier.value] = by_tier.get(answer.tier.value, 0) + 1
        return {
            "calls": len(self.calls),
            "input_tokens": total_in,
            "output_tokens": total_out,
            "total_tokens": total_in + total_out,
            "by_tier": by_tier,
            "llm_free_share": (by_tier.get("template", 0) + by_tier.get("cache", 0))
            / len(self.calls)
            if self.calls
            else 1.0,
            "fallbacks": sum(1 for a in self.calls if a.fell_back),
            "cache_hits": self.cache.hits,
        }
