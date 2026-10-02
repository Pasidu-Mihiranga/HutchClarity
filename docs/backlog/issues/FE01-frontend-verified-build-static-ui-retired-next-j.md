# [FE01] Frontend: verified build, static UI retired, Next.js 16, accessibility and language review

| Field | Value |
|---|---|
| Wave | W5 Frontend and hardening |
| Area | `frontend` |
| Priority | P1 |
| Depends on | [B09](B09-frontend-sdk-generated-from-openapi-checked-in-c.md) |
| Plan | 19 §2.2 |
| Labels | `wave:w5`, `area:frontend`, `priority:p1`, `type:feature` |

## Context
Next.js 14 apps; build not verified on dev; static UI still served.

## Scope
- Green build in CI (blocking); retire `interfaces/http/static` once parity is shown
- Upgrade to Next.js 16; axe checks; native-speaker review of si/ta strings

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | the four journeys | driven in the Next.js apps | pass in Playwright | `frontend e2e` |
| 2 | each page | axe run | no serious violations | `frontend e2e` |

## Definition of Done
- [ ] Every acceptance test above exists, fails before the change and passes after it
- [ ] `make check` green: lint, format, `mypy --strict`, import contracts, module boundaries, dependency map, all tests
- [ ] R0 acceptance suite green; OpenAPI snapshot unchanged, or regenerated on purpose with a CHANGELOG entry
- [ ] New call edges or events declared (plan 21 §11.2, §11.3; `test_module_dependencies.py`)
- [ ] Docs per the AGENTS.md sync matrix: `MODULE.md`, a devlog file, `ARCHITECTURE.md` / `docs/modules.md` when structure or status changes
- [ ] No secrets, no real personal data, simulated parts labelled; no em dash; commits follow AGENTS.md §10.1
