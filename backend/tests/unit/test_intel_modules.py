"""Smoke tests for intelligence modules (E1–E7 + content)."""

from __future__ import annotations

from clarity.modules.autopsy.module import AutopsyModule
from clarity.modules.content.module import ContentModule
from clarity.modules.deskops.module import DeskOpsModule
from clarity.modules.deskops.public import get_handover, handover, reset_deskops
from clarity.modules.foresight.module import ForesightModule
from clarity.modules.governance.module import GovernanceModule
from clarity.modules.governance.public import replay, reset_governance, teach
from clarity.modules.insights.module import InsightsModule
from clarity.modules.knowledge.module import KnowledgeModule
from clarity.modules.knowledge.public import reset_knowledge, search
from clarity.modules.proactive.module import ProactiveModule
from clarity.modules.proactive.public import evaluate_event, reset_proactive


def setup_function() -> None:
    reset_knowledge()
    reset_proactive()
    reset_governance()
    reset_deskops()


def test_knowledge_search_fup_and_cache() -> None:
    first = search("what is FUP fair use cap", lang="en")
    assert first["hits"], "expected FUP article hit"
    assert first["hits"][0]["article_id"] == "KB-FUP"
    assert first["citations"]
    assert first["cached"] is False

    second = search("what is FUP fair use cap", lang="en")
    assert second["cached"] is True
    assert second["answer"]


def test_proactive_fup_80_notice() -> None:
    actions = evaluate_event(
        {
            "type": "usage.threshold_reached",
            "subscriber_ref": "sub_demo",
            "data": {"percent": 82, "pack_sku": "anytime-10gb"},
        }
    )
    assert len(actions) == 1
    assert actions[0]["kind"] == "fup_80_notice"
    assert actions[0]["subscriber_ref"] == "sub_demo"

    high = evaluate_event(
        {
            "type": "usage.threshold_reached",
            "subscriber_ref": "sub_demo",
            "data": {"percent": 96},
        }
    )
    assert high[0]["kind"] == "fup_95_notice"


def test_governance_replay_what_if() -> None:
    taught = teach(
        case_summary="duplicate reload",
        expected_cause="DOUBLE_CHARGE",
        expected_outcome="AUTO_FIX",
    )
    assert taught["id"].startswith("TCH-")

    result = replay(
        timeline={"outcome": "EXPLAIN_ONLY", "detections": [{"cause": "DOUBLE_CHARGE"}]},
        proposal={"outcome": "AUTO_FIX"},
    )
    assert result["changed"] is True
    assert result["baseline_outcome"] == "EXPLAIN_ONLY"
    assert result["candidate_outcome"] == "AUTO_FIX"


def test_deskops_handover() -> None:
    recorded = handover(
        team="desk",
        from_shift="morning",
        to_shift="evening",
        open_cases=[{"id": "CAS-1"}],
        promises=["call back sub_demo"],
        owners={"CAS-1": "agent-a"},
    )
    assert recorded["id"].startswith("HDO-")

    latest = get_handover(team="desk")
    assert latest["open_cases"][0]["id"] == "CAS-1"
    assert latest["promises"] == ["call back sub_demo"]


def test_intel_module_class_names() -> None:
    assert KnowledgeModule.name == "knowledge"
    assert ProactiveModule.name == "proactive"
    assert AutopsyModule.name == "autopsy"
    assert ForesightModule.name == "foresight"
    assert GovernanceModule.name == "governance"
    assert DeskOpsModule.name == "deskops"
    assert InsightsModule.name == "insights"
    assert ContentModule.name == "content"
