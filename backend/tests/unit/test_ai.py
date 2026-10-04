"""AI guardrail tests (deck S7, S8, plan §12.6, §20.1).

The AI layer is the one place where untrusted text meets the system, so these
tests are mostly about what must *not* happen: personal data reaching a model,
a credential being stored, an invented number reaching a customer, or a promise
nobody authorised.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from clarity.ai.gateway import AIGateway, Prompt, Tier, Usage
from clarity.ai.pii import (
    ForbiddenContent,
    Masker,
    PiiKind,
    TokenVault,
    find_forbidden,
    find_pii,
)
from clarity.ai.verifier import Facts, OutputVerifier
from clarity.contracts.decision import ActionType, Decision, Outcome
from clarity.kernel.common import Language, utc_now
from clarity.kernel.ids import new_id
from clarity.platform.content.templates import explanation, has_template


def a_decision(**overrides) -> Decision:
    defaults = {
        "decision_id": new_id("DEC"),
        "case_id": "CASE-T",
        "outcome": Outcome.ONE_TAP_FIX,
        "policy_version": "test.1",
        "input_hash": "sha256:test",
        "allowed_actions": [ActionType.REFUND, ActionType.DEACTIVATE_VAS],
        "amount_lkr": "49.00",
        "top_cause_ref": "VAS_NO_CONSENT@4",
    }
    return Decision(**(defaults | overrides))


# --------------------------------------------------------------------------- #
# PII detection and masking
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "text",
    [
        "call me on 0781234567",
        "my number is +94 78 123 4567",
        "078-123-4567 was charged",
    ],
)
def test_phone_numbers_are_detected_in_any_format(text):
    assert any(m.kind is PiiKind.PHONE for m in find_pii(text))


@pytest.mark.parametrize("nic", ["951234567V", "199512345678"])
def test_both_nic_formats_are_detected(nic):
    assert any(m.kind is PiiKind.NIC for m in find_pii(f"my NIC is {nic}"))


def test_a_long_number_that_is_not_a_nic_is_not_called_one():
    """A new NIC has a plausible birth year and day field; this has neither."""
    kinds = {m.kind for m in find_pii("reference 999999999999")}

    assert PiiKind.NIC not in kinds


def test_masking_replaces_personal_data_and_keeps_the_rest():
    masker = Masker()
    original = "I am Nimal, 0781234567, NIC 951234567V - LKR 49.00 was taken"

    masked = masker.mask(original)

    assert "0781234567" not in masked.text
    assert "951234567V" not in masked.text
    assert "LKR 49.00" in masked.text, "the facts must survive masking"


def test_the_same_value_always_gets_the_same_token():
    """So a model can refer to one number consistently across a message."""
    masked = Masker().mask("0781234567 called 0781234567 again")

    assert masked.text.count("<PHONE_1>") == 2


def test_masking_is_reversible_inside_the_boundary():
    masker = Masker()
    original = "my number 0781234567 and email a@b.lk"

    assert masker.restore(masker.mask(original).text) == original


@pytest.mark.parametrize(
    "text",
    [
        "my OTP is 483920",
        "the code 123456 came by SMS",
        "card 4111 1111 1111 1111",
        "cvv 123",
    ],
)
def test_credentials_are_refused_not_masked(text):
    """Deck S8: OTPs and cards are never sent. Not tokenised - refused."""
    with pytest.raises(ForbiddenContent):
        Masker().mask(text)


def test_a_refused_message_stores_nothing():
    masker = Masker()

    with pytest.raises(ForbiddenContent):
        masker.mask("my pin 4821 and number 0781234567")

    assert len(masker.vault) == 0, "nothing from a refused message may be kept"


def test_a_random_long_number_is_not_treated_as_a_card():
    """Card detection uses Luhn, so ordinary references do not trip it."""
    assert not find_forbidden("order number 1234567890123")


# --------------------------------------------------------------------------- #
# Token vault
# --------------------------------------------------------------------------- #


def test_vault_entries_expire():
    vault = TokenVault(ttl=timedelta(minutes=30))
    now = utc_now()
    vault.store("<PHONE_1>", "0781234567", PiiKind.PHONE, now=now)

    assert vault.resolve("<PHONE_1>", now=now) == "0781234567"
    assert vault.resolve("<PHONE_1>", now=now + timedelta(minutes=31)) is None


def test_vault_restores_are_counted_for_audit():
    masker = Masker()
    masked = masker.mask("0781234567")

    masker.restore(masked.text)

    assert masker.vault.restore_count == 1


def test_an_unknown_token_is_left_alone_on_restore():
    """A token we never issued must not resolve to anything."""
    assert Masker().restore("see <PHONE_7>") == "see <PHONE_7>"


# --------------------------------------------------------------------------- #
# Output verifier
# --------------------------------------------------------------------------- #


@pytest.fixture
def facts() -> Facts:
    return Facts(
        amounts={Decimal("49.00")},
        identifiers={"VAS_NO_CONSENT"},
        allowed_actions={"REFUND"},
        language=Language.EN,
    )


def test_a_correct_sentence_passes(facts):
    result = OutputVerifier().verify("We will refund LKR 49.00 under VAS_NO_CONSENT.", facts)

    assert result.ok, result.summary


def test_an_invented_amount_is_blocked(facts):
    """The core promise: a model cannot state a number the case does not have."""
    result = OutputVerifier().verify("We will refund LKR 499.00.", facts)

    assert not result.ok
    assert any(i.code == "UNVERIFIED_NUMBER" for i in result.issues)


def test_a_promise_beyond_the_decision_is_blocked(facts):
    result = OutputVerifier().verify("We will refund and block the merchant.", facts)

    assert not result.ok
    assert any(i.code == "UNAUTHORISED_PROMISE" for i in result.issues)


def test_personal_data_in_the_reply_is_blocked(facts):
    result = OutputVerifier().verify("Call 0781234567 about your refund.", facts)

    assert any(i.code == "PII_IN_OUTPUT" for i in result.issues)


def test_a_token_we_never_issued_is_blocked(facts):
    result = OutputVerifier().verify("We refunded <PHONE_4>.", facts, issued_tokens={"<PHONE_1>"})

    assert any(i.code == "INVENTED_TOKEN" for i in result.issues)


def test_a_reply_in_the_wrong_language_is_blocked():
    sinhala_expected = Facts(allowed_actions={"REFUND"}, language=Language.SI)

    result = OutputVerifier().verify("We will refund you.", sinhala_expected)

    assert any(i.code == "WRONG_LANGUAGE" for i in result.issues)


def test_a_rule_name_from_another_case_is_blocked(facts):
    result = OutputVerifier().verify("This was DUPLICATE_RELOAD.", facts)

    assert any(i.code == "UNVERIFIED_IDENTIFIER" for i in result.issues)


# --------------------------------------------------------------------------- #
# Templates - the floor the system stands on
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("language", [Language.EN, Language.SI, Language.TA])
def test_every_prototype_rule_has_a_template_in_every_language(language):
    for rule_id in (
        "VAS_NO_CONSENT",
        "DUPLICATE_RELOAD",
        "RELOAD_NOT_CREDITED",
        "FUP_CAP_REACHED",
        "DUPLICATE_VAS_CHARGE",
        "PACK_EXPIRY_BURN",
    ):
        assert has_template(rule_id, language), f"{rule_id} has no {language.value} template"


def test_a_template_states_the_amount_from_the_decision():
    text = explanation(
        rule_id="VAS_NO_CONSENT",
        outcome=Outcome.ONE_TAP_FIX,
        amount=Decimal("49.00"),
        language=Language.EN,
    )

    assert "49.00" in text


def test_an_unknown_cause_still_produces_an_honest_answer():
    text = explanation(rule_id=None, outcome=Outcome.HANDOFF, amount=None, language=Language.EN)

    assert "could not confirm" in text.lower()


@pytest.mark.parametrize("language", [Language.SI, Language.TA])
def test_templates_pass_their_own_language_check(language):
    """A Sinhala template must actually contain Sinhala."""
    text = explanation(
        rule_id="VAS_NO_CONSENT",
        outcome=Outcome.ONE_TAP_FIX,
        amount=Decimal("49.00"),
        language=language,
    )

    result = OutputVerifier().verify(
        text, Facts(amounts={Decimal("49.00")}, allowed_actions={"REFUND"}, language=language)
    )

    assert not any(i.code == "WRONG_LANGUAGE" for i in result.issues)


# --------------------------------------------------------------------------- #
# Gateway routing
# --------------------------------------------------------------------------- #


def test_with_no_model_configured_the_answer_still_arrives():
    """Deck S7: 'Works without the LLM'. This is that path, for real."""
    answer = AIGateway().explain(a_decision(), rule_id="VAS_NO_CONSENT", language=Language.SI)

    assert answer.tier is Tier.TEMPLATE
    assert answer.usage.total == 0
    assert "49.00" in answer.text


class _InventingProvider:
    """A model that states an amount the case does not have."""

    name = "inventing"

    def complete(self, prompt: Prompt) -> tuple[str, Usage]:
        return "We will refund LKR 4900.00 to you immediately.", Usage(120, 20)


class _BrokenProvider:
    name = "broken"

    def complete(self, prompt: Prompt) -> tuple[str, Usage]:
        raise RuntimeError("provider is down")


class _GoodProvider:
    name = "good"

    def complete(self, prompt: Prompt) -> tuple[str, Usage]:
        amount = prompt.facts["amount_lkr"]
        return f"A subscription charge of LKR {amount} had no confirmation from you.", Usage(
            100, 18
        )


def test_a_model_that_invents_an_amount_never_reaches_the_customer():
    gateway = AIGateway(provider=_InventingProvider(), prefer_templates=False)

    answer = gateway.explain(a_decision(), rule_id="VAS_NO_CONSENT")

    assert "4900.00" not in answer.text, "the invented figure must not be shown"
    assert answer.tier is Tier.TEMPLATE
    assert answer.fell_back and not answer.verified


def test_a_provider_outage_falls_back_to_a_template():
    gateway = AIGateway(provider=_BrokenProvider(), prefer_templates=False)

    answer = gateway.explain(a_decision(), rule_id="VAS_NO_CONSENT")

    assert answer.tier is Tier.TEMPLATE
    assert answer.fell_back
    assert "49.00" in answer.text


def test_a_well_behaved_model_is_used_and_counted():
    gateway = AIGateway(provider=_GoodProvider(), prefer_templates=False)

    answer = gateway.explain(a_decision(), rule_id="VAS_NO_CONSENT")

    assert answer.tier is Tier.SMALL_MODEL
    assert answer.usage.total == 118
    assert answer.verified


def test_customer_text_is_masked_before_it_reaches_a_provider():
    seen: list[str] = []

    class _Spy:
        name = "spy"

        def complete(self, prompt: Prompt) -> tuple[str, Usage]:
            seen.append(prompt.user_masked)
            return "A subscription charge of LKR 49.00 had no confirmation.", Usage(10, 5)

    gateway = AIGateway(provider=_Spy(), prefer_templates=False)
    gateway.explain(
        a_decision(),
        rule_id="VAS_NO_CONSENT",
        customer_text="I am on 0781234567 and LKR 49 went missing",
    )

    assert seen, "the provider should have been called"
    assert "0781234567" not in seen[0], "a raw number must never reach a model"


def test_a_message_containing_an_otp_is_dropped_not_forwarded():
    seen: list[str] = []

    class _Spy:
        name = "spy"

        def complete(self, prompt: Prompt) -> tuple[str, Usage]:
            seen.append(prompt.user_masked)
            return "A subscription charge of LKR 49.00 had no confirmation.", Usage(10, 5)

    gateway = AIGateway(provider=_Spy(), prefer_templates=False)
    gateway.explain(a_decision(), rule_id="VAS_NO_CONSENT", customer_text="my OTP is 483920, help")

    assert seen[0] == "", "the whole message is dropped rather than partially sent"


def test_case_specific_answers_are_never_cached():
    """Caching an answer that names an amount would state it to someone else."""
    gateway = AIGateway(provider=_GoodProvider(), prefer_templates=False)

    gateway.explain(a_decision(), rule_id="VAS_NO_CONSENT")
    gateway.explain(a_decision(), rule_id="VAS_NO_CONSENT")

    assert gateway.cache.hits == 0


def test_usage_summary_reports_what_the_disclosure_needs():
    gateway = AIGateway()
    gateway.explain(a_decision(), rule_id="VAS_NO_CONSENT")

    summary = gateway.usage_summary

    assert summary["calls"] == 1
    assert summary["total_tokens"] == 0
    assert summary["llm_free_share"] == 1.0
