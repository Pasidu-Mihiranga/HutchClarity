"""Idempotent tool layer with budget cap (lite in-memory)."""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from clarity.kernel.common import money, utc_now
from clarity.kernel.ids import new_id
from clarity.platform.idempotency.store import MemoryIdempotencyStore

EXECUTABLE = frozenset({"refund", "credit", "cancel_vas", "REFUND", "CREDIT", "CANCEL_VAS"})


class ToolLayerError(RuntimeError):
    code = "TOOL_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


class BudgetExhausted(ToolLayerError):
    code = "BUDGET_EXHAUSTED"


class IdempotencyConflict(ToolLayerError):
    code = "IDEMPOTENCY_CONFLICT"


@dataclass
class _Budget:
    daily_limit_lkr: Decimal = field(default_factory=lambda: Decimal("250000.00"))
    spent_lkr: Decimal = field(default_factory=lambda: Decimal("0.00"))
    reserved_lkr: Decimal = field(default_factory=lambda: Decimal("0.00"))

    @property
    def remaining(self) -> Decimal:
        return money(self.daily_limit_lkr - self.spent_lkr - self.reserved_lkr)

    def reserve(self, amount: Decimal) -> None:
        wanted = money(amount)
        if wanted > self.remaining:
            raise BudgetExhausted(
                f"refund budget cannot cover LKR {wanted} (remaining LKR {self.remaining})"
            )
        self.reserved_lkr = money(self.reserved_lkr + wanted)

    def commit(self, amount: Decimal) -> None:
        wanted = money(amount)
        self.reserved_lkr = money(max(Decimal("0.00"), self.reserved_lkr - wanted))
        self.spent_lkr = money(self.spent_lkr + wanted)

    def release(self, amount: Decimal) -> None:
        wanted = money(amount)
        self.reserved_lkr = money(max(Decimal("0.00"), self.reserved_lkr - wanted))


@dataclass
class ActionRecord:
    action_id: str
    case_id: str | None
    subscriber_ref: str
    action_type: str
    amount_lkr: Decimal | None
    status: str
    idempotency_key: str | None = None
    confirmation_token: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] | None = None
    created_at: str = field(default_factory=lambda: utc_now().isoformat())
    executed_at: str | None = None
    approved_by: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "id": self.action_id,
            "case_id": self.case_id,
            "subscriber_ref": self.subscriber_ref,
            "action_type": self.action_type,
            "amount_lkr": f"{self.amount_lkr:.2f}" if self.amount_lkr is not None else None,
            "status": self.status,
            "idempotency_key": self.idempotency_key,
            "confirmation_token": self.confirmation_token,
            "params": self.params,
            "result": self.result,
            "created_at": self.created_at,
            "executed_at": self.executed_at,
            "approved_by": self.approved_by,
        }


