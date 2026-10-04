"""Issuing and verifying Trust Receipts (deck S6, plan §15).

Issuing is the last step of a case: an action completed, so the customer gets
proof they can check and quote. Verification is deliberately available to
anyone holding the receipt, using only published public keys.

Three properties this service is responsible for:

- **Tamper evidence.** Each receipt is hashed canonically and signed, and
  carries the previous receipt's hash, so altering an old receipt breaks every
  receipt after it.
- **Honest safeguards.** The recurrence test re-reads live state; it never
  infers success from a command being accepted.
- **Correction without rewriting.** A superseding receipt points at the one it
  replaces; nothing is edited in place.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime

from clarity.contracts.case import Case
from clarity.contracts.decision import ActionStatus, ActionType, CauseAssessment, Decision
from clarity.contracts.events import ReceiptIssuedV1
from clarity.contracts.receipt import (
    ActorType,
    ReceiptAction,
    ReceiptActor,
    ReceiptAuditAnchor,
    ReceiptCause,
    ReceiptDecision,
    ReceiptEvidence,
    ReceiptPayload,
    ReceiptRecurrenceTest,
    ReceiptSafeguard,
    ReceiptSignature,
    ReceiptSubject,
    RecurrenceResult,
    TrustReceipt,
)
from clarity.contracts.timeline import EvidenceSnapshot
from clarity.kernel.canonical import hash_payload
from clarity.kernel.common import Language, utc_now
from clarity.kernel.ids import receipt_id as make_receipt_id
from clarity.modules.actions.public import ConfirmedBy, ExecutionResult
from clarity.modules.receipts.recurrence import CHECK_FOR_ACTION, RecurrenceProbe, run_check
from clarity.modules.receipts.repository import (
    BY_PLAN,
    RECEIPT_SEQUENCE,
    RECEIPTS,
    SUBSCRIBERS,
    SUPERSEDED,
    ReceiptRepository,
    StoredReceiptRepository,
)
from clarity.modules.receipts.signing import SigningService, UnknownKeyId, verify_signature
from clarity.platform.messaging.envelope import Event
from clarity.platform.messaging.outbox import outbox_in
from clarity.platform.persistence import UnitOfWork, UnitOfWorkFactory

#: Where the public verification page lives. Configured per environment;
#: the host is a placeholder until HUTCH confirms the domain.
DEFAULT_VERIFY_BASE = "https://clarity.example/r"

_ACTOR_FOR_CONFIRMATION = {
    ConfirmedBy.CUSTOMER: ActorType.CUSTOMER_CONFIRMED,
    ConfirmedBy.STAFF: ActorType.STAFF_APPROVED,
    ConfirmedBy.SYSTEM: ActorType.SYSTEM_AUTO_FIX,
}


@dataclass
class VerificationResult:
    """What a verifier can tell the person holding a receipt."""

    receipt_id: str
    valid: bool
    reason: str
    kid: str | None = None
    chain_ok: bool = False
    superseded_by: str | None = None

    @property
    def display(self) -> str:
        return "VERIFIED" if self.valid else "NOT VALID"


class ReceiptService:
    """Issues receipts and verifies them."""

    def __init__(
        self,
        signing: SigningService,
        *,
        ledger: ReceiptRepository,
        probe: RecurrenceProbe | None = None,
        verify_base: str = DEFAULT_VERIFY_BASE,
        persist: bool = False,
        open_unit: UnitOfWorkFactory | None = None,
        audit_anchor: Callable[[], ReceiptAuditAnchor | None] | None = None,
    ) -> None:
        self._signing = signing
        self._probe = probe
        self._verify_base = verify_base.rstrip("/")
        #: The current signed audit checkpoint, so a receipt carries an external
        #: witness of the audit head (ADR-0035). A callable supplied by the
        #: composition root rather than the checkpointer itself: this module must
        #: not depend on ``platform.audit`` (I4), and a receipt must still be
        #: issuable where there is no checkpointer at all.
        self._audit_anchor = audit_anchor
        # The chain lives in the repository (B02); the service keeps no copy.
        self._ledger = ledger
        self._lock = threading.Lock()
        self._persist = persist
        self._open_unit = open_unit
        if persist:
            self._hydrate()

    def _hydrate(self) -> None:
        from clarity.integration.drivers.mock.store import list_receipts, session_scope

        with session_scope() as session:
            for receipt, subscriber_ref in list_receipts(session, verify_base=self._verify_base):
                self._ledger.append(receipt, subscriber_ref=subscriber_ref)
                if receipt.payload.supersedes:
                    self._ledger.mark_superseded(
                        receipt.payload.supersedes, by_receipt_id=receipt.receipt_id
                    )
                # Keep the sequence ahead of any restored receipt number.
                with suppress(ValueError):
                    # RCP-2027-000042 -> 42
                    self._ledger.bump_sequence_to(int(receipt.receipt_id.rsplit("-", 1)[-1]))

    def subscriber_ref_for(self, receipt_id: str) -> str | None:
        return self._ledger.subscriber_ref_for(receipt_id)

    def for_plan(self, plan_id: str) -> TrustReceipt | None:
        """The receipt issued for one executed plan, if it has been issued."""
        receipt_id = self._ledger.receipt_id_for_plan(plan_id)
        return None if receipt_id is None else self._ledger.get(receipt_id)

    # ------------------------------------------------------------------ #
    # Issuing
    # ------------------------------------------------------------------ #

    def issue(
        self,
        *,
        case: Case,
        decision: Decision,
        cause: CauseAssessment | None,
        snapshot: EvidenceSnapshot,
        execution: ExecutionResult | None,
        summary: str,
        subscriber_ref: str,
        safeguard_params: dict[str, object] | None = None,
        supersedes: str | None = None,
        plan_id: str | None = None,
        now: datetime | None = None,
    ) -> TrustReceipt:
        """Issue a receipt for a completed case.

        Called for an executed remedy and for an explain-only outcome alike:
        the deck promises a receipt for what was decided, not only for money
        that moved.

        With a ``plan_id`` this is idempotent: one executed plan has exactly one
        receipt, however many times the event that triggered it is delivered
        (D1). Without one (an explain-only outcome) every call issues a receipt,
        because there is no plan to key it to.
        """
        issued_at = now or utc_now()
        actions = self._receipt_actions(execution)
        safeguard, recurrence = self._safeguard_and_check(
            cause, actions, subscriber_ref, safeguard_params or {}, issued_at
        )

        with self._lock:
            if self._open_unit is None:
                receipt, created = self._issue_in(
                    self._ledger,
                    case=case,
                    decision=decision,
                    cause=cause,
                    snapshot=snapshot,
                    execution=execution,
                    summary=summary,
                    subscriber_ref=subscriber_ref,
                    issued_at=issued_at,
                    actions=actions,
                    safeguard=safeguard,
                    recurrence=recurrence,
                    supersedes=supersedes,
                    plan_id=plan_id,
                )
            else:
                with self._open_unit() as unit:
                    receipt, created = self._issue_in(
                        self._ledger_in(unit),
                        case=case,
                        decision=decision,
                        cause=cause,
                        snapshot=snapshot,
                        execution=execution,
                        summary=summary,
                        subscriber_ref=subscriber_ref,
                        issued_at=issued_at,
                        actions=actions,
                        safeguard=safeguard,
                        recurrence=recurrence,
                        supersedes=supersedes,
                        plan_id=plan_id,
                    )
                    if created:
                        outbox_in(unit).append(
                            Event.of(
                                ReceiptIssuedV1(
                                    case_id=case.case_id,
                                    receipt_id=receipt.receipt_id,
                                    plan_id=plan_id,
                                    payload_hash=receipt.payload_hash,
                                    key_id=receipt.signature.kid,
                                ),
                                subject=subscriber_ref,
                            )
                        )
                    unit.commit()

            if created and self._persist:
                from clarity.integration.drivers.mock.store import save_receipt, session_scope

                with session_scope() as session:
                    save_receipt(session, receipt, subscriber_ref=subscriber_ref)
            return receipt

    def _issue_in(
        self,
        ledger: ReceiptRepository,
        *,
        case: Case,
        decision: Decision,
        cause: CauseAssessment | None,
        snapshot: EvidenceSnapshot,
        execution: ExecutionResult | None,
        summary: str,
        subscriber_ref: str,
        issued_at: datetime,
        actions: list[ReceiptAction],
        safeguard: ReceiptSafeguard | None,
        recurrence: ReceiptRecurrenceTest | None,
        supersedes: str | None,
        plan_id: str | None,
    ) -> tuple[TrustReceipt, bool]:
        """Build and stage one receipt in the supplied repository."""
        if plan_id is not None:
            existing = ledger.receipt_id_for_plan(plan_id)
            if existing is not None:
                already = ledger.get(existing)
                if already is not None:
                    return already, False

        sequence = ledger.next_receipt_number()
        payload = ReceiptPayload(
            receipt_id=make_receipt_id(sequence, year=issued_at.year),
            case_id=case.case_id,
            issued_at=issued_at,
            subject=ReceiptSubject(
                msisdn_masked=case.customer.msisdn_masked,
                subscriber_ref_hash=hash_payload(subscriber_ref),
            ),
            what_happened=ReceiptCause(
                cause_rule=cause.rule_id if cause else "NO_CAUSE_DETERMINED",
                rule_version=cause.rule_version if cause else 0,
                summary=summary,
            ),
            evidence=self._receipt_evidence(cause, snapshot),
            decision=ReceiptDecision(
                decision_id=decision.decision_id,
                outcome=decision.outcome,
                policy_version=decision.policy_version,
                input_hash=decision.input_hash,
            ),
            actions=actions,
            safeguard=safeguard,
            recurrence_test=recurrence,
            actor=self._actor(execution),
            languages=[Language.SI, Language.TA, Language.EN],
            supersedes=supersedes,
            prev_receipt_hash=self._chain_head(ledger),
        )

        payload_hash = payload.compute_hash()
        kid, signature = self._signing.sign(payload_hash)
        receipt = TrustReceipt(
            payload=payload,
            payload_hash=payload_hash,
            signature=ReceiptSignature(kid=kid, value=signature),
            verify_url=f"{self._verify_base}/{payload.receipt_id}",
        )
        ledger.append(receipt, subscriber_ref=subscriber_ref)
        if plan_id is not None:
            ledger.link_plan(plan_id, receipt_id=receipt.receipt_id)
        if supersedes:
            ledger.mark_superseded(supersedes, by_receipt_id=receipt.receipt_id)
        return receipt, True

    @staticmethod
    def _ledger_in(unit: UnitOfWork) -> StoredReceiptRepository:
        return StoredReceiptRepository(
            unit.repository(RECEIPTS),
            unit.repository(SUPERSEDED),
            unit.repository(SUBSCRIBERS),
            unit.repository(RECEIPT_SEQUENCE),
            unit.repository(BY_PLAN),
        )

    def _anchor(self) -> ReceiptAuditAnchor | None:
        """The current audit checkpoint, or ``None`` rather than a failed receipt.

        A receipt must not fail to issue because the checkpointer is unavailable:
        the customer is owed their proof of what happened to their money, and an
        absent anchor weakens the audit witness without weakening the receipt.
        The absence is visible in the payload, so nobody can mistake a receipt
        with no anchor for one that was never checked.
        """
        if self._audit_anchor is None:
            return None
        try:
            return self._audit_anchor()
        except Exception:  # never block a receipt on the audit side
            return None

    @staticmethod
    def _chain_head(ledger: ReceiptRepository) -> str | None:
        chain = ledger.in_order()
        return chain[-1].payload_hash if chain else None

    @staticmethod
    def _receipt_actions(execution: ExecutionResult | None) -> list[ReceiptAction]:
        if execution is None:
            return []
        return [
            ReceiptAction(
                action_id=action.action_id,
                type=action.type,
                amount_lkr=action.amount_lkr,
                before={k: str(v) for k, v in action.before_state.items()},
                after={k: str(v) for k, v in action.after_state.items()},
                status=action.status,
                adapter_ref=action.adapter_ref,
            )
            for action in execution.actions
        ]

    @staticmethod
    def _receipt_evidence(
        cause: CauseAssessment | None, snapshot: EvidenceSnapshot
    ) -> list[ReceiptEvidence]:
        """Cite the evidence the cause rested on, by id and hash."""
        if cause is None:
            return []
        cited: list[ReceiptEvidence] = []
        for event_id in cause.evidence_refs:
            event = snapshot.by_id(event_id)
            if event is None:
                continue
            cited.append(
                ReceiptEvidence(
                    event_id=event.event_id,
                    source=event.source,
                    hash=event.evidence_hash,
                )
            )
        return cited

    def _safeguard_and_check(
        self,
        cause: CauseAssessment | None,
        actions: list[ReceiptAction],
        subscriber_ref: str,
        params: dict[str, object],
        issued_at: datetime,
    ) -> tuple[ReceiptSafeguard | None, ReceiptRecurrenceTest | None]:
        if cause is None or cause.safeguard is None:
            return None, None

        applied = any(
            a.type is cause.safeguard and a.status is ActionStatus.COMPLETED for a in actions
        )
        safeguard = ReceiptSafeguard(
            type=cause.safeguard, status="ACTIVE" if applied else "NOT_APPLIED"
        )

        check_name = cause.recurrence_check or CHECK_FOR_ACTION.get(cause.safeguard)
        if not applied:
            return safeguard, ReceiptRecurrenceTest(
                check=check_name or "none",
                result=RecurrenceResult.NOT_APPLICABLE,
                checked_at=issued_at,
            )

        result = run_check(self._probe, check_name, subscriber_ref, params)
        return safeguard, ReceiptRecurrenceTest(
            check=check_name or "none", result=result, checked_at=issued_at
        )

    @staticmethod
    def _actor(execution: ExecutionResult | None) -> ReceiptActor:
        if execution is None:
            return ReceiptActor(type=ActorType.SYSTEM_AUTO_FIX, system="clarity-decision-policy")
        actor_type = _ACTOR_FOR_CONFIRMATION[execution.confirmed_by]
        return ReceiptActor(
            type=actor_type,
            # The roles that actually approved, in order (e.g. "supervisor+finance"
            # for four-eyes). Signed proof must not name a role that was not there.
            approver_role="+".join(execution.approver_roles) or None
            if actor_type is ActorType.STAFF_APPROVED
            else None,
            system="clarity-tool-layer",
        )

    # ------------------------------------------------------------------ #
    # Verification
    # ------------------------------------------------------------------ #

    def get(self, receipt_id: str) -> TrustReceipt | None:
        return self._ledger.get(receipt_id)

    def issued(self) -> list[TrustReceipt]:
        """Every receipt in issue order."""
        return self._ledger.in_order()

    def verify(self, receipt_id: str) -> VerificationResult:
        """Verify a receipt we issued, by id (what the QR code resolves to)."""
        receipt = self._ledger.get(receipt_id)
        if receipt is None:
            return VerificationResult(
                receipt_id=receipt_id, valid=False, reason="no such receipt was ever issued"
            )
        return self.verify_document(receipt)

    def verify_document(self, receipt: TrustReceipt) -> VerificationResult:
        """Verify a receipt document, e.g. one a customer brings to a shop.

        Checks the hash, the signature, and the chain. A document that looks
        right but was never issued fails on the ledger lookup.
        """
        superseded_by = self._ledger.superseded_by(receipt.receipt_id)

        recomputed = receipt.payload.compute_hash()
        if recomputed != receipt.payload_hash:
            return VerificationResult(
                receipt_id=receipt.receipt_id,
                valid=False,
                reason="the receipt contents do not match its hash",
                kid=receipt.signature.kid,
                superseded_by=superseded_by,
            )

        try:
            signed = verify_signature(
                receipt.payload_hash,
                kid=receipt.signature.kid,
                signature_b64=receipt.signature.value,
                public_keys=self._signing.public_keys(),
            )
        except UnknownKeyId:
            return VerificationResult(
                receipt_id=receipt.receipt_id,
                valid=False,
                reason="signed with a key we do not publish",
                kid=receipt.signature.kid,
                superseded_by=superseded_by,
            )

        if not signed:
            return VerificationResult(
                receipt_id=receipt.receipt_id,
                valid=False,
                reason="the signature does not match",
                kid=receipt.signature.kid,
                superseded_by=superseded_by,
            )

        issued = self._ledger.get(receipt.receipt_id)
        if issued is None or issued.payload_hash != receipt.payload_hash:
            return VerificationResult(
                receipt_id=receipt.receipt_id,
                valid=False,
                reason="this document does not match the receipt on record",
                kid=receipt.signature.kid,
                superseded_by=superseded_by,
            )

        chain_ok = self._chain_is_intact(receipt.receipt_id)
        return VerificationResult(
            receipt_id=receipt.receipt_id,
            valid=True,
            reason="signature and contents check out",
            kid=receipt.signature.kid,
            chain_ok=chain_ok,
            superseded_by=superseded_by,
        )

    def _chain_is_intact(self, receipt_id: str) -> bool:
        """Does this receipt still point at the receipt issued before it?"""
        chain = self._ledger.in_order()
        position = [r.receipt_id for r in chain].index(receipt_id)
        receipt = chain[position]
        if position == 0:
            return receipt.payload.prev_receipt_hash is None
        return receipt.payload.prev_receipt_hash == chain[position - 1].payload_hash

    def verify_chain(self) -> bool:
        """Verify the whole ledger, as a tamper check would (plan §20.3)."""
        return all(self._chain_is_intact(receipt_id) for receipt_id in self._ledger.ids_in_order())

    # ------------------------------------------------------------------ #
    # Presentation
    # ------------------------------------------------------------------ #

    def sms_text(self, receipt: TrustReceipt, language: Language = Language.EN) -> str:
        """Short form for SMS (deck S6).

        Sinhala and Tamil need UCS-2, which fits only 67 characters per
        concatenated segment, so this stays terse and puts the quotable id
        first (plan §9.7).
        """
        corrected = receipt.payload.total_corrected_lkr
        amount = f" LKR {corrected}" if corrected else ""
        match language:
            case Language.SI:
                return f"Hutch Clarity {receipt.receipt_id}:{amount} ආපසු. {receipt.verify_url}"
            case Language.TA:
                return f"Hutch Clarity {receipt.receipt_id}:{amount} திரும்ப. {receipt.verify_url}"
            case _:
                return f"Hutch Clarity {receipt.receipt_id}:{amount} returned. {receipt.verify_url}"

    def public_view(self, receipt: TrustReceipt) -> dict[str, object]:
        """What the QR verification page shows anyone (plan §15.2).

        Deliberately narrow: enough to confirm the receipt is real, not enough
        to expose the customer's account to whoever scans the code.
        """
        result = self.verify_document(receipt)
        payload = receipt.payload
        return {
            "receipt_id": payload.receipt_id,
            "status": result.display,
            "issued_at": payload.issued_at.isoformat(),
            "number": payload.subject.msisdn_masked,
            "corrected_lkr": str(payload.total_corrected_lkr or "0.00"),
            "safeguard": payload.safeguard.type.value if payload.safeguard else None,
            "recurrence_test": (
                payload.recurrence_test.result.value if payload.recurrence_test else None
            ),
            "superseded_by": result.superseded_by,
            "key_id": result.kid,
        }


def explain_summary(
    cause: CauseAssessment | None, decision: Decision, actions: list[ActionType]
) -> str:
    """Deterministic one-line summary for a receipt.

    Built from the decision's own facts, not written by a model, so a receipt
    never carries a sentence nobody can trace back to evidence.
    """
    if cause is None:
        return "No single cause could be confirmed from the available records."

    parts = [f"Cause: {cause.rule_id} (rule version {cause.rule_version})."]
    if decision.amount_lkr and decision.amount_lkr > 0:
        parts.append(f"Amount in question: LKR {decision.amount_lkr}.")
    if actions:
        parts.append("Actions: " + ", ".join(a.value for a in actions) + ".")
    return " ".join(parts)
