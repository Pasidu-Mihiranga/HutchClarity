# 2026-10-05 - D4 - Retire the demo routes

| Field | Value |
|---|---|
| Author(s) | Pasidu-Mihiranga; agent: Claude Code |
| Work package | D4 (Workstream D, "Retire the demo routes") |
| PR / commit | feat/retire-demo-routes |
| Units touched | app/container, interfaces/http, modules/autopsy, modules/insights, frontend/apps/console, frontend/packages/sdk |

## What changed

- Deleted `GET /v1/demo/ops` and `GET /v1/demo/autopsy` from
  `interfaces/http/main.py`, and `demoOps()` / `demoAutopsy()` from the SDK.
- Moved the synthetic complaint seeding out of the deleted `demo/autopsy` route
  into `Clarity._seed_synthetic_complaints`, called from the composition root
  for every profile that is not `prod`.
- `frontend/apps/console/app/insights/page.tsx` reads `client.autopsyClusters()`
  instead of `client.demoAutopsy()`, and the cluster list is typed as
  `AutopsyWorkspace` rather than `Record<string, unknown>` with a cast.
- Removed both routes from `SYNTHETIC_ONLY` in `test_route_contract.py`.
- Replaced `test_the_real_route_answers_the_same_numbers_as_the_demo_one` with
  `test_the_demo_address_is_gone`, asserting 404.
- Regenerated the OpenAPI golden, `contracts/openapi.json` and the SDK schema.
- Fixed `frontend/scripts/check-sdk.mjs` on Windows.

## Why

Workstream D4. D1 and D2 gave autopsy and insights surfaces of their own, which
left two routes tagged `demo` serving data a console depends on. Two addresses
for one resource is how a console ends up reading the demo one again.

## Decisions made

- **`GET /v1/demo/foresight` stays. This deviates from the written D4 scope,
  which said to delete all three.** Workstream C was never built, so foresight
  has no persistence, no API and no permissions of its own, and the foresight
  console has nothing else to read. Deleting the route would blank a working
  screen without making anything more honest. The SDK method carries a comment
  saying exactly this so the next person does not think it was an oversight.
- **The synthetic seed belongs in the composition root, not in a route.** The
  deleted route seeded the dataset lazily on first read, so a GET wrote to a
  store. The replacement route could not inherit that: a production-shaped
  route must not import `integration.drivers.mock`. The container is the only
  place allowed to know which profile it is building (I20) and already decides
  every other synthetic-versus-real driver, so it is where this goes.
- **The seed is best effort and logs rather than raises.** A console with an
  empty cluster list is a better outcome than a process that will not start.
- **Kept the 404 assertion after deleting the route.** The equivalence test
  existed only to make the move safe while both routes lived. The property
  worth keeping afterwards is that the old address does not quietly come back.
- **`demo/reset`, `demo/inbox` and `demo/subscribers` stay** as
  `SYNTHETIC_ONLY`. They describe the simulated world rather than serving a
  product surface, and nothing replaces them.

## Docs updated

- [x] MODULE.md of: modules/autopsy (used-by, seeding, history),
      modules/insights (used-by, migration status, history)
- [x] CHANGELOG.md / contracts (a `Removed` section; OpenAPI golden,
      `contracts/openapi.json` and the SDK schema regenerated)
- [x] Walkthrough: `docs/walkthroughs/WT-13-staff-console.md` steps 8 and 9
      rewritten for the D3 and D1 flows, with a re-verification note
- [x] `frontend/README.md` console route list
- [ ] ARCHITECTURE.md / modules.md: no module, edge or event changed.
- [ ] Plan via CHANGES.md: no plan chapter edited. The foresight deviation is
      recorded here and in the CHANGELOG rather than as a plan edit, because
      the plan's D4 line is a scope statement and this is a deliberate
      departure from it, not a correction to it.

## Tests

- `tests/acceptance/test_insights_api.py`, `test_autopsy_api.py`,
  `test_route_contract.py` - 114 passed.
- `ruff check` and `ruff format --check` - clean, after `--fix` removed an
  unused `noqa` and reformatted one line.
- `mypy` - "Success: no issues found in 247 source files".
- `lint-imports` - "Contracts: 3 kept, 0 broken."
- Full `pytest` - ran to 100% with no failures or errors reported. The run was
  interrupted before the summary line printed, so the pass count is not
  recorded here; the character output showed no `F` or `E`.
- `npm run sdk:check` - "SDK types match the committed OpenAPI schema." This is
  the first time it has run on this machine; see below.
- `npx tsc -p packages/sdk/tsconfig.json --noEmit` - clean.
- `npm run build --workspace=apps/console` - compiled, 11/11 pages.
- Not run: `make e2e`. The Playwright suite covers the console sign-in and desk
  paths and has no autopsy, insights or studio spec, so it would not exercise
  anything this change touches. Workstream E6 adds those specs.

## Open issues / next step

- **The SDK guard had never run on Windows.** `check-sdk.mjs` called
  `execFileSync("npx", ...)`, and `execFileSync` does not resolve `PATHEXT`, so
  `npx.cmd` was never found and the script threw `ENOENT` instead of comparing
  anything. Fixed with `shell: process.platform === "win32"`. Worth knowing
  that this guard was decorative on this platform for however long it has been
  there; CI runs on Linux, so CI was fine and the local check was not.
- Workstream D is complete: D1, D2, D3 and D4 are all landed. The remaining
  console gap is foresight, which needs Workstream C before it can come off its
  demo route.
- WT-13 steps 8 and 9 need a browser walk to be genuinely re-verified.