class ToolLayer:
    """Propose → confirm/approve → execute with idempotency + budget."""

    def __init__(
        self,
        *,
        idempotency: MemoryIdempotencyStore | None = None,
        daily_budget_lkr: Decimal | str = "250000.00",
    ) -> None:
        self._idem = idempotency or MemoryIdempotencyStore()
        self._budget = _Budget(daily_limit_lkr=money(daily_budget_lkr))
        self._actions: dict[str, ActionRecord] = {}
        self._lock = threading.Lock()
        # Executed actions awaiting adapter confirmation (for reconciliation).
        self.executed: list[dict[str, Any]] = []

    @property
    def budget_remaining(self) -> Decimal:
        return self._budget.remaining

    def propose(
        self,
        *,
        action_type: str,
        subscriber_ref: str,
        case_id: str | None = None,
        amount_lkr: Any | None = None,
        idempotency_key: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalised = action_type.strip().lower()
        if normalised not in {a.lower() for a in EXECUTABLE}:
            raise ValueError(f"unsupported action_type: {action_type}")
        amount = money(amount_lkr) if amount_lkr is not None else None
        if normalised in {"refund", "credit"} and amount is None:
            raise ValueError(f"{normalised} requires amount_lkr")

        record = ActionRecord(
            action_id=new_id("ACT"),
            case_id=case_id,
            subscriber_ref=subscriber_ref,
            action_type=normalised,
            amount_lkr=amount,
            status="proposed",
            idempotency_key=idempotency_key,
            params=dict(params or {}),
        )
        with self._lock:
            self._actions[record.action_id] = record
        return record.to_dict()

    def confirm(self, action_id: str, *, subscriber_ref: str) -> dict[str, Any]:
        with self._lock:
            record = self._require(action_id)
            if record.subscriber_ref != subscriber_ref:
                raise ToolLayerError("subscriber_ref does not match action", code="FORBIDDEN")
            if record.status not in {"proposed", "awaiting_confirmation"}:
                raise ToolLayerError(
                    f"action is {record.status}, cannot confirm", code="NOT_PENDING"
                )
            token = new_id("TOK")
            record.confirmation_token = token
            record.status = "confirmed"
            return record.to_dict()

    def approve(self, action_id: str, *, approver_ref: str) -> dict[str, Any]:
        with self._lock:
            record = self._require(action_id)
            if record.status not in {"proposed", "awaiting_confirmation", "confirmed"}:
                raise ToolLayerError(
                    f"action is {record.status}, cannot approve", code="NOT_PENDING"
                )
            token = record.confirmation_token or new_id("TOK")
            record.confirmation_token = token
            record.approved_by = approver_ref
            record.status = "approved"
            return record.to_dict()

    def execute(
        self,
        action_id: str,
        *,
        idempotency_key: str,
        confirmation_token: str | None = None,
    ) -> dict[str, Any]:
        """Execute refund / credit / cancel_vas. Idempotent on key."""
        payload_hash = hashlib.sha256(
            json.dumps({"action_id": action_id}, sort_keys=True).encode()
        ).hexdigest()

        existing = self._idem.get(key=idempotency_key, scope="tool.execute")
        if existing is not None:
            if existing["request_hash"] != payload_hash:
                raise IdempotencyConflict("Idempotency-Key reused with a different payload")
            return dict(existing["response"])

        with self._lock:
            record = self._require(action_id)
            if record.status not in {"confirmed", "approved"}:
                raise ToolLayerError(
                    "action needs confirm or approve before execute",
                    code="CONFIRMATION_REQUIRED",
                )
            if confirmation_token and record.confirmation_token != confirmation_token:
                raise ToolLayerError("invalid confirmation token", code="CONFIRMATION_INVALID")

            amount = record.amount_lkr or Decimal("0.00")
            if amount > 0:
                self._budget.reserve(amount)

            try:
                result = self._apply(record)
                if amount > 0:
                    self._budget.commit(amount)
            except Exception:
                if amount > 0:
                    self._budget.release(amount)
                raise

            record.status = "completed"
            record.idempotency_key = idempotency_key
            record.executed_at = utc_now().isoformat()
            record.result = result
            payload = record.to_dict()
            self.executed.append(payload)

        self._idem.put(
            key=idempotency_key,
            scope="tool.execute",
            request_hash_value=payload_hash,
            response=payload,
            status_code=200,
        )
        return payload

    def get(self, action_id: str) -> dict[str, Any]:
        with self._lock:
            return self._require(action_id).to_dict()

    def list_executed(self, *, day: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            if day is None:
                return list(self.executed)
            return [a for a in self.executed if (a.get("executed_at") or "").startswith(day)]

    def _apply(self, record: ActionRecord) -> dict[str, Any]:
        """Simulate adapter execution for lite profile."""
        kind = record.action_type.lower()
        if kind == "refund":
            return {
                "adapter": "billing",
                "op": "refund",
                "amount_lkr": f"{record.amount_lkr:.2f}",
                "accepted": True,
                "confirmation_ref": new_id("ADX"),
            }
        if kind == "credit":
            return {
                "adapter": "billing",
                "op": "credit",
                "amount_lkr": f"{record.amount_lkr:.2f}",
                "accepted": True,
                "confirmation_ref": new_id("ADX"),
            }
        if kind == "cancel_vas":
            return {
                "adapter": "vas",
                "op": "cancel_vas",
                "subscription_id": record.params.get("subscription_id"),
                "accepted": True,
                "confirmation_ref": new_id("ADX"),
            }
        raise ToolLayerError(f"cannot execute {record.action_type}", code="UNSUPPORTED")

    def _require(self, action_id: str) -> ActionRecord:
        record = self._actions.get(action_id)
        if record is None:
            raise ToolLayerError(f"no such action: {action_id}", code="NOT_FOUND")
        return record

    def clear(self) -> None:
        with self._lock:
            self._actions.clear()
            self.executed.clear()
            self._budget = _Budget(daily_limit_lkr=self._budget.daily_limit_lkr)
