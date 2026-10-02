"""Trust Receipt tests (deck S6, plan §15).

A receipt is a promise to a customer and to a regulator, so the tests that
matter most are the adversarial ones: a tampered document, a forged one, a
signature from the wrong key, and a safeguard claimed but not actually in
force.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from clarity.core.receipts.service import ReceiptService, explain_summary
from clarity.core.receipts.signing import DevSigningService, verify_signature
from clarity.core.timeline.builder import TimelineRequest
from clarity.core.tools.budget import RefundBudget
from clarity.core.tools.layer import ToolLayer
from clarity.integrations.mocks.recurrence import MockRecurrenceProbe
from clarity.integrations.mocks.world import DEMO_NOW, ref_for
from clarity.schemas.case import Case, CaseTrigger, CustomerReference
from clarity.schemas.common import Channel, Language, mask_msisdn
from clarity.schemas.decision import (
    ActionType,
    CauseAssessment,
    Decision,
    Outcome,
)
from clarity.schemas.ids import new_id
from clarity.schemas.receipt import RecurrenceResult

DILANI = "+94771234567"
SUBSCRIBER = ref_for(DILANI)


@pytest.fixture
def signing() -> DevSigningService:
    return DevSigningService(kid="test-key-1")


@pytest.fixture
def receipts(signing: DevSigningService, world) -> ReceiptService:
    return ReceiptService(signing, probe=MockRecurrenceProbe(world))


@pytest.fixture
def case() -> Case:
    return Case(
        case_id="CASE-T",
        case_no="CASE-2027-000001",
        customer=CustomerReference(
            subscriber_ref=SUBSCRIBER,
            msisdn_masked=mask_msisdn(DILANI),
            preferred_language=Language.SI,
        ),
        trigger=CaseTrigger.CUSTOMER,
        origin_channel=Channel.APP,
    )


def a_decision(amount: str = "49.00") -> Decision:
    return Decision(
        decision_id=new_id("DEC"),
        case_id="CASE-T",
        outcome=Outcome.ONE_TAP_FIX,
        policy_version="test.1",
        input_hash="sha256:test",
        allowed_actions=[
            ActionType.REFUND,
            ActionType.DEACTIVATE_VAS,
            ActionType.BLOCK_MERCHANT_UNTIL_OPTIN,
        ],
        amount_lkr=amount,
        top_cause_ref="VAS_NO_CONSENT@4",
    )


def a_cause(evidence_refs: list[str] | None = None) -> CauseAssessment:
    return CauseAssessment(
        rule_id="VAS_NO_CONSENT",
        rule_version=4,
        matched=True,
        confidence=Decimal("0.96"),
        category="unauthorized_vas",
        money_effect_lkr="49.00",
        evidence_refs=evidence_refs or [],
        allowed_actions=[ActionType.REFUND, ActionType.BLOCK_MERCHANT_UNTIL_OPTIN],
        safeguard=ActionType.BLOCK_MERCHANT_UNTIL_OPTIN,
        recurrence_check="merchant_block_active",
    )


@pytest.fixture
def executed(registry, builder):
    """Run the VAS remedy for real, so the receipt describes true state."""
    tools = ToolLayer(registry.command_port, budget=RefundBudget(daily_limit_lkr="100000"))
    decision = a_decision()
    plan = tools.propose(
        decision,
        subscriber_ref=SUBSCRIBER,
        created_by="mcp:customer-assist",
        params={
            ActionType.DEACTIVATE_VAS: {"subscription_id": "SUB-GAME-1"},
            ActionType.BLOCK_MERCHANT_UNTIL_OPTIN: {"merchant_id": "MER-GAMEHUB"},
        },
    )
    token = tools.confirm_by_customer(plan.plan_id, subscriber_ref=SUBSCRIBER)
    result = tools.execute(plan.plan_id, confirmation=token, idempotency_key="rk-1")
    snapshot = builder.build(TimelineRequest.for_case("CASE-T", SUBSCRIBER, now=DEMO_NOW))
    return decision, result, snapshot


def issue(receipts: ReceiptService, case: Case, executed, **kwargs):
    decision, result, snapshot = executed
    return receipts.issue(
        case=case,
        decision=decision,
        cause=kwargs.pop("cause", a_cause()),
        snapshot=snapshot,
        execution=result,
        summary="A daily game subscription was charged with no OTP from you.",
        subscriber_ref=SUBSCRIBER,
        safeguard_params={"merchant_id": "MER-GAMEHUB"},
        **kwargs,
    )


# --------------------------------------------------------------------------- #
# Issuing
# --------------------------------------------------------------------------- #


def test_a_receipt_records_what_was_corrected(receipts, case, executed):
    receipt = issue(receipts, case, executed)

    refund = next(a for a in receipt.payload.actions if a.type is ActionType.REFUND)
    assert refund.amount_lkr == Decimal("49.00")
    assert refund.before == {"balance_lkr": "451.00"}
    assert refund.after == {"balance_lkr": "500.00"}


def test_a_receipt_never_contains_the_raw_number(receipts, case, executed):
    receipt = issue(receipts, case, executed)

    serialized = receipt.model_dump_json()
    assert "771234567" not in serialized
    assert receipt.payload.subject.msisdn_masked == "07X XXX 4567"


def test_a_receipt_is_quotable_and_has_a_verify_url(receipts, case, executed):
    """Deck S6: customers quote the id on 1788, WhatsApp or to TRCSL."""
    import re

    receipt = issue(receipts, case, executed)

    assert re.fullmatch(r"TR-\d{4}-\d{6}", receipt.receipt_id), "short enough to read aloud"
    assert receipt.receipt_id in receipt.verify_url


def test_a_receipt_cites_evidence_by_hash_not_content(receipts, case, executed):
    _, _, snapshot = executed
    cited = [snapshot.events[0].event_id]

    receipt = issue(receipts, case, executed, cause=a_cause(evidence_refs=cited))

    assert receipt.payload.evidence
    assert receipt.payload.evidence[0].hash.startswith("sha256:")


def test_a_receipt_names_the_rule_version_and_policy_version(receipts, case, executed):
    receipt = issue(receipts, case, executed)

    assert receipt.payload.what_happened.rule_version == 4
    assert receipt.payload.decision.policy_version == "test.1"


# --------------------------------------------------------------------------- #
# The recurrence test must be earned
# --------------------------------------------------------------------------- #


def test_recurrence_passes_only_when_the_block_is_really_in_place(receipts, case, executed, world):
    """Deck S6: 'PASSED only if really blocked'."""
    receipt = issue(receipts, case, executed)

    assert world.is_merchant_blocked(SUBSCRIBER, "MER-GAMEHUB"), "precondition"
    assert receipt.payload.recurrence_test.result is RecurrenceResult.PASSED
    assert receipt.payload.safeguard.status == "ACTIVE"


def test_recurrence_fails_when_the_safeguard_is_not_really_in_force(signing, case, executed, world):
    """A probe that reports 'not blocked' must produce FAILED, not PASSED."""
    receipts = ReceiptService(signing, probe=MockRecurrenceProbe(world))

    receipt = receipts.issue(
        case=case,
        decision=executed[0],
        cause=a_cause(),
        snapshot=executed[2],
        execution=executed[1],
        summary="test",
        subscriber_ref=SUBSCRIBER,
        safeguard_params={"merchant_id": "MER-SOMEONE-ELSE"},
    )

    assert receipt.payload.recurrence_test.result is RecurrenceResult.FAILED


def test_recurrence_is_unavailable_rather_than_optimistic(signing, case, executed):
    """With no probe, the receipt says so instead of claiming a pass."""
    receipts = ReceiptService(signing, probe=None)

    receipt = receipts.issue(
        case=case,
        decision=executed[0],
        cause=a_cause(),
        snapshot=executed[2],
        execution=executed[1],
        summary="test",
        subscriber_ref=SUBSCRIBER,
        safeguard_params={"merchant_id": "MER-GAMEHUB"},
    )

    assert receipt.payload.recurrence_test.result is RecurrenceResult.UNAVAILABLE


# --------------------------------------------------------------------------- #
# Verification
# --------------------------------------------------------------------------- #


def test_an_issued_receipt_verifies(receipts, case, executed):
    receipt = issue(receipts, case, executed)

    result = receipts.verify(receipt.receipt_id)

    assert result.valid and result.chain_ok
    assert result.display == "VERIFIED"


def test_a_tampered_amount_fails_verification(receipts, case, executed):
    """The point of signing: changing the number invalidates the receipt."""
    receipt = issue(receipts, case, executed)
    tampered_actions = [
        a.model_copy(update={"amount_lkr": Decimal("9999.00")}) for a in receipt.payload.actions
    ]
    tampered = receipt.model_copy(
        update={"payload": receipt.payload.model_copy(update={"actions": tampered_actions})}
    )

    result = receipts.verify_document(tampered)

    assert not result.valid
    assert "hash" in result.reason


def test_a_forged_receipt_that_was_never_issued_fails(receipts, case, executed, signing):
    """A convincing-looking document still has to be in the ledger."""
    receipt = issue(receipts, case, executed)
    forged_payload = receipt.payload.model_copy(update={"receipt_id": "TR-2027-999999"})
    forged_hash = forged_payload.compute_hash()
    kid, value = signing.sign(forged_hash)
    forged = receipt.model_copy(
        update={
            "payload": forged_payload,
            "payload_hash": forged_hash,
            "signature": receipt.signature.model_copy(update={"kid": kid, "value": value}),
        }
    )

    result = receipts.verify_document(forged)

    assert not result.valid
    assert "never issued" in result.reason or "on record" in result.reason


def test_a_receipt_signed_by_a_different_key_fails(receipts, case, executed):
    receipt = issue(receipts, case, executed)
    attacker = DevSigningService(kid="test-key-1")  # same kid, different key material
    _, forged_signature = attacker.sign(receipt.payload_hash)
    forged = receipt.model_copy(
        update={"signature": receipt.signature.model_copy(update={"value": forged_signature})}
    )

    assert not receipts.verify_document(forged).valid


def test_an_unknown_key_id_fails_clearly(receipts, case, executed):
    receipt = issue(receipts, case, executed)
    unknown = receipt.model_copy(
        update={"signature": receipt.signature.model_copy(update={"kid": "not-our-key"})}
    )

    result = receipts.verify_document(unknown)

    assert not result.valid
    assert "do not publish" in result.reason


def test_verifying_an_unknown_id_says_so(receipts):
    result = receipts.verify("TR-2027-000999")

    assert not result.valid
    assert "never issued" in result.reason or "ever issued" in result.reason


def test_signatures_verify_with_public_material_only(signing):
    """Anyone, including TRCSL, can verify without anything secret."""
    payload_hash = "sha256:abc123"
    kid, signature = signing.sign(payload_hash)

    assert verify_signature(
        payload_hash, kid=kid, signature_b64=signature, public_keys=signing.public_keys()
    )
    assert not verify_signature(
        "sha256:different", kid=kid, signature_b64=signature, public_keys=signing.public_keys()
    )


# --------------------------------------------------------------------------- #
# Chaining and correction
# --------------------------------------------------------------------------- #


def test_receipts_chain_to_their_predecessor(receipts, case, executed):
    first = issue(receipts, case, executed)
    second = issue(receipts, case, executed)

    assert first.payload.prev_receipt_hash is None, "the first has no predecessor"
    assert second.payload.prev_receipt_hash == first.payload_hash
    assert receipts.verify_chain()


def test_a_correction_supersedes_rather_than_edits(receipts, case, executed):
    """Deck/plan §15.2: receipts are never edited."""
    original = issue(receipts, case, executed)

    correction = issue(receipts, case, executed, supersedes=original.receipt_id)

    assert correction.payload.supersedes == original.receipt_id
    assert receipts.verify(original.receipt_id).superseded_by == correction.receipt_id
    assert receipts.verify(original.receipt_id).valid, "the original stays verifiable"


# --------------------------------------------------------------------------- #
# Presentation
# --------------------------------------------------------------------------- #


def test_the_public_view_proves_validity_without_exposing_the_account(receipts, case, executed):
    receipt = issue(receipts, case, executed)

    view = receipts.public_view(receipt)

    assert view["status"] == "VERIFIED"
    assert view["corrected_lkr"] == "49.00"
    assert view["recurrence_test"] == "PASSED"
    assert "771234567" not in str(view)
    assert "evidence" not in view, "full evidence needs authentication"


@pytest.mark.parametrize("language", [Language.EN, Language.SI, Language.TA])
def test_sms_form_is_short_and_quotable(receipts, case, executed, language):
    receipt = issue(receipts, case, executed)

    text = receipts.sms_text(receipt, language)

    assert receipt.receipt_id in text
    assert receipt.verify_url in text


def test_summary_is_built_from_facts_not_prose(receipts, case, executed):
    """A receipt sentence must trace back to the decision record."""
    decision = executed[0]

    summary = explain_summary(a_cause(), decision, [ActionType.REFUND])

    assert "VAS_NO_CONSENT" in summary
    assert "rule version 4" in summary
    assert "49.00" in summary


# --------------------------------------------------------------------------- #
# Rendering (deck S6: PNG, PDF, SMS in si/ta/en)
# --------------------------------------------------------------------------- #


def test_receipt_html_is_built_in_the_requested_language(receipts, case, executed):
    from clarity.core.receipts.render import receipt_html

    receipt = issue(receipts, case, executed)

    sinhala = receipt_html(receipt, Language.SI)
    english = receipt_html(receipt, Language.EN)

    assert 'lang="si"' in sinhala
    assert any("඀" <= ch <= "෿" for ch in sinhala), "expected Sinhala script"
    assert sinhala != english


def test_receipt_html_escapes_everything_it_renders(receipts, case, executed):
    """The render input is data, so it must not be able to inject markup."""
    from clarity.core.receipts.render import receipt_html

    receipt = issue(receipts, case, executed)
    hostile = receipt.model_copy(
        update={
            "payload": receipt.payload.model_copy(
                update={
                    "what_happened": receipt.payload.what_happened.model_copy(
                        update={"summary": "<script>alert(1)</script>"}
                    )
                }
            )
        }
    )

    markup = receipt_html(hostile, Language.EN)

    assert "<script>" not in markup
    assert "&lt;script&gt;" in markup


def test_receipt_html_loads_nothing_external(receipts, case, executed):
    """Plan §7.2 T9: the render pool has no network egress, so nothing may ask."""
    from clarity.core.receipts.render import receipt_html

    markup = receipt_html(issue(receipts, case, executed), Language.EN)

    assert "http://" not in markup.replace("http://localhost", "")
    assert "<img" not in markup and "<script" not in markup


def test_receipt_html_carries_the_proof_fields(receipts, case, executed):
    from clarity.core.receipts.render import receipt_html

    receipt = issue(receipts, case, executed)

    markup = receipt_html(receipt, Language.EN)

    assert receipt.receipt_id in markup
    assert receipt.payload_hash in markup
    assert receipt.signature.kid in markup
    assert "PASSED" in markup, "the recurrence result must be visible on the receipt"
