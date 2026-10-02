"""Decision engine: ZEN table remedies + hard gates in code."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from clarity.kernel.ids import new_id
from clarity.modules.detection.domain.models import Detection
from clarity.modules.decision.domain.zen_tables import DEFAULT_CAPS, table_for


def _money(value: Any, default: Decimal = Decimal("0.00")) -> Decimal:
    if value is None:
        return default
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except Exception:  # noqa: BLE001
        return default


def _resolve_amount(formula: str, detection: Detection, cap: Decimal) -> Decimal:
    amount = detection.amount_lkr or Decimal("0.00")
    text = (formula or "0").strip()
    if text in {"$detection.amount_lkr", "$amount"}:
        return amount
    if text.startswith("min(") and text.endswith(")"):
        inner = text[4:-1]
        parts = [p.strip() for p in inner.split(",")]
        values: list[Decimal] = []
        for part in parts:
            if part in {"$detection.amount_lkr", "$amount"}:
                values.append(amount)
            elif part == "$cap":
                values.append(cap)
            else:
                values.append(_money(part))
        return min(values) if values else Decimal("0.00")
    return _money(text)


@dataclass(slots=True)
class Decision:
    decision_id: str
    outcome: str
    rule_id: str | None
    rule_version: str | None
    action_type: str
    amount_lkr: Decimal
    requires_approval: bool
    requires_four_eyes: bool
    cap_lkr: Decimal
    rationale: list[str] = field(default_factory=list)
    table_id: str | None = None
    table_version: str | None = None
    top_confidence: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "outcome": self.outcome,
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
            "action_type": self.action_type,
            "amount_lkr": f"{self.amount_lkr:.2f}",
            "requires_approval": self.requires_approval,
            "requires_four_eyes": self.requires_four_eyes,
            "cap_lkr": f"{self.cap_lkr:.2f}",
            "rationale": self.rationale,
            "table_id": self.table_id,
            "table_version": self.table_version,
            "top_confidence": self.top_confidence,
        }


def evaluate(
    detections: list[Detection],
    caps: dict[str, Any] | None = None,
    *,
    risk: dict[str, Any] | None = None,
) -> Decision:
    """Map top detection through ZEN tables; apply hard gates in code.

    Hard gates:
    - recent SIM swap -> HANDOFF
    - amount > four_eyes threshold -> FOUR_EYES (staff + finance)
    """
    merged = {**DEFAULT_CAPS, **(caps or {})}
    auto_cap = _money(merged.get("auto_cap_lkr"), Decimal("1000.00"))
    one_tap_cap = _money(merged.get("one_tap_cap_lkr"), Decimal("5000.00"))
    four_eyes = _money(merged.get("four_eyes_threshold_lkr"), Decimal("25000.00"))
    sim_window = int(merged.get("sim_swap_window_days", 7))
    risk = risk or {}
    why: list[str] = []

    # Hard gate: SIM swap
    sim_days = risk.get("sim_swap_days")
    if sim_days is not None and int(sim_days) <= sim_window:
        why.append(f"SIM swap {sim_days} days ago (within {sim_window}) → handoff")
        return Decision(
            decision_id=new_id("DEC"),
            outcome="HANDOFF",
            rule_id=detections[0].rule_id if detections else None,
            rule_version=detections[0].version if detections else None,
            action_type="HANDOFF",
            amount_lkr=Decimal("0.00"),
            requires_approval=True,
            requires_four_eyes=False,
            cap_lkr=one_tap_cap,
            rationale=why,
            top_confidence=detections[0].confidence if detections else None,
        )

    if not detections:
        why.append("no detections to decide on")
        return Decision(
            decision_id=new_id("DEC"),
            outcome="HANDOFF",
            rule_id=None,
            rule_version=None,
            action_type="HANDOFF",
            amount_lkr=Decimal("0.00"),
            requires_approval=True,
            requires_four_eyes=False,
            cap_lkr=one_tap_cap,
            rationale=why,
        )

    top = detections[0]
    table = table_for(top.rule_id)
    if table is None:
        why.append(f"no ZEN table for {top.rule_id}")
        return Decision(
            decision_id=new_id("DEC"),
            outcome="HANDOFF",
            rule_id=top.rule_id,
            rule_version=top.version,
            action_type="HANDOFF",
            amount_lkr=top.amount_lkr or Decimal("0.00"),
            requires_approval=True,
            requires_four_eyes=False,
            cap_lkr=one_tap_cap,
            rationale=why,
            top_confidence=top.confidence,
        )

    remedy = table.get("remedy") or {}
    cap = _money(remedy.get("cap_lkr"), one_tap_cap)
    raw_amount = _resolve_amount(str(remedy.get("refund_amount", "0")), top, cap)
    amount = raw_amount
    if amount > cap > 0:
        amount = cap
        why.append(f"amount capped at LKR {cap}")

    action_type = str(remedy.get("action_type", "EXPLAIN"))
    requires_approval = bool(remedy.get("requires_approval", False))
    outcome = str(remedy.get("outcome_hint", "STAFF_APPROVAL"))
    auto_whitelisted = bool(remedy.get("auto_whitelisted", False))

    # Soft routing from table + caps (use raw amount for threshold checks).
    check_amount = raw_amount
    if outcome == "AUTO_FIX" and (not auto_whitelisted or check_amount > auto_cap):
        why.append("auto-fix declined: whitelist/cap")
        outcome = "ONE_TAP_FIX" if check_amount <= one_tap_cap else "STAFF_APPROVAL"
        requires_approval = outcome == "STAFF_APPROVAL"

    if check_amount > one_tap_cap and outcome in {"AUTO_FIX", "ONE_TAP_FIX"}:
        why.append(f"LKR {check_amount} above one-tap cap {one_tap_cap}")
        outcome = "STAFF_APPROVAL"
        requires_approval = True

    requires_four_eyes = False
    # Hard gate: amount above four-eyes threshold (evaluated on uncapped amount).
    if check_amount > four_eyes:
        why.append(f"LKR {check_amount} above four-eyes threshold {four_eyes}")
        outcome = "FOUR_EYES"
        requires_approval = True
        requires_four_eyes = True

    if not why:
        why.append(f"ZEN table {table['table_id']}@{table['version']} → {outcome}")

    return Decision(
        decision_id=new_id("DEC"),
        outcome=outcome,
        rule_id=top.rule_id,
        rule_version=top.version,
        action_type=action_type,
        amount_lkr=amount,
        requires_approval=requires_approval,
        requires_four_eyes=requires_four_eyes,
        cap_lkr=cap,
        rationale=why,
        table_id=table.get("table_id"),
        table_version=str(table.get("version")),
        top_confidence=top.confidence,
    )
