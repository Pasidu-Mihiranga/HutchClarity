"""The Complaint Autopsy reviewer workspace (D1).

Autopsy had a repository, an event consumer, a clustering pipeline and a
review service with `record` and `supersede`, and **no way to reach any of
it**. The only surface was `GET /v1/demo/autopsy`, a read-only view behind the
desk permission, so a cluster could be looked at and never judged. The domain
was finished and the product was not.

Four routes, and the shape of them is the argument:

``GET  /v1/autopsy/clusters``                      what is waiting to be judged
``POST /v1/autopsy/clusters/{id}/review``          confirm or reject it
``POST /v1/autopsy/clusters/{id}/supersede``       change a verdict, with a reason
``POST /v1/autopsy/clusters/{id}/rule-candidate``  propose a rule, never publish one

**Reviewing and drafting a rule are different permissions on purpose.**
`autopsy:review` says "these complaints are the same problem", which is a CX
judgement on evidence. `rule:draft` says "this is what the system should do
about it", which changes how money moves. A reviewer holding one permission
that did both would have a confirmation already halfway to a published rule.

**A rule candidate goes through governance or it does not exist** (AU02). This
module cannot write a rule pack, activate anything, or shortcut the approval
lifecycle: it creates a `PolicyChange` in the draft state and hands back its
id. Somebody with `config:approve` takes it from there, through the same
review, approve, schedule and activate path every other policy change uses.
A cluster is a hypothesis about a pattern; it is not evidence that a rule
should fire, and the gap between those two is a person.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException

from clarity.interfaces.http import trail
from clarity.interfaces.http.auth import requires
from clarity.interfaces.http.deps import ClarityDep
from clarity.interfaces.http.schemas import ApiModel
from clarity.modules.autopsy.public import ReviewRefused, staff_view
from clarity.modules.governance.public import ChangeRefused
from clarity.platform.audit.ledger import ActorKind, AuditEventType
from clarity.platform.config.artefacts import PolicyValue
from clarity.platform.config.resolver import UnknownPolicyKey
from clarity.platform.security.principal import Permission, Principal


class ReviewRequest(ApiModel):
    """A verdict on a cluster.

    `accept` rather than a status string: the vocabulary of verdicts belongs to
    the domain, and a route that took `"confirmed"` would be a second place
    those names are written down.
    """

    accept: bool
    note: str = ""


class SupersedeRequest(ApiModel):
    """A deliberate change to somebody else's verdict.

    The note is required here and optional on a first review. Changing a
    professional judgement is the case where the reason matters most, and an
    unexplained reversal is the thing an auditor asks about.
    """

    accept: bool
    note: str


class RuleCandidateRequest(ApiModel):
    """A proposal that a confirmed cluster should change a detection parameter.

    It names an **existing** policy key. Governance drafts changes to artefacts
    that already exist, with a change class derived from that artefact's tags,
    and inventing a key here would route around the thing that decides how
    risky the change is. Authoring a brand-new rule pack is a different act
    with a different lifecycle, and this route does not pretend to do it.
    """

    key: str
    value: str
    rationale: str


#: Who may rule on a cluster, and who may propose a change from one.
#:
#: Module level, not inside `register`. `from __future__ import annotations`
#: turns every annotation into a string that FastAPI resolves against the
#: *module*, so an alias created inside a function is invisible by the time it
#: is needed and the whole OpenAPI document fails to generate.
Reviewer = Annotated[Principal, Depends(requires(Permission.AUTOPSY_REVIEW))]
Drafter = Annotated[Principal, Depends(requires(Permission.RULE_DRAFT))]
DeskReader = Annotated[Principal, Depends(requires(Permission.DESK_QUEUE_READ))]


def register(app: FastAPI) -> None:
    """Register the autopsy routes on the app.

    Directly on `app`, not through a router: an included router is invisible
    to the route-classification test, so a route added that way would skip the
    I9 check entirely.
    """

    @app.get("/v1/autopsy/clusters", tags=["autopsy"])
    def list_clusters(
        clarity: ClarityDep,
        principal: DeskReader,
    ) -> dict[str, Any]:
        """The reviewer workspace: clusters, and what is known about each.

        Reading is `desk:queue:read`, not `autopsy:review`: the desk should be
        able to see what the pattern engine thinks without being able to rule
        on it. Every cluster goes through `staff_view`, so one nobody has
        checked cannot reach a screen without saying so.
        """
        workspace = clarity.autopsy.workspace()
        return {
            **workspace,
            "hypothesis": any(view["hypothesis"] for view in workspace["clusters"]),
            "note": (
                "SYNTHETIC DATA. Clusters are hypotheses until a person reviews "
                "them. A suggested mapping never activates a rule."
            ),
        }

    @app.post("/v1/autopsy/clusters/{cluster_id}/review", tags=["autopsy"])
    def review_cluster(
        cluster_id: str,
        body: ReviewRequest,
        clarity: ClarityDep,
        principal: Reviewer,
    ) -> dict[str, Any]:
        """Record a first verdict.

        Refuses a cluster that already has one. A second `review` would
        overwrite a judgement with no trace of the first, which is what
        `supersede` is for.

        The reviewer is the authenticated principal, never a field in the body:
        an anonymous verdict is not an audit record, and a verdict attributed
        to whoever the caller typed is worse than none.
        """
        try:
            updated = clarity.autopsy.review(
                cluster_id, reviewer=principal.ref, accept=body.accept, note=body.note
            )
        except ReviewRefused as refused:
            raise HTTPException(status_code=409, detail=str(refused)) from refused

        trail.record(
            clarity,
            AuditEventType.AUTOPSY_CLUSTER_REVIEWED,
            actor_ref=principal.ref,
            actor_kind=ActorKind.STAFF,
            object_ref=cluster_id,
            detail={
                "accepted": body.accept,
                "superseded": False,
                "status": updated.status.value,
            },
        )
        return staff_view(updated)

    @app.post("/v1/autopsy/clusters/{cluster_id}/supersede", tags=["autopsy"])
    def supersede_review(
        cluster_id: str,
        body: SupersedeRequest,
        clarity: ClarityDep,
        principal: Reviewer,
    ) -> dict[str, Any]:
        """Change a verdict, keeping the one it replaces.

        Both survive. A reversal that erased what it reversed would leave the
        trail saying the cluster was always judged this way.
        """
        if not body.note.strip():
            raise HTTPException(status_code=422, detail="superseding a verdict needs a reason")
        try:
            updated = clarity.autopsy.review(
                cluster_id,
                reviewer=principal.ref,
                accept=body.accept,
                note=body.note,
                supersede=True,
            )
        except ReviewRefused as refused:
            raise HTTPException(status_code=409, detail=str(refused)) from refused

        trail.record(
            clarity,
            AuditEventType.AUTOPSY_CLUSTER_REVIEWED,
            actor_ref=principal.ref,
            actor_kind=ActorKind.STAFF,
            object_ref=cluster_id,
            detail={
                "accepted": body.accept,
                "superseded": True,
                "status": updated.status.value,
            },
        )
        return staff_view(updated)

    @app.post("/v1/autopsy/clusters/{cluster_id}/rule-candidate", tags=["autopsy"])
    def propose_rule(
        cluster_id: str,
        body: RuleCandidateRequest,
        clarity: ClarityDep,
        principal: Drafter,
    ) -> dict[str, Any]:
        """Propose a policy change from a confirmed cluster (AU02).

        **This publishes nothing.** It creates a policy change in the draft
        state and returns its id; approval, scheduling and activation all
        happen through the governance routes, by somebody else. A pattern
        engine that could activate its own rule would be deciding causes from
        complaint text, which is exactly what I2 forbids.

        Refuses a cluster nobody has confirmed. A hypothesis is not grounds for
        a rule, and letting an unreviewed cluster seed one would make the
        review step decorative.
        """
        held = next(
            (item for item in clarity.autopsy.clusters() if item.cluster.cluster_id == cluster_id),
            None,
        )
        if held is None:
            raise HTTPException(status_code=404, detail="no such cluster")
        if not held.reviewed or held.latest is None or not held.latest.accepted:
            raise HTTPException(
                status_code=409,
                detail=(
                    "only a confirmed cluster may be proposed as a rule; "
                    "a hypothesis is not grounds for one"
                ),
            )

        try:
            artefact = clarity.policies.key(body.key)
        except UnknownPolicyKey as unknown:
            raise HTTPException(
                status_code=422,
                detail=f"no policy artefact named {body.key}",
            ) from unknown

        try:
            change = clarity.governance.draft(
                key=body.key,
                candidate=PolicyValue(value=body.value),
                # From the artefact's own tags, never from this request. A
                # caller who could choose the class could choose how many
                # approvals their change needs.
                computed_class=artefact.change_class,
                maker_ref=principal.ref,
                reason=(
                    f"Complaint Autopsy cluster {cluster_id}, confirmed by "
                    f"{held.latest.reviewer}. {body.rationale}"
                ),
            )
        except ChangeRefused as refused:
            raise HTTPException(status_code=409, detail=str(refused)) from refused

        trail.record(
            clarity,
            AuditEventType.AUTOPSY_RULE_PROPOSED,
            actor_ref=principal.ref,
            actor_kind=ActorKind.STAFF,
            object_ref=cluster_id,
            detail={"change_id": change.change_id, "key": body.key},
        )
        return {
            "change_id": change.change_id,
            "state": change.state.value,
            "cluster_id": cluster_id,
            "note": (
                "A draft policy change, not a rule. It activates only through "
                "the governance lifecycle, approved by somebody else."
            ),
        }


__all__ = ["ReviewRequest", "RuleCandidateRequest", "SupersedeRequest", "register"]
