"""Model roles, chains and quotas (issue #2, A01; I12, ADR-0009).

The two behaviours A01 exists for: the system answers with no model configured
at all, and a rate-limited provider costs a fallback rather than an outage. Both
matter because the prototype runs on free tiers, where 429 is the ordinary case.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

import clarity
from clarity.ai.buckets import Priority, ProviderQuota, TokenBuckets
from clarity.ai.gateway import Prompt, Usage
from clarity.ai.local import LOCAL_IMPLEMENTATIONS, RuleExtractor
from clarity.ai.providers import ProviderError, ProviderRateLimited
from clarity.ai.roles import ModelCatalogue, ModelConfigInvalid, ModelRole
from clarity.ai.routing import RoleRouter
from clarity.kernel.common import Language

CONFIG = Path(clarity.__file__).parents[3] / "config" / "ai" / "models.yaml"


@pytest.fixture
def catalogue() -> ModelCatalogue:
    """The real config, so these tests fail when it loses a local terminator."""
    return ModelCatalogue.from_file(CONFIG)


def a_prompt(text: str = "I was charged LKR 49 twice for a VAS subscription") -> Prompt:
    return Prompt(
        system="explain", facts={"outcome": "ONE_TAP_FIX"}, user_masked=text, language=Language.EN
    )


def _local_only(catalogue: ModelCatalogue) -> RoleRouter:
    """A router with only the local providers, as an unconfigured deployment has."""
    from clarity.ai.gateway import TemplateProvider

    router = RoleRouter(catalogue)
    router.register("template", TemplateProvider())
    router.register("local-bge", TemplateProvider())
    for name, implementation in LOCAL_IMPLEMENTATIONS.items():
        router.register(name, implementation())
    return router


# -- acceptance 1: no provider configured, every role still answers, 0 tokens #


@pytest.mark.parametrize("role", list(ModelRole))
def test_every_role_answers_with_no_provider_and_spends_nothing(
    role: ModelRole, catalogue: ModelCatalogue
) -> None:
    """ADR-0009: no model is the default, not a degraded mode."""
    router = _local_only(catalogue)

    answer = router.invoke(role, a_prompt())

    assert answer.text, f"the {role.value} role returned nothing"
    assert answer.spent_tokens == 0, "a local provider must spend no tokens"
    assert answer.role is role


def test_the_roles_that_cannot_work_locally_say_so_rather_than_inventing(
    catalogue: ModelCatalogue,
) -> None:
    """There is no honest local judge or speech-to-text.

    A fabricated score would be averaged by the evaluation harness and trusted
    by a release gate; a guessed transcript is invented customer input, which is
    what I2 exists to prevent. So both report the gap, and the answer is marked
    as a refusal so a caller can route to a person.
    """
    router = _local_only(catalogue)

    for role in (ModelRole.JUDGE, ModelRole.STT):
        answer = router.invoke(role, a_prompt())
        assert answer.is_refusal, f"{role.value} must admit it cannot answer"
        assert "unavailable" in answer.text or "unscored" in answer.text

    # And the roles that can work locally are not marked as refusals.
    for role in (ModelRole.FAST_TEXT, ModelRole.EXTRACT, ModelRole.REASON):
        assert not router.invoke(role, a_prompt()).is_refusal


def test_the_local_extract_path_reports_intents_without_deciding_anything(
    catalogue: ModelCatalogue,
) -> None:
    """I1: extraction narrows the candidates; it never supplies an amount."""
    answer = _local_only(catalogue).invoke(
        ModelRole.EXTRACT, a_prompt("charged twice for a VAS subscription, LKR 49")
    )

    assert "unauthorized_vas" in answer.text
    assert "duplicate_charge" in answer.text
    assert "amounts_mentioned=49" in answer.text, "reports what the customer said"
    assert answer.provider == RuleExtractor.name


# -- acceptance 2: a 429 on the primary falls through the chain -------------- #


class _RateLimited:
    """A provider that is always over its quota."""

    name = "rate-limited"

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, prompt: Prompt) -> tuple[str, Usage]:
        self.calls += 1
        raise ProviderRateLimited("429 from the provider", retry_after_seconds=30.0)


class _Working:
    """A provider that answers."""

    name = "working"

    def __init__(self, text: str = "the second provider answered") -> None:
        self.text = text
        self.calls = 0

    def complete(self, prompt: Prompt) -> tuple[str, Usage]:
        self.calls += 1
        return self.text, Usage(input_tokens=10, output_tokens=5)


def test_a_rate_limited_primary_falls_through_to_the_next_provider() -> None:
    """The free-tier case: 429 is routine, so it must cost a hop, not an error."""
    catalogue = ModelCatalogue.from_document(
        {
            "roles": {
                "reason": {
                    "primary": {"provider": "groq", "model": "primary-model"},
                    "fallback": [
                        {"provider": "gemini", "model": "second-model"},
                        {"provider": "template", "model": "local-template"},
                    ],
                }
            }
        }
    )
    primary, second = _RateLimited(), _Working()
    router = RoleRouter(catalogue, providers={"groq": primary, "gemini": second})

    answer = router.invoke(ModelRole.REASON, a_prompt())

    assert answer.provider == "gemini"
    assert answer.model == "second-model"
    assert answer.text == "the second provider answered"
    assert primary.calls == 1, "the primary was tried"
    assert second.calls == 1
    assert any("rate limited" in reason for reason in answer.skipped)


def test_a_provider_that_fails_for_another_reason_also_falls_through() -> None:
    class _Broken:
        name = "broken"

        def complete(self, prompt: Prompt) -> tuple[str, Usage]:
            raise ProviderError("returned a response that was not JSON")

    catalogue = ModelCatalogue.from_document(
        {
            "roles": {
                "reason": {
                    "primary": {"provider": "groq", "model": "a"},
                    "fallback": [{"provider": "gemini", "model": "b"}],
                }
            }
        }
    )
    router = RoleRouter(catalogue, providers={"groq": _Broken(), "gemini": _Working()})

    assert router.invoke(ModelRole.REASON, a_prompt()).provider == "gemini"


def test_an_unconfigured_step_is_skipped_rather_than_failing() -> None:
    """A deployment with no Groq key is a supported deployment."""
    catalogue = ModelCatalogue.from_document(
        {
            "roles": {
                "reason": {
                    "primary": {"provider": "groq", "model": "a"},
                    "fallback": [{"provider": "gemini", "model": "b"}],
                }
            }
        }
    )
    router = RoleRouter(catalogue, providers={"gemini": _Working()})

    answer = router.invoke(ModelRole.REASON, a_prompt())

    assert answer.provider == "gemini"
    assert any("not configured" in reason for reason in answer.skipped)


# -- quotas and priority ---------------------------------------------------- #


def test_batch_work_cannot_spend_the_share_reserved_for_customers() -> None:
    """The failure this prevents: a 3am batch job taking the whole day's quota.

    A customer asking "why was I charged" is the one request that must not be
    the one that fails, so a share of every window is theirs alone.
    """
    buckets = TokenBuckets()
    buckets.add(
        ProviderQuota(
            provider="groq",
            tokens_per_window=1000,
            window=timedelta(minutes=1),
            customer_reserve=0.3,
        )
    )

    # Batch may reach 700 of the 1000.
    buckets.claim("groq", tokens=700, priority=Priority.BATCH)
    assert buckets.remaining("groq", priority=Priority.BATCH) == 0

    with pytest.raises(Exception, match="allowance"):
        buckets.claim("groq", tokens=1, priority=Priority.BATCH)

    # The customer's 300 is untouched.
    assert buckets.remaining("groq", priority=Priority.CUSTOMER_LIVE) == 300
    buckets.claim("groq", tokens=300, priority=Priority.CUSTOMER_LIVE)


def test_an_exhausted_quota_falls_through_to_the_next_provider() -> None:
    catalogue = ModelCatalogue.from_document(
        {
            "roles": {
                "reason": {
                    "primary": {"provider": "groq", "model": "a"},
                    "fallback": [{"provider": "gemini", "model": "b"}],
                }
            }
        }
    )
    buckets = TokenBuckets()
    buckets.add(ProviderQuota(provider="groq", tokens_per_window=1, customer_reserve=0.0))
    primary, second = _Working("primary"), _Working("second")
    router = RoleRouter(catalogue, providers={"groq": primary, "gemini": second}, buckets=buckets)

    answer = router.invoke(ModelRole.REASON, a_prompt(), priority=Priority.BATCH)

    assert answer.provider == "gemini"
    assert primary.calls == 0, "a provider over quota is not called at all"


def test_a_window_resets(catalogue: ModelCatalogue) -> None:
    moments = [0.0]

    class _Clock:
        def __call__(self) -> object:
            from datetime import UTC, datetime

            return datetime.fromtimestamp(moments[0], tz=UTC)

    buckets = TokenBuckets(now=_Clock())  # type: ignore[arg-type]
    buckets.add(
        ProviderQuota(
            provider="groq",
            tokens_per_window=100,
            window=timedelta(seconds=60),
            customer_reserve=0.0,
        )
    )
    buckets.claim("groq", tokens=100, priority=Priority.BATCH)
    assert buckets.remaining("groq", priority=Priority.BATCH) == 0

    moments[0] += 61
    assert buckets.remaining("groq", priority=Priority.BATCH) == 100


# -- the config is a contract ----------------------------------------------- #


def test_the_real_config_declares_every_role(catalogue: ModelCatalogue) -> None:
    for role in ModelRole:
        assert catalogue.routing(role).chain, f"{role.value} has an empty chain"


def test_an_unknown_role_in_config_is_refused() -> None:
    with pytest.raises(ModelConfigInvalid, match="not a model role"):
        ModelCatalogue.from_document(
            {"roles": {"telepathy": {"primary": {"provider": "p", "model": "m"}}}}
        )


def test_a_chain_step_without_a_model_is_refused() -> None:
    with pytest.raises(ModelConfigInvalid, match="provider and a model"):
        ModelCatalogue.from_document({"roles": {"reason": {"primary": {"provider": "p"}}}})
