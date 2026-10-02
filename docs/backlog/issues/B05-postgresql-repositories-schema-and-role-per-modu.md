# [B05] PostgreSQL repositories: schema and role per module, migrations, row-level security

| Field | Value |
|---|---|
| Wave | W0 Baseline wiring |
| Area | `platform` |
| Priority | P0 |
| Depends on | [B02](B02-unit-of-work-and-repository-interfaces-per-modul.md) |
| Plan | 21 §11.6 R2a.5, ADR-0013, 11 §19 |
| Labels | `wave:w0`, `area:platform`, `priority:p0`, `type:baseline` |

## Context
The `full` profile persists only the simulated HUTCH estate; Clarity's own state is in memory, so two API replicas cannot run.

## Scope
- Alembic migrations per module schema; one DB role per module with grants on its schema only
- PostgreSQL drivers for every repository from B02, passing the same parity suites
- Row-level security on customer-scoped tables keyed by `subscriber_ref` set per request
- CI `full` lane with a PostgreSQL service

## Out of scope
- Read replicas, partitioning (production tuning)

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | module A's role | it queries module B's schema | the database refuses | `backend/tests/integration/test_postgres_isolation.py` |
| 2 | a request bound to subscriber X with a bug that drops the filter | it reads cases | only X's rows are returned | `backend/tests/integration/test_postgres_rls.py` |
| 3 | two API processes on one database | 1,000 concurrent double confirms | each plan has one refund and one receipt | `backend/tests/integration/test_two_replicas.py` |

## Definition of Done
- [ ] Every acceptance test above exists, fails before the change and passes after it
- [ ] `make check` green: lint, format, `mypy --strict`, import contracts, module boundaries, dependency map, all tests
- [ ] R0 acceptance suite green; OpenAPI snapshot unchanged, or regenerated on purpose with a CHANGELOG entry
- [ ] New call edges or events declared (plan 21 §11.2, §11.3; `test_module_dependencies.py`)
- [ ] Docs per the AGENTS.md sync matrix: `MODULE.md`, a devlog file, `ARCHITECTURE.md` / `docs/modules.md` when structure or status changes
- [ ] No secrets, no real personal data, simulated parts labelled; no em dash; commits follow AGENTS.md §10.1
- [ ] Risk R28 closed in plan 14
