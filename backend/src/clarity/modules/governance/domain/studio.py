"""Policy studio: teach-once, golden runs, what-if replay, four-eyes publish."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from clarity.kernel.common import utc_now
from clarity.kernel.ids import new_id


class ChangeClass(StrEnum):
    """Policy change classes C0–C4 and emergency E."""

    C0 = "C0"  # copy / wording only
    C1 = "C1"  # threshold tweak
    C2 = "C2"  # new detector branch
    C3 = "C3"  # decision outcome change
    C4 = "C4"  # money-path / auto-fix
    E = "E"  # emergency hotfix


@dataclass(slots=True)
class TaughtExample:
    id: str
    case_summary: str
    expected_cause: str
    expected_outcome: str
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "case_summary": self.case_summary,
            "expected_cause": self.expected_cause,
            "expected_outcome": self.expected_outcome,
            "notes": self.notes,
        }


@dataclass(slots=True)
class PolicyBundle:
    id: str
    change_class: ChangeClass
    proposal: dict[str, Any]
    signature: str
    status: str = "draft"  # draft | pending_four_eyes | published
    approvals: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: utc_now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "change_class": self.change_class.value,
            "proposal": dict(self.proposal),
            "signature": self.signature,
            "status": self.status,
            "approvals": list(self.approvals),
            "created_at": self.created_at,
        }


def sign_bundle(payload: dict[str, Any], *, secret: str = "clarity-dev") -> str:
    raw = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(secret.encode("utf-8") + raw).hexdigest()


class PolicyStudio:
    def __init__(self) -> None:
        self.examples: list[TaughtExample] = []
        self.replays: list[dict[str, Any]] = []
        self.bundles: dict[str, PolicyBundle] = {}
        self.golden_results: list[dict[str, Any]] = []

    def teach_once(
        self,
        *,
        case_summary: str,
        expected_cause: str,
        expected_outcome: str,
        notes: str = "",
    ) -> TaughtExample:
        example = TaughtExample(
            id=new_id("TCH"),
            case_summary=case_summary,
            expected_cause=expected_cause,
            expected_outcome=expected_outcome,
            notes=notes,
        )
        self.examples.append(example)
        return example

    def golden_run(self, *, rule_id: str | None = None) -> dict[str, Any]:
        """Replay taught examples as a golden suite."""
        passed = 0
        failures: list[dict[str, Any]] = []
        for ex in self.examples:
            # Lite: "pass" if expected fields are non-empty (stand-in for detector replay).
            ok = bool(ex.expected_cause and ex.expected_outcome)
            if ok:
                passed += 1
            else:
                failures.append(ex.to_dict())
        result = {
            "run_id": new_id("GLD"),
            "rule_id": rule_id,
            "total": len(self.examples),
            "passed": passed,
            "failed": len(failures),
            "failures": failures,
            "ran_at": utc_now().isoformat(),
        }
        self.golden_results.append(result)
        return result

    def what_if_replay(
        self,
        *,
        timeline: dict[str, Any],
        proposal: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Policy what-if: compare baseline vs proposal labels on a timeline."""
        detections = list(timeline.get("detections") or [])
        baseline_outcome = str(timeline.get("outcome") or "EXPLAIN_ONLY")
        proposal = proposal or {}
        candidate_outcome = str(proposal.get("outcome") or baseline_outcome)
        replay = {
            "replay_id": new_id("RPL"),
            "baseline_outcome": baseline_outcome,
            "candidate_outcome": candidate_outcome,
            "detections": detections,
            "changed": baseline_outcome != candidate_outcome,
            "proposal": proposal,
            "ran_at": utc_now().isoformat(),
        }
        self.replays.append(replay)
        return replay

    def four_eyes_publish(
        self,
        *,
        proposal: dict[str, Any],
        change_class: str | ChangeClass,
        approver_a: str,
        approver_b: str | None = None,
    ) -> PolicyBundle:
        cc = ChangeClass(change_class)
        if approver_a == approver_b:
            raise ValueError("four-eyes requires two distinct approvers")
        # C3/C4/E require both eyes before publish
        needs_second = cc in {ChangeClass.C3, ChangeClass.C4, ChangeClass.E}
        approvals = [approver_a]
        status = "pending_four_eyes"
        if needs_second:
            if not approver_b:
                bundle = PolicyBundle(
                    id=new_id("BND"),
                    change_class=cc,
                    proposal=proposal,
                    signature=sign_bundle(proposal),
                    status=status,
                    approvals=approvals,
                )
                self.bundles[bundle.id] = bundle
                return bundle
            approvals.append(approver_b)
        else:
            if approver_b:
                approvals.append(approver_b)
        bundle = PolicyBundle(
            id=new_id("BND"),
            change_class=cc,
            proposal=proposal,
            signature=sign_bundle({"proposal": proposal, "change_class": cc.value}),
            status="published",
            approvals=approvals,
        )
        self.bundles[bundle.id] = bundle
        return bundle

    def clear(self) -> None:
        self.examples.clear()
        self.replays.clear()
        self.bundles.clear()
        self.golden_results.clear()
