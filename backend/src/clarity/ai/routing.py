"""Invoking a model role by walking its chain (A01, I12, ADR-0009).

A caller names a role and a priority. This walks that role's chain from
``config/ai/models.yaml`` and returns the first answer it can get:

1. a step whose provider is not configured is skipped, not an error, because a
   deployment with no Groq key is a supported deployment;
2. a step refused by the token buckets is skipped, because a free-tier ceiling
   reached by batch work must not take a customer's answer with it;
3. a step that is rate limited is skipped, which on a free tier is the ordinary
   case rather than an exception;
4. a step that fails for any other reason is skipped and recorded, because the
   next provider is a better answer than an error page.

Every chain ends in a local provider, so this cannot run out of steps. Two of
those local ends report that they cannot do the job instead of inventing a
result, and the answer says so, so a caller can tell "here is your explanation"
from "nobody could transcribe this, hand it to a person".
"""

from __future__ import annotations

from dataclasses import dataclass, field

from clarity.ai.buckets import Priority, QuotaExhausted, TokenBuckets
from clarity.ai.gateway import ModelProvider, Prompt, Usage
from clarity.ai.providers import ProviderError, ProviderRateLimited
from clarity.ai.roles import NON_ANSWERING_PROVIDERS, ModelCatalogue, ModelRole

#: Tokens assumed before a call, so a bucket can refuse before spending.
#: Corrected afterwards with what the provider reported.
ESTIMATED_TOKENS = 600


@dataclass(frozen=True)
class RoleAnswer:
    """What a role returned, and who answered."""

    role: ModelRole
    text: str
    provider: str
    model: str
    usage: Usage = field(default_factory=Usage)
    skipped: tuple[str, ...] = ()
    """Each step passed over, with the reason, for the trace and the devlog."""

    @property
    def is_refusal(self) -> bool:
        """Whether the answer is "I cannot do this" rather than a result."""
        return self.provider in NON_ANSWERING_PROVIDERS

    @property
    def spent_tokens(self) -> int:
        return self.usage.total


class RoleRouter:
    """Resolves a role to an answer by walking its configured chain."""

    def __init__(
        self,
        catalogue: ModelCatalogue,
        *,
        providers: dict[str, ModelProvider] | None = None,
        buckets: TokenBuckets | None = None,
    ) -> None:
        self._catalogue = catalogue
        # Keyed by the provider name used in models.yaml. A name with no entry
        # is simply not configured in this deployment.
        self._providers = dict(providers or {})
        self._buckets = buckets or TokenBuckets()

    def register(self, provider_name: str, provider: ModelProvider) -> None:
        self._providers[provider_name] = provider

    @property
    def configured(self) -> frozenset[str]:
        return frozenset(self._providers)

    def invoke(
        self,
        role: ModelRole,
        prompt: Prompt,
        *,
        priority: Priority = Priority.CUSTOMER_LIVE,
    ) -> RoleAnswer:
        """The first answer this role's chain can give."""
        routing = self._catalogue.routing(role)
        skipped: list[str] = []

        for step in routing.chain:
            provider = self._providers.get(step.provider)
            if provider is None:
                skipped.append(f"{step.provider}: not configured")
                continue

            if not step.is_local:
                try:
                    self._buckets.claim(step.provider, tokens=ESTIMATED_TOKENS, priority=priority)
                except QuotaExhausted as exhausted:
                    skipped.append(f"{step.provider}: {exhausted}")
                    continue

            try:
                text, usage = provider.complete(prompt)
            except ProviderRateLimited as limited:
                skipped.append(f"{step.provider}: rate limited ({limited})")
                continue
            except ProviderError as failed:
                skipped.append(f"{step.provider}: {failed}")
                continue

            if not step.is_local:
                # Replace the estimate with what was really spent.
                self._buckets.record(step.provider, tokens=usage.total - ESTIMATED_TOKENS)

            return RoleAnswer(
                role=role,
                text=text,
                provider=step.provider,
                model=step.model,
                usage=usage,
                skipped=tuple(skipped),
            )

        # Unreachable while every chain ends in a local provider, which
        # tests/architecture/test_no_model_ids.py enforces. If it is reached,
        # the config lost its local terminator and that is worth saying loudly
        # rather than returning an empty answer.
        raise ProviderError(
            f"the {role.value!r} chain produced no answer, having skipped: "
            + "; ".join(skipped)
            + ". Every role needs a local last step (ADR-0009)."
        )


__all__ = ["ESTIMATED_TOKENS", "RoleAnswer", "RoleRouter"]
