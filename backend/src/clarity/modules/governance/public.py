"""Public facade for the governance module."""

from __future__ import annotations

from typing import Any

from clarity.modules.governance.domain.studio import ChangeClass, PolicyStudio

_studio = PolicyStudio()


def reset_governance() -> None:
    _studio.clear()


def teach(
    *,
    case_summary: str,
    expected_cause: str,
    expected_outcome: str,
    notes: str = "",
) -> dict[str, Any]:
    return _studio.teach_once(
        case_summary=case_summary,
        expected_cause=expected_cause,
        expected_outcome=expected_outcome,
        notes=notes,
    ).to_dict()


def golden_run(*, rule_id: str | None = None) -> dict[str, Any]:
    return _studio.golden_run(rule_id=rule_id)


def replay(
    *,
    timeline: dict[str, Any],
    proposal: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _studio.what_if_replay(timeline=timeline, proposal=proposal)


def publish(
    *,
    proposal: dict[str, Any],
    change_class: str = "C1",
    approver_a: str,
    approver_b: str | None = None,
) -> dict[str, Any]:
    return _studio.four_eyes_publish(
        proposal=proposal,
        change_class=change_class,
        approver_a=approver_a,
        approver_b=approver_b,
    ).to_dict()


__all__ = [
    "ChangeClass",
    "golden_run",
    "publish",
    "replay",
    "reset_governance",
    "teach",
]
