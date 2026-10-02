"""Public facade for the actions module."""

from __future__ import annotations

from typing import Any

from clarity.modules.actions.domain.layer import ToolLayer, ToolLayerError

_layer = ToolLayer()


def get_tool_layer() -> ToolLayer:
    return _layer


def reset_actions(layer: ToolLayer | None = None) -> None:
    global _layer
    if layer is None:
        _layer.clear()
    else:
        _layer = layer


def propose_action(
    *,
    action_type: str,
    subscriber_ref: str,
    case_id: str | None = None,
    amount_lkr: Any | None = None,
    idempotency_key: str | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _layer.propose(
        action_type=action_type,
        subscriber_ref=subscriber_ref,
        case_id=case_id,
        amount_lkr=amount_lkr,
        idempotency_key=idempotency_key,
        params=params,
    )


def confirm_action(action_id: str, *, subscriber_ref: str) -> dict[str, Any]:
    return _layer.confirm(action_id, subscriber_ref=subscriber_ref)


def approve_action(action_id: str, *, approver_ref: str) -> dict[str, Any]:
    return _layer.approve(action_id, approver_ref=approver_ref)


def execute_action(
    action_id: str,
    *,
    idempotency_key: str,
    confirmation_token: str | None = None,
) -> dict[str, Any]:
    return _layer.execute(
        action_id,
        idempotency_key=idempotency_key,
        confirmation_token=confirmation_token,
    )


__all__ = [
    "ToolLayer",
    "ToolLayerError",
    "approve_action",
    "confirm_action",
    "execute_action",
    "get_tool_layer",
    "propose_action",
    "reset_actions",
]
