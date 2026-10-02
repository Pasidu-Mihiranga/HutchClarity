# [B09] Frontend SDK generated from OpenAPI, checked in CI

| Field | Value |
|---|---|
| Wave | W0 Baseline wiring |
| Area | `frontend` |
| Priority | P1 |
| Depends on | none |
| Plan | 19 §2.2, B10 |
| Labels | `wave:w0`, `area:frontend`, `priority:p1`, `type:baseline` |

## Context
The handwritten SDK drifted (`detect`, `decide` call routes that do not exist).

## Scope
- Generate types and client from `/openapi.json` (openapi-typescript or similar)
- CI fails if the generated SDK differs from the committed one
- Remove the two unserved methods

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | a backend route renamed | CI runs | the frontend job fails until the SDK is regenerated | `CI` |
| 2 | the generated SDK | type-checked against all apps | no errors | `frontend `npm run build`` |

## Definition of Done
- [ ] Every acceptance test above exists, fails before the change and passes after it
- [ ] `make check` green: lint, format, `mypy --strict`, import contracts, module boundaries, dependency map, all tests
- [ ] R0 acceptance suite green; OpenAPI snapshot unchanged, or regenerated on purpose with a CHANGELOG entry
- [ ] New call edges or events declared (plan 21 §11.2, §11.3; `test_module_dependencies.py`)
- [ ] Docs per the AGENTS.md sync matrix: `MODULE.md`, a devlog file, `ARCHITECTURE.md` / `docs/modules.md` when structure or status changes
- [ ] No secrets, no real personal data, simulated parts labelled; no em dash; commits follow AGENTS.md §10.1
