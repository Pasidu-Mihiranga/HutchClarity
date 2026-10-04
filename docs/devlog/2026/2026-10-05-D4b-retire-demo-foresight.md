# 2026-10-05 - D4b - Retire the last demo route and put the console on /v1/foresight

| Field | Value |
|---|---|
| Author(s) | Pasidu-Mihiranga; agent: Claude Code |
| Work package | D4, the part deferred until Workstream C landed |
| PR / commit | feat/retire-demo-foresight, stacked on feat/foresight-complete |
| Units touched | interfaces/http, modules/foresight (docs), frontend/apps/console, frontend/packages/sdk |

## What changed

- Deleted `GET /v1/demo/foresight` and removed it from `SYNTHETIC_ONLY` in
  `test_route_contract.py`. No demo route serves a product surface any more.
- SDK: `demoForesight()` replaced by `foresightScenarios`, `foresightScenario`,
  `foresightRuns`, `foresightRun`, `requestForesightRun`,
  `foresightCalibration` and `foresightSpikes`, with typed `ScenarioView`,
  `ForesightRun`, `ForesightReport`, `ForesightPrediction`,
  `ForesightCalibration` and `ForesightSpike`.
- `apps/console/app/foresight/page.tsx` rewritten: lists scenarios, requests a
  run, polls it, renders the stored report with its basis and caveats, the
  calibration panel and the radar's spikes. Built on the E1 design system
  (`Table`, `Select`, `Alert`, `EmptyState`, `Spinner`).
- `apps/console/app/insights/page.tsx` reads the latest succeeded run's stored
  report instead of rehearsing one per page load.
- De-duplicated `modules/foresight/MODULE.md`, which the C merge had left with
  two "Used by" paragraphs and two "Events" tables.
- Regenerated the OpenAPI contract, the golden snapshot and the SDK schema.

## Why

The D4 PR kept this route with a stated reason: Workstream C had not reached
`main`, foresight had no API, and deleting the route would have blanked a
working screen. `feat/foresight-complete` lands C, so the reason expired and
leaving the route would have left a stale justification in the CHANGELOG and a
console reading a demo endpoint next to a real API.

## Decisions made

- **Permissions, not the desk's.** The old route was gated on
  `desk:queue:read`; the real routes use `foresight:read` and `foresight:run`.
  The foresight page now gates on `foresight:read`, and the Insights page,
  which is a desk page, asks for its foresight panel **separately** and shows a
  note when the reader holds neither. A single `Promise.all` would have failed
  the whole Insights page with a 403 for every desk agent.
- **The calibration badge comes from the API.** The page hard-coded
  "NOT CALIBRATED". It happened to be true, which is the problem: it was not
  something the page had checked. It now reads
  `GET /v1/foresight/calibration`, and renders the status the API reports.
- **A fresh `Idempotency-Key` per click.** The run route requires the header
  (I8). Minting a new key per press means a press is a new rehearsal; reusing
  one would return the original run, which is what the header is for and what
  the `replayed` badge shows.
- **Stored reports, not a rehearsal per request.** The demo route built a
  scenario, ran it and discarded the result on every call, so nothing it
  displayed could be cited later. Both pages now read stored runs.
- **The page records no outcomes.** `foresight:outcome:record` is deliberately
  absent from `Role.PRODUCT`, because the person who wants the calibration gate
  open must not be the one recording the evidence that opens it. The console
  offers no way to record one, so the separation is not left to a permission
  check alone.
- **404 on calibration is not an error.** No backtest having run is the normal
  state, so it renders as a sentence rather than a red banner.

## Docs updated

- [x] MODULE.md of: modules/foresight (used-by, events, de-duplicated)
- [x] CHANGELOG.md, replacing the stale "Workstream C has not been built" note
- [x] contracts: OpenAPI golden, `contracts/openapi.json`, SDK schema
- [x] `frontend/README.md` console route list
- [x] Walkthrough `WT-13-staff-console.md` step 10, now 10, 10a and 10b
- [ ] Plan via CHANGES.md: no plan chapter edited.
- [ ] ARCHITECTURE.md / modules.md: no module, edge or event changed.

## Tests

- `ruff check` and `ruff format --check` - clean, 415 files, after `--fix`
  removed a `datetime.date` import the deleted route was the last user of.
- `mypy --strict` - "Success: no issues found in 253 source files".
- `pytest tests/acceptance tests/architecture` - all passed.
- `npm run sdk:check` - "SDK types match the committed OpenAPI schema."
- `npx tsc -p packages/sdk/tsconfig.json --noEmit` - clean.
- `npm run build --workspace=apps/console` - compiled, 9/9 routes. One fix on
  the way: the E1 `Table` requires a `caption`, which is an accessibility
  constraint the old hand-rolled `<table>` did not have.
- Not run: `make e2e`. There is no foresight spec; E6 adds one.

## Open issues / next step

- WT-13 steps 8-10b have not been walked in a browser. The routes are covered
  by acceptance tests, the click path is not.
- The foresight page has no component or e2e test, same as autopsy, insights
  and studio. That is the Workstream E6 gap, now four pages wide.
- No demo-namespaced route serves a product surface any more.
  `POST /v1/demo/reset`, `GET /v1/demo/inbox` and `GET /v1/demo/subscribers`
  remain and describe the simulated world rather than a feature.
