# [B07] Typed settings and profile wiring: no environment reads outside the composition root

| Field | Value |
|---|---|
| Wave | W0 Baseline wiring |
| Area | `app` |
| Priority | P1 |
| Depends on | none |
| Plan | ADR-0027, I20 |
| Labels | `wave:w0`, `area:app`, `priority:p1`, `type:baseline` |

## Context
`integration/drivers/mock/store/db.py` reads `DATABASE_URL` itself; settings are scattered.

## Scope
- One `Settings` model (pydantic-settings) loaded in `app.container`; drivers receive values, never read env
- `.env.example` lists every variable with comments
- Startup fails fast with a clear message on invalid settings

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | any module outside `app.container` | source is scanned | no `os.environ` / `getenv` reads remain | `backend/tests/architecture/test_settings.py` |
| 2 | `CLARITY_PROFILE=full` with no `DATABASE_URL` | the app starts | it stops with a message naming the variable | `backend/tests/unit/test_settings.py` |

## Definition of Done
- [ ] Every acceptance test above exists, fails before the change and passes after it
- [ ] `make check` green: lint, format, `mypy --strict`, import contracts, module boundaries, dependency map, all tests
- [ ] R0 acceptance suite green; OpenAPI snapshot unchanged, or regenerated on purpose with a CHANGELOG entry
- [ ] New call edges or events declared (plan 21 §11.2, §11.3; `test_module_dependencies.py`)
- [ ] Docs per the AGENTS.md sync matrix: `MODULE.md`, a devlog file, `ARCHITECTURE.md` / `docs/modules.md` when structure or status changes
- [ ] No secrets, no real personal data, simulated parts labelled; no em dash; commits follow AGENTS.md §10.1
