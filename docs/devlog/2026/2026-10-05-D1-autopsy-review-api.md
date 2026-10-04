# 2026-10-05 - D1 - Autopsy review API

| Field | Value |
|---|---|
| Author(s) | Pasidu-Mihiranga; agent: Claude Code |
| Work package | D1 (Workstream D, "Autopsy write path") |
| PR / commit | feat/autopsy-review-api / c421284 |
| Units touched | modules/autopsy, interfaces/http, platform/security, platform/audit, frontend/apps/console, frontend/packages/sdk |

Written after the commit rather than with it. The entry for D2 is in
`2026-10-05-D2-insights-api.md`.

## What changed

- New `backend/src/clarity/interfaces/http/autopsy_api.py` with four routes:
  `GET /v1/autopsy/clusters`, `POST /v1/autopsy/clusters/{id}/review`,
  `POST .../supersede`, `POST .../rule-candidate`.
- New permission `autopsy:review`, granted to `Role.SUPERVISOR` and
  `Role.CX_ENGINEER`, mirrored into `config/opa/data.json`.
- New audit event types `AUTOPSY_CLUSTER_REVIEWED` and `AUTOPSY_RULE_PROPOSED`.
- `frontend/apps/console/app/autopsy/page.tsx` rewritten from a read-only view
  of `/v1/demo/autopsy` onto the new routes, with confirm, reject and
  supersede-with-reason, each gated on the permission the route checks.
- SDK: `autopsyClusters`, `reviewCluster`, `supersedeClusterReview`,
  `proposeRuleCandidate`, types `AutopsyCluster` and `AutopsyWorkspace`.
- 13 acceptance tests in `backend/tests/acceptance/test_autopsy_api.py`.

## Why

Workstream D1 and backlog UI02/AU02. The autopsy module already had a
repository, an event consumer, a clustering pipeline and a review service with
`record` and `supersede`. The only HTTP surface was one read-only demo route,
so a cluster could be looked at and never judged: the domain was finished and
the product was not.

## Decisions made

- **Reading and ruling are different permissions.** The list route checks
  `desk:queue:read`, the verdict routes check `autopsy:review`. An agent can
  see what the pattern engine thinks without being able to decide it is right.
- **Proposing a rule needs `rule:draft` on top.** "These complaints are the
  same problem" is a CX judgement; "this is what the system should do about
  it" changes how money moves.
- **A rule candidate names an existing policy artefact** and cannot invent a
  key. `governance.draft` derives the change class from the artefact's tags, so
  an invented key would route around the thing that decides how many approvals
  the change needs. Unknown key gives 422.
- **Only a confirmed cluster may propose** (AU02). A hypothesis seeding a rule
  would make the review step decorative. Unreviewed or rejected gives 409.
- **The proposal creates a draft and nothing more.** No rule pack is written
  and nothing activates; the change goes through the same governance path as
  any other.
- **The reviewer is the authenticated principal, never a body field.** An
  anonymous verdict is not an audit record, and one attributed to whatever the
  caller typed is worse than none.
- **Routes registered directly on `app`, not via an `APIRouter`.** An included
  router is invisible to the route-classification test, so a route added that
  way would skip the I9 check.

## Docs updated

- [x] MODULE.md of: modules/autopsy
- [x] CHANGELOG.md / contracts (OpenAPI golden and `contracts/openapi.json`
      regenerated, SDK schema regenerated)
- [x] `backend/tests/acceptance/test_route_contract.py` classifications
- [ ] ARCHITECTURE.md / modules.md: no new module or module-to-module edge.
      The rule-candidate route calls governance from the HTTP layer, which is
      an interface composing two modules, not a new dependency between them.
- [ ] Walkthrough: none yet for the autopsy reviewer flow.

## Tests

- `backend/tests/acceptance/test_autopsy_api.py` - 13 passed.
- OPA parity suite against a real OPA container - 40 passed, after a fix: the
  permission first landed on `Role.VAS_OPS` instead of `Role.SUPERVISOR` and
  the parity test caught it.
- `make check` - green.

## Open issues / next step

- The dependency alias trap bit again: `Reviewer` and `Drafter` defined inside
  `register()` under `from __future__ import annotations` made the whole
  OpenAPI document fail to generate. They are module level now, with a comment.
  This is the third time; it is worth an architecture test.
- `GET /v1/demo/autopsy` still exists and is now unused by the console. D4
  removes it.
