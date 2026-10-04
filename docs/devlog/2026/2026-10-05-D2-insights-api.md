# 2026-10-05 - D2 - Insights as a real resource

| Field | Value |
|---|---|
| Author(s) | Pasidu-Mihiranga; agent: Claude Code |
| Work package | D2 (Workstream D, "Insights as a real resource") |
| PR / commit | feat/insights-api / 83ec5d5 |
| Units touched | interfaces/http, frontend/apps/console, frontend/packages/sdk |

Written after the commit rather than with it.

## What changed

- New `GET /v1/insights/dashboards`, returning the same projections the
  insights service already folds from the event log.
- SDK: `insightsDashboards()`.
- `frontend/apps/console/app/insights/page.tsx` reads it instead of
  `client.demoOps()`.
- 6 acceptance tests in `backend/tests/acceptance/test_insights_api.py`.

## Why

Workstream D2. `InsightsService` already folded real projections; the only way
to reach them was `GET /v1/demo/ops`, a demo-namespaced route. A dashboard that
the console depends on should not live behind a name that says it is a demo.

## Decisions made

- **Same numbers, asserted.** `test_the_real_route_answers_the_same_numbers_as_the_demo_one`
  pins the new route to the old one while both exist, so D4 can delete the demo
  route knowing nothing moved.
- **Read permission only.** The route exposes aggregates, not customer records,
  and is gated like the rest of the insights surface rather than opened up.

## Docs updated

- [x] CHANGELOG.md / contracts (OpenAPI golden and `contracts/openapi.json`
      regenerated, SDK schema regenerated)
- [x] `backend/tests/acceptance/test_route_contract.py`
- [ ] MODULE.md: the insights module's public surface did not change; this
      exposes an existing service method over HTTP.
- [ ] Walkthrough: none yet for the insights console.

## Tests

- `backend/tests/acceptance/test_insights_api.py` - 6 passed.
- `make check` - green.

## Open issues / next step

- `GET /v1/demo/ops` still exists and is now unused by the console. D4 removes
  it, together with the equivalence test that exists only to guard the move.
