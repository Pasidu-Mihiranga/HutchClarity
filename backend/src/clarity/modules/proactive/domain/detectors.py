"""Zero-contact stream detectors for proactive outreach."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from clarity.kernel.events import EventType
from clarity.kernel.ids import new_id


@dataclass(slots=True)
class ProactiveAction:
    action_id: str
    kind: str
    subscriber_ref: str
    reason: str
    priority: str
    channel_hint: str = "app"
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "kind": self.kind,
            "subscriber_ref": self.subscriber_ref,
            "reason": self.reason,
            "priority": self.priority,
            "channel_hint": self.channel_hint,
            "payload": dict(self.payload),
        }


DetectorFn = Callable[[dict[str, Any]], list[ProactiveAction]]


def _ref(event: dict[str, Any]) -> str:
    return str(
        event.get("subscriber_ref")
        or event.get("subject")
        or (event.get("data") or {}).get("subscriber_ref")
        or ""
    )


def _data(event: dict[str, Any]) -> dict[str, Any]:
    data = event.get("data")
    return data if isinstance(data, dict) else {}


def _etype(event: dict[str, Any]) -> str:
    raw = event.get("type") or event.get("event_type") or ""
    return str(raw)


def detect_payment_refund_path(event: dict[str, Any]) -> list[ProactiveAction]:
    """Zero-contact duplicate-reload refund path on payment.recorded."""
    if _etype(event) not in {EventType.PAYMENT_RECORDED.value, "payment.recorded"}:
        return []
    data = _data(event)
    if not data.get("duplicate") and not data.get("zero_contact_refund"):
        # Also fire when two payments share the same amount within a short window flag.
        if not data.get("likely_duplicate"):
            return []
    ref = _ref(event)
    if not ref:
        return []
    return [
        ProactiveAction(
            action_id=new_id("PRA"),
            kind="zero_contact_refund",
            subscriber_ref=ref,
            reason="duplicate payment.recorded eligible for auto-refund path",
            priority="high",
            payload={
                "payment_id": data.get("payment_id"),
                "amount_lkr": data.get("amount_lkr"),
                "path": "auto_fix",
            },
        )
    ]


def detect_fup_thresholds(event: dict[str, Any]) -> list[ProactiveAction]:
    """FUP 80% / 95% heads-up."""
    if _etype(event) not in {
        EventType.USAGE_THRESHOLD_REACHED.value,
        "usage.threshold_reached",
        "fup.threshold",
    }:
        return []
    data = _data(event)
    pct = data.get("percent") or data.get("threshold_pct") or data.get("fup_pct")
    try:
        pct_f = float(pct)
    except (TypeError, ValueError):
        return []
    if pct_f < 80:
        return []
    band = "95" if pct_f >= 95 else "80"
    ref = _ref(event)
    if not ref:
        return []
    return [
        ProactiveAction(
            action_id=new_id("PRA"),
            kind=f"fup_{band}_notice",
            subscriber_ref=ref,
            reason=f"FUP usage reached {band}%",
            priority="medium" if band == "80" else "high",
            channel_hint="sms",
            payload={"percent": pct_f, "pack_sku": data.get("pack_sku")},
        )
    ]


def detect_pack_end_choice(event: dict[str, Any]) -> list[ProactiveAction]:
    """Choose-before-you-pay when pack is expiring."""
    if _etype(event) not in {EventType.PACK_EXPIRING.value, "pack.expiring"}:
        return []
    ref = _ref(event)
    if not ref:
        return []
    data = _data(event)
    return [
        ProactiveAction(
            action_id=new_id("PRA"),
            kind="pack_end_choice",
            subscriber_ref=ref,
            reason="pack ending — offer renewal choices before PAYG burn",
            priority="medium",
            payload={
                "pack_sku": data.get("pack_sku"),
                "expires_at": data.get("expires_at"),
                "choices": data.get("choices") or ["renew", "downgrade", "stop"],
            },
        )
    ]


def detect_vas_renewal_notice(event: dict[str, Any]) -> list[ProactiveAction]:
    if _etype(event) not in {EventType.VAS_RENEWED.value, "vas.renewed", "vas.renewal_due"}:
        return []
    ref = _ref(event)
    if not ref:
        return []
    data = _data(event)
    return [
        ProactiveAction(
            action_id=new_id("PRA"),
            kind="vas_renewal_notice",
            subscriber_ref=ref,
            reason="VAS renewal notice before next charge",
            priority="medium",
            channel_hint="app",
            payload={
                "subscription_id": data.get("subscription_id"),
                "amount_lkr": data.get("amount_lkr"),
                "renews_at": data.get("renews_at"),
            },
        )
    ]


def detect_outage_heads_up(event: dict[str, Any]) -> list[ProactiveAction]:
    et = _etype(event)
    if et not in {"outage.detected", "outage.planned", EventType.RISK_DETECTED.value}:
        data = _data(event)
        if not data.get("outage"):
            return []
    else:
        data = _data(event)
        if et == EventType.RISK_DETECTED.value and not data.get("outage"):
            return []
    ref = _ref(event)
    if not ref and not data.get("segment"):
        return []
    return [
        ProactiveAction(
            action_id=new_id("PRA"),
            kind="outage_heads_up",
            subscriber_ref=ref or str(data.get("segment", "segment")),
            reason="outage heads-up with ETA",
            priority="high",
            channel_hint="sms",
            payload={
                "eta": data.get("eta"),
                "region": data.get("region"),
                "outage_id": data.get("outage_id"),
            },
        )
    ]


def detect_bill_shock(event: dict[str, Any]) -> list[ProactiveAction]:
    """Bill-shock score from spend velocity / PAYG burn signals."""
    data = _data(event)
    score = data.get("bill_shock_score")
    if score is None:
        # Derive a crude score from burn flags
        if data.get("payg_burn") or data.get("spend_velocity") == "high":
            score = 0.75
        elif _etype(event) in {EventType.CHARGE_APPLIED.value, "charge.applied"} and data.get(
            "amount_lkr"
        ):
            try:
                amt = float(data["amount_lkr"])
            except (TypeError, ValueError):
                return []
            if amt < 500:
                return []
            score = min(1.0, amt / 2000.0)
        else:
            return []
    try:
        score_f = float(score)
    except (TypeError, ValueError):
        return []
    if score_f < 0.6:
        return []
    ref = _ref(event)
    if not ref:
        return []
    return [
        ProactiveAction(
            action_id=new_id("PRA"),
            kind="bill_shock_alert",
            subscriber_ref=ref,
            reason=f"bill-shock score {score_f:.2f}",
            priority="high" if score_f >= 0.8 else "medium",
            payload={"bill_shock_score": score_f},
        )
    ]


DETECTORS: list[DetectorFn] = [
    detect_payment_refund_path,
    detect_fup_thresholds,
    detect_pack_end_choice,
    detect_vas_renewal_notice,
    detect_outage_heads_up,
    detect_bill_shock,
]


def run_detectors(event: dict[str, Any]) -> list[ProactiveAction]:
    actions: list[ProactiveAction] = []
    for detector in DETECTORS:
        actions.extend(detector(event))
    return actions
