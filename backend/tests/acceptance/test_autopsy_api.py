"""The Complaint Autopsy reviewer workspace over HTTP (D1).

Autopsy had the whole domain and no way to reach it: a repository, an event
consumer, a clustering pipeline and a review service with `record` and
`supersede`, behind a single read-only demo route. A cluster could be looked
at and never judged.

These cover the surface that closes that, and in particular the three refusals
that make the review step mean something: an unreviewed cluster cannot seed a
rule, a second verdict cannot quietly overwrite a first, and a reversal cannot
be unexplained.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from clarity.app.container import Clarity
from clarity.integration.drivers.mock.world import build_demo_world
from clarity.interfaces.http.main import create_app

from .conftest import bearer, staff_token

#: Four complaints in two obvious shapes, so clustering has something to find.
COMPLAINTS = {
    "CMP-1": "charged 99 rupees for a subscription I never asked for",
    "CMP-2": "charged 99 rupees for a subscription i did not ask for",
    "CMP-3": "my reload did not arrive after I paid",
    "CMP-4": "reload did not arrive even though I paid",
}


@pytest.fixture
def clarity() -> Clarity:
    core = Clarity(world=build_demo_world())
    for complaint_id, text in COMPLAINTS.items():
        core.autopsy.accept(complaint_id, text=text)
    core.autopsy.rerun()
    return core


@pytest.fixture
def api(clarity: Clarity) -> TestClient:
    return TestClient(create_app(clarity))


@pytest.fixture
def reviewer(api: TestClient) -> dict[str, str]:
    return bearer(staff_token(api, "cx:roshan", ["cx_engineer"], step_up=False))


@pytest.fixture
def agent(api: TestClient) -> dict[str, str]:
    return bearer(staff_token(api, "agent:nadeesha", ["agent"], step_up=False))


def _a_cluster(api: TestClient, headers: dict[str, str]) -> str:
    listed = api.get("/v1/autopsy/clusters", headers=headers)
    assert listed.status_code == 200, listed.text
    clusters = listed.json()["clusters"]
    assert clusters, "the fixture should have produced at least one cluster"
    return str(clusters[0]["cluster_id"])


# --------------------------------------------------------------------------- #
# Reading
# --------------------------------------------------------------------------- #


def test_the_workspace_needs_a_session(api: TestClient) -> None:
    assert api.get("/v1/autopsy/clusters").status_code == 401


def test_the_desk_can_read_without_being_able_to_rule(
    api: TestClient, agent: dict[str, str]
) -> None:
    """Reading is `desk:queue:read`, ruling is `autopsy:review`. An agent can
    see what the pattern engine thinks and cannot decide it is right."""
    assert api.get("/v1/autopsy/clusters", headers=agent).status_code == 200

    cluster_id = _a_cluster(api, agent)
    refused = api.post(
        f"/v1/autopsy/clusters/{cluster_id}/review", json={"accept": True}, headers=agent
    )

    assert refused.status_code == 403


def test_every_cluster_says_whether_anybody_has_checked_it(
    api: TestClient, reviewer: dict[str, str]
) -> None:
    """AU01's rule, still true through the new surface: an unreviewed cluster
    cannot reach a screen without saying nobody has checked it."""
    body = api.get("/v1/autopsy/clusters", headers=reviewer).json()

    assert body["hypothesis"] is True
    assert body["synthetic"] is True
    for view in body["clusters"]:
        assert "hypothesis" in view


# --------------------------------------------------------------------------- #
# Ruling
# --------------------------------------------------------------------------- #


def test_a_reviewer_can_confirm_a_cluster(api: TestClient, reviewer: dict[str, str]) -> None:
    cluster_id = _a_cluster(api, reviewer)

    ruled = api.post(
        f"/v1/autopsy/clusters/{cluster_id}/review",
        json={"accept": True, "note": "same silent VAS charge"},
        headers=reviewer,
    )

    assert ruled.status_code == 200, ruled.text
    assert ruled.json()["hypothesis"] is False


def test_the_verdict_is_attributed_to_the_caller_not_the_body(
    api: TestClient, reviewer: dict[str, str], clarity: Clarity
) -> None:
    """An anonymous verdict is not an audit record, and one attributed to
    whoever the caller typed is worse than none."""
    cluster_id = _a_cluster(api, reviewer)

    api.post(
        f"/v1/autopsy/clusters/{cluster_id}/review",
        json={"accept": True, "note": "mine"},
        headers=reviewer,
    )

    held = next(
        item for item in clarity.autopsy.clusters() if item.cluster.cluster_id == cluster_id
    )
    assert held.latest is not None
    assert held.latest.reviewer == "cx:roshan"


def test_a_second_verdict_cannot_quietly_overwrite_the_first(
    api: TestClient, reviewer: dict[str, str]
) -> None:
    """Overwriting a professional judgement with no trace of it is what
    `supersede` exists to make deliberate."""
    cluster_id = _a_cluster(api, reviewer)
    api.post(f"/v1/autopsy/clusters/{cluster_id}/review", json={"accept": True}, headers=reviewer)

    again = api.post(
        f"/v1/autopsy/clusters/{cluster_id}/review", json={"accept": False}, headers=reviewer
    )

    assert again.status_code == 409


def test_superseding_keeps_both_verdicts(
    api: TestClient, reviewer: dict[str, str], clarity: Clarity
) -> None:
    """A reversal that erased what it reversed would leave the trail saying
    the cluster was always judged this way."""
    cluster_id = _a_cluster(api, reviewer)
    api.post(f"/v1/autopsy/clusters/{cluster_id}/review", json={"accept": True}, headers=reviewer)

    changed = api.post(
        f"/v1/autopsy/clusters/{cluster_id}/supersede",
        json={"accept": False, "note": "two different causes, not one"},
        headers=reviewer,
    )

    assert changed.status_code == 200, changed.text
    held = next(
        item for item in clarity.autopsy.clusters() if item.cluster.cluster_id == cluster_id
    )
    assert len(held.reviews) == 2
    assert held.reviews[0].accepted is True
    assert held.reviews[-1].accepted is False
    assert held.reviews[-1].supersedes == held.reviews[0].review_id


def test_an_unexplained_reversal_is_refused(api: TestClient, reviewer: dict[str, str]) -> None:
    cluster_id = _a_cluster(api, reviewer)
    api.post(f"/v1/autopsy/clusters/{cluster_id}/review", json={"accept": True}, headers=reviewer)

    unexplained = api.post(
        f"/v1/autopsy/clusters/{cluster_id}/supersede",
        json={"accept": False, "note": "   "},
        headers=reviewer,
    )

    assert unexplained.status_code == 422


def test_superseding_a_cluster_nobody_judged_is_refused(
    api: TestClient, reviewer: dict[str, str]
) -> None:
    cluster_id = _a_cluster(api, reviewer)

    nothing_to_change = api.post(
        f"/v1/autopsy/clusters/{cluster_id}/supersede",
        json={"accept": False, "note": "changing what, exactly"},
        headers=reviewer,
    )

    assert nothing_to_change.status_code == 409


# --------------------------------------------------------------------------- #
# Proposing a change, through governance and nowhere else (AU02)
# --------------------------------------------------------------------------- #


def test_a_hypothesis_cannot_seed_a_policy_change(
    api: TestClient, reviewer: dict[str, str]
) -> None:
    """If an unreviewed cluster could propose one, the review step would be
    decorative."""
    cluster_id = _a_cluster(api, reviewer)

    refused = api.post(
        f"/v1/autopsy/clusters/{cluster_id}/rule-candidate",
        json={"key": "detection.vas.window", "value": "48h", "rationale": "x"},
        headers=reviewer,
    )

    assert refused.status_code == 409


def test_a_confirmed_cluster_proposes_a_draft_and_nothing_more(
    api: TestClient, reviewer: dict[str, str], clarity: Clarity
) -> None:
    """The whole point of AU02: a pattern engine never activates its own rule."""
    cluster_id = _a_cluster(api, reviewer)
    api.post(f"/v1/autopsy/clusters/{cluster_id}/review", json={"accept": True}, headers=reviewer)
    key = clarity.policies.keys()[0].key

    proposed = api.post(
        f"/v1/autopsy/clusters/{cluster_id}/rule-candidate",
        json={"key": key, "value": "1", "rationale": "the cluster shows this is too tight"},
        headers=reviewer,
    )

    assert proposed.status_code == 200, proposed.text
    body = proposed.json()
    assert body["state"] == "draft"
    # It is a draft, not an activation: the change is still waiting for
    # somebody else to review and approve it.
    assert clarity.governance.get(body["change_id"]).state.value == "draft"


def test_a_confirmed_complaint_pattern_can_complete_the_governed_policy_pipeline(
    api: TestClient, reviewer: dict[str, str], clarity: Clarity
) -> None:
    """The Desk-to-Studio seam is real: the autopsy candidate is the same
    persisted change that is reviewed, independently approved, scheduled and
    activated. Complaint text itself never bypasses governance into policy."""
    cluster_id = _a_cluster(api, reviewer)
    confirmed = api.post(
        f"/v1/autopsy/clusters/{cluster_id}/review",
        json={"accept": True, "note": "recurring complaint outside the current mapping"},
        headers=reviewer,
    )
    assert confirmed.status_code == 200, confirmed.text

    proposed = api.post(
        f"/v1/autopsy/clusters/{cluster_id}/rule-candidate",
        json={
            "key": "decision.conflict_margin",
            "value": "0.25",
            "rationale": "confirmed complaints need a wider conflict margin",
        },
        headers=reviewer,
    )
    assert proposed.status_code == 200, proposed.text
    change_id = proposed.json()["change_id"]

    replayed = api.post(
        f"/v1/admin/policy/changes/{change_id}/review",
        json={"cases_evaluated": len(COMPLAINTS), "candidate_summary": "autopsy replay"},
        headers=reviewer,
    )
    assert replayed.status_code == 200, replayed.text

    approver = bearer(staff_token(api, "fin:amara", ["finance"], step_up=True))
    approved = api.post(
        f"/v1/admin/policy/changes/{change_id}/approve", headers=approver
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["state"] == "approved"

    effective_from = datetime.now(UTC) - timedelta(seconds=1)
    scheduled = api.post(
        f"/v1/admin/policy/changes/{change_id}/schedule",
        json={"effective_from": effective_from.isoformat()},
        headers=approver,
    )
    assert scheduled.status_code == 200, scheduled.text
    assert scheduled.json()["state"] == "scheduled"

    activated = api.post(
        f"/v1/admin/policy/changes/{change_id}/activate", headers=approver
    )
    assert activated.status_code == 200, activated.text
    assert activated.json()["state"] == "active"
    assert str(
        clarity.policies.resolve("decision.conflict_margin", as_of=datetime.now(UTC))
    ) == "0.25"


def test_a_proposal_cannot_invent_a_policy_key(api: TestClient, reviewer: dict[str, str]) -> None:
    """The artefact's tags are what decide how risky a change is, so a key
    with no artefact would route around the thing that sets the class."""
    cluster_id = _a_cluster(api, reviewer)
    api.post(f"/v1/autopsy/clusters/{cluster_id}/review", json={"accept": True}, headers=reviewer)

    invented = api.post(
        f"/v1/autopsy/clusters/{cluster_id}/rule-candidate",
        json={"key": "detection.not.a.real.key", "value": "1", "rationale": "x"},
        headers=reviewer,
    )

    assert invented.status_code == 422


def test_proposing_needs_more_than_the_right_to_review(
    api: TestClient, agent: dict[str, str]
) -> None:
    """Reviewing and drafting a rule are different judgements. An agent holds
    neither; this asserts the route is not merely gated on reading."""
    cluster_id = _a_cluster(api, agent)

    refused = api.post(
        f"/v1/autopsy/clusters/{cluster_id}/rule-candidate",
        json={"key": "detection.vas.window", "value": "48h", "rationale": "x"},
        headers=agent,
    )

    assert refused.status_code == 403
