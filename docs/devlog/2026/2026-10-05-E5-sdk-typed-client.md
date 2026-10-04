# 2026-10-05 - E5 - SDK client typed from the OpenAPI schema

| Field | Value |
|---|---|
| Author(s) | Pasidu-Mihiranga |
| Work package | Workstream E5 (enterprise UI plan) |
| PR / commit | feat/sdk-typed-client |
| Units touched | frontend/packages/sdk, frontend/apps/console, frontend/apps/customer-web, frontend/scripts |

## What changed
- Every `ClarityClient` method now goes through `call` or `declared`, which take a path from the generated `paths`, a method that path defines, and its params, query and body. A renamed or removed route, or a wrong method, is a `tsc` error.
- Modelled responses (cases, decisions, timeline, plans, executions, session, receipts verdict, queue, demo subscribers) now return the generated schema types. The `[key: string]: unknown` escape hatches are gone.
- Routes the backend answers with an open dictionary keep a hand-written shape, now in one file (`types.ts`), each citing its handler. `declared` refuses a route whose response the schema already types, so a hand type disappears when the backend publishes a model.
- New methods for routes that existed and were never called: `myApp`, `myHome`, `myCases`, `myReceipts`, `reload`, `purchasePackage`, `cancelSubscription`, `setSafeguard`, `addFamilyMember`, `savePreferences`, `confirmCase`, `refreshSession`, `logout`, `stepUp`, `signInMethods`, `listSessions`, `endOtherSessions`, `oidcStartUrl`.
- `npm run typecheck` now runs `tsc --noEmit` in every workspace (sdk, ui, customer-web, console, verify), not only the SDK.
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
- `npm run typecheck`: clean in all five workspaces.
- `npm test -w @clarity/sdk`: 12 passed. `npm run sdk:check`: schema types current.
- `npm run build`: all three apps compile.
- Not run: Playwright (`make e2e`).

## Open issues / next step
Branches that add SDK methods (the autopsy, insights and policy-studio branches) will conflict with this rewrite of `client.ts`; re-add their methods through `call` or `declared`. E4 uses the new `my*` methods.
