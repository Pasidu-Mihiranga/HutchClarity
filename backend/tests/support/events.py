"""One valid example payload per event type, shared by contract and outbox tests."""

from __future__ import annotations

from datetime import UTC, date, datetime

from clarity.contracts.decision import ActionType, Outcome
from clarity.contracts.events import (
    ActionCompletedV1,
    ActionFailedV1,
    ActionRequestedV1,
    ActionStepV1,
    ApprovalRequestedV1,
    CaseCreatedV1,
    CauseDetectedV1,
    ChargeAppliedV1,
    ClusterUpdatedV1,
    ComplaintCreatedV1,
    ConversationTurnCompletedV1,
    DecisionGeneratedV1,
    DomainEventType,
    EventPayload,
    ForecastReadyV1,
    KnowledgePublishedV1,
    McpInvokedV1,
    PackExpiringV1,
    PaymentRecordedV1,
    PolicyPublishedV1,
    ReceiptIssuedV1,
    ReconciliationMismatchV1,
    RiskDetectedV1,
    RulePublishedV1,
    SpikeDetectedV1,
    UsageThresholdReachedV1,
    VasRenewedV1,
)
from clarity.kernel.common import Channel, Language

AT = datetime(2027, 9, 14, 14, 6, tzinfo=UTC)

SAMPLES: dict[DomainEventType, EventPayload] = {
    p.event_type: p
    for p in (
        PaymentRecordedV1(
            payment_ref="pay-1", amount_lkr="3500.00", bank_ref_hash="sha256:aa", captured_at=AT
        ),
        ChargeAppliedV1(
            charge_ref="chg-1", amount_lkr="49.00", merchant_id="MER-GAMEHUB", rated_at=AT
        ),
        UsageThresholdReachedV1(
            offering_id="PKG-DATA-30", bucket="data", threshold_percent=80, reached_at=AT
        ),
        PackExpiringV1(offering_id="PKG-DATA-30", expires_at=AT),
        VasRenewedV1(
            subscription_id="SUB-GAME-1",
            merchant_id="MER-GAMEHUB",
            amount_lkr="49.00",
            renewed_at=AT,
        ),
        ComplaintCreatedV1(complaint_id="CMP-1", channel=Channel.APP, language=Language.SI),
        CaseCreatedV1(
            case_id="CASE-1",
            case_no="CL-2027-000001",
            channel=Channel.APP,
            trigger="customer",
            language=Language.SI,
        ),
        CauseDetectedV1(
            case_id="CASE-1",
            rule_id="VAS_NO_CONSENT",
            rule_version=4,
            confidence=0.96,
            snapshot_hash="sha256:bb",
        ),
        DecisionGeneratedV1(
            case_id="CASE-1",
            decision_id="DEC-1",
            outcome=Outcome.ONE_TAP_FIX,
            amount_lkr="49.00",
            policy_version="2027.09.1",
            input_hash="sha256:cc",
        ),
        ActionRequestedV1(
            case_id="CASE-1",
            plan_id="PLAN-1",
            action_id="ACT-1",
            action_type=ActionType.REFUND,
            amount_lkr="49.00",
            idempotency_key="CASE-1:PLAN-1:0",
        ),
        ActionCompletedV1(
            case_id="CASE-1",
            plan_id="PLAN-1",
            decision_id="DEC-1",
            steps=[
                ActionStepV1(
                    action_id="ACT-1",
                    action_type=ActionType.REFUND,
                    amount_lkr="49.00",
                    status="COMPLETED",
                    idempotency_key="case-1:plan-1:0:refund",
                    adapter_ref="adj-1",
                )
            ],
            confirmed_by="customer_confirmed",
            total_amount_lkr="49.00",
        ),
        ApprovalRequestedV1(
            case_id="CASE-1",
            plan_id="PLAN-1",
            decision_id="DEC-1",
            total_amount_lkr="12000.00",
            approvals_needed=2,
            approvals_held=1,
            four_eyes_threshold_lkr="25000.00",
            requested_by="agent-1",
        ),
        ActionFailedV1(
            case_id="CASE-1",
            plan_id="PLAN-1",
            failed_step=ActionType.DEACTIVATE_VAS,
            error_code="ADAPTER_TIMEOUT",
            compensated=True,
        ),
        ReceiptIssuedV1(
            case_id="CASE-1",
            receipt_id="TR-2027-000001",
            plan_id="PLAN-1",
            payload_hash="sha256:dd",
            key_id="clarity-rcpt-2027-01",
        ),
        RiskDetectedV1(
            risk_type="duplicate_reload", band="high", score=0.97, evidence_refs=["ev-1", "ev-2"]
        ),
        McpInvokedV1(
            invocation_id="MCP-1",
            tool="get_case_timeline",
            profile="customer-assist",
            allowed=True,
            args_hash="sha256:ee",
            latency_ms=12,
        ),
        RulePublishedV1(
            rule_id="VAS_NO_CONSENT", rule_version=4, pack_hash="sha256:ff", change_class="C2"
        ),
        PolicyPublishedV1(
            change_id="CHG-1",
            key="decision.auto_fix.cap_lkr",
            policy_version=2,
            change_class="C3",
            effective_from=AT,
        ),
        KnowledgePublishedV1(
            source_id="SIM-TC-FUP",
            source_version=2,
            kind="legal_text",
            owner="legal-sim",
            audience="customer",
            language="en",
            effective_from=AT,
            chunk_count=3,
            corpus_version="sha256:aa",
        ),
        ReconciliationMismatchV1(
            plan_id="PLAN-1",
            action_id="ACT-1",
            expected_lkr="49.00",
            reason="no adapter confirmation",
        ),
        ConversationTurnCompletedV1(
            case_id="CASE-1",
            turn_no=2,
            channel=Channel.WHATSAPP,
            flow="vas_dispute",
            flow_state="awaiting_confirmation",
            intent="UNEXPECTED_CHARGE",
            language=Language.SI,
            resumed=True,
            tools_called=["get_case_timeline"],
            chunk_ids=["chunk-7"],
            verifier_ok=True,
        ),
        ClusterUpdatedV1(
            cluster_id="CL-1",
            status="confirmed",
            size=12,
            suggested_rule_id="VAS_NO_CONSENT",
            reviewed_by="cx:ruwan",
        ),
        ForecastReadyV1(
            run_id="RUN-1",
            report_id="FOR-1",
            scenario_id="SIM-1",
            scenario_version_id="SCV-1",
            change_type="pack_retired",
            effective_date=date(2027, 10, 1),
            predicted_pairs=15,
            high_band_pairs=2,
            backtested=False,
            calibration_status="not_calibrated",
        ),
        SpikeDetectedV1(
            spike_id="SPK-app-1798783200",
            scope="channel",
            scope_ref="app",
            window_start=AT,
            window_end=AT,
            observed=12,
            baseline="2.000",
            threshold_multiple="3",
        ),
    )
}
