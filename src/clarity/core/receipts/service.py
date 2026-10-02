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
from dataclasses import dataclass, field
from datetime import datetime

from clarity.core.receipts.recurrence import CHECK_FOR_ACTION, RecurrenceProbe, run_check
from clarity.core.receipts.signing import SigningService, UnknownKeyId, verify_signature
from clarity.core.tools.confirmation import ConfirmedBy
from clarity.core.tools.layer import ExecutionResult
from clarity.schemas.canonical import hash_payload
from clarity.schemas.case import Case
from clarity.schemas.common import Language, utc_now
from clarity.schemas.decision import ActionStatus, ActionType, CauseAssessment, Decision
from clarity.schemas.ids import receipt_id as make_receipt_id
from clarity.schemas.receipt import (
    ActorType,
    ReceiptAction,
    ReceiptActor,
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
from clarity.schemas.timeline import EvidenceSnapshot

#: Where the public verification page lives. Configured per environment;
#: the host is a placeholder until HUTCH confirms the domain.
DEFAULT_VERIFY_BASE = "https://clarity.example/v"

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


@dataclass
class _Ledger:
    """Append-only store of issued receipts, in issue order."""

    receipts: dict[str, TrustReceipt] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)
    superseded_by: dict[str, str] = field(default_factory=dict)


class ReceiptService:
    """Issues receipts and verifies them."""

    def __init__(
        self,
        signing: SigningService,
        *,
        probe: RecurrenceProbe | None = None,
        verify_base: str = DEFAULT_VERIFY_BASE,
        persist: bool = False,
    ) -> None:
        self._signing = signing
        self._probe = probe
        self._verify_base = verify_base.rstrip("/")
        self._ledger = _Ledger()
        self._lock = threading.Lock()
        self._sequence = 0
        self._persist = persist
        self._subscriber_by_receipt: dict[str, str] = {}
        if persist:
            self._hydrate()

    def _hydrate(self) -> None:
        from clarity.integrations.store import list_receipts, session_scope

        with session_scope() as session:
            for receipt, subscriber_ref in list_receipts(session):
                self._ledger.receipts[receipt.receipt_id] = receipt
                self._ledger.order.append(receipt.receipt_id)
                self._subscriber_by_receipt[receipt.receipt_id] = subscriber_ref
                if receipt.payload.supersedes:
                    self._ledger.superseded_by[receipt.payload.supersedes] = receipt.receipt_id
                # Keep sequence ahead of any restored receipt number.
                try:
                    # RCP-2027-000042 → 42
                    num = int(receipt.receipt_id.rsplit("-", 1)[-1])
                    self._sequence = max(self._sequence, num)
                except ValueError:
                    pass

    def subscriber_ref_for(self, receipt_id: str) -> str | None:
        return self._subscriber_by_receipt.get(receipt_id)

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
        now: datetime | None = None,
    ) -> TrustReceipt:
        """Issue a receipt for a completed case.

        Called for an executed remedy and for an explain-only outcome alike:
        the deck promises a receipt for what was decided, not only for money
        that moved.
        """
        issued_at = now or utc_now()
        actions = self._receipt_actions(execution)
        safeguard, recurrence = self._safeguard_and_check(
            cause, actions, subscriber_ref, safeguard_params or {}, issued_at
        )

        with self._lock:
            self._sequence += 1
            payload = ReceiptPayload(
                receipt_id=make_receipt_id(self._sequence, year=issued_at.year),
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
                prev_receipt_hash=self._chain_head(),
            )

            payload_hash = payload.compute_hash()
            kid, signature = self._signing.sign(payload_hash)
            receipt = TrustReceipt(
                payload=payload,
                payload_hash=payload_hash,
                signature=ReceiptSignature(kid=kid, value=signature),
                verify_url=f"{self._verify_base}/{payload.receipt_id}",
            )

            self._ledger.receipts[receipt.receipt_id] = receipt
            self._ledger.order.append(receipt.receipt_id)
            self._subscriber_by_receipt[receipt.receipt_id] = subscriber_ref
            if supersedes:
                self._ledger.superseded_by[supersedes] = receipt.receipt_id
            if self._persist:
                from clarity.integrations.store import save_receipt, session_scope

                with session_scope() as session:
                    save_receipt(session, receipt, subscriber_ref=subscriber_ref)
            return receipt

    def _chain_head(self) -> str | None:
        if not self._ledger.order:
            return None
        return self._ledger.receipts[self._ledger.order[-1]].payload_hash

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
            approver_role="supervisor" if actor_type is ActorType.STAFF_APPROVED else None,
            system="clarity-tool-layer",
        )

    # ------------------------------------------------------------------ #
    # Verification
    # ------------------------------------------------------------------ #

    def get(self, receipt_id: str) -> TrustReceipt | None:
        return self._ledger.receipts.get(receipt_id)

    def issued(self) -> list[TrustReceipt]:
        """Every receipt in issue order."""
        return [self._ledger.receipts[receipt_id] for receipt_id in self._ledger.order]

    def verify(self, receipt_id: str) -> VerificationResult:
        """Verify a receipt we issued, by id (what the QR code resolves to)."""
        receipt = self._ledger.receipts.get(receipt_id)
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
        superseded_by = self._ledger.superseded_by.get(receipt.receipt_id)

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

        issued = self._ledger.receipts.get(receipt.receipt_id)
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
        position = self._ledger.order.index(receipt_id)
        receipt = self._ledger.receipts[receipt_id]
        if position == 0:
            return receipt.payload.prev_receipt_hash is None
        previous = self._ledger.receipts[self._ledger.order[position - 1]]
        return receipt.payload.prev_receipt_hash == previous.payload_hash

    def verify_chain(self) -> bool:
        """Verify the whole ledger, as a tamper check would (plan §20.3)."""
        return all(self._chain_is_intact(receipt_id) for receipt_id in self._ledger.order)

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
