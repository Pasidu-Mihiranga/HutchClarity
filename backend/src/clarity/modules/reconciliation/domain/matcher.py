"""Match executed actions to adapter confirmations (T+1)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Mismatch:
    action_id: str
    reason: str
    action: dict[str, Any]
    confirmation: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "reason": self.reason,
            "action": self.action,
            "confirmation": self.confirmation,
        }


@dataclass
class ReconciliationStore:
    """Holds adapter confirmation feed for matching (lite)."""

    confirmations: list[dict[str, Any]] = field(default_factory=list)

    def add_confirmation(self, confirmation: dict[str, Any]) -> None:
        self.confirmations.append(confirmation)

    def clear(self) -> None:
        self.confirmations.clear()


def match_actions(
    actions: list[dict[str, Any]],
    confirmations: list[dict[str, Any]],
) -> list[Mismatch]:
    """Compare Clarity-executed actions to adapter confirmations.

    Match key preference: result.confirmation_ref → action_id → idempotency_key.
    """
    by_ref: dict[str, dict[str, Any]] = {}
    for conf in confirmations:
        for key_name in ("confirmation_ref", "action_id", "idempotency_key"):
            key = conf.get(key_name)
            if key:
                by_ref[str(key)] = conf

    mismatches: list[Mismatch] = []
    matched_refs: set[str] = set()

    for action in actions:
        result = action.get("result") or {}
        candidates = [
            result.get("confirmation_ref"),
            action.get("action_id"),
            action.get("id"),
            action.get("idempotency_key"),
        ]
        conf: dict[str, Any] | None = None
        matched_key: str | None = None
        for candidate in candidates:
            if candidate and str(candidate) in by_ref:
                conf = by_ref[str(candidate)]
                matched_key = str(candidate)
                break

        if conf is None:
            mismatches.append(
                Mismatch(
                    action_id=str(action.get("action_id") or action.get("id") or "?"),
                    reason="missing_confirmation",
                    action=action,
                )
            )
            continue

        matched_refs.add(matched_key or "")
        # Amount check when both sides carry money.
        action_amount = action.get("amount_lkr")
        conf_amount = conf.get("amount_lkr")
        if (
            action_amount is not None
            and conf_amount is not None
            and str(action_amount) != str(conf_amount)
        ):
            mismatches.append(
                Mismatch(
                    action_id=str(action.get("action_id") or action.get("id") or "?"),
                    reason="amount_mismatch",
                    action=action,
                    confirmation=conf,
                )
            )
            continue

        if conf.get("accepted") is False:
            mismatches.append(
                Mismatch(
                    action_id=str(action.get("action_id") or action.get("id") or "?"),
                    reason="adapter_rejected",
                    action=action,
                    confirmation=conf,
                )
            )

    # Orphan confirmations with no Clarity action.
    for conf in confirmations:
        keys = [
            str(conf[k])
            for k in ("confirmation_ref", "action_id", "idempotency_key")
            if conf.get(k)
        ]
        if keys and not any(k in matched_refs for k in keys):
            # Only flag if none of its keys matched any action.
            action_ids = {
                str(a.get("action_id") or a.get("id") or "")
                for a in actions
            }
            refs = {
                str((a.get("result") or {}).get("confirmation_ref") or "")
                for a in actions
            }
            if not any(k in action_ids or k in refs for k in keys):
                mismatches.append(
                    Mismatch(
                        action_id=str(conf.get("action_id") or conf.get("confirmation_ref") or "?"),
                        reason="orphan_confirmation",
                        action={},
                        confirmation=conf,
                    )
                )

    return mismatches
