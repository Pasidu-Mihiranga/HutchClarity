# 2026-10-05 - E5 - SDK client typed from the OpenAPI schema

| Field | Value |
|---|---|
| Author(s) | Pasidu-Mihiranga; agent: Claude Code (the merge with main) |
| Work package | Workstream E5 (enterprise UI plan) |
| PR / commit | feat/sdk-typed-client |
| Units touched | frontend/packages/sdk, frontend/apps/console, frontend/apps/customer-web, frontend/scripts |

## What changed
- Every `ClarityClient` method now goes through `call` or `declared`, which take a path from the generated `paths`, a method that path defines, and its params, query and body. A renamed or removed route, or a wrong method, is a `tsc` error.
- Modelled responses (cases, decisions, timeline, plans, executions, session, receipts verdict, queue, demo subscribers) now return the generated schema types. The `[key: string]: unknown` escape hatches are gone.
- Routes the backend answers with an open dictionary keep a hand-written shape, now in one file (`types.ts`), each citing its handler. `declared` refuses a route whose response the schema already types, so a hand type disappears when the backend publishes a model.
- New methods for routes that existed and were never called: `myApp`, `myHome`, `myCases`, `myReceipts`, `reload`, `purchasePackage`, `cancelSubscription`, `setSafeguard`, `addFamilyMember`, `savePreferences`, `confirmCase`, `refreshSession`, `logout`, `stepUp`, `signInMethods`, `listSessions`, `endOtherSessions`, `oidcStartUrl`.
- `npm run typecheck` now runs `tsc --noEmit` in every workspace that defines the script (sdk, customer-web, console, verify; ui via the design-system branch), not only the SDK.
- Console `StaffSessionProvider` uses the client instead of four raw `fetch` calls.
- `check-sdk.mjs` works on Windows (shell for npx, CRLF-insensitive compare).
- Vitest tests for the SDK: URL and body building, server-default fill-in, CSRF and bearer headers, error mapping, and a test that every route in `client.ts` exists in `contracts/openapi.json`.

## Why
A call to a method that did not exist shipped because the client imported neither the generated schema nor the route list, and `typecheck` never looked at the apps. Making the schema the only source closes that.

## Decisions made
- No codegen step for method bodies: a thin typed `call` over `paths` keeps the surface small and reviewable, and needs no new dependency.
- Generated types mark defaulted request fields required, so the client fills the defaults (`channel: "web"`, `step_up: false`, ...) and accepts them as optional. `SessionView.roles` and `permissions` are normalised to arrays for the same reason.
- Backend routes that return `dict[str, Any]` (`/v1/me/*`, audit, alerts, switches, auth sessions) should get response models. Not done here: it is a backend change in a file other work is touching. Until then they are the declared types.
- Stricter types found real issues: `ApproveResult` can be a 202 pending-approval body, which the desk page now narrows with `"detail" in body`.

## Docs updated
- [ ] MODULE.md: n/a
- [ ] CHANGELOG.md: n/a (no /v1 change)
- [x] This devlog

## Tests
- `npm run typecheck`: clean in sdk, customer-web, console and verify (the ui package joins once the design-system branch is merged).
- `npm test -w @clarity/sdk`: 12 passed. `npm run sdk:check`: schema types current.
- `npm run build`: all three apps compile.
- Not run: Playwright (`make e2e`).

## Merged with main (2026-10-05)

This branch predated D1-D4, E1 and Workstream C, all of which landed on `main`
while it was open, and three of them added methods to the file this rewrite
replaces. The merge re-added every one of them through `call` or `declared`:

- `insightsDashboards` (D2).
- `policyChanges`, `draftPolicyChange`, `reviewPolicyChange`,
  `approvePolicyChange`, `schedulePolicyChange`, `activatePolicyChange`,
  `rollbackPolicyChange` (D3).
- `autopsyClusters`, `reviewCluster`, `supersedeClusterReview`,
  `proposeRuleCandidate` (D1).
- `foresightScenarios`, `foresightScenario`, `foresightRuns`, `foresightRun`,
  `requestForesightRun`, `foresightCalibration`, `foresightSpikes` (C4).
- `demoOps`, `demoAutopsy` and `demoForesight` dropped: D4 retired all three
  routes, so the typed client would not compile against them anyway, which is
  the point of typing it.
- Their eleven types moved from `client.ts` into `types.ts`, where the
  hand-declared shapes now live.

Two changes to the machinery were needed:

- **`CallOptions` gained `headers`.** There was no way to send one, and
  `POST /v1/foresight/runs` requires `Idempotency-Key` (I8). Kept as a plain
  record rather than typed from the schema's `header` parameters, which the
  generator models inconsistently enough to reject calls the backend accepts.
- **`omittingServerDefaults`.** The typed call caught four request bodies that
  disagreed with the generated types: `version`, `candidate_summary`, `note`
  and `seed`. The disagreement is the generator's: `openapi-typescript` marks
  any property carrying a `default` as non-optional, which is correct for a
  response and wrong for a request body, where omitting the field is how the
  caller asks for the default. The OpenAPI document has all four outside their
  `required` array. The helper lets an omitted field through and never invents
  a value, because writing the server's default into the client would pin it
  here and diverge the day the backend changed it.

Also resolved: both branches had independently fixed `check-sdk.mjs` for
Windows, so the merge kept one copy of the fix.

## Open issues / next step
E4 uses the new `my*` methods. The backend routes that return `dict[str, Any]`
still need response models; until they have them, `types.ts` carries the
declared shapes and `declared` refuses any route the schema already types, so
each hand-written type disappears on its own when the backend publishes one.
